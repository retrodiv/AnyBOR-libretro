#!/usr/bin/env python3
"""Finalize one engine's relocatable Mach-O object for the single-file core.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>

The ELF/PE targets localize each engine's symbols with objcopy
(--keep-global-symbols / --redefine-sym) and bound its zero-initialized
statics with a linker script.  Darwin has neither objcopy nor linker
scripts, so this tool performs the same work on the object produced by
`ld -r`.  ld64 needs -d to turn the tentative definitions that -fcommon
produces into real definitions; the linker in Xcode 15 and later defines
them itself and refuses that option.  Either shape is accepted, and
tentative definitions that are still unresolved get storage here:

  * collect the engine's zero-initialized statics — the linker's
    __DATA,__bss and __DATA,__common sections, plus any tentative
    definition the linker left undefined — into one per-engine
    zerofill section (default __obss<build>), so a save state can skip the
    statics of the five engines that are not running,
  * define the region boundary symbols the glue's engine table uses
    (___obor_bss_begin_<build> / ___obor_bss_end_<build>),
  * localize every symbol the engine defines except its obor_* ABI, and
    rename those ABI entries with the build suffix the glue expects.

Relocations reference symbols and sections by index and neither index
changes here, so only the symbol and string tables are rebuilt; they are
appended at the end of the file and LC_SYMTAB is repointed at them.

Usage:
  python3 macho_rewrite.py --input whole.o --output obor_engine_8020.o \
      --build 8020 --section __obss8020 --abi keep.txt [--manifest m.json]
"""
import argparse
import json
import struct
import sys

MH_MAGIC_64 = 0xFEEDFACF
MH_OBJECT = 0x1
LC_SEGMENT_64 = 0x19
LC_SYMTAB = 0x2
S_ZEROFILL = 0x1
N_STAB = 0xE0
N_PEXT = 0x10
N_TYPE = 0x0E
N_EXT = 0x01
N_SECT = 0x0E
N_UNDF = 0x00
N_ABS = 0x02
SCATTERED_RELOCATION = 0x80000000

# Absolute address forms (x86_64 and arm64): the addend travels in the word.
ADDRESS_RELOCATIONS = (0, 1, 6, 7, 8)

# arm64 names a moved section from code with a page pair; an explicit addend
# record (ARM64_RELOC_ADDEND) may carry the offset ahead of either member.
PAGE_RELOCATIONS = (3, 4)
ARM64_ADDEND = 10

BSS_NAME = b'__bss'
COMMON_NAME = b'__common'
DATA_SEGMENT = b'__DATA'


class RewriteError(RuntimeError):
    pass


def align_up(value, power):
    """Align value upwards to 2**power bytes."""
    if power <= 0:
        return value
    return (value + (1 << power) - 1) // (1 << power) * (1 << power)


def field(blob):
    return blob.rstrip(b'\0')


class Section(object):
    __slots__ = ('sectname', 'segname', 'addr', 'size', 'offset', 'align',
                 'reloff', 'nreloc', 'flags', 'reserved1', 'reserved2',
                 'reserved3')

    def __init__(self, raw):
        (self.sectname, self.segname, self.addr, self.size, self.offset,
         self.align, self.reloff, self.nreloc, self.flags, self.reserved1,
         self.reserved2, self.reserved3) = struct.unpack('<16s16sQQIIIIIIII', raw)

    def pack(self):
        return struct.pack('<16s16sQQIIIIIIII', self.sectname, self.segname,
                           self.addr, self.size, self.offset, self.align,
                           self.reloff, self.nreloc, self.flags,
                           self.reserved1, self.reserved2, self.reserved3)

    @property
    def zerofill(self):
        return (self.flags & 0xFF) == S_ZEROFILL

    @property
    def title(self):
        return (field(self.segname).decode('utf-8', 'replace') + ',' +
                field(self.sectname).decode('utf-8', 'replace'))


class Symbol(object):
    __slots__ = ('strx', 'type', 'sect', 'desc', 'value', 'name')

    def __init__(self, strx, ntype, sect, desc, value, name):
        self.strx = strx
        self.type = ntype
        self.sect = sect
        self.desc = desc
        self.value = value
        self.name = name

    @property
    def defined(self):
        return (self.type & N_TYPE) == N_SECT and self.sect != 0

    @property
    def external(self):
        """Exported or imported: visible outside the object."""
        return bool(self.type & N_EXT) and not self.debug

    @property
    def undefined(self):
        """Referenced here, defined elsewhere."""
        return (self.type & N_TYPE) == N_UNDF

    @property
    def common(self):
        """A tentative definition the linker left for the final link to place.

        A Mach-O common is an undefined symbol whose n_value holds the size; a
        plain import has n_value 0.
        """
        return self.undefined and self.external and self.value > 0

    @property
    def debug(self):
        return bool(self.type & N_STAB)

    def pack(self, strx):
        return struct.pack('<IBBHQ', strx, self.type, self.sect, self.desc,
                           self.value)


class MachOObject(object):
    """A 64-bit little-endian MH_OBJECT, the output of `ld -r`."""

    def __init__(self, data):
        if len(data) < 32:
            raise RewriteError('file is too small to be a Mach-O object')
        magic = struct.unpack_from('<I', data, 0)[0]
        if magic != MH_MAGIC_64:
            raise RewriteError('not a 64-bit little-endian Mach-O file '
                               '(magic 0x%08x)' % magic)
        self.data = bytearray(data)
        (self.cputype, self.cpusubtype, self.filetype, self.ncmds,
         self.sizeofcmds, self.flags, self.reserved) = struct.unpack_from(
            '<iiIIIII', self.data, 4)
        if self.filetype != MH_OBJECT:
            raise RewriteError('expected MH_OBJECT, found filetype 0x%x' %
                               self.filetype)
        self.sections = []
        self.segments = []
        self.section_offset = None
        self.symtab_offset = None
        self.symoff = self.nsyms = self.stroff = self.strsize = 0
        self._parse()

    def _parse(self):
        offset = 32
        for _ in range(self.ncmds):
            command, size = struct.unpack_from('<II', self.data, offset)
            if size < 8 or offset + size > len(self.data):
                raise RewriteError('malformed load command at 0x%x' % offset)
            if command == LC_SEGMENT_64:
                if size < 72:
                    raise RewriteError('malformed LC_SEGMENT_64')
                nsects = struct.unpack_from('<I', self.data, offset + 64)[0]
                first = offset + 72
                if first + nsects * 80 > offset + size:
                    raise RewriteError('section headers exceed the load command')
                if self.section_offset is None:
                    self.section_offset = first
                self.segments.append(dict(
                    offset=offset, first=len(self.sections), nsects=nsects,
                    vmaddr=struct.unpack_from('<Q', self.data, offset + 24)[0],
                    vmsize=struct.unpack_from('<Q', self.data, offset + 32)[0]))
                for index in range(nsects):
                    self.sections.append(Section(
                        self.data[first + index * 80:first + (index + 1) * 80]))
            elif command == LC_SYMTAB:
                if size < 24:
                    raise RewriteError('malformed LC_SYMTAB')
                self.symtab_offset = offset
                (self.symoff, self.nsyms, self.stroff,
                 self.strsize) = struct.unpack_from('<IIII', self.data,
                                                    offset + 8)
                if self.symoff + self.nsyms * 16 > len(self.data) or \
                        self.stroff + self.strsize > len(self.data):
                    raise RewriteError('symbol or string table outside the file')
            offset += size

    def ordinal(self, name):
        for index, section in enumerate(self.sections):
            if field(section.sectname) == name:
                return index + 1
        return 0

    def read_symbols(self):
        symbols = []
        for index in range(self.nsyms):
            strx, ntype, sect, desc, value = struct.unpack_from(
                '<IBBHQ', self.data, self.symoff + index * 16)
            name = ''
            if strx < self.strsize:
                end = self.data.find(b'\0', self.stroff + strx)
                if end > 0:
                    name = self.data[self.stroff + strx:end].decode(
                        'utf-8', 'replace')
            symbols.append(Symbol(strx, ntype, sect, desc, value, name))
        return symbols

    def write_section_header(self, index):
        start = self.section_offset + index * 80
        self.data[start:start + 80] = self.sections[index].pack()

    def grow_segment(self, index):
        """Keep the segment that owns a section covering all its sections.

        Widening a zerofill section past its segment's end is what the
        linker reports as a section end address beyond the containing
        segment's end, so the segment command is extended to the farthest
        section end.  Only the virtual size changes: zerofill sections
        occupy no file space.
        """
        for segment in self.segments:
            if segment['first'] <= index < segment['first'] + segment['nsects']:
                break
        else:
            return
        farthest = segment['vmaddr']
        for section in self.sections[segment['first']:
                                     segment['first'] + segment['nsects']]:
            farthest = max(farthest, section.addr + section.size)
        if farthest > segment['vmaddr'] + segment['vmsize']:
            struct.pack_into('<Q', self.data, segment['offset'] + 32,
                             farthest - segment['vmaddr'])

    def migrate_section_relocations(self, ordinal, target, extra_base,
                                    remap=None):
        """Repoint references that address the moved section by ordinal.

        A relocatable link may address a section by number instead of by
        symbol: a local tentative definition the linker resolved inside
        __common is the common case, and the linker in Xcode 15 and later
        emits it that way for arm64.  The storage is about to move to the
        tail of the region, so every such reference names the target
        section and gains that offset.  Two shapes are accepted: an
        absolute relocation that keeps its addend in the relocated word,
        and the arm64 page pair whose addend is either an explicit
        ARM64_RELOC_ADDEND record ahead of it or zero in the instruction.
        An offset that lives in an instruction this tool does not rewrite
        is refused rather than guessed.
        """
        migrated = 0
        for index, section in enumerate(self.sections):
            if index + 1 == ordinal:
                continue
            addend_entry = None
            addend_shifted = False
            for entry in range(section.nreloc):
                offset = section.reloff + entry * 8
                if offset + 8 > len(self.data):
                    raise RewriteError('relocation entry outside the file')
                word0, word1 = struct.unpack_from('<II', self.data, offset)
                if word0 & SCATTERED_RELOCATION:
                    raise RewriteError('scattered relocations are not supported')
                pcrel = (word1 >> 24) & 1
                length = (word1 >> 25) & 3
                kind = (word1 >> 28) & 0xF
                if not (word1 >> 27) & 1 and kind == ARM64_ADDEND:
                    # Names no section: it carries the addend of the record
                    # that follows it, and one addend serves a page pair.
                    addend_entry = entry
                    addend_shifted = False
                    continue
                if (word1 >> 27) & 1 or (word1 & 0xFFFFFF) != ordinal:
                    addend_entry = None
                    addend_shifted = False
                    continue
                if kind in PAGE_RELOCATIONS:
                    if addend_entry is None or length != 2:
                        raise RewriteError(
                            'section %d is addressed by relocation type %d '
                            'without an explicit addend record in section '
                            '%d; cannot move its storage'
                            % (ordinal, kind, index + 1))
                    struct.pack_into('<I', self.data, offset + 4,
                                     (word1 & ~0xFFFFFF) | target)
                    if not addend_shifted:
                        aoff = section.reloff + addend_entry * 8
                        _, addend_word = struct.unpack_from('<II', self.data,
                                                            aoff)
                        addend = addend_word & 0xFFFFFF
                        if addend & 0x800000:
                            addend -= 1 << 24
                        adjusted = extra_base + (
                            remap(addend) if remap else addend)
                        if not -0x800000 <= adjusted < 0x800000:
                            raise RewriteError(
                                'moved reference does not fit its addend '
                                'field')
                        struct.pack_into('<I', self.data, aoff + 4,
                                         (addend_word & ~0xFFFFFF) |
                                         (adjusted & 0xFFFFFF))
                        addend_shifted = True
                    migrated += 1
                    continue
                if pcrel or kind not in ADDRESS_RELOCATIONS or \
                        addend_entry is not None:
                    raise RewriteError(
                        'section %d is addressed by relocation type %d '
                        '(pcrel %d) in section %d; cannot move its storage'
                        % (ordinal, kind, pcrel, index + 1))
                if section.zerofill:
                    raise RewriteError(
                        'section %d has no file content for the relocated '
                        'address' % (index + 1))
                size = 1 << length
                at = section.offset + (word0 & 0xFFFFFF)
                if at + size > len(self.data):
                    raise RewriteError('relocated address outside the file')
                addend = int.from_bytes(self.data[at:at + size], 'little')
                adjusted = extra_base + (remap(addend) if remap else addend)
                if adjusted >= 1 << (8 * size):
                    raise RewriteError(
                        'relocated address does not fit its field')
                self.data[at:at + size] = adjusted.to_bytes(size, 'little')
                struct.pack_into('<I', self.data, offset + 4,
                                 (word1 & ~0xFFFFFF) | target)
                migrated += 1
                addend_entry = None
        return migrated


def collect_regions(obj, report):
    """Return (target_ordinal, extra_ordinal, extra_base, extra_size).

    The engine's zero-initialized statics are the linker's __bss section plus
    the tentative-definition section __common: ld64 with -d, and the linker in
    Xcode 15 and later by default, have already turned the tentatives into
    definitions there (anything still unresolved is placed by define_commons).
    Both must end up in the engine's region; the tool moves the __common
    storage to the tail of __bss and leaves __common empty.  The tail keeps a
    16-byte alignment: a common's alignment lives in its symbol entry and
    arm64 LDR/STR fixups require the storage to keep it.
    """
    bss = obj.ordinal(BSS_NAME)
    common = obj.ordinal(COMMON_NAME)
    if bss and common:
        bss_section = obj.sections[bss - 1]
        common_section = obj.sections[common - 1]
        for section in (bss_section, common_section):
            if not section.zerofill:
                raise RewriteError('%s is not a zerofill section (flags 0x%x)'
                                   % (section.title, section.flags))
        # A common records its alignment in the high byte of n_desc, and a
        # dependency may ask for more than the sections declare; the tail has
        # to keep the strictest of them or arm64 LDR/STR fixups fail.  A
        # materialized common carries no alignment record at all, so its
        # placement is not trusted either: every moved symbol is laid out
        # again at an aligned offset and the references are remapped.
        symbols = obj.read_symbols()
        moved = sorted((s for s in symbols if s.defined and s.sect == common),
                       key=lambda s: s.value)
        alignment = max(common_section.align, 4)
        for symbol in moved:
            declared = (symbol.desc >> 8) & 0xF
            if 0 < declared <= 6:
                alignment = max(alignment, declared)
        bss_section.align = max(bss_section.align, alignment)
        base = align_up(bss_section.size, max(alignment, 4))
        # The region keeps the address the partial link gave it and that
        # address is often only 8-byte aligned, which drags every moved
        # symbol to the same residue.  Shift the block so the values stay
        # 16-byte aligned as recorded, references follow through the base.
        base += (-(bss_section.addr + base)) % 16
        layout = {}
        cursor = 0
        for position, symbol in enumerate(moved):
            if position + 1 < len(moved):
                size = moved[position + 1].value - symbol.value
            else:
                size = common_section.addr + common_section.size - symbol.value
            cursor = align_up(cursor, 4)
            layout[symbol.value - common_section.addr] = (cursor, max(size, 1))
            cursor += max(size, 1)
        # Blank storage nobody names must survive the move: the block keeps
        # its own size when the packed symbols do not fill it, so a reference
        # into an unnamed tail stays inside real storage.
        moved_bytes = max(align_up(cursor, 4), common_section.size)

        def remap(offset):
            for old, (new, size) in layout.items():
                if old <= offset < old + size:
                    return new + (offset - old)
            if not moved or offset < min(layout):
                # A reference to the block's own start (or to alignment
                # padding ahead of the first symbol) keeps its place.
                return offset
            raise RewriteError(
                'a reference at offset 0x%x of the moved section does not '
                'fall inside any of its symbols' % offset)

        migrated = obj.migrate_section_relocations(common, bss, base, remap)
        if migrated:
            report['migrated_relocations'] = (
                report.get('migrated_relocations', 0) + migrated)
        report['merged_sections'] = ['__DATA,__bss', '__DATA,__common']
        return bss, common, base, moved_bytes, remap
    if common:
        report['merged_sections'] = ['__DATA,__common']
        return common, 0, 0, 0
    if bss:
        report['merged_sections'] = ['__DATA,__bss']
        return bss, 0, 0, 0
    report['warnings'].append('no __DATA,__bss or __DATA,__common section: '
                              'this engine defines no zero-initialized statics')
    return 0, 0, 0, 0


def define_commons(obj, commons, target, report):
    """Give tentative definitions the linker left undefined real storage.

    ld64 with -d (and the linker in Xcode 15 and later by default) turn
    tentative definitions into definitions the section sweep collects.  A
    linker that does neither leaves them commons, which the final link would
    coalesce across all six engines; this places each one at the tail of the
    engine's zerofill region instead, so every engine keeps its own instance.
    A 16-byte alignment is used unconditionally: over-aligning data is always
    safe, and the region is zero-filled memory either way.
    """
    if not target:
        raise RewriteError(
            '%d tentative definitions are still unresolved and the object has '
            'no zerofill section to hold them; the partial link must define '
            'commons (pass -d on ld64)' % len(commons))
    section = obj.sections[target - 1]
    offset = section.size
    for symbol in sorted(commons, key=lambda entry: entry.name):
        size = symbol.value
        offset = align_up(offset, 4)
        symbol.type = N_SECT | N_EXT
        symbol.sect = target
        symbol.value = section.addr + offset
        offset += max(size, 1)
    section.size = align_up(offset, 4)
    section.align = max(section.align, 4)
    obj.write_section_header(target - 1)
    report['defined_commons'] = len(commons)
    report['region_bytes'] = section.size
    return len(commons)


def rewrite(data, build, section_name, abi_names, begin_symbol=None,
            end_symbol=None):
    """Return (rewritten file bytes, report dict)."""
    obj = MachOObject(data)
    abi = set(abi_names)
    report = {'build': str(build), 'section': section_name,
              'abi_symbols': sorted(abi), 'localized': 0, 'renamed': [],
              'merged_sections': [], 'boundary_symbols': [],
              'defined_commons': 0, 'region_bytes': 0, 'symbols': 0,
              'migrated_relocations': 0, 'warnings': []}
    regions = collect_regions(obj, report)
    target, extra, extra_base, extra_size = regions[:4]
    remap = regions[4] if len(regions) > 4 else None
    symbols = obj.read_symbols()

    if target:
        section = obj.sections[target - 1]
        if extra:
            previous = obj.sections[extra - 1]
            for symbol in symbols:
                if symbol.sect == extra and symbol.defined:
                    offset = symbol.value - previous.addr
                    if remap is not None:
                        offset = remap(offset)
                    symbol.value = section.addr + extra_base + offset
                    symbol.sect = target
            section.align = max(section.align, previous.align)
            previous.size = 0
            section.size = extra_base + extra_size
        name = section_name.encode('utf-8')[:16]
        section.sectname = name
        section.segname = DATA_SEGMENT[:16]
        section.flags = S_ZEROFILL
        section.offset = 0
        section.reloff = 0
        section.nreloc = 0
        report['region_bytes'] = section.size
        obj.write_section_header(target - 1)
        if extra:
            obj.write_section_header(extra - 1)

    commons = [symbol for symbol in symbols if symbol.common]
    if commons:
        define_commons(obj, commons, target, report)

    if target:
        obj.grow_segment(target - 1)

    for symbol in symbols:
        if symbol.debug or not symbol.defined:
            continue
        plain = symbol.name[1:] if symbol.name.startswith('_') else symbol.name
        if plain in abi:
            symbol.name = '_' + plain + '_' + str(build)
            report['renamed'].append(symbol.name)
        else:
            symbol.type = symbol.type & 0xFF & ~N_EXT & ~N_PEXT
            report['localized'] += 1

    if target:
        if begin_symbol is None:
            begin_symbol = '___obor_bss_begin_' + str(build)
        if end_symbol is None:
            end_symbol = '___obor_bss_end_' + str(build)
        start = obj.sections[target - 1].addr
        end = start + obj.sections[target - 1].size
        for name, value in ((begin_symbol, start), (end_symbol, end)):
            symbols.append(Symbol(0, N_SECT | N_EXT, target, 0, value, name))
            report['boundary_symbols'].append(name)

    # Rebuild the symbol and string tables; relocation data is untouched
    # because symbol indices and section ordinals are unchanged.
    table = bytearray(b'\x20')
    offsets = {}
    encoded = []
    for symbol in symbols:
        name = symbol.name
        if name not in offsets:
            offsets[name] = len(table)
            table += name.encode('utf-8') + b'\0'
        encoded.append(symbol.pack(offsets[name]))
    if len(obj.data) % 8:
        obj.data.extend(b'\0' * (8 - len(obj.data) % 8))
    symoff = len(obj.data)
    for entry in encoded:
        obj.data.extend(entry)
    stroff = len(obj.data)
    obj.data.extend(table)
    if obj.symtab_offset is None:
        raise RewriteError('object has no LC_SYMTAB: nothing to finalize')
    struct.pack_into('<IIII', obj.data, obj.symtab_offset + 8, symoff,
                     len(symbols), stroff, len(table))
    report['symbols'] = len(symbols)
    return bytes(obj.data), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--build', required=True)
    parser.add_argument('--section', required=True)
    parser.add_argument('--abi', required=True,
                        help='file listing the ABI symbols to keep exported')
    parser.add_argument('--begin-symbol')
    parser.add_argument('--end-symbol')
    parser.add_argument('--manifest')
    args = parser.parse_args()
    try:
        with open(args.input, 'rb') as handle:
            data = handle.read()
        with open(args.abi, 'r') as handle:
            abi = [line.strip() for line in handle if line.strip()]
        rewritten, report = rewrite(data, args.build, args.section, abi,
                                    args.begin_symbol, args.end_symbol)
        with open(args.output, 'wb') as handle:
            handle.write(rewritten)
        if args.manifest:
            with open(args.manifest, 'w') as handle:
                handle.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
        detail = '+'.join(report['merged_sections']) or 'nothing'
        if report['defined_commons']:
            detail += ', %d tentative definitions placed' % \
                report['defined_commons']
        if report['migrated_relocations']:
            detail += ', %d section references repointed' % \
                report['migrated_relocations']
        print('macho_rewrite: %s -> %s (%d symbols, %d localized, %d renamed, '
              'region %d bytes from %s)' %
              (args.input, args.output, report['symbols'], report['localized'],
               len(report['renamed']), report['region_bytes'], detail))
    except (RewriteError, OSError, struct.error, ValueError) as error:
        sys.exit('macho_rewrite: ' + str(error))
    return 0


if __name__ == '__main__':
    sys.exit(main())
