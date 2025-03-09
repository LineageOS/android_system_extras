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

#include "BranchListFile.h"

#include "ETMDecoder.h"
#include "ZstdUtil.h"
#include "system/extras/simpleperf/branch_list.pb.h"

namespace simpleperf {

static constexpr const char* ETM_BRANCH_LIST_PROTO_MAGIC = "simpleperf:EtmBranchList";

std::string ETMBranchToProtoString(const std::vector<bool>& branch) {
  size_t bytes = (branch.size() + 7) / 8;
  std::string res(bytes, '\0');
  for (size_t i = 0; i < branch.size(); i++) {
    if (branch[i]) {
      res[i >> 3] |= 1 << (i & 7);
    }
  }
  return res;
}

std::vector<bool> ProtoStringToETMBranch(const std::string& s, size_t bit_size) {
  std::vector<bool> branch(bit_size, false);
  for (size_t i = 0; i < bit_size; i++) {
    if (s[i >> 3] & (1 << (i & 7))) {
      branch[i] = true;
    }
  }
  return branch;
}

static std::optional<proto::ETMBinary::BinaryType> ToProtoBinaryType(DsoType dso_type) {
  switch (dso_type) {
    case DSO_ELF_FILE:
      return proto::ETMBinary::ELF_FILE;
    case DSO_KERNEL:
      return proto::ETMBinary::KERNEL;
    case DSO_KERNEL_MODULE:
      return proto::ETMBinary::KERNEL_MODULE;
    default:
      LOG(ERROR) << "unexpected dso type " << dso_type;
      return std::nullopt;
  }
}

bool ETMBinaryMapToString(const ETMBinaryMap& binary_map, std::string& s) {
  auto writer = BranchListProtoWriter::CreateForString(&s, false);
  if (!writer) {
    return false;
  }
  if (!writer->Write(binary_map)) {
    return false;
  }
  return true;
}

static std::optional<DsoType> ToDsoType(proto::ETMBinary::BinaryType binary_type) {
  switch (binary_type) {
    case proto::ETMBinary::ELF_FILE:
      return DSO_ELF_FILE;
    case proto::ETMBinary::KERNEL:
      return DSO_KERNEL;
    case proto::ETMBinary::KERNEL_MODULE:
      return DSO_KERNEL_MODULE;
    default:
      LOG(ERROR) << "unexpected binary type " << binary_type;
      return std::nullopt;
  }
}

bool StringToETMBinaryMap(const std::string& s, ETMBinaryMap& binary_map) {
  LBRData lbr_data;
  auto reader = BranchListProtoReader::CreateForString(s);
  if (!reader) {
    return false;
  }
  return reader->Read(binary_map, lbr_data);
}

class ETMThreadTreeWhenRecording : public ETMThreadTree {
 public:
  ETMThreadTreeWhenRecording(bool dump_maps_from_proc)
      : dump_maps_from_proc_(dump_maps_from_proc) {}

  ThreadTree& GetThreadTree() { return thread_tree_; }
  void ExcludePid(pid_t pid) { exclude_pid_ = pid; }

  const ThreadEntry* FindThread(int tid) override {
    const ThreadEntry* thread = thread_tree_.FindThread(tid);
    if (thread == nullptr) {
      if (dump_maps_from_proc_) {
        thread = FindThreadFromProc(tid);
      }
      if (thread == nullptr) {
        return nullptr;
      }
    }
    if (exclude_pid_ && exclude_pid_ == thread->pid) {
      return nullptr;
    }

    if (dump_maps_from_proc_) {
      DumpMapsFromProc(thread->pid);
    }
    return thread;
  }

  void DisableThreadExitRecords() override { thread_tree_.DisableThreadExitRecords(); }
  const MapSet& GetKernelMaps() override { return thread_tree_.GetKernelMaps(); }

 private:
  const ThreadEntry* FindThreadFromProc(int tid) {
    std::string comm;
    pid_t pid;
    if (ReadThreadNameAndPid(tid, &comm, &pid)) {
      thread_tree_.SetThreadName(pid, tid, comm);
      return thread_tree_.FindThread(tid);
    }
    return nullptr;
  }

  void DumpMapsFromProc(int pid) {
    if (dumped_processes_.count(pid) == 0) {
      dumped_processes_.insert(pid);
      std::vector<ThreadMmap> maps;
      if (GetThreadMmapsInProcess(pid, &maps)) {
        for (const auto& map : maps) {
          thread_tree_.AddThreadMap(pid, pid, map.start_addr, map.len, map.pgoff, map.name);
        }
      }
    }
  }

  ThreadTree thread_tree_;
  bool dump_maps_from_proc_;
  std::unordered_set<int> dumped_processes_;
  std::optional<pid_t> exclude_pid_;
};

class ETMBranchListGeneratorImpl : public ETMBranchListGenerator {
 public:
  ETMBranchListGeneratorImpl(bool dump_maps_from_proc)
      : thread_tree_(dump_maps_from_proc), binary_filter_(nullptr) {}

  void SetExcludePid(pid_t pid) override { thread_tree_.ExcludePid(pid); }
  void SetBinaryFilter(const RegEx* binary_name_regex) override {
    binary_filter_.SetRegex(binary_name_regex);
  }

  bool ProcessRecord(const Record& r, bool& consumed) override;
  ETMBinaryMap GetETMBinaryMap() override;

 private:
  struct AuxRecordData {
    uint64_t start;
    uint64_t end;
    bool formatted;
    AuxRecordData(uint64_t start, uint64_t end, bool formatted)
        : start(start), end(end), formatted(formatted) {}
  };

  struct PerCpuData {
    std::vector<uint8_t> aux_data;
    uint64_t data_offset = 0;
    std::queue<AuxRecordData> aux_records;
  };

  bool ProcessAuxRecord(const AuxRecord& r);
  bool ProcessAuxTraceRecord(const AuxTraceRecord& r);
  void ProcessBranchList(const ETMBranchList& branch_list);

  ETMThreadTreeWhenRecording thread_tree_;
  uint64_t kernel_map_start_addr_ = 0;
  BinaryFilter binary_filter_;
  std::map<uint32_t, PerCpuData> cpu_map_;
  std::unique_ptr<ETMDecoder> etm_decoder_;
  std::unordered_map<Dso*, ETMBinary> branch_list_binary_map_;
};

bool ETMBranchListGeneratorImpl::ProcessRecord(const Record& r, bool& consumed) {
  consumed = true;  // No need to store any records.
  uint32_t type = r.type();
  if (type == PERF_RECORD_AUXTRACE_INFO) {
    etm_decoder_ = ETMDecoder::Create(*static_cast<const AuxTraceInfoRecord*>(&r), thread_tree_);
    if (!etm_decoder_) {
      return false;
    }
    etm_decoder_->RegisterCallback(
        [this](const ETMBranchList& branch) { ProcessBranchList(branch); });
    return true;
  }
  if (type == PERF_RECORD_AUX) {
    return ProcessAuxRecord(*static_cast<const AuxRecord*>(&r));
  }
  if (type == PERF_RECORD_AUXTRACE) {
    return ProcessAuxTraceRecord(*static_cast<const AuxTraceRecord*>(&r));
  }
  if (type == PERF_RECORD_MMAP && r.InKernel()) {
    auto& mmap_r = *static_cast<const MmapRecord*>(&r);
    if (android::base::StartsWith(mmap_r.filename, DEFAULT_KERNEL_MMAP_NAME)) {
      kernel_map_start_addr_ = mmap_r.data->addr;
    }
  }
  thread_tree_.GetThreadTree().Update(r);
  return true;
}

bool ETMBranchListGeneratorImpl::ProcessAuxRecord(const AuxRecord& r) {
  OverflowResult result = SafeAdd(r.data->aux_offset, r.data->aux_size);
  if (result.overflow || r.data->aux_size > SIZE_MAX) {
    LOG(ERROR) << "invalid aux record";
    return false;
  }
  size_t size = r.data->aux_size;
  uint64_t start = r.data->aux_offset;
  uint64_t end = result.value;
  PerCpuData& data = cpu_map_[r.Cpu()];
  if (start >= data.data_offset && end <= data.data_offset + data.aux_data.size()) {
    // The ETM data is available. Process it now.
    uint8_t* p = data.aux_data.data() + (start - data.data_offset);
    if (!etm_decoder_) {
      LOG(ERROR) << "ETMDecoder isn't created";
      return false;
    }
    return etm_decoder_->ProcessData(p, size, !r.Unformatted(), r.Cpu());
  }
  // The ETM data isn't available. Put the aux record into queue.
  data.aux_records.emplace(start, end, !r.Unformatted());
  return true;
}

bool ETMBranchListGeneratorImpl::ProcessAuxTraceRecord(const AuxTraceRecord& r) {
  OverflowResult result = SafeAdd(r.data->offset, r.data->aux_size);
  if (result.overflow || r.data->aux_size > SIZE_MAX) {
    LOG(ERROR) << "invalid auxtrace record";
    return false;
  }
  size_t size = r.data->aux_size;
  uint64_t start = r.data->offset;
  uint64_t end = result.value;
  PerCpuData& data = cpu_map_[r.Cpu()];
  data.data_offset = start;
  CHECK(r.location.addr != nullptr);
  data.aux_data.resize(size);
  memcpy(data.aux_data.data(), r.location.addr, size);

  // Process cached aux records.
  while (!data.aux_records.empty() && data.aux_records.front().start < end) {
    const AuxRecordData& aux = data.aux_records.front();
    if (aux.start >= start && aux.end <= end) {
      uint8_t* p = data.aux_data.data() + (aux.start - start);
      if (!etm_decoder_) {
        LOG(ERROR) << "ETMDecoder isn't created";
        return false;
      }
      if (!etm_decoder_->ProcessData(p, aux.end - aux.start, aux.formatted, r.Cpu())) {
        return false;
      }
    }
    data.aux_records.pop();
  }
  return true;
}

void ETMBranchListGeneratorImpl::ProcessBranchList(const ETMBranchList& branch_list) {
  if (!binary_filter_.Filter(branch_list.dso)) {
    return;
  }
  auto& branch_map = branch_list_binary_map_[branch_list.dso].branch_map;
  ++branch_map[branch_list.addr][branch_list.branch];
}

ETMBinaryMap ETMBranchListGeneratorImpl::GetETMBinaryMap() {
  ETMBinaryMap binary_map;
  for (auto& p : branch_list_binary_map_) {
    Dso* dso = p.first;
    ETMBinary& binary = p.second;
    binary.dso_type = dso->type();
    BuildId build_id;
    GetBuildId(*dso, build_id);
    BinaryKey key(dso->Path(), build_id);
    if (binary.dso_type == DSO_KERNEL) {
      if (kernel_map_start_addr_ == 0) {
        LOG(WARNING) << "Can't convert kernel ip addresses without kernel start addr. So remove "
                        "branches for the kernel.";
        continue;
      }
      key.kernel_start_addr = kernel_map_start_addr_;
    }
    binary_map[key] = std::move(binary);
  }
  return binary_map;
}

std::unique_ptr<ETMBranchListGenerator> ETMBranchListGenerator::Create(bool dump_maps_from_proc) {
  return std::unique_ptr<ETMBranchListGenerator>(
      new ETMBranchListGeneratorImpl(dump_maps_from_proc));
}

ETMBranchListGenerator::~ETMBranchListGenerator() {}

bool LBRDataToString(const LBRData& data, std::string& s) {
  auto writer = BranchListProtoWriter::CreateForString(&s, false);
  if (!writer) {
    return false;
  }
  if (!writer->Write(data)) {
    return false;
  }
  return true;
}

std::unique_ptr<BranchListProtoWriter> BranchListProtoWriter::CreateForFile(
    const std::string& output_filename, bool compress, size_t max_branches_per_message) {
  auto writer = std::unique_ptr<BranchListProtoWriter>(
      new BranchListProtoWriter(output_filename, nullptr, compress, max_branches_per_message));
  if (!writer->WriteHeader()) {
    return nullptr;
  }
  return writer;
}

std::unique_ptr<BranchListProtoWriter> BranchListProtoWriter::CreateForString(
    std::string* output_str, bool compress, size_t max_branches_per_message) {
  auto writer = std::unique_ptr<BranchListProtoWriter>(
      new BranchListProtoWriter("", output_str, compress, max_branches_per_message));
  if (!writer->WriteHeader()) {
    return nullptr;
  }
  return writer;
}

bool BranchListProtoWriter::Write(const ETMBinaryMap& etm_data) {
  if (!output_fp_ && !WriteHeader()) {
    return false;
  }
  std::unique_ptr<proto::BranchList> proto_branch_list = std::make_unique<proto::BranchList>();
  proto::ETMBinary* proto_binary = nullptr;
  proto::ETMBinary_Address* proto_addr = nullptr;
  size_t branch_count = 0;

  auto add_proto_binary = [&](const BinaryKey& key, const ETMBinary& binary) {
    proto_binary = proto_branch_list->add_etm_data();
    proto_binary->set_path(key.path);
    if (!key.build_id.IsEmpty()) {
      proto_binary->set_build_id(key.build_id.ToString().substr(2));
    }
    auto opt_binary_type = ToProtoBinaryType(binary.dso_type);
    if (!opt_binary_type.has_value()) {
      return false;
    }
    proto_binary->set_type(opt_binary_type.value());
    if (binary.dso_type == DSO_KERNEL) {
      proto_binary->mutable_kernel_info()->set_kernel_start_addr(key.kernel_start_addr);
    }
    return true;
  };

  auto add_proto_addr = [&](uint64_t addr) {
    proto_addr = proto_binary->add_addrs();
    proto_addr->set_addr(addr);
  };

  for (const auto& [key, binary] : etm_data) {
    if (!add_proto_binary(key, binary)) {
      return false;
    }
    for (const auto& [addr, branch_map] : binary.branch_map) {
      add_proto_addr(addr);
      size_t new_branch_count = 0;
      for (const auto& [branch, _] : branch_map) {
        new_branch_count += branch.size();
      }
      if (branch_count + new_branch_count > max_branches_per_message_) {
        if (!WriteProtoBranchList(*proto_branch_list)) {
          return false;
        }
        proto_branch_list.reset(new proto::BranchList);
        if (!add_proto_binary(key, binary)) {
          return false;
        }
        add_proto_addr(addr);
        branch_count = 0;
      }
      branch_count += new_branch_count;
      for (const auto& [branch, count] : branch_map) {
        proto::ETMBinary_Address_Branch* proto_branch = proto_addr->add_branches();
        proto_branch->set_branch(ETMBranchToProtoString(branch));
        proto_branch->set_branch_size(branch.size());
        proto_branch->set_count(count);
      }
    }
  }
  return WriteProtoBranchList(*proto_branch_list);
}

bool BranchListProtoWriter::Write(const LBRData& lbr_data) {
  if (!output_fp_ && !WriteHeader()) {
    return false;
  }
  proto::BranchList proto_branch_list;
  proto_branch_list.set_magic(ETM_BRANCH_LIST_PROTO_MAGIC);
  auto proto_lbr = proto_branch_list.mutable_lbr_data();
  for (const LBRSample& sample : lbr_data.samples) {
    auto proto_sample = proto_lbr->add_samples();
    proto_sample->set_binary_id(sample.binary_id);
    proto_sample->set_vaddr_in_file(sample.vaddr_in_file);
    for (const LBRBranch& branch : sample.branches) {
      auto proto_branch = proto_sample->add_branches();
      proto_branch->set_from_binary_id(branch.from_binary_id);
      proto_branch->set_to_binary_id(branch.to_binary_id);
      proto_branch->set_from_vaddr_in_file(branch.from_vaddr_in_file);
      proto_branch->set_to_vaddr_in_file(branch.to_vaddr_in_file);
    }
  }
  for (const BinaryKey& binary : lbr_data.binaries) {
    auto proto_binary = proto_lbr->add_binaries();
    proto_binary->set_path(binary.path);
    proto_binary->set_build_id(binary.build_id.ToString().substr(2));
  }
  return WriteProtoBranchList(proto_branch_list);
}

bool BranchListProtoWriter::WriteHeader() {
  if (!output_filename_.empty()) {
    output_fp_.reset(fopen(output_filename_.c_str(), "wbe"));
    if (!output_fp_) {
      PLOG(ERROR) << "failed to open " << output_filename_;
      return false;
    }
  } else {
    output_str_->clear();
  }
  if (!WriteData(ETM_BRANCH_LIST_PROTO_MAGIC, strlen(ETM_BRANCH_LIST_PROTO_MAGIC))) {
    return false;
  }
  uint32_t version = 1;
  if (!WriteData(&version, sizeof(version))) {
    return false;
  }
  uint8_t compress = compress_ ? 1 : 0;
  if (!WriteData(&compress, sizeof(compress))) {
    return false;
  }
  return true;
}

bool BranchListProtoWriter::WriteProtoBranchList(proto::BranchList& branch_list) {
  std::string s;
  if (!branch_list.SerializeToString(&s)) {
    LOG(ERROR) << "failed to serialize branch list binary map";
    return false;
  }
  if (compress_ && !ZstdCompress(s.data(), s.size(), s)) {
    return false;
  }
  uint32_t msg_size = s.size();
  return WriteData(&msg_size, sizeof(msg_size)) && WriteData(s.data(), s.size());
}

bool BranchListProtoWriter::WriteData(const void* data, size_t size) {
  if (output_fp_) {
    if (fwrite(data, size, 1, output_fp_.get()) != 1) {
      LOG(ERROR) << "failed to write to " << output_filename_;
      return false;
    }
  } else {
    output_str_->insert(output_str_->size(), static_cast<const char*>(data), size);
  }
  return true;
}

std::unique_ptr<BranchListProtoReader> BranchListProtoReader::CreateForFile(
    const std::string& input_filename) {
  return std::unique_ptr<BranchListProtoReader>(new BranchListProtoReader(input_filename, ""));
}

std::unique_ptr<BranchListProtoReader> BranchListProtoReader::CreateForString(
    const std::string& input_str) {
  return std::unique_ptr<BranchListProtoReader>(new BranchListProtoReader("", input_str));
}

bool BranchListProtoReader::Read(ETMBinaryMap& etm_data, LBRData& lbr_data) {
  if (!input_filename_.empty()) {
    input_fp_.reset(fopen(input_filename_.c_str(), "rbe"));
    if (!input_fp_) {
      PLOG(ERROR) << "failed to open " << input_filename_;
      return false;
    }
  }
  char magic[24];
  if (!ReadData(magic, sizeof(magic)) ||
      memcmp(magic, ETM_BRANCH_LIST_PROTO_MAGIC, sizeof(magic)) != 0) {
    return ReadOldFileFormat(etm_data, lbr_data);
  }
  uint32_t version;
  if (!ReadData(&version, sizeof(version)) && version != 1) {
    LOG(ERROR) << "unsupported version in " << input_filename_;
    return false;
  }
  uint8_t compress;
  if (!ReadData(&compress, sizeof(compress))) {
    return false;
  }
  compress_ = compress == 1;
  long file_offset = ftell(input_fp_.get());
  if (file_offset == -1) {
    PLOG(ERROR) << "failed to call ftell";
    return false;
  }
  uint64_t file_size = GetFileSize(input_filename_);
  while (file_offset < file_size) {
    uint32_t msg_size;
    if (!ReadData(&msg_size, sizeof(msg_size))) {
      return false;
    }
    proto::BranchList proto_branch_list;
    if (!ReadProtoBranchList(msg_size, proto_branch_list)) {
      return false;
    }
    for (size_t i = 0; i < proto_branch_list.etm_data_size(); i++) {
      const proto::ETMBinary& proto_binary = proto_branch_list.etm_data(i);
      if (!AddETMBinary(proto_binary, etm_data)) {
        return false;
      }
    }
    if (proto_branch_list.has_lbr_data()) {
      AddLBRData(proto_branch_list.lbr_data(), lbr_data);
    }
    file_offset += 4 + msg_size;
  }
  return true;
}

bool BranchListProtoReader::AddETMBinary(const proto::ETMBinary& proto_binary,
                                         ETMBinaryMap& etm_data) {
  BinaryKey key(proto_binary.path(), BuildId(proto_binary.build_id()));
  if (proto_binary.has_kernel_info()) {
    key.kernel_start_addr = proto_binary.kernel_info().kernel_start_addr();
  }
  ETMBinary& binary = etm_data[key];
  auto dso_type = ToDsoType(proto_binary.type());
  if (!dso_type) {
    LOG(ERROR) << "invalid binary type " << proto_binary.type();
    return false;
  }
  binary.dso_type = dso_type.value();
  auto& branch_map = binary.branch_map;
  for (size_t i = 0; i < proto_binary.addrs_size(); i++) {
    const auto& proto_addr = proto_binary.addrs(i);
    auto& b_map = branch_map[proto_addr.addr()];
    for (size_t j = 0; j < proto_addr.branches_size(); j++) {
      const auto& proto_branch = proto_addr.branches(j);
      std::vector<bool> branch =
          ProtoStringToETMBranch(proto_branch.branch(), proto_branch.branch_size());
      b_map[branch] = proto_branch.count();
    }
  }
  return true;
}

void BranchListProtoReader::AddLBRData(const proto::LBRData& proto_lbr_data, LBRData& lbr_data) {
  for (size_t i = 0; i < proto_lbr_data.samples_size(); ++i) {
    const auto& proto_sample = proto_lbr_data.samples(i);
    lbr_data.samples.resize(lbr_data.samples.size() + 1);
    LBRSample& sample = lbr_data.samples.back();
    sample.binary_id = proto_sample.binary_id();
    sample.vaddr_in_file = proto_sample.vaddr_in_file();
    sample.branches.resize(proto_sample.branches_size());
    for (size_t j = 0; j < proto_sample.branches_size(); ++j) {
      const auto& proto_branch = proto_sample.branches(j);
      LBRBranch& branch = sample.branches[j];
      branch.from_binary_id = proto_branch.from_binary_id();
      branch.to_binary_id = proto_branch.to_binary_id();
      branch.from_vaddr_in_file = proto_branch.from_vaddr_in_file();
      branch.to_vaddr_in_file = proto_branch.to_vaddr_in_file();
    }
  }
  for (size_t i = 0; i < proto_lbr_data.binaries_size(); ++i) {
    const auto& proto_binary = proto_lbr_data.binaries(i);
    lbr_data.binaries.emplace_back(proto_binary.path(), BuildId(proto_binary.build_id()));
  }
}

bool BranchListProtoReader::ReadProtoBranchList(uint32_t size,
                                                proto::BranchList& proto_branch_list) {
  std::string s;
  s.resize(size);
  if (!ReadData(s.data(), size)) {
    return false;
  }
  if (compress_ && !ZstdDecompress(s.data(), s.size(), s)) {
    return false;
  }
  if (!proto_branch_list.ParseFromString(s)) {
    PLOG(ERROR) << "failed to read ETMBranchList msg";
    return false;
  }
  return true;
}

void BranchListProtoReader::Rewind() {
  if (input_fp_) {
    rewind(input_fp_.get());
  } else {
    input_str_pos_ = 0;
  }
}

bool BranchListProtoReader::ReadData(void* data, size_t size) {
  if (input_fp_) {
    if (fread(data, size, 1, input_fp_.get()) != 1) {
      PLOG(ERROR) << "failed to read " << input_filename_;
      return false;
    }
  } else {
    if (input_str_pos_ + size > input_str_.size()) {
      LOG(ERROR) << "failed to read BranchList from string";
      return false;
    }
    memcpy(data, &input_str_[input_str_pos_], size);
    input_str_pos_ += size;
  }
  return true;
}

bool BranchListProtoReader::ReadOldFileFormat(ETMBinaryMap& etm_data, LBRData& lbr_data) {
  size_t size = 0;
  if (!input_filename_.empty()) {
    size = static_cast<size_t>(GetFileSize(input_filename_));
    if (android::base::EndsWith(input_filename_, ".zst")) {
      compress_ = true;
    }
  } else {
    size = input_str_.size();
  }
  Rewind();
  proto::BranchList proto_branch_list;
  if (!ReadProtoBranchList(size, proto_branch_list)) {
    return false;
  }
  if (proto_branch_list.magic() != ETM_BRANCH_LIST_PROTO_MAGIC) {
    PLOG(ERROR) << "not in format of branch_list.proto";
  }
  for (size_t i = 0; i < proto_branch_list.etm_data_size(); i++) {
    const proto::ETMBinary& proto_binary = proto_branch_list.etm_data(i);
    if (!AddETMBinary(proto_binary, etm_data)) {
      return false;
    }
  }
  if (proto_branch_list.has_lbr_data()) {
    AddLBRData(proto_branch_list.lbr_data(), lbr_data);
  }
  return true;
}

bool DumpBranchListFile(std::string filename) {
  ETMBinaryMap etm_data;
  LBRData lbr_data;
  auto reader = BranchListProtoReader::CreateForFile(filename);
  if (!reader || !reader->Read(etm_data, lbr_data)) {
    return false;
  }

  if (!etm_data.empty()) {
    std::vector<BinaryKey> sorted_keys;
    for (const auto& [key, _] : etm_data) {
      sorted_keys.emplace_back(key);
    }
    std::sort(sorted_keys.begin(), sorted_keys.end(),
              [](const BinaryKey& key1, const BinaryKey& key2) { return key1.path < key2.path; });
    PrintIndented(0, "etm_data:\n");
    for (size_t i = 0; i < sorted_keys.size(); ++i) {
      const auto& key = sorted_keys[i];
      const auto& binary = etm_data[key];
      PrintIndented(1, "binary[%zu].path: %s\n", i, key.path.c_str());
      PrintIndented(1, "binary[%zu].build_id: %s\n", i, key.build_id.ToString().c_str());
      PrintIndented(1, "binary[%zu].binary_type: %s\n", i, DsoTypeToString(binary.dso_type));
      if (binary.dso_type == DSO_KERNEL) {
        PrintIndented(1, "binary[%zu].kernel_start_addr: 0x%" PRIx64 "\n", i,
                      key.kernel_start_addr);
      }
      PrintIndented(1, "binary[%zu].addrs:\n", i);
      size_t addr_id = 0;
      for (const auto& [addr, branches] : binary.GetOrderedBranchMap()) {
        PrintIndented(2, "addr[%zu]: 0x%" PRIx64 "\n", addr_id++, addr);
        size_t branch_id = 0;
        for (const auto& [branch, count] : branches) {
          std::string s = "0b";
          for (auto it = branch.rbegin(); it != branch.rend(); ++it) {
            s.push_back(*it ? '1' : '0');
          }
          PrintIndented(3, "branch[%zu].branch: %s\n", branch_id, s.c_str());
          PrintIndented(3, "branch[%zu].count: %" PRIu64 "\n", branch_id, count);
          ++branch_id;
        }
      }
    }
  }
  if (!lbr_data.samples.empty()) {
    PrintIndented(0, "lbr_data:\n");
    for (size_t i = 0; i < lbr_data.samples.size(); ++i) {
      const auto& sample = lbr_data.samples[i];
      PrintIndented(1, "sample[%zu].binary_id: %u\n", i, sample.binary_id);
      PrintIndented(1, "sample[%zu].vaddr_in_file: 0x%" PRIx64 "\n", i, sample.vaddr_in_file);
      PrintIndented(1, "sample[%zu].branches:\n", i);
      for (size_t j = 0; j < sample.branches.size(); ++j) {
        const auto& branch = sample.branches[j];
        PrintIndented(2, "branch[%zu].from_binary_id: %u\n", j, branch.from_binary_id);
        PrintIndented(2, "branch[%zu].from_vaddr_in_file: 0x%" PRIx64 "\n", j,
                      branch.from_vaddr_in_file);
        PrintIndented(2, "branch[%zu].to_binary_id: %u\n", j, branch.to_binary_id);
        PrintIndented(2, "branch[%zu].to_vaddr_in_file: 0x%" PRIx64 "\n", j,
                      branch.to_vaddr_in_file);
      }
    }
    for (size_t i = 0; i < lbr_data.binaries.size(); ++i) {
      const auto& binary = lbr_data.binaries[i];
      PrintIndented(1, "binary[%zu].path: %s\n", i, binary.path.c_str());
      PrintIndented(1, "binary[%zu].build_id: %s\n", i, binary.build_id.ToString().c_str());
    }
  }
  return true;
}

}  // namespace simpleperf
