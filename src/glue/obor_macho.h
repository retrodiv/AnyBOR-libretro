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

#if defined(__APPLE__)

#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/mach.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

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
typedef void (*obor_macho_segment_cb)(uint64_t lo, uint64_t hi, void *context);

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
                    callback(start, end, context);
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
