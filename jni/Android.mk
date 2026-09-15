# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 retrodiv <retrodiv@proton.me>
# The portable builder produces the core; ndk-build installs it using the
# standard prebuilt-module rule expected by libretro's Android CI template.
LOCAL_PATH := $(call my-dir)
ANYBOR_SOURCE_ROOT := $(abspath $(LOCAL_PATH)/..)
ANYBOR_JNI_CORE := $(ANYBOR_SOURCE_ROOT)/.build/dist/android-arm64/anybor_libretro_android.so
ANYBOR_NDK := $(NDK_ROOT)
PYTHON ?= python3

ifneq ($(TARGET_ARCH_ABI),arm64-v8a)
  $(error AnyBOR currently supports Android arm64-v8a)
endif

include $(CLEAR_VARS)
LOCAL_MODULE := retro
LOCAL_MODULE_FILENAME := libretro
LOCAL_SRC_FILES := $(ANYBOR_JNI_CORE)
LOCAL_ALLOW_MISSING_PREBUILT := true
LOCAL_STRIP_MODULE := false
include $(PREBUILT_SHARED_LIBRARY)

.PHONY: anybor_build_current_sources
$(ANYBOR_JNI_CORE): anybor_build_current_sources

anybor_build_current_sources:
	+env -u CC -u CXX -u AR -u RANLIB -u LD -u STRIP -u OBJCOPY -u OBJDUMP \
	    ANDROID_NDK="$(ANYBOR_NDK)" OBOR_BUILD_ROOT="$(ANYBOR_SOURCE_ROOT)/.build" \
	    $(PYTHON) "$(ANYBOR_SOURCE_ROOT)/tools/build.py" --target android-arm64
