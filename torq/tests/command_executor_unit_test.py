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

import unittest
import subprocess
import sys
import io
from unittest import mock
from command import ProfilerCommand, ConfigCommand
from device import AdbDevice
from validation_error import ValidationError
from torq import DEFAULT_DUR_MS, DEFAULT_OUT_DIR, PREDEFINED_PERFETTO_CONFIGS

PROFILER_COMMAND_TYPE = "profiler"
PROFILER_TYPE = "perfetto"
TEST_ERROR_MSG = "test-error"
TEST_EXCEPTION = Exception(TEST_ERROR_MSG)
TEST_VALIDATION_ERROR = ValidationError(TEST_ERROR_MSG, None)
TEST_SERIAL = "test-serial"
DEFAULT_PERFETTO_CONFIG = "default"
TEST_USER_ID_1 = 0
TEST_USER_ID_2 = 1
TEST_USER_ID_3 = 2
TEST_PACKAGE_1 = "test-package-1"
TEST_PACKAGE_2 = "test-package-2"
TEST_PACKAGE_3 = "test-package-3"
TEST_DURATION = 0
ANDROID_SDK_VERSION_S = 32
ANDROID_SDK_VERSION_T = 33

TEST_DEFAULT_CONFIG = f'''\
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
      cpufreq_period_ms: 500
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
      ftrace_events: "dmabuf_heap/dma_heap_stat"
      ftrace_events: "ftrace/print"
      ftrace_events: "gpu_mem/gpu_mem_total"
      ftrace_events: "ion/ion_stat"
      ftrace_events: "kmem/ion_heap_grow"
      ftrace_events: "kmem/ion_heap_shrink"
      ftrace_events: "kmem/rss_stat"
      ftrace_events: "lowmemorykiller/lowmemory_kill"
      ftrace_events: "mm_event/mm_event_record"
      ftrace_events: "oom/mark_victim"
      ftrace_events: "oom/oom_score_adj_update"
      ftrace_events: "power/cpu_frequency"
      ftrace_events: "power/cpu_idle"
      ftrace_events: "power/gpu_frequency"
      ftrace_events: "power/suspend_resume"
      ftrace_events: "power/wakeup_source_activate"
      ftrace_events: "power/wakeup_source_deactivate"
      ftrace_events: "sched/sched_blocked_reason"
      ftrace_events: "sched/sched_process_exit"
      ftrace_events: "sched/sched_process_free"
      ftrace_events: "sched/sched_switch"
      ftrace_events: "sched/sched_wakeup"
      ftrace_events: "sched/sched_wakeup_new"
      ftrace_events: "sched/sched_waking"
      ftrace_events: "task/task_newtask"
      ftrace_events: "task/task_rename"
      ftrace_events: "vmscan/*"
      ftrace_events: "workqueue/*"
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
duration_ms: 10000
write_into_file: true
file_write_period_ms: 5000
max_file_size_bytes: 100000000000
flush_period_ms: 5000
incremental_state_config {{
  clear_period_ms: 5000
}}
'''

TEST_DEFAULT_CONFIG_OLD_ANDROID = f'''\
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
      ftrace_events: "dmabuf_heap/dma_heap_stat"
      ftrace_events: "ftrace/print"
      ftrace_events: "gpu_mem/gpu_mem_total"
      ftrace_events: "ion/ion_stat"
      ftrace_events: "kmem/ion_heap_grow"
      ftrace_events: "kmem/ion_heap_shrink"
      ftrace_events: "kmem/rss_stat"
      ftrace_events: "lowmemorykiller/lowmemory_kill"
      ftrace_events: "mm_event/mm_event_record"
      ftrace_events: "oom/mark_victim"
      ftrace_events: "oom/oom_score_adj_update"
      ftrace_events: "power/cpu_frequency"
      ftrace_events: "power/cpu_idle"
      ftrace_events: "power/gpu_frequency"
      ftrace_events: "power/suspend_resume"
      ftrace_events: "power/wakeup_source_activate"
      ftrace_events: "power/wakeup_source_deactivate"
      ftrace_events: "sched/sched_blocked_reason"
      ftrace_events: "sched/sched_process_exit"
      ftrace_events: "sched/sched_process_free"
      ftrace_events: "sched/sched_switch"
      ftrace_events: "sched/sched_wakeup"
      ftrace_events: "sched/sched_wakeup_new"
      ftrace_events: "sched/sched_waking"
      ftrace_events: "task/task_newtask"
      ftrace_events: "task/task_rename"
      ftrace_events: "vmscan/*"
      ftrace_events: "workqueue/*"
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
duration_ms: 10000
write_into_file: true
file_write_period_ms: 5000
max_file_size_bytes: 100000000000
flush_period_ms: 5000
incremental_state_config {{
  clear_period_ms: 5000
}}
'''


class ProfilerCommandExecutorUnitTest(unittest.TestCase):

  def setUp(self):
    self.command = ProfilerCommand(
        PROFILER_COMMAND_TYPE, "custom", PROFILER_TYPE, DEFAULT_OUT_DIR, DEFAULT_DUR_MS,
        None, 1, None, DEFAULT_PERFETTO_CONFIG, None, False, None, None, None,
        None)
    self.mock_device = mock.create_autospec(AdbDevice, instance=True,
                                            serial=TEST_SERIAL)
    self.mock_device.check_device_connection.return_value = None
    self.mock_device.get_android_sdk_version.return_value = ANDROID_SDK_VERSION_T

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_one_run_and_use_ui_success(self, mock_process):
    with mock.patch("command_executor.open_trace", autospec=True):
      self.command.use_ui = True
      self.mock_device.start_perfetto_trace.return_value = mock_process

      error = self.command.execute(self.mock_device)

      self.assertEqual(error, None)
      self.assertEqual(self.mock_device.pull_file.call_count, 1)

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_one_run_no_ui_success(self, mock_process):
    self.mock_device.start_perfetto_trace.return_value = mock_process

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)

  def test_execute_check_device_connection_failure(self):
    self.mock_device.check_device_connection.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_root_device_failure(self):
    self.mock_device.root_device.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_create_default_config_no_dur_ms_error(self):
    self.command.dur_ms = None

    with self.assertRaises(ValueError) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception),
                     "Cannot create config because a valid dur_ms was not set.")
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_create_default_config_bad_excluded_ftrace_event_error(self):
    self.command.excluded_ftrace_events = ["mock-ftrace-event"]

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message,
                     ("Cannot remove ftrace event %s from config because it is"
                      " not one of the config's ftrace events."
                      % self.command.excluded_ftrace_events[0]))
    self.assertEqual(error.suggestion, ("Please specify one of the following"
                                        " possible ftrace events:\n\t"
                                        " dmabuf_heap/dma_heap_stat\n\t"
                                        " ftrace/print\n\t"
                                        " gpu_mem/gpu_mem_total\n\t"
                                        " ion/ion_stat\n\t"
                                        " kmem/ion_heap_grow\n\t"
                                        " kmem/ion_heap_shrink\n\t"
                                        " kmem/rss_stat\n\t"
                                        " lowmemorykiller/lowmemory_kill\n\t"
                                        " mm_event/mm_event_record\n\t"
                                        " oom/mark_victim\n\t"
                                        " oom/oom_score_adj_update\n\t"
                                        " power/cpu_frequency\n\t"
                                        " power/cpu_idle\n\t"
                                        " power/gpu_frequency\n\t"
                                        " power/suspend_resume\n\t"
                                        " power/wakeup_source_activate\n\t"
                                        " power/wakeup_source_deactivate\n\t"
                                        " sched/sched_blocked_reason\n\t"
                                        " sched/sched_process_exit\n\t"
                                        " sched/sched_process_free\n\t"
                                        " sched/sched_switch\n\t"
                                        " sched/sched_wakeup\n\t"
                                        " sched/sched_wakeup_new\n\t"
                                        " sched/sched_waking\n\t"
                                        " task/task_newtask\n\t"
                                        " task/task_rename\n\t"
                                        " vmscan/*\n\t"
                                        " workqueue/*"))
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_create_default_config_bad_included_ftrace_event_error(self):
    self.command.included_ftrace_events = ["power/cpu_idle"]

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message,
                     ("Cannot add ftrace event %s to config because it is"
                      " already one of the config's ftrace events."
                      % self.command.included_ftrace_events[0]))
    self.assertEqual(error.suggestion, ("Please do not specify any of the"
                                        " following ftrace events that are"
                                        " already included:\n\t"
                                        " dmabuf_heap/dma_heap_stat\n\t"
                                        " ftrace/print\n\t"
                                        " gpu_mem/gpu_mem_total\n\t"
                                        " ion/ion_stat\n\t"
                                        " kmem/ion_heap_grow\n\t"
                                        " kmem/ion_heap_shrink\n\t"
                                        " kmem/rss_stat\n\t"
                                        " lowmemorykiller/lowmemory_kill\n\t"
                                        " mm_event/mm_event_record\n\t"
                                        " oom/mark_victim\n\t"
                                        " oom/oom_score_adj_update\n\t"
                                        " power/cpu_frequency\n\t"
                                        " power/cpu_idle\n\t"
                                        " power/gpu_frequency\n\t"
                                        " power/suspend_resume\n\t"
                                        " power/wakeup_source_activate\n\t"
                                        " power/wakeup_source_deactivate\n\t"
                                        " sched/sched_blocked_reason\n\t"
                                        " sched/sched_process_exit\n\t"
                                        " sched/sched_process_free\n\t"
                                        " sched/sched_switch\n\t"
                                        " sched/sched_wakeup\n\t"
                                        " sched/sched_wakeup_new\n\t"
                                        " sched/sched_waking\n\t"
                                        " task/task_newtask\n\t"
                                        " task/task_rename\n\t"
                                        " vmscan/*\n\t"
                                        " workqueue/*"))
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_remove_file_failure(self):
    self.mock_device.remove_file.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_start_perfetto_trace_failure(self):
    self.mock_device.start_perfetto_trace.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_process_wait_failure(self, mock_process):
    self.mock_device.start_perfetto_trace.return_value = mock_process
    mock_process.wait.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_pull_file_failure(self, mock_process):
    self.mock_device.start_perfetto_trace.return_value = mock_process
    self.mock_device.pull_file.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)


class UserSwitchCommandExecutorUnitTest(unittest.TestCase):

  def simulate_user_switch(self, user):
    self.current_user = user

  def setUp(self):
    self.command = ProfilerCommand(
        PROFILER_COMMAND_TYPE, "user-switch", PROFILER_TYPE, DEFAULT_OUT_DIR,
        DEFAULT_DUR_MS, None, 1, None, DEFAULT_PERFETTO_CONFIG, None, False,
        None, None, None, None)
    self.mock_device = mock.create_autospec(AdbDevice, instance=True,
                                            serial=TEST_SERIAL)
    self.mock_device.check_device_connection.return_value = None
    self.mock_device.user_exists.return_value = None
    self.current_user = TEST_USER_ID_3
    self.mock_device.get_current_user.side_effect = lambda: self.current_user
    self.mock_device.get_android_sdk_version.return_value = ANDROID_SDK_VERSION_T

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_all_users_different_success(self, mock_process):
    self.command.from_user = TEST_USER_ID_1
    self.command.to_user = TEST_USER_ID_2
    self.mock_device.start_perfetto_trace.return_value = mock_process
    self.mock_device.perform_user_switch.side_effect = (
        lambda user: self.simulate_user_switch(user))

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.current_user, TEST_USER_ID_3)
    self.assertEqual(self.mock_device.perform_user_switch.call_count, 3)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_perform_user_switch_failure(self, mock_process):
    self.command.from_user = TEST_USER_ID_2
    self.command.to_user = TEST_USER_ID_1
    self.mock_device.start_perfetto_trace.return_value = mock_process
    self.mock_device.perform_user_switch.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.perform_user_switch.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_to_user_is_from_user_error(self):
    self.command.from_user = TEST_USER_ID_1
    self.command.to_user = TEST_USER_ID_1

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message, ("Cannot perform user-switch to user %s"
                                     " because the current user on device"
                                     " %s is already %s."
                                     % (TEST_USER_ID_1, TEST_SERIAL,
                                        TEST_USER_ID_1)))
    self.assertEqual(error.suggestion, ("Choose a --to-user ID that is"
                                        " different than the --from-user ID."))
    self.assertEqual(self.mock_device.perform_user_switch.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_from_user_empty_success(self, mock_process):
    self.command.from_user = None
    self.command.to_user = TEST_USER_ID_2
    self.mock_device.start_perfetto_trace.return_value = mock_process
    self.mock_device.perform_user_switch.side_effect = (
        lambda user: self.simulate_user_switch(user))

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.current_user, TEST_USER_ID_3)
    self.assertEqual(self.mock_device.perform_user_switch.call_count, 2)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)

  def test_execute_to_user_is_current_user_and_from_user_empty_error(self):
    self.command.from_user = None
    self.command.to_user = self.current_user

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message, ("Cannot perform user-switch to user %s"
                                     " because the current user on device"
                                     " %s is already %s."
                                     % (self.current_user, TEST_SERIAL,
                                        self.current_user)))
    self.assertEqual(error.suggestion, ("Choose a --to-user ID that is"
                                        " different than the --from-user ID."))
    self.assertEqual(self.mock_device.perform_user_switch.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_from_user_is_current_user_success(self, mock_process):
    self.command.from_user = self.current_user
    self.command.to_user = TEST_USER_ID_2
    self.mock_device.start_perfetto_trace.return_value = mock_process
    self.mock_device.perform_user_switch.side_effect = (
        lambda user: self.simulate_user_switch(user))

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.current_user, TEST_USER_ID_3)
    self.assertEqual(self.mock_device.perform_user_switch.call_count, 2)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)

  @mock.patch.object(subprocess, "Popen", autospec=True)
  def test_execute_to_user_is_current_user_success(self, mock_process):
    self.command.from_user = TEST_USER_ID_1
    self.command.to_user = self.current_user
    self.mock_device.start_perfetto_trace.return_value = mock_process
    self.mock_device.perform_user_switch.side_effect = (
        lambda user: self.simulate_user_switch(user))

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.current_user, TEST_USER_ID_3)
    self.assertEqual(self.mock_device.perform_user_switch.call_count, 2)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)


class BootCommandExecutorUnitTest(unittest.TestCase):

  def setUp(self):
    self.command = ProfilerCommand(
        PROFILER_COMMAND_TYPE, "boot", PROFILER_TYPE, DEFAULT_OUT_DIR,
        TEST_DURATION, None, 1, None, DEFAULT_PERFETTO_CONFIG, TEST_DURATION,
        False, None, None, None, None)
    self.mock_device = mock.create_autospec(AdbDevice, instance=True,
                                            serial=TEST_SERIAL)
    self.mock_device.check_device_connection.return_value = None
    self.mock_device.get_android_sdk_version.return_value = ANDROID_SDK_VERSION_T

  def test_execute_reboot_success(self):
    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.mock_device.reboot.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)

  def test_execute_reboot_multiple_runs_success(self):
    self.command.runs = 5

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.mock_device.reboot.call_count, 5)
    self.assertEqual(self.mock_device.pull_file.call_count, 5)

  def test_execute_reboot_failure(self):
    self.mock_device.reboot.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.reboot.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_get_prop_and_old_android_version_failure(self):
    self.mock_device.get_android_sdk_version.return_value = ANDROID_SDK_VERSION_S

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message, (
        "Cannot perform trace on boot because only devices with version Android 13 (T)"
        " or newer can be configured to automatically start recording traces on boot."))
    self.assertEqual(error.suggestion, (
        "Update your device or use a different device with Android 13 (T) or"
        " newer."))
    self.assertEqual(self.mock_device.reboot.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_write_to_file_failure(self):
    self.mock_device.write_to_file.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.reboot.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_remove_file_failure(self):
    self.mock_device.remove_file.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.reboot.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_set_prop_failure(self):
    self.mock_device.set_prop.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.reboot.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_wait_for_device_failure(self):
    self.mock_device.wait_for_device.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.reboot.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_second_root_device_failure(self):
    self.mock_device.root_device.side_effect = [None, TEST_EXCEPTION]

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.reboot.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_execute_wait_for_boot_to_complete_failure(self):
    self.mock_device.wait_for_boot_to_complete.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.reboot.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)


class AppStartupExecutorUnitTest(unittest.TestCase):

  def setUp(self):
    self.command = ProfilerCommand(
        PROFILER_COMMAND_TYPE, "app-startup", PROFILER_TYPE, DEFAULT_OUT_DIR,
        DEFAULT_DUR_MS, TEST_PACKAGE_1, 1, None, DEFAULT_PERFETTO_CONFIG, None,
        False, None, None, None, None)
    self.mock_device = mock.create_autospec(AdbDevice, instance=True,
                                            serial=TEST_SERIAL)
    self.mock_device.check_device_connection.return_value = None
    self.mock_device.get_packages.return_value = [TEST_PACKAGE_1,
                                                  TEST_PACKAGE_2]
    self.mock_device.is_package_running.return_value = False
    self.mock_device.get_android_sdk_version.return_value = ANDROID_SDK_VERSION_T

  def test_app_startup_command_success(self):
    self.mock_device.start_package.return_value = None

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(self.mock_device.start_package.call_count, 1)
    self.assertEqual(self.mock_device.force_stop_package.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 1)

  def test_start_package_failure(self):
    self.mock_device.start_package.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.start_package.call_count, 1)
    self.assertEqual(self.mock_device.force_stop_package.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_get_packages_failure(self):
    self.mock_device.get_packages.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.start_package.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_package_does_not_exist_failure(self):
    self.mock_device.get_packages.return_value = [TEST_PACKAGE_2,
                                                  TEST_PACKAGE_3]

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message, (
        "Package %s does not exist on device with serial %s."
        % (TEST_PACKAGE_1, self.mock_device.serial)))
    self.assertEqual(error.suggestion, (
        "Select from one of the following packages on device with serial %s:"
        " \n\t %s,\n\t %s" % (self.mock_device.serial, TEST_PACKAGE_2,
                              TEST_PACKAGE_3)))
    self.assertEqual(self.mock_device.start_package.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_package_is_running_failure(self):
    self.mock_device.is_package_running.return_value = True

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message, (
        "Package %s is already running on device with serial %s."
        % (TEST_PACKAGE_1, self.mock_device.serial)))
    self.assertEqual(error.suggestion, (
        "Run 'adb -s %s shell am force-stop %s' to close the package %s before"
        " trying to start it."
        % (self.mock_device.serial, TEST_PACKAGE_1, TEST_PACKAGE_1)))
    self.assertEqual(self.mock_device.start_package.call_count, 0)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_force_stop_package_failure(self):
    self.mock_device.start_package.return_value = None
    self.mock_device.force_stop_package.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.start_package.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_kill_pid_success(self):
    self.mock_device.start_package.return_value = TEST_VALIDATION_ERROR

    error = self.command.execute(self.mock_device)

    self.assertNotEqual(error, None)
    self.assertEqual(error.message, TEST_ERROR_MSG)
    self.assertEqual(error.suggestion, None)
    self.assertEqual(self.mock_device.start_package.call_count, 1)
    self.assertEqual(self.mock_device.kill_pid.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)

  def test_kill_pid_failure(self):
    self.mock_device.start_package.return_value = TEST_VALIDATION_ERROR
    self.mock_device.kill_pid.side_effect = TEST_EXCEPTION

    with self.assertRaises(Exception) as e:
      self.command.execute(self.mock_device)

    self.assertEqual(str(e.exception), TEST_ERROR_MSG)
    self.assertEqual(self.mock_device.start_package.call_count, 1)
    self.assertEqual(self.mock_device.kill_pid.call_count, 1)
    self.assertEqual(self.mock_device.pull_file.call_count, 0)


class ConfigCommandExecutorUnitTest(unittest.TestCase):

  def setUp(self):
    self.mock_device = mock.create_autospec(AdbDevice, instance=True,
                                            serial=TEST_SERIAL)
    self.mock_device.check_device_connection.return_value = None
    self.mock_device.get_android_sdk_version.return_value = (
        ANDROID_SDK_VERSION_T)

  @staticmethod
  def generate_mock_completed_process(stdout_string=b'\n', stderr_string=b'\n'):
    return mock.create_autospec(subprocess.CompletedProcess, instance=True,
                                stdout=stdout_string, stderr=stderr_string)

  def test_config_list(self):
    terminal_output = io.StringIO()
    sys.stdout = terminal_output

    self.command = ConfigCommand("config list", None, None, None, None, None)
    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(terminal_output.getvalue(), (
        "%s\n" % "\n".join(list(PREDEFINED_PERFETTO_CONFIGS.keys()))))

  def test_config_show(self):
    terminal_output = io.StringIO()
    sys.stdout = terminal_output

    self.command = ConfigCommand("config show", "default", None, DEFAULT_DUR_MS,
                                 None, None)
    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(terminal_output.getvalue(), TEST_DEFAULT_CONFIG)

  def test_config_show_no_device_connection(self):
    self.mock_device.check_device_connection.return_value = (
        TEST_VALIDATION_ERROR)
    terminal_output = io.StringIO()
    sys.stdout = terminal_output

    self.command = ConfigCommand("config show", "default", None, DEFAULT_DUR_MS,
                                 None, None)
    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(terminal_output.getvalue(), TEST_DEFAULT_CONFIG)

  def test_config_show_old_android_version(self):
    self.mock_device.get_android_sdk_version.return_value = (
        ANDROID_SDK_VERSION_S)
    terminal_output = io.StringIO()
    sys.stdout = terminal_output

    self.command = ConfigCommand("config show", "default", None, DEFAULT_DUR_MS,
                                 None, None)
    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)
    self.assertEqual(terminal_output.getvalue(),
                     TEST_DEFAULT_CONFIG_OLD_ANDROID)

  @mock.patch.object(subprocess, "run", autospec=True)
  def test_config_pull(self, mock_subprocess_run):
    mock_subprocess_run.return_value = self.generate_mock_completed_process()
    self.command = ConfigCommand("config pull", "default", None, DEFAULT_DUR_MS,
                                 None, None)

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)

  @mock.patch.object(subprocess, "run", autospec=True)
  def test_config_pull_no_device_connection(self, mock_subprocess_run):
    self.mock_device.check_device_connection.return_value = (
        TEST_VALIDATION_ERROR)
    mock_subprocess_run.return_value = self.generate_mock_completed_process()
    self.command = ConfigCommand("config pull", "default", None, DEFAULT_DUR_MS,
                                 None, None)

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)

  @mock.patch.object(subprocess, "run", autospec=True)
  def test_config_pull_old_android_version(self, mock_subprocess_run):
    self.mock_device.get_android_sdk_version.return_value = (
        ANDROID_SDK_VERSION_S)
    mock_subprocess_run.return_value = self.generate_mock_completed_process()
    self.command = ConfigCommand("config pull", "default", None, DEFAULT_DUR_MS,
                                 None, None)

    error = self.command.execute(self.mock_device)

    self.assertEqual(error, None)


if __name__ == '__main__':
  unittest.main()
