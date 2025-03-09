/*
 * Copyright (C) 2022 The Android Open Source Project
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

#include <inttypes.h>
#include <stdio.h>
#include <unistd.h>

#include <string>

#include <android-base/stringprintf.h>

#include <memory_trace/MemoryTrace.h>

namespace memory_trace {

// This is larger than the maximum length of a possible line.
constexpr size_t kBufferLen = 256;

bool FillInEntryFromString(const std::string& line, Entry& entry, std::string& error) {
  // All lines have this format:
  //   TID: ALLOCATION_TYPE POINTER [START_TIME_NS END_TIME_NS]
  // where
  //   TID is the thread id of the thread doing the operation.
  //   ALLOCATION_TYPE is one of malloc, calloc, memalign, realloc, free, thread_done
  //   POINTER is the hex value of the actual pointer
  //   START_TIME_NS is the start time of the operation in nanoseconds.
  //   END_TIME_NS is the end time of the operation in nanoseconds.
  // The START_TIME_NS and END_TIME_NS are optional parameters, either both
  // are present are neither are present.
  int op_prefix_pos = 0;
  char name[128];
  if (sscanf(line.c_str(), "%d: %127s %" SCNx64 " %n", &entry.tid, name, &entry.ptr,
             &op_prefix_pos) != 3) {
    error = "Failed to process line: " + line;
    return false;
  }

  // Handle each individual type of entry type.
  std::string type(name);
  if (type == "thread_done") {
    //   TID: thread_done 0x0 [END_TIME_NS]
    // Where END_TIME_NS is optional.
    entry.type = THREAD_DONE;
    entry.start_ns = 0;
    // Thread done has an optional time which is when the thread ended.
    // This is the only entry type that has a single timestamp.
    int n_match = sscanf(&line[op_prefix_pos], " %" SCNd64, &entry.end_ns);
    entry.start_ns = 0;
    if (n_match == EOF) {
      entry.end_ns = 0;
    } else if (n_match != 1) {
      error = "Failed to read thread_done end time: " + line;
      return false;
    }
    return true;
  }

  int args_offset = 0;
  const char* args_beg = &line[op_prefix_pos];
  if (type == "malloc") {
    // Format:
    //   TID: malloc POINTER SIZE_OF_ALLOCATION [START_TIME_NS END_TIME_NS]
    if (sscanf(args_beg, "%zu%n", &entry.size, &args_offset) != 1) {
      error = "Failed to read malloc data: " + line;
      return false;
    }
    entry.type = MALLOC;
  } else if (type == "free") {
    // Format:
    //   TID: free POINTER [START_TIME_NS END_TIME_NS]
    entry.type = FREE;
  } else if (type == "calloc") {
    // Format:
    //   TID: calloc POINTER ITEM_COUNT ITEM_SIZE [START_TIME_NS END_TIME_NS]
    if (sscanf(args_beg, "%" SCNd64 " %zu%n", &entry.u.n_elements, &entry.size, &args_offset) !=
        2) {
      error = "Failed to read calloc data: " + line;
      return false;
    }
    entry.type = CALLOC;
  } else if (type == "realloc") {
    // Format:
    //   TID: realloc POINTER OLD_POINTER NEW_SIZE [START_TIME_NS END_TIME_NS]
    if (sscanf(args_beg, "%" SCNx64 " %zu%n", &entry.u.old_ptr, &entry.size, &args_offset) != 2) {
      error = "Failed to read realloc data: " + line;
      return false;
    }
    entry.type = REALLOC;
  } else if (type == "memalign") {
    // Format:
    //   TID: memalign POINTER ALIGNMENT SIZE [START_TIME_NS END_TIME_NS]
    if (sscanf(args_beg, "%" SCNd64 " %zu%n", &entry.u.align, &entry.size, &args_offset) != 2) {
      error = "Failed to read memalign data: " + line;
      return false;
    }
    entry.type = MEMALIGN;
  } else {
    printf("Unknown type %s: %s\n", type.c_str(), line.c_str());
    error = "Unknown type " + type + ": " + line;
    return false;
  }

  const char* timestamps_beg = &args_beg[args_offset];

  // Get the optional timestamps if they exist.
  int n_match = sscanf(timestamps_beg, "%" SCNd64 " %" SCNd64, &entry.start_ns, &entry.end_ns);
  if (n_match == EOF) {
    entry.start_ns = 0;
    entry.end_ns = 0;
  } else if (n_match != 2) {
    error = "Failed to read timestamps: " + line;
    return false;
  }
  return true;
}

static const char* TypeToName(const TypeEnum type) {
  switch (type) {
    case CALLOC:
      return "calloc";
    case FREE:
      return "free";
    case MALLOC:
      return "malloc";
    case MEMALIGN:
      return "memalign";
    case REALLOC:
      return "realloc";
    case THREAD_DONE:
      return "thread_done";
  }
  return "unknown";
}

static size_t FormatEntry(const Entry& entry, char* buffer, size_t buffer_len) {
  int len = snprintf(buffer, buffer_len, "%d: %s 0x%" PRIx64, entry.tid, TypeToName(entry.type),
                     entry.ptr);
  if (len < 0) {
    return 0;
  }
  size_t cur_len = len;
  switch (entry.type) {
    case FREE:
      len = 0;
      break;
    case CALLOC:
      len = snprintf(&buffer[cur_len], buffer_len - cur_len, " %" PRIu64 " %zu", entry.u.n_elements,
                     entry.size);
      break;
    case MALLOC:
      len = snprintf(&buffer[cur_len], buffer_len - cur_len, " %zu", entry.size);
      break;
    case MEMALIGN:
      len = snprintf(&buffer[cur_len], buffer_len - cur_len, " %" PRIu64 " %zu", entry.u.align,
                     entry.size);
      break;
    case REALLOC:
      len = snprintf(&buffer[cur_len], buffer_len - cur_len, " 0x%" PRIx64 " %zu", entry.u.old_ptr,
                     entry.size);
      break;
    case THREAD_DONE:
      // Thread done only has a single optional timestamp, end_ns.
      if (entry.end_ns != 0) {
        len = snprintf(&buffer[cur_len], buffer_len - cur_len, " %" PRId64, entry.end_ns);
        if (len < 0) {
          return 0;
        }
        return cur_len + len;
      }
      return cur_len;
    default:
      return 0;
  }
  if (len < 0) {
    return 0;
  }

  cur_len += len;
  if (entry.start_ns == 0) {
    return cur_len;
  }

  len = snprintf(&buffer[cur_len], buffer_len - cur_len, " %" PRIu64 " %" PRIu64, entry.start_ns,
                 entry.end_ns);
  if (len < 0) {
    return 0;
  }
  return cur_len + len;
}

std::string CreateStringFromEntry(const Entry& entry) {
  std::string line(kBufferLen, '\0');

  size_t size = FormatEntry(entry, line.data(), line.size());
  if (size == 0) {
    return "";
  }
  line.resize(size);
  return line;
}

bool WriteEntryToFd(int fd, const Entry& entry) {
  char buffer[kBufferLen];
  size_t size = FormatEntry(entry, buffer, sizeof(buffer));
  if (size == 0 || size == sizeof(buffer)) {
    return false;
  }
  buffer[size++] = '\n';
  buffer[size] = '\0';
  ssize_t bytes = TEMP_FAILURE_RETRY(write(fd, buffer, size));
  if (bytes < 0 || static_cast<size_t>(bytes) != size) {
    return false;
  }
  return true;
}

}  // namespace memory_trace
