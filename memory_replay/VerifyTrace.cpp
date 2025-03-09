/*
 * Copyright (C) 2024 The Android Open Source Project
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

#include <fcntl.h>
#include <getopt.h>
#include <inttypes.h>
#include <stdio.h>
#include <unistd.h>

#include <string>
#include <unordered_map>
#include <utility>

#include <android-base/file.h>

#include <memory_trace/MemoryTrace.h>

#include "File.h"

static void Usage() {
  fprintf(stderr, "Usage: %s [--attempt_repair] TRACE_FILE1 TRACE_FILE2 ...\n",
          android::base::Basename(android::base::GetExecutablePath()).c_str());
  fprintf(stderr, "  --attempt_repair\n");
  fprintf(stderr, "    If a trace file has some errors, try to fix them. The new\n");
  fprintf(stderr, "    file will be named TRACE_FILE.repair\n");
  fprintf(stderr, "  TRACE_FILE1 TRACE_FILE2 ...\n");
  fprintf(stderr, "      The trace files to verify\n");
  fprintf(stderr, "\n  Verify trace are valid.\n");
  exit(1);
}

static bool WriteRepairEntries(const std::string& repair_file, memory_trace::Entry* entries,
                               size_t num_entries) {
  int fd = open(repair_file.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0644);
  if (fd == -1) {
    printf("  Failed to create repair file %s: %s\n", repair_file.c_str(), strerror(errno));
    return false;
  }
  bool valid = true;
  for (size_t i = 0; i < num_entries; i++) {
    if (!memory_trace::WriteEntryToFd(fd, entries[i])) {
      printf("  Failed to write entry to file:\n");
      valid = false;
      break;
    }
  }
  close(fd);
  if (!valid) {
    unlink(repair_file.c_str());
  }
  return valid;
}

static void VerifyTrace(const char* trace_file, bool attempt_repair) {
  printf("Checking %s\n", trace_file);

  memory_trace::Entry* entries;
  size_t num_entries;
  GetUnwindInfo(trace_file, &entries, &num_entries);

  size_t errors_found = 0;
  size_t errors_repaired = 0;
  std::unordered_map<uint64_t, std::pair<memory_trace::Entry*, size_t>> live_ptrs;
  std::pair<memory_trace::Entry*, size_t> erased(nullptr, 0);
  for (size_t i = 0; i < num_entries; i++) {
    memory_trace::Entry* entry = &entries[i];

    uint64_t ptr = 0;
    switch (entry->type) {
      case memory_trace::MALLOC:
      case memory_trace::MEMALIGN:
        ptr = entry->ptr;
        break;
      case memory_trace::CALLOC:
        ptr = entry->ptr;
        break;
      case memory_trace::REALLOC:
        if (entry->ptr != 0) {
          ptr = entry->ptr;
        }
        if (entry->u.old_ptr != 0) {
          // Verify old pointer
          auto entry_iter = live_ptrs.find(entry->u.old_ptr);
          if (entry_iter == live_ptrs.end()) {
            // Verify the pointer didn't get realloc'd to itself.
            if (entry->u.old_ptr != entry->ptr) {
              printf("  Line %zu: freeing of unknown ptr 0x%" PRIx64 "\n", i + 1, entry->u.old_ptr);
              printf("    %s\n", memory_trace::CreateStringFromEntry(*entry).c_str());
              errors_found++;
              if (attempt_repair) {
                printf("  Unable to repair this failure.\n");
              }
            }
          } else {
            if (attempt_repair) {
              erased = entry_iter->second;
            }
            live_ptrs.erase(entry_iter);
          }
        }
        break;
      case memory_trace::FREE:
        if (entry->ptr != 0) {
          // Verify pointer is present.
          auto entry_iter = live_ptrs.find(entry->ptr);
          if (entry_iter == live_ptrs.end()) {
            printf("  Line %zu: freeing of unknown ptr 0x%" PRIx64 "\n", i + 1, entry->ptr);
            printf("    %s\n", memory_trace::CreateStringFromEntry(*entry).c_str());
            errors_found++;
            if (attempt_repair) {
              printf("  Unable to repair this failure.\n");
            }
          } else {
            live_ptrs.erase(entry_iter);
          }
        }
        break;
      case memory_trace::THREAD_DONE:
        break;
    }

    if (ptr != 0) {
      auto old_entry = live_ptrs.find(ptr);
      if (old_entry != live_ptrs.end()) {
        printf("  Line %zu: duplicate ptr 0x%" PRIx64 "\n", i + 1, ptr);
        printf("    Original entry at line %zu:\n", old_entry->second.second);
        printf("      %s\n", memory_trace::CreateStringFromEntry(*old_entry->second.first).c_str());
        printf("    Duplicate entry at line %zu:\n", i + 1);
        printf("      %s\n", memory_trace::CreateStringFromEntry(*entry).c_str());
        errors_found++;
        if (attempt_repair) {
          // There is a small chance of a race where the same pointer is returned
          // in two different threads before the free is recorded. If this occurs,
          // the way to repair is to search forward for the free of the pointer and
          // swap the two entries.
          bool fixed = false;
          for (size_t j = i + 1; j < num_entries; j++) {
            if ((entries[j].type == memory_trace::FREE && entries[j].ptr == ptr) ||
                (entries[j].type == memory_trace::REALLOC && entries[j].u.old_ptr == ptr)) {
              memory_trace::Entry tmp_entry = *entry;
              *entry = entries[j];
              entries[j] = tmp_entry;
              errors_repaired++;

              live_ptrs.erase(old_entry);
              if (entry->type == memory_trace::REALLOC) {
                if (entry->ptr != 0) {
                  // Need to add the newly allocated pointer.
                  live_ptrs[entry->ptr] = std::make_pair(entry, i + 1);
                }
                if (erased.first != nullptr) {
                  // Need to put the erased old ptr back.
                  live_ptrs[tmp_entry.u.old_ptr] = erased;
                }
              }
              fixed = true;
              break;
            }
          }
          if (!fixed) {
            printf("  Unable to fix error.\n");
          }
        }
      } else {
        live_ptrs[ptr] = std::make_pair(entry, i + 1);
      }
    }
  }

  if (errors_found != 0) {
    printf("Trace %s is not valid.\n", trace_file);
    if (attempt_repair) {
      // Save the repaired data out to a file.
      std::string repair_file(std::string(trace_file) + ".repair");
      printf("Creating repaired trace file %s...\n", repair_file.c_str());
      if (!WriteRepairEntries(repair_file, entries, num_entries)) {
        printf("Failed trying to write repaired entries to file.\n");
      } else if (errors_repaired == errors_found) {
        printf("Repaired file is complete, no more errors.\n");
      } else {
        printf("Repaired file is still not valid.\n");
      }
    }
  } else if (attempt_repair) {
    printf("Trace %s is valid, no repair needed.\n", trace_file);
  } else {
    printf("Trace %s is valid.\n", trace_file);
  }

  FreeEntries(entries, num_entries);
}

int main(int argc, char** argv) {
  option options[] = {
      {"attempt_repair", no_argument, nullptr, 'a'},
      {nullptr, 0, nullptr, 0},
  };
  int option_index = 0;
  int opt = getopt_long(argc, argv, "", options, &option_index);
  if (argc == 1 || (argc == 2 && opt != -1)) {
    fprintf(stderr, "Requires at least one TRACE_FILE\n");
    Usage();
  }

  bool attempt_repair = false;
  if (opt == 'a') {
    attempt_repair = true;
  } else if (opt != -1) {
    Usage();
  }

  for (int i = 1; i < argc; i++) {
    if (i + 1 == optind) {
      continue;
    }
    VerifyTrace(argv[i], attempt_repair);
  }

  return 0;
}
