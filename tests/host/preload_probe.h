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
static unsigned preload_seen_models, preload_stale_checks;
static int preload_level_active, preload_level_finished;
static int preload_level_end_frame = -1;
static unsigned char *preload_reference;
static size_t preload_reference_size;
static unsigned char *preload_scratch;
static size_t preload_scratch_size;
static unsigned char *preload_reverse_state[2];
static uint32_t preload_reverse_video[2], preload_reverse_audio[2];
static int preload_reverse_frame[2];
static unsigned preload_reverse_pushes, preload_reverse_refused, preload_reverse_checks;
static unsigned preload_reverse_wait_frames;

static uint32_t preload_video_hash(void)
{
    uint32_t hash = 2166136261u;
    for (unsigned y = 0; g_fb && y < g_fh; ++y) {
        const uint32_t *row = (const uint32_t *)((const uint8_t *)g_fb + y * g_fpitch);
        for (unsigned x = 0; x < g_fw; ++x) hash = (hash ^ row[x]) * 16777619u;
    }
    return hash;
}

/* Keep just the two latest complete snapshots before a real level preload.
 * Once loading has finished, pop across its boundary with the frontend's
 * rewind throttle, then restore the post-load world for the PCM control.
 * Three buffers stay within the ordinary 256 MiB history budget. */
static int preload_reverse_after_run(size_t (*capacity)(void),
                                     bool (*save)(void *, size_t),
                                     bool (*load)(const void *, size_t),
                                     void (*run)(void), int ready)
{
    if (!ready || preload_reverse_checks) return 1;
    size_t size = capacity();
    if (!size || size > (256u << 20) / 3) return 0;
    if (!preload_scratch) {
        preload_scratch = malloc(size);
        preload_scratch_size = size;
        for (unsigned i = 0; i < 2; ++i) preload_reverse_state[i] = malloc(size);
        if (!preload_scratch || !preload_reverse_state[0] || !preload_reverse_state[1]) return 0;
    }
    if (size != preload_scratch_size) return 0;
    int captured = save(preload_scratch, size);
    if (!captured) {
        ++preload_reverse_refused;
        return 1;
    }
    if (!preload_level_finished) {
        unsigned slot = preload_reverse_pushes++ % 2;
        memcpy(preload_reverse_state[slot], preload_scratch, size);
        preload_reverse_video[slot] = preload_video_hash();
        preload_reverse_audio[slot] = g_frame_audio_hash;
        preload_reverse_frame[slot] = g_frame;
        return 1;
    }
    if (preload_reverse_pushes < 2 || preload_reverse_refused < 3) return 0;
    uint32_t post_video = preload_video_hash(), post_audio = g_frame_audio_hash;
    int previous = g_frame;
    for (unsigned step = 0; step < 2; ++step) {
        unsigned slot = (preload_reverse_pushes - 1 - step) % 2;
        if (preload_reverse_frame[slot] >= previous ||
            !load(preload_reverse_state[slot], size)) {
            fprintf(stderr, "preload rewind rejected complete snapshot step=%u frame=%d\n",
                    step, preload_reverse_frame[slot]);
            return 0;
        }
        previous = preload_reverse_frame[slot];
        g_reverse_presentation = 1;
        g_frame_audio_hash = 2166136261u;
        run();
        if (preload_video_hash() != preload_reverse_video[slot] ||
            g_frame_audio_hash != preload_reverse_audio[slot]) {
            fprintf(stderr, "preload rewind advanced complete snapshot step=%u frame=%d\n",
                    step, previous);
            return 0;
        }
        ++preload_reverse_checks;
        printf("preload_reverse step=%u frame=%d video=MATCH audio=MATCH\n", step, previous);
        if (!step) {
            /* Stock rewind can pop failed-capture entries between two valid
             * states. These refusals must not restart forward loading while
             * the frontend still reports reverse playback. */
            uint32_t magic;
            memcpy(&magic, preload_reverse_state[slot], sizeof(magic));
            memset(preload_reverse_state[slot], 0, sizeof(magic));
            for (unsigned gap = 0; gap < 3; ++gap) {
                if (load(preload_reverse_state[slot], size)) return 0;
                g_frame_audio_hash = 2166136261u;
                run();
                if (preload_video_hash() != preload_reverse_video[slot] ||
                    g_frame_audio_hash != preload_reverse_audio[slot]) {
                    fprintf(stderr, "failed rewind entry advanced the engine gap=%u\n", gap);
                    return 0;
                }
            }
            memcpy(preload_reverse_state[slot], &magic, sizeof(magic));
            puts("preload_reverse_failed_entries=3 unchanged=1");
        }
    }
    if (!load(preload_scratch, size)) return 0;
    g_frame_audio_hash = 2166136261u;
    run();
    g_reverse_presentation = 0;
    if (preload_video_hash() != post_video || g_frame_audio_hash != post_audio) return 0;
    preload_level_finished = 2;
    return 1;
}

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
    for (unsigned i = 0; i < 2; ++i) {
        free(preload_reverse_state[i]);
        preload_reverse_state[i] = NULL;
    }
    preload_reverse_pushes = preload_reverse_refused = preload_reverse_checks = 0;
    preload_reverse_wait_frames = 0;
}

static int preload_probe_after_run(size_t (*capacity)(void),
                                   bool (*save)(void *, size_t),
                                   bool (*load)(const void *, size_t),
                                   void (*run)(void), int ready)
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
    if (getenv("OBOR_PRELOAD_REWIND_PROBE"))
        return preload_reverse_after_run(capacity, save, load, run, ready);
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
        int stale = preload_reference && preload_reference_size == size;
        if (stale) memcpy(probe, preload_reference, size);
        else memset(probe, 0xa5, size);
        int ok = !save(probe, size) && capacity() == size;
        for (size_t i = 0; ok && i < size; ++i)
            ok = probe[i] == (i < sizeof(uint32_t) ? 0 :
                             stale ? preload_reference[i] : 0xa5);
        if (!ok) { fprintf(stderr, "refused preload capture did not invalidate only its header\n"); return 0; }
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
        if (preload_scratch && load(preload_scratch, preload_scratch_size)) {
            fprintf(stderr, "refused capture loaded stale bytes after preload cleanup\n");
            return 0;
        }
        if (preload_scratch) ++preload_stale_checks;
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
    printf("preload_probe boot=%u level=%u refused_load=%u recovered=%d level_end=%d stale_refused=%u\n",
           preload_boot_checks, preload_level_checks, preload_load_checks,
           preload_level_finished == 2, preload_level_end_frame, preload_stale_checks);
    int trace_first = -1, trace_last = -1;
    const char *trace = getenv("OBOR_REPLAY_TRACE");
    if (trace && sscanf(trace, "%d,%d", &trace_first, &trace_last) != 2) return 0;
    int control = getenv("OBOR_PRELOAD_PROBE_CONTROL") != NULL;
    int reverse = getenv("OBOR_PRELOAD_REWIND_PROBE") != NULL;
    printf("preload_reverse_checks=%u refused_captures=%u\n",
           preload_reverse_checks, preload_reverse_refused);
    printf("preload_reverse_initial_wait_frames=%u\n", preload_reverse_wait_frames);
    int ok = preload_seen_models == 127 && preload_level_finished == 2 &&
             (trace_first < 0 || preload_level_end_frame < trace_first) &&
             (reverse ? preload_reverse_checks == 2 && preload_reverse_refused >= 3 &&
                        preload_reverse_wait_frames > 0 : (control ||
             (preload_boot_checks >= 3 && preload_level_checks >= 3 &&
              preload_load_checks >= 3 && preload_stale_checks >= 2)));
    preload_probe_restart();
    return ok;
}
#endif
