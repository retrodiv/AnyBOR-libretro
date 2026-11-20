# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 retrodiv <retrodiv@proton.me>
# The build uses only sources in this repository and an installed toolchain.
# macOS: `make platform=osx` is what libretro's build recipe passes for both
# Mach-O targets; tools/build.py picks x86_64 or arm64 from the compiler.
PYTHON ?= python3
platform ?= $(if $(filter Darwin,$(shell uname -s)),osx,unix)
TARGET ?= auto
DIST_DIR ?= dist
SYSTEM_DEPS ?= 0
PKG_CONFIG ?= pkg-config
SYSTEM_DEPS_FLAG = $(if $(filter 1,$(SYSTEM_DEPS)),--system-deps)

# Do not export GNU make's built-in CC=cc / CXX=g++ to a cross build.
ifeq ($(filter default undefined,$(origin CC)),)
export CC
endif
ifeq ($(filter default undefined,$(origin CXX)),)
export CXX
endif
ifeq ($(filter default undefined,$(origin AR)),)
export AR
endif
export CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
export CONFIGURE_HOST CONFIGURE_BUILD
export PKG_CONFIG

all:
	+$(PYTHON) tools/build.py --target $(TARGET) --platform $(platform) $(SYSTEM_DEPS_FLAG)

glue:
	+$(PYTHON) tools/build.py --target $(TARGET) --platform $(platform) --glue-only $(SYSTEM_DEPS_FLAG)

release deploy:
	$(PYTHON) tools/check.py --sources-only
	+$(MAKE) all
	$(PYTHON) tools/package_current.py --target $(TARGET) --platform $(platform) --dest $(DIST_DIR)

source-release:
	$(PYTHON) tools/source_release.py --dest $(DIST_DIR)

check:
	$(PYTHON) tools/check.py

check-binary:
	$(PYTHON) tools/check.py --binary $(BINARY) $(SYSTEM_DEPS_FLAG)

clean:
	rm -rf .build
	rm -f anybor_libretro.so anybor_libretro.dll anybor_libretro_android.so anybor_libretro.dylib

.PHONY: all glue release deploy source-release check check-binary clean
