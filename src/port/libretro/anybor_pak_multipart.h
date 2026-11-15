/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PAK_MULTIPART_H
#define OBOR_PAK_MULTIPART_H
int obor_multipart_init(const char *path);
int obor_multipart_active(void);
int obor_multipart_open(const char *name);
int obor_multipart_read(int handle, void *data, int bytes);
int obor_multipart_seek(int handle, int offset, int origin);
int obor_multipart_close(int handle);
void obor_multipart_closeall(void);
void obor_multipart_rebind(const char *path);
void obor_multipart_term(void);
#endif
