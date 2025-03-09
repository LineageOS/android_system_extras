/*
 * Copyright (C) 2023 The Android Open Source Project
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

#include <gtest/gtest.h>

#include "BranchListFile.h"
#include "get_test_data.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(BranchListFile, etm_branch_to_proto_string) {
  std::vector<bool> branch;
  for (size_t i = 0; i < 100; i++) {
    branch.push_back(i % 2 == 0);
    std::string s = ETMBranchToProtoString(branch);
    for (size_t j = 0; j <= i; j++) {
      bool b = s[j >> 3] & (1 << (j & 7));
      ASSERT_EQ(b, branch[j]);
    }
    std::vector<bool> branch2 = ProtoStringToETMBranch(s, branch.size());
    ASSERT_EQ(branch, branch2);
  }
}

static bool IsETMDataEqual(ETMBinaryMap& data1, ETMBinaryMap& data2) {
  if (data1.size() != data2.size()) {
    return false;
  }
  for (const auto& [key, binary1] : data1) {
    auto it = data2.find(key);
    if (it == data2.end()) {
      return false;
    }
    ETMBinary& binary2 = it->second;
    if (binary1.dso_type != binary2.dso_type) {
      return false;
    }
    const UnorderedETMBranchMap& branch_map1 = binary1.branch_map;
    const UnorderedETMBranchMap& branch_map2 = binary2.branch_map;
    if (branch_map1.size() != branch_map2.size()) {
      return false;
    }
    for (const auto& [addr, b_map1] : branch_map1) {
      auto it2 = branch_map2.find(addr);
      if (it2 == branch_map2.end()) {
        return false;
      }
      const auto& b_map2 = it2->second;
      if (b_map1.size() != b_map2.size()) {
        return false;
      }
      for (const auto& [branch, count1] : b_map1) {
        auto it3 = b_map2.find(branch);
        if (it3 == b_map2.end()) {
          return false;
        }
        if (count1 != it3->second) {
          return false;
        }
      }
    }
  }
  return true;
}

static bool IsLBRDataEqual(const LBRData& data1, const LBRData& data2) {
  if (data1.samples.size() != data2.samples.size()) {
    return false;
  }
  for (size_t i = 0; i < data1.samples.size(); i++) {
    const LBRSample& sample1 = data1.samples[i];
    const LBRSample& sample2 = data2.samples[i];
    if (sample1.binary_id != sample2.binary_id) {
      return false;
    }
    if (sample1.vaddr_in_file != sample2.vaddr_in_file) {
      return false;
    }
    if (sample1.branches.size() != sample2.branches.size()) {
      return false;
    }
    for (size_t j = 0; j < sample1.branches.size(); j++) {
      const LBRBranch& b1 = sample1.branches[j];
      const LBRBranch& b2 = sample2.branches[j];
      if (b1.from_binary_id != b2.from_binary_id || b1.to_binary_id != b2.to_binary_id ||
          b1.from_vaddr_in_file != b2.from_vaddr_in_file ||
          b1.to_vaddr_in_file != b2.to_vaddr_in_file) {
        return false;
      }
    }
  }
  return data1.binaries == data2.binaries;
}

// @CddTest = 6.1/C-0-2
TEST(BranchListProtoReaderWriter, smoke) {
  ETMBinaryMap etm_data;
  ETMBinary& binary = etm_data[BinaryKey("fake_binary", BuildId())];
  binary.dso_type = DSO_ELF_FILE;
  UnorderedETMBranchMap& branch_map = binary.branch_map;
  for (size_t addr = 0; addr <= 1024; addr++) {
    auto& b_map = branch_map[addr];
    std::vector<bool> branch1 = {true};
    b_map[branch1] = 1;
    std::vector<bool> branch2 = {true, false};
    b_map[branch2] = 2;
  }
  LBRData lbr_data;
  lbr_data.binaries.emplace_back(BinaryKey("binary1", BuildId()));
  lbr_data.binaries.emplace_back(BinaryKey("binary2", BuildId()));
  for (uint64_t from_addr = 0; from_addr <= 10; from_addr++) {
    for (uint64_t to_addr = 100; to_addr <= 110; to_addr++) {
      LBRBranch branch = {0, 1, from_addr, to_addr};
      LBRSample sample = {0, from_addr, {branch}};
      lbr_data.samples.emplace_back(sample);
    }
  }

  TemporaryFile tmpfile;
  close(tmpfile.fd);
  for (size_t max_branches_per_message : {100, 100000000}) {
    for (bool compress : {false, true}) {
      auto writer =
          BranchListProtoWriter::CreateForFile(tmpfile.path, compress, max_branches_per_message);
      ASSERT_TRUE(writer);
      ASSERT_TRUE(writer->Write(etm_data));
      ASSERT_TRUE(writer->Write(lbr_data));
      writer = nullptr;
      auto reader = BranchListProtoReader::CreateForFile(tmpfile.path);
      ASSERT_TRUE(reader);
      ETMBinaryMap new_etm_data;
      LBRData new_lbr_data;
      ASSERT_TRUE(reader->Read(new_etm_data, new_lbr_data));
      ASSERT_TRUE(IsETMDataEqual(etm_data, new_etm_data));
      ASSERT_TRUE(IsLBRDataEqual(lbr_data, new_lbr_data));
    }
  }
}

// @CddTest = 6.1/C-0-2
TEST(BranchListProtoReaderWriter, read_old_branch_list_file) {
  std::string path = GetTestData("etm/old_branch_list.data");
  auto reader = BranchListProtoReader::CreateForFile(path);
  ASSERT_TRUE(reader);
  ETMBinaryMap etm_data;
  LBRData lbr_data;
  ASSERT_TRUE(reader->Read(etm_data, lbr_data));
  ASSERT_EQ(etm_data.size(), 1u);
}
