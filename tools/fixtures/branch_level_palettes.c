/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */

#include "openbor.h"
#include "source/openborscript/commands.h"
#include <assert.h>

uint32_t obor_profile_build;
int pixelformat;
char packfile[OBOR_CONTENT_PATH_MAX] = "profile-test.pak";

static int raw_reads;
static int image_reads;
static int open_handles;
static int read_limit;
static int factory_calls;
static int factory_limit;

void *checkAlloc(void *value, size_t size, const char *function, const char *file, int line)
{
    (void)size;
    (void)function;
    (void)file;
    (void)line;
    assert(value);
    return value;
}

void writeToLogFile(const char *format, ...)
{
    (void)format;
}

int openpackfile(const char *filename, const char *archive)
{
    assert(*filename && archive == packfile);
    assert(!open_handles);
    return ++open_handles;
}

int readpackfile(int handle, void *buffer, int size)
{
    assert(handle == 1 && open_handles && size == 3);
    if(raw_reads++ == read_limit)
    {
        return 0;
    }
    memcpy(buffer, (unsigned char[]){13, 37, 99}, 3);
    return 3;
}

int closepackfile(int handle)
{
    assert(handle == 1 && open_handles == 1);
    --open_handles;
    return 0;
}

int loadimagepalette(char *filename, char *archive, unsigned char *palette)
{
    assert(strcmp(filename, "image.png") == 0 && archive == packfile);
    ++image_reads;
    palette[5] = 231;
    return 1;
}

int getValidInt(char *value, char *filename, char *command)
{
    assert(*filename && *command);
    return atoi(value);
}

void ScriptVariant_Clear(ScriptVariant *value)
{
    *value = (ScriptVariant){0};
}

void ScriptVariant_ChangeType(ScriptVariant *value, VARTYPE type)
{
    value->vt = type;
}

static unsigned char *make_table(unsigned char *palette, unsigned char mode)
{
    assert(((unsigned *)palette)[1] == colour32(13, 37, 99));
    if(factory_calls++ == factory_limit)
    {
        return NULL;
    }
    unsigned char *table = malloc(1);
    assert(table);
    *table = mode;
    return table;
}

#define FACTORY(name, mode) \
    unsigned char *palette_table_##name(unsigned char *palette) { return make_table(palette, mode); }
FACTORY(screen, 0)
FACTORY(multiply, 1)
FACTORY(overlay, 2)
FACTORY(hardlight, 3)
FACTORY(dodge, 4)
FACTORY(half, 5)
#undef FACTORY

@METHODS@

static int load_level_palette(s_level *level, char *name)
{
    char *filename = "test-level.txt";
    char *command = "palette";
    const char *errormessage = NULL;
    ArgList arglist = {.count = 8};
    arglist.args[1] = name;
    for(int i = 0; i < MAX_BLENDINGS; ++i)
    {
        arglist.args[i + 2] = i % 2 == 0 ? "1" : "0";
    }
    switch(CMD_LEVEL_PALETTE)
    {
@COMMAND@
    }
    return 1;
lCleanup:
    assert(errormessage);
    return 0;
}

static ScriptVariant query(s_level *handle)
{
    ScriptVariant value = {0};
    ScriptVariant *slot = &value;
    ScriptVariant **pretvar = &slot;
    switch(LEVEL_PROP_PALETTE_BLENDING_COLLECTION)
    {
@PROPERTY@
    }
    return value;
}

static void release(s_level *lv)
{
@CLEANUP@
}

int main(void)
{
    const unsigned profiles[] = {6997, 7039, 7086, 7091, 7123, 7142};
    for(size_t p = 0; p < sizeof(profiles) / sizeof(profiles[0]); ++p)
    {
        obor_profile_build = profiles[p];
        const int legacy = profiles[p] == 6997 || profiles[p] == 7039;
        s_level *lv = calloc(1, sizeof(*lv));
        assert(lv && query(lv).vt == VT_EMPTY);
        pixelformat = PIXEL_x8;
        raw_reads = image_reads = open_handles = factory_calls = 0;
        read_limit = factory_limit = -1;
        assert(load_level_palette(lv, "image.png"));
        assert(lv->numpalettes == 1 && !open_handles && !factory_calls);
        assert(raw_reads == (legacy ? 256 : 0) && image_reads == !legacy);
        if(legacy)
        {
            assert(((unsigned *)lv->palettes[0])[0] == 0);
            assert(((unsigned *)lv->palettes[0])[1] == colour32(13, 37, 99));
        }
        else
        {
            assert(lv->palettes[0][5] == 231);
        }
        ScriptVariant collection = query(lv);
        assert(collection.vt == (legacy ? VT_PTR : VT_EMPTY));
        if(legacy)
        {
            assert(collection.ptrVal == lv->obor_palette_blendings);
        }

        raw_reads = 0;
        pixelformat = PIXEL_8;
        assert(load_level_palette(lv, "palette.ACT"));
        assert(lv->numpalettes == 2 && raw_reads == 256 && !open_handles);
        assert(factory_calls == (legacy ? 3 : 0));
        if(legacy)
        {
            for(int mode = 0; mode < MAX_BLENDINGS; ++mode)
            {
                assert(!lv->obor_palette_blendings[0][mode]);
                unsigned char *table = lv->obor_palette_blendings[1][mode];
                if(mode % 2 == 0)
                {
                    assert(table && *table == mode);
                }
                else
                {
                    assert(!table);
                }
            }
        }

        raw_reads = 0;
        read_limit = 4;
        assert(!load_level_palette(lv, "palette.ACT"));
        assert(lv->numpalettes == 2 && !open_handles);
        if(legacy)
        {
            raw_reads = 0;
            read_limit = -1;
            factory_limit = factory_calls + 1;
            assert(!load_level_palette(lv, "palette.ACT"));
            assert(lv->numpalettes == 2 && lv->obor_palette_blending_count == 3);
        }
        release(lv);
    }
}
