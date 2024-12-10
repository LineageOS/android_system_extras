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

import time
from abc import ABC, abstractmethod
from config_builder import PREDEFINED_PERFETTO_CONFIGS, build_custom_config
from open_ui import open_trace

PERFETTO_TRACE_FILE = "/data/misc/perfetto-traces/trace.perfetto-trace"
PERFETTO_BOOT_TRACE_FILE = "/data/misc/perfetto-traces/boottrace.perfetto-trace"
PERFETTO_WEB_UI_ADDRESS = "https://ui.perfetto.dev"
PERFETTO_TRACE_START_DELAY_SECS = 0.5


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
    config, error = self.create_config(command)
    if error is not None:
      return error
    error = self.prepare_device(command, device, config)
    if error is not None:
      return error
    host_file = None
    for run in range(1, command.runs + 1):
      host_file = f"{command.out_dir}/trace-{run}.perfetto-trace"
      error = self.prepare_device_for_run(command, device, run)
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
      open_trace(host_file, PERFETTO_WEB_UI_ADDRESS)
    return None

  def create_config(self, command):
    if command.perfetto_config in PREDEFINED_PERFETTO_CONFIGS:
      return PREDEFINED_PERFETTO_CONFIGS[command.perfetto_config](command)
    else:
      return build_custom_config(command)

  def prepare_device(self, command, device, config):
    return None

  def prepare_device_for_run(self, command, device, run):
    device.remove_file(PERFETTO_TRACE_FILE)

  def execute_run(self, command, device, config, run):
    print("Performing run %s" % run)
    process = device.start_perfetto_trace(config)
    time.sleep(PERFETTO_TRACE_START_DELAY_SECS)
    error = self.trigger_system_event(command, device)
    if error is not None:
      device.kill_pid("perfetto")
      return error
    process.wait()

  def trigger_system_event(self, command, device):
    return None

  def retrieve_perf_data(self, command, device, host_file):
    device.pull_file(PERFETTO_TRACE_FILE, host_file)

  def cleanup(self, command, device):
    return None


class UserSwitchCommandExecutor(ProfilerCommandExecutor):

  def prepare_device_for_run(self, command, device, run):
    super().prepare_device_for_run(command, device, run)
    current_user = device.get_current_user()
    if command.from_user != current_user:
      print("Switching from the current user, %s, to the from-user, %s."
            % (current_user, command.from_user))
      device.perform_user_switch(command.from_user)

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

  def prepare_device_for_run(self, command, device, run):
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


class HWCommandExecutor(CommandExecutor):

  def execute_command(self, hw_command, device):
    match hw_command.get_type():
      case "hw set":
        return self.execute_hw_set_command(device, hw_command.hw_config,
                                           hw_command.num_cpus,
                                           hw_command.memory)
      case "hw get":
        return self.execute_hw_get_command(device)
      case "hw list":
        return self.execute_hw_list_command(device)
      case _:
        raise ValueError("Invalid hw subcommand was used.")

  def execute_hw_set_command(self, device, hw_config, num_cpus, memory):
    return None

  def execute_hw_get_command(self, device):
    return None

  def execute_hw_list_command(self, device):
    return None


class ConfigCommandExecutor(CommandExecutor):

  def execute(self, command, device):
    return self.execute_command(command, device)

  def execute_command(self, config_command, device):
    match config_command.get_type():
      case "config list":
        return self.execute_config_list_command()
      case "config show":
        return self.execute_config_show_command(config_command.config_name)
      case "config pull":
        return self.execute_config_pull_command(config_command.config_name,
                                                config_command.file_path)
      case _:
        raise ValueError("Invalid config subcommand was used.")

  def execute_config_list_command(self):
    return None

  def execute_config_show_command(self, config_name):
    return None

  def execute_config_pull_command(self, config_name, file_path):
    return None
