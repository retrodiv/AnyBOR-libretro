/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR save states.
 *
 * A state is a lossless image of the engine world:
 *   - the core module's writable PT_LOAD segments, excluding inactive
 *     engines' linker-delimited BSS (.data + active .bss: every
 *     engine global, the port layer's statics, dlmalloc's bookkeeping and
 *     libco's current-thread pointer)
 *   - the live dlmalloc chunks plus the complete allocator metadata needed
 *     to reconstruct the snapshot arena (obor_alloc.c)
 *
 * The arena lives at a fixed VA, so arena-internal pointers never relocate.
 * Pointers into the module image (function pointers, string literals) are
 * rebased on cross-session loads by scanning for values inside the saved
 * image span. The module image sits in high VA space, outside the range
 * used by integer values.
 *
 * OS handles are the only things bytes can't capture:
 *   - pak file descriptors: obor_packfile_fixup() (patched into packfile.c
 *     per era) revalidates each slot via fstat identity and reopens if stale
 *   - the main/cache PAK descriptors and log FILE*s: retain this session's
 *     live resources across the module restore
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE /* dl_iterate_phdr */
#endif

#include "libretroport.h"
#include "obor_abi.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "obor_runtime.h"
#include "obor_write_watch.h"
#include "obor_snapshot_cache.h"

#if defined(_WIN32)
#include <windows.h>
/* MinGW's stack protector guard lives in the module's writable data.
 * It belongs to the current process, not to the serialized game. */
extern uintptr_t __stack_chk_guard;
#elif defined(__APPLE__)
#include <unistd.h>
/* Mach-O: the writable ranges come from this image's own load commands. */
#include "obor_macho.h"
#else
#include <link.h>
#include <unistd.h>
#endif

static int collect_segments(void);

#define OBS_MAGIC 0x3153424FU /* "OBS1" */
#define OBS_VERSION 3U

/* Snapshots omit inactive engines' BSS. The heap precedes the variable-length
 * stack slice, keeping its offset stable for incremental dirty-page copies. */

/* serialize_size is a ceiling the frontend scans EVERY frame when rewind is
 * on, so it must hug reality: only the live stack slice (not the 16 MB
 * region) and a measured-heap-based bound (no pak-size padding). */
#define OBOR_STACK_BUDGET (4ULL << 20)
#define OBOR_REWIND_COMPACT_CAP (160ULL << 20)
#if defined(__aarch64__) || defined(__arm__)
#define OBOR_STACK_HEAD (16ULL * 1024) /* cothread context page */
#else
#define OBOR_STACK_HEAD 4096ULL /* cothread context page */
#endif

#ifndef OBOR_ENGINE_BUILD
#define OBOR_ENGINE_BUILD 0
#endif

/* obor_alloc.c — the arena starts with a guard page + the 16 MB stack
 * region; the dlmalloc heap begins right after the stack region. */
char *obor_arena_base(void);
size_t obor_arena_used(void);
int obor_arena_grow_to(size_t used);
void obor_arena_stats(size_t *live, size_t *free_bytes, size_t *top_free);
uint64_t obor_heap_sparse_size(void);
int obor_heap_owned_layout(uint64_t *prefix, uint64_t *suffix,
                           uint64_t *suffix_length);
uint64_t obor_heap_sparse_write(void *destination, uint64_t capacity);
int obor_heap_sparse_validate(const void *source, uint64_t length,
                              uint64_t arena_used);
int obor_heap_sparse_restore(const void *source, uint64_t length,
                             uint64_t arena_used);

static uint64_t heap_lo(void)
{
    return (uint64_t)(uintptr_t)(obor_stack_ptr() + obor_stack_size());
}

static uint64_t heap_used(void)
{
    uint64_t total = obor_arena_used();
    uint64_t pre = heap_lo() - (uint64_t)(uintptr_t)obor_arena_base();
    return total > pre ? total - pre : 0;
}

/* ------------------------------------------------ per-game peak memory --
 * The size bound must never grow mid-session, but level loads grow the heap
 * after boot. Remember each game's observed peak in its absolute save
 * directory (serialization runs with the frontend's cwd) and fold it into next
 * session's bound: self-calibrating after the first full play. */

static char g_peak_dir[4096];
static uint64_t g_peak_written;
static uint32_t g_profile_build;

int obor_state_set_save_dir(const char *dir, uint32_t profile_build)
{
    if (!dir || !dir[0] || !profile_build)
        return 0;
    g_profile_build = profile_build;
    int n = snprintf(g_peak_dir, sizeof(g_peak_dir), "%s/%d/Saves",
                     dir, (int)g_profile_build);
    g_peak_written = 0;
    return n >= 0 && (size_t)n < sizeof(g_peak_dir);
}

static void peak_path(char *out, size_t n)
{
    const char *base = strrchr(packfile, '/');
#ifdef _WIN32
    const char *b2 = strrchr(packfile, '\\');
    if (!base || (b2 && b2 > base))
        base = b2;
#endif
    snprintf(out, n, "%s/.obor_peak_sparse_v2_%s.txt", g_peak_dir,
             base ? base + 1 : packfile);
}

static uint64_t peak_read(void)
{
    char p[sizeof(g_peak_dir) + MAX_FILENAME_LEN + 32];
    peak_path(p, sizeof(p));
    FILE *f = fopen(p, "rt");
    if (!f)
        return 0;
    unsigned long long v = 0;
    if (fscanf(f, "%llu", &v) != 1)
        v = 0;
    fclose(f);
    return v <= OBOR_ARENA_MAX_SZ ? v : 0;
}

static void peak_update(uint64_t heap_now)
{
    if (!g_peak_written)
        g_peak_written = peak_read();
    if (heap_now <= g_peak_written + g_peak_written / 16)
        return;
    char p[sizeof(g_peak_dir) + MAX_FILENAME_LEN + 32];
    peak_path(p, sizeof(p));
    FILE *f = fopen(p, "wt");
    if (f) {
        fprintf(f, "%llu\n", (unsigned long long)heap_now);
        fclose(f);
        g_peak_written = heap_now;
    }
}

/* patched into packfile.c per era; weak so an unpatched era still links */
#if defined(_WIN32)
/* mingw supports weak in practice via gcc attribute on ELF only; use a
 * dllexport-free plain extern and provide a fallback default instead. */
int obor_packfile_fixup(const char *pakpath);
#else
int obor_packfile_fixup(const char *pakpath) __attribute__((weak));
#endif

#ifdef OBOR_HAS_MOVIE_PLAYBACK
void obor_packfile_suspend(void);
void obor_webm_state_suspend(void);
void obor_webm_state_resume(void);
#endif
void *obor_frontend_context(void);
void obor_frontend_context_restore(void *context);

/* engine log handles (globals in utils.c across eras) */
extern FILE *openborLog __attribute__((weak));
extern FILE *scriptLog __attribute__((weak));

/* Made engine-local globals by the resource-lifecycle patch. These refer
 * to this process's main PAK and cache handles, never to a saved session. */
extern int pakfd, real_pakfd;

#define MAX_SEGS 16

typedef struct {
    uint64_t vaddr;
    uint64_t size;
} seg_t;

static seg_t g_segs[MAX_SEGS];
static int g_nsegs;
static uint64_t g_image_lo, g_image_hi;
static uint64_t g_boot_id;
static uint32_t g_size_bound; /* monotonic capacity within this content run */
static obor_engine_region g_regions[OBOR_MAX_ENGINE_REGIONS];
static uint32_t g_region_count;
static int g_segments_failed;
static uint64_t g_full_segment_bytes;

int obor_state_set_regions(const obor_boot_info *info)
{
    if (!info->engine_regions || !info->engine_region_count ||
        info->engine_region_count > OBOR_MAX_ENGINE_REGIONS)
        return 0;
    uint64_t previous_end = 0;
    unsigned own = 0;
    for (uint32_t i = 0; i < info->engine_region_count; ++i) {
        const obor_engine_region *r = &info->engine_regions[i];
        if (!r->begin || r->begin < previous_end || r->end <= r->begin)
            return 0;
        previous_end = r->end;
        if (r->engine_build == OBOR_ENGINE_BUILD)
            ++own;
    }
    if (own != 1)
        return 0;
    memcpy(g_regions, info->engine_regions,
           info->engine_region_count * sizeof(g_regions[0]));
    g_region_count = info->engine_region_count;
    g_nsegs = 0;
    g_segments_failed = 0;
    g_full_segment_bytes = 0;
    return 1;
}

/* ---------------------------------------------------- segment discovery */

static void push_raw_seg(uint64_t lo, uint64_t hi)
{
    if (hi <= lo)
        return;
    if (g_nsegs == MAX_SEGS) {
        g_segments_failed = 1;
        return;
    }
    g_segs[g_nsegs].vaddr = lo;
    g_segs[g_nsegs++].size = hi - lo;
}

static void push_engine_seg(uint64_t lo, uint64_t hi)
{
    if (hi <= lo)
        return;
    g_full_segment_bytes += hi - lo;
    /* All ranges are ordered, disjoint and supplied by our own linker.
     * Leave the active engine, shared glue and initialized data unchanged.
     * Inactive engines are never run in this loaded world; a build switch
     * goes through pristine_restore, not through a state from another era. */
    for (uint32_t i = 0; i < g_region_count && lo < hi; ++i) {
        const obor_engine_region *r = &g_regions[i];
        if (r->engine_build == OBOR_ENGINE_BUILD || r->end <= lo || r->begin >= hi)
            continue;
        if (r->begin > lo)
            push_raw_seg(lo, r->begin);
        lo = r->end;
    }
    push_raw_seg(lo, hi);
}

static void push_seg(uint64_t lo, uint64_t hi)
{
    uintptr_t runtime_lo, runtime_hi;
    obor_runtime_bounds(&runtime_lo, &runtime_hi);
    if (runtime_hi > runtime_lo && runtime_lo < hi && runtime_hi > lo) {
        if (runtime_lo > lo) push_engine_seg(lo, runtime_lo);
        if (runtime_hi < hi) push_engine_seg(runtime_hi, hi);
    } else push_engine_seg(lo, hi);
}

#if defined(_WIN32)

static int collect_segments(void)
{
    if (!g_region_count || g_segments_failed)
        return 0;
    if (g_nsegs)
        return 1;
    HMODULE mod = NULL;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                                GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            (LPCSTR)&collect_segments, &mod))
        return 0;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)mod;
    const IMAGE_NT_HEADERS *nt =
        (const IMAGE_NT_HEADERS *)((const char *)mod + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    g_image_lo = (uint64_t)(uintptr_t)mod;
    g_image_hi = g_image_lo + nt->OptionalHeader.SizeOfImage;
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; i++) {
        if (!(sec[i].Characteristics & IMAGE_SCN_MEM_WRITE))
            continue;
        /* the IAT is rebound at every load — constant afterwards, and
         * restoring a stale one cross-session would wreck imports */
        if (memcmp(sec[i].Name, ".idata", 6) == 0)
            continue;
        uint64_t va = g_image_lo + sec[i].VirtualAddress;
        uint64_t sz = sec[i].Misc.VirtualSize;
        if (memcmp(sec[i].Name, ".bss", 4) == 0) {
            /* MinGW dllcrt2.o owns the first 32 bytes of .bss: its on-exit
             * table and attachment flag. These point into the current
             * process's CRT heap and must never enter a savestate. */
            if (sz <= 32)
                continue;
            va += 32;
            sz -= 32;
        }
        push_seg(va, va + sz);
    }
    return g_nsegs > 0 && !g_segments_failed;
}

#elif defined(__APPLE__)

/* Darwin: dyld slides the whole image and applies relocations before our
 * constructors run, so the snapshot ranges are read straight from the
 * mach_header_64 of the image that contains this code.  __DATA_CONST is
 * already read-only at that point (the Mach-O equivalent of PT_GNU_RELRO)
 * and is excluded by the segment permissions, exactly like the ELF path.
 * There is no fixed image address on Darwin: states are rebased on load by
 * rebase_range(), as on Android. */
static void macho_seg_cb(uint64_t lo, uint64_t hi, void *context)
{
    (void)context;
    push_seg(lo, hi);
}

static int collect_segments(void)
{
    if (!g_region_count || g_segments_failed)
        return 0;
    if (g_nsegs)
        return 1;
    const struct mach_header_64 *header =
        obor_macho_own_header((const void *)&collect_segments);
    if (!header) {
        g_segments_failed = 1;
        return 0;
    }
    obor_macho_image_range(header, &g_image_lo, &g_image_hi);
    obor_macho_writable_segments(header, macho_seg_cb, NULL);
    return g_nsegs > 0 && !g_segments_failed;
}

#else

static int phdr_cb(struct dl_phdr_info *info, size_t size, void *data)
{
    (void)size;
    (void)data;
    /* find the object containing this function */
    uintptr_t self = (uintptr_t)&collect_segments;
    int mine = 0;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD)
            continue;
        uintptr_t lo = info->dlpi_addr + ph->p_vaddr;
        if (self >= lo && self < lo + ph->p_memsz) {
            mine = 1;
            break;
        }
    }
    if (!mine)
        return 0;

    /* GNU_RELRO gets mprotected read-only after relocation: not writable at
     * runtime and constant after load — exclude it from the snapshot. The
     * loader page-aligns the protected range. */
    long host_page = sysconf(_SC_PAGESIZE);
    uint64_t page_mask = (host_page > 0 ? (uint64_t)host_page : 4096) - 1;
    uint64_t relro_lo = 0, relro_hi = 0;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type == PT_GNU_RELRO) {
            relro_lo = info->dlpi_addr + ph->p_vaddr;
            relro_hi = (relro_lo + ph->p_memsz + page_mask) & ~page_mask;
            relro_lo &= ~page_mask;
        }
    }

    uint64_t img_lo = UINT64_MAX, img_hi = 0;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD)
            continue;
        uint64_t lo = info->dlpi_addr + ph->p_vaddr;
        uint64_t hi = lo + ph->p_memsz;
        if (lo < img_lo)
            img_lo = lo;
        if (hi > img_hi)
            img_hi = hi;
        if (ph->p_flags & PF_W) {
            if (relro_hi > relro_lo && relro_lo < hi && relro_hi > lo) {
                push_seg(lo, relro_lo > lo ? relro_lo : lo);
                push_seg(relro_hi < hi ? relro_hi : hi, hi);
            } else {
                push_seg(lo, hi);
            }
        }
    }
    g_image_lo = img_lo;
    g_image_hi = img_hi;
    return 1;
}

static int collect_segments(void)
{
    if (!g_region_count || g_segments_failed)
        return 0;
    if (g_nsegs)
        return 1;
    dl_iterate_phdr(phdr_cb, NULL);
    return g_nsegs > 0 && !g_segments_failed;
}

#endif

static void ensure_boot_id(void)
{
    if (!g_boot_id) {
        /* Identifies this process+load; must differ across sessions and stay
         * stable within one. NB: never mix two intra-image addresses — ASLR
         * shifts them together and the xor cancels out. */
#if defined(_WIN32)
        uint64_t pid = (uint64_t)GetCurrentProcessId();
        uint64_t t = (uint64_t)GetTickCount64();
#else
        uint64_t pid = (uint64_t)getpid();
        uint64_t t;
        {
            struct timespec ts;
            clock_gettime(CLOCK_MONOTONIC, &ts);
            t = (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
        }
#endif
        g_boot_id = (pid * 0x9E3779B97F4A7C15ULL) ^ (t << 1) ^ g_image_lo;
        if (!g_boot_id)
            g_boot_id = 1;
    }
}

/* ------------------------------------------------------------ size ----- */

typedef struct {
    uint32_t magic, version;
    uint32_t profile_build;
    uint32_t physical_build;
    uint32_t nsegs;
    uint64_t image_lo, image_hi;
    uint64_t boot_id;
    uint64_t arena_used;  /* full break, for grow_to on restore */
    uint64_t stack_off;   /* saved slice offset within the stack region */
    uint64_t stack_len;
    uint64_t heap_len;    /* bytes of sparse dlmalloc heap image */
} obs_header;

static uint64_t segs_bytes(void)
{
    uint64_t t = 0;
    for (int i = 0; i < g_nsegs; i++)
        t += g_segs[i].size;
    return t;
}

static obor_snapshot_cache owned_cache OBOR_RUNTIME;
static uint32_t owned_capacity OBOR_RUNTIME;

/* Invalidation keeps the caller's registration but forgets both images.
 * Epochs must never survive restarting a watcher (generation one again). */
void obor_state_owned_forget(void)
{
    owned_cache.slot[0].epoch = owned_cache.slot[1].epoch = 0;
    owned_cache.previous_epoch = 0;
}

void obor_state_owned_discard(void)
{
    memset(&owned_cache, 0, sizeof(owned_cache));
    owned_capacity = 0;
}

static int owned_stop_images(void)
{
    if (!obor_write_watch_stop()) return 0;
    obor_state_owned_forget();
    return 1;
}

void obor_state_owned_suspend(void)
{
    if (!owned_stop_images()) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
}

static void owned_full_range(obor_state_ranges *ranges, uint32_t size)
{
    ranges->count = 1;
    ranges->ranges[0].offset = 0;
    ranges->ranges[0].length = size;
}

#if OBOR_WRITE_WATCH_ENABLED
typedef struct { obor_state_ranges *ranges; uint32_t size; } owned_range_context;
static void owned_emit_range(void *context, size_t offset, size_t length)
{
    owned_range_context *r = context;
    obor_state_ranges *out = r->ranges;
    if (!length || (out->count == 1 && out->ranges[0].offset == 0 &&
                    out->ranges[0].length == r->size)) return;
    if (offset > r->size || length > r->size - offset ||
        out->count == OBOR_STATE_RANGE_MAX) {
        owned_full_range(out, r->size);
        return;
    }
    if (out->count) {
        obor_state_range *last = &out->ranges[out->count - 1];
        if ((uint64_t)last->offset + last->length == offset) {
            last->length += (uint32_t)length;
            return;
        }
    }
    out->ranges[out->count++] = (obor_state_range){(uint32_t)offset, (uint32_t)length};
}
#endif

static int checked_add_u64(uint64_t *total, uint64_t add)
{
    if (*total > UINT64_MAX - add)
        return 0;
    *total += add;
    return 1;
}

/* Before a game's first observed peak, its menu heap is a poor predictor of
 * level-loading allocations. Ordinary PACK stores uncompressed resource bytes;
 * use that data footprint as an additional cold-session reserve hint. This is
 * deliberately generic and has no title-specific sizes or identifiers. Later
 * sessions retain the measured-peak policy instead of permanently paying for
 * unused music/resources in large archives. Unpacked content has no such hint. */
static uint64_t cold_pack_reserve(void)
{
    unsigned char h[8], d[4];
    uint64_t result = 0;
    FILE *fp = fopen(packfile, "rb");
    if (!fp)
        return 0;
    if (fread(h, 1, sizeof(h), fp) == sizeof(h) &&
        !memcmp(h, "PACK\0\0\0\0", sizeof(h)) &&
        !fseek(fp, -4, SEEK_END) && fread(d, 1, sizeof(d), fp) == sizeof(d)) {
        uint64_t directory = (uint64_t)d[0] | (uint64_t)d[1] << 8 |
                             (uint64_t)d[2] << 16 | (uint64_t)d[3] << 24;
        if (directory > 8 && directory < OBOR_ARENA_MAX_SZ)
            result = directory - 8;
    }
    fclose(fp);
    return result;
}

static uint32_t serialize_size_impl(void)
{
    if (!collect_segments())
        return 0;
    uint64_t hn = obor_heap_sparse_size();
    if (!hn)
        return 0;
    uint64_t previous_peak = g_size_bound ? 0 : peak_read();
    /* Boot now completes resource loading before exposing this API. Teach
     * the existing peak policy that measured footprint before its first
     * capacity decision, including when an older run left a bootstrap-only
     * peak. Retain larger peaks from later levels and the usual margin. */
    if (!g_size_bound)
        peak_update(hn);
    uint64_t required = sizeof(obs_header) +
                        (uint64_t)g_nsegs * sizeof(seg_t) + segs_bytes() +
                        OBOR_STACK_HEAD + OBOR_STACK_BUDGET + hn +
                        (8ULL << 20);
    required = (required + (1ULL << 20) - 1) & ~((1ULL << 20) - 1);
    if (required > UINT32_MAX)
        return 0;
    if (!g_size_bound) {
        uint64_t fixed = sizeof(obs_header) + (uint64_t)g_nsegs * sizeof(seg_t) +
                         g_full_segment_bytes + OBOR_STACK_HEAD + OBOR_STACK_BUDGET;
        uint64_t peak = peak_read();
        uint64_t bound;
        if (peak) {
            /* a previous session recorded this game's real high-water:
             * trust it (plus margin) — much tighter than guessing */
            bound = peak + peak / 3;
            if (bound < hn + (8ULL << 20))
                bound = hn + (8ULL << 20);
        } else {
            bound = hn * 2;
            if (bound < hn + (16ULL << 20))
                bound = hn + (16ULL << 20);
        }
        /* A bootstrap-only cache is not evidence of a completed session.
         * Keep the existing cold PACK allowance until a trustworthy peak
         * exists, even when the newly measured boot footprint was persisted. */
        if (!previous_peak || previous_peak < hn) {
            uint64_t packed = cold_pack_reserve() * 5 / 8;
            /* Five eighths of the uncompressed PACK data is a useful upper
             * estimate for the images/scripts cached by typical mods while
             * discounting
             * streamed music and video.  The inactive-engine subtraction
             * below removes about 24 MiB from build 8023: cap the estimate at
             * 216 MiB so a large first-run game still advertises the proven
             * 223 MiB transport size, below a 256 MiB rewind ring. */
            if (packed > (216ULL << 20))
                packed = 216ULL << 20;
            if (bound < packed)
                bound = packed;
        }
        bound += fixed;
        bound = (bound + (8ULL << 20) - 1) & ~((8ULL << 20) - 1);
        /* Preserve the old policy's ENTIRE heap/stack growth allowance,
         * including its coarse rounding. Remove only bytes belonging to
         * inactive engines, then align transport capacity to one MiB.
         * Rounding the reduced payload first could accidentally consume
         * allowance on which an already-working larger level relied. */
        bound -= g_full_segment_bytes - segs_bytes();
        bound = (bound + (1ULL << 20) - 1) & ~((1ULL << 20) - 1);
        /* RetroArch's fixed-size rewind ring can fail while restoring a
         * large advertised state even when its live payload is much smaller.
         * When the current state plus the normal growth allowance fits this
         * compact capacity, avoid advertising the unused cold/peak reserve.
         * The condition depends only on live state structure, never content
         * identity. A later larger state still raises the reported bound for
         * frontends that query it again. */
        if (bound > OBOR_REWIND_COMPACT_CAP &&
            required <= OBOR_REWIND_COMPACT_CAP)
            bound = OBOR_REWIND_COMPACT_CAP;
        g_size_bound = (uint32_t)bound;
    }

    /* The variable-size serialization contract lets manual saves follow a
     * level that grows beyond the initial rewind allocation. RetroArch keeps
     * its rewind ring at the earlier size; captures then fail cleanly while
     * a manual save, which re-queries this function, remains lossless. */
    if (required > g_size_bound)
        g_size_bound = (uint32_t)required;
    return g_size_bound;
}

/* -------------------------------------------------------- serialize ---- */

static uint32_t serialize_impl(void *buf, uint32_t size, obor_state_ranges *ranges)
{
    static int profile_heap_reported;
    if (!collect_segments())
        return 0;
    ensure_boot_id();

    /* webm cutscene threads allocate concurrently; a snapshot taken mid-
     * alloc would capture a torn heap. Rare and short-lived: skip. */
    if (__atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST) > 0) {
        fprintf(stderr, "[obor] serialize skipped during threaded playback\n");
        return 0;
    }

    /* Stack payload = two pieces:
     *  - the first page of the region, where co_derive keeps the cothread
     *    handle (saved SP/IP/callee regs) — without it a restore resumes
     *    the WRONG context over the right stack
     *  - the live slice [parked SP - red zone, top]; below SP is ABI-dead */
    uint8_t *stack_lo = (uint8_t *)obor_stack_ptr();
    uint8_t *stack_hi = stack_lo + obor_stack_size();
    uint8_t *sp = (uint8_t *)obor_engine_sp();
    uint8_t *slice = stack_lo;
    if (sp > stack_lo + OBOR_STACK_HEAD + 128 && sp < stack_hi)
        slice = sp - 128; /* x86-64 red zone */
    uint64_t stack_len = (uint64_t)(stack_hi - slice);
    if (stack_len > OBOR_STACK_BUDGET) {
        fprintf(stderr, "[obor] parked stack %llu > budget — state skipped\n",
                (unsigned long long)stack_len);
        return 0;
    }

    uint64_t heap_high_water = heap_used();
    if (!profile_heap_reported && getenv("OBOR_PROFILE")) {
        size_t live = 0, free_bytes = 0, top_free = 0;
        obor_arena_stats(&live, &free_bytes, &top_free);
        fprintf(stderr,
                "[obor-profile] heap_high_water=%llu live_allocated=%llu "
                "free_chunks=%llu top_free=%llu\n",
                (unsigned long long)heap_high_water,
                (unsigned long long)live,
                (unsigned long long)free_bytes,
                (unsigned long long)top_free);
        profile_heap_reported = 1;
    }
    uint64_t fixed = sizeof(obs_header) +
                     (uint64_t)g_nsegs * sizeof(seg_t) + segs_bytes() +
                     OBOR_STACK_HEAD + stack_len;
    if (fixed >= size)
        return 0;
    /* A frontend may retain an earlier rewind allocation after the heap
     * grows. Do not partially overwrite its previous valid snapshot when
     * the new heap no longer fits. */
    int owned = 0;
    unsigned owned_index = 0;
    uint64_t owned_prefix = heap_high_water, owned_suffix = 0,
             owned_suffix_length = 0, owned_heap_bytes = heap_high_water + 48;
#if OBOR_WRITE_WATCH_ENABLED
    if (ranges && size == owned_capacity) {
        if (buf == owned_cache.slot[0].buffer) owned = 1;
        else if (buf == owned_cache.slot[1].buffer) { owned = 1; owned_index = 1; }
    }
    if (owned) {
        if (owned_heap_bytes > size - fixed) {
            uint64_t prefix, suffix, suffix_length;
            if (obor_heap_owned_layout(&prefix, &suffix, &suffix_length) &&
                prefix <= heap_high_water && suffix >= prefix &&
                suffix <= heap_high_water &&
                suffix_length == heap_high_water - suffix &&
                prefix + suffix_length + 64 <= size - fixed) {
                owned_prefix = prefix;
                owned_suffix = suffix;
                owned_suffix_length = suffix_length;
                owned_heap_bytes = prefix + suffix_length + 64;
            }
        }
        size_t page = obor_write_watch_page_size();
        if (!page) {
            long actual_page = sysconf(_SC_PAGESIZE);
            if (actual_page > 0) page = (size_t)actual_page;
        }
        uint64_t maximum = OBOR_ARENA_MAX_SZ - (heap_lo() - (uint64_t)(uintptr_t)obor_arena_base());
        uint64_t rounded = page && heap_high_water <= UINT64_MAX - (page - 1) ?
            (heap_high_water + page - 1) / page * page : 0;
        if (!rounded || rounded > maximum || owned_heap_bytes > size - fixed ||
            (!obor_write_watch_epoch() && !obor_write_watch_start(
                (void *)(uintptr_t)heap_lo(), (size_t)rounded, (size_t)maximum)) ||
            !obor_write_watch_extend((size_t)rounded)) {
            if (!owned_stop_images()) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
            owned = 0;
        }
    }
#endif
    uint64_t heap_required = owned ? owned_heap_bytes : obor_heap_sparse_size();
    /* Learn growth even when an older fixed frontend allocation cannot
     * hold it. This check precedes sparse_write, so its failure path alone
     * cannot update the next session's capacity. */
    if (heap_required && !owned)
        peak_update(heap_required);
    if (!heap_required || heap_required > size - fixed)
        return 0;

    uint8_t *p = (uint8_t *)buf;
    obs_header h;
    memset(&h, 0, sizeof(h));
    h.magic = OBS_MAGIC;
    h.version = OBS_VERSION;
    h.profile_build = g_profile_build;
    h.physical_build = (uint32_t)OBOR_ENGINE_BUILD;
    h.nsegs = (uint32_t)g_nsegs;
    h.image_lo = g_image_lo;
    h.image_hi = g_image_hi;
    h.boot_id = g_boot_id;
    h.arena_used = obor_arena_used();
    h.stack_off = (uint64_t)(slice - stack_lo);
    h.stack_len = stack_len;

    /* v3 blob layout: header | seg table | seg data | stack head |
     * sparse heap | stack slice.  The heap encoder retains complete live
     * chunks and allocator metadata while omitting free user bytes. */
    uint8_t *heap_blob = p + sizeof(h) + (size_t)g_nsegs * sizeof(seg_t) +
                         (size_t)segs_bytes() + OBOR_STACK_HEAD;

    struct timespec ts0, ts1;
    clock_gettime(CLOCK_MONOTONIC, &ts0);
    memcpy(p, &h, sizeof(h));
    p += sizeof(h);
    memcpy(p, g_segs, (size_t)g_nsegs * sizeof(seg_t));
    p += (size_t)g_nsegs * sizeof(seg_t);
    for (int i = 0; i < g_nsegs; i++) {
        memcpy(p, (void *)(uintptr_t)g_segs[i].vaddr, (size_t)g_segs[i].size);
        p += g_segs[i].size;
    }
    memcpy(p, stack_lo, OBOR_STACK_HEAD);
    p += OBOR_STACK_HEAD;
    obor_test_fault_phase("save-copy");
    clock_gettime(CLOCK_MONOTONIC, &ts1);
    {
        static int dbg3 = -1, n3;
        if (dbg3 < 0)
            dbg3 = getenv("OBOR_DEBUG") != NULL;
        if (dbg3 && (++n3 % 30) == 1)
            fprintf(stderr, "[obor] seg copy %.2f ms\n",
                    (ts1.tv_sec - ts0.tv_sec) * 1e3 +
                        (ts1.tv_nsec - ts0.tv_nsec) / 1e6);
    }

    uint64_t hlen = 0;
#if OBOR_WRITE_WATCH_ENABLED
    if (owned) {
        /* Both layouts use ordinary OHS v2 spans. The split form omits only
         * the unused top chunk, retaining its header and segment footer. */
        struct { uint32_t magic, version, count, reserved;
                 uint64_t arena_used, payload; } heap_header = {
            0x3153484fU, 2, owned_suffix_length ? 2 : 1, 0,
            h.arena_used, owned_prefix + owned_suffix_length};
        uint64_t span[2] = {0, owned_prefix};
        memcpy(heap_blob, &heap_header, sizeof(heap_header));
        memcpy(heap_blob + sizeof(heap_header), span, sizeof(span));
        hlen = owned_heap_bytes;
        if (owned_suffix_length) {
            uint64_t tail_span[2] = {owned_suffix, owned_suffix_length};
            uint8_t *tail = heap_blob + 48 + owned_prefix;
            memcpy(tail, tail_span, sizeof(tail_span));
            memcpy(tail + sizeof(tail_span),
                (void *)(uintptr_t)(heap_lo() + owned_suffix),
                (size_t)owned_suffix_length);
        }
        memcpy(heap_blob + hlen, slice, (size_t)stack_len);
        ranges->count = 0;
        owned_range_context range_context = {ranges, size};
        uint64_t epoch = obor_write_watch_epoch();
        obor_snapshot_copy(&owned_cache, owned_index, (void *)(uintptr_t)heap_lo(),
            (size_t)(heap_blob + 48 - (uint8_t *)buf), (size_t)owned_prefix,
            (size_t)(fixed + hlen), size, obor_write_watch_page_size(), epoch,
            obor_write_watch_page_epoch, owned_emit_range, &range_context);
        size_t page = obor_write_watch_page_size();
        size_t protected_length = ((size_t)heap_high_water + page - 1) / page * page;
        int armed = obor_write_watch_arm(protected_length);
        if (armed != 1) {
            if (armed < 0 || !owned_stop_images()) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
            owned_full_range(ranges, size);
        }
    } else
#endif
    {
        hlen = obor_heap_sparse_write(heap_blob, size - fixed);
        if (ranges) {
            if (!owned_stop_images()) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
            owned_full_range(ranges, size);
        }
    }
    if (!hlen) {
        /* A failed save must still teach the next session the real bound. */
        uint64_t required = obor_heap_sparse_size();
        peak_update(required);
        fprintf(stderr,
                "[obor] sparse heap exceeds announced state capacity — "
                "save/rewind disabled until restart (needs %llu heap bytes)\n",
                (unsigned long long)required);
        return 0;
    }
    h.heap_len = hlen;
    memcpy(buf, &h, sizeof(h));
    if (!owned) peak_update(hlen);

    memcpy(heap_blob + hlen, slice, (size_t)stack_len);
    return (uint32_t)(fixed + hlen);
}

/* ------------------------------------------------------ unserialize ---- */

/* Shift every stored pointer that falls in the save-time module range by
 * delta (cross-process load: the module lands at a new ASLR base).
 *
 * Scans at 4-BYTE granularity, not 8: the engine's script Instruction packs
 * its builtin-function pointer after 32-bit fields, so those pointers sit at
 * 4-byte-aligned-but-8-byte-misaligned offsets. A word-aligned scan skipped
 * them, leaving stale code pointers that crashed the interpreter on load for
 * script-heavy games (AoF Remix, Bad School Girls...). Unaligned access via
 * memcpy (safe on x86-64 and ARM64). After fixing a pointer we advance past
 * its 8 bytes so a straddling window can't re-shift it. */
#if !defined(OBOR_FIXED_ELF_IMAGE) && !defined(OBOR_FIXED_PE_IMAGE)
static void rebase_range(void *region, size_t nbytes, uint64_t old_lo,
                         uint64_t old_hi, int64_t delta)
{
    uint8_t *b = (uint8_t *)region;
    size_t i = 0;
    while (i + 8 <= nbytes) {
        uint64_t v;
        memcpy(&v, b + i, 8);
        if (v >= old_lo && v < old_hi) {
            v = (uint64_t)((int64_t)v + delta);
            memcpy(b + i, &v, 8);
            i += 8;
        } else {
            i += 4;
        }
    }
}
#endif

static int32_t unserialize_impl(const void *buf, uint32_t size, int *committed)
{
    /* Restoring the arena while playback workers use it would destroy
     * their queues and synchronization objects. As with serialization,
     * leave playback intact and refuse the operation until it finishes. */
    if (__atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST) > 0)
        return 0;
    if (!buf || !collect_segments())
        return 0;
    ensure_boot_id();
    int debug_restore = getenv("OBOR_DEBUG") != NULL;

    if (size < sizeof(obs_header))
        return 0;
    obs_header h;
    memcpy(&h, buf, sizeof(h));
    if (h.magic != OBS_MAGIC || h.version != OBS_VERSION)
        return 0;
    if (h.profile_build != g_profile_build ||
        h.physical_build != (uint32_t)OBOR_ENGINE_BUILD) {
        fprintf(stderr, "[obor] state from profile %u / engine %u, running %u / %u — rejected\n",
                h.profile_build, h.physical_build, g_profile_build,
                (unsigned)OBOR_ENGINE_BUILD);
        return 0;
    }
    if (h.nsegs == 0 || h.nsegs > MAX_SEGS ||
        h.nsegs != (uint32_t)g_nsegs)
        return 0;

    /* Validate every variable-length field before reading the segment
     * table. In particular, a header-only/truncated state must never make
     * the memcpy below read beyond the frontend's buffer. */
    uint64_t table_bytes = (uint64_t)h.nsegs * sizeof(seg_t);
    uint64_t prefix = sizeof(h);
    if (!checked_add_u64(&prefix, table_bytes) || prefix > size)
        return 0;
    if (h.image_hi <= h.image_lo || g_image_hi <= g_image_lo ||
        h.image_hi - h.image_lo != g_image_hi - g_image_lo)
        return 0;
    uint64_t arena_pre = heap_lo() -
                         (uint64_t)(uintptr_t)obor_arena_base();
    if (arena_pre > OBOR_ARENA_MAX_SZ ||
        h.arena_used < arena_pre || h.arena_used > OBOR_ARENA_MAX_SZ)
        return 0;
    if (h.stack_len > OBOR_STACK_BUDGET ||
        h.stack_off < OBOR_STACK_HEAD ||
        h.stack_off > obor_stack_size() ||
        h.stack_len != obor_stack_size() - h.stack_off)
        return 0;

    const uint8_t *p = (const uint8_t *)buf + sizeof(h);
    seg_t saved[MAX_SEGS];
    memcpy(saved, p, (size_t)h.nsegs * sizeof(seg_t));
    p += (size_t)h.nsegs * sizeof(seg_t);

    /* layout must match modulo one common displacement */
    int64_t delta;
    if (g_image_lo >= h.image_lo) {
        if (g_image_lo - h.image_lo > INT64_MAX)
            return 0;
        delta = (int64_t)(g_image_lo - h.image_lo);
    } else {
        if (h.image_lo - g_image_lo > INT64_MAX)
            return 0;
        delta = -(int64_t)(h.image_lo - g_image_lo);
    }
    for (int i = 0; i < g_nsegs; i++) {
        if (!saved[i].size ||
            saved[i].size > h.image_hi - h.image_lo ||
            saved[i].vaddr < h.image_lo ||
            saved[i].vaddr > h.image_hi - saved[i].size ||
            saved[i].size != g_segs[i].size ||
            saved[i].vaddr - h.image_lo !=
                g_segs[i].vaddr - g_image_lo)
            return 0;
    }
#if defined(OBOR_FIXED_ELF_IMAGE) || defined(OBOR_FIXED_PE_IMAGE)
    /* This build deliberately has a stable PT_LOAD address so its stored
     * code and static-data pointers need no inference.  A different address
     * identifies a state made by an older ASLR build; reject it before
     * touching live engine memory instead of heuristically rewriting every
     * pointer-looking word in arbitrary game buffers. */
    if (delta != 0) {
        fprintf(stderr,
                "[obor] state image base differs from fixed-address core — rejected\n");
        return 0;
    }
#endif
    uint64_t total = prefix;
    if (!checked_add_u64(&total, segs_bytes()) ||
        !checked_add_u64(&total, OBOR_STACK_HEAD) ||
        !checked_add_u64(&total, h.heap_len) ||
        !checked_add_u64(&total, h.stack_len) || total > size)
        return 0;
    const uint8_t *heap_src = p + segs_bytes() + OBOR_STACK_HEAD;
    if (!obor_heap_sparse_validate(heap_src, h.heap_len, h.arena_used))
        return 0;
    if (!obor_arena_grow_to((size_t)h.arena_used))
        return 0;

    if (debug_restore)
        fprintf(stderr, "[obor] unserialize validated heap=%llu delta pending\n",
                (unsigned long long)h.heap_len);

    int same_session = (h.boot_id == g_boot_id);

    /* Everything below runs while the module's own .data/.bss — including
     * this file's globals — is being overwritten with the saved image, so
     * every value we still need lives in LOCALS on the frontend stack. */
    int nsegs_l = g_nsegs;
    seg_t segs_l[MAX_SEGS];
    memcpy(segs_l, g_segs, sizeof(segs_l));
    uint64_t image_lo_l = g_image_lo, image_hi_l = g_image_hi;
    uint64_t boot_id_l = g_boot_id;
    uint32_t size_bound_l = g_size_bound;
    char peak_dir_l[sizeof(g_peak_dir)];
    memcpy(peak_dir_l, g_peak_dir, sizeof(peak_dir_l));
    uint64_t peak_written_l = g_peak_written;
    obor_engine_region regions_l[OBOR_MAX_ENGINE_REGIONS];
    memcpy(regions_l, g_regions, sizeof(regions_l));
    uint32_t region_count_l = g_region_count;
    uint64_t full_segment_bytes_l = g_full_segment_bytes;
    void *frontend_context_l = obor_frontend_context();
    obor_session_paths session_paths_l;
    obor_session_paths_get(&session_paths_l);
    FILE *openbor_log_l = &openborLog ? openborLog : NULL;
    FILE *script_log_l = &scriptLog ? scriptLog : NULL;
    int pakfd_l = pakfd, cache_fd_l = real_pakfd;
#if defined(_WIN32)
    uintptr_t stack_guard_l = __stack_chk_guard;
#endif

    /* keep the pak path of THIS load (the buffer's copy will overwrite the
     * global, which is fine — same game — but we need it for the fd fixup) */
    char pak_now[MAX_FILENAME_LEN];
    strncpy(pak_now, packfile, sizeof(pak_now) - 1);
    pak_now[sizeof(pak_now) - 1] = '\0';

    uint8_t *stack_dst = (uint8_t *)obor_stack_ptr() + h.stack_off;

    /* From here onwards a failed load cannot retain a coherent live world. */
    *committed = 1;

#ifdef OBOR_HAS_MOVIE_PLAYBACK
    if (debug_restore)
        fprintf(stderr, "[obor] unserialize suspending live resources\n");
    obor_packfile_suspend();
    obor_webm_state_suspend();
#endif
    if (debug_restore)
        fprintf(stderr, "[obor] unserialize copying snapshot\n");
    for (int i = 0; i < nsegs_l; i++) {
        memcpy((void *)(uintptr_t)segs_l[i].vaddr, p, (size_t)segs_l[i].size);
        p += segs_l[i].size;
        if (i == 0) obor_test_fault_phase("load-partial");
    }
    obor_test_fault_phase("load-copy");
#if defined(_WIN32)
    __stack_chk_guard = stack_guard_l;
#endif
    memcpy(obor_stack_ptr(), p, OBOR_STACK_HEAD);
    p += OBOR_STACK_HEAD;
    if (!obor_heap_sparse_restore(p, h.heap_len, h.arena_used))
        return 0;
    obor_test_fault_phase("load-heap");
    p += h.heap_len;
    memcpy(stack_dst, p, (size_t)h.stack_len);
    p += h.stack_len;

    if (!same_session && delta != 0) {
#if !defined(OBOR_FIXED_ELF_IMAGE) && !defined(OBOR_FIXED_PE_IMAGE)
        if (debug_restore)
            fprintf(stderr, "[obor] unserialize rebasing segments and stacks delta=%lld\n",
                    (long long)delta);
        for (int i = 0; i < nsegs_l; i++)
            rebase_range((void *)(uintptr_t)segs_l[i].vaddr,
                         (size_t)segs_l[i].size, h.image_lo, h.image_hi, delta);
        rebase_range(obor_stack_ptr(), OBOR_STACK_HEAD, h.image_lo,
                     h.image_hi, delta);
        rebase_range(stack_dst, (size_t)h.stack_len, h.image_lo, h.image_hi,
                     delta);
        if (debug_restore)
            fprintf(stderr, "[obor] unserialize rebasing heap bytes=%llu\n",
                    (unsigned long long)(h.arena_used - arena_pre));
        rebase_range((void *)(uintptr_t)heap_lo(),
                     (size_t)(h.arena_used - arena_pre),
                     h.image_lo, h.image_hi, delta);
        if (debug_restore)
            fprintf(stderr, "[obor] unserialize heap rebase complete\n");
#endif
    }

    /* repair this module's identity globals (they now hold save-time values;
     * rebase already shifted the seg/image addresses, but boot id and size
     * bound must reflect THIS session) */
    memcpy(g_segs, segs_l, sizeof(segs_l));
    g_nsegs = nsegs_l;
    g_image_lo = image_lo_l;
    g_image_hi = image_hi_l;
    g_boot_id = boot_id_l;
    g_size_bound = size_bound_l;
    memcpy(g_peak_dir, peak_dir_l, sizeof(g_peak_dir));
    g_peak_written = peak_written_l;
    memcpy(g_regions, regions_l, sizeof(g_regions));
    g_region_count = region_count_l;
    g_segments_failed = 0;
    g_full_segment_bytes = full_segment_bytes_l;
    /* co_frontend is a pointer to this process's thread-local libco context.
     * The snapshot's value belongs to the saving process and cannot be
     * rebased as a module pointer. */
    obor_frontend_context_restore(frontend_context_l);
    obor_session_paths_restore(&session_paths_l);
    /* OS-handle fixups (bytes can't carry fds/FILEs across sessions) */
#ifdef OBOR_HAS_MOVIE_PLAYBACK
    if (debug_restore)
        fprintf(stderr, "[obor] unserialize resuming movie state\n");
    obor_webm_state_resume();
    if (debug_restore)
        fprintf(stderr, "[obor] unserialize repairing pack handles\n");
    int resources_ok = obor_packfile_fixup(pak_now);
    if (debug_restore)
        fprintf(stderr, "[obor] unserialize resource repair complete ok=%d\n",
                resources_ok);
#elif defined(_WIN32)
    obor_packfile_fixup(pak_now);
#else
    if (obor_packfile_fixup)
        obor_packfile_fixup(pak_now);
#endif
    /* Keep current OS resources on both rewind and cross-session loads.
     * Losing the current FILE leaks it; using the saved one is invalid.
     * Cache reads seek explicitly, so retaining its live fd is sufficient. */
    pakfd = pakfd_l;
    real_pakfd = cache_fd_l;
    if (&openborLog)
        openborLog = openbor_log_l;
    if (&scriptLog)
        scriptLog = script_log_l;
#ifdef OBOR_HAS_MOVIE_PLAYBACK
    return resources_ok;
#else
    return 1;
#endif
}

#include "obor_state_padding.h"

/* These contexts and the recovery point live on the frontend stack. In
 * particular they survive faults partway through restoring module globals. */
typedef struct {
    void *buffer;
    uint32_t size, result;
    int operation, committed;
    void *second;
    obor_state_ranges *ranges;
} state_call;

static void execute_state(void *context)
{
    state_call *call = (state_call *)context;
    if (call->operation == 0) {
        obor_test_fault_phase("size");
        call->result = serialize_size_impl();
    } else if (call->operation == 1 || call->operation == 3) {
        if (call->ranges) call->ranges->count = 0;
        obor_test_fault_phase("save");
        call->result = serialize_impl(call->buffer, call->size, call->ranges);
        if (call->result && call->result < call->size &&
            (!call->ranges || !owned_cache.previous_epoch))
        {
            obor_test_fault_phase("save-padding");
            obor_state_clear_padding((uint8_t *)call->buffer + call->result,
                                      call->size - call->result);
        }
    } else if (call->operation == 2) {
        if (!owned_stop_images())
            obor_fault_abort(OBOR_FAULT_MEMORY, 0);
        obor_test_fault_phase("load");
        call->result = unserialize_impl(call->buffer, call->size, &call->committed);
        if (!call->result && call->committed)
            obor_fault_abort(OBOR_FAULT_STATE, 0);
    } else if (call->operation == 4) {
#if OBOR_WRITE_WATCH_ENABLED
        if (!owned_capacity && !__atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST)) {
            owned_cache.slot[0].buffer = call->buffer;
            owned_cache.slot[1].buffer = call->second;
            owned_capacity = call->size;
            obor_state_owned_forget();
            call->result = 1;
        }
#endif
    } else if (call->operation == 5) {
        if (!owned_stop_images()) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
        obor_state_owned_discard();
        call->result = 1;
    }
}

int32_t obor_owned_begin(void *first, void *second, uint32_t size)
{
    uintptr_t a = (uintptr_t)first, b = (uintptr_t)second;
    uintptr_t arena = (uintptr_t)obor_arena_base();
    if (!first || !second || !size || a > UINTPTR_MAX - size ||
        b > UINTPTR_MAX - size || (a < b + size && b < a + size) ||
        (a < arena + OBOR_ARENA_MAX_SZ && arena < a + size) ||
        (b < arena + OBOR_ARENA_MAX_SZ && arena < b + size)) return 0;
    state_call call = {first, size, 0, 4, 0, second, NULL};
    return obor_protect_call(execute_state, &call, "owned state begin") ? (int32_t)call.result : 0;
}

uint32_t obor_owned_serialize(void *buffer, uint32_t size, obor_state_ranges *ranges)
{
    if (!ranges || size != owned_capacity || !size ||
        (buffer != owned_cache.slot[0].buffer && buffer != owned_cache.slot[1].buffer)) return 0;
    uintptr_t r = (uintptr_t)ranges;
    uintptr_t a = (uintptr_t)owned_cache.slot[0].buffer;
    uintptr_t b = (uintptr_t)owned_cache.slot[1].buffer;
    uintptr_t arena = (uintptr_t)obor_arena_base();
    if (r > UINTPTR_MAX - sizeof(*ranges) ||
        (r < a + size && a < r + sizeof(*ranges)) ||
        (r < b + size && b < r + sizeof(*ranges)) ||
        (r < arena + OBOR_ARENA_MAX_SZ && arena < r + sizeof(*ranges))) return 0;
    state_call call = {buffer, size, 0, 3, 0, NULL, ranges};
    return obor_protect_call(execute_state, &call, "owned save state") ? call.result : 0;
}

int32_t obor_owned_end(void)
{
    if (!owned_capacity && !obor_write_watch_epoch()) return 1;
    state_call call = {NULL, 0, 0, 5, 0, NULL, NULL};
    return obor_protect_call(execute_state, &call, "owned state end") ? (int32_t)call.result : 0;
}

uint32_t obor_serialize_size(void)
{
    state_call call = {NULL, 0, 0, 0, 0, NULL, NULL};
    return obor_protect_call(execute_state, &call, "state size") ? call.result : 0;
}

uint32_t obor_serialize(void *buffer, uint32_t size)
{
    state_call call = {buffer, size, 0, 1, 0, NULL, NULL};
    return obor_protect_call(execute_state, &call, "save state") ? call.result : 0;
}

int32_t obor_unserialize(const void *buffer, uint32_t size)
{
    state_call call = {(void *)buffer, size, 0, 2, 0, NULL, NULL};
    return obor_protect_call(execute_state, &call, "load state") ? (int32_t)call.result : 0;
}
