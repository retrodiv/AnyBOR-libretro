"""Keep each engine's zero-initialized globals in a bounded linker region.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


def write_bss_script(path, engines, *, pe=False):
    """Augment the default ELF/PE linker script without folding partials.

    No KEEP: normal dead-section collection still applies. ELF NOLOAD retains
    zero-fill storage instead of adding the multi-MiB BSS to the core file.
    PE must inherit the input BSS type and align the output section itself:
    NOLOAD produces an invalid raw size/type, and aligning only its contents
    leaves the section RVA unaligned. Wine accepts images Windows rejects.
    COMMON matters for LLD partials, which retain tentative definitions.
    """
    section = ".obss ALIGN(__section_alignment__)" if pe else ".obss (NOLOAD)"
    lines = ["SECTIONS {", "  " + section + " : { "]
    for obj in engines:
        match = re.fullmatch(r"obor_engine_(\d+)\.o", obj.name)
        if not match:
            raise ValueError("Invalid engine object name: " + obj.name)
        build = match.group(1)
        lines += ["    . = ALIGN(64);",
                  "    __obor_bss_begin_" + build + " = .;",
                  "    " + json.dumps(str(obj), ensure_ascii=False) + "(.bss .bss.* COMMON)",
                  "    __obor_bss_end_" + build + " = .;"]
    lines += ["  }"]
    engine_bss = lines[1:]
    lines = ['SECTIONS {']
    # These archives/startup objects implement the host language/OS runtime,
    # not game logic. Their mutable pointers, handlers, TLS keys, exit tables,
    # locks and exception pools must survive reset and cross-process loads.
    # Classify linked runtime archives by object provenance. Compiler-emitted
    # process metadata inside engine objects is handled separately below.
    runtime_archives, runtime_objects = RUNTIME_ARCHIVES, RUNTIME_OBJECTS
    alignment = '__section_alignment__' if pe else '64'
    lines += ['  obor_rt ALIGN(' + alignment + ') : {']
    data = ['.data', '.data.*']
    if pe:
        # MinGW COMDAT data uses '$', including C++ exception-handler state
        # and emulated TLS descriptors. It is mutable runtime storage too.
        data += ['.data$*']
    if not pe:
        # Preserve ELF's existing RELRO inputs and protections. GNU ld file
        # selectors take precedence over default wildcard assignments, so a
        # broad .data.* would otherwise steal .data.rel.ro into writable data.
        data = ['.data']
        prefix = '.data.'
        for char in 'rel.ro':
            data += [prefix, prefix + '[^' + char + ']*']
            prefix += char
    sections = ' '.join(data + ['.bss', '.bss.*', '.sdata', '.sdata.*',
                                 '.sbss', '.sbss.*'] +
                        (['.bss$*', '.sdata$*', '.sbss$*'] if pe else []) + ['COMMON'])
    # Emulated-TLS controls are compiler process metadata, even when emitted
    # alongside engine code. Their mutable TLS indexes are not game globals.
    # Explicit input-file selectors retain precedence over the default .data.*
    # rule in GNU ld; LLD honors the same rule. Match the ABI storage class,
    # never an individual TLS variable or a numerical pointer value.
    for obj in engines:
        lines += ['    ' + json.dumps(str(obj), ensure_ascii=False) +
                  '(' + ' '.join(EMULATED_TLS_INPUTS) + ')']
    for archive in runtime_archives:
        lines += ['    *' + archive + ':*(' + sections + ')']
    for obj in runtime_objects:
        lines += ['    *' + obj + '(' + sections + ')']
    lines += ['    *(obor_rt)', '  }']
    # Initialized runtime data must precede NOLOAD engine BSS. Otherwise GNU
    # ELF ld fills the intervening engine BSS with file-backed zeroes.
    lines += engine_bss
    lines += ["} INSERT BEFORE .bss;", ""]
    path.write_text("\n".join(lines), encoding="utf-8")

# Provenance shared by the linker rule and the final-image audit.
RUNTIME_ARCHIVES = ('libpthread.a', 'libwinpthread.a', 'libgcc.a', 'libgcc_eh.a',
    'libstdc++.a', 'libsupc++.a', 'libssp.a', 'libssp_nonshared.a', 'libc++abi.a', 'libc++_static.a', 'libc++.a',
    'libunwind.a', 'libclang_rt.*.a', 'libmingw32.a', 'libmingwex.a',
    'libmoldname.a', 'libmsvcrt.a', 'libucrt.a', 'libucrtbase.a')
RUNTIME_OBJECTS = ('dllcrt2.o', 'crt2.o', 'crtbegin*.o', 'crtend*.o', 'crti.o', 'crtn.o')
EMULATED_TLS_INPUTS = ('.data*__emutls_v.*', '.sdata*__emutls_v.*')


def emulated_tls_input(section):
    import fnmatch
    return any(fnmatch.fnmatchcase(section, pattern) for pattern in EMULATED_TLS_INPUTS)


def runtime_origin(origin):
    import fnmatch
    from pathlib import Path
    name = Path(origin.strip()).name
    match = re.search(r'([^/\s]+\.a)\([^)]*\)$', origin.strip())
    archive = match[1] if match else name
    return (any(fnmatch.fnmatchcase(archive, pattern) for pattern in RUNTIME_ARCHIVES) or
            any(fnmatch.fnmatchcase(name, pattern) for pattern in RUNTIME_OBJECTS))


def gnu_map_inputs(text):
    """Keep allocated input sections and their object/archive provenance."""
    if text.lstrip().startswith('VMA'):
        for line in text.splitlines():
            match = re.fullmatch(r'\s*([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)\s+\d+\s+(.+):\(([^)]+)\)',line)
            if match:
                address,size=int(match[1],16),int(match[2],16)
                if address and size: yield match[4],address,size,match[3]
        return
    pending = None
    for line in text.splitlines():
        match = re.fullmatch(r' (\.[^\s]+|COMMON)\s*(.*)', line)
        if match:
            section, rest = match.groups()
            pending = section
        elif pending and re.match(r'^\s+0x[0-9a-fA-F]+\s+', line):
            section, rest = pending, line.strip()
        else:
            pending = None
            continue
        fields = re.fullmatch(r'0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+(.+)', rest)
        if fields:
            pending = None
            address, size = int(fields[1], 16), int(fields[2], 16)
            if address and size:
                yield section, address, size, fields[3].strip()


def captured_image_ranges(image):
    """Mirror only the existing module ownership boundaries, never game bytes."""
    import struct
    if len(image) > 256 << 20:
        raise ValueError('Image exceeds the runtime audit bound')
    if image[:2] == b'MZ':
        nt, = struct.unpack_from('<I', image, 60)
        if image[nt:nt+4] != b'PE\0\0':
            raise ValueError('Invalid PE signature')
        count, = struct.unpack_from('<H', image, nt+6)
        size, = struct.unpack_from('<H', image, nt+20)
        magic, = struct.unpack_from('<H', image, nt+24)
        if magic != 0x20b or not 0 < count <= 1024:
            raise ValueError('Expected bounded PE32+ image')
        base, = struct.unpack_from('<Q', image, nt+48)
        captured, runtime = [], []
        for i in range(count):
            at = nt+24+size+i*40
            name = image[at:at+8].rstrip(b'\0')
            length, address = struct.unpack_from('<II', image, at+8)
            flags, = struct.unpack_from('<I', image, at+36)
            span = (base+address, base+address+length)
            if name == b'obor_rt': runtime.append(span)
            if flags & 0x80000000 and name not in (b'obor_rt', b'.idata', b'.tls', b'.CRT'):
                captured.append(span)
        if len(runtime) != 1:
            raise ValueError('Expected one process runtime section')
        return captured
    if image[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected little-endian ELF64 or PE32+')
    phoff, = struct.unpack_from('<Q', image, 32)
    shoff, = struct.unpack_from('<Q', image, 40)
    phsize, phcount, shsize, shcount, names = struct.unpack_from('<5H', image, 54)
    if (phsize != 56 or shsize != 64 or not 0 < phcount <= 1024 or
            not 0 < shcount <= 8192 or names >= shcount or
            phoff > len(image) or phcount*phsize > len(image)-phoff or
            shoff > len(image) or shcount*shsize > len(image)-shoff):
        raise ValueError('Unbounded or truncated ELF tables')
    strings_offset, strings_size = struct.unpack_from('<QQ', image, shoff+names*shsize+24)
    if strings_offset > len(image) or strings_size > len(image)-strings_offset:
        raise ValueError('ELF string table out of bounds')
    strings = image[strings_offset:strings_offset+strings_size]
    runtime = []
    for i in range(shcount):
        at = shoff+i*shsize
        name, = struct.unpack_from('<I', image, at)
        end = strings.find(b'\0', name)
        if end < 0: raise ValueError('Invalid section name')
        if strings[name:end] == b'obor_rt':
            address, _, length = struct.unpack_from('<QQQ', image, at+16)
            runtime.append((address, address+length))
    if len(runtime) != 1: raise ValueError('Expected one process runtime section')
    loads, excluded = [], runtime[:]
    for i in range(phcount):
        kind, flags, _, address, _, _, length, _ = struct.unpack_from('<II6Q', image, phoff+i*phsize)
        if kind == 1 and flags & 2: loads.append((address, address+length))
        if kind == 0x6474e552:
            # 4KiB is the conservative minimum of our supported ELF hosts.
            excluded.append((address & ~4095, (address+length+4095) & ~4095))
    for lo, hi in excluded:
        result = []
        for begin, end in loads:
            if hi <= begin or lo >= end: result.append((begin, end)); continue
            if begin < lo: result.append((begin, lo))
            if hi < end: result.append((hi, end))
        loads = result
    return loads


def macho_state_layout(image):
    """Bound the actual Darwin capture ranges, including the fixed segment table."""
    import struct
    if not 32 <= len(image) <= 256 << 20 or image[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('Expected bounded little-endian Mach-O64')
    count, extent = struct.unpack_from('<II', image, 16)
    if count > 4096 or extent > len(image)-32:
        raise ValueError('Unbounded Mach-O commands')
    at, segments, sections = 32, [], []
    process_types = {6, 7, 9, 10, 13, 16, 17, 18, 19, 20, 21, 22}
    for _ in range(count):
        if at+8 > 32+extent: raise ValueError('Truncated Mach-O command')
        kind, size = struct.unpack_from('<II', image, at)
        if size < 8 or size > 32+extent-at: raise ValueError('Invalid Mach-O command size')
        if kind == 0x19:
            if size < 72: raise ValueError('Truncated Mach-O segment')
            name = image[at+8:at+24].rstrip(b'\0')
            address, length = struct.unpack_from('<QQ', image, at+24)
            prot, number = struct.unpack_from('<II', image, at+60)
            if (number > 4096 or len(sections)+number > 8192 or
                    number*80 > size-72 or address+length >= 1 << 64):
                raise ValueError('Invalid Mach-O segment sections')
            if prot & 2 and name not in (b'__DATA_CONST', b'__AUTH_CONST', b'__LINKEDIT', b'__PAGEZERO'):
                segments.append((address, address+length))
            for i in range(number):
                section = at+72+i*80
                sname = image[section:section+16].rstrip(b'\0')
                begin, width = struct.unpack_from('<QQ', image, section+32)
                flags, = struct.unpack_from('<I', image, section+64)
                if begin+width >= 1 << 64: raise ValueError('Overflowed Mach-O section')
                sections.append((sname, begin, begin+width,
                                 flags & 255 in process_types or sname == b'__dyld'))
        at += size
    if at != 32+extent: raise ValueError('Unexpected trailing Mach-O command bytes')
    def subtract(ranges, holes):
        for lo, hi in holes:
            if hi <= lo: continue
            result = []
            for begin, end in ranges:
                if end <= begin: continue
                if hi <= begin or lo >= end: result.append((begin, end)); continue
                if begin < lo: result.append((begin, lo))
                if hi < end: result.append((hi, end))
            ranges = result
        return ranges
    metadata = [(lo, hi) for _, lo, hi, process in sections if process and hi > lo]
    runtime = [(lo, hi) for name, lo, hi, _ in sections if name == b'__obor_rt']
    if len(runtime) != 1: raise ValueError('Expected one Darwin process runtime section')
    captured = subtract(segments, metadata + runtime)
    engines = [(name, lo, hi) for name, lo, hi, _ in sections if name.startswith(b'__obss')]
    counts = {name.decode(): len(subtract(captured, [(lo, hi) for other, lo, hi in engines if other != name]))
              for name, _, _ in engines}
    if len(captured) > 16 or any(n > 16 for n in counts.values()):
        raise ValueError('Darwin state exceeds the fixed segment capacity')
    return dict(captured_ranges=captured, pristine_segments=len(captured),
                engine_segments=counts, excluded_loader_bytes=sum(hi-lo for lo, hi in metadata))


def audit_runtime_storage(binary, link_map):
    from pathlib import Path
    binary, link_map = Path(binary), Path(link_map)
    if link_map.stat().st_size > 64 << 20 or binary.stat().st_size > 256 << 20:
        raise ValueError('Runtime audit input exceeds its bound')
    # Apple ld64 may include literal __cstring bytes in its symbol listing.
    # Preserve undecodable bytes, including those in object paths, without
    # changing the ASCII [N] origin records used by the ownership audit.
    text = link_map.read_text(encoding='utf-8', errors='surrogateescape')
    if text.startswith('# Path:'):
        origins = re.findall(r'^\[\s*\d+\]\s+(.+)$', text, re.M)
        linked = [name for name in origins if runtime_origin(name)]
        if linked:
            raise ValueError('Static Darwin runtime storage requires explicit ownership: '+', '.join(linked))
        return dict(format='Mach-O', static_runtime_objects=0,
                    captured_runtime_bytes=0, runtime='External libSystem; no static language runtime input',
                    **macho_state_layout(binary.read_bytes()))
    captured = captured_image_ranges(binary.read_bytes())
    records, bad = [], []
    for section, address, size, origin in gnu_map_inputs(text):
        overlaps = [(max(address, lo), min(address+size, hi)) for lo, hi in captured
                    if address < hi and lo < address+size]
        if not runtime_origin(origin) and not emulated_tls_input(section):
            if '.a(' in origin and overlaps:
                raise ValueError('Unclassified mutable archive input enters the state: '+origin+' '+section)
            continue
        record = dict(section=section, address=hex(address), bytes=size,
                      origin=Path(origin).name, captured_bytes=sum(hi-lo for lo,hi in overlaps))
        records.append(record)
        if overlaps: bad.append(record)
    if not records: raise ValueError('No allocated compiler/runtime objects found in link map')
    if bad:
        raise ValueError('Process runtime storage enters the state: '+json.dumps(bad))
    return dict(format='PE' if binary.read_bytes()[:2]==b'MZ' else 'ELF',
                captured_runtime_bytes=0, checked_inputs=records)
