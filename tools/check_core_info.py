#!/usr/bin/env python3
"""Check the public core metadata against the maintained frontend contract.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from datetime import date


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
                       "fallback_build", "engine_repo", "engines", "profiles", "deps", "transform_vm"}
    engine_fields = {"build", "commit", "date", "covers", "major", "stage", "version_major"}
    revision_fields = {"upstream_commit", "upstream_date", "upstream_branch"}
    profile_fields = {"build", "engine", "covers", "major", "stage", "auto_until", "automatic", "tagged", "reconstruction"} | revision_fields
    if set(pin) != expected_fields or set(pin["engine_repo"]) != {"url"}:
        raise RuntimeError("Unexpected public source metadata fields")
    if type(pin["source_date_epoch"]) is not int or pin["source_date_epoch"] < 0:
        raise RuntimeError("Invalid reproducible build timestamp")
    # MAJOR.MINOR.PATCH as plain integers without leading zeros: the patch
    # component is what advances per published state.
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", str(pin["version"])):
        raise RuntimeError("Invalid runtime version in src/pin.json: " + str(pin["version"]))
    for engine in pin["engines"]:
        if set(engine) - engine_fields or not {"build", "commit", "date", "major"} <= set(engine):
            raise RuntimeError("Unexpected public engine metadata fields")
    for item in pin["engines"] + pin["profiles"]:
        if item.get("stage", "") not in ("", "dev", "alpha"):
            raise RuntimeError("Invalid engine release stage")
    physical = {engine["build"] for engine in pin["engines"]}
    logical = set()
    for profile in pin["profiles"]:
        if (set(profile) - profile_fields or
                not {"build", "engine", "covers", "major"} <= set(profile) or
                profile["engine"] not in physical or profile["build"] in logical or
                int(profile.get("auto_until", profile["build"])) < int(profile["build"]) or
                type(profile.get("automatic", True)) is not bool or
                type(profile.get("tagged", True)) is not bool):
            raise RuntimeError("Invalid public logical profile metadata")
        logical.add(profile["build"])
        if revision_fields & set(profile):
            if (not revision_fields <= set(profile) or
                    not isinstance(profile["upstream_commit"], str) or
                    not re.fullmatch(r"[0-9a-f]{40}", profile["upstream_commit"]) or
                    not isinstance(profile["upstream_date"], str) or
                    not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", profile["upstream_date"]) or
                    not isinstance(profile["upstream_branch"], str) or
                    not profile["upstream_branch"].strip()):
                raise RuntimeError("Invalid upstream profile provenance")
            try:
                date.fromisoformat(profile["upstream_date"])
            except ValueError as error:
                raise RuntimeError("Invalid upstream profile provenance") from error
        if "reconstruction" in profile:
            provenance = profile["reconstruction"]
            if (not isinstance(provenance, dict) or
                    set(provenance) != {"basis", "discussion", "source_commits"} or
                    not isinstance(provenance["basis"], str) or not provenance["basis"].strip() or
                    not isinstance(provenance["discussion"], str) or
                    not provenance["discussion"].startswith(("https://", "http://")) or
                    not isinstance(provenance["source_commits"], list) or
                    not provenance["source_commits"] or
                    any(not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit)
                        for commit in provenance["source_commits"])):
                raise RuntimeError("Invalid reconstructed profile provenance")
    if pin["fallback_build"] not in logical:
        raise RuntimeError("Fallback build has no logical profile")
    basename = pin["core_basename"]
    info = read_info(root / (basename + ".info"))
    expected = {
        # The downloader shows the engine first and the project in parentheses;
        # the core name, library name and file names stay the project name.
        "display_name": "OpenBOR (AnyBOR)", "corename": pin["core_name"],
        # The offered metadata names the series, never a build: the core
        # reports its own version at runtime, so this copy cannot go stale.
        "display_version": "Git", "supported_extensions": "pak|spk|txt|zip",
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
