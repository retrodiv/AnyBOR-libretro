"""Compare wrapper-initialized sprite colors with real native LUT factories.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_sprite_raster import render_sprite_raster


def render_sprite_composition(*, revision, clipping, resource_hooks, assert_refusal,
        channels, tint, native_modes, palettes, cases, perturb_pixel=False):
    if not isinstance(cases,list) or any(not isinstance(row,dict) or row.get('bits') not in (16,32) for row in cases):
        raise ValueError('True-color sprite observations required; indexed pixels have their separate contract')
    return render_sprite_raster(revision=revision,clipping=clipping,resource_hooks=resource_hooks,
        assert_refusal=assert_refusal,palettes=palettes,cases=cases,perturb_pixel=perturb_pixel,
        composition=dict(channels=channels,tint=tint,native_modes=native_modes))
