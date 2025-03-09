#
# Copyright (C) 2024 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import textwrap
from validation_error import ValidationError

ANDROID_SDK_VERSION_T = 33


def create_ftrace_events_string(predefined_ftrace_events,
    excluded_ftrace_events, included_ftrace_events):
  if excluded_ftrace_events is not None:
    for event in excluded_ftrace_events:
      if event in predefined_ftrace_events:
        predefined_ftrace_events.remove(event)
      else:
        return None, ValidationError(("Cannot remove ftrace event %s from"
                                      " config because it is not one"
                                      " of the config's ftrace events."
                                      % event),
                                     ("Please specify one of the following"
                                      " possible ftrace events:\n\t %s"
                                      % "\n\t ".join(predefined_ftrace_events)))

  if included_ftrace_events is not None:
    for event in included_ftrace_events:
      if event not in predefined_ftrace_events:
        predefined_ftrace_events.append(event)
      else:
        return None, ValidationError(("Cannot add ftrace event %s to config"
                                      " because it is already one of the"
                                      " config's ftrace events." % event),
                                     ("Please do not specify any of the"
                                      " following ftrace events that are"
                                      " already included:\n\t %s"
                                      % "\n\t ".join(predefined_ftrace_events)))

  ftrace_events_string = ("ftrace_events: \"%s\"" % ("""\"
          ftrace_events: \"""".join(predefined_ftrace_events)))
  return ftrace_events_string, None


def build_default_config(command, android_sdk_version):
  if command.dur_ms is None:
    # This is always defined because it has a default value that is always
    # set in torq.py.
    raise ValueError("Cannot create config because a valid dur_ms was not set.")
  predefined_ftrace_events = [
      "dmabuf_heap/dma_heap_stat",
      "ftrace/print",
      "gpu_mem/gpu_mem_total",
      "ion/ion_stat",
      "kmem/ion_heap_grow",
      "kmem/ion_heap_shrink",
      "kmem/rss_stat",
      "lowmemorykiller/lowmemory_kill",
      "mm_event/mm_event_record",
      "oom/mark_victim",
      "oom/oom_score_adj_update",
      "power/cpu_frequency",
      "power/cpu_idle",
      "power/gpu_frequency",
      "power/suspend_resume",
      "power/wakeup_source_activate",
      "power/wakeup_source_deactivate",
      "sched/sched_blocked_reason",
      "sched/sched_process_exit",
      "sched/sched_process_free",
      "sched/sched_switch",
      "sched/sched_wakeup",
      "sched/sched_wakeup_new",
      "sched/sched_waking",
      "task/task_newtask",
      "task/task_rename",
      "vmscan/*",
      "workqueue/*",
  ]
  ftrace_events_string, error = create_ftrace_events_string(
      predefined_ftrace_events, command.excluded_ftrace_events,
      command.included_ftrace_events)
  if error is not None:
    return None, error
  cpufreq_period_string = "cpufreq_period_ms: 500"
  if android_sdk_version < ANDROID_SDK_VERSION_T:
    cpufreq_period_string = ""
  config = f'''\
    <<EOF

    buffers: {{
      size_kb: 4096
      fill_policy: RING_BUFFER
    }}
    buffers {{
      size_kb: 4096
      fill_policy: RING_BUFFER
    }}
    buffers: {{
      size_kb: 260096
      fill_policy: RING_BUFFER
    }}

    data_sources: {{
      config {{
        name: "linux.process_stats"
        process_stats_config {{
          scan_all_processes_on_start: true
        }}
      }}
    }}

    data_sources: {{
      config {{
        name: "android.log"
        android_log_config {{
        }}
      }}
    }}

    data_sources {{
      config {{
        name: "android.packages_list"
      }}
    }}

    data_sources: {{
      config {{
        name: "linux.sys_stats"
        target_buffer: 1
        sys_stats_config {{
          stat_period_ms: 500
          stat_counters: STAT_CPU_TIMES
          stat_counters: STAT_FORK_COUNT
          meminfo_period_ms: 1000
          meminfo_counters: MEMINFO_ACTIVE_ANON
          meminfo_counters: MEMINFO_ACTIVE_FILE
          meminfo_counters: MEMINFO_INACTIVE_ANON
          meminfo_counters: MEMINFO_INACTIVE_FILE
          meminfo_counters: MEMINFO_KERNEL_STACK
          meminfo_counters: MEMINFO_MLOCKED
          meminfo_counters: MEMINFO_SHMEM
          meminfo_counters: MEMINFO_SLAB
          meminfo_counters: MEMINFO_SLAB_UNRECLAIMABLE
          meminfo_counters: MEMINFO_VMALLOC_USED
          meminfo_counters: MEMINFO_MEM_FREE
          meminfo_counters: MEMINFO_SWAP_FREE
          vmstat_period_ms: 1000
          vmstat_counters: VMSTAT_PGFAULT
          vmstat_counters: VMSTAT_PGMAJFAULT
          vmstat_counters: VMSTAT_PGFREE
          vmstat_counters: VMSTAT_PGPGIN
          vmstat_counters: VMSTAT_PGPGOUT
          vmstat_counters: VMSTAT_PSWPIN
          vmstat_counters: VMSTAT_PSWPOUT
          vmstat_counters: VMSTAT_PGSCAN_DIRECT
          vmstat_counters: VMSTAT_PGSTEAL_DIRECT
          vmstat_counters: VMSTAT_PGSCAN_KSWAPD
          vmstat_counters: VMSTAT_PGSTEAL_KSWAPD
          vmstat_counters: VMSTAT_WORKINGSET_REFAULT
          {cpufreq_period_string}
        }}
      }}
    }}

    data_sources: {{
      config {{
        name: "android.surfaceflinger.frametimeline"
        target_buffer: 2
      }}
    }}

    data_sources: {{
      config {{
        name: "linux.ftrace"
        target_buffer: 2
        ftrace_config {{
          {ftrace_events_string}
          atrace_categories: "aidl"
          atrace_categories: "am"
          atrace_categories: "dalvik"
          atrace_categories: "binder_lock"
          atrace_categories: "binder_driver"
          atrace_categories: "bionic"
          atrace_categories: "camera"
          atrace_categories: "disk"
          atrace_categories: "freq"
          atrace_categories: "idle"
          atrace_categories: "gfx"
          atrace_categories: "hal"
          atrace_categories: "input"
          atrace_categories: "pm"
          atrace_categories: "power"
          atrace_categories: "res"
          atrace_categories: "rro"
          atrace_categories: "sched"
          atrace_categories: "sm"
          atrace_categories: "ss"
          atrace_categories: "thermal"
          atrace_categories: "video"
          atrace_categories: "view"
          atrace_categories: "wm"
          atrace_apps: "lmkd"
          atrace_apps: "system_server"
          atrace_apps: "com.android.systemui"
          atrace_apps: "com.google.android.gms"
          atrace_apps: "com.google.android.gms.persistent"
          atrace_apps: "android:ui"
          atrace_apps: "com.google.android.apps.maps"
          atrace_apps: "*"
          buffer_size_kb: 16384
          drain_period_ms: 150
          symbolize_ksyms: true
        }}
      }}
    }}
    duration_ms: {command.dur_ms}
    write_into_file: true
    file_write_period_ms: 5000
    max_file_size_bytes: 100000000000
    flush_period_ms: 5000
    incremental_state_config {{
      clear_period_ms: 5000
    }}

    EOF'''
  return textwrap.dedent(config), None


def build_lightweight_config(command, android_sdk_version):
  raise NotImplementedError


def build_memory_config(command, android_sdk_version):
  raise NotImplementedError


PREDEFINED_PERFETTO_CONFIGS = {
    'default': build_default_config,
    'lightweight': build_lightweight_config,
    'memory': build_memory_config
}


def build_custom_config(command):
  file_content = ""
  duration_prefix = "duration_ms:"
  appended_duration = duration_prefix + " " + str(command.dur_ms)
  try:
    with open(command.perfetto_config, "r") as file:
      for line in file:
        stripped_line = line.strip()
        if stripped_line.startswith(duration_prefix):
          duration = stripped_line[len(duration_prefix):].strip()
          appended_duration = ""
          command.dur_ms = int(duration)
        file_content += line
  except ValueError:
    return None, ValidationError(("Failed to parse custom perfetto-config on"
                                  " local file path: %s. Invalid duration_ms"
                                  " field in config."
                                  % command.perfetto_config),
                                 ("Make sure the perfetto config passed via"
                                  " arguments has a valid duration_ms value."))
  except Exception as e:
    return None, ValidationError(("Failed to parse custom perfetto-config on"
                                  " local file path: %s. %s"
                                  % (command.perfetto_config, str(e))), None)
  config_string = f"<<EOF\n\n{file_content}\n{appended_duration}\n\nEOF"
  return config_string, None
