/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Integer circle rasterization from x*x + y*y = radius*radius.
 * Each octant uses the nearest integer ordinate. Axis and diagonal points
 * are emitted once, so blending does not apply twice at octant boundaries.
 */
#ifndef OBOR_CIRCLE_H
#define OBOR_CIRCLE_H
#include <stdint.h>

typedef void (*obor_circle_pixel_fn)(int, int, void *);

static void obor_circle_raster(int center_x, int center_y, int radius,
                               int width, int height,
                               obor_circle_pixel_fn pixel, void *context)
{
    int64_t cx = center_x, cy = center_y, r = radius;
    uint64_t squared;
    int64_t u, v;
    if (r < 0 || width <= 0 || height <= 0 || !pixel)
        return;
    if (cx + r < 0 || cy + r < 0 || cx - r >= width || cy - r >= height)
        return;
    squared = (uint64_t)r * (uint64_t)r;
    v = r;
    for (u = 0; u <= v; ++u) {
        uint64_t remaining = squared - (uint64_t)u * (uint64_t)u;
        /* y is rounded to the closest integer: compare the lower half-pixel
         * boundary squared with the circle equation, without floating point. */
        while (v > 0 && (uint64_t)(2 * v - 1) * (uint64_t)(2 * v - 1)
                        > 4 * remaining)
            --v;
        if (u > v)
            break;
        {
            int64_t points[8][2] = {
                {u, v}, {-u, v}, {u, -v}, {-u, -v},
                {v, u}, {-v, u}, {v, -u}, {-v, -u}
            };
            int i, j;
            for (i = 0; i < 8; ++i) {
                int64_t x = cx + points[i][0], y = cy + points[i][1];
                if (x < 0 || y < 0 || x >= width || y >= height)
                    continue;
                for (j = 0; j < i; ++j)
                    if (points[j][0] == points[i][0] &&
                        points[j][1] == points[i][1])
                        break;
                if (j == i)
                    pixel((int)x, (int)y, context);
            }
        }
    }
}
#endif
