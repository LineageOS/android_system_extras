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

import argparse
import os
from command import ProfilerCommand, ConfigCommand, OpenCommand
from device import AdbDevice
from validation_error import ValidationError
from config_builder import PREDEFINED_PERFETTO_CONFIGS
from utils import path_exists
from validate_simpleperf import verify_simpleperf_args

DEFAULT_DUR_MS = 10000
MIN_DURATION_MS = 3000
DEFAULT_OUT_DIR = "."


def create_parser():
  parser = argparse.ArgumentParser(prog='torq command',
                                   description=('Torq CLI tool for performance'
                                                ' tests.'))
  parser.add_argument('-e', '--event',
                      choices=['boot', 'user-switch', 'app-startup', 'custom'],
                      default='custom', help='The event to trace/profile.')
  parser.add_argument('-p', '--profiler', choices=['perfetto', 'simpleperf'],
                      default='perfetto', help='The performance data source.')
  parser.add_argument('-o', '--out-dir', default=DEFAULT_OUT_DIR,
                      help='The path to the output directory.')
  parser.add_argument('-d', '--dur-ms', type=int, default=DEFAULT_DUR_MS,
                      help=('The duration (ms) of the event. Determines when'
                            ' to stop collecting performance data.'))
  parser.add_argument('-a', '--app',
                      help='The package name of the app we want to start.')
  parser.add_argument('-r', '--runs', type=int, default=1,
                      help=('The number of times to run the event and'
                            ' capture the perf data.'))
  parser.add_argument('-s', '--simpleperf-event', action='append',
                      help=('Simpleperf supported events to be collected.'
                            ' e.g. cpu-cycles, instructions'))
  parser.add_argument('--perfetto-config', default='default',
                      help=('Predefined perfetto configs can be used:'
                            ' %s. A filepath with a custom config could'
                            ' also be provided.'
                            % (", ".join(PREDEFINED_PERFETTO_CONFIGS.keys()))))
  parser.add_argument('--between-dur-ms', type=int, default=DEFAULT_DUR_MS,
                      help='Time (ms) to wait before executing the next event.')
  parser.add_argument('--ui', action=argparse.BooleanOptionalAction,
                      help=('Specifies opening of UI visualization tool'
                            ' after profiling is complete.'))
  parser.add_argument('--excluded-ftrace-events', action='append',
                      help=('Excludes specified ftrace event from the perfetto'
                            ' config events.'))
  parser.add_argument('--included-ftrace-events', action='append',
                      help=('Includes specified ftrace event in the perfetto'
                            ' config events.'))
  parser.add_argument('--from-user', type=int,
                      help='The user id from which to start the user switch')
  parser.add_argument('--to-user', type=int,
                      help='The user id of user that system is switching to.')
  parser.add_argument('--serial',
                      help=(('Specifies serial of the device that will be'
                             ' used.')))
  parser.add_argument('--symbols',
                      help='Specifies path to symbols library.')
  subparsers = parser.add_subparsers(dest='subcommands', help='Subcommands')
  config_parser = subparsers.add_parser('config',
                                        help=('The config subcommand used'
                                              ' to list and show the'
                                              ' predefined perfetto configs.'))
  config_subparsers = config_parser.add_subparsers(dest='config_subcommand',
                                                   help=('torq config'
                                                         ' subcommands'))
  config_subparsers.add_parser('list',
                               help=('Command to list the predefined'
                                     ' perfetto configs'))
  config_show_parser = config_subparsers.add_parser('show',
                                                    help=('Command to print'
                                                          ' the '
                                                          ' perfetto config'
                                                          ' in the terminal.'))
  config_show_parser.add_argument('config_name',
                                  choices=['lightweight', 'default', 'memory'],
                                  help=('Name of the predefined perfetto'
                                        ' config to print.'))
  config_pull_parser = config_subparsers.add_parser('pull',
                                                    help=('Command to copy'
                                                          ' a predefined config'
                                                          ' to the specified'
                                                          ' file path.'))
  config_pull_parser.add_argument('config_name',
                                  choices=['lightweight', 'default', 'memory'],
                                  help='Name of the predefined config to copy')
  config_pull_parser.add_argument('file_path', nargs='?',
                                  help=('File path to copy the predefined'
                                        ' config to'))
  open_parser = subparsers.add_parser('open',
                                      help=('The open subcommand is used '
                                            'to open trace files in the '
                                            'perfetto ui.'))
  open_parser.add_argument('file_path', help='Path to trace file.')
  return parser


def user_changed_default_arguments(args):
  return any([args.event != "custom",
              args.profiler != "perfetto",
              args.out_dir != DEFAULT_OUT_DIR,
              args.dur_ms != DEFAULT_DUR_MS,
              args.app is not None,
              args.runs != 1,
              args.simpleperf_event is not None,
              args.perfetto_config != "default",
              args.between_dur_ms != DEFAULT_DUR_MS,
              args.ui is not None,
              args.excluded_ftrace_events is not None,
              args.included_ftrace_events is not None,
              args.from_user is not None,
              args.to_user is not None,
              args.serial is not None])


def verify_args(args):
  if (args.subcommands is not None and
      user_changed_default_arguments(args)):
    return None, ValidationError(
        ("Command is invalid because profiler command is followed by a config"
         " command."),
        "Remove the 'config' subcommand to profile the device instead.")

  if args.out_dir != DEFAULT_OUT_DIR and not os.path.isdir(args.out_dir):
    return None, ValidationError(
        ("Command is invalid because --out-dir is not a valid directory"
         " path: %s." % args.out_dir), None)

  if args.dur_ms < MIN_DURATION_MS:
    return None, ValidationError(
        ("Command is invalid because --dur-ms cannot be set to a value smaller"
         " than %d." % MIN_DURATION_MS),
        ("Set --dur-ms %d to capture a trace for %d seconds."
         % (MIN_DURATION_MS, (MIN_DURATION_MS / 1000))))

  if args.from_user is not None and args.event != "user-switch":
    return None, ValidationError(
        ("Command is invalid because --from-user is passed, but --event is not"
         " set to user-switch."),
        ("Set --event user-switch --from-user %s to perform a user-switch from"
         " user %s." % (args.from_user, args.from_user)))

  if args.to_user is not None and args.event != "user-switch":
    return None, ValidationError((
        "Command is invalid because --to-user is passed, but --event is not set"
        " to user-switch."),
        ("Set --event user-switch --to-user %s to perform a user-switch to user"
         " %s." % (args.to_user, args.to_user)))

  if args.event == "user-switch" and args.to_user is None:
    return None, ValidationError(
        "Command is invalid because --to-user is not passed.",
        ("Set --event %s --to-user <user-id> to perform a %s."
         % (args.event, args.event)))

  # TODO(b/374313202): Support for simpleperf boot event will
  #                    be added in the future
  if args.event == "boot" and args.profiler == "simpleperf":
    return None, ValidationError(
        "Boot event is not yet implemented for simpleperf.",
        "Please try another event.")

  if args.app is not None and args.event != "app-startup":
    return None, ValidationError(
        ("Command is invalid because --app is passed and --event is not set"
         " to app-startup."),
        ("To profile an app startup run:"
         " torq --event app-startup --app <package-name>"))

  if args.event == "app-startup" and args.app is None:
    return None, ValidationError(
        "Command is invalid because --app is not passed.",
        ("Set --event %s --app <package> to perform an %s."
         % (args.event, args.event)))

  if args.runs < 1:
    return None, ValidationError(
        ("Command is invalid because --runs cannot be set to a value smaller"
         " than 1."), None)

  if args.runs > 1 and args.ui:
    return None, ValidationError(("Command is invalid because --ui cannot be"
                                  " passed if --runs is set to a value greater"
                                  " than 1."),
                                 ("Set torq -r %d --no-ui to perform %d runs."
                                  % (args.runs, args.runs)))

  if args.simpleperf_event is not None and args.profiler != "simpleperf":
    return None, ValidationError(
        ("Command is invalid because --simpleperf-event cannot be passed"
         " if --profiler is not set to simpleperf."),
        ("To capture the simpleperf event run:"
         " torq --profiler simpleperf --simpleperf-event %s"
         % " --simpleperf-event ".join(args.simpleperf_event)))

  if (args.simpleperf_event is not None and
      len(args.simpleperf_event) != len(set(args.simpleperf_event))):
    return None, ValidationError(
        ("Command is invalid because redundant calls to --simpleperf-event"
         " cannot be made."),
        ("Only set --simpleperf-event cpu-cycles once if you want"
         " to collect cpu-cycles."))

  if args.perfetto_config != "default":
    if args.profiler != "perfetto":
      return None, ValidationError(
          ("Command is invalid because --perfetto-config cannot be passed"
           " if --profiler is not set to perfetto."),
          ("Set --profiler perfetto to choose a perfetto-config"
           " to use."))

  if (args.perfetto_config not in PREDEFINED_PERFETTO_CONFIGS and
      not os.path.isfile(args.perfetto_config)):
    return None, ValidationError(
        ("Command is invalid because --perfetto-config is not a valid"
         " file path: %s" % args.perfetto_config),
        ("Predefined perfetto configs can be used:\n"
         "\t torq --perfetto-config %s\n"
         "\t A filepath with a config can also be used:\n"
         "\t torq --perfetto-config <config-filepath>"
         % ("\n\t torq --perfetto-config"
            " ".join(PREDEFINED_PERFETTO_CONFIGS.keys()))))

  if args.between_dur_ms < MIN_DURATION_MS:
    return None, ValidationError(
        ("Command is invalid because --between-dur-ms cannot be set to a"
         " smaller value than %d." % MIN_DURATION_MS),
        ("Set --between-dur-ms %d to wait %d seconds between"
         " each run." % (MIN_DURATION_MS, (MIN_DURATION_MS / 1000))))

  if args.between_dur_ms != DEFAULT_DUR_MS and args.runs == 1:
    return None, ValidationError(
        ("Command is invalid because --between-dur-ms cannot be passed"
         " if --runs is not a value greater than 1."),
        "Set --runs 2 to run 2 tests.")

  if args.excluded_ftrace_events is not None and args.profiler != "perfetto":
    return None, ValidationError(
        ("Command is invalid because --excluded-ftrace-events cannot be passed"
         " if --profiler is not set to perfetto."),
        ("Set --profiler perfetto to exclude an ftrace event"
         " from perfetto config."))

  if (args.excluded_ftrace_events is not None and
      len(args.excluded_ftrace_events) != len(set(
          args.excluded_ftrace_events))):
    return None, ValidationError(
        ("Command is invalid because duplicate ftrace events cannot be"
         " included in --excluded-ftrace-events."),
        ("--excluded-ftrace-events should only include one instance of an"
         " ftrace event."))

  if args.included_ftrace_events is not None and args.profiler != "perfetto":
    return None, ValidationError(
        ("Command is invalid because --included-ftrace-events cannot be passed"
         " if --profiler is not set to perfetto."),
        ("Set --profiler perfetto to include an ftrace event"
         " in perfetto config."))

  if (args.included_ftrace_events is not None and
      len(args.included_ftrace_events) != len(set(
          args.included_ftrace_events))):
    return None, ValidationError(
        ("Command is invalid because duplicate ftrace events cannot be"
         " included in --included-ftrace-events."),
        ("--included-ftrace-events should only include one instance of an"
         " ftrace event."))

  if (args.included_ftrace_events is not None and
      args.excluded_ftrace_events is not None):
    ftrace_event_intersection = sorted((set(args.excluded_ftrace_events) &
                                        set(args.included_ftrace_events)))
    if len(ftrace_event_intersection):
      return None, ValidationError(
          ("Command is invalid because ftrace event(s): %s cannot be both"
           " included and excluded." % ", ".join(ftrace_event_intersection)),
          ("\n\t ".join("Only set --excluded-ftrace-events %s if you want to"
                        " exclude %s from the config or"
                        " --included-ftrace-events %s if you want to include %s"
                        " in the config."
                        % (event, event, event, event)
                        for event in ftrace_event_intersection)))

  if args.subcommands == "config" and args.config_subcommand is None:
    return None, ValidationError(
        ("Command is invalid because torq config cannot be called"
         " without a subcommand."),
        ("Use one of the following subcommands:\n"
         "\t torq config list\n"
         "\t torq config show\n"
         "\t torq config pull\n"))

  if args.profiler == "simpleperf" and args.simpleperf_event is None:
    args.simpleperf_event = ['cpu-cycles']

  if args.ui is None:
    args.ui = args.runs == 1

  if args.subcommands == "config" and args.config_subcommand == "pull":
    if args.file_path is None:
      args.file_path = "./" + args.config_name + ".pbtxt"
    elif not os.path.isfile(args.file_path):
      return None, ValidationError(
          ("Command is invalid because %s is not a valid filepath."
           % args.file_path),
          ("A default filepath can be used if you do not specify a file-path:\n"
           "\t torq pull default to copy to ./default.pbtxt\n"
           "\t torq pull lightweight to copy to ./lightweight.pbtxt\n"
           "\t torq pull memory to copy to ./memory.pbtxt"))

  if args.subcommands == "open" and not path_exists(args.file_path):
    return None, ValidationError(
        "Command is invalid because %s is an invalid file path."
        % args.file_path, "Make sure your file exists.")

  if args.profiler == "simpleperf":
    args, error = verify_simpleperf_args(args)
    if error is not None:
      return None, error
  else:
    args.scripts_path = None

  return args, None


def create_profiler_command(args):
  return ProfilerCommand("profiler", args.event, args.profiler, args.out_dir,
                         args.dur_ms,
                         args.app, args.runs, args.simpleperf_event,
                         args.perfetto_config, args.between_dur_ms,
                         args.ui, args.excluded_ftrace_events,
                         args.included_ftrace_events, args.from_user,
                         args.to_user)


def create_config_command(args):
  type = "config " + args.config_subcommand
  config_name = None
  file_path = None
  dur_ms = None
  excluded_ftrace_events = None
  included_ftrace_events = None
  if args.config_subcommand == "pull" or args.config_subcommand == "show":
    config_name = args.config_name
    dur_ms = args.dur_ms
    excluded_ftrace_events = args.excluded_ftrace_events
    included_ftrace_events = args.included_ftrace_events
    if args.config_subcommand == "pull":
      file_path = args.file_path

  command = ConfigCommand(type, config_name, file_path, dur_ms,
      excluded_ftrace_events, included_ftrace_events)
  return command


def get_command_type(args):
  command = None
  if args.subcommands is None:
    command = create_profiler_command(args)
  if args.subcommands == "config":
    command = create_config_command(args)
  if args.subcommands == "open":
    command = OpenCommand(args.file_path)
  return command


def print_error(error):
  print(error.message)
  if error.suggestion is not None:
    print("Suggestion:\n\t", error.suggestion)


def main():
  parser = create_parser()
  args = parser.parse_args()
  args, error = verify_args(args)
  if error is not None:
    print_error(error)
    return
  command = get_command_type(args)
  device = AdbDevice(args.serial)
  error = command.execute(device)
  if error is not None:
    print_error(error)
    return


if __name__ == '__main__':
  main()
