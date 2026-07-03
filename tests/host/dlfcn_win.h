/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* minimal dlopen shim for the windows host build */
#ifndef DLFCN_WIN_H
#define DLFCN_WIN_H
#include <stdio.h>
#include <windows.h>
#define RTLD_NOW 0
#define RTLD_LOCAL 0
static void *dlopen(const char *p, int f) { (void)f; return (void *)LoadLibraryA(p); }
static void *dlsym(void *h, const char *n) { return (void *)GetProcAddress((HMODULE)h, n); }
static int dlclose(void *h) { return FreeLibrary((HMODULE)h) ? 0 : -1; }
static const char *dlerror(void) { static char b[64]; snprintf(b, sizeof(b), "err %lu", (unsigned long)GetLastError()); return b; }
#endif
