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

import os
import subprocess
from utils import path_exists, dir_exists
from validation_error import ValidationError

TORQ_TEMP_DIR = "/tmp/.torq"
TEMP_CACHE_BUILDER_SCRIPT = TORQ_TEMP_DIR + "/binary_cache_builder.py"
SIMPLEPERF_SCRIPTS_DIR = "/system/extras/simpleperf/scripts"
BUILDER_SCRIPT = SIMPLEPERF_SCRIPTS_DIR + "/binary_cache_builder.py"

def verify_simpleperf_args(args):
  args.scripts_path = TORQ_TEMP_DIR
  if ("ANDROID_BUILD_TOP" in os.environ
      and path_exists(os.environ["ANDROID_BUILD_TOP"] + BUILDER_SCRIPT)):
    args.scripts_path = (os.environ["ANDROID_BUILD_TOP"]
                         + SIMPLEPERF_SCRIPTS_DIR)

  if args.symbols is None or not dir_exists(args.symbols):
    if args.symbols is not None:
      return None, ValidationError(
          ("%s is not a valid path." % args.symbols),
          "Set --symbols to a valid symbols lib path or set "
          "$ANDROID_PRODUCT_OUT to your android product out directory "
          "(<ANDROID_BUILD_TOP>/out/target/product/<TARGET>).")
    if "ANDROID_PRODUCT_OUT" not in os.environ:
      return None, ValidationError(
          "ANDROID_PRODUCT_OUT is not set.",
          "Set --symbols to a valid symbols lib path or set "
          "$ANDROID_PRODUCT_OUT to your android product out directory "
          "(<ANDROID_BUILD_TOP>/out/target/product/<TARGET>).")
    if not dir_exists(os.environ["ANDROID_PRODUCT_OUT"]):
      return None, ValidationError(
          ("%s is not a valid $ANDROID_PRODUCT_OUT."
           % (os.environ["ANDROID_PRODUCT_OUT"])),
          "Set --symbols to a valid symbols lib path or set "
          "$ANDROID_PRODUCT_OUT to your android product out directory "
          "(<ANDROID_BUILD_TOP>/out/target/product/<TARGET>).")
    args.symbols = os.environ["ANDROID_PRODUCT_OUT"]

  if (args.scripts_path != TORQ_TEMP_DIR or
      path_exists(TEMP_CACHE_BUILDER_SCRIPT)):
    return args, None

  error = download_simpleperf_scripts()

  if error is not None:
    return None, error

  return args, None

def download_simpleperf_scripts():
  i = 0
  while i <= 3:
    i += 1
    confirmation = input("You do not have an Android Root configured with "
                         "the simpleperf directory. To use simpleperf, torq "
                         "will download simpleperf scripts to '%s'. "
                         "Are you ok with this download? [Y/N]: "
                         % TORQ_TEMP_DIR)

    if confirmation.lower() == "y":
      break
    elif confirmation.lower() == "n":
      return ValidationError("Did not download simpleperf scripts.",
                             "Set $ANDROID_BUILD_TOP to your android root "
                             "path and make sure you have $ANDROID_BUILD_TOP"
                             "/system/extras/simpleperf/scripts "
                             "downloaded.")
    if i == 3:
      return ValidationError("Invalid inputs.",
                             "Set $ANDROID_BUILD_TOP to your android root "
                             "path and make sure you have $ANDROID_BUILD_TOP"
                             "/system/extras/simpleperf/scripts "
                             "downloaded.")

  subprocess.run(("mkdir -p %s && wget -P %s "
                 "https://android.googlesource.com/platform/system/extras"
                 "/+archive/refs/heads/main/simpleperf/scripts.tar.gz "
                 "&& tar -xvzf %s/scripts.tar.gz -C %s"
                  % (TORQ_TEMP_DIR, TORQ_TEMP_DIR, TORQ_TEMP_DIR,
                     TORQ_TEMP_DIR)),
                 shell=True)

  if not path_exists(TEMP_CACHE_BUILDER_SCRIPT):
    raise Exception("Error while downloading simpleperf scripts. Try again "
                    "or set $ANDROID_BUILD_TOP to your android root path and "
                    "make sure you have $ANDROID_BUILD_TOP/system/extras/"
                    "simpleperf/scripts downloaded.")

  return None
