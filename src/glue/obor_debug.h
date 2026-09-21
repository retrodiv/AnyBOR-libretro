/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* obor_debug.h — opt-in diagnostics for the AnyBOR glue.
 * Crash reporter and flushed breadcrumb log for the AnyBOR glue.
 * Real-frontend failures on machines we can't attach a debugger to
 * (Windows boxes) leave diagnostic evidence instead of a silently
 * vanishing console.
 *
 * OFF by default: installs no handler, writes no files, costs nothing.
 * Enable with env OBOR_DEBUG=1 (or OBOR_CRASHLOG=1), or by placing a file
 * named "obor_debug.enable" next to the .pak (Windows-friendly, no env
 * var needed). Output lands NEXT TO THE PAK (or the cwd as fallback —
 * never a hardcoded absolute path; Windows has no /tmp):
 *   obor_crash.log — fault code + PC and stack as core+RVA offsets, to be
 *                    symbolized offline against the matching UNSTRIPPED
 *                    core (builds/<target>/anybor_libretro.*.sym). The
 *                    offsets are relative to the module load base:
 *                    linux:   addr2line -f -e anybor_libretro.so.sym 0x<rva>
 *                    windows: x86_64-w64-mingw32-addr2line -f
 *                               -e anybor_libretro.dll.sym 0x<base+rva>
 *                             (base = ImageBase from objdump -p ....dll.sym)
 *                    macos:   atos -o anybor_libretro.dylib.sym -l <base>
 *                             0x<base+rva>   (base = the image base printed
 *                             in the log header; the dylib is slid by dyld)
 *   obor_debug.log — breadcrumbs (boot steps, pristine capture, engine
 *                    selection), fflush'd per line so a crash mid-step
 *                    loses nothing.
 * The single-file core makes one handler cover everything: glue and all
 * six engines share this module, so any PC inside the port shows as
 * core+0x... The handler never swallows the crash: Windows returns
 * EXCEPTION_CONTINUE_SEARCH, POSIX restores SIG_DFL and re-raises.
 */
#ifndef OBOR_DEBUG_H
#define OBOR_DEBUG_H

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <signal.h>
#if defined(__APPLE__) && !defined(_XOPEN_SOURCE)
/* Apple's ucontext.h refuses to declare the legacy routines without it. */
#define _XOPEN_SOURCE 600
#define OBOR_DEBUG_XOPEN_SOURCE_ADDED 1
#endif
#include <ucontext.h>
#if defined(OBOR_DEBUG_XOPEN_SOURCE_ADDED)
#undef OBOR_DEBUG_XOPEN_SOURCE_ADDED
#undef _XOPEN_SOURCE
#endif
#if defined(__APPLE__)
/* Mach-O module range comes from dyld, not from the ELF phdr walk. */
#include "obor_macho.h"
#else
#include <link.h>
#endif
#if defined(__GLIBC__) || defined(__APPLE__)
#include <execinfo.h>
#endif
#endif

typedef struct {
    char directory[1024];
    FILE *file;
    int checked, enabled, installed;
#if defined(_WIN32)
    LPTOP_LEVEL_EXCEPTION_FILTER previous;
#else
    struct sigaction previous[5];
#endif
} obor_diagnostics_state;
static obor_diagnostics_state g_diagnostics;
#define g_dbg_dir (g_diagnostics.directory)
#define g_dbg_file (g_diagnostics.file)
static void obor_dbg_uninstall(void);

/* Remember where the content lives (called once per retro_load_game). */
static void obor_dbg_set_dir(const char *pak_path)
{
    obor_dbg_uninstall();
    g_diagnostics.checked = 0;
    strncpy(g_dbg_dir, pak_path, sizeof(g_dbg_dir) - 1);
    g_dbg_dir[sizeof(g_dbg_dir) - 1] = '\0';
    char *s1 = strrchr(g_dbg_dir, '/');
    char *s2 = strrchr(g_dbg_dir, '\\');
    char *s = (s2 && (!s1 || s2 > s1)) ? s2 : s1;
    if (s)
        *s = '\0';
    else
        g_dbg_dir[0] = '\0';
}

static int obor_dbg_on(void)
{
    int &st = g_diagnostics.enabled;
    if (!g_diagnostics.checked) {
        g_diagnostics.checked = 1;
        st = 0;
        if (getenv("OBOR_DEBUG") || getenv("OBOR_CRASHLOG"))
            st = 1;
        else if (g_dbg_dir[0]) {
            char p[1100];
            snprintf(p, sizeof(p), "%s/obor_debug.enable", g_dbg_dir);
            FILE *e = fopen(p, "rb");
            if (e) {
                fclose(e);
                st = 1;
            }
        }
    }
    return st;
}

/* Open a diagnostics file next to the pak, else cwd-relative. */
static FILE *obor_dbg_open(const char *name, const char *mode)
{
    FILE *f = NULL;
    if (g_dbg_dir[0]) {
        char p[1100];
        snprintf(p, sizeof(p), "%s/%s", g_dbg_dir, name);
        f = fopen(p, mode);
    }
    if (!f)
        f = fopen(name, mode);
    return f;
}

/* Breadcrumb: appended + flushed so a crash right after loses nothing. */
static void obor_dbg(const char *fmt, ...)
{
    if (!obor_dbg_on())
        return;
    if (!g_dbg_file)
        g_dbg_file = obor_dbg_open("obor_debug.log", "w");
    if (!g_dbg_file)
        return;
    va_list va;
    va_start(va, fmt);
    vfprintf(g_dbg_file, fmt, va);
    va_end(va);
    fputc('\n', g_dbg_file);
    fflush(g_dbg_file);
}

/* ---- crash reporter ---------------------------------------------------- */

#if !defined(_WIN32) && !defined(__APPLE__)
struct obor_crash_range {
    uintptr_t self, lo, hi;
};
static int obor_crash_phdr_cb(struct dl_phdr_info *info, size_t sz, void *data)
{
    (void)sz;
    struct obor_crash_range *c = (struct obor_crash_range *)data;
    uintptr_t lo = (uintptr_t)-1, hi = 0;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD)
            continue;
        uintptr_t a = (uintptr_t)info->dlpi_addr + ph->p_vaddr;
        uintptr_t b = a + ph->p_memsz;
        if (a < lo)
            lo = a;
        if (b > hi)
            hi = b;
    }
    if (hi > lo && c->self >= lo && c->self < hi) {
        c->lo = lo;
        c->hi = hi;
        return 1;
    }
    return 0;
}
#endif

/* [base,end) of the core module (the one containing this very code). */
static void obor_module_range(uintptr_t *lo, uintptr_t *hi)
{
    *lo = 0;
    *hi = 0;
#if defined(_WIN32)
    HMODULE mod = NULL;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                               GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)(const void *)&obor_module_range, &mod) &&
        mod) {
        const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)mod;
        const IMAGE_NT_HEADERS *nt =
            (const IMAGE_NT_HEADERS *)((const uint8_t *)mod + dos->e_lfanew);
        *lo = (uintptr_t)mod;
        *hi = (uintptr_t)mod + nt->OptionalHeader.SizeOfImage;
    }
#elif defined(__APPLE__)
    uint64_t low = 0, high = 0;
    obor_macho_image_range(obor_macho_own_header((const void *)&obor_module_range),
                           &low, &high);
    *lo = (uintptr_t)low;
    *hi = (uintptr_t)high;
#else
    struct obor_crash_range ctx = {
        (uintptr_t)(const void *)&obor_module_range, 0, 0};
    dl_iterate_phdr(obor_crash_phdr_cb, &ctx);
    *lo = ctx.lo;
    *hi = ctx.hi;
#endif
}

static void obor_crash_head(FILE *f, uintptr_t *lo, uintptr_t *hi, uintptr_t pc)
{
    obor_module_range(lo, hi);
    fprintf(f, "core base=%p end=%p\n", (void *)*lo, (void *)*hi);
    if (*lo && pc >= *lo && pc < *hi)
        fprintf(f, "PC   core+0x%zx\n", (size_t)(pc - *lo));
    else
        fprintf(f, "PC   %p (outside core)\n", (void *)pc);
    fprintf(f, "-- stack (return addrs in core) --\n");
    fflush(f);
}

static void obor_crash_frame(FILE *f, uintptr_t lo, uintptr_t hi, uintptr_t v)
{
    if (lo && v >= lo && v < hi) {
        fprintf(f, "  core+0x%zx\n", (size_t)(v - lo));
        fflush(f);
    }
}

#if defined(_WIN32)
static LONG WINAPI obor_crash_filter(EXCEPTION_POINTERS *ep)
{
    FILE *f = obor_dbg_open("obor_crash.log", "w");
    if (!f)
        return EXCEPTION_CONTINUE_SEARCH;
    fprintf(f, "CRASH code=0x%08lx addr=%p\n",
            (unsigned long)ep->ExceptionRecord->ExceptionCode,
            ep->ExceptionRecord->ExceptionAddress);
    uintptr_t pc = (uintptr_t)ep->ExceptionRecord->ExceptionAddress, sp = 0;
    if (ep->ContextRecord) {
        pc = (uintptr_t)ep->ContextRecord->Rip;
        sp = (uintptr_t)ep->ContextRecord->Rsp;
    }
    uintptr_t lo = 0, hi = 0;
    obor_crash_head(f, &lo, &hi, pc);
    if (sp) { /* bounded to the mapped stack region so the scan can't fault */
        uintptr_t sp_end = sp + 0x40000;
        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery((void *)sp, &mbi, sizeof(mbi))) {
            uintptr_t e = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
            if (e < sp_end)
                sp_end = e;
        }
        for (uintptr_t p = sp; p + sizeof(uintptr_t) <= sp_end;
             p += sizeof(uintptr_t))
            obor_crash_frame(f, lo, hi, *(uintptr_t *)p);
    }
    fclose(f);
    return EXCEPTION_CONTINUE_SEARCH; /* crash propagates normally */
}
#else
static void obor_posix_crash(int sig, siginfo_t *si, void *ucv)
{
    /* defaults FIRST: a fault while logging propagates, no re-entry loop */
    signal(SIGSEGV, SIG_DFL);
    signal(SIGABRT, SIG_DFL);
    signal(SIGFPE, SIG_DFL);
    signal(SIGBUS, SIG_DFL);
    signal(SIGILL, SIG_DFL);
    FILE *f = obor_dbg_open("obor_crash.log", "w");
    if (f) {
        fprintf(f, "CRASH signal=%d fault_addr=%p\n", sig,
                si ? si->si_addr : (void *)0);
        uintptr_t pc = 0;
        ucontext_t *uc = (ucontext_t *)ucv;
#if defined(__APPLE__)
        /* Darwin reports registers through the mcontext64 of the ucontext. */
#if defined(__x86_64__)
        if (uc && uc->uc_mcontext)
            pc = (uintptr_t)uc->uc_mcontext->__ss.__rip;
#elif defined(__aarch64__)
        if (uc && uc->uc_mcontext)
            pc = (uintptr_t)uc->uc_mcontext->__ss.__pc;
#else
        (void)uc;
#endif
#elif defined(__x86_64__)
        if (uc)
            pc = (uintptr_t)uc->uc_mcontext.gregs[REG_RIP];
#elif defined(__aarch64__)
        if (uc)
            pc = (uintptr_t)uc->uc_mcontext.pc;
#else
        (void)uc;
#endif
        uintptr_t lo = 0, hi = 0;
        obor_crash_head(f, &lo, &hi, pc);
#if defined(__GLIBC__) || defined(__APPLE__)
        void *bt[64];
        int n = backtrace(bt, 64);
        for (int i = 0; i < n; i++)
            obor_crash_frame(f, lo, hi, (uintptr_t)bt[i]);
#else
        uintptr_t sp = (uintptr_t)__builtin_frame_address(0);
        for (uintptr_t p = sp; p + sizeof(uintptr_t) <= sp + 0x4000;
             p += sizeof(uintptr_t))
            obor_crash_frame(f, lo, hi, *(uintptr_t *)p);
#endif
        fclose(f);
    }
    raise(sig); /* re-raise -> default handling propagates the crash */
}
#endif

static void obor_dbg_install(void)
{
    if (g_diagnostics.installed || !obor_dbg_on())
        return;
#if defined(_WIN32)
    g_diagnostics.previous = SetUnhandledExceptionFilter(obor_crash_filter);
    g_diagnostics.installed = 1;
#else
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = obor_posix_crash;
    sa.sa_flags = SA_SIGINFO;
    sigemptyset(&sa.sa_mask);
    const int sigs[] = {SIGSEGV, SIGABRT, SIGFPE, SIGBUS, SIGILL};
    for (unsigned i = 0; i < sizeof(sigs) / sizeof(sigs[0]); i++)
        if (sigaction(sigs[i], &sa, &g_diagnostics.previous[i]) == 0)
            g_diagnostics.installed |= 1 << i;
#endif
    obor_dbg("diagnostics on: crash handler installed");
}

static void obor_dbg_uninstall(void)
{
    if (g_diagnostics.installed) {
#if defined(_WIN32)
        LPTOP_LEVEL_EXCEPTION_FILTER current = SetUnhandledExceptionFilter(g_diagnostics.previous);
        if (current != obor_crash_filter)
            SetUnhandledExceptionFilter(current);
#else
        const int sigs[] = {SIGSEGV, SIGABRT, SIGFPE, SIGBUS, SIGILL};
        for (unsigned i = 0; i < sizeof(sigs) / sizeof(sigs[0]); ++i) {
            struct sigaction current;
            if ((g_diagnostics.installed & (1 << i)) && sigaction(sigs[i], NULL, &current) == 0 &&
                (current.sa_flags & SA_SIGINFO) && current.sa_sigaction == obor_posix_crash)
                sigaction(sigs[i], &g_diagnostics.previous[i], NULL);
        }
#endif
        g_diagnostics.installed = 0;
    }
    if (g_dbg_file) {
        fclose(g_dbg_file);
        g_dbg_file = NULL;
    }
}

#endif /* OBOR_DEBUG_H */
