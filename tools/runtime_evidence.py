"""Retain opt-in native test diagnostics outside disposable work directories.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re


def record_process(suite, case, result, metadata=None):
    folder = os.environ.get('ANYBOR_TEST_EVIDENCE_DIR')
    if not folder:
        return
    safe = lambda name: re.sub(r'[^A-Za-z0-9_.-]', '_', name)
    destination = Path(folder).resolve() / safe(suite) / safe(case)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'stdout.log').write_text(result.stdout, encoding='utf-8')
    (destination / 'stderr.log').write_text(result.stderr, encoding='utf-8')
    (destination / 'result.json').write_text(json.dumps(dict(
        returncode=result.returncode, metadata=metadata), indent=2) + '\n')
