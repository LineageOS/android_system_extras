# Collect ETM data for AutoFDO

[TOC]

## Introduction

The ARM Embedded Trace Macrocell (ETM) is an instruction tracing unit available on ARM SoCs. ETM
traces the instruction stream executed on each core and sends the stream to system memory via other
Coresight components. ETM data contains branch records, similar to Last Branch Records (LBRs) on
x86 architectures.

Simpleperf supports collecting ETM data and converting it to input files for AutoFDO, which can
then be used for Profile-Guided Optimization (PGO) during compilation.

On ARMv8, the ETM and other Coresight components are considered part of the external debug
interface. Therefore, they are typically only used internally and are disabled on production
devices. ARMv9 introduces the Embedded Trace Extension (ETE) and Trace Buffer Extension (TRBE)
to enhance self-hosted ETM data collection. This new hardware is not bound to the external debug
interface and can be used more widely to collect AutoFDO profiles.

For Pixel devices, ETM data collection is supported on EVT and DVT devices starting with Pixel 4.
For other devices, you can try the commands in this document to see if ETM data recording is
possible. To enable ETM data collection on a device, refer to the documentation in
[Enable ETM data collection](#enable-etm-data-collection).

## Examples

Below are examples collecting ETM data for AutoFDO. It has two steps: first recording ETM data,
second converting ETM data to AutoFDO input files.

Record ETM data:

```sh
# preparation: we need to be root to record ETM data
$ adb root
$ adb shell
redfin:/ \# cd data/local/tmp
redfin:/data/local/tmp \#

# Do a system wide collection, it writes output to perf.data.
# If only want ETM data for kernel, use `-e cs-etm:k`.
# If only want ETM data for userspace, use `-e cs-etm:u`.
redfin:/data/local/tmp \# simpleperf record -e cs-etm --duration 3 -a

# To reduce file size and time converting to AutoFDO input files, we recommend converting ETM data
# into an intermediate branch-list format.
redfin:/data/local/tmp \# simpleperf inject --output branch-list -o branch_list.data
```

Converting ETM data to AutoFDO input files needs to read binaries.
So for userspace libraries, they can be converted on device. For kernel, it needs
to be converted on host, with vmlinux and kernel modules available.

Convert ETM data for userspace libraries:

```sh
# Injecting ETM data on device. It writes output to perf_inject.data.
# perf_inject.data is a text file, containing branch counts for each library.
redfin:/data/local/tmp \# simpleperf inject -i branch_list.data
```

Convert ETM data for kernel:

```sh
# pull ETM data to host.
host $ adb pull /data/local/tmp/branch_list.data
# download vmlinux and kernel modules to <binary_dir>
# host simpleperf is in <aosp-top>/system/extras/simpleperf/scripts/bin/linux/x86_64/simpleperf,
# or you can build simpleperf by `mmma system/extras/simpleperf`.
host $ simpleperf inject --symdir <binary_dir> -i branch_list.data
```

The generated perf_inject.data may contain branch info for multiple binaries. But AutoFDO only
accepts one at a time. So we need to split perf_inject.data.
The format of perf_inject.data is below:

```perf_inject.data format

executed range with count info for binary1
branch with count info for binary1
// name for binary1

executed range with count info for binary2
branch with count info for binary2
// name for binary2

...
```

We need to split perf_inject.data, and make sure one file only contains info for one binary.

Then we can use [AutoFDO](https://github.com/google/autofdo) to create profile. Follow README.md
in AutoFDO to build create_llvm_prof, then use `create_llvm_prof` to create profiles for clang.

```sh
# perf_inject_binary1.data is split from perf_inject.data, and only contains branch info for binary1.
host $ create_llvm_prof -profile perf_inject_binary1.data -profiler text -binary path_of_binary1 -out a.prof -format binary

# perf_inject_kernel.data is split from perf_inject.data, and only contains branch info for [kernel.kallsyms].
host $ create_llvm_prof -profile perf_inject_kernel.data -profiler text -binary vmlinux -out a.prof -format binary
```

Then we can use a.prof for PGO during compilation, via `-fprofile-sample-use=a.prof`.
[Here](https://clang.llvm.org/docs/UsersManual.html#using-sampling-profilers) are more details.

### A complete example: etm_test_loop.cpp

`etm_test_loop.cpp` is an example to show the complete process.
The source code is in [etm_test_loop.cpp](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/runtest/etm_test_loop.cpp).
The build script is in [Android.bp](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/runtest/Android.bp).
It builds an executable called `etm_test_loop`, which runs on device.

**Step 1: Build `etm_test_loop` binary**

```sh
(host) <AOSP>$ . build/envsetup.sh
(host) <AOSP>$ lunch aosp_arm64-trunk_staging-userdebug
(host) <AOSP>$ make etm_test_loop
```

**Step 2: Run `etm_test_loop` on device, and collect ETM data for its running**

```sh
(host) <AOSP>$ adb push out/target/product/generic_arm64/system/bin/etm_test_loop /data/local/tmp
(host) <AOSP>$ adb root
(host) <AOSP>$ adb shell
(device) / $ cd /data/local/tmp
(device) /data/local/tmp $ chmod a+x etm_test_loop
(device) /data/local/tmp $ simpleperf record -e cs-etm:u ./etm_test_loop
simpleperf I cmd_record.cpp:809] Recorded for 0.033556 seconds. Start post processing.
simpleperf I cmd_record.cpp:879] Aux data traced: 1,134,720
(device) /data/local/tmp $ simpleperf inject -i perf.data --output branch-list -o branch_list.data
(device) /data/local/tmp $ exit
(host) <AOSP>$ adb pull /data/local/tmp/branch_list.data
```

**Step 3: Convert ETM data to AutoFDO profile**

```sh
# Build simpleperf tool on host.
(host) <AOSP>$ make simpleperf_ndk
(host) <AOSP>$ simpleperf inject -i branch_list.data -o perf_inject_etm_test_loop.data --symdir out/target/product/generic_arm64/symbols/system/bin
(host) <AOSP>$ cat perf_inject_etm_test_loop.data
14
4000-4010:1
4014-4048:1
...
418c->0:1
// build_id: 0xa6fc5b506adf9884cdb680b4893c505a00000000
// /data/local/tmp/etm_test_loop

(host) <AOSP>$ create_llvm_prof -profile perf_inject_etm_test_loop.data -profiler text -binary out/target/product/generic_arm64/symbols/system/bin/etm_test_loop -out etm_test_loop.afdo -format binary
(host) <AOSP>$ ls -lh etm_test_loop.afdo
rw-r--r-- 1 user group 241 Apr 30 09:52 etm_test_loop.afdo
```

**Step 4: Use AutoFDO profile to build optimized binary**

```sh
(host) <AOSP>$ cp etm_test_loop.afdo toolchain/pgo-profiles/sampling/
(host) <AOSP>$ vi toolchain/pgo-profiles/sampling/Android.bp
# Edit Android.bp to add a fdo_profile module:
#
# fdo_profile {
#    name: "etm_test_loop",
#    profile: "etm_test_loop.afdo"
# }
(host) <AOSP>$ vi toolchain/pgo-profiles/sampling/afdo_profiles.mk
# Edit afdo_profiles.mk to add etm_test_loop profile mapping:
#
# AFDO_PROFILES += keystore2://toolchain/pgo-profiles/sampling:keystore2 \
#  ...
#  server_configurable_flags://toolchain/pgo-profiles/sampling:server_configurable_flags \
#  etm_test_loop://toolchain/pgo-profiles/sampling:etm_test_loop
#
(host) <AOSP>$ vi system/extras/simpleperf/runtest/Android.bp
# Edit Android.bp to enable afdo for etm_test_loop:
#
# cc_binary {
#    name: "etm_test_loop",
#    srcs: ["etm_test_loop.cpp"],
#    afdo: true,
# }
(host) <AOSP>$ make etm_test_loop
```

We can check if `etm_test_loop.afdo` is used when building etm_test_loop.

```sh
(host) <AOSP>$ gzip -d out/verbose.log.gz
(host) <AOSP>$ cat out/verbose.log | grep etm_test_loop.afdo
   ... -fprofile-sample-use=toolchain/pgo-profiles/sampling/etm_test_loop.afdo ...
```

If comparing the disassembly of `out/target/product/generic_arm64/symbols/system/bin/etm_test_loop`
before and after optimizing with AutoFDO data, we can see different preferences when branching.

### A complete example: kernel

This example demonstrates how to collect ETM data for the Android kernel on a device, convert it to
an AutoFDO profile on the host machine, and then use that profile to build an optimized kernel.


**Step 1 (Optional): Build a Kernel with `-fdebug-info-for-profiling`**

While not strictly required, we recommend building the vmlinux file with the
`-fdebug-info-for-profiling` compiler flag. This option adds extra debug information that helps map
instructions accurately to source code, improving profile quality. For more details, see
[this LLVM review](https://reviews.llvm.org/D25435).

An example of how to add this flag to a kernel build can be found in
[this Android kernel commit](https://android-review.googlesource.com/c/kernel/common/+/3101987).


**Step 2: Collect ETM data for the kernel on device**

```sh
(host) $ adb root && adb shell
(device) / $ cd /data/local/tmp
# Record ETM data while running a representative workload (e.g., launching applications or
# running benchmarks):
(device) / $ simpleperf record -e cs-etm:k -a --duration 60 -z -o perf.data
simpleperf I cmd_record.cpp:826] Recorded for 60.0796 seconds. Start post processing.
simpleperf I cmd_record.cpp:902] Aux data traced: 91,780,432
simpleperf I cmd_record.cpp:894] Record compressed: 27.76 MB (original 110.13 MB, ratio 4)
# Convert the raw ETM data to a branch list to reduce file size:
(device) / $ mkdir branch_data
(device) / $ simpleperf inject -i perf.data -o branch_data/branch01.data --output branch-list \
             --binary kernel.kallsyms
(device) / $ ls branch01.data
-rw-rw-rw- 1 root  root  437K 2024-10-17 23:03 branch01.data
# Run the record command and the inject command multiple times to capture a wider range of kernel
# code execution. ETM data traces the instruction stream, and under heavy load, much of this data
# can be lost due to overflow and rate limiting within simpleperf. Recording multiple profiles and
# merging them improves coverage.
```

Alternative: Instead of manual recording, you can use `profcollectd` to continuously collect ETM
data in the background. See the [Collect ETM Data with a Daemon](#collect-etm-data-with-a-daemon)
section for more information.


**Step 3: Convert ETM data to AutoFDO Profile on Host**

```sh
(host) $ adb pull /data/local/tmp/branch_data
(host) $ cd branch_data
# Download the corresponding vmlinux file and place it in the current directory.
# Merge the branch data files and generate an AutoFDO profile:
(host) $ simpleperf inject -i branch01.data,branch02.data,... --binary kernel.kallsyms --symdir . \
         --allow-mismatched-build-id -o kernel.autofdo -j 20
(host) $ ls -lh kernel.autofdo
-rw-r--r-- 1 yabinc primarygroup 1.3M Oct 17 16:39 kernel.autofdo
# Convert the AutoFDO profile to the LLVM profile format:
(host) $ create_llvm_prof --profiler text --binary=vmlinux --profile=kernel.autofdo \
				--out=kernel.llvm_profdata --format extbinary
(host) $ ls -lh kernel.llvm_profdata
-rw-r--r-- 1 yabinc primarygroup 1.4M Oct 17 19:00 kernel.llvm_profdata
```

**Step 4: Use the AutoFDO Profile when Building a New Kernel**

Integrate the generated kernel.llvm_profdata file into your kernel build process. An example of
how to use this profile data with vmlinux can be found in
[this Android kernel commit](https://android-review.googlesource.com/c/kernel/common/+/3293642).


## Convert ETM data for llvm-bolt (experiment)

We can also convert ETM data to profiles for [llvm-bolt](https://github.com/llvm/llvm-project/tree/main/bolt).
The binaries should have an unstripped symbol table, and linked with relocations (--emit-relocs or
-q linker flag).

```sh
# symdir is the directory containting etm_test_loop with unstripped symbol table and relocations.
(host) $ simpleperf inject -i perf.data --output bolt -o perf_inject_bolt.data --symdir symdir
# Remove the comment line.
(host) $ sed -i '/^\/\//d' perf_inject_bolt.data
(host) $ <LLVM_BIN>/perf2bolt --pa -p=perf_inject_bolt.data -o perf.fdata symdir/etm_test_loop
# --no-huge-pages and --align-text=0x4000 are used to avoid generating big binaries due to
# alignment. See https://github.com/facebookarchive/BOLT/issues/138.
# However, if the original binary is built with huge page alignments (-z max-page-size=0x200000),
# then don't use these flags.
(host) $ <LLVM_BIN>/llvm-bolt symdir/etm_test_loop -o etm_test_loop.bolt -data=perf.fdata \
         -reorder-blocks=ext-tsp -reorder-functions=hfsort -split-functions -split-all-cold \
         -split-eh -dyno-stats --no-huge-pages --align-text=0x4000
```

## Collect ETM data with a daemon

Android also has a daemon collecting ETM data periodically. It only runs on userdebug and eng
devices. The source code is in https://android.googlesource.com/platform/system/extras/+/main/profcollectd/.

## Options for collecting ETM data

Simpleperf provides several options for ETM data collection, which are listed in the
"ETM recording options" section of the `simpleperf record -h` output. Here's an introduction to some
of them:

ETM traces the instruction stream and can generate a large amount of data in a short time. The
kernel uses a buffer to store this data.  The default buffer size is 4MB, which can be controlled
with the `--aux-buffer-size` option. Simpleperf periodically reads data from this buffer, by default
every 100ms. This interval can be adjusted using the `--etm-flush-interval` option. If the buffer
overflows, excess ETM data is lost. The default data generation rate is 40MB/s. This is true when
using ETR, TRBE might copy data more frequently.

To reduce storage size, ETM data can be compressed before being written to disk using the `-z`
option. In practice, this reduces storage size by 75%.

Another way to reduce storage size is to decode ETM data before storing it, using the `--decode-etm`
option. This can achieve around a 98% reduction in storage size. However, it doubles CPU cycles and
and power for recording, and can lead to data loss if processing doesn't keep up with the data
generation rate. For this reason, profcollectd currently uses `-z` for compression instead of
`--decode-etm`.

## Enable ETM data collection

To enable ETM data collection on a device, you must first verify that the required hardware is
present. Then, you need to enable ETM in both the bootloader and the kernel.

### Check hardware support

In ARMv8, instruction tracing relies on two Coresight components:

**Coresight ETM**: Generates the ETM data, recording the instruction stream.

**Coresight ETR**: Transfers the ETM data to system memory for analysis.

ARMv9 offers more flexibility with the introduction of new components:

**Embedded Trace Extension (ETE)**: Replaces the Coresight ETM as the instruction trace source.

**Trace Buffer Extension (TRBE)**: Provides an alternative to Coresight ETR for transferring trace
data to memory. For example:

Pixel 7: Uses Coresight ETM and Coresight ETR (ARMv8).

Pixel 8: Uses ETE and Coresight ETR (ARMv9). While the Pixel 8 has TRBE, known errata with TRBE on
         its Cortex cores makes it unsuitable for use.

Finding Device Support Information:

**ETE and TRBE support**: Refer to the relevant core's technical reference manual (e.g.,
                          [Arm® Cortex-X4 Core Technical Reference Manual](https://developer.arm.com/documentation/102484/0002)).

**TRBE errata**: Consult the core's errata notice (e.g.,
                 [Arm® Cortex-X4 (MP161) Software Developer Errata Notice](https://developer.arm.com/documentation/SDEN-2432808/0800/?lang=en)).

**Coresight ETR support**: Typically detailed in the SoC's manual.

### Enable ETM in the bootloader

To enable Coresight ETM and Coresight ETR on ARMv8 devices (or only Coresight ETR on ARMv9 devices),
you need to allow non-secure, non-invasive debug access on the CPU. The specific method for doing
this varies depending on the SoC. After enabling ETM in the bootloader and kernel, you can verify
that Coresight ETM and ETR are operational by checking their respective `TRCAUTHSTATUS` registers.
Following is an example of Pixel 6 with ETM enabled:

```sh
oriole:/ # cat /sys/bus/coresight/devices/etm0/mgmt/trcauthstatus
0xcc
oriole:/ # cat /sys/bus/coresight/devices/tmc_etr0/mgmt/authstatus
0x33
```

To enable ETE on ARMv9 devices, you need to allow the kernel to access trace system registers. This
is done by setting the `ENABLE_SYS_REG_TRACE_FOR_NS` build option in Trusted Firmware-A (see
[documentation](https://trustedfirmware-a.readthedocs.io/en/v2.11/getting_started/build-options.html)).

To enable TRBE on ARMv9 devices, you need to allow the kernel to access trace buffer control
registers. This is done by setting the `ENABLE_TRBE_FOR_NS` build option in Trusted Firmware-A (see
[documentation](https://trustedfirmware-a.readthedocs.io/en/v2.11/getting_started/build-options.html)).


### Enable ETM in the kernel

Android kernels from version 6.x onwards generally include the necessary patches for ETM data
collection. To enable ETM in the kernel, you need to build the required kernel modules and add the
appropriate device tree entries.

Enable the following kernel configuration options to include the ETM kernel modules:
```config
	CONFIG_CORESIGHT=m
	CONFIG_CORESIGHT_LINK_AND_SINK_TMC=m
	CONFIG_CORESIGHT_SOURCE_ETM4X=m
	CONFIG_CORESIGHT_TRBE=m
```

These options will build the following kernel modules:
```
coresight.ko
coresight-etm4x.ko
coresight-funnel.ko
coresight-replicator.ko
coresight-tmc.ko
coresight-trbe.ko
```

Different SoCs have varying Coresight device connections, address assignments, and interrupt
configurations. Therefore, providing a universal device tree example is not feasible. However, the
following examples from Pixel devices illustrate how device tree entries for ETM components might
look.

**Example 1: Coresight ETM and Coresight ETR (Pixel 6)**

This example shows the device tree entries for Coresight ETM and ETR on Pixel 6
(source: [gs101-debug.dtsi](https://android.googlesource.com/kernel/devices/google/gs101/+/refs/heads/android-gs-tangorpro-6.1-android16-dp/dts/gs101-debug.dtsi#287)).

```device-tree
etm0: etm@25840000 {
    compatible = "arm,primecell";
    arm,primecell-periphid = <0x000bb95d>;
    reg = <0 0x25840000 0x1000>;
    cpu = <&cpu0>;
    coresight-name = "coresight-etm0";
    clocks = <&clock ATCLK>;
    clock-names = "apb_pclk";
    arm,coresight-loses-context-with-cpu;
    out-ports {
        port {
            etm0_out_port: endpoint {
                remote-endpoint = <&funnel0_in_port0>;
            };
        };
    };
};

// ... etm1 to etm7, funnel0 to funnel2, etf0, etf1 ...

etr: etr@2500a000 {
    compatible = "arm,coresight-tmc", "arm,primecell";
    arm,primecell-periphid = <0x001bb961>;
    reg = <0 0x2500a000 0x1000>;
    coresight-name = "coresight-etr";
    arm,scatter-gather;
    clocks = <&clock ATCLK>;
    clock-names = "apb_pclk";
    in-ports {
        port {
            etr_in_port: endpoint {
                remote-endpoint = <&funnel2_out_port>;
            };
        };
    };
};

**Example 2: ETE and Coresight ETR (Pixel 8)**

This example shows the device tree entries for ETE and Coresight ETR on Pixel 8
(source: [zuma-debug.dtsi](https://android.googlesource.com/kernel/devices/google/zuma/+/refs/heads/android-gs-shusky-6.1-android16-dp/dts/zuma-debug.dtsi#428)).

```device-tree
ete0 {
    compatible = "arm,embedded-trace-extension";
    cpu = <&cpu0>;
    arm,coresight-loses-context-with-cpu;
    out-ports {
        port {
            ete0_out_port: endpoint {
                remote-endpoint = <&funnel0_in_port0>;
            };
        };
    };
};

// ... ete1 to ete8, funnel0 to funnel2, etf0 ...

etr: etr@2a00a000 {
    compatible = "arm,coresight-tmc", "arm,primecell";
    arm,primecell-periphid = <0x001bb961>;
    reg = <0 0x2a00a000 0x1000>;
    coresight-name = "coresight-etr";
    arm,scatter-gather;
    clocks = <&clock ATCLK>;
    clock-names = "apb_pclk";
    in-ports {
        port {
            etr_in_port: endpoint {
                remote-endpoint = <&funnel2_out_port>;
            };
        };
    };
};
```

**Example 3: TRBE

This example shows a basic device tree entry for TRBE.

```device-tree
trbe {
    compatible = "arm,trace-buffer-extension";
    interrupts = <GIC_PPI 0 IRQ_TYPE_LEVEL_HIGH 0>;
};
```

One optional flag in the ETM/ETE device tree is `arm,coresight-loses-context-with-cpu`. This flag
ensures that ETM registers are saved when a CPU enters a low-power state. It is necessary if the
CPU powers down the ETM/ETE during low-power states. Without this flag, the kernel cannot properly
resume ETM data collection after the CPU wakes up, and you will likely see a
`coresight_disclaim_device_unlocked` warning during system-wide data collection.

Another optional flag in the ETR device tree is `arm,scatter-gather`. Simpleperf requires 4MB of
contiguous system memory for the ETR to store ETM data (unless an IOMMU is present). If the kernel
cannot provide this contiguous memory, simpleperf will report an out-of-memory error.  Using the
`arm,scatter-gather` flag allows the ETR to operate in scatter-gather mode, enabling it to utilize
non-contiguous memory.

Each CPU has an ETM device with a unique trace_id assigned by the kernel. The standard formula for
determining the trace_id is: `trace_id = 0x10 + cpu * 2` (as defined in
[coresight-pmu.h](https://github.com/torvalds/linux/blob/master/include/linux/coresight-pmu.h#L22)).
If your kernel uses a different formula due to local patches, the simpleperf inject command may
fail to parse the ETM data correctly, potentially resulting in empty output.


### Check ETM enable status in /sys

The status of ETM devices is reflected in /sys. The following is an example from a Pixel 9.

```sh
# List available Coresight devices, including ETE and TRBE.
comet:/sys/bus/coresight/devices $ ls
ete0  ete1  ete2  ete3  ete4  ete5  ete6  ete7  funnel0  funnel1  funnel2  tmc_etf0  tmc_etr0

# Check if Coresight ETR is enabled.
comet:/sys/bus/coresight/devices $ cat tmc_etr0/mgmt/authstatus
0x33

# Check if we have Coresight ETM/ETE devices as perf event sources.
comet:/sys/bus/event_source/devices/cs_etm $ ls -l
total 0
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu0 -> ../platform/ete0/ete0
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu1 -> ../platform/ete1/ete1
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu2 -> ../platform/ete2/ete2
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu3 -> ../platform/ete3/ete3
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu4 -> ../platform/ete4/ete4
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu5 -> ../platform/ete5/ete5
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu6 -> ../platform/ete6/ete6
lrwxrwxrwx 1 root root    0 2024-12-03 17:37 cpu7 -> ../platform/ete7/ete7

# Check if we have Coresight ETR/TRBE to move ETM data to system memory.
comet:/sys/bus/event_source/devices/cs_etm/sinks $ ls
tmc_etf0  tmc_etr0
```


## Related docs

* [Arm Architecture Reference Manual for A-profile architecture, D3-D6](https://developer.arm.com/documentation/ddi0487/latest/)
* [ARM ETM Architecture Specification](https://developer.arm.com/documentation/ihi0064/latest/)
* [ARM CoreSight Architecture Specification](https://developer.arm.com/documentation/ihi0029/latest)
* [CoreSight Components Technical Reference Manual](https://developer.arm.com/documentation/ddi0314/h/)
* [CoreSight Trace Memory Controller Technical Reference Manual](https://developer.arm.com/documentation/ddi0461/b/)
* [OpenCSD library for decoding ETM data](https://github.com/Linaro/OpenCSD)
* [AutoFDO tool for converting profile data](https://github.com/google/autofdo)
