"""Verify compiler-selected file ABI bindings before engine isolation.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
from macho_rewrite import MachOObject

OPERATIONS = ('fopen', 'fclose', 'open', 'close', 'opendir', 'stat',
              'remove', 'unlink', 'rmdir', 'rename', 'mkdir', 'chmod')


def symbol_sets(path, nm):
    """POSIX output is supported by GNU, LLVM and Apple's nm."""
    output = subprocess.check_output(shlex.split(str(nm)) + ['-P', str(path)],
                                     universal_newlines=True, timeout=30)
    defined, undefined = set(), set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        if len(fields[1]) == 1:
            name, kind = fields[:2]
        elif fields[0] == 'U':
            kind, name = fields[:2]
        else:
            continue
        if kind == 'U':
            undefined.add(name)
        elif kind not in ('w', 'v', '?'):
            defined.add(name)
    return defined, undefined


def path_operation(name, macho=False):
    """Classify API families, without guessing a versioned SDK symbol."""
    if macho and name.startswith('_'):
        name = name[1:]
    if name.startswith('__imp_'):
        name = name[len('__imp_'):]
    name = name.lstrip('_').split('$', 1)[0]
    return (name in OPERATIONS or
            re.match(r'^(stat|open|fopen)(32|64|32i64|64i32)$', name) is not None)


def verify_darwin_names(compiler, flags, port, output):
    """Compare native lookup strings with actual SDK-selected relocations."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source, obj = output / 'native-io-sdk.c', output / 'native-io-sdk.o'
    lines = ['#include <stdio.h>', '#include <sys/stat.h>', '#include <dirent.h>',
             '#include <unistd.h>', '#include <fcntl.h>', '#include "obor_native_io.h"']
    for name in OPERATIONS:
        lines += ['__typeof__(&{0}) obor_probe_{0} = &{0};'.format(name),
                  'const char obor_native_name_{0}[] = OBOR_NATIVE_IO_{1};'.format(name, name.upper())]
    source.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    subprocess.check_call(shlex.split(str(compiler)) + list(flags) + [
        '-std=gnu99', '-Werror', '-I', str(port), '-c', str(source), '-o', str(obj)])
    data = obj.read_bytes()
    parsed = MachOObject(data)
    symbols = parsed.read_symbols()
    undefined = {entry.name for entry in symbols if not entry.defined and entry.name}
    names = {}
    for name in OPERATIONS:
        entry = next(s for s in symbols if s.name == '_obor_native_name_' + name)
        section = parsed.sections[entry.sect - 1]
        start = section.offset + entry.value - section.addr
        end = min(section.offset + section.size, start + 256)
        if not section.offset <= start < end <= len(data):
            raise ValueError('Invalid native I/O probe string bounds')
        value, separator, unused = data[start:end].partition(b'\0')
        if not separator:
            raise ValueError('Unterminated native I/O probe string')
        native = value.decode('ascii')
        if '_' + native not in undefined:
            raise ValueError('SDK file ABI mismatch: {0} lookup {1}, declarations {2}'.format(
                name, native, sorted(undefined)))
        names[name] = native
    # The strings must be used by the actual native forwarders too. Merely
    # keeping an unused correct definition in a header would not guard a
    # later accidental dlsym(RTLD_NEXT, "stat") in obor_files.c.
    implementation = output / 'native-io-port.o'
    subprocess.check_call(shlex.split(str(compiler)) + list(flags) + [
        '-std=gnu99', '-Werror', '-I', str(port), '-c',
        str(Path(port) / 'obor_files.c'), '-o', str(implementation)])
    native_object = MachOObject(implementation.read_bytes())
    strings = set()
    for section in native_object.sections:
        if section.sectname.rstrip(b'\0') != b'__cstring':
            continue
        if section.size > 1 << 20 or section.offset + section.size > len(native_object.data):
            raise ValueError('Invalid native I/O forwarder string section')
        strings.update(bytes(native_object.data[section.offset:section.offset + section.size]).split(b'\0'))
    missing = [name for name in names.values() if name.encode('ascii') not in strings]
    if missing:
        raise ValueError('Native forwarders do not use the selected SDK ABI: ' + ', '.join(missing))
    report = dict(operations=names, sdk_imports=sorted(undefined),
                  native_execution=False, all_sdk_lookups_match=True,
                  actual_native_forwarder_object_checked=True)
    (output / 'native-io-sdk.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def audit_engine(spec, objects, archives, output):
    """Check every caller's emitted file references against the real wrappers.

    Native forwarders and the glue legitimately import libc functions. Inspect
    caller objects and the actual partial-link arguments, rather than banning
    those imports from the final shared library.
    """
    objects, output = Path(objects), Path(output)
    macho = spec['plat'] == 'darwin'
    nm = spec['nm']
    wrappers, unused = symbol_sets(objects / 'port/obor_files.o', nm)
    if macho:
        bound = wrappers
    else:
        actual = (objects / 'file-wraps.txt').read_text().split()
        configured = {entry[len('--wrap='):] for entry in actual if entry.startswith('--wrap=')}
        # A shared Makefile can list unused 32-bit-time aliases on a 64-bit
        # target. Every emitted caller reference still requires both the
        # real linker option and a definition; an unused option needs neither.
        bound = {name for name in configured if '__wrap_' + name in wrappers}
    checked, bindings = 0, set()
    excluded = {'obor_files.o', 'whole.o', 'kept.o', 'android-kept.o'}
    paths = [p for p in sorted(objects.rglob('*.o'))
             if p.name not in excluded and not p.name.startswith(('obor_engine_', 'linker-probe'))]
    paths += list(map(Path, archives))
    for path in paths:
        unused, imports = symbol_sets(path, nm)
        for name in imports:
            if not path_operation(name, macho):
                continue
            if name not in bound:
                raise ValueError('File call escapes session wrapper: {0}: {1}'.format(path.name, name))
            bindings.add(name)
        checked += 1
    if not checked or not bindings:
        raise ValueError('Empty engine file binding audit')
    report = dict(objects_and_archives_checked=checked, caller_symbols=sorted(bindings),
                  wrapper_symbols=sorted(bound), all_file_calls_bound=True,
                  checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Engine file bindings: {0} objects/archives, {1} caller symbols: OK'.format(
        checked, len(bindings)), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--flags', default='')
    parser.add_argument('--port', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_darwin_names(args.compiler, shlex.split(args.flags),
                                        args.port, args.output), indent=2))


if __name__ == '__main__':
    main()
