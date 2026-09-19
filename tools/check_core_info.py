#!/usr/bin/env python3
"""Check the public core metadata against the maintained frontend contract.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


def read_info(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, raw = line.partition("=")
        key = key.strip()
        if not separator or not re.match(r"^[a-z_][a-z_0-9]*$", key) or key in values:
            raise RuntimeError("Invalid or duplicate core-info field: " + line)
        value = json.loads(raw.strip())
        if not isinstance(value, (str, int)):
            raise RuntimeError("Invalid core-info value: " + key)
        values[key] = value
    return values


def check_core_info(root, pin):
    expected_fields = {"core_name", "core_basename", "version", "source_date_epoch",
                       "fallback_build", "engine_repo", "engines", "deps", "transform_vm"}
    engine_fields = {"build", "commit", "date", "covers", "major", "version_major"}
    if set(pin) != expected_fields or set(pin["engine_repo"]) != {"url"}:
        raise RuntimeError("Unexpected public source metadata fields")
    if type(pin["source_date_epoch"]) is not int or pin["source_date_epoch"] < 0:
        raise RuntimeError("Invalid reproducible build timestamp")
    for engine in pin["engines"]:
        if set(engine) - engine_fields or not {"build", "commit", "date", "major"} <= set(engine):
            raise RuntimeError("Unexpected public engine metadata fields")
    basename = pin["core_basename"]
    info = read_info(root / (basename + ".info"))
    expected = {
        # The downloader shows the engine first and the project in parentheses;
        # the core name, library name and file names stay the project name.
        "display_name": "OpenBOR (AnyBOR)", "corename": pin["core_name"],
        "display_version": pin["version"], "supported_extensions": "pak|spk|txt|zip",
        "systemname": "OpenBOR", "license": "Non-commercial",
        "firmware_count": 0, "supports_no_game": "false",
        "savestate": "true", "savestate_features": "serialized",
        "cheats": "false", "libretro_saves": "false", "load_subsystem": "false",
        "single_purpose": "false", "input_descriptors": "true",
        "memory_descriptors": "true", "core_options": "true",
        "core_options_version": "2.0", "needs_fullpath": "true",
        "hw_render": "false", "disk_control": "false",
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise RuntimeError("Core metadata disagrees with the published contract: " + key)
    if not info.get("authors") or not info.get("notes") or not 0 < len(info.get("description", "")) <= 512:
        raise RuntimeError("Missing authors, runtime notes or valid core description")
    for rel in (".gitlab-ci.yml", ".github/workflows/ci.yml", "Makefile",
                "jni/Android.mk", "jni/Application.mk", "docs/PUBLISHING.md",
                "docs/ANYBOR.md", "tools/source_release.py"):
        if not (root / rel).is_file():
            raise RuntimeError("Missing publication entry point: " + rel)
    print("Core-info metadata and publication entry points: OK")
