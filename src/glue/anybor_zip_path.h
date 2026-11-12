/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_ZIP_PATH_H
#define OBOR_ZIP_PATH_H
#include <stddef.h>
#include <string.h>

/* Use the same portable namespace on every host, including DOS device names. */
static int obor_zip_component(const char *s, size_t n)
{
    char stem[16];
    size_t i = 0;
    if (!n || s[n-1] == '.' || s[n-1] == ' ') return 0;
    while (i < n && s[i] != '.' && i + 1 < sizeof(stem)) {
        unsigned char c = (unsigned char)s[i];
        stem[i++] = (char)(c >= 'a' && c <= 'z' ? c - 32 : c);
    }
    while (i && stem[i-1] == ' ') --i;
    stem[i] = 0;
    if (!strcmp(stem, "CON") || !strcmp(stem, "PRN") ||
        !strcmp(stem, "AUX") || !strcmp(stem, "NUL") ||
        !strcmp(stem, "CONIN$") || !strcmp(stem, "CONOUT$")) return 0;
    if ((!strncmp(stem, "COM", 3) || !strncmp(stem, "LPT", 3)) &&
        ((i == 4 && stem[3] >= '1' && stem[3] <= '9') ||
         (i == 5 && (unsigned char)stem[3] == 0xc2 &&
          ((unsigned char)stem[4] == 0xb9 || (unsigned char)stem[4] == 0xb2 ||
           (unsigned char)stem[4] == 0xb3)))) return 0;
    return 1;
}

/* Normalize separators while preserving case, and reject absolute paths,
 * parent/current components, control bytes, drive prefixes and NTFS ADS. */
static int obor_zip_safe_name(const char *in, char *out, size_t cap)
{
    size_t k = 0, component = 0;
    if (!in || !in[0] || in[0] == '/' || in[0] == '\\') return 0;
    for (size_t i = 0; in[i]; i++) {
        unsigned char uc = (unsigned char)in[i];
        char c = (char)uc;
        if (uc < 32 || uc == 127 || c == ':' || c == '<' || c == '>' ||
            c == '"' || c == '|' || c == '?' || c == '*') return 0;
        if (c == '\\') c = '/';
        if (k + 1 >= cap) return 0;
        if (c == '/') {
            if (component && !obor_zip_component(out + k - component, component)) return 0;
            if (component == 0) continue;
            component = 0;
        } else {
            component++;
        }
        out[k++] = c;
    }
    if (component && !obor_zip_component(out + k - component, component)) return 0;
    out[k] = '\0';
    return k != 0;
}

#endif
