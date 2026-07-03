/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* obor_padmap.h — per-game button labels for the frontend's Port Controls.
 *
 * The pad mapper is sourced from the game itself: the pak's playable
 * characters declare their inputs (`com` lines), so we can tell WHICH of
 * the engine's logical buttons this game actually uses and which
 * single-button special moves it binds. The result is published through
 * RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS, which the frontend renders in
 * Quick Menu -> Controls -> Port N Controls (and uses as labels in its own
 * remapping UI). Games that only use the generic controls get the generic
 * labels.
 *
 * Read-only, bounded work at retro_load_game time (a handful of text files
 * from the pak's table); any parse failure falls back to generic labels.
 */
#ifndef OBOR_PADMAP_H
#define OBOR_PADMAP_H

#include <stdio.h>
#include <string.h>

/* per-game evidence gathered from the player entities */
typedef struct {
    int players;              /* type player entities found */
    int uses[3];              /* attack2/attack3/attack4 used at all */
    /* single-button com target anim per button (a2/a3/a4), if unique */
    char solo[3][32];
    int solo_n[3];            /* distinct target count (0/1/2+) */
    int has_specials;         /* any com sequence declared at all */
} obor_padinfo;

/* Per-character multi-key sequences, kept for the special-move macros
 * (L2/R2/L3/R3). Steps are token bitmasks; F/B stay abstract here and get
 * resolved against the character's facing when a macro fires. */
#define OBOR_PM_TK_U (1 << 0)
#define OBOR_PM_TK_D (1 << 1)
#define OBOR_PM_TK_F (1 << 2)
#define OBOR_PM_TK_B (1 << 3)
#define OBOR_PM_TK_A (1 << 4)
#define OBOR_PM_TK_A2 (1 << 5)
#define OBOR_PM_TK_A3 (1 << 6)
#define OBOR_PM_TK_A4 (1 << 7)
#define OBOR_PM_TK_J (1 << 8)
#define OBOR_PM_TK_S (1 << 9)

#define OBOR_PM_MAXCH 24
#define OBOR_PM_MAXSEQ 4
#define OBOR_PM_MAXSTEP 8

typedef struct {
    char name[32];
    uint16_t seq[OBOR_PM_MAXSEQ][OBOR_PM_MAXSTEP];
    uint8_t slen[OBOR_PM_MAXSEQ];
    uint8_t nseq;
} obor_pm_char;

static obor_pm_char g_pm_chars[OBOR_PM_MAXCH];
static int g_pm_nchars;

static uint16_t obor_pm_token_bits(const char *tok)
{
    uint16_t bits = 0;
    char tmp[24];
    strncpy(tmp, tok, sizeof(tmp) - 1);
    tmp[sizeof(tmp) - 1] = '\0';
    for (char *part = strtok(tmp, "+"); part; part = strtok(NULL, "+")) {
        if (!strcmp(part, "u")) bits |= OBOR_PM_TK_U;
        else if (!strcmp(part, "d")) bits |= OBOR_PM_TK_D;
        else if (!strcmp(part, "f")) bits |= OBOR_PM_TK_F;
        else if (!strcmp(part, "b")) bits |= OBOR_PM_TK_B;
        else if (!strcmp(part, "a") || !strcmp(part, "a1")) bits |= OBOR_PM_TK_A;
        else if (!strcmp(part, "a2")) bits |= OBOR_PM_TK_A2;
        else if (!strcmp(part, "a3")) bits |= OBOR_PM_TK_A3;
        else if (!strcmp(part, "a4")) bits |= OBOR_PM_TK_A4;
        else if (!strcmp(part, "j") || !strcmp(part, "k")) bits |= OBOR_PM_TK_J;
        else if (!strcmp(part, "s")) bits |= OBOR_PM_TK_S;
        else return 0; /* unknown token — drop the sequence */
    }
    return bits;
}

/* ---- pak reading (same table layout the detector walks) ----------------
 * The whole file table is loaded ONCE into memory: per-file table walks
 * are brutal over slow I/O paths (wine + network shares). */

typedef struct {
    unsigned start, size;
    char name[160];
} obor_pm_ent;

static obor_pm_ent *g_pm_tab;
static int g_pm_ntab;

static void obor_pm_load_table(FILE *fp)
{
    free(g_pm_tab);
    g_pm_tab = NULL;
    g_pm_ntab = 0;
    unsigned char tail[4];
    if (fseek(fp, -4, SEEK_END) != 0 || fread(tail, 1, 4, fp) != 4)
        return;
    long end = 0;
    fseek(fp, 0, SEEK_END);
    end = ftell(fp);
    unsigned dir = tail[0] | (tail[1] << 8) | (tail[2] << 16) |
                   ((unsigned)tail[3] << 24);
    if (end < 4 || (long)dir > end - 4 || fseek(fp, (long)dir, SEEK_SET) != 0)
        return;
    /* slurp the raw table region in one read */
    size_t tab_sz = (size_t)(end - 4 - (long)dir);
    if (tab_sz > (32u << 20))
        return;
    unsigned char *raw = (unsigned char *)malloc(tab_sz);
    if (!raw || fread(raw, 1, tab_sz, fp) != tab_sz) {
        free(raw);
        return;
    }
    int cap = 256;
    g_pm_tab = (obor_pm_ent *)malloc(sizeof(obor_pm_ent) * cap);
    size_t off = 0;
    while (g_pm_tab && off + 12 <= tab_sz) {
        unsigned nlen = raw[off] | (raw[off + 1] << 8) |
                        (raw[off + 2] << 16) |
                        ((unsigned)raw[off + 3] << 24);
        unsigned st = raw[off + 4] | (raw[off + 5] << 8) |
                      (raw[off + 6] << 16) | ((unsigned)raw[off + 7] << 24);
        unsigned sz = raw[off + 8] | (raw[off + 9] << 8) |
                      (raw[off + 10] << 16) | ((unsigned)raw[off + 11] << 24);
        if (nlen < 13 || nlen > 512 || off + nlen > tab_sz)
            break;
        if (g_pm_ntab >= 65536 || st > dir || sz > dir - st)
            break;
        if (g_pm_ntab == cap) {
            cap *= 2;
            obor_pm_ent *nt =
                (obor_pm_ent *)realloc(g_pm_tab, sizeof(obor_pm_ent) * cap);
            if (!nt)
                break;
            g_pm_tab = nt;
        }
        obor_pm_ent *e = &g_pm_tab[g_pm_ntab];
        e->start = st;
        e->size = sz;
        /* normalize: lowercase, backslashes, leading slash */
        unsigned k = 0;
        for (unsigned i = 0; i < nlen - 12 && k < sizeof(e->name) - 1; i++) {
            char c = (char)raw[off + 12 + i];
            if (!c)
                break;
            if (c == '\\')
                c = '/';
            if (c >= 'A' && c <= 'Z')
                c += 32;
            if (k == 0 && c == '/')
                continue;
            e->name[k++] = c;
        }
        e->name[k] = '\0';
        g_pm_ntab++;
        off += nlen;
    }
    free(raw);
}

/* read a pak member into a NUL-terminated heap buffer (glue-side malloc) */
static char *obor_pm_read(FILE *fp, const char *path, unsigned cap)
{
    for (int i = 0; i < g_pm_ntab; i++) {
        if (strcmp(g_pm_tab[i].name, path) != 0)
            continue;
        unsigned size = g_pm_tab[i].size;
        if (size == 0 || size > cap)
            return NULL;
        char *buf = (char *)malloc(size + 1);
        if (!buf)
            return NULL;
        if (fseek(fp, (long)g_pm_tab[i].start, SEEK_SET) != 0 ||
            fread(buf, 1, size, fp) != (size_t)size) {
            free(buf);
            return NULL;
        }
        buf[size] = '\0';
        return buf;
    }
    return NULL;
}

/* ---- entity parsing ----------------------------------------------------- */

static int obor_pm_key_index(const char *tok)
{
    if (strcmp(tok, "a2") == 0)
        return 0;
    if (strcmp(tok, "a3") == 0)
        return 1;
    if (strcmp(tok, "a4") == 0)
        return 2;
    return -1;
}

static void obor_pm_scan_entity(const char *txt, obor_padinfo *info)
{
    int is_player = 0;
    obor_pm_char ch;
    memset(&ch, 0, sizeof(ch));
    const char *p = txt;
    char line[512];
    while (*p) {
        unsigned n = 0;
        while (*p && *p != '\n' && n < sizeof(line) - 1)
            line[n++] = *p++;
        while (*p == '\n' || *p == '\r')
            p++;
        line[n] = '\0';
        char *hash = strchr(line, '#');
        if (hash)
            *hash = '\0';
        char *tok[12];
        int nt = 0;
        for (char *t = strtok(line, " \t\r"); t && nt < 12;
             t = strtok(NULL, " \t\r")) {
            for (char *c = t; *c; c++)
                if (*c >= 'A' && *c <= 'Z')
                    *c += 32;
            tok[nt++] = t;
        }
        if (!nt)
            continue;
        if (strcmp(tok[0], "type") == 0 && nt > 1) {
            is_player = strcmp(tok[1], "player") == 0;
            if (!is_player)
                return; /* enemies/items don't describe the pad */
        } else if (strcmp(tok[0], "name") == 0 && nt > 1) {
            strncpy(ch.name, tok[1], sizeof(ch.name) - 1);
        } else if (strcmp(tok[0], "com") == 0 && nt > 1) {
            /* NOTE: `anim attack2` is NOT evidence the attack2 BUTTON is
             * used — attackN anims are the combo chain of the base attack
             * button. Only com sequences reference the extra buttons. */
            info->has_specials = 1;
            /* header form ends with the target anim name */
            int keys_end = nt;
            const char *target = NULL;
            if (nt > 2 && strstr(tok[nt - 1], "special")) {
                target = tok[nt - 1];
                keys_end = nt - 1;
            }
            for (int i = 1; i < keys_end; i++) {
                int bi = obor_pm_key_index(tok[i]);
                if (bi >= 0)
                    info->uses[bi] = 1;
            }
            /* single-key com on a2/a3/a4 = a direct button special */
            if (target && keys_end == 2) {
                int bi = obor_pm_key_index(tok[1]);
                if (bi >= 0) {
                    if (info->solo_n[bi] == 0) {
                        strncpy(info->solo[bi], target,
                                sizeof(info->solo[bi]) - 1);
                        info->solo_n[bi] = 1;
                    } else if (strcmp(info->solo[bi], target) != 0) {
                        info->solo_n[bi] = 2; /* varies per character */
                    }
                }
            }
            /* multi-key sequence: candidate for the macro buttons */
            if (keys_end > 2 && keys_end - 1 <= OBOR_PM_MAXSTEP &&
                ch.nseq < OBOR_PM_MAXSEQ) {
                uint16_t steps[OBOR_PM_MAXSTEP];
                int ok = 1, n = 0;
                for (int i = 1; i < keys_end && ok; i++) {
                    steps[n] = obor_pm_token_bits(tok[i]);
                    ok = steps[n] != 0;
                    n++;
                }
                if (ok) {
                    memcpy(ch.seq[ch.nseq], steps, sizeof(steps));
                    ch.slen[ch.nseq] = (uint8_t)n;
                    ch.nseq++;
                }
            }
        }
    }
    if (is_player) {
        info->players++;
        if (g_pm_nchars < OBOR_PM_MAXCH && ch.name[0]) {
            g_pm_chars[g_pm_nchars] = ch;
            g_pm_nchars++;
        }
    }
}

/* models.txt: follow know/load entries to entity files (bounded) */
static void obor_pm_collect(const char *pak_path, obor_padinfo *info)
{
    memset(info, 0, sizeof(*info));
    memset(g_pm_chars, 0, sizeof(g_pm_chars));
    g_pm_nchars = 0;
    FILE *fp = fopen(pak_path, "rb");
    if (!fp)
        return;
    obor_pm_load_table(fp);
    char *models = obor_pm_read(fp, "data/models.txt", 1 << 20);
    if (!models) {
        free(g_pm_tab);
        g_pm_tab = NULL;
        g_pm_ntab = 0;
        fclose(fp);
        return;
    }
    int scanned = 0;
    char *save = NULL;
    for (char *line = strtok_r(models, "\r\n", &save);
         line && scanned < 256; line = strtok_r(NULL, "\r\n", &save)) {
        char *hash = strchr(line, '#');
        if (hash)
            *hash = '\0';
        char *s2 = NULL;
        char *k = strtok_r(line, " \t", &s2);
        if (!k)
            continue;
        for (char *c = k; *c; c++)
            if (*c >= 'A' && *c <= 'Z')
                *c += 32;
        if (strcmp(k, "know") != 0 && strcmp(k, "load") != 0)
            continue;
        /* the path column ends in .txt; extra columns (name before it,
         * loading flags after it) vary per era — pick the .txt token */
        char *path = NULL, *t;
        while ((t = strtok_r(NULL, " \t", &s2)) != NULL) {
            size_t tl = strlen(t);
            if (tl > 4 && strcasecmp(t + tl - 4, ".txt") == 0)
                path = t;
        }
        if (!path)
            continue;
        char norm[512];
        unsigned n = 0;
        for (char *c = path; *c && n < sizeof(norm) - 1; c++) {
            char ch = *c == '\\' ? '/' : *c;
            if (ch >= 'A' && ch <= 'Z')
                ch += 32;
            if (n == 0 && ch == '/')
                continue;
            norm[n++] = ch;
        }
        norm[n] = '\0';
        if (n < 5 || strcmp(norm + n - 4, ".txt") != 0)
            continue;
        char *ent = obor_pm_read(fp, norm, 8 << 20);
        if (!ent)
            continue;
        obor_pm_scan_entity(ent, info);
        free(ent);
        scanned++;
    }
    free(models);
    free(g_pm_tab);
    g_pm_tab = NULL;
    g_pm_ntab = 0;
    fclose(fp);
}

/* ---- descriptor publication -------------------------------------------- */

static void obor_dbg(const char *fmt, ...); /* obor_debug.h (same TU) */

static void obor_padmap_apply(retro_environment_t env, const char *pak_path)
{
    static obor_padinfo info;
    obor_pm_collect(pak_path, &info);
    obor_dbg("padmap: players=%d uses=%d/%d/%d solo_n=%d/%d/%d (%s/%s/%s)",
             info.players, info.uses[0], info.uses[1], info.uses[2],
             info.solo_n[0], info.solo_n[1], info.solo_n[2],
             info.solo[0], info.solo[1], info.solo[2]);

#if defined(OBOR_NO_INPUT_DESCRIPTORS)
    return;
#endif

    /* attack2/3/4 labels depend on what the game declares */
    static char lab[3][64];
    const char *base[3] = {"Attack 2", "Attack 3", "Attack 4"};
    for (int i = 0; i < 3; i++) {
        if (info.solo_n[i] == 1)
            snprintf(lab[i], sizeof(lab[i]), "%s · %s", base[i],
                     info.solo[i]);
        else if (info.solo_n[i] > 1)
            snprintf(lab[i], sizeof(lab[i]), "%s · per-character special",
                     base[i]);
        else if (info.uses[i] || info.players == 0)
            snprintf(lab[i], sizeof(lab[i]), "%s", base[i]);
        else
            snprintf(lab[i], sizeof(lab[i]), "%s (unused in this game)",
                     base[i]);
    }

    static struct retro_input_descriptor desc[4 * 12 + 1];
    int n = 0;
    for (unsigned port = 0; port < 4; port++) {
        struct {
            unsigned id;
            const char *txt;
        } m[12] = {
            {RETRO_DEVICE_ID_JOYPAD_UP, "Up"},
            {RETRO_DEVICE_ID_JOYPAD_DOWN, "Down"},
            {RETRO_DEVICE_ID_JOYPAD_LEFT, "Left"},
            {RETRO_DEVICE_ID_JOYPAD_RIGHT, "Right"},
            {RETRO_DEVICE_ID_JOYPAD_Y, "Attack"},
            {RETRO_DEVICE_ID_JOYPAD_B, "Jump"},
            {RETRO_DEVICE_ID_JOYPAD_A, "Special (escape, costs health)"},
            {RETRO_DEVICE_ID_JOYPAD_X, lab[0]},
            {RETRO_DEVICE_ID_JOYPAD_L, lab[1]},
            {RETRO_DEVICE_ID_JOYPAD_R, lab[2]},
            {RETRO_DEVICE_ID_JOYPAD_START, "Start / Pause"},
            {RETRO_DEVICE_ID_JOYPAD_SELECT, "Menu / Quit (Esc)"},
        };
        for (int i = 0; i < 12; i++) {
            desc[n].port = port;
            desc[n].device = RETRO_DEVICE_JOYPAD;
            desc[n].index = 0;
            desc[n].id = m[i].id;
            desc[n].description = m[i].txt;
            n++;
        }
    }
    memset(&desc[n], 0, sizeof(desc[n]));
    env(RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS, desc);
}

#endif /* OBOR_PADMAP_H */
