/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include <stdint.h>
#include <unistd.h>

#include <string>

#include <gtest/gtest.h>

#include <android-base/file.h>
#include <memory_trace/MemoryTrace.h>

TEST(MemoryTraceReadTest, malloc_valid) {
  std::string line = "1234: malloc 0xabd0000 20";
  memory_trace::Entry entry{.start_ns = 1, .end_ns = 1};
  std::string error;
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::MALLOC, entry.type);
  EXPECT_EQ(1234, entry.tid);
  EXPECT_EQ(0xabd0000U, entry.ptr);
  EXPECT_EQ(20U, entry.size);
  EXPECT_EQ(0U, entry.u.align);
  EXPECT_EQ(0U, entry.start_ns);
  EXPECT_EQ(0U, entry.end_ns);

  line += " 1000 1020";
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::MALLOC, entry.type);
  EXPECT_EQ(1234, entry.tid);
  EXPECT_EQ(0xabd0000U, entry.ptr);
  EXPECT_EQ(20U, entry.size);
  EXPECT_EQ(0U, entry.u.align);
  EXPECT_EQ(1000U, entry.start_ns);
  EXPECT_EQ(1020U, entry.end_ns);
}

TEST(MemoryTraceReadTest, malloc_invalid) {
  // Missing size
  std::string line = "1234: malloc 0xabd0000";
  memory_trace::Entry entry;
  std::string error;
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read malloc data: 1234: malloc 0xabd0000", error);

  // Missing pointer and size
  line = "1234: malloc";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to process line: 1234: malloc", error);

  // Missing end time
  line = "1234: malloc 0xabd0000 10 100";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read timestamps: 1234: malloc 0xabd0000 10 100", error);
}

TEST(MemoryTraceReadTest, free_valid) {
  std::string line = "1235: free 0x5000";
  memory_trace::Entry entry{.start_ns = 1, .end_ns = 1};
  std::string error;
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::FREE, entry.type);
  EXPECT_EQ(1235, entry.tid);
  EXPECT_EQ(0x5000U, entry.ptr);
  EXPECT_EQ(0U, entry.size);
  EXPECT_EQ(0U, entry.u.align);
  EXPECT_EQ(0U, entry.start_ns);
  EXPECT_EQ(0U, entry.end_ns);

  line += " 540 2000";
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::FREE, entry.type);
  EXPECT_EQ(1235, entry.tid);
  EXPECT_EQ(0x5000U, entry.ptr);
  EXPECT_EQ(0U, entry.size);
  EXPECT_EQ(0U, entry.u.align);
  EXPECT_EQ(540U, entry.start_ns);
  EXPECT_EQ(2000U, entry.end_ns);
}

TEST(MemoryTraceReadTest, free_invalid) {
  // Missing pointer
  std::string line = "1234: free";
  memory_trace::Entry entry;
  std::string error;
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to process line: 1234: free", error);

  // Missing end time
  line = "1234: free 0x100 100";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read timestamps: 1234: free 0x100 100", error);
}

TEST(MemoryTraceReadTest, calloc_valid) {
  std::string line = "1236: calloc 0x8000 50 30";
  memory_trace::Entry entry{.start_ns = 1, .end_ns = 1};
  std::string error;
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::CALLOC, entry.type);
  EXPECT_EQ(1236, entry.tid);
  EXPECT_EQ(0x8000U, entry.ptr);
  EXPECT_EQ(30U, entry.size);
  EXPECT_EQ(50U, entry.u.n_elements);
  EXPECT_EQ(0U, entry.start_ns);
  EXPECT_EQ(0U, entry.end_ns);

  line += " 700 1000";
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::CALLOC, entry.type);
  EXPECT_EQ(1236, entry.tid);
  EXPECT_EQ(0x8000U, entry.ptr);
  EXPECT_EQ(30U, entry.size);
  EXPECT_EQ(50U, entry.u.n_elements);
  EXPECT_EQ(700U, entry.start_ns);
  EXPECT_EQ(1000U, entry.end_ns);
}

TEST(MemoryTraceReadTest, calloc_invalid) {
  // Missing number of elements
  std::string line = "1236: calloc 0x8000 50";
  memory_trace::Entry entry;
  std::string error;
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read calloc data: 1236: calloc 0x8000 50", error);

  // Missing size and number of elements
  line = "1236: calloc 0x8000";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read calloc data: 1236: calloc 0x8000", error);

  // Missing pointer, size and number of elements
  line = "1236: calloc";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to process line: 1236: calloc", error);

  // Missing end time
  line = "1236: calloc 0x8000 50 20 100";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read timestamps: 1236: calloc 0x8000 50 20 100", error);
}

TEST(MemoryTraceReadTest, realloc_valid) {
  std::string line = "1237: realloc 0x9000 0x4000 80";
  memory_trace::Entry entry{.start_ns = 1, .end_ns = 1};
  std::string error;
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::REALLOC, entry.type);
  EXPECT_EQ(1237, entry.tid);
  EXPECT_EQ(0x9000U, entry.ptr);
  EXPECT_EQ(80U, entry.size);
  EXPECT_EQ(0x4000U, entry.u.old_ptr);
  EXPECT_EQ(0U, entry.start_ns);
  EXPECT_EQ(0U, entry.end_ns);

  line += " 3999 10020";
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::REALLOC, entry.type);
  EXPECT_EQ(1237, entry.tid);
  EXPECT_EQ(0x9000U, entry.ptr);
  EXPECT_EQ(80U, entry.size);
  EXPECT_EQ(0x4000U, entry.u.old_ptr);
  EXPECT_EQ(3999U, entry.start_ns);
  EXPECT_EQ(10020U, entry.end_ns);
}

TEST(MemoryTraceReadTest, realloc_invalid) {
  // Missing size
  std::string line = "1237: realloc 0x9000 0x4000";
  memory_trace::Entry entry;
  std::string error;
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read realloc data: 1237: realloc 0x9000 0x4000", error);

  // Missing size and old pointer
  line = "1237: realloc 0x9000";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read realloc data: 1237: realloc 0x9000", error);

  // Missing new pointer, size and old pointer
  line = "1237: realloc";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to process line: 1237: realloc", error);

  // Missing end time
  line = "1237: realloc 0x9000 0x4000 10 500";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read timestamps: 1237: realloc 0x9000 0x4000 10 500", error);
}

TEST(MemoryTraceReadTest, memalign_valid) {
  std::string line = "1238: memalign 0xa000 16 89";
  memory_trace::Entry entry{.start_ns = 1, .end_ns = 1};
  std::string error;
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::MEMALIGN, entry.type);
  EXPECT_EQ(1238, entry.tid);
  EXPECT_EQ(0xa000U, entry.ptr);
  EXPECT_EQ(89U, entry.size);
  EXPECT_EQ(16U, entry.u.align);
  EXPECT_EQ(0U, entry.start_ns);
  EXPECT_EQ(0U, entry.end_ns);

  line += " 900 1000";
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::MEMALIGN, entry.type);
  EXPECT_EQ(1238, entry.tid);
  EXPECT_EQ(0xa000U, entry.ptr);
  EXPECT_EQ(89U, entry.size);
  EXPECT_EQ(16U, entry.u.align);
  EXPECT_EQ(900U, entry.start_ns);
  EXPECT_EQ(1000U, entry.end_ns);
}

TEST(MemoryTraceReadTest, memalign_invalid) {
  // Missing size
  std::string line = "1238: memalign 0xa000 16";
  memory_trace::Entry entry;
  std::string error;
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read memalign data: 1238: memalign 0xa000 16", error);

  // Missing alignment and size
  line = "1238: memalign 0xa000";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read memalign data: 1238: memalign 0xa000", error);

  // Missing pointer, alignment and size
  line = "1238: memalign";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to process line: 1238: memalign", error);

  // Missing end time
  line = "1238: memalign 0xa000 16 10 800";
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to read timestamps: 1238: memalign 0xa000 16 10 800", error);
}

TEST(MemoryTraceReadTest, thread_done_valid) {
  std::string line = "1239: thread_done 0x0";
  memory_trace::Entry entry{.start_ns = 1, .end_ns = 1};
  std::string error;
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::THREAD_DONE, entry.type);
  EXPECT_EQ(1239, entry.tid);
  EXPECT_EQ(0U, entry.ptr);
  EXPECT_EQ(0U, entry.size);
  EXPECT_EQ(0U, entry.u.old_ptr);
  EXPECT_EQ(0U, entry.start_ns);
  EXPECT_EQ(0U, entry.end_ns);

  line += " 290";
  ASSERT_TRUE(memory_trace::FillInEntryFromString(line, entry, error)) << error;
  EXPECT_EQ(memory_trace::THREAD_DONE, entry.type);
  EXPECT_EQ(1239, entry.tid);
  EXPECT_EQ(0U, entry.ptr);
  EXPECT_EQ(0U, entry.size);
  EXPECT_EQ(0U, entry.u.old_ptr);
  EXPECT_EQ(0U, entry.start_ns);
  EXPECT_EQ(290U, entry.end_ns);
}

TEST(MemoryTraceReadTest, thread_done_invalid) {
  // Missing pointer
  std::string line = "1240: thread_done";
  memory_trace::Entry entry;
  std::string error;
  EXPECT_FALSE(memory_trace::FillInEntryFromString(line, entry, error));
  EXPECT_EQ("Failed to process line: 1240: thread_done", error);
}

class MemoryTraceOutputTest : public ::testing::Test {
 protected:
  void SetUp() override {
    tmp_file_ = new TemporaryFile();
    ASSERT_TRUE(tmp_file_->fd != -1);
  }

  void TearDown() override { delete tmp_file_; }

  void WriteAndReadString(const memory_trace::Entry& entry, std::string& str) {
    EXPECT_EQ(lseek(tmp_file_->fd, 0, SEEK_SET), 0);
    EXPECT_TRUE(memory_trace::WriteEntryToFd(tmp_file_->fd, entry));
    EXPECT_EQ(lseek(tmp_file_->fd, 0, SEEK_SET), 0);
    EXPECT_TRUE(android::base::ReadFdToString(tmp_file_->fd, &str));
  }

  std::string WriteAndGetString(const memory_trace::Entry& entry) {
    std::string str;
    WriteAndReadString(entry, str);
    return str;
  }

  void VerifyEntry(const memory_trace::Entry& entry, const std::string expected) {
    EXPECT_EQ(expected, memory_trace::CreateStringFromEntry(entry));
    // The WriteEntryToFd always appends a newline, but string creation doesn't.
    EXPECT_EQ(expected + "\n", WriteAndGetString(entry));
  }

  TemporaryFile* tmp_file_ = nullptr;
};

TEST_F(MemoryTraceOutputTest, malloc_output) {
  memory_trace::Entry entry{.tid = 123, .type = memory_trace::MALLOC, .ptr = 0x123, .size = 50};
  VerifyEntry(entry, "123: malloc 0x123 50");

  entry.start_ns = 10;
  entry.end_ns = 200;
  VerifyEntry(entry, "123: malloc 0x123 50 10 200");
}

TEST_F(MemoryTraceOutputTest, calloc_output) {
  memory_trace::Entry entry{
      .tid = 123, .type = memory_trace::CALLOC, .ptr = 0x123, .size = 200, .u.n_elements = 400};
  VerifyEntry(entry, "123: calloc 0x123 400 200");

  entry.start_ns = 15;
  entry.end_ns = 315;
  VerifyEntry(entry, "123: calloc 0x123 400 200 15 315");
}

TEST_F(MemoryTraceOutputTest, memalign_output) {
  memory_trace::Entry entry{
      .tid = 123, .type = memory_trace::MEMALIGN, .ptr = 0x123, .size = 1024, .u.align = 0x10};
  VerifyEntry(entry, "123: memalign 0x123 16 1024");

  entry.start_ns = 23;
  entry.end_ns = 289;
  VerifyEntry(entry, "123: memalign 0x123 16 1024 23 289");
}

TEST_F(MemoryTraceOutputTest, realloc_output) {
  memory_trace::Entry entry{
      .tid = 123, .type = memory_trace::REALLOC, .ptr = 0x123, .size = 300, .u.old_ptr = 0x125};
  VerifyEntry(entry, "123: realloc 0x123 0x125 300");

  entry.start_ns = 45;
  entry.end_ns = 1000;
  VerifyEntry(entry, "123: realloc 0x123 0x125 300 45 1000");
}

TEST_F(MemoryTraceOutputTest, free_output) {
  memory_trace::Entry entry{.tid = 123, .type = memory_trace::FREE, .ptr = 0x123};
  VerifyEntry(entry, "123: free 0x123");

  entry.start_ns = 60;
  entry.end_ns = 2000;
  VerifyEntry(entry, "123: free 0x123 60 2000");
}

TEST_F(MemoryTraceOutputTest, thread_done_output) {
  memory_trace::Entry entry{.tid = 123, .type = memory_trace::THREAD_DONE};
  VerifyEntry(entry, "123: thread_done 0x0");

  entry.start_ns = 0;
  entry.end_ns = 2500;
  VerifyEntry(entry, "123: thread_done 0x0 2500");
}
