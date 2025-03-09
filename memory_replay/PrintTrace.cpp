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

#include <stdio.h>

#include <android-base/file.h>

#include <memory_trace/MemoryTrace.h>

#include "File.h"

static void Usage() {
  fprintf(stderr, "Usage: %s TRACE_FILE\n",
          android::base::Basename(android::base::GetExecutablePath()).c_str());
  fprintf(stderr, "  TRACE_FILE\n");
  fprintf(stderr, "      The trace file\n");
  fprintf(stderr, "\n  Print a trace to stdout.\n");
}

int main(int argc, char** argv) {
  if (argc != 2) {
    Usage();
    return 1;
  }

  memory_trace::Entry* entries;
  size_t num_entries;
  GetUnwindInfo(argv[1], &entries, &num_entries);

  for (size_t i = 0; i < num_entries; i++) {
    printf("%s\n", memory_trace::CreateStringFromEntry(entries[i]).c_str());
  }

  FreeEntries(entries, num_entries);
  return 0;
}
