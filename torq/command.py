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

from abc import ABC, abstractmethod
from command_executor import ProfilerCommandExecutor, \
  UserSwitchCommandExecutor, BootCommandExecutor, AppStartupCommandExecutor, \
  HWCommandExecutor, ConfigCommandExecutor
from validation_error import ValidationError


class Command(ABC):
  """
  Abstract base class representing a command.
  """
  def __init__(self, type):
    self.type = type
    self.command_executor = None

  def get_type(self):
    return self.type

  def execute(self, device):
    return self.command_executor.execute(self, device)

  @abstractmethod
  def validate(self, device):
    raise NotImplementedError


class ProfilerCommand(Command):
  """
  Represents commands which profile and trace the system.
  """
  def __init__(self, type, event, profiler, out_dir, dur_ms, app, runs,
      simpleperf_event, perfetto_config, between_dur_ms, ui,
      excluded_ftrace_events, included_ftrace_events, from_user, to_user):
    super().__init__(type)
    self.event = event
    self.profiler = profiler
    self.out_dir = out_dir
    self.dur_ms = dur_ms
    self.app = app
    self.runs = runs
    self.simpleperf_event = simpleperf_event
    self.perfetto_config = perfetto_config
    self.between_dur_ms = between_dur_ms
    self.use_ui = ui
    self.excluded_ftrace_events = excluded_ftrace_events
    self.included_ftrace_events = included_ftrace_events
    self.from_user = from_user
    self.to_user = to_user
    match event:
      case "custom":
        self.command_executor = ProfilerCommandExecutor()
      case "user-switch":
        self.original_user = None
        self.command_executor = UserSwitchCommandExecutor()
      case "boot":
        self.command_executor = BootCommandExecutor()
      case "app-startup":
        self.command_executor = AppStartupCommandExecutor()
      case _:
        raise ValueError("Invalid event name was used.")

  def validate(self, device):
    print("Further validating arguments of ProfilerCommand.")
    if self.simpleperf_event is not None:
      device.simpleperf_event_exists(self.simpleperf_event)
    match self.event:
      case "user-switch":
        return self.validate_user_switch(device)
      case "app-startup":
        return self.validate_app_startup(device)

  def validate_user_switch(self, device):
    error = device.user_exists(self.to_user)
    if error is not None:
      return error
    self.original_user = device.get_current_user()
    if self.from_user is None:
      self.from_user = self.original_user
    else:
      error = device.user_exists(self.from_user)
      if error is not None:
        return error
    if self.from_user == self.to_user:
      return ValidationError("Cannot perform user-switch to user %s because"
                             " the current user on device %s is already %s."
                             % (self.to_user, device.serial, self.from_user),
                             "Choose a --to-user ID that is different than"
                             " the --from-user ID.")
    return None

  def validate_app_startup(self, device):
    packages = device.get_packages()
    if self.app not in packages:
      return ValidationError(("Package %s does not exist on device with serial"
                              " %s." % (self.app, device.serial)),
                             ("Select from one of the following packages on"
                              " device with serial %s: \n\t %s"
                              % (device.serial, (",\n\t ".join(packages)))))
    if device.is_package_running(self.app):
      return ValidationError(("Package %s is already running on device with"
                              " serial %s." % (self.app, device.serial)),
                             ("Run 'adb -s %s shell am force-stop %s' to close"
                              " the package %s before trying to start it."
                              % (device.serial, self.app, self.app)))
    return None


class HWCommand(Command):
  """
  Represents commands which get information from the device or changes the
  device's hardware.
  """
  def __init__(self, type, hw_config, num_cpus, memory):
    super().__init__(type)
    self.hw_config = hw_config
    self.num_cpus = num_cpus
    self.memory = memory
    self.command_executor = HWCommandExecutor()

  def validate(self, device):
    print("Further validating arguments of HWCommand.")
    if self.num_cpus is not None:
      if self.num_cpus > device.get_max_num_cpus():
        return ValidationError(("The number of cpus requested is not"
                                " available on the device. Requested: %d,"
                                " Available: %d"
                                % (self.num_cpus, device.get_max_num_cpus())),
                               None)
    if self.memory is not None:
      if self.memory > device.get_max_memory():
        return ValidationError(("The amount of memory requested is not"
                                "available on the device. Requested: %s,"
                                " Available: %s"
                                % (self.memory, device.get_max_memory())), None)
    return None


class ConfigCommand(Command):
  """
  Represents commands which get information about the predefined configs.
  """
  def __init__(self, type, config_name, file_path):
    super().__init__(type)
    self.config_name = config_name
    self.file_path = file_path
    self.command_executor = ConfigCommandExecutor()

  def validate(self, device):
    raise NotImplementedError
