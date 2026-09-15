#!/usr/bin/env python3
"""Resolve the same target as make and package its exact build receipt.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
from pathlib import Path
import build
import release

parser = argparse.ArgumentParser()
parser.add_argument("--target", default="auto")
parser.add_argument("--platform", default="unix")
parser.add_argument("--dest", default="dist")
args = parser.parse_args()
target, spec = build.configure_target(args.target, args.platform)
release.package(target, build.BUILD_ROOT, Path(args.dest))
