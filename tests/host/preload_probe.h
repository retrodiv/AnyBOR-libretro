/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Opt-in authored-fixture probe. Each fixture model ends with one safely
 * ignored optional attack entry. Its existing flushed warning is an indirect
 * parser-end witness: parent load directives precede child/image/warning work.
 * Read the engine log after each retro_run so frontend tail limits cannot merge
 * witnesses. No hook or diagnostic mode is installed in the core. */
#ifndef OBOR_PRELOAD_PROBE_H
#define OBOR_PRELOAD_PROBE_H

static long preload_log_offset;
static unsigned preload_boot_checks, preload_level_checks, preload_load_checks;
static unsigned preload_seen_models;
static int preload_level_active, preload_level_finished;
static int preload_level_end_frame = -1;
static unsigned char *preload_reference;
static size_t preload_reference_size;
static unsigned char *preload_scratch;
static size_t preload_scratch_size;

static void preload_probe_restart(void)
{
    preload_log_offset = 0;
    preload_level_active = preload_level_finished = 0;
    preload_level_end_frame = -1;
    preload_seen_models = 0;
    free(preload_reference);
    preload_reference = NULL;
    preload_reference_size = 0;
    free(preload_scratch);
    preload_scratch = NULL;
    preload_scratch_size = 0;
}

static int preload_probe_after_run(size_t (*capacity)(void),
                                   bool (*save)(void *, size_t),
                                   bool (*load)(const void *, size_t), int ready)
{
    const char *path = getenv("OBOR_PRELOAD_PROBE_LOG");
    if (!path) return 1;
    FILE *log = fopen(path, "rb");
    if (!log) return 1; /* Packed-content preparation has not reached the engine. */
    unsigned completed = 0;
    static const char *models[] = {
        "block", "BootParent", "BootChildOne", "BootChildTwo",
        "LevelParent", "LevelChildOne", "LevelChildTwo"
    };
    char line[1024];
    if (fseek(log, preload_log_offset, SEEK_SET)) { fclose(log); return 0; }
    while (fgets(line, sizeof(line), log)) {
        if (strstr(line, "Level Loading:")) preload_level_active = 1;
        if (strstr(line, "Warning: Ignoring out-of-range attack type 'normal2147483647'")) {
            int found = 0;
            for (unsigned i = 0; i < sizeof(models) / sizeof(models[0]); ++i) {
                char witness[256];
                snprintf(witness, sizeof(witness),
                         "Warning: Ignoring out-of-range attack type 'normal2147483647' "
                         "in data/chars/%s.txt (offense; maxattacktypes ", models[i]);
                if (!strstr(line, witness)) continue;
                if (preload_seen_models & (1u << i)) {
                    fprintf(stderr, "repeated authored parser witness: %s\n", models[i]);
                    fclose(log);
                    return 0;
                }
                preload_seen_models |= 1u << i;
                ++completed;
                found = 1;
                break;
            }
            if (!found) {
                fprintf(stderr, "unknown authored parser witness: %s", line);
                fclose(log);
                return 0;
            }
        }
        if (strstr(line, "Level Loaded:")) {
            preload_level_active = 0;
            preload_level_finished = 1;
            preload_level_end_frame = g_frame;
        }
    }
    preload_log_offset = ftell(log);
    int read_error = ferror(log);
    int close_error = fclose(log);
    if (read_error || close_error || preload_log_offset < 0) return 0;
    if (completed > 1) {
        fprintf(stderr, "multiple model parser-end witnesses without a frontend return: %u\n", completed);
        return 0;
    }
    if (completed && (!ready || preload_level_active) &&
        !getenv("OBOR_PRELOAD_PROBE_CONTROL")) {
        size_t size = capacity();
        if (!size) return 0;
        if (size > preload_scratch_size) {
            unsigned char *grown = realloc(preload_scratch, size);
            if (!grown) return 0;
            preload_scratch = grown;
            preload_scratch_size = size;
        }
        unsigned char *probe = preload_scratch;
        memset(probe, 0xa5, size);
        int ok = !save(probe, size) && capacity() == size;
        for (size_t i = 0; ok && i < size; ++i) ok = probe[i] == 0xa5;
        if (!ok) { fprintf(stderr, "preload capture changed a refused buffer\n"); return 0; }
        if (preload_reference) {
            if (load(preload_reference, preload_reference_size) || capacity() != size) {
                fprintf(stderr, "preload accepted a previously valid state\n");
                return 0;
            }
            ++preload_load_checks;
        }
        if (!ready) ++preload_boot_checks;
        else ++preload_level_checks;
    }
    if (ready && !preload_level_active &&
        (!preload_reference || preload_level_finished == 1)) {
        size_t size = capacity();
        unsigned char *probe = size ? malloc(size) : NULL;
        if (!probe || !save(probe, size) || !load(probe, size)) {
            free(probe);
            fprintf(stderr, "state did not recover after preload cleanup\n");
            return 0;
        }
        free(preload_reference);
        preload_reference = probe;
        preload_reference_size = size;
        if (preload_level_finished) preload_level_finished = 2;
    }
    return 1;
}

static int preload_probe_finish(void)
{
    if (!getenv("OBOR_PRELOAD_PROBE_LOG")) return 1;
    printf("preload_probe boot=%u level=%u refused_load=%u recovered=%d level_end=%d\n",
           preload_boot_checks, preload_level_checks, preload_load_checks,
           preload_level_finished == 2, preload_level_end_frame);
    int trace_first = -1, trace_last = -1;
    const char *trace = getenv("OBOR_REPLAY_TRACE");
    if (trace && sscanf(trace, "%d,%d", &trace_first, &trace_last) != 2) return 0;
    int control = getenv("OBOR_PRELOAD_PROBE_CONTROL") != NULL;
    int ok = preload_seen_models == 127 && preload_level_finished == 2 &&
             (trace_first < 0 || preload_level_end_frame < trace_first) && (control ||
             (preload_boot_checks >= 3 && preload_level_checks >= 3 &&
              preload_load_checks >= 3));
    preload_probe_restart();
    return ok;
}
#endif
