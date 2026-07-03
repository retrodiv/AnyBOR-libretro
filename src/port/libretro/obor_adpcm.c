/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * IMA/DVI ADPCM with the OpenBOR stream convention: high nibble first,
 * and, for stereo, one left/right pair per byte. Lengths are bytes.
 * The step table and index transitions are the codec's numeric parameters.
 */
#include <limits.h>
#include <stddef.h>
#if __has_include("adpcm.h")
#include "adpcm.h"

static int predictor[2];
static unsigned step_index[2];
static const unsigned short quantizer[89] = {
    7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,
    50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,
    230,253,279,307,337,371,408,449,494,544,598,658,724,796,
    876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,
    2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,
    8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,
    22385,24623,27086,29794,32767
};

static short decode_nibble(unsigned code, unsigned channel)
{
    unsigned step = quantizer[step_index[channel]];
    int magnitude = (int)(step >> 3);
    unsigned bit;
    for (bit = 0; bit != 3; ++bit)
        if (code & (4u >> bit))
            magnitude += (int)(step >> bit);
    predictor[channel] += (code & 8) ? -magnitude : magnitude;
    if (predictor[channel] < -32768) predictor[channel] = -32768;
    if (predictor[channel] > 32767) predictor[channel] = 32767;
    {
        unsigned level = code & 7;
        int next = (int)step_index[channel] + (level < 4 ? -1 : 2 * ((int)level - 3));
        step_index[channel] = next < 0 ? 0u : next > 88 ? 88u : (unsigned)next;
    }
    return (short)predictor[channel];
}

static unsigned encode_sample(short sample, unsigned channel)
{
    int distance = (int)sample - predictor[channel];
    unsigned code = distance < 0 ? 8u : 0u;
    unsigned step = quantizer[step_index[channel]], bit;
    if (distance < 0) distance = -distance;
    for (bit = 0; bit != 3; ++bit) {
        unsigned threshold = step >> bit;
        if ((unsigned)distance >= threshold) {
            code |= 4u >> bit;
            distance -= (int)threshold;
        }
    }
    (void)decode_nibble(code, channel);
    return code;
}

void adpcm_reset(void)
{
    predictor[0] = predictor[1] = 0;
    step_index[0] = step_index[1] = 0;
}

short adpcm_valprev(int channel)
{
    return (unsigned)channel < 2 ? (short)predictor[channel] : 0;
}

char adpcm_index(int channel)
{
    return (unsigned)channel < 2 ? (char)step_index[channel] : 0;
}

void adpcm_loop_reset(int channel, short value, char index)
{
    if ((unsigned)channel < 2) {
        predictor[channel] = value;
        step_index[channel] = (unsigned char)index > 88 ? 88u : (unsigned char)index;
    }
}

int adpcm_encode(short *input, unsigned char *output, int bytes, int channels)
{
    int sample, samples;
    if (!input || !output || bytes < (channels == 2 ? 4 : 2)) return 0;
    samples = channels == 2 ? (bytes / 4) * 2 : bytes / 2;
    for (sample = 0; sample < samples; ++sample) {
        unsigned channel = channels == 2 ? (unsigned)sample & 1u : 0;
        unsigned code = encode_sample(input[sample], channel);
        if (!(sample & 1)) output[sample / 2] = (unsigned char)(code << 4);
        else output[sample / 2] |= (unsigned char)code;
    }
    return (samples + 1) / 2;
}

int adpcm_decode(unsigned char *input, short *output, int bytes, int channels)
{
    int byte;
    if (!input || !output || bytes < 1 || bytes > INT_MAX / 4) return 0;
    for (byte = 0; byte < bytes; ++byte) {
        unsigned code = input[byte];
        output[2 * byte] = decode_nibble(code >> 4, 0);
        output[2 * byte + 1] = decode_nibble(code & 15, channels == 2 ? 1u : 0u);
    }
    return bytes * 4;
}

#endif /* legacy ADPCM API */
