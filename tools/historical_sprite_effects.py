"""Compare real sprite water/plane entries with bounded independent pixels.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_sprite_raster import render_sprite_raster


def render_sprite_effects(*,revision,clipping,resource_hooks,assert_refusal,channels,tint,
                          native_modes,palettes,cases,perturb_pixel=False):
    if not isinstance(cases,list) or not 1<=len(cases)<=2048:
        raise ValueError('Bounded native procedural sprite cases required')
    normal=[];effects=[]
    for row in cases:
        if not isinstance(row,dict) or 'effect' not in row:
            raise ValueError('Complete discriminated native water/plane parameters required')
        effect=row['effect']
        if not isinstance(effect,dict) or type(effect.get('mode')) is not int:
            raise ValueError('Explicit native effect mode required')
        if effect['mode'] in (1,2):
            if (set(effect)!={'mode','amplitude','wavelength','phase'} or
                    type(effect['amplitude']) is not int or effect['amplitude'] not in (1,2,4) or
                    type(effect['wavelength']) is not int or effect['wavelength']!=4 or
                    type(effect['phase']) is not int or effect['phase'] not in (-64,0,64,128,192)):
                raise ValueError('Positive finite water amplitude and cardinal wave steps required')
            route=5;amplitude=effect['amplitude'];a=effect['wavelength'];b=0;perspective=0
        elif effect['mode']==3:
            if (set(effect)!={'mode','size','phase','perspective'} or
                    type(effect['size']) is not int or effect['size'] not in (1,2,4) or
                    type(effect['phase']) is not int or not -4<=effect['phase']<=4 or
                    type(effect['perspective']) is not int or effect['perspective'] not in (0,1,2)):
                raise ValueError('Positive finite plane sizes and native perspective required')
            route=6;amplitude=0;a=b=effect['size'];perspective=effect['perspective']
        else:raise ValueError('One supported native procedural entry required')
        if type(row.get('expected_route')) is not int or row['expected_route']!=route:
            raise ValueError('Explicit expected water or plane function entry required')
        # The base constructor validates every common pixel/method input. Its
        # ordinary route field is superseded by the explicit procedural row.
        normal.append({k:v for k,v in row.items() if k!='effect'}|dict(expected_route=3))
        effects.append('{'+','.join(map(str,(route,effect['mode'],amplitude,effect['phase'],perspective,a,b)))+'}')
    code=render_sprite_raster(revision=revision,clipping=clipping,resource_hooks=resource_hooks,
        assert_refusal=assert_refusal,palettes=palettes,cases=normal,perturb_pixel=perturb_pixel,
        composition=dict(channels=channels,tint=tint,native_modes=native_modes))
    declarations='''struct effect_case {int route,mode,amplitude,phase,perspective;float a,b;};
static const struct effect_case effects[]={'''+',\n'.join(effects)+'};\n'
    marker='struct sprite_case {'
    if code.count(marker)!=1:raise ValueError('One native sprite case declaration required')
    code=code.replace(marker,declarations+marker)
    code=code.replace('route_counts[5]','route_counts[7]').replace('r<5;','r<7;')
    marker=' else if(function==(void*)gfx_draw_rotate)++route_counts[4];'
    if code.count(marker)!=1:raise ValueError('Actual native function entry observer required')
    code=code.replace(marker,marker+'''
 else if(function==(void*)gfx_draw_water)++route_counts[5];
 else if(function==(void*)gfx_draw_plane)++route_counts[6];''')
    code=code.replace('test->expected_route','effects[active_case].route')
    marker='  unsigned char original_method[sizeof(method)];'
    if code.count(marker)!=1:raise ValueError('One immutable native method observation required')
    initialization='''  const struct effect_case *effect=effects+active_case;
  method.water.watermode=effect->mode;method.water.wavetime=effect->phase;
  if(effect->mode==3){
   method.water.beginsize=effect->a;method.water.endsize=effect->b;
   method.water.perspective=effect->perspective;
  }else{
   method.water.amplitude=effect->amplitude;method.water.wavelength=effect->a;
   method.water.wavespeed=0.0f;
  }
'''
    return code.replace(marker,initialization+marker)
