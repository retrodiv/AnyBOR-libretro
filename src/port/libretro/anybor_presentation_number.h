/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PRESENTATION_NUMBER_H
#define OBOR_PRESENTATION_NUMBER_H

#include "anybor_abi.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef int32_t (*obor_presentation_read_global)(const char *name, double *value);

static inline int obor_presentation_name_char(char c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}

static inline void obor_presentation_skip_space(const char **cursor)
{
    while (**cursor == ' ' || **cursor == '\t') ++*cursor;
}

static inline int obor_presentation_expression(const char **cursor,
    obor_presentation_read_global read_global, unsigned depth, double *out);

static inline int obor_presentation_operand(const char **cursor,
    obor_presentation_read_global read_global, unsigned depth, double *out)
{
    obor_presentation_skip_space(cursor);
    const char *p = *cursor;
    int negative = *p == '-';
    if (*p == '-' || *p == '+') {
        ++p;
        obor_presentation_skip_space(&p);
    }
    if (*p == '(') {
        ++p;
        if (depth == 16 || !obor_presentation_expression(&p, read_global, depth + 1, out) ||
            *p != ')') return 0;
        ++p;
    } else if (!strncmp(p, "$global.", 8)) {
        p += 8;
        const char *start = p;
        while (obor_presentation_name_char(*p)) ++p;
        char name[OBOR_PRESENTATION_NAME];
        size_t size = (size_t)(p - start);
        if (!size || size >= sizeof(name)) return 0;
        memcpy(name, start, size);
        name[size] = 0;
        *out = 0;
        if (read_global && !read_global(name, out)) return 0;
    } else {
        const char *start = p;
        if ((*p < '0' || *p > '9') && *p != '.') return 0;
        while (*p >= '0' && *p <= '9') ++p;
        if (*p == '.') {
            ++p;
            while (*p >= '0' && *p <= '9') ++p;
        }
        if (*p == 'e' || *p == 'E') {
            ++p;
            if (*p == '+' || *p == '-') ++p;
            while (*p >= '0' && *p <= '9') ++p;
        }
        char *end;
        *out = strtod(start, &end);
        if (end == start || end != p || !isfinite(*out)) return 0;
    }
    if (negative) *out = -*out;
    *cursor = p;
    obor_presentation_skip_space(cursor);
    return 1;
}

static inline int obor_presentation_product(const char **cursor,
    obor_presentation_read_global read_global, unsigned depth, double *out)
{
    if (!obor_presentation_operand(cursor, read_global, depth, out)) return 0;
    while (**cursor == '*' || **cursor == '/') {
        char operation = *(*cursor)++;
        double right;
        if (!obor_presentation_operand(cursor, read_global, depth, &right)) return 0;
        if (!read_global) continue;
        if (operation == '/' && right == 0) return 0;
        *out = operation == '*' ? *out * right : *out / right;
        if (!isfinite(*out)) return 0;
    }
    return 1;
}

static inline int obor_presentation_expression(const char **cursor,
    obor_presentation_read_global read_global, unsigned depth, double *out)
{
    if (!obor_presentation_product(cursor, read_global, depth, out)) return 0;
    while (**cursor == '+' || **cursor == '-') {
        char operation = *(*cursor)++;
        double right;
        if (!obor_presentation_product(cursor, read_global, depth, &right)) return 0;
        if (!read_global) continue;
        *out = operation == '+' ? *out + right : *out - right;
        if (!isfinite(*out)) return 0;
    }
    return 1;
}

/* A null reader validates syntax without depending on live game globals. */
static inline int obor_presentation_number(const char *text,
    obor_presentation_read_global read_global, double *out)
{
    return obor_presentation_expression(&text, read_global, 0, out) && !*text;
}

#endif
