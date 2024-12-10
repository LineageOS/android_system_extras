/*
 * Copyright (C) 2024 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
//
// Test if simpleperf -> create_llvm_prof can convert addresses in ETM data correctly to
// symbols and source lines in llvm prof data.
//
// To test address conversion for userspace binaries:
// 1. Generate branch list file on device:
//   (device) $ simpleperf record -e cs-etm:u --delay 10 --duration 1 ./autofdo_addr_test
//   (device) $ simpleperf inject -i perf.data --output branch-list -o branch_user.data
//
// 2. Generate llvm prof data on host:
//   (host) $ simpleperf inject -i branch_user.data --symdir .
//   (host) $ create_llvm_prof --profiler text --binary=autofdo_addr_test \
//            --profile=perf_inject.data --out=user.profdata --format text
//
// 3. Check llvm prof data. It should show something like the following content:
//    (host) $ cat user.profdata
//       main:4289758:0
//          0: 0
//          1: 428974
//          2: 428976
//
// To test address conversion for vmlinux:
// 1. Generate branch list file on device:
//   (device) $ simpleperf inject -e cs-etm:k --delay 10 --duration 1 ./autofdo_addr_test
//   (device) $ simpleperf inject -i perf.data --output branch-list -o branch.data
//
// 2. Generate llvm prof data on host:
//   (device) $ simpleperf inject -i branch.data --symdir .
//   (device) $ create_llvm_prof --profiler text --binary=vmlinux --profile=perf_inject.data \
//              --out=kernel.profdata --format text
//
// 3. Check llvm prof data. The top functions should be like the following content:
//    (host) $ cat kernel.profdata | grep -v "^ "
//        __arm64_sys_getpriority:24967795:0
//        do_el0_svc:13978399:185833
//        el0_svc:11968147:184885
//        invoke_syscall:8962484:2843
//        __rcu_read_unlock:8667849:200748
//        el0_svc_common:7142648:0
//
// [TODO] Test address conversion for kernel modules
//
//
//
// Test if simpleperf -> perf2bolt can convert addresses in ETM data correctly to symbols and
// and offsets in perf2bolt.
//
// To test address conversion for userspace binaries:
// 1. Generate branch list file on device (as for create_llvm_prof)
// 2. Generate perf2bolt profile on host:
//   (host) $ simpleperf inject -i branch_user.data --output bolt -o perf_inject_bolt.data \
//              --symdir .
//   (host) $ sed -i '1d' perf_inject_bolt.data
//   (host) $ perf2bolt --pa -p perf_inject_bolt.data -o perf.fdata autofdo_addr_test
//
// 3. Check perf.fdata. The output should be like the following content:
//   (host) $ cat perf.fdata
//   1 getpriority@PLT c 0 [unknown] 0 0 429112
//   1 main 10 1 getpriority@PLT 0 0 429110
//   1 main 14 1 main 8 0 429109
//
//

#include <sys/resource.h>

int main() {
  while (true) {
    getpriority(PRIO_PROCESS, 0);
  }
  return 0;
}
