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

import math
import os
import subprocess
import time

from validation_error import ValidationError

ADB_ROOT_TIMED_OUT_LIMIT_SECS = 5
ADB_BOOT_COMPLETED_TIMED_OUT_LIMIT_SECS = 30
POLLING_INTERVAL_SECS = 0.5
SIMPLEPERF_TRACE_FILE = "/data/misc/perfetto-traces/perf.data"

class AdbDevice:
  """
  Class representing a device. APIs interact with the current device through
  the adb bridge.
  """
  def __init__(self, serial):
    self.serial = serial

  @staticmethod
  def get_adb_devices():
    """
    Returns a list of devices connected to the adb bridge.
    The output of the command 'adb devices' is expected to be of the form:
    List of devices attached
    SOMEDEVICE1234    device
    device2:5678    device
    """
    command_output = subprocess.run(["adb", "devices"], capture_output=True)
    output_lines = command_output.stdout.decode("utf-8").split("\n")
    devices = []
    for line in output_lines[:-2]:
      if line[0] == "*" or line == "List of devices attached":
        continue
      words_in_line = line.split('\t')
      if words_in_line[1] == "device":
        devices.append(words_in_line[0])
    return devices

  def check_device_connection(self):
    devices = self.get_adb_devices()
    if len(devices) == 0:
      return ValidationError("There are currently no devices connected.", None)
    if self.serial is not None:
      if self.serial not in devices:
        return ValidationError(("Device with serial %s is not connected."
                                % self.serial), None)
    elif "ANDROID_SERIAL" in os.environ:
      if os.environ["ANDROID_SERIAL"] not in devices:
        return ValidationError(("Device with serial %s is set as environment"
                                " variable, ANDROID_SERIAL, but is not"
                                " connected."
                                % os.environ["ANDROID_SERIAL"]), None)
      self.serial = os.environ["ANDROID_SERIAL"]
    elif len(devices) == 1:
      self.serial = devices[0]
    else:
      return ValidationError(("There is more than one device currently"
                              " connected."),
                             ("Run one of the following commands to choose one"
                              " of the connected devices:\n\t torq --serial %s"
                              % "\n\t torq --serial ".join(devices)))
    return None

  @staticmethod
  def poll_is_task_completed(timed_out_limit, interval, check_is_completed):
    start_time = time.time()
    while True:
      time.sleep(interval)
      if check_is_completed():
        return True
      if time.time() - start_time > timed_out_limit:
        return False

  def root_device(self):
    subprocess.run(["adb", "-s", self.serial, "root"])
    if not self.poll_is_task_completed(ADB_ROOT_TIMED_OUT_LIMIT_SECS,
                                       POLLING_INTERVAL_SECS,
                                       lambda: self.serial in
                                               self.get_adb_devices()):
      raise Exception(("Device with serial %s took too long to reconnect after"
                       " being rooted." % self.serial))

  def remove_file(self, file_path):
    subprocess.run(["adb", "-s", self.serial, "shell", "rm", "-f", file_path])

  def start_perfetto_trace(self, config):
    return subprocess.Popen(("adb -s %s shell perfetto -c - --txt -o"
                             " /data/misc/perfetto-traces/"
                             "trace.perfetto-trace %s"
                             % (self.serial, config)), shell=True)

  def start_simpleperf_trace(self, command):
    events_param = "-e " + ",".join(command.simpleperf_event)
    return subprocess.Popen(("adb -s %s shell simpleperf record -a -f 1000 "
                             "--post-unwind=yes -m 8192 -g --duration %d"
                             " %s -o %s"
                             % (self.serial,
                                int(math.ceil(command.dur_ms/1000)),
                                events_param, SIMPLEPERF_TRACE_FILE)),
                            shell=True)

  def pull_file(self, file_path, host_file):
    subprocess.run(["adb", "-s", self.serial, "pull", file_path, host_file])

  def get_all_users(self):
    command_output = subprocess.run(["adb", "-s", self.serial, "shell", "pm",
                                     "list", "users"], capture_output=True)
    output_lines = command_output.stdout.decode("utf-8").split("\n")[1:-1]
    return [int((line.split("{", 1)[1]).split(":", 1)[0]) for line in
            output_lines]

  def user_exists(self, user):
    users = self.get_all_users()
    if user not in users:
      return ValidationError(("User ID %s does not exist on device with serial"
                              " %s." % (user, self.serial)),
                             ("Select from one of the following user IDs on"
                              " device with serial %s: %s"
                              % (self.serial, ", ".join(map(str, users)))))
    return None

  def get_current_user(self):
    command_output = subprocess.run(["adb", "-s", self.serial, "shell", "am",
                                     "get-current-user"], capture_output=True)
    return int(command_output.stdout.decode("utf-8").split()[0])

  def perform_user_switch(self, user):
    subprocess.run(["adb", "-s", self.serial, "shell", "am", "switch-user",
                    str(user)])

  def write_to_file(self, file_path, host_file_string):
    subprocess.run(("adb -s %s shell 'cat > %s %s'"
                    % (self.serial, file_path, host_file_string)), shell=True)

  def set_prop(self, prop, value):
    subprocess.run(["adb", "-s", self.serial, "shell", "setprop", prop, value])

  def reboot(self):
    subprocess.run(["adb", "-s", self.serial, "reboot"])
    if not self.poll_is_task_completed(ADB_ROOT_TIMED_OUT_LIMIT_SECS,
                                       POLLING_INTERVAL_SECS,
                                       lambda: self.serial not in
                                               self.get_adb_devices()):
      raise Exception(("Device with serial %s took too long to start"
                       " rebooting." % self.serial))

  def wait_for_device(self):
    subprocess.run(["adb", "-s", self.serial, "wait-for-device"])

  def is_boot_completed(self):
    command_output = subprocess.run(["adb", "-s", self.serial, "shell",
                                     "getprop", "sys.boot_completed"],
                                    capture_output=True)
    return command_output.stdout.decode("utf-8").strip() == "1"

  def wait_for_boot_to_complete(self):
    if not self.poll_is_task_completed(ADB_BOOT_COMPLETED_TIMED_OUT_LIMIT_SECS,
                                       POLLING_INTERVAL_SECS,
                                       self.is_boot_completed):
      raise Exception(("Device with serial %s took too long to finish"
                       " rebooting." % self.serial))

  def get_packages(self):
    return [package.removeprefix("package:") for package in subprocess.run(
        ["adb", "-s", self.serial, "shell", "pm", "list", "packages"],
        capture_output=True).stdout.decode("utf-8").splitlines()]

  def get_pid(self, package):
    return subprocess.run("adb -s %s shell pidof %s" % (self.serial, package),
                          shell=True, capture_output=True
                          ).stdout.decode("utf-8").split("\n")[0]

  def is_package_running(self, package):
    return self.get_pid(package) != ""

  def start_package(self, package):
    if subprocess.run(
        ["adb", "-s", self.serial, "shell", "am", "start", package],
        capture_output=True).stderr.decode("utf-8").split("\n")[0] != "":
      return ValidationError(("Cannot start package %s on device with"
                              " serial %s because %s is a service package,"
                              " which doesn't implement a MAIN activity."
                              % (package, self.serial, package)), None)
    return None

  def kill_pid(self, package):
    pid = self.get_pid(package)
    if pid != "":
      subprocess.run(["adb", "-s", self.serial, "shell", "kill", "-9", pid])

  def force_stop_package(self, package):
    subprocess.run(["adb", "-s", self.serial, "shell", "am", "force-stop",
                    package])

  def get_prop(self, prop):
    return subprocess.run(
        ["adb", "-s", self.serial, "shell", "getprop", prop],
        capture_output=True).stdout.decode("utf-8").split("\n")[0]

  def get_android_sdk_version(self):
    return int(self.get_prop("ro.build.version.sdk"))

  def simpleperf_event_exists(self, simpleperf_events):
    events_copy = simpleperf_events.copy()
    grep_command = "grep"
    for event in simpleperf_events:
      grep_command += " -e " + event.lower()

    output = subprocess.run(["adb", "-s", self.serial, "shell",
                             "simpleperf", "list", "|", grep_command],
                            capture_output=True)

    if output is None or len(output.stdout) == 0:
      raise Exception("Error while validating simpleperf events.")
    lines = output.stdout.decode("utf-8").split("\n")

    # Anything that does not start with two spaces is not a command.
    # Any command with a space will have the command before the first space.
    for line in lines:
      if len(line) <= 3 or line[:2] != "  " or line[2] == "#":
        # Line doesn't contain a simpleperf event
        continue
      event = line[2:].split(" ")[0]
      if event in events_copy:
        events_copy.remove(event)
        if len(events_copy) == 0:
          # All of the events exist, exit early
          break

    if len(events_copy) > 0:
      return ValidationError("The following simpleperf event(s) are invalid:"
                             " %s."
                             % events_copy,
                             "Run adb shell simpleperf list to"
                             " see valid simpleperf events.")
    return None
