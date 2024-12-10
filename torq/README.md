# **torq: AAOS Performance CLI**

**torq** is a command-line tool designed to streamline and standardize OS
performance profiling across Android Automotive devices. By providing a flexible
and easy-to-use interface, **torq** enables engineers and OEMs to capture and
analyze performance data for critical system events such as boot, user switch,
app startup, or any of their own interactions with their device. This tool helps
ensure consistent results amongst different users and helps reduce the time and
effort required for performance analysis, ensuring that developers can focus on
optimizing their systems and bug detection rather than navigating fragmented
tooling solutions.


## Getting Started

- **torq** is an open source Android tool. Run the following commands to get
started:

```
cd $ANDROID_ROOT
source build/envsetup.sh
lunch <target-name> (e.g., lunch sdk_gcar_x86_64-next-userdebug)
cd $ANDROID_ROOT/system/extras/torq
m torq
```

- Connect to an Android Automotive device or start an emulator.
- Ensure the connected device appears in `adb devices`.
- You can now run `torq` anywhere, followed by any necessary arguments
(e.g., `torq -d 7000`).


## Example Usages

### ./torq -d 7000
- Run a custom event for 7 seconds.
### ./torq -e user-switch --from-user 10 --to-user 11
- Run a user-switch event, switching from user 10 to user 11.
### ./torq -e boot --perfetto-config ./config
- Run a boot event, using the user's local Perfetto config specified in the
./config file path.
### ./torq -e boot -r 5 --between-dur-ms 3000
- Run a boot event 5 times, waiting 3 seconds between each boot run.
### ./torq -e app-startup -a android.google.kitchensink
- Run an app-startup event, starting the android.google.kitchensink package.
### ./torq -e user-switch --to-user 9 --serial emulator-5554
- Run a user-switch event, switching to user 9 on the connected device with
serial, emulator-5554.
### ./torq -p simpleperf -d 10000
- Run a custom event using the Simpleperf profiler for 10 seconds.
### ./torq -p simpleperf -s cpu-cycles -s instructions
- Run a custom event using the Simpleperf profiler, in which the stats,
cpu-cycles and instructions, are collected.
### ./torq -d 10000 --perfetto-config lightweight
- Run a custom event for 10 seconds using the "lightweight" predefined Perfetto
config.
### ./torq config show memory
- Print the contents of the memory predefined Perfetto config to the terminal.
### ./torq -d 10000 --exclude-ftrace-event power/cpu_idle
- Run a custom event for 10 seconds, using the "default" predefined Perfetto
config, in which the ftrace event, power/cpu_idle, is not collected.


## CLI Arguments

| Argument                 | Description                                                                                                                                                                                                                                                                        | Currently Supported Arguments                                                                | Default                    |
|--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|----------------------------|
| `-e, --event`            | The event to trace/profile.                                                                                                                                                                                                                                                        | `boot`, `user-switch`,`app-startup`, `custom`                                                | `custom`                   |
| `-p, --profiler`         | The performance data profiler.                                                                                                                                                                                                                                                     | `perfetto`, (`simpleperf` coming soon)                                                       | `perfetto`                 |
| `-o, --out-dir`          | The path to the output directory.                                                                                                                                                                                                                                                  | Any local path                                                                               | Current directory: `.`     |
| `-d, --dur-ms`           | The duration (ms) of the event. Determines when to stop collecting performance data.                                                                                                                                                                                               | Float >= `3000`                                                                              | `10000`                    |
| `-a, --app`              | The package name of the app to start.<br/>(Requires use of `-e app-startup`)                                                                                                                                                                                                       | Any package on connected device                                                              |                            |
| `-r, --runs`             | The amount of times to run the event and capture the performance data.                                                                                                                                                                                                             | Integer >= `1`                                                                               | `1`                        |
| `--serial`               | The serial of the connected device that you want to use.<br/>(If not provided, the ANDROID_SERIAL environment variable is used. If ANDROID_SERIAL is also not set and there is only one device connected, the device is chosen.)                                                   |                                                                                              |                            |
| `--perfetto-config`      | The local file path of the user's Perfetto config or used to specify a predefined Perfetto configs.                                                                                                                                                                                | `default`, any local perfetto config,<br/>(`lightweight`, `memory` coming soon)              | `default`                  |
| `--between-dur-ms`       | The amount of time (ms) to wait between different runs.<br/>(Requires that `--r` is set to a value greater than 1)                                                                                                                                                                 | Float >= `3000`                                                                              | `10000`                    |
| `--ui`                   | Specifies opening of UI visualization tool after profiling is complete.<br/>(Requires that `-r` is not set to a value greater than 1)                                                                                                                                              | `--ui`, `--no-ui`,                                                                           | `ui` if `runs` is `1`      |
| `--exclude-ftrace-event` | Excludes the ftrace event from the Perfetto config. Can be defined multiple times in a command.<br/>(Requires use of `-p perfetto`)<br/>(Currently only works with `--perfetto-config default`,<br/>support for local Perfetto configs, `lightweight`, and `memory` coming soon)   | Any supported perfetto ftrace event<br/>(e.g., `power/cpu_idle`, `sched/sched_process_exit`) | Empty list                 |
| `--include-ftrace-event` | Includes the ftrace event in the Perfetto config. Can be defined multiple times in a command.<br/>(Requires use of `-p perfetto`)<br/>(Currently only works with `--perfetto-config default`,<br/>support for any local Perfetto configs, `lightweight`, and `memory` coming soon) | Any supported perfetto ftrace event<br/>(e.g., `power/cpu_idle`, `sched/sched_process_exit`) | Empty list                 |
| `--from-user`            | The user ID from which to start the user switch. (Requires use of `-e user-switch`)                                                                                                                                                                                                | ID of any user on connected device                                                           | Current user on the device |
| `--to-user`              | The user ID of user that device is switching to. (Requires use of `-e user-switch`).                                                                                                                                                                                               | ID of any user on connected device                                                           |                            |

## Functionality Coming Soon

| Argument                                | Description                                                                                                                                                   | Accepted Values                                                                         | Default                               |
|-----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|---------------------------------------|
| `-s, --simpleperf-event`                | Simpleperf supported events that should be collected. Can be defined multiple times in a command.                                                             | Any supported simpleperf event<br/>(e.g., `cpu-cycles`, `instructions`)                 | Empty list                            |
| `config list`                           | Subcommand to list the predefined Perfetto configs (`default`, `lightweight`, `memory`).                                                                      |                                                                                         |                                       |
| `config show <config-name>`             | Subcommand to print the contents of a predefined Perfetto config to the terminal.                                                                             | `default`, `lightweight`, `memory`                                                      |                                       |
| `config pull <config-name> [file-path]` | Subcommand to download a predefined Perfetto config to a specified local file path.                                                                           | <config-name>: `default`, `lightweight`, `memory`<br/> [file-path]: Any local file path | [file-path]: `./<config-name>.config` |
