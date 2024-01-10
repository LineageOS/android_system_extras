/*
 * Copyright (C) 2015 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <sched.h>
#include <stdio.h>

#include <atomic>
#include <map>
#include <string>
#include <thread>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>

#include "ETMRecorder.h"
#include "command.h"
#include "environment.h"
#include "event_attr.h"
#include "event_fd.h"
#include "event_selection_set.h"
#include "event_type.h"

namespace simpleperf {
namespace {

struct RawEventTestThreadArg {
  int cpu;
  std::atomic<pid_t> tid;
  std::atomic<bool> start;
};

static void RawEventTestThread(RawEventTestThreadArg* arg) {
  cpu_set_t mask;
  CPU_ZERO(&mask);
  CPU_SET(arg->cpu, &mask);
  int tid = gettid();
  sched_setaffinity(tid, sizeof(mask), &mask);
  arg->tid = tid;
  while (!arg->start) {
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  TemporaryFile tmpfile;
  FILE* fp = fopen(tmpfile.path, "w");
  if (fp == nullptr) {
    return;
  }
  for (int i = 0; i < 10; ++i) {
    fprintf(fp, "output some data\n");
  }
  fclose(fp);
}

struct RawEventSupportStatus {
  std::vector<int> supported_cpus;
  std::vector<int> may_supported_cpus;
};

class RawEventSupportChecker {
 public:
  bool Init() {
#if defined(__aarch64__) || defined(__arm__)
    cpu_models_ = GetARMCpuModels();
    if (cpu_models_.empty()) {
      LOG(ERROR) << "can't get device cpu info";
      return false;
    }
#endif  // defined(__aarch64__) || defined(__arm__)
    return true;
  }

  RawEventSupportStatus GetCpusSupportingEvent(const EventType& event_type) {
    RawEventSupportStatus status;
    for (const auto& model : cpu_models_) {
      bool supported;
      bool may_supported;
      TestEventSupportOnCpu(event_type, model.cpus[0], supported, may_supported);

      if (supported) {
        status.supported_cpus.insert(status.supported_cpus.end(), model.cpus.begin(),
                                     model.cpus.end());
      } else if (may_supported) {
        status.may_supported_cpus.insert(status.may_supported_cpus.end(), model.cpus.begin(),
                                         model.cpus.end());
      }
    }
    return status;
  }

 private:
  void TestEventSupportOnCpu(const EventType& event_type, int cpu, bool& supported,
                             bool& may_supported) {
    // Because the kernel may not check whether the raw event is supported by the cpu pmu.
    // We can't decide whether the raw event is supported by calling perf_event_open().
    // Instead, we can check if it can collect some real number.
    RawEventTestThreadArg test_thread_arg;
    test_thread_arg.cpu = cpu;
    test_thread_arg.tid = 0;
    test_thread_arg.start = false;
    std::thread test_thread(RawEventTestThread, &test_thread_arg);
    while (test_thread_arg.tid == 0) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    perf_event_attr attr = CreateDefaultPerfEventAttr(event_type);
    std::unique_ptr<EventFd> event_fd = EventFd::OpenEventFile(
        attr, test_thread_arg.tid, test_thread_arg.cpu, nullptr, event_type.name, false);
    test_thread_arg.start = true;
    test_thread.join();
    if (event_fd == nullptr) {
      supported = may_supported = false;
      return;
    }
    PerfCounter counter;
    if (!event_fd->ReadCounter(&counter)) {
      supported = may_supported = false;
      return;
    }
    if (counter.value != 0) {
      supported = true;
      may_supported = false;
    } else {
      supported = false;
      may_supported = true;
    }
  }

  std::vector<ARMCpuModel> cpu_models_;
};

static std::string ToCpuString(const std::vector<int>& cpus) {
  std::string s;
  if (cpus.empty()) {
    return s;
  }
  s += std::to_string(cpus[0]);
  int last_cpu = cpus[0];
  bool added = true;
  for (size_t i = 1; i < cpus.size(); ++i) {
    if (cpus[i] == last_cpu + 1) {
      last_cpu = cpus[i];
      added = false;
    } else {
      s += "-" + std::to_string(last_cpu) + "," + std::to_string(cpus[i]);
      last_cpu = cpus[i];
      added = true;
    }
  }
  if (!added) {
    s += "-" + std::to_string(last_cpu);
  }
  return s;
}

static void PrintRawEventTypes(const std::string& type_desc) {
  printf("List of %s:\n", type_desc.c_str());
#if defined(__aarch64__) || defined(__arm__)
  printf(
      // clang-format off
"  # Please refer to \"PMU common architectural and microarchitectural event numbers\"\n"
"  # and \"ARM recommendations for IMPLEMENTATION DEFINED event numbers\" listed in\n"
"  # ARMv9 manual for details.\n"
"  # A possible link is https://developer.arm.com/documentation/ddi0487.\n"
      // clang-format on
  );
#endif  // defined(__aarch64__) || defined(__arm__)
  RawEventSupportChecker support_checker;
  if (!support_checker.Init()) {
    return;
  }
  auto callback = [&](const EventType& event_type) {
    if (event_type.type != PERF_TYPE_RAW) {
      return true;
    }
    RawEventSupportStatus status = support_checker.GetCpusSupportingEvent(event_type);
    if (status.supported_cpus.empty() && status.may_supported_cpus.empty()) {
      return true;
    }
    std::string text = "  " + event_type.name + " (";
    if (!status.supported_cpus.empty()) {
      text += "supported on cpu " + ToCpuString(status.supported_cpus);
      if (!status.may_supported_cpus.empty()) {
        text += ", ";
      }
    }
    if (!status.may_supported_cpus.empty()) {
      text += "may supported on cpu " + ToCpuString(status.may_supported_cpus);
    }
    text += ")";
    printf("%s", text.c_str());
    if (!event_type.description.empty()) {
      printf("\t\t# %s", event_type.description.c_str());
    }
    printf("\n");
    return true;
  };
  EventTypeManager::Instance().ForEachType(callback);
  printf("\n");
}

static bool IsEventTypeSupported(const EventType& event_type) {
  // Because PMU events are provided by kernel, we assume it's supported.
  if (event_type.IsPmuEvent()) {
    return true;
  }
  perf_event_attr attr = CreateDefaultPerfEventAttr(event_type);
  // Exclude kernel to list supported events even when kernel recording isn't allowed.
  attr.exclude_kernel = 1;
  return IsEventAttrSupported(attr, event_type.name);
}

static void PrintEventTypesOfType(const std::string& type_name, const std::string& type_desc,
                                  const std::function<bool(const EventType&)>& is_type_fn) {
  if (type_name == "raw") {
    return PrintRawEventTypes(type_desc);
  }
  printf("List of %s:\n", type_desc.c_str());
  if (GetTargetArch() == ARCH_ARM || GetTargetArch() == ARCH_ARM64) {
    if (type_name == "cache") {
      printf("  # More cache events are available in `simpleperf list raw`.\n");
    }
  }
  auto callback = [&](const EventType& event_type) {
    if (is_type_fn(event_type)) {
      if (!IsEventTypeSupported(event_type)) {
        return true;
      }
      printf("  %s", event_type.name.c_str());
      if (!event_type.description.empty()) {
        printf("\t\t# %s", event_type.description.c_str());
      }
      printf("\n");
    }
    return true;
  };
  EventTypeManager::Instance().ForEachType(callback);
  printf("\n");
}

class ListCommand : public Command {
 public:
  ListCommand()
      : Command("list", "list available event types",
                // clang-format off
"Usage: simpleperf list [options] [hw|sw|cache|raw|tracepoint|pmu]\n"
"       List all available event types.\n"
"       Filters can be used to show only event types belong to selected types:\n"
"         hw          hardware events\n"
"         sw          software events\n"
"         cache       hardware cache events\n"
"         raw         raw cpu pmu events\n"
"         tracepoint  tracepoint events\n"
"         cs-etm      coresight etm instruction tracing events\n"
"         pmu         system-specific pmu events\n"
"Options:\n"
"--show-features    Show features supported on the device, including:\n"
"                     dwarf-based-call-graph\n"
"                     trace-offcpu\n"
                // clang-format on
        ) {}

  bool Run(const std::vector<std::string>& args) override;

 private:
  void ShowFeatures();
};

bool ListCommand::Run(const std::vector<std::string>& args) {
  if (!CheckPerfEventLimit()) {
    return false;
  }

  static std::map<std::string, std::pair<std::string, std::function<bool(const EventType&)>>>
      type_map =
  { {"hw", {"hardware events", [](const EventType& e) { return e.type == PERF_TYPE_HARDWARE; }}},
    {"sw", {"software events", [](const EventType& e) { return e.type == PERF_TYPE_SOFTWARE; }}},
    {"cache", {"hw-cache events", [](const EventType& e) { return e.type == PERF_TYPE_HW_CACHE; }}},
    {"raw",
     {"raw events provided by cpu pmu",
      [](const EventType& e) { return e.type == PERF_TYPE_RAW; }}},
    {"tracepoint",
     {"tracepoint events", [](const EventType& e) { return e.type == PERF_TYPE_TRACEPOINT; }}},
#if defined(__arm__) || defined(__aarch64__)
    {"cs-etm",
     {"coresight etm events",
      [](const EventType& e) { return e.type == ETMRecorder::GetInstance().GetEtmEventType(); }}},
#endif
    {"pmu", {"pmu events", [](const EventType& e) { return e.IsPmuEvent(); }}},
  };

  std::vector<std::string> names;
  if (args.empty()) {
    for (auto& item : type_map) {
      names.push_back(item.first);
    }
  } else {
    for (auto& arg : args) {
      if (type_map.find(arg) != type_map.end()) {
        names.push_back(arg);
      } else if (arg == "--show-features") {
        ShowFeatures();
        return true;
      } else {
        LOG(ERROR) << "unknown event type category: " << arg << ", try using \"help list\"";
        return false;
      }
    }
  }

  for (auto& name : names) {
    auto it = type_map.find(name);
    PrintEventTypesOfType(name, it->second.first, it->second.second);
  }
  return true;
}

void ListCommand::ShowFeatures() {
  if (IsDwarfCallChainSamplingSupported()) {
    printf("dwarf-based-call-graph\n");
  }
  if (IsDumpingRegsForTracepointEventsSupported()) {
    printf("trace-offcpu\n");
  }
  if (IsSettingClockIdSupported()) {
    printf("set-clockid\n");
  }
}

}  // namespace

void RegisterListCommand() {
  RegisterCommand("list", [] { return std::unique_ptr<Command>(new ListCommand); });
}

}  // namespace simpleperf
