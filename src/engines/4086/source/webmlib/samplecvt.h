/* AnyBOR modification record: 2026-10-19.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Import the native 4153 media component, retaining its upstream authorship
 * and license notices.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2015 OpenBOR Team
 */

#ifndef SAMPLECVT_H
#define SAMPLECVT_H

#include <ogg/os_types.h>

/**
 * Converts decoded samples to signed 16-bit PCM.
 * @param pcm the raw samples
 * @param buffer a buffer for the decoded samples
 * @param samples the number of samples
 * @param channels the number of channels (1 for mono, 2 for stereo)
 */
#if TREMOR
void pack_samples(ogg_int32_t **pcm, short *buffer, int samples, int channels);
#else // libvorbis
void pack_samples(float **pcm, short *buffer, int samples, int channels);
#endif

#endif
