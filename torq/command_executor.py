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

import datetime
import subprocess
import time
from abc import ABC, abstractmethod
from config_builder import PREDEFINED_PERFETTO_CONFIGS, build_custom_config
from open_ui import open_trace
from device import SIMPLEPERF_TRACE_FILE

PERFETTO_TRACE_FILE = "/data/misc/perfetto-traces/trace.perfetto-trace"
PERFETTO_BOOT_TRACE_FILE = "/data/misc/perfetto-traces/boottrace.perfetto-trace"
WEB_UI_ADDRESS = "https://ui.perfetto.dev"
TRACE_START_DELAY_SECS = 0.5
MAX_WAIT_FOR_INIT_USER_SWITCH_SECS = 180
ANDROID_SDK_VERSION_T = 33


class CommandExecutor(ABC):
  """
  Abstract base class representing a command executor.
  """
  def __init__(self):
    pass

  def execute(self, command, device):
    error = device.check_device_connection()
    if error is not None:
      return error
    device.root_device()
    error = command.validate(device)
    if error is not None:
      return error
    return self.execute_command(command, device)

  @abstractmethod
  def execute_command(self, command, device):
    raise NotImplementedError


class ProfilerCommandExecutor(CommandExecutor):

  def execute_command(self, command, device):
    config, error = self.create_config(command, device.get_android_sdk_version())
    if error is not None:
      return error
    error = self.prepare_device(command, device, config)
    if error is not None:
      return error
    host_file = None
    for run in range(1, command.runs + 1):
      timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
      if command.profiler == "perfetto":
        host_file = f"{command.out_dir}/trace-{timestamp}.perfetto-trace"
      else:
        host_file = f"{command.out_dir}/perf-{timestamp}.data"
      error = self.prepare_device_for_run(command, device)
      if error is not None:
        return error
      error = self.execute_run(command, device, config, run)
      if error is not None:
        return error
      error = self.retrieve_perf_data(command, device, host_file)
      if error is not None:
        return error
      if command.runs != run:
        time.sleep(command.between_dur_ms / 1000)
    error = self.cleanup(command, device)
    if error is not None:
      return error
    if command.use_ui:
      open_trace(host_file, WEB_UI_ADDRESS)
    return None

  @staticmethod
  def create_config(command, android_sdk_version):
    if command.perfetto_config in PREDEFINED_PERFETTO_CONFIGS:
      return PREDEFINED_PERFETTO_CONFIGS[command.perfetto_config](
          command, android_sdk_version)
    else:
      return build_custom_config(command)

  def prepare_device(self, command, device, config):
    return None

  def prepare_device_for_run(self, command, device):
    if command.profiler == "perfetto":
      device.remove_file(PERFETTO_TRACE_FILE)
    else:
      device.remove_file(SIMPLEPERF_TRACE_FILE)

  def execute_run(self, command, device, config, run):
    print("Performing run %s" % run)
    if command.profiler == "perfetto":
      process = device.start_perfetto_trace(config)
    else:
      process = device.start_simpleperf_trace(command)
    time.sleep(TRACE_START_DELAY_SECS)
    error = self.trigger_system_event(command, device)
    if error is not None:
      device.kill_pid(command.profiler)
      return error
    process.wait()

  def trigger_system_event(self, command, device):
    return None

  def retrieve_perf_data(self, command, device, host_file):
    if command.profiler == "perfetto":
      device.pull_file(PERFETTO_TRACE_FILE, host_file)
    else:
      device.pull_file(SIMPLEPERF_TRACE_FILE, host_file)

  def cleanup(self, command, device):
    return None


class UserSwitchCommandExecutor(ProfilerCommandExecutor):

  def prepare_device_for_run(self, command, device):
    super().prepare_device_for_run(command, device)
    current_user = device.get_current_user()
    if command.from_user != current_user:
      dur_seconds = min(command.dur_ms / 1000,
                        MAX_WAIT_FOR_INIT_USER_SWITCH_SECS)
      print("Switching from the current user, %s, to the from-user, %s. Waiting"
            " for %s seconds."
            % (current_user, command.from_user, dur_seconds))
      device.perform_user_switch(command.from_user)
      time.sleep(dur_seconds)
      if device.get_current_user() != command.from_user:
        raise Exception(("Device with serial %s took more than %d secs to "
                         "switch to the initial user."
                         % (device.serial, dur_seconds)))

  def trigger_system_event(self, command, device):
    print("Switching from the from-user, %s, to the to-user, %s."
          % (command.from_user, command.to_user))
    device.perform_user_switch(command.to_user)

  def cleanup(self, command, device):
    if device.get_current_user() != command.original_user:
      print("Switching from the to-user, %s, back to the original user, %s."
            % (command.to_user, command.original_user))
      device.perform_user_switch(command.original_user)


class BootCommandExecutor(ProfilerCommandExecutor):

  def prepare_device(self, command, device, config):
    device.write_to_file("/data/misc/perfetto-configs/boottrace.pbtxt", config)

  def prepare_device_for_run(self, command, device):
    device.remove_file(PERFETTO_BOOT_TRACE_FILE)
    device.set_prop("persist.debug.perfetto.boottrace", "1")

  def execute_run(self, command, device, config, run):
    print("Performing run %s" % run)
    self.trigger_system_event(command, device)
    device.wait_for_device()
    device.root_device()
    dur_seconds = command.dur_ms / 1000
    print("Tracing for %s seconds." % dur_seconds)
    time.sleep(dur_seconds)
    device.wait_for_boot_to_complete()

  def trigger_system_event(self, command, device):
    device.reboot()

  def retrieve_perf_data(self, command, device, host_file):
    device.pull_file(PERFETTO_BOOT_TRACE_FILE, host_file)


class AppStartupCommandExecutor(ProfilerCommandExecutor):

  def execute_run(self, command, device, config, run):
    error = super().execute_run(command, device, config, run)
    if error is not None:
      return error
    device.force_stop_package(command.app)

  def trigger_system_event(self, command, device):
    return device.start_package(command.app)


class ConfigCommandExecutor(CommandExecutor):

  def execute(self, command, device):
    return self.execute_command(command, device)

  def execute_command(self, command, device):
    match command.get_type():
      case "config list":
        print("\n".join(list(PREDEFINED_PERFETTO_CONFIGS.keys())))
        return None
      case "config show" | "config pull":
        return self.execute_config_command(command, device)
      case _:
        raise ValueError("Invalid config subcommand was used.")

  def execute_config_command(self, command, device):
    android_sdk_version = ANDROID_SDK_VERSION_T
    error = device.check_device_connection()
    if error is None:
      device.root_device()
      android_sdk_version = device.get_android_sdk_version()

    config, error = PREDEFINED_PERFETTO_CONFIGS[command.config_name](
        command, android_sdk_version)

    if error is not None:
      return error

    if command.get_type() == "config pull":
      subprocess.run(("cat > %s %s" % (command.file_path, config)), shell=True)
    else:
      print("\n".join(config.strip().split("\n")[2:-2]))

    return None
