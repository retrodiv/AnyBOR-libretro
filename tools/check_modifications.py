#!/usr/bin/env python3
"""Validate the public change record from the distributed tree alone.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
import release


def check_modifications(root, pin):
    documents = [root / "MODIFICATIONS.md"]
    catalogue = documents[0].read_text(encoding="utf-8")
    topics = {line[3:].lower().replace(" ", "-")
              for line in catalogue.splitlines() if line.startswith("## ")}
    if any((root / "docs").rglob("*.patch")):
        raise RuntimeError("Unexpected diff payload in public documentation")
    for eng in pin["engines"]:
        directory = root / "src/engines" / eng["build"]
        manifest = release.read_json(directory / "ANYBOR-SOURCE.json")
        if manifest.get("schema") != 3:
            raise RuntimeError("Unsupported modification inventory schema")
        record = root / manifest["modification_record"]
        documents.append(record)
        text = record.read_text(encoding="utf-8")
        if eng["commit"] not in text:
            raise RuntimeError("Modification record baseline mismatch: " + str(record))
        allowed = {"schema", "build", "repository", "commit", "files", "record_date",
                   "modification_record", "omitted_upstream_files", "selection"}
        if set(manifest) != allowed:
            raise RuntimeError("Unexpected modification inventory fields")
        if manifest["build"] != eng["build"] or manifest["commit"] != eng["commit"]:
            raise RuntimeError("Modification inventory baseline mismatch")
        files = manifest["files"]
        if set(files) & set(manifest["omitted_upstream_files"]):
            raise RuntimeError("Retained engine file also marked omitted")
        recorded = set(re.findall(r"\[`([^`]+)`\]\(../../src/engines/" +
                                  eng["build"] + r"/[^)]+\)", text))
        expected = {rel for rel, data in files.items() if data["modified"]}
        if recorded != expected:
            raise RuntimeError("Modification inventory coverage mismatch: " + eng["build"])
        for rel, data in files.items():
            changed = data["upstream_sha256"] != data["distributed_sha256"]
            if changed != data["modified"]:
                raise RuntimeError("Incorrect modification flag: " + rel)
            allowed = {"upstream_sha256", "distributed_sha256", "modified", "topics",
                       "summary", "origin"}
            if set(data) - allowed:
                raise RuntimeError("Unexpected file attribution fields: " + rel)
            references = data.get("topics", [])
            if references != sorted(set(references)) or set(references) - topics:
                raise RuntimeError("Unknown or duplicate modification topic: " + rel)
            if not changed:
                continue
            if not data.get("summary") or not (references or data.get("origin")):
                raise RuntimeError("Unexplained engine change: " + rel)
            path = directory / rel
            if data["upstream_sha256"] is not None and path.suffix in (".c", ".h") and rel != "version.h":
                notice = path.read_bytes().split(b" */", 1)[0].decode("utf-8")
                if not notice.startswith("/* AnyBOR modification record: ") or (
                        "MODIFICATIONS.md" not in notice or
                        manifest["modification_record"] not in notice):
                    raise RuntimeError("Missing engine modification notice: " + rel)
                if ("(original contributions)" not in notice or
                        "These contributions are licensed under BSD-3-Clause" not in notice or
                        "Upstream code retains its original license and notices." not in notice):
                    raise RuntimeError("Missing contribution license scope: " + rel)
    for document in documents:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("mailto:"):
                continue
            rel, _, fragment = target.partition("#")
            path = (document.parent / rel).resolve() if rel else document
            if not path.exists():
                raise RuntimeError("Broken modification citation in " + str(document) + ": " + target)
            if fragment and path.suffix == ".md":
                headings = {re.sub(r"[^\w\- ]", "", line.lstrip("# ").strip()).lower().replace(" ", "-")
                            for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")}
                if fragment not in headings:
                    raise RuntimeError("Broken modification anchor: " + target)
    print("Modification inventories, modification explanations, source notices and citations: OK")
