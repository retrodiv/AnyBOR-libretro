"""Compare native sprite repeat grids and disabled/null wrapper methods.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_sprite_raster import render_sprite_raster


def render_sprite_repeats(*, revision, clipping, resource_hooks, assert_refusal,
                          channels, tint, native_modes, palettes, cases, perturb_pixel=False):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 2048:
        raise ValueError('Bounded native repeat cases required')
    normal, grids = [], []
    modes = {'enabled':0, 'disabled':1, 'null':2}
    for row in cases:
        if not isinstance(row, dict) or not isinstance(row.get('repeat'), dict):
            raise ValueError('Explicit native wrapper method and repeat grid required')
        grid = row['repeat']
        if (set(grid) != {'mode','count','span'} or not isinstance(grid.get('mode'),str) or
                grid['mode'] not in modes):
            raise ValueError('One native enabled, disabled or null wrapper method required')
        for name, low, high in (('count',-1,3), ('span',-3,3)):
            values = grid[name]
            if (not isinstance(values,list) or len(values)!=2 or
                    any(type(v) is not int or not low<=v<=high for v in values)):
                raise ValueError('Bounded native repeat counts and spans required')
        normal.append({k:v for k,v in row.items() if k != 'repeat'})
        grids.append('{' + ','.join(str(v) for v in
            (modes[grid['mode']], *grid['count'], *grid['span'])) + '}')
    code = render_sprite_raster(revision=revision, clipping=clipping, resource_hooks=resource_hooks,
        assert_refusal=assert_refusal, palettes=palettes, cases=normal, perturb_pixel=perturb_pixel,
        composition=dict(channels=channels,tint=tint,native_modes=native_modes))

    def replace(old, new):
        nonlocal code
        if code.count(old) != 1:
            raise ValueError('One native repeat integration point required: ' + old)
        code = code.replace(old,new)

    replace('struct sprite_case {', '''struct repeat_case {int mode,nx,ny,dx,dy;};
static const struct repeat_case grids[]={''' + ',\n'.join(grids) + '};\nstruct sprite_case {')
    replace('  unsigned char original_method[sizeof(method)];', '''  const struct repeat_case *grid=grids+active_case;
  method.flag=grid->mode==0;method.xrepeat=grid->nx;method.yrepeat=grid->ny;
  method.xspan=grid->dx;method.yspan=grid->dy;
  unsigned copies=grid->mode?1u:(grid->nx>0 && grid->ny>0?(unsigned)(grid->nx*grid->ny):0u);
  unsigned char original_method[sizeof(method)];''')
    replace('putsprite(test->x,test->y,frame,dest,&method);',
            'putsprite(test->x,test->y,frame,dest,grid->mode==2?NULL:&method);')
    old='r==(unsigned)test->expected_route'
    if code.count(old)!=2:
        raise ValueError('Both native repeat route expectations required')
    return code.replace(old, 'copies*(r==(unsigned)test->expected_route)')
