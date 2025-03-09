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
import sys
import os
from unittest import mock
from torq import create_parser, verify_args, get_command_type,\
  DEFAULT_DUR_MS, DEFAULT_OUT_DIR

TEST_USER_ID = 10
TEST_PACKAGE = "com.android.contacts"
TEST_FILE = "file.pbtxt"
SYMBOLS_PATH = "/folder/symbols"


class TorqUnitTest(unittest.TestCase):

  def set_up_parser(self, command_string):
    parser = create_parser()
    sys.argv = command_string.split()
    return parser

  # TODO(b/285191111): Parameterize the test functions.
  def test_create_parser_default_values(self):
    parser = self.set_up_parser("torq.py")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.event, "custom")
    self.assertEqual(args.profiler, "perfetto")
    self.assertEqual(args.out_dir, DEFAULT_OUT_DIR)
    self.assertEqual(args.runs, 1)
    self.assertEqual(args.perfetto_config, "default")
    self.assertEqual(args.dur_ms, DEFAULT_DUR_MS)
    self.assertEqual(args.between_dur_ms, DEFAULT_DUR_MS)

  def test_create_parser_valid_event_names(self):
    parser = self.set_up_parser("torq.py -e custom")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.event, "custom")

    parser = self.set_up_parser("torq.py -e boot")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.event, "boot")

    parser = self.set_up_parser(
        "torq.py -e user-switch --to-user %s" % str(TEST_USER_ID))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.event, "user-switch")

    parser = self.set_up_parser(
        "torq.py -e app-startup --app %s" % TEST_PACKAGE)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.event, "app-startup")

  def test_create_parser_invalid_event_names(self):
    parser = self.set_up_parser("torq.py -e fake-event")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  @mock.patch.object(os.path, "exists", autospec=True)
  @mock.patch.object(os.path, "isdir", autospec=True)
  def test_create_parser_valid_profiler_names(self, mock_isdir, mock_exists):
    mock_isdir.return_value = True
    mock_exists.return_value = True
    parser = self.set_up_parser("torq.py -p perfetto")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.profiler, "perfetto")

    parser = self.set_up_parser("torq.py -p simpleperf --symbols %s"
                                % SYMBOLS_PATH)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.profiler, "simpleperf")

  def test_create_parser_invalid_profiler_names(self):
    parser = self.set_up_parser("torq.py -p fake-profiler")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  @mock.patch.object(os.path, "isdir", autospec=True)
  def test_verify_args_valid_out_dir_path(self, mock_is_dir):
    mock_is_dir.return_value = True
    parser = self.set_up_parser("torq.py -o mock-directory")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.out_dir, "mock-directory")

  @mock.patch.object(os.path, "isdir", autospec=True)
  def test_verify_args_invalid_out_dir_paths(self, mock_is_dir):
    mock_is_dir.return_value = False
    parser = self.set_up_parser("torq.py -o mock-file")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --out-dir is not a valid"
                                     " directory path: mock-file."))
    self.assertEqual(error.suggestion, None)

  def test_create_parser_valid_ui(self):
    parser = self.set_up_parser("torq.py --ui")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.ui, True)

    parser = self.set_up_parser("torq.py --no-ui")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.ui, False)

  def test_verify_args_valid_dur_ms_values(self):
    parser = self.set_up_parser("torq.py -d 100000")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.dur_ms, 100000)

  def test_verify_args_ui_and_runs_valid_dependency(self):
    parser = self.set_up_parser("torq.py -r 2 --no-ui")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)

  def test_verify_args_ui_and_runs_invalid_dependency(self):
    parser = self.set_up_parser("torq.py -r 2 --ui")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because --ui cannot be"
                                     " passed if --runs is set to a value"
                                     " greater than 1."))
    self.assertEqual(error.suggestion, ("Set torq -r 2 --no-ui to perform 2"
                                        " runs."))

  def test_verify_args_ui_bool_true_and_runs_default_dependencies(self):
    parser = self.set_up_parser("torq.py")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.ui, True)

    parser = self.set_up_parser("torq.py -r 1")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.ui, True)

  # UI is false by default when multiple runs are specified.
  def test_verify_args_ui_bool_false_and_runs_default_dependency(self):
    parser = self.set_up_parser("torq.py -r 2")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.ui, False)

  def test_verify_args_invalid_dur_ms_values(self):
    parser = self.set_up_parser("torq.py -d -200")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --dur-ms cannot be set to a value"
                                     " smaller than 3000."))
    self.assertEqual(error.suggestion, ("Set --dur-ms 3000 to capture a"
                                        " trace for 3 seconds."))

    parser = self.set_up_parser("torq.py -d 0")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --dur-ms cannot be set to a value"
                                     " smaller than 3000."))
    self.assertEqual(error.suggestion, ("Set --dur-ms 3000 to capture a"
                                        " trace for 3 seconds."))

    parser = self.set_up_parser("torq.py -d 20")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --dur-ms cannot be set to a value"
                                     " smaller than 3000."))
    self.assertEqual(error.suggestion, ("Set --dur-ms 3000 to capture a"
                                        " trace for 3 seconds."))

  def test_verify_args_valid_between_dur_ms_values(self):
    parser = self.set_up_parser("torq.py -r 2 --between-dur-ms 10000")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.between_dur_ms, 10000)

  def test_verify_args_invalid_between_dur_ms_values(self):
    parser = self.set_up_parser("torq.py -r 2 --between-dur-ms -200")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --between-dur-ms cannot be set to"
                                     " a smaller value than 3000."))
    self.assertEqual(error.suggestion, ("Set --between-dur-ms 3000 to wait"
                                        " 3 seconds between each run."))

    parser = self.set_up_parser("torq.py -r 2 --between-dur-ms 0")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message,  ("Command is invalid because"
                                      " --between-dur-ms cannot be set to a"
                                      " smaller value than 3000."))
    self.assertEqual(error.suggestion, ("Set --between-dur-ms 3000 to wait"
                                        " 3 seconds between each run."))

    parser = self.set_up_parser("torq.py -r 2 --between-dur-ms 20")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --between-dur-ms cannot be set to a"
                                     " smaller value than 3000."))
    self.assertEqual(error.suggestion, ("Set --between-dur-ms 3000 to wait"
                                        " 3 seconds between each run."))

  def test_verify_args_valid_runs_values(self):
    parser = self.set_up_parser("torq.py -r 4")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.runs, 4)

  def test_verify_args_invalid_runs_values(self):
    parser = self.set_up_parser("torq.py -r -2")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because --runs"
                                     " cannot be set to a value smaller"
                                     " than 1."))
    self.assertEqual(error.suggestion, None)

    parser = self.set_up_parser("torq.py -r 0")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because --runs"
                                     " cannot be set to a value smaller"
                                     " than 1."))
    self.assertEqual(error.suggestion, None)

  @mock.patch.object(os.path, "isfile", autospec=True)
  def test_verify_args_valid_perfetto_config_path(self, mock_is_file):
    mock_is_file.return_value = True
    parser = self.set_up_parser("torq.py --perfetto-config mock-file")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.perfetto_config, "mock-file")

    parser = self.set_up_parser("torq.py --perfetto-config default")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.perfetto_config, "default")

    parser = self.set_up_parser("torq.py --perfetto-config lightweight")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.perfetto_config, "lightweight")

    parser = self.set_up_parser("torq.py --perfetto-config memory")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.perfetto_config, "memory")

  @mock.patch.object(os.path, "isfile", autospec=True)
  def test_verify_args_invalid_perfetto_config_path(self, mock_is_file):
    mock_is_file.return_value = False
    parser = self.set_up_parser("torq.py --perfetto-config unexisting-file")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --perfetto-config is not a"
                                     " valid file path: unexisting-file"))
    self.assertEqual(error.suggestion, ("Predefined perfetto configs can be"
                                        " used:\n"
                                        "\t torq --perfetto-config default\n"
                                        "\t torq --perfetto-config"
                                        " lightweight\n"
                                        "\t torq --perfetto-config memory\n"
                                        "\t A filepath with a config can also"
                                        " be used:\n"
                                        "\t torq --perfetto-config"
                                        " <config-filepath>"))

    parser = self.set_up_parser("torq.py --perfetto-config mock-directory")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --perfetto-config is not a"
                                     " valid file path: mock-directory"))
    self.assertEqual(error.suggestion, ("Predefined perfetto configs can be"
                                        " used:\n"
                                        "\t torq --perfetto-config default\n"
                                        "\t torq --perfetto-config"
                                        " lightweight\n"
                                        "\t torq --perfetto-config memory\n"
                                        "\t A filepath with a config can also"
                                        " be used:\n"
                                        "\t torq --perfetto-config"
                                        " <config-filepath>"))

  def test_verify_args_from_user_and_event_valid_dependency(self):
    parser = self.set_up_parser(("torq.py -e user-switch --from-user 0"
                                 " --to-user %s") % str(TEST_USER_ID))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)

  def test_verify_args_from_user_and_event_invalid_dependency(self):
    parser = self.set_up_parser("torq.py --from-user %s" % str(TEST_USER_ID))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because --from-user"
                                     " is passed, but --event is not set to"
                                     " user-switch."))
    self.assertEqual(error.suggestion, ("Set --event user-switch --from-user %s"
                                        " to perform a user-switch from user"
                                        " %s." % (str(TEST_USER_ID),
                                                  str(TEST_USER_ID))))

  def test_verify_args_to_user_and_event_valid_dependency(self):
    parser = self.set_up_parser(
        "torq.py -e user-switch --to-user %s" % str(TEST_USER_ID))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)

  def test_verify_args_to_user_not_passed_and_event_invalid_dependency(self):
    parser = self.set_up_parser("torq.py -e user-switch")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because --to-user is"
                                     " not passed."))
    self.assertEqual(error.suggestion, ("Set --event user-switch --to-user"
                                        " <user-id> to perform a user-switch."))

  def test_verify_args_to_user_and_user_switch_not_set_invalid_dependency(self):
    parser = self.set_up_parser("torq.py --to-user %s" % str(TEST_USER_ID))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because --to-user"
                                     " is passed, but --event is not set to"
                                     " user-switch."))
    self.assertEqual(error.suggestion, ("Set --event user-switch --to-user %s"
                                        " to perform a user-switch to user"
                                        " %s." % (str(TEST_USER_ID),
                                                  str(TEST_USER_ID))))

  def test_verify_args_app_and_event_valid_dependency(self):
    parser = self.set_up_parser("torq.py -e app-startup -a %s" % TEST_PACKAGE)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)

  def test_verify_args_app_not_passed_and_event_invalid_dependency(self):
    parser = self.set_up_parser("torq.py -e app-startup")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message,
                     "Command is invalid because --app is not passed.")
    self.assertEqual(error.suggestion, ("Set --event app-startup --app "
                                        "<package> to perform an app-startup."))

  def test_verify_args_app_and_app_startup_not_set_invalid_dependency(self):
    parser = self.set_up_parser("torq.py -a %s" % TEST_PACKAGE)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because --app is"
                                     " passed and --event is not set to"
                                     " app-startup."))
    self.assertEqual(error.suggestion, ("To profile an app startup run:"
                                        " torq --event app-startup --app"
                                        " <package-name>"))

  @mock.patch.object(os.path, "exists", autospec=True)
  @mock.patch.object(os.path, "isdir", autospec=True)
  def test_verify_args_profiler_and_simpleperf_event_valid_dependencies(self,
      mock_isdir, mock_exists):
    mock_isdir.return_value = True
    mock_exists.return_value = True
    parser = self.set_up_parser("torq.py -p simpleperf --symbols %s"
                                % SYMBOLS_PATH)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(len(args.simpleperf_event), 1)
    self.assertEqual(args.simpleperf_event[0], "cpu-cycles")

    parser = self.set_up_parser("torq.py -p simpleperf -s cpu-cycles "
                                "--symbols %s" % SYMBOLS_PATH)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(len(args.simpleperf_event), 1)
    self.assertEqual(args.simpleperf_event[0], "cpu-cycles")

  def test_verify_args_profiler_and_simpleperf_event_invalid_dependencies(
      self):
    parser = self.set_up_parser("torq.py -s cpu-cycles")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --simpleperf-event cannot be passed if"
                                     " --profiler is not set to simpleperf."))
    self.assertEqual(error.suggestion, ("To capture the simpleperf event run:"
                                        " torq --profiler simpleperf"
                                        " --simpleperf-event cpu-cycles"))

  def test_profiler_and_perfetto_config_valid_dependency(self):
    parser = self.set_up_parser(("torq.py -p perfetto --perfetto-config"
                                 " lightweight"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)

  def test_verify_args_profiler_and_perfetto_config_invalid_dependency(self):
    parser = self.set_up_parser("torq.py -p simpleperf --perfetto-config"
                                " lightweight")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --perfetto-config cannot be passed if"
                                     " --profiler is not set to perfetto."))
    self.assertEqual(error.suggestion, ("Set --profiler perfetto to choose a"
                                        " perfetto-config to use."))

  def test_verify_args_runs_and_between_dur_ms_valid_dependency(self):
    parser = self.set_up_parser("torq.py -r 2 --between-dur-ms 5000")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)

  def test_verify_args_runs_and_between_dur_ms_invalid_dependency(self):
    parser = self.set_up_parser("torq.py --between-dur-ms 5000")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --between-dur-ms cannot be passed"
                                     " if --runs is not a value greater"
                                     " than 1."))
    self.assertEqual(error.suggestion, "Set --runs 2 to run 2 tests.")

    parser = self.set_up_parser("torq.py -r 1 --between-dur-ms 5000")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --between-dur-ms cannot be passed"
                                     " if --runs is not a value greater"
                                     " than 1."))
    self.assertEqual(error.suggestion, "Set --runs 2 to run 2 tests.")

  def test_verify_args_profiler_and_ftrace_events_valid_dependencies(self):
    parser = self.set_up_parser(("torq.py --excluded-ftrace-events"
                                 " syscall-enter"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.excluded_ftrace_events, ["syscall-enter"])

    parser = self.set_up_parser(("torq.py -p perfetto --excluded-ftrace-events"
                                 " syscall-enter"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(args.excluded_ftrace_events, ["syscall-enter"])
    self.assertEqual(error, None)

    parser = self.set_up_parser(("torq.py -p perfetto --included-ftrace-events"
                                 " syscall-enter"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(args.included_ftrace_events, ["syscall-enter"])
    self.assertEqual(error, None)

  def test_verify_args_profiler_and_ftrace_events_invalid_dependencies(self):
    parser = self.set_up_parser(("torq.py -p simpleperf"
                                 " --excluded-ftrace-events syscall-enter"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --excluded-ftrace-events cannot be"
                                     " passed if --profiler is not set to"
                                     " perfetto."))
    self.assertEqual(error.suggestion, ("Set --profiler perfetto to exclude an"
                                        " ftrace event from perfetto config."))

    parser = self.set_up_parser(("torq.py -p simpleperf"
                                 " --included-ftrace-events syscall-enter"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because"
                                     " --included-ftrace-events cannot be"
                                     " passed if --profiler is not set to"
                                     " perfetto."))
    self.assertEqual(error.suggestion, ("Set --profiler perfetto to include"
                                        " an ftrace event in perfetto config."))

  def test_verify_args_multiple_valid_excluded_ftrace_events(self):
    parser = self.set_up_parser(("torq.py --excluded-ftrace-events"
                                 " power/cpu_idle --excluded-ftrace-events"
                                 " ion/ion_stat"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.excluded_ftrace_events, ["power/cpu_idle",
                                                 "ion/ion_stat"])

  def test_verify_args_multiple_invalid_excluded_ftrace_events(self):
    parser = self.set_up_parser(("torq.py --excluded-ftrace-events"
                                 " power/cpu_idle --excluded-ftrace-events"
                                 " power/cpu_idle"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because duplicate"
                                     " ftrace events cannot be"
                                     " included in --excluded-ftrace-events."))
    self.assertEqual(error.suggestion, ("--excluded-ftrace-events should only"
                                        " include one instance of an ftrace"
                                        " event."))

  def test_verify_args_multiple_valid_included_ftrace_events(self):
    parser = self.set_up_parser(("torq.py --included-ftrace-events"
                                 " power/cpu_idle --included-ftrace-events"
                                 " ion/ion_stat"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.included_ftrace_events, ["power/cpu_idle",
                                                   "ion/ion_stat"])

  def test_verify_args_multiple_invalid_included_ftrace_events(self):
    parser = self.set_up_parser(("torq.py --included-ftrace-events"
                                 " power/cpu_idle --included-ftrace-events"
                                 " power/cpu_idle"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because duplicate"
                                     " ftrace events cannot be"
                                     " included in --included-ftrace-events."))
    self.assertEqual(error.suggestion, ("--included-ftrace-events should only"
                                        " include one instance of an ftrace"
                                        " event."))

  def test_verify_args_invalid_overlap_ftrace_events(self):
    parser = self.set_up_parser(("torq.py --excluded-ftrace-events"
                                 " ion/ion_stat --excluded-ftrace-events"
                                 " power/cpu_idle --excluded-ftrace-events"
                                 " power/gpu_frequency --included-ftrace-events"
                                 " ion/ion_stat --included-ftrace-events"
                                 " power/cpu_idle --included-ftrace-events"
                                 " ftrace/print"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because ftrace"
                                     " event(s): ion/ion_stat, power/cpu_idle"
                                     " cannot be both included and excluded."))
    self.assertEqual(error.suggestion, ("Only set --excluded-ftrace-events"
                                        " ion/ion_stat if you want to"
                                        " exclude ion/ion_stat from the"
                                        " config or --included-ftrace-events"
                                        " ion/ion_stat if you want to"
                                        " include ion/ion_stat in the"
                                        " config.\n\t"
                                        " Only set --excluded-ftrace-events"
                                        " power/cpu_idle if you want to"
                                        " exclude power/cpu_idle from the"
                                        " config or --included-ftrace-events"
                                        " power/cpu_idle if you want to"
                                        " include power/cpu_idle in the"
                                        " config."))

  @mock.patch.object(os.path, "exists", autospec=True)
  @mock.patch.object(os.path, "isdir", autospec=True)
  def test_verify_args_multiple_valid_simpleperf_events(self, mock_isdir,
      mock_exists):
    mock_isdir.return_value = True
    mock_exists.return_value = True
    parser = self.set_up_parser(("torq.py -p simpleperf -s cpu-cycles"
                                 " -s instructions --symbols %s"
                                 % SYMBOLS_PATH))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.simpleperf_event, ["cpu-cycles", "instructions"])

  def test_verify_args_multiple_invalid_simpleperf_events(self):
    parser = self.set_up_parser(("torq.py -p simpleperf -s cpu-cycles"
                                 " -s cpu-cycles"))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because redundant"
                                     " calls to --simpleperf-event cannot"
                                     " be made."))
    self.assertEqual(error.suggestion, ("Only set --simpleperf-event cpu-cycles"
                                        " once if you want to collect"
                                        " cpu-cycles."))

  def test_create_parser_invalid_perfetto_config_command(self):
    parser = self.set_up_parser("torq.py --perfetto-config")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  def test_verify_args_invalid_mixing_of_profiler_and_config_subcommand(self):
    parser = self.set_up_parser("torq.py -d 20000 config pull lightweight")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because profiler"
                                     " command is followed by a config"
                                     " command."))
    self.assertEqual(error.suggestion, ("Remove the 'config' subcommand to"
                                        " profile the device instead."))

  def test_create_parser_invalid_mixing_of_profiler_and_config_subcommand(self):
    parser = self.set_up_parser("torq.py config pull lightweight -d 20000")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  def test_get_command_type_profiler(self):
    parser = self.set_up_parser("torq.py -d 20000")

    args = parser.parse_args()
    args, error = verify_args(args)
    command = get_command_type(args)

    self.assertEqual(error, None)
    self.assertEqual(command.get_type(), "profiler")

  def test_create_parser_valid_config_show_values(self):
    parser = self.set_up_parser("torq.py config show default")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.config_name, "default")

    parser = self.set_up_parser("torq.py config show lightweight")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.config_name, "lightweight")

    parser = self.set_up_parser("torq.py config show memory")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.config_name, "memory")

  def test_create_parser_invalid_config_show_values(self):
    parser = self.set_up_parser("torq.py config show fake-config")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  def test_create_parser_valid_config_pull_values(self):
    parser = self.set_up_parser("torq.py config pull default")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.config_name, "default")

    parser = self.set_up_parser("torq.py config pull lightweight")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.config_name, "lightweight")

    parser = self.set_up_parser("torq.py config pull memory")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.config_name, "memory")

  def test_create_parser_invalid_config_pull_values(self):
    parser = self.set_up_parser("torq.py config pull fake-config")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  def test_verify_args_invalid_config_subcommands(self):
    parser = self.set_up_parser("torq.py config")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, ("Command is invalid because torq config"
                                     " cannot be called without a"
                                     " subcommand."))
    self.assertEqual(error.suggestion, ("Use one of the following"
                                        " subcommands:\n"
                                        "\t torq config list\n"
                                        "\t torq config show\n"
                                        "\t torq config pull\n"))

  def test_create_parser_invalid_config_subcommands(self):
    parser = self.set_up_parser("torq.py config get")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  def test_verify_args_default_config_pull_filepath(self):
    parser = self.set_up_parser("torq.py config pull default")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.file_path, "./default.pbtxt")

    parser = self.set_up_parser("torq.py config pull lightweight")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.file_path, "./lightweight.pbtxt")

    parser = self.set_up_parser("torq.py config pull memory")

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.file_path, "./memory.pbtxt")

  @mock.patch.object(os.path, "isfile", autospec=True)
  def test_verify_args_default_config_pull_invalid_filepath(self, mock_is_file):
    mock_invalid_file_path = "mock-invalid-file-path"
    mock_is_file.return_value = False
    parser = self.set_up_parser(("torq.py config pull default %s"
                                 % mock_invalid_file_path))

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, (
        "Command is invalid because %s is not a valid filepath."
        % mock_invalid_file_path))
    self.assertEqual(error.suggestion, (
        "A default filepath can be used if you do not specify a file-path:\n\t"
        " torq pull default to copy to ./default.pbtxt\n\t"
        " torq pull lightweight to copy to ./lightweight.pbtxt\n\t "
        "torq pull memory to copy to ./memory.pbtxt"))

  def test_get_command_type_config_list(self):
    parser = self.set_up_parser("torq.py config list")

    args = parser.parse_args()
    args, error = verify_args(args)
    command = get_command_type(args)

    self.assertEqual(error, None)
    self.assertEqual(command.get_type(), "config list")

  def test_get_command_type_config_show(self):
    parser = self.set_up_parser("torq.py config show default")

    args = parser.parse_args()
    args, error = verify_args(args)
    command = get_command_type(args)

    self.assertEqual(error, None)
    self.assertEqual(command.get_type(), "config show")

  def test_get_command_type_config_pull(self):
    parser = self.set_up_parser("torq.py config pull default")

    args = parser.parse_args()
    args, error = verify_args(args)
    command = get_command_type(args)

    self.assertEqual(error, None)
    self.assertEqual(command.get_type(), "config pull")

  @mock.patch.object(os.path, "exists", autospec=True)
  def test_create_parser_valid_open_subcommand(self, mock_exists):
    mock_exists.return_value = True
    parser = self.set_up_parser("torq.py open %s" % TEST_FILE)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error, None)
    self.assertEqual(args.file_path, TEST_FILE)

  def test_create_parser_open_subcommand_no_file(self):
    parser = self.set_up_parser("torq.py open")

    with self.assertRaises(SystemExit):
      parser.parse_args()

  @mock.patch.object(os.path, "exists", autospec=True)
  def test_create_parser_open_subcommand_invalid_file(self, mock_exists):
    mock_exists.return_value = False
    parser = self.set_up_parser("torq.py open %s" % TEST_FILE)

    args = parser.parse_args()
    args, error = verify_args(args)

    self.assertEqual(error.message, "Command is invalid because %s is an "
                                    "invalid file path." % TEST_FILE)
    self.assertEqual(error.suggestion, "Make sure your file exists.")


if __name__ == '__main__':
  unittest.main()
