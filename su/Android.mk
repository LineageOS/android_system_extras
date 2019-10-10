LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)

LOCAL_CFLAGS := -Wall -Werror

LOCAL_SRC_FILES := su.cpp
LOCAL_SRC_FILES += \
    binder/appops-wrapper.cpp \
    binder/pm-wrapper.cpp

LOCAL_MODULE := su

LOCAL_SHARED_LIBRARIES := \
    libbinder \
    libutils

LOCAL_MODULE_PATH := $(TARGET_OUT_OPTIONAL_EXECUTABLES)

include $(BUILD_EXECUTABLE)
