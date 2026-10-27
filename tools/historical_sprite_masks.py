"""Compare native masked sprite pixels using independently owned encodings.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_sprite_raster import render_sprite_raster


def render_sprite_masks(*, revision, clipping, resource_hooks, assert_refusal,
                        channels, tint, native_modes, palettes, cases, perturb_pixel=False):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 2048:
        raise ValueError('Bounded native mask cases required')
    normal, masks = [], []
    for row in cases:
        if (not isinstance(row, dict) or not isinstance(row.get('mask'), list) or
                len(row['mask']) != 16 or
                any(type(v) is not int or not 0 <= v <= 255 for v in row['mask']) or
                not isinstance(row.get('source'), list) or len(row['source']) != 16 or
                any(bool(a) != bool(b) for a, b in zip(row['mask'], row['source']))):
            raise ValueError('Matching native base/mask run topology required')
        # Older readers retain the first mask row after top clipping. Identical
        # row topology keeps both source conventions inside their valid domain.
        topology = [[bool(v) for v in row['source'][y*4:y*4+4]] for y in range(4)]
        if any(shape != topology[0] for shape in topology):
            raise ValueError('Matching row topology required for historical top clipping')
        if row.get('bits') not in (16, 32):
            raise ValueError('Native mask color readers require true-color output')
        normal.append({k:v for k,v in row.items() if k != 'mask'})
        masks.append('{' + ','.join(str(v) for v in row['mask']) + '}')
    code = render_sprite_raster(revision=revision, clipping=clipping, resource_hooks=resource_hooks,
        assert_refusal=assert_refusal, palettes=palettes, cases=normal, perturb_pixel=perturb_pixel,
        composition=dict(channels=channels, tint=tint, native_modes=native_modes))

    def replace(old, new):
        nonlocal code
        if code.count(old) != 1:
            raise ValueError('One native mask integration point required: ' + old)
        code = code.replace(old, new)

    replace('struct sprite_case {', 'static const unsigned char masks[][16]={' +
            ',\n'.join(masks) + '};\nstruct sprite_case {')
    setup = '''  size_t mask_bitmap_bytes=offsetof(s_bitmap,data)+16;
  if(mask_bitmap_bytes<sizeof(s_bitmap))mask_bitmap_bytes=sizeof(s_bitmap);
  s_bitmap *mask_bitmap=calloc(1,mask_bitmap_bytes);assert(mask_bitmap);
  mask_bitmap->magic=bitmap_magic;mask_bitmap->width=mask_bitmap->height=4;
  mask_bitmap->pixelformat=PIXEL_8;
  memcpy(mask_bitmap->data,masks[active_case],16);
  unsigned char *mask_bitmap_copy=malloc(mask_bitmap_bytes);assert(mask_bitmap_copy);
  memcpy(mask_bitmap_copy,mask_bitmap,mask_bitmap_bytes);
  size_t mask_capacity=sizeof(s_sprite)+4*sizeof(int)+4*(2*4+1)+32;
  s_sprite *mask_frame=calloc(1,mask_capacity);assert(mask_frame);
@MASK_OWNER@
  unsigned mask_size=encodesprite(test->anchor[0],test->anchor[1],mask_bitmap,mask_frame);
  assert(mask_size>=offsetof(s_sprite,data) && (size_t)mask_size<=mask_capacity);
  assert(mask_frame->width==4 && mask_frame->height==4 && !mask_frame->mask && !mask_frame->palette);
  unsigned char *mask_copy=malloc(mask_size);assert(mask_copy);memcpy(mask_copy,mask_frame,mask_size);
  frame->mask=mask_frame;
'''
    owner = '''  assert(forget_calls==1 && encode_calls==1);
  expected_bitmap=mask_bitmap;expected_owner=mask_frame;owner_capacity=mask_capacity;
  forget_calls=encode_calls=0;''' if resource_hooks else ''
    replace('  unsigned char *encoded_copy=malloc(size);',
            setup.replace('@MASK_OWNER@', owner) + '  unsigned char *encoded_copy=malloc(size);')
    replace('  free(encoded_copy);free(original_bitmap);free(frame);free(bitmap);free(dest);', '''  assert(!memcmp(mask_copy,mask_frame,mask_size));
  assert(!memcmp(mask_bitmap_copy,mask_bitmap,mask_bitmap_bytes));
  free(mask_copy);free(mask_bitmap_copy);free(mask_frame);free(mask_bitmap);
  free(encoded_copy);free(original_bitmap);free(frame);free(bitmap);free(dest);''')
    return code
