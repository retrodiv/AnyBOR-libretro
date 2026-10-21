"""Use native sanitizers without requesting an unavailable leak detector.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
import sys


def _options(value, required):
    kept = [item for item in value.split(':')
            if item and item.partition('=')[0] not in required]
    return ':'.join(kept + [key + '=' + setting for key, setting in required.items()])


def sanitizer_environment(base=None, *, platform=None):
    """Copy the environment, retaining ASan/UBSan and Linux leak checks.

    Apple toolchains can omit LeakSanitizer even though AddressSanitizer works.
    Leak detection is enabled on Linux hosts; other hosts keep address and UB
    checks without requesting LeakSanitizer. A supplied platform is for tests.
    """
    result = dict(os.environ if base is None else base)
    host = sys.platform if platform is None else platform
    result['ASAN_OPTIONS'] = _options(result.get('ASAN_OPTIONS', ''), {
        'detect_leaks': '1' if host.startswith('linux') else '0',
        'halt_on_error': '1',
    })
    result['UBSAN_OPTIONS'] = _options(result.get('UBSAN_OPTIONS', ''), {
        'halt_on_error': '1', 'print_stacktrace': '1',
    })
    return result
