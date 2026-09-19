#!/usr/bin/env python3
"""Read Mach-O 64-bit metadata without otool, nm or any third-party package.

Used by the builder for macOS build receipts (dynamic dependencies) and by the
public checks (file type, architecture, minimum OS version and the exported
libretro entry points) on machines that have no Apple toolchain.

Only little-endian 64-bit Mach-O images are parsed. FAT/universal containers,
big-endian images and 32-bit images are reported through 'errors' with filetype
'unknown:0' instead of crashing. A file that cannot be read as such an image
raises MachOError, a ValueError subclass, and no read ever leaves the file:
the header, load commands, symbol and string tables, export trie and code
signature regions are validated before they are touched.

Exports come from the dyld export trie (LC_DYLD_EXPORTS_TRIE, or the export
blob of LC_DYLD_INFO/_ONLY, which uses the same format) because a stripped
dylib keeps its trie but loses its symbol table. 'exports_from_trie' records
which source was used; without a usable trie 'exports' falls back to the
external defined symbols of LC_SYMTAB.

'symbols_defined_external' lists defined symbols carrying N_EXT. A linker can
localize an unexported symbol by clearing N_EXT and keeping N_PEXT; those are
listed separately in 'symbols_defined_private_external', not as undefined.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import json
import struct
import sys
from pathlib import Path

_LE64 = b'\xcf\xfa\xed\xfe'
_BE64 = b'\xfe\xed\xfa\xcf'
_LE32 = b'\xce\xfa\xed\xfe'
_BE32 = b'\xfe\xed\xfa\xce'
_FAT_BYTES = (b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca')
_MACHO64_MAGIC = '0x%08x' % struct.unpack('>I', _LE64)[0]

_HEADER_SIZE = 32
_SEGMENT_64 = 0x19
_SEGMENT_COMMAND_SIZE = 72
_SECTION_SIZE = 80
_SYMTAB = 0x02
_LOAD_DYLIB = 0x0c
_ID_DYLIB = 0x0d
_DYLIB_COMMANDS = (0x0d, 0x0c, 0x80000018, 0x8000001f)
_BUILD_VERSION = 0x32
_VERSION_MIN_COMMANDS = {0x24: 'macos', 0x25: 'ios', 0x2f: 'tvos', 0x30: 'watchos'}
_DYLD_INFO = (0x22, 0x80000022)
_EXPORTS_TRIE = 0x80000033
_CODE_SIGNATURE = 0x1d

_CPU_TYPE_X86_64 = 0x01000007
_CPU_TYPE_ARM64 = 0x0100000c
_CPU_SUBTYPE_ARM64E = 0x02
_CPU_SUBTYPE_MASK = 0x00ffffff

_CPUTYPE_NAMES = {_CPU_TYPE_X86_64: 'x86_64'}
_FILETYPES = {1: 'OBJECT', 2: 'EXECUTE', 6: 'DYLIB', 8: 'BUNDLE'}
_INSPECTED_FILETYPES = ('DYLIB', 'BUNDLE', 'OBJECT')
_PLATFORMS = {1: 'macos', 2: 'ios', 3: 'tvos', 4: 'watchos', 5: 'bridgeos', 6: 'maccatalyst',
              7: 'iossimulator', 8: 'tvossimulator', 9: 'watchossimulator', 10: 'driverkit',
              11: 'visionos', 12: 'visionossimulator'}

_N_STAB = 0xe0
_N_PEXT = 0x10
_N_TYPE = 0x0e
_N_EXT = 0x01
_N_UNDF = 0x00
_ZEROFILL_TYPES = (0x01, 0x0c, 0x12)

_EXPORT_FLAGS_REEXPORT = 0x08
_EXPORT_FLAGS_STUB_AND_RESOLVER = 0x10
_MAX_TRIE_VISITS = 1 << 17
_MAX_TRIE_NAME = 4096
_MAX_TRIE_EXPANSION = 8 << 20
_MAX_ERRORS = 64


class MachOError(ValueError):
    """Raised when a file is not a readable little-endian 64-bit Mach-O image."""


class _Malformed(Exception):
    """A single structure is malformed while the rest of the file is readable."""


class _Reader:
    """A byte string whose every read is checked against the file size."""

    def __init__(self, data, name):
        self.data = data
        self.name = name
        self.size = len(data)

    def region(self, offset, size, what):
        """Validate [offset, offset + size) inside the file before it is touched."""
        if offset < 0 or size < 0 or offset > self.size or size > self.size - offset:
            raise MachOError('%s: %s leaves the %d byte file (offset %d, size %d)'
                             % (self.name, what, self.size, offset, size))

    def unpack(self, fmt, offset, what):
        self.region(offset, struct.calcsize(fmt), what)
        return struct.unpack_from(fmt, self.data, offset)

    def contains(self, offset, size):
        return 0 <= offset and 0 <= size and offset <= self.size and size <= self.size - offset

    def cstring(self, offset, end, what):
        """Read a NUL-terminated string from [offset, end).

        Leaving the file is fatal; a string that does not fit where its own
        structure says it should is only a defect of that structure.
        """
        if not self.contains(offset, 0) or not self.contains(end, 0):
            raise MachOError('%s: %s leaves the %d byte file' % (self.name, what, self.size))
        if offset >= end:
            raise _Malformed('%s starts outside its own structure' % what)
        terminator = self.data.find(b'\0', offset, end)
        if terminator < 0:
            raise _Malformed('%s is not NUL terminated inside its own structure' % what)
        return self.data[offset:terminator].decode('utf-8', 'replace')

    def fixed(self, offset, size, what):
        """Read a fixed-width padded C string field."""
        self.region(offset, size, what)
        return self.data[offset:offset + size].rstrip(b'\0').decode('utf-8', 'replace')


def _note(errors, message):
    if len(errors) < _MAX_ERRORS:
        errors.append(message)
    elif len(errors) == _MAX_ERRORS:
        errors.append('further problems suppressed')


def _arch_name(cpu_type, cpu_subtype):
    if cpu_type == _CPU_TYPE_ARM64:
        return 'arm64e' if (cpu_subtype & _CPU_SUBTYPE_MASK) == _CPU_SUBTYPE_ARM64E else 'arm64'
    return _CPUTYPE_NAMES.get(cpu_type, 'unknown:%d' % cpu_type)


def format_version(value):
    """Render a packed (major << 16 | minor << 8 | patch) version as text."""
    major, minor, patch = value >> 16, (value >> 8) & 0xff, value & 0xff
    if patch:
        return '%d.%d.%d' % (major, minor, patch)
    return '%d.%d' % (major, minor)


def _uleb128(reader, offset, end, what):
    value = 0
    shift = 0
    while True:
        if offset >= end or offset >= reader.size:
            raise MachOError('%s: truncated ULEB128 in %s' % (reader.name, what))
        byte = reader.data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise MachOError('%s: ULEB128 overflow in %s' % (reader.name, what))
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            raise MachOError('%s: ULEB128 overflow in %s' % (reader.name, what))


def parse_export_trie(data, offset, size):
    """Return the sorted names of a dyld export trie (the loader's format).

    Each node holds a ULEB128 terminal size, the terminal fields, a byte-sized
    child count and its NUL-terminated edge strings with ULEB128 child offsets
    relative to the start of the trie. Nodes can be shared between prefixes and
    terminals can be plain, weak, absolute, thread local, stub+resolver or
    reexport entries; a reexport reports the trie name, which is the name
    clients see. Cycles and excessive expansion are refused before allocation.
    """
    reader = _Reader(data, '<trie>')
    reader.region(offset, size, 'export trie')
    if not size:
        return []
    end = offset + size
    names = set()
    pending = [(offset, '', False)]
    active = set()
    scheduled, expansion = 1, 0
    while pending:
        node, prefix, leaving = pending.pop()
        if leaving:
            active.remove(node)
            continue
        if node in active:
            raise MachOError('cycle in export trie')
        active.add(node)
        pending.append((node, '', True))
        if node < offset or node >= end:
            raise MachOError('export trie node offset %d leaves the trie' % node)
        terminal_size, cursor = _uleb128(reader, node, end, 'terminal size')
        if terminal_size:
            terminal_end = cursor + terminal_size
            if terminal_end > end:
                raise MachOError('export trie terminal leaves the trie')
            flags, cursor = _uleb128(reader, cursor, terminal_end, 'flags')
            if flags & _EXPORT_FLAGS_REEXPORT:
                _ordinal, cursor = _uleb128(reader, cursor, terminal_end, 'ordinal')
                reader.cstring(cursor, terminal_end, 'reexport name')
            elif flags & _EXPORT_FLAGS_STUB_AND_RESOLVER:
                _stub, cursor = _uleb128(reader, cursor, terminal_end, 'stub offset')
                _resolver, cursor = _uleb128(reader, cursor, terminal_end, 'resolver offset')
            else:
                _address, cursor = _uleb128(reader, cursor, terminal_end, 'address')
            if prefix:
                names.add(prefix)
            cursor = terminal_end
        if cursor >= end:
            raise MachOError('export trie is missing its child count')
        child_count = reader.data[cursor]
        cursor += 1
        for _ in range(child_count):
            edge, cursor = _trie_edge(reader, cursor, end)
            child, cursor = _uleb128(reader, cursor, end, 'child offset')
            length = len(prefix) + len(edge)
            expansion += length
            scheduled += 1
            if (not edge or length > _MAX_TRIE_NAME
                    or expansion > _MAX_TRIE_EXPANSION or scheduled > _MAX_TRIE_VISITS):
                raise MachOError('export trie exceeds bounded name expansion')
            pending.append((offset + child, prefix + edge, False))
    return sorted(names)


def _trie_edge(reader, offset, end):
    terminator = reader.data.find(b'\0', offset, end) if offset < end else -1
    if terminator < 0:
        raise MachOError('%s: unterminated export trie edge' % reader.name)
    if terminator - offset > _MAX_TRIE_NAME:
        raise MachOError('export trie edge exceeds the name limit')
    return reader.data[offset:terminator].decode('utf-8', 'replace'), terminator + 1


def _parse_dylib(reader, offset, cmdsize, what):
    """Parse LC_ID_DYLIB/LC_LOAD_DYLIB/LC_LOAD_WEAK_DYLIB/LC_REEXPORT_DYLIB."""
    if cmdsize < 24:
        raise _Malformed('%s is too small (%d bytes)' % (what, cmdsize))
    name_offset, = reader.unpack('<I', offset + 8, what)
    if name_offset < 24:
        raise _Malformed('%s name offset %d overlaps its header' % (what, name_offset))
    return reader.cstring(offset + name_offset, offset + cmdsize, what + ' name')


def _parse_build_version(reader, offset, cmdsize, result, command, what):
    if command == _BUILD_VERSION:
        if cmdsize < 24:
            raise _Malformed('%s is too small (%d bytes)' % (what, cmdsize))
        platform, min_os, sdk, tools = reader.unpack('<IIII', offset + 8, what)
        if cmdsize < 24 + tools * 8:
            raise _Malformed('%s does not hold its %d build tools' % (what, tools))
        result['platform'] = _PLATFORMS.get(platform, 'unknown:%d' % platform)
        result['min_os'] = format_version(min_os) if min_os else None
        result['sdk'] = format_version(sdk) if sdk else None
        return
    version, sdk = reader.unpack('<II', offset + 8, what)
    result['platform'] = _VERSION_MIN_COMMANDS[command]
    result['min_os'] = format_version(version)
    result['sdk'] = format_version(sdk) if sdk else None


def _parse_symtab(reader, offset, errors, result):
    """Read LC_SYMTAB: the external defined and undefined symbol names."""
    symoff, nsyms, stroff, strsize = reader.unpack('<IIII', offset + 8, 'LC_SYMTAB')
    reader.region(symoff, nsyms * 16, 'symbol table')
    reader.region(stroff, strsize, 'string table')
    external, private, undefined = set(), set(), set()
    for index in range(nsyms):
        strx, n_type, _n_sect, _n_desc, _n_value = reader.unpack('<IBBHQ', symoff + index * 16,
                                                                 'symbol %d' % index)
        if n_type & _N_STAB:
            continue
        if strx >= strsize:
            _note(errors, 'symbol %d names string %d outside the string table' % (index, strx))
            continue
        try:
            name = reader.cstring(stroff + strx, stroff + strsize, 'symbol %d name' % index)
        except _Malformed as error:
            _note(errors, str(error))
            continue
        if not name:
            continue
        if (n_type & _N_TYPE) == _N_UNDF:
            if n_type & _N_EXT:
                undefined.add(name)
        elif n_type & _N_EXT:
            external.add(name)
        elif n_type & _N_PEXT:
            private.add(name)
    result['symbols_defined_external'] = sorted(external)
    result['symbols_defined_private_external'] = sorted(private)
    result['symbols_undefined'] = sorted(undefined)


def _parse_segment(reader, offset, cmdsize, errors, result):
    """Collect the sections of one LC_SEGMENT_64 in load order."""
    segname = reader.fixed(offset + 8, 16, 'segment name')
    _vmaddr, _vmsize, fileoff, filesize, _maxprot, _initprot, nsects, _flags = reader.unpack(
        '<QQQQIIII', offset + 24, 'segment ' + segname)
    if filesize and not reader.contains(fileoff, filesize):
        _note(errors, 'segment %s contents leave the file (offset %d, size %d)'
              % (segname, fileoff, filesize))
    if nsects * _SECTION_SIZE > cmdsize - _SEGMENT_COMMAND_SIZE:
        _note(errors, 'segment %s claims %d sections that do not fit in its command'
              % (segname, nsects))
        return
    for index in range(nsects):
        section = offset + _SEGMENT_COMMAND_SIZE + index * _SECTION_SIZE
        sectname = reader.fixed(section, 16, 'section name')
        section_segment = reader.fixed(section + 16, 16, 'section segment name')
        addr, size = reader.unpack('<QQ', section + 32, 'section ' + sectname)
        file_offset, _align, _reloff, _nreloc, section_flags = reader.unpack(
            '<IIIII', section + 48, 'section ' + sectname)
        zerofill = section_flags & 0xff in _ZEROFILL_TYPES
        if not zerofill and size and not reader.contains(file_offset, size):
            _note(errors, 'section %s,%s contents leave the file (offset %d, size %d)'
                  % (section_segment, sectname, file_offset, size))
        result['sections'].append(dict(segname=section_segment, sectname=sectname, addr=addr,
                                       size=size, offset=file_offset, flags=section_flags,
                                       zerofill=zerofill))


def inspect(path):
    """Inspect one Mach-O file and return its metadata as a dictionary."""
    return inspect_bytes(Path(path).read_bytes(), str(path))


def inspect_bytes(data, name='<memory>'):
    """Inspect a 64-bit Mach-O image held in memory.

    Keys: magic, arch, filetype, cpu_type, cpu_subtype, flags, install_name,
    dependencies, platform, min_os, sdk, sections, symbols_defined_external,
    symbols_defined_private_external, symbols_undefined, exports,
    exports_from_trie, errors, size.

    Raises MachOError (a ValueError) when the image cannot be read, and never
    raises struct.error: FAT/universal containers, big-endian images and 32-bit
    images are reported through 'errors' with filetype 'unknown:0'.
    """
    reader = _Reader(data, name)
    result = dict(magic='', arch='unknown:0', filetype='unknown:0', cpu_type=0, cpu_subtype=0,
                  flags=0, install_name='', dependencies=[], platform=None, min_os=None, sdk=None,
                  sections=[], symbols_defined_external=[], symbols_defined_private_external=[],
                  symbols_undefined=[], exports=[], exports_from_trie=False, errors=[],
                  size=len(data))
    errors = result['errors']
    if len(data) < 4:
        raise MachOError('%s: %d bytes is too small to hold a Mach-O magic' % (name, len(data)))
    result['magic'] = '0x%08x' % struct.unpack_from('>I', data, 0)[0]
    raw = bytes(data[:4])
    if raw in _FAT_BYTES:
        _note(errors, 'FAT/universal container: individual architecture slices are not inspected')
        return result
    if raw == _BE64:
        _note(errors, 'big-endian 64-bit Mach-O (MH_CIGAM_64) is not supported')
        return result
    if raw in (_LE32, _BE32):
        _note(errors, '32-bit Mach-O is not supported')
        return result
    if raw != _LE64:
        raise MachOError('%s: not a Mach-O image (magic %s)' % (name, result['magic']))

    _magic, cpu_type, cpu_subtype, filetype, ncmds, sizeofcmds, flags, _reserved = reader.unpack(
        '<IiiIIIII', 0, 'Mach-O header')
    cpu_type &= 0xffffffff
    cpu_subtype &= 0xffffffff
    result['cpu_type'] = cpu_type
    result['cpu_subtype'] = cpu_subtype
    result['arch'] = _arch_name(cpu_type, cpu_subtype)
    result['filetype'] = _FILETYPES.get(filetype, 'unknown:%d' % filetype)
    result['flags'] = flags
    reader.region(_HEADER_SIZE, sizeofcmds, 'load commands')

    export_ranges = []
    offset = _HEADER_SIZE
    command_limit = _HEADER_SIZE + sizeofcmds
    for index in range(ncmds):
        if offset >= command_limit:
            _note(errors, 'load command %d starts past the load command area' % index)
            break
        command, cmdsize = reader.unpack('<II', offset, 'load command %d' % index)
        if cmdsize < 8 or cmdsize % 8 or cmdsize > command_limit - offset:
            _note(errors, 'load command %d has invalid size %d' % (index, cmdsize))
            break
        what = 'load command %d' % index
        try:
            minimum = {_SEGMENT_64: 72, _SYMTAB: 24, _BUILD_VERSION: 24,
                       _EXPORTS_TRIE: 16, _CODE_SIGNATURE: 16}.get(command, 8)
            if command in _DYLD_INFO:
                minimum = 48
            elif command in _VERSION_MIN_COMMANDS:
                minimum = 16
            if cmdsize < minimum:
                raise _Malformed('command is smaller than its required header')
            if command == _SEGMENT_64:
                _parse_segment(reader, offset, cmdsize, errors, result)
            elif command == _SYMTAB:
                _parse_symtab(reader, offset, errors, result)
            elif command in _DYLIB_COMMANDS:
                library = _parse_dylib(reader, offset, cmdsize, what)
                if command == _ID_DYLIB:
                    result['install_name'] = library
                else:
                    result['dependencies'].append(library)
            elif command == _BUILD_VERSION or command in _VERSION_MIN_COMMANDS:
                _parse_build_version(reader, offset, cmdsize, result, command, what)
            elif command == _EXPORTS_TRIE:
                dataoff, datasize = reader.unpack('<II', offset + 8, what)
                export_ranges.append((dataoff, datasize, 'LC_DYLD_EXPORTS_TRIE'))
            elif command in _DYLD_INFO:
                _rebase, _rebase_size, _bind, _bind_size, _weak, _weak_size, _lazy, _lazy_size, \
                    export_off, export_size = reader.unpack('<10I', offset + 8, what)
                if export_size:
                    export_ranges.append((export_off, export_size, 'LC_DYLD_INFO export trie'))
            elif command == _CODE_SIGNATURE:
                dataoff, datasize = reader.unpack('<II', offset + 8, what)
                reader.region(dataoff, datasize, 'code signature')
        except _Malformed as error:
            _note(errors, '%s is malformed: %s' % (what, error))
        offset += cmdsize
    result['dependencies'] = sorted(set(result['dependencies']))

    for dataoff, datasize, source in sorted(export_ranges,
                                           key=lambda item: item[2] != 'LC_DYLD_EXPORTS_TRIE'):
        try:
            names = parse_export_trie(data, dataoff, datasize)
        except (MachOError, _Malformed) as error:
            _note(errors, '%s is unusable: %s' % (source, error))
            continue
        result['exports'] = names
        result['exports_from_trie'] = True
        break
    if not result['exports_from_trie']:
        result['exports'] = list(result['symbols_defined_external'])
    return result


def render(result, path=None):
    """Render an inspection result as aligned text lines for people."""
    lines = ['%s:' % path] if path else []
    for key in ('magic', 'arch', 'filetype', 'cpu_type', 'cpu_subtype', 'flags', 'install_name',
                'dependencies', 'platform', 'min_os', 'sdk', 'size', 'exports_from_trie',
                'symbols_defined_external', 'symbols_defined_private_external',
                'symbols_undefined', 'exports', 'errors'):
        value = result[key]
        if isinstance(value, list):
            lines.append('  %s (%d):' % (key, len(value)))
            lines += ['    ' + str(item) for item in value]
        elif key in ('cpu_type', 'cpu_subtype', 'flags'):
            lines.append('  %s: 0x%x' % (key, value))
        else:
            lines.append('  %s: %s' % (key, value))
    lines.append('  sections (%d):' % len(result['sections']))
    for section in result['sections']:
        lines.append('    %-12s %-16s addr=0x%x size=%d offset=%d flags=0x%x zerofill=%s'
                     % (section['segname'], section['sectname'], section['addr'], section['size'],
                        section['offset'], section['flags'], section['zerofill']))
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--json', action='store_true',
                        help='print the inspection dictionary as JSON (one file: the dictionary, '
                             'several files: a list that carries the path)')
    parser.add_argument('paths', type=Path, nargs='+', metavar='PATH')
    args = parser.parse_args()
    results, status = [], 0
    for path in args.paths:
        try:
            result = inspect(path)
        except (MachOError, OSError) as error:
            print('%s: %s' % (path, error), file=sys.stderr)
            status = 1
            continue
        results.append((str(path), result))
        if (result['errors'] or result['magic'] != _MACHO64_MAGIC
                or result['filetype'] not in _INSPECTED_FILETYPES):
            status = 1
    if args.json:
        payload = [dict(path=path, **result) for path, result in results]
        print(json.dumps(payload[0] if len(payload) == 1 else payload, indent=2, sort_keys=True))
    else:
        for path, result in results:
            print('\n'.join(render(result, path)))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
