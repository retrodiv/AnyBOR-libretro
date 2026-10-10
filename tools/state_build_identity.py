"""Stamp exact linked layout identity before embedding/signing.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
from pathlib import Path

MARKER = b'AnyBOR-state-build-identity-v1'.ljust(32, b'\0')
MAX_BINARY = 256 << 20


def _read(path):
    path = Path(path)
    if not 64 <= path.stat().st_size <= MAX_BINARY:
        raise ValueError('Binary identity input outside size bound')
    data = path.read_bytes()
    at = data.find(MARKER)
    if at < 0 or data.find(MARKER, at + 1) >= 0 or at + 64 > len(data):
        raise ValueError('Missing, duplicate or truncated binary identity slot')
    return data, at + len(MARKER)


def stamp(path, identity=None):
    """Require an unstamped image; return its 32-byte linked-image identity.

    The optional identity stamps a corresponding unstripped debug copy with
    the same identity as its stripped runtime image. Callers must establish
    that pairing; this is build metadata, not authentication of untrusted data.
    """
    data, offset = _read(path)
    if any(data[offset:offset + 32]):
        raise ValueError('Binary identity slot already filled')
    if identity is None:
        identity = hashlib.sha256(data).digest()
    if not isinstance(identity, bytes) or len(identity) != 32 or not any(identity):
        raise ValueError('Invalid binary identity')
    with Path(path).open('r+b') as stream:
        stream.seek(offset)
        if stream.write(identity) != 32:
            raise OSError('Incomplete binary identity write')
    actual, actual_offset = _read(path)
    if actual_offset != offset or actual[:offset] != data[:offset] or \
            actual[offset + 32:] != data[offset + 32:] or \
            actual[offset:offset + 32] != identity:
        raise OSError('Binary changed while stamping its identity')
    return identity
