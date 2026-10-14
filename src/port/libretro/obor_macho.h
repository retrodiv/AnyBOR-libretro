/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * obor_macho.h — Mach-O image introspection for the single-file core.
 *
 * The ELF and PE paths discover the module's writable segments through
 * dl_iterate_phdr() / the PE headers.  Darwin exposes neither: dyld owns the
 * load commands of the image that contains the running code, and a core
 * loaded by a frontend is always a slide-rebased dylib.  Everything both the
 * glue and an engine runtime need is therefore derived from
 * <mach-o/dyld.h> + the image's own LC_SEGMENT_64 commands:
 *
 *   - obor_macho_own_header()          the mach_header_64 of the caller's image
 *   - obor_macho_writable_segments()   snapshot ranges (writable, non-RELRO)
 *   - obor_macho_section()             a named section and its runtime range
 *
 * All helpers are static inline: the glue and each engine runtime are
 * separate translation units that must not export port symbols.
 */
#ifndef OBOR_MACHO_H
#define OBOR_MACHO_H

#include <stdint.h>
typedef void (*obor_macho_segment_cb)(uint64_t lo, uint64_t hi, void *context);
typedef int (*obor_macho_state_section_reader)(void *, uint32_t,
                                              uint64_t *, uint64_t *, int *);

/* Mach-O ABI section types, verified against the actual SDK below. These
 * contain dyld bindings, constructor tables or TLS metadata, not game bytes. */
static inline int obor_macho_process_section_type(uint32_t flags)
{
    switch (flags & 0xffU) {
    case 0x6: case 0x7: case 0x9: case 0xa: case 0xd: case 0x10:
    case 0x11: case 0x12: case 0x13: case 0x14: case 0x15: case 0x16:
        return 1;
    default: return 0;
    }
}

/* Emit maximal retained ranges, even with an unsorted/overlapping section
 * table. No allocation and no caller output before every view is validated.
 * The only reader used in production reads this loaded image's own headers. */
static inline int obor_macho_state_ranges(uint64_t begin, uint64_t end,
        uint32_t count, obor_macho_state_section_reader reader, void *sections,
        obor_macho_segment_cb callback, void *context)
{
    if (end <= begin || count > 4096 || !reader || !callback) return 0;
    for (uint32_t i = 0; i < count; ++i) {
        uint64_t lo, size; int process;
        if (!reader(sections, i, &lo, &size, &process) || size > UINT64_MAX-lo) return 0;
    }
    uint64_t cursor = begin;
    while (cursor < end) {
        uint64_t gap_end = end, skip_end = end;
        for (uint32_t i = 0; i < count; ++i) {
            uint64_t lo, size; int process;
            if (!reader(sections, i, &lo, &size, &process)) return 0;
            uint64_t hi = lo + size;
            if (!process || !size || hi <= cursor || lo >= end) continue;
            if (lo < cursor) lo = cursor;
            if (hi > end) hi = end;
            if (lo < gap_end) { gap_end = lo; skip_end = hi; }
            else if (lo == gap_end && hi > skip_end) skip_end = hi;
        }
        if (gap_end > cursor) callback(cursor, gap_end, context);
        if (gap_end == end) break;
        cursor = skip_end;
    }
    return 1;
}

#if defined(__APPLE__)

#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/mach.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if S_NON_LAZY_SYMBOL_POINTERS != 0x6 || S_LAZY_SYMBOL_POINTERS != 0x7 || \
    S_MOD_INIT_FUNC_POINTERS != 0x9 || S_MOD_TERM_FUNC_POINTERS != 0xa || \
    S_INTERPOSING != 0xd || S_LAZY_DYLIB_SYMBOL_POINTERS != 0x10 || \
    S_THREAD_LOCAL_REGULAR != 0x11 || S_THREAD_LOCAL_ZEROFILL != 0x12 || \
    S_THREAD_LOCAL_VARIABLES != 0x13 || S_THREAD_LOCAL_VARIABLE_POINTERS != 0x14 || \
    S_THREAD_LOCAL_INIT_FUNCTION_POINTERS != 0x15 || S_INIT_FUNC_OFFSETS != 0x16
#error Unsupported Mach-O process section ABI
#endif

typedef struct {
    const struct section_64 *sections;
    uint64_t slide;
} obor_macho_state_sections;
static inline int obor_macho_state_section(void *context, uint32_t index,
        uint64_t *address, uint64_t *size, int *process)
{
    const obor_macho_state_sections *view = (const obor_macho_state_sections *)context;
    const struct section_64 *section = view->sections + index;
    if (section->addr > UINT64_MAX-view->slide) return 0;
    *address = section->addr + view->slide;
    *size = section->size;
    *process = obor_macho_process_section_type(section->flags) ||
        !strncmp(section->sectname, "__dyld", sizeof(section->sectname));
    return 1;
}

/* The image (dylib/executable) that contains `probe`.
 *
 * dladdr() resolves the nearest preceding symbol, whose dli_fbase is the
 * mach_header_64 of that image.  A probe in the core's own code always
 * resolves; a NULL result means the caller asked about foreign memory. */
static inline const struct mach_header_64 *obor_macho_own_header(const void *probe)
{
    Dl_info info;
    memset(&info, 0, sizeof(info));
    if (!dladdr(probe, &info) || !info.dli_fbase)
        return NULL;
    const struct mach_header *header = (const struct mach_header *)info.dli_fbase;
    if (header->magic != MH_MAGIC_64)
        return NULL;
    return (const struct mach_header_64 *)header;
}

/* Slide applied by dyld to every vmaddr in this image. */
static inline uint64_t obor_macho_slide(const struct mach_header_64 *header)
{
    const struct load_command *command = (const struct load_command *)(header + 1);
    for (uint32_t i = 0; i < header->ncmds; i++) {
        if (command->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *segment =
                (const struct segment_command_64 *)command;
            return (uint64_t)(uintptr_t)header - (uint64_t)segment->vmaddr;
        }
        command = (const struct load_command *)((const char *)command + command->cmdsize);
    }
    return 0;
}

/* Range of the whole image: [min vmaddr, max vmaddr + vmsize). */
static inline void obor_macho_image_range(const struct mach_header_64 *header,
                                          uint64_t *lo, uint64_t *hi)
{
    *lo = 0;
    *hi = 0;
    if (!header)
        return;
    uint64_t slide = obor_macho_slide(header);
    uint64_t low = UINT64_MAX, high = 0;
    const struct load_command *command = (const struct load_command *)(header + 1);
    for (uint32_t i = 0; i < header->ncmds; i++) {
        if (command->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *segment =
                (const struct segment_command_64 *)command;
            uint64_t start = segment->vmaddr + slide;
            uint64_t end = start + segment->vmsize;
            if (start < low)
                low = start;
            if (end > high)
                high = end;
        }
        command = (const struct load_command *)((const char *)command + command->cmdsize);
    }
    if (low == UINT64_MAX || high <= low) {
        *lo = 0;
        *hi = 0;
        return;
    }
    *lo = low;
    *hi = high;
}

/* Writable, non-RELRO segments of `header`, in load order.
 *
 * Mach-O mirrors the ELF RELRO split with segment permissions: dyld drops
 * write permission from __DATA_CONST once relocations are applied, so its
 * initprot is read-only in the file and it is skipped here exactly like a
 * PT_GNU_RELRO range is on ELF.  __LINKEDIT and __PAGEZERO are read-only
 * or unmapped and therefore never selected. */
static inline int obor_macho_writable_segments(const struct mach_header_64 *header,
                                               obor_macho_segment_cb callback,
                                               void *context)
{
    if (!header)
        return 0;
    uint64_t slide = obor_macho_slide(header);
    int found = 0;
    const struct load_command *command = (const struct load_command *)(header + 1);
    for (uint32_t i = 0; i < header->ncmds; i++) {
        if (command->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *segment =
                (const struct segment_command_64 *)command;
            if ((segment->initprot & VM_PROT_WRITE) &&
                strncmp(segment->segname, "__DATA_CONST", sizeof(segment->segname)) &&
                strncmp(segment->segname, "__AUTH_CONST", sizeof(segment->segname)) &&
                strncmp(segment->segname, "__LINKEDIT", sizeof(segment->segname)) &&
                strncmp(segment->segname, "__PAGEZERO", sizeof(segment->segname))) {
                uint64_t start = segment->vmaddr + slide;
                uint64_t end = start + segment->vmsize;
                if (end > start) {
                    obor_macho_state_sections view = {
                        (const struct section_64 *)(segment + 1), slide };
                    if (!obor_macho_state_ranges(start, end, segment->nsects,
                        obor_macho_state_section, &view, callback, context)) return 0;
                    found = 1;
                }
            }
        }
        command = (const struct load_command *)((const char *)command + command->cmdsize);
    }
    return found;
}

/* Runtime range of section `segname`/`sectname` in this image.
 *
 * The Darwin build places each engine runtime's zero-initialized statics in
 * its own section (the Mach-O counterpart of the ELF linker script's
 * per-engine .obss region), so the engine region table is derived from these
 * ranges at boot instead of from linker-defined begin/end symbols. */
static inline int obor_macho_section(const struct mach_header_64 *header,
                                     const char *segname, const char *sectname,
                                     uint64_t *address, uint64_t *size)
{
    if (!header)
        return 0;
    uint64_t slide = obor_macho_slide(header);
    const struct load_command *command = (const struct load_command *)(header + 1);
    for (uint32_t i = 0; i < header->ncmds; i++) {
        if (command->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *segment =
                (const struct segment_command_64 *)command;
            const struct section_64 *section =
                (const struct section_64 *)(segment + 1);
            for (uint32_t s = 0; s < segment->nsects; s++) {
                if (!strncmp(section[s].segname, segname, sizeof(section[s].segname)) &&
                    !strncmp(section[s].sectname, sectname, sizeof(section[s].sectname))) {
                    *address = section[s].addr + slide;
                    *size = section[s].size;
                    return 1;
                }
            }
        }
        command = (const struct load_command *)((const char *)command + command->cmdsize);
    }
    return 0;
}

#endif /* __APPLE__ */

#endif /* OBOR_MACHO_H */
