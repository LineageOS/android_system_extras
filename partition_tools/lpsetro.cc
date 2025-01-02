/*
 * Copyright (C) 2018 The Android Open Source Project
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
#include <stdlib.h>
#include <sysexits.h>

#include <string>

#include <liblp/liblp.h>

using namespace android;
using namespace android::fs_mgr;

/* Prints program usage to |where|. */
static int usage(int /* argc */, char* argv[]) {
    fprintf(stderr,
            "%s - command-line tool for setting LP_PARTITION_ATTR_READONLY attribute for all "
            "partitions.\n"
            "\n"
            "Usage:\n"
            "  %s [block-device] [slot-number] [true or false]\n",
            argv[0], argv[0]);
    return EX_USAGE;
}

int main(int argc, char* argv[]) {
    if (argc != 4) {
        return usage(argc, argv);
    }

    std::string super_block_device = std::string(argv[1]);
    uint32_t slot_number = atoi(argv[2]);
    bool read_only = strcmp(argv[3], "true") == 0;

    std::unique_ptr<LpMetadata> pt = ReadMetadata(super_block_device, slot_number);
    if (!pt) {
        printf("Failed to read metadata from super block device.\n");
        return EX_NOINPUT;
    }

    for (auto& partition : pt->partitions) {
        std::string part_name = GetPartitionName(partition);
        bool part_read_only = partition.attributes & LP_PARTITION_ATTR_READONLY;

        if (part_read_only == read_only) {
            printf("Partition %s is already %s.\n", part_name.c_str(),
                   read_only ? "read-only" : "read-write");
            continue;
        }

        if (read_only) {
            partition.attributes |= LP_PARTITION_ATTR_READONLY;
        } else {
            partition.attributes &= ~LP_PARTITION_ATTR_READONLY;
        }

        printf("Partition %s has been changed to %s.\n", part_name.c_str(),
               read_only ? "read-only" : "read-write");
    }

    if (!FlashPartitionTable(argv[1], *pt.get())) {
        printf("Failed to flash partition table.\n");
        return EX_SOFTWARE;
    }
    printf("Successfully flashed partition table.\n");
    return EX_OK;
}
