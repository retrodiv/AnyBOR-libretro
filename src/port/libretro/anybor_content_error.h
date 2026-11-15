/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef ANYBOR_CONTENT_ERROR_H
#define ANYBOR_CONTENT_ERROR_H
/* Called on the engine coroutine. Parking it follows borExit's normal error
 * path; the frontend closes workers, handles and arena before another load. */
void obor_content_error(const char *path, unsigned long row, unsigned long column,
                        const char *reason) __attribute__((noreturn));
void obor_content_import_begin(const char *path);
void obor_content_import_end(void);
#endif
