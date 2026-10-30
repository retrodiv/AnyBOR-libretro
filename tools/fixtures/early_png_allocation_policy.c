/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <png.h>

uint32_t obor_profile_build;
static unsigned phase;
#define CHECK(c) do { if(!(c)) { fprintf(stderr,"PNG allocation policy revision=%u phase=%u line=%d: %s\n",obor_profile_build,phase,__LINE__,#c); abort(); } } while(0)
#define BYTES 1
static const unsigned char encoded_png[] = {@PNG_BYTES@};
static size_t cursor, failed_bytes;
static int opened, closed, callback_calls, fail_callback, fail_next, logs, ram_calls;
static char diagnostic[512];
static int handle = -1, res[2], png_height;
static png_structp png_ptr;
static png_infop info_ptr;
static png_bytep *row_pointers;

static int openpackfile(char *name, char *pack)
{
    CHECK(!strcmp(name,"image.png") && !strcmp(pack,"fixture"));
    ++opened; cursor = 0; return 7;
}
static int readpackfile(int descriptor, void *out, int bytes)
{
    CHECK(descriptor == 7 && bytes >= 0 && (size_t)bytes <= sizeof(encoded_png) - cursor);
    memcpy(out, encoded_png + cursor, (size_t)bytes);
    cursor += (size_t)bytes;
    return bytes;
}
static int closepackfile(int descriptor)
{
    CHECK(descriptor == 7); ++closed; return 0;
}
static uint64_t getFreeRam(int unit)
{
    CHECK(unit == BYTES); ++ram_calls; return UINT64_C(4294967297);
}
static void writeToLogFile(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    int count = vsnprintf(diagnostic, sizeof(diagnostic), format, args);
    va_end(args);
    CHECK(count >= 0 && (size_t)count < sizeof(diagnostic));
    ++logs;
}
static void *provide_malloc(size_t bytes)
{
    if(fail_next) { fail_next = 0; failed_bytes = bytes; return NULL; }
    return malloc(bytes);
}
#define malloc provide_malloc
@MALLOC_POLICY@
#undef malloc

static void *observe_named(const char *name, size_t bytes)
{
    if(!strcmp(name,"png_tracemalloc"))
    {
        ++callback_calls;
        if(fail_callback) fail_next = 1;
    }
    return obor_profile_malloc_named(name, bytes);
}
#define obor_profile_malloc_named observe_named
@PNG_FUNCTIONS@
#undef obor_profile_malloc_named

static const struct { unsigned revision; int proxy; } rows[] = {@ROWS@};

static void check_pixels(void)
{
    png_colorp palette = NULL;
    int colors = 0;
    CHECK(res[0] == 2 && res[1] == 1 && png_height == 1);
    CHECK(row_pointers && row_pointers[0]);
    CHECK(row_pointers[0][0] == 1 && row_pointers[0][1] == 2);
    CHECK(png_get_PLTE(png_ptr, info_ptr, &palette, &colors) && colors == 256);
    CHECK(palette[1].red == 80 && palette[1].green == 230 && palette[1].blue == 140);
    CHECK(palette[2].red == 240 && palette[2].green == 240 && palette[2].blue == 240);
}

int main(void)
{
    unsigned cases = 0;
    for(size_t index = 0; index < sizeof(rows)/sizeof(rows[0]); ++index)
    {
        obor_profile_build = rows[index].revision;
        for(int refusal = 0; refusal <= 1; ++refusal)
        {
            CHECK(!png_ptr && !info_ptr && !row_pointers && !png_height && handle == -1);
            opened = closed = callback_calls = fail_next = logs = ram_calls = 0;
            failed_bytes = 0; diagnostic[0] = 0;
            fail_callback = refusal; phase = (unsigned)refusal;
            int result = openpng("image.png","fixture");
            CHECK(opened == 1);
            if(refusal && rows[index].proxy)
            {
                char expected[512];
                CHECK(!result && closed == 1 && callback_calls == 1 && failed_bytes > 0);
                CHECK(logs == 1 && ram_calls == 1);
                snprintf(expected, sizeof(expected),
                         "name: png_tracemalloc Requested: %zu Bytes, Remaining, 4294967297 Bytes\n",
                         failed_bytes);
                CHECK(!strcmp(expected, diagnostic));
            }
            else
            {
                CHECK(result == 1 && !closed && !logs && !ram_calls && !failed_bytes);
                CHECK(rows[index].proxy ? callback_calls > 0 : callback_calls == 0);
                check_pixels();
                closepng();
                CHECK(closed == 1);
            }
            CHECK(!png_ptr && !info_ptr && !row_pointers && !png_height && handle == -1);
            ++cases;
        }
    }
    printf("png_allocation_policy=1 contexts=%zu cases=%u\n",sizeof(rows)/sizeof(rows[0]),cases);
    return 0;
}
