#!/usr/bin/env python3
#
# Copyright (C) 2015 The Android Open Source Project
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

import json
import sys


def gen_event_type_entry_str(event_type_name, event_type, event_config, description='',
                             limited_arch=''):
    """
    return string as below:
    EVENT_TYPE_TABLE_ENTRY(event_type_name, event_type, event_config, description, limited_arch)
    """
    return 'EVENT_TYPE_TABLE_ENTRY("%s", %s, %s, "%s", "%s")\n' % (
        event_type_name, event_type, event_config, description, limited_arch)


def gen_arm_event_type_entry_str(event_type_name, event_type, event_config, description):
    return gen_event_type_entry_str(event_type_name, event_type, event_config, description,
                                    "arm")


def gen_hardware_events():
    hardware_configs = ["cpu-cycles",
                        "instructions",
                        "cache-references",
                        "cache-misses",
                        "branch-instructions",
                        "branch-misses",
                        "bus-cycles",
                        "stalled-cycles-frontend",
                        "stalled-cycles-backend",
                        ]
    generated_str = ""
    for config in hardware_configs:
        event_type_name = config
        event_config = "PERF_COUNT_HW_" + config.replace('-', '_').upper()

        generated_str += gen_event_type_entry_str(
            event_type_name, "PERF_TYPE_HARDWARE", event_config)

    return generated_str


def gen_software_events():
    software_configs = ["cpu-clock",
                        "task-clock",
                        "page-faults",
                        "context-switches",
                        "cpu-migrations",
                        ["minor-faults", "PERF_COUNT_SW_PAGE_FAULTS_MIN"],
                        ["major-faults", "PERF_COUNT_SW_PAGE_FAULTS_MAJ"],
                        "alignment-faults",
                        "emulation-faults",
                        ]
    generated_str = ""
    for config in software_configs:
        if isinstance(config, list):
            event_type_name = config[0]
            event_config = config[1]
        else:
            event_type_name = config
            event_config = "PERF_COUNT_SW_" + config.replace('-', '_').upper()

        generated_str += gen_event_type_entry_str(
            event_type_name, "PERF_TYPE_SOFTWARE", event_config)

    return generated_str


def gen_hw_cache_events():
    hw_cache_types = [["L1-dcache", "PERF_COUNT_HW_CACHE_L1D"],
                      ["L1-icache", "PERF_COUNT_HW_CACHE_L1I"],
                      ["LLC", "PERF_COUNT_HW_CACHE_LL"],
                      ["dTLB", "PERF_COUNT_HW_CACHE_DTLB"],
                      ["iTLB", "PERF_COUNT_HW_CACHE_ITLB"],
                      ["branch", "PERF_COUNT_HW_CACHE_BPU"],
                      ["node", "PERF_COUNT_HW_CACHE_NODE"],
                      ]
    hw_cache_ops = [["loads", "load", "PERF_COUNT_HW_CACHE_OP_READ"],
                    ["stores", "store", "PERF_COUNT_HW_CACHE_OP_WRITE"],
                    ["prefetches", "prefetch",
                     "PERF_COUNT_HW_CACHE_OP_PREFETCH"],
                    ]
    hw_cache_op_results = [["accesses", "PERF_COUNT_HW_CACHE_RESULT_ACCESS"],
                           ["misses", "PERF_COUNT_HW_CACHE_RESULT_MISS"],
                           ]
    generated_str = ""
    for (type_name, type_config) in hw_cache_types:
        for (op_name_access, op_name_miss, op_config) in hw_cache_ops:
            for (result_name, result_config) in hw_cache_op_results:
                if result_name == "accesses":
                    event_type_name = type_name + '-' + op_name_access
                else:
                    event_type_name = type_name + '-' + \
                        op_name_miss + '-' + result_name
                event_config = "((%s) | (%s << 8) | (%s << 16))" % (
                    type_config, op_config, result_config)
                generated_str += gen_event_type_entry_str(
                    event_type_name, "PERF_TYPE_HW_CACHE", event_config)

    return generated_str


class RawEventGenerator:
    def __init__(self, event_table_file: str):
        with open(event_table_file, 'r') as fh:
            self.event_table = json.load(fh)

    def generate_raw_events(self) -> str:
        lines = []
        for event in self.event_table['arm64']['events']:
            event_number = event[0]
            event_name = 'raw-' + event[1].lower().replace('_', '-')
            event_desc = event[2]
            lines.append(gen_arm_event_type_entry_str(
                event_name, 'PERF_TYPE_RAW', event_number, event_desc))
        return ''.join(lines)


def gen_events(event_table_file: str):
    generated_str = """
        #include "event_type.h"

        namespace simpleperf {

        #define EVENT_TYPE_TABLE_ENTRY(name, type, config, description, limited_arch) \
            {name, type, config, description, limited_arch},

        std::set<EventType> builtin_event_types = {
    """
    generated_str += gen_hardware_events() + '\n'
    generated_str += gen_software_events() + '\n'
    generated_str += gen_hw_cache_events() + '\n'
    raw_event_generator = RawEventGenerator(event_table_file)
    generated_str += raw_event_generator.generate_raw_events() + '\n'
    generated_str += """
        };
        }  // namespace simpleperf
    """
    return generated_str


def main():
    event_table_file = sys.argv[1]
    output_file = sys.argv[2]
    generated_str = gen_events(event_table_file)
    with open(output_file, 'w') as fh:
        fh.write(generated_str)


if __name__ == '__main__':
    main()
