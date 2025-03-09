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

import dataclasses
from dataclasses import dataclass
import json
import sys
from typing import List


def gen_event_type_entry_str(event_type_name, event_type, event_config, description='',
                             limited_arch=''):
    return '{"%s", %s, %s, "%s", "%s"},\n' % (
        event_type_name, event_type, event_config, description, limited_arch)


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


@dataclass
class RawEvent:
    number: int
    name: str
    desc: str
    limited_arch: str


@dataclass
class CpuModel:
    name: str
    implementer: int
    partnum: int
    mvendorid: int
    marchid: str
    mimpid: str
    supported_raw_events: list[int] = dataclasses.field(default_factory=list)


class ArchData:
    def __init__(self, arch: str):
        self.arch = arch
        self.events: List[RawEvent] = []
        self.cpus: List[CpuModel] = []

    def load_from_json_data(self, data) -> None:
        # Load common events
        for event in data['events']:
            number = int(event[0], 16)
            name = 'raw-' + event[1].lower().replace('_', '-')
            desc = event[2]
            self.events.append(RawEvent(number, name, desc, self.arch))
        for cpu in data['cpus']:
            cpu_name = cpu['name'].lower().replace('_', '-')
            cpu_model = CpuModel(
                cpu['name'],
                int(cpu.get('implementer', '0'), 16),
                int(cpu.get('partnum', '0'), 16),
                int(cpu.get('mvendorid', '0'), 16),
                cpu.get('marchid', '0'),
                cpu.get('mimpid', '0'),
                []
            )
            cpu_index = len(self.cpus)

            self.cpus.append(cpu_model)
            # Load common events supported in this cpu model.
            for number in cpu['common_events']:
                number = int(number, 16)
                event = self.get_event(number)
                cpu_model.supported_raw_events.append(number)

            # Load cpu specific events supported in this cpu model.
            if 'implementation_defined_events' in cpu:
                for event in cpu['implementation_defined_events']:
                    number = int(event[0], 16)
                    name = ('raw-' + cpu_name + '-' + event[1]).lower().replace('_', '-')
                    desc = event[2]
                    limited_arch = self.arch + ':' + cpu['name']
                    self.events.append(RawEvent(number, name, desc, limited_arch))
                    cpu_model.supported_raw_events.append(number)

    def get_event(self, event_number: int) -> RawEvent:
        for event in self.events:
            if event.number == event_number:
                return event
        raise Exception(f'no event for event number {event_number}')


class X86ArchData:
    def __init__(self, arch: str):
        self.arch = arch
        self.events: List[RawEvent] = []

    def load_from_json_data(self, data) -> None:
        for event in data['events']:
            number = int(event[0], 16)
            name = event[1]
            desc = event[2]
            self.events.append(RawEvent(number, name, desc, self.arch))


class RawEventGenerator:
    def __init__(self, event_table_file: str):
        with open(event_table_file, 'r') as fh:
            event_table = json.load(fh)
            self.arm64_data = ArchData('arm64')
            self.arm64_data.load_from_json_data(event_table['arm64'])
            self.riscv64_data = ArchData('riscv64')
            self.riscv64_data.load_from_json_data(event_table['riscv64'])
            self.x86_intel_data = X86ArchData('x86-intel')
            self.x86_intel_data.load_from_json_data(event_table['x86-intel'])
            self.x86_amd_data = X86ArchData('x86-amd')
            self.x86_amd_data.load_from_json_data(event_table['x86-amd'])

    def generate_raw_events(self) -> str:
        def generate_event_entries(events, guard) -> list:
            lines = []
            for event in events:
                lines.append(gen_event_type_entry_str(event.name, 'PERF_TYPE_RAW', '0x%x' %
                         event.number, event.desc, event.limited_arch))
            return guard(''.join(lines))

        lines_arm64 = generate_event_entries(self.arm64_data.events, self.add_arm_guard)
        lines_riscv64 = generate_event_entries(self.riscv64_data.events, self.add_riscv_guard)
        lines_x86_intel = generate_event_entries(self.x86_intel_data.events, self.add_x86_guard)
        lines_x86_amd = generate_event_entries(self.x86_amd_data.events, self.add_x86_guard)

        return lines_arm64 + lines_riscv64 + lines_x86_intel + lines_x86_amd

    def generate_cpu_support_events(self) -> str:
        def generate_cpu_events(data, guard) -> str:
            lines = []
            for cpu in data:
                event_list = ', '.join('0x%x' % number for number in cpu.supported_raw_events)
                lines.append('{"%s", {%s}},' % (cpu.name, event_list))
            return guard('\n'.join(lines))

        text = f"""
        // Map from cpu model to raw events supported on that cpu.
        std::unordered_map<std::string, std::unordered_set<int>> cpu_supported_raw_events = {{
        {generate_cpu_events(self.arm64_data.cpus, self.add_arm_guard)}
        {generate_cpu_events(self.riscv64_data.cpus, self.add_riscv_guard)}
        }};\n
        """

        return text

    def generate_cpu_models(self) -> str:
        def generate_model(data, map_type, map_key_type, id_func) -> str:
            lines = [f'std::{map_type}<{map_key_type}, std::string> cpuid_to_name = {{']
            for cpu in data:
                cpu_id = id_func(cpu)
                lines.append(f'{{{cpu_id}, "{cpu.name}"}},')
            lines.append('};')
            return '\n'.join(lines)

        arm64_model = generate_model(
            self.arm64_data.cpus,
            "unordered_map",
            "uint64_t",
            lambda cpu: f"0x{((cpu.implementer << 32) | cpu.partnum):x}ull"
        )

        riscv64_model = generate_model(
            self.riscv64_data.cpus,
            "map",
            "std::tuple<uint64_t, std::string, std::string>",
            lambda cpu: f'{{0x{cpu.mvendorid:x}ull, "{cpu.marchid}", "{cpu.mimpid}"}}'
        )

        return self.add_arm_guard(arm64_model) + "\n" + self.add_riscv_guard(riscv64_model)

    def add_arm_guard(self, data: str) -> str:
        return f'#if defined(__aarch64__) || defined(__arm__)\n{data}\n#endif\n'

    def add_riscv_guard(self, data: str) -> str:
        return f'#if defined(__riscv)\n{data}\n#endif\n'

    def add_x86_guard(self, data: str) -> str:
        return f'#if defined(__i386__) || defined(__x86_64__)\n{data}\n#endif\n'


def gen_events(event_table_file: str):
    generated_str = """
        #include <unordered_map>
        #include <unordered_set>
        #include <map>
        #include <string_view>

        #include "event_type.h"

        namespace simpleperf {

        // A constexpr-constructible version of EventType for the built-in table.
        struct BuiltinEventType {
          std::string_view name;
          uint32_t type;
          uint64_t config;
          std::string_view description;
          std::string_view limited_arch;

          explicit operator EventType() const {
            return {std::string(name), type, config, std::string(description), std::string(limited_arch)};
          }
        };

        static constexpr BuiltinEventType kBuiltinEventTypes[] = {
    """
    generated_str += gen_hardware_events() + '\n'
    generated_str += gen_software_events() + '\n'
    generated_str += gen_hw_cache_events() + '\n'
    raw_event_generator = RawEventGenerator(event_table_file)
    generated_str += raw_event_generator.generate_raw_events() + '\n'
    generated_str += """
        };

        void LoadBuiltinEventTypes(std::set<EventType>& set) {
          for (const auto& event_type : kBuiltinEventTypes) {
            set.insert(static_cast<EventType>(event_type));
          }
        }


    """
    generated_str += raw_event_generator.generate_cpu_support_events()
    generated_str += raw_event_generator.generate_cpu_models()

    generated_str += """
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
