#!/usr/bin/env python3
#
# Copyright (C) 2021 The Android Open Source Project
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

"""gecko_profile_generator.py: converts perf.data to Gecko Profile Format,
    which can be read by https://profiler.firefox.com/.

  Example:
    ./app_profiler.py
    ./gecko_profile_generator.py | gzip > gecko-profile.json.gz

  Then open gecko-profile.json.gz in https://profiler.firefox.com/
"""

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, unique
import json
import logging
import sys
from typing import List, Dict, Optional, NamedTuple, Tuple

from simpleperf_report_lib import GetReportLib
from simpleperf_utils import BaseArgumentParser, ReportLibOptions


StringID = int
StackID = int
FrameID = int
CategoryID = int
Milliseconds = float
GeckoProfile = Dict


# https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L156
class GeckoFrame(NamedTuple):
    string_id: StringID
    relevantForJS: bool
    innerWindowID: int
    implementation: None
    optimizations: None
    line: None
    column: None
    category: CategoryID
    subcategory: int


# https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L216
class GeckoStack(NamedTuple):
    prefix_id: Optional[StackID]
    frame_id: FrameID
    category_id: CategoryID


# https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L90
class GeckoSample(NamedTuple):
    stack_id: Optional[StackID]
    time_ms: Milliseconds
    responsiveness: int
    complete_stack: bool

    def to_json(self):
        return [self.stack_id, self.time_ms, self.responsiveness]


# Schema: https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/profile.js#L425
# Colors must be defined in:
# https://github.com/firefox-devtools/profiler/blob/50124adbfa488adba6e2674a8f2618cf34b59cd2/res/css/categories.css
@unique
class Category(Enum):
  # Follow Brendan Gregg's Flamegraph convention: yellow for userland
  # https://github.com/brendangregg/FlameGraph/blob/810687f180f3c4929b5d965f54817a5218c9d89b/flamegraph.pl#L419
  USER = 0, 'User', 'yellow'
  # Follow Brendan Gregg's Flamegraph convention: orange for kernel
  # https://github.com/brendangregg/FlameGraph/blob/810687f180f3c4929b5d965f54817a5218c9d89b/flamegraph.pl#L417
  KERNEL = 1, 'Kernel', 'orange'
  # Follow Brendan Gregg's Flamegraph convention: yellow for userland
  # https://github.com/brendangregg/FlameGraph/blob/810687f180f3c4929b5d965f54817a5218c9d89b/flamegraph.pl#L419
  NATIVE = 2, 'Native', 'yellow'
  # Follow Brendan Gregg's Flamegraph convention: green for Java/JIT
  # https://github.com/brendangregg/FlameGraph/blob/810687f180f3c4929b5d965f54817a5218c9d89b/flamegraph.pl#L411
  DEX = 3, 'DEX', 'green'
  OAT = 4, 'OAT', 'green'
  # Follow Brendan Gregg's Flamegraph convention: blue for off-CPU
  # https://github.com/brendangregg/FlameGraph/blob/810687f180f3c4929b5d965f54817a5218c9d89b/flamegraph.pl#L470
  OFF_CPU = 5, 'Off-CPU', 'blue'
  # Not used by this exporter yet, but some Firefox Profiler code assumes
  # there is an 'Other' category by searching for a category with
  # color=grey, so include this.
  OTHER = 6, 'Other', 'grey'
  # Follow Brendan Gregg's Flamegraph convention: green for Java/JIT
  # https://github.com/brendangregg/FlameGraph/blob/810687f180f3c4929b5d965f54817a5218c9d89b/flamegraph.pl#L411
  JIT = 7, 'JIT', 'green'

  def __init__(self, value, label, color):
    self._value_ = value
    self.label = label
    self.color = color

  @classmethod
  def to_json(cls):
    return [{
        "name": enum.label,
        "color": enum.color,
        # We don't use subcategories, but Firefox Profiler seems to require it.
        "subcategories":['Other']
    } for enum in cls]


@dataclass
class StackFrame:
  symbol_name: str
  dso_name: str

  def to_gecko_frame_string(self):
    return '%s (in %s)' % (self.symbol_name, self.dso_name)

  def category(self) -> Category:
    # Heuristic: kernel code contains "kallsyms" as the library name.
    if self.dso_name == "[kernel.kallsyms]" or self.dso_name.endswith(".ko"):
        # Heuristic: empirically, off-CPU profiles mostly measure off-CPU
        # time accounted to the linux kernel __schedule function, which
        # handles blocking. This only works if we have kernel symbol
        # (kallsyms) access though.  __schedule defined here:
        # https://cs.android.com/android/kernel/superproject/+/common-android-mainline:common/kernel/sched/core.c;l=6593;drc=0c99414a07ddaa18d8eb4be90b551d2687cbde2f
        if self.symbol_name == "__schedule":
            return Category.OFF_CPU
        return Category.KERNEL
    elif self.dso_name.endswith(".so"):
        return Category.NATIVE
    elif self.dso_name.endswith(".vdex"):
        return Category.DEX
    # APKs are full of dex code.
    elif self.dso_name.endswith(".apk"):
        return Category.DEX
    # /system/framework/ has .jar files which seem to be full of .dex code.
    elif self.dso_name.endswith(".jar"):
        return Category.DEX
    elif self.dso_name.endswith(".oat"):
        return Category.OAT
    # In ART, odex is just OAT code
    elif self.dso_name.endswith(".odex"):
        return Category.OAT
    # "[JIT app cache]" is returned for JIT code here:
    # https://cs.android.com/android/platform/superproject/+/master:system/extras/simpleperf/dso.cpp;l=551;drc=4d8137f55782cc1e8cc93e4694ba3a7159d9a2bc
    elif self.dso_name == "[JIT app cache]":
        return Category.JIT
    return Category.USER


def is_complete_stack(stack: List[StackFrame]) -> bool:
    """ Check if the callstack is complete. The stack starts from root. """
    for frame in stack:
        if frame.symbol_name == '__libc_init' or frame.symbol_name == '__start_thread':
            return True
    return False


@dataclass
class Thread:
    """A builder for a profile of a single thread.

    Attributes:
      comm: Thread command-line (name).
      pid: process ID of containing process.
      tid: thread ID.
      samples: Timeline of profile samples.
      frameTable: interned stack frame ID -> stack frame.
      stringTable: interned string ID -> string.
      stringMap: interned string -> string ID.
      stackTable: interned stack ID -> stack.
      stackMap: (stack prefix ID, leaf stack frame ID) -> interned Stack ID.
      frameMap: Stack Frame string -> interned Frame ID.
    """
    comm: str
    pid: int
    tid: int
    samples: List[GeckoSample] = field(default_factory=list)
    frameTable: List[GeckoFrame] = field(default_factory=list)
    stringTable: List[str] = field(default_factory=list)
    # TODO: this is redundant with frameTable, could we remove this?
    stringMap: Dict[str, int] = field(default_factory=dict)
    stackTable: List[GeckoStack] = field(default_factory=list)
    stackMap: Dict[Tuple[Optional[int], int], int] = field(default_factory=dict)
    frameMap: Dict[str, int] = field(default_factory=dict)

    def _intern_stack(self, frame_id: int, prefix_id: Optional[int]) -> int:
        """Gets a matching stack, or saves the new stack. Returns a Stack ID."""
        key = (prefix_id, frame_id)
        stack_id = self.stackMap.get(key)
        if stack_id is not None:
            return stack_id
        stack_id = len(self.stackTable)
        self.stackTable.append(GeckoStack(
            prefix_id=prefix_id,
            frame_id=frame_id,
            category_id=0,
        ))
        self.stackMap[key] = stack_id
        return stack_id

    def _intern_string(self, string: str) -> int:
        """Gets a matching string, or saves the new string. Returns a String ID."""
        string_id = self.stringMap.get(string)
        if string_id is not None:
            return string_id
        string_id = len(self.stringTable)
        self.stringTable.append(string)
        self.stringMap[string] = string_id
        return string_id

    def _intern_frame(self, frame: StackFrame) -> int:
        """Gets a matching stack frame, or saves the new frame. Returns a Frame ID."""
        frame_str = frame.to_gecko_frame_string()
        frame_id = self.frameMap.get(frame_str)
        if frame_id is not None:
            return frame_id
        frame_id = len(self.frameTable)
        self.frameMap[frame_str] = frame_id
        string_id = self._intern_string(frame_str)


        self.frameTable.append(GeckoFrame(
            string_id=string_id,
            relevantForJS=False,
            innerWindowID=0,
            implementation=None,
            optimizations=None,
            line=None,
            column=None,
            category=frame.category().value,
            subcategory=0,
        ))
        return frame_id

    def add_sample(self, comm: str, stack: List[StackFrame], time_ms: Milliseconds) -> None:
        """Add a timestamped stack trace sample to the thread builder.

        Args:
          comm: command-line (name) of the thread at this sample
          stack: sampled stack frames. Root first, leaf last.
          time_ms: timestamp of sample in milliseconds
        """
        # Unix threads often don't set their name immediately upon creation.
        # Use the last name
        if self.comm != comm:
            self.comm = comm

        prefix_stack_id = None
        for frame in stack:
            frame_id = self._intern_frame(frame)
            prefix_stack_id = self._intern_stack(frame_id, prefix_stack_id)

        self.samples.append(GeckoSample(
            stack_id=prefix_stack_id,
            time_ms=time_ms,
            responsiveness=0,
            complete_stack=is_complete_stack(stack),
        ))

    def sort_samples(self) -> None:
        """ The samples aren't guaranteed to be in order. Sort them by time. """
        self.samples.sort(key=lambda s: s.time_ms)

    def remove_stack_gaps(self, max_remove_gap_length: int, gap_distr: Dict[int, int]) -> None:
        """ Ideally all callstacks are complete. But some may be broken for different reasons.
            To create a smooth view in "Stack Chart", remove small gaps of broken callstacks.

        Args:
            max_remove_gap_length: the max length of continuous broken-stack samples to remove
        """
        if max_remove_gap_length == 0:
            return
        i = 0
        remove_flags = [False] * len(self.samples)
        while i < len(self.samples):
            if self.samples[i].complete_stack:
                i += 1
                continue
            n = 1
            while (i + n < len(self.samples)) and (not self.samples[i + n].complete_stack):
                n += 1
            gap_distr[n] += 1
            if n <= max_remove_gap_length:
                for j in range(i, i + n):
                    remove_flags[j] = True
            i += n
        if True in remove_flags:
            old_samples = self.samples
            self.samples = [s for s, remove in zip(old_samples, remove_flags) if not remove]

    def to_json_dict(self) -> Dict:
        """Converts this Thread to GeckoThread JSON format."""

        # Gecko profile format is row-oriented data as List[List],
        # And a schema for interpreting each index.
        # Schema:
        # https://github.com/firefox-devtools/profiler/blob/main/docs-developer/gecko-profile-format.md
        # https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L230
        return {
            "tid": self.tid,
            "pid": self.pid,
            "name": self.comm,
            # https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L51
            "markers": {
                "schema": {
                    "name": 0,
                    "startTime": 1,
                    "endTime": 2,
                    "phase": 3,
                    "category": 4,
                    "data": 5,
                },
                "data": [],
            },
            # https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L90
            "samples": {
                "schema": {
                    "stack": 0,
                    "time": 1,
                    "responsiveness": 2,
                },
                "data": [s.to_json() for s in self.samples],
            },
            # https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L156
            "frameTable": {
                "schema": {
                    "location": 0,
                    "relevantForJS": 1,
                    "innerWindowID": 2,
                    "implementation": 3,
                    "optimizations": 4,
                    "line": 5,
                    "column": 6,
                    "category": 7,
                    "subcategory": 8,
                },
                "data": self.frameTable,
            },
            # https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L216
            "stackTable": {
                "schema": {
                    "prefix": 0,
                    "frame": 1,
                    "category": 2,
                },
                "data": self.stackTable,
            },
            "stringTable": self.stringTable,
            "registerTime": 0,
            "unregisterTime": None,
            "processType": "default",
        }


def remove_stack_gaps(max_remove_gap_length: int, thread_map: Dict[int, Thread]) -> None:
    """ Remove stack gaps for each thread, and print status. """
    if max_remove_gap_length == 0:
        return
    total_sample_count = 0
    remove_sample_count = 0
    gap_distr = Counter()
    for tid in list(thread_map.keys()):
        thread = thread_map[tid]
        old_n = len(thread.samples)
        thread.remove_stack_gaps(max_remove_gap_length, gap_distr)
        new_n = len(thread.samples)
        total_sample_count += old_n
        remove_sample_count += old_n - new_n
        if new_n == 0:
            del thread_map[tid]
    if total_sample_count != 0:
        logging.info('Remove stack gaps with length <= %d. %d (%.2f%%) samples are removed.',
                     max_remove_gap_length, remove_sample_count,
                     remove_sample_count / total_sample_count * 100
                     )
        logging.debug('Stack gap length distribution among samples (gap_length: count): %s',
                      gap_distr)


def _gecko_profile(
        record_file: str,
        symfs_dir: Optional[str],
        kallsyms_file: Optional[str],
        report_lib_options: ReportLibOptions,
        max_remove_gap_length: int,
        percpu_samples: bool) -> GeckoProfile:
    """convert a simpleperf profile to gecko format"""
    lib = GetReportLib(record_file)

    lib.ShowIpForUnknownSymbol()
    if symfs_dir is not None:
        lib.SetSymfs(symfs_dir)
    if kallsyms_file is not None:
        lib.SetKallsymsFile(kallsyms_file)
    if percpu_samples:
        # Grouping samples by cpus doesn't support off cpu samples.
        if lib.GetSupportedTraceOffCpuModes():
            report_lib_options.trace_offcpu = 'on-cpu'
    lib.SetReportOptions(report_lib_options)

    arch = lib.GetArch()
    meta_info = lib.MetaInfo()
    record_cmd = lib.GetRecordCmd()

    # Map from tid to Thread
    thread_map: Dict[int, Thread] = {}
    # Map from pid to process name
    process_names: Dict[int, str] = {}

    while True:
        sample = lib.GetNextSample()
        if sample is None:
            lib.Close()
            break
        symbol = lib.GetSymbolOfCurrentSample()
        callchain = lib.GetCallChainOfCurrentSample()
        sample_time_ms = sample.time / 1000000
        stack : List[StackFrame] = [
            StackFrame(symbol.symbol_name, symbol.dso_name),
        ]

        for i in range(callchain.nr):
            entry = callchain.entries[i]
            stack.append(StackFrame(
                symbol_name = entry.symbol.symbol_name,
                dso_name = entry.symbol.dso_name
            ))
        # We want root first, leaf last.
        stack.reverse()

        if percpu_samples:
            if sample.tid == sample.pid:
                process_names[sample.pid] = sample.thread_comm
            process_name = process_names.get(sample.pid)
            stack = [
                # This is a synthetic stack frame, these aren't real symbols or
                # DSOs, but they show up nicely in the UI.
                StackFrame(
                    symbol_name = '%s tid %d' % (sample.thread_comm, sample.tid),
                    dso_name = '%s pid %d' % (process_name, sample.pid),
                )
            ] + stack
            thread = thread_map.get(sample.cpu)
            if thread is None:
                thread = Thread(comm=f'Cpu {sample.cpu}', pid=sample.cpu, tid=sample.cpu)
                thread_map[sample.cpu] = thread
            thread.add_sample(
                comm=f'Cpu {sample.cpu}',
                stack=stack,
                time_ms=sample_time_ms)
        else:
            # add thread sample
            thread = thread_map.get(sample.tid)
            if thread is None:
                thread = Thread(comm=sample.thread_comm, pid=sample.pid, tid=sample.tid)
                thread_map[sample.tid] = thread
            thread.add_sample(
                comm=sample.thread_comm,
                stack=stack,
                # We are being a bit fast and loose here with time here.  simpleperf
                # uses CLOCK_MONOTONIC by default, which doesn't use the normal unix
                # epoch, but rather some arbitrary time. In practice, this doesn't
                # matter, the Firefox Profiler normalises all the timestamps to begin at
                # the minimum time.  Consider fixing this in future, if needed, by
                # setting `simpleperf record --clockid realtime`.
                time_ms=sample_time_ms)

    for thread in thread_map.values():
        thread.sort_samples()

    remove_stack_gaps(max_remove_gap_length, thread_map)

    threads = [thread.to_json_dict() for thread in thread_map.values()]

    profile_timestamp = meta_info.get('timestamp')
    end_time_ms = (int(profile_timestamp) * 1000) if profile_timestamp else 0

    # Schema: https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L305
    gecko_profile_meta = {
        "interval": 1,
        "processType": 0,
        "product": record_cmd,
        "device": meta_info.get("product_props"),
        "platform": meta_info.get("android_build_fingerprint"),
        "stackwalk": 1,
        "debug": 0,
        "gcpoison": 0,
        "asyncstack": 1,
        # The profile timestamp is actually the end time, not the start time.
        # This is close enough for our purposes; I mostly just want to know which
        # day the profile was taken! Consider fixing this in future, if needed,
        # by setting `simpleperf record --clockid realtime` and taking the minimum
        # sample time.
        "startTime": end_time_ms,
        "shutdownTime": None,
        "version": 24,
        "presymbolicated": True,
        "categories": Category.to_json(),
        "markerSchema": [],
        "abi": arch,
        "oscpu": meta_info.get("android_build_fingerprint"),
        "appBuildID": meta_info.get("app_versioncode"),
    }

    # Schema:
    # https://github.com/firefox-devtools/profiler/blob/53970305b51b9b472e26d7457fee1d66cd4e2737/src/types/gecko-profile.js#L377
    # https://github.com/firefox-devtools/profiler/blob/main/docs-developer/gecko-profile-format.md
    return {
        "meta": gecko_profile_meta,
        "libs": [],
        "threads": threads,
        "processes": [],
        "pausedRanges": [],
    }


def main() -> None:
    parser = BaseArgumentParser(description=__doc__)
    parser.add_argument('--symfs',
                        help='Set the path to find binaries with symbols and debug info.')
    parser.add_argument('--kallsyms', help='Set the path to find kernel symbols.')
    parser.add_argument('-i', '--record_file', nargs='?', default='perf.data',
                        help='Default is perf.data.')
    parser.add_argument('--remove-gaps', metavar='MAX_GAP_LENGTH', dest='max_remove_gap_length',
                        type=int, default=3, help="""
                        Ideally all callstacks are complete. But some may be broken for different
                        reasons. To create a smooth view in "Stack Chart", remove small gaps of
                        broken callstacks. MAX_GAP_LENGTH is the max length of continuous
                        broken-stack samples we want to remove.
                        """
                        )
    parser.add_argument(
        '--percpu-samples', action='store_true',
        help='show samples based on cpus instead of threads')
    parser.add_report_lib_options()
    args = parser.parse_args()
    profile = _gecko_profile(
        record_file=args.record_file,
        symfs_dir=args.symfs,
        kallsyms_file=args.kallsyms,
        report_lib_options=args.report_lib_options,
        max_remove_gap_length=args.max_remove_gap_length,
        percpu_samples=args.percpu_samples,
    )

    json.dump(profile, sys.stdout, sort_keys=True)


if __name__ == '__main__':
    main()
