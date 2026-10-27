"""Compare real queued sprite, packed-screen and primitive composition.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from historical_sprite_raster import render_sprite_raster


def render_sprite_queue(*, queue_source, method_api, expected_capacity, revision, clipping,
                        resource_hooks, assert_refusal, channels, tint, native_modes,
                        palettes, cases, perturb_pixel=False):
    if (not isinstance(queue_source,str) or not queue_source.startswith('/') or
            not queue_source.endswith('.c') or len(queue_source)>4096 or
            any(c in queue_source for c in ('\0','\r','\n')) or type(method_api) is not bool or
            type(expected_capacity) is not int or not 1<=expected_capacity<=4096 or
            type(native_modes) is not int or native_modes not in (6,7) or
            not isinstance(cases,list) or not 1<=len(cases)<=2048):
        raise ValueError('Complete native queue unit, API, capacity and bounded images required')
    kinds={'sprite':0,'screen':1,'box':2,'line':3,'pixel':4}
    controls=[];normal=[]
    for row in cases:
        if not isinstance(row,dict) or not isinstance(row.get('queue'),dict):
            raise ValueError('Explicit native queue controls required')
        q=row['queue']
        if (set(q)!={'layers','lock_prefix','newonly','minz','maxz','offset','order','routes'} or
                not isinstance(q['layers'],list) or not 1<=len(q['layers'])<=4 or
                type(q['lock_prefix']) is not int or not -1<=q['lock_prefix']<=len(q['layers']) or
                type(q['newonly']) is not bool or
                any(type(q[k]) is not int or not -8<=q[k]<=8 for k in ('minz','maxz')) or
                q['minz']>q['maxz'] or not isinstance(q['offset'],list) or len(q['offset'])!=2 or
                any(type(v) is not int or not -1<=v<=1 for v in q['offset']) or
                not isinstance(q['order'],list) or any(type(v) is not int for v in q['order']) or
                sorted(q['order'])!=list(range(len(q['layers']))) or
                not isinstance(q['routes'],list) or len(q['routes'])!=11 or
                any(type(v) is not int or not 0<=v<=4 for v in q['routes']) or q['routes'][10]!=1):
            raise ValueError('Bounded native queue filtering, order and actual route counts required')
        if row.get('scale')!=[256,256] or row.get('shift')!=0 or row.get('angle')!=0 or row.get('fill')!=0:
            raise ValueError('Queue integration uses unscaled native images; transforms have separate contracts')
        bits=row.get('bits')
        if (type(bits) is not int or bits not in (8,16,32) or
                any(type(row.get(k)) is not int or not -16<=row[k]<=16 for k in ('x','y'))):
            raise ValueError('Native queued pixel format and finite coordinates required')
        maximum={8:255,16:65535,32:0xffffff}[bits]
        layers=[]
        for layer in q['layers']:
            if (not isinstance(layer,dict) or set(layer)!={'kind','offset','z','sortid','method','alpha','remap','rgb','tint','color'} or
                    not isinstance(layer['kind'],str) or layer['kind'] not in kinds or
                    not isinstance(layer['offset'],list) or len(layer['offset'])!=2 or
                    any(type(v) is not int or not -1<=v<=1 for v in layer['offset']) or
                    any(type(layer[k]) is not int or not -8<=layer[k]<=8 for k in ('z','sortid')) or
                    layer['kind'] not in ('sprite','screen') and layer['sortid']!=0 or
                    type(layer['method']) is not int or layer['method'] not in (-1,0,1) or
                    type(layer['alpha']) is not int or not 0<=layer['alpha']<=native_modes or
                    type(layer['remap']) is not bool or type(layer['color']) is not int or
                    not 0<=layer['color']<=maximum or not isinstance(layer['rgb'],list) or len(layer['rgb'])!=3 or
                    any(type(v) is not int or not 0<=v<=255 for v in layer['rgb']) or
                    not isinstance(layer['tint'],list) or len(layer['tint'])!=2 or
                    any(type(v) is not int for v in layer['tint']) or not 0<=layer['tint'][0]<=6 or
                    not 0<=layer['tint'][1]<=maximum):
                raise ValueError('Complete bounded native layer and copied method required')
            if layer['kind'] in ('pixel','line'):
                x=row.get('x',-100)+layer['offset'][0]+q['offset'][0]
                y=row.get('y',-100)+layer['offset'][1]+q['offset'][1]
                end=2 if layer['kind']=='line' else 0
                if not(0<=x<=x+end<12 and 0<=y<=y+end<10):
                    raise ValueError('Displaced primitive endpoints must stay in their original valid domain')
            values=[kinds[layer['kind']],*layer['offset'],layer['z'],layer['sortid'],layer['method'],layer['alpha'],int(layer['remap']),layer['color']]
            layers.append('{'+','.join(map(str,values))+',{' + ','.join(map(str,layer['rgb']))+'},{'+','.join(map(str,layer['tint']))+'}}')
        values=[len(layers),q['lock_prefix'],int(q['newonly']),q['minz'],q['maxz'],*q['offset']]
        controls.append('{'+','.join(map(str,values))+',{' + ','.join(map(str,q['order']))+'},{'+','.join(map(str,q['routes']))+'},{'+','.join(layers)+'}}')
        normal.append({k:v for k,v in row.items() if k!='queue'})
    code=render_sprite_raster(revision=revision,clipping=clipping,resource_hooks=resource_hooks,
        assert_refusal=assert_refusal,palettes=palettes,cases=normal,perturb_pixel=perturb_pixel,
        composition=dict(channels=channels,tint=tint,native_modes=native_modes))

    def replace(old,new):
        nonlocal code
        if code.count(old)!=1:raise ValueError('One complete queue integration point required: '+old)
        code=code.replace(old,new)

    replace('#include "sprite.c"','#include "sprite.c"\n#include "screen.h"\n#include "draw.h"\n#include '+json.dumps(queue_source))
    code=code.replace('route_counts[5]','route_counts[11]').replace('r<5;','r<11;')
    extra='''
 else if(function==(void*)putsprite)++route_counts[5];
 else if(function==(void*)putscreen)++route_counts[6];
 else if(function==(void*)spriteq_draw)++route_counts[10];'''
    for slot,names in ((7,['putbox'] if method_api else ['drawbox','drawbox16','drawbox32']),
                       (8,['putline'] if method_api else ['line','line16','line32']),
                       (9,['putpixel'] if method_api else ['putpixel','putpixel16','putpixel32'])):
        extra+='\n else if('+ ' || '.join('function==(void*)'+name for name in names)+')++route_counts['+str(slot)+'];'
    marker=' else if(function==(void*)gfx_draw_rotate)++route_counts[4];'
    replace(marker,marker+extra)
    declarations='''struct queue_layer {int kind,dx,dy,z,sortid,method,alpha,remap;unsigned color,rgb[3],tint[2];};
struct queue_control {int count,lock_prefix,newonly,minz,maxz,dx,dy,order[4];unsigned routes[11];struct queue_layer layers[4];};
static const struct queue_control controls[]={'''+',\n'.join(controls)+'};\n'
    replace('struct sprite_case {',declarations+'struct sprite_case {')
    marker='  unsigned char original_method[sizeof(method)];'
    setup='''  const struct queue_control *control=controls+active_case;
  assert(MAXQSPRITES==@CAPACITY@);spriteq_unlock();spriteq_clear();assert(spritequeue_len==0);
  s_screen *source_screen=owned_screen(test->bits);source_screen->width=source_screen->height=4;
  for(unsigned p=0;p<16;++p)store_pixel(source_screen,test->bits,p,test->bits==8?test->source[p]:
   test->bits==16?palette_16_original[test->source[p]]:palette_32_original[test->source[p]]);
  size_t source_bytes=offsetof(s_screen,data)+(size_t)120*(test->bits/8);
  if(source_bytes<sizeof(s_screen))source_bytes=sizeof(s_screen);
  unsigned char *source_copy=malloc(source_bytes);assert(source_copy);memcpy(source_copy,source_screen,source_bytes);
  s_drawmethod methods[4];
  for(int i=0;i<control->count;++i){
   if(control->lock_prefix==i)spriteq_lock();
   const struct queue_layer *layer=control->layers+i;
   methods[i]=method;methods[i].flag=layer->method==1;methods[i].alpha=layer->alpha;
   methods[i].table=layer->remap?(test->bits==8?palette_8_override:
    test->bits==16?(unsigned char*)palette_16_override:(unsigned char*)palette_32_override):NULL;
@COLOR@
   s_drawmethod *selected=layer->method<0?NULL:methods+i;
   int x=test->x+layer->dx,y=test->y+layer->dy;
   if(layer->kind==0)spriteq_add_frame(x,y,layer->z,frame,selected,layer->sortid);
   else if(layer->kind==1)spriteq_add_screen(x,y,layer->z,source_screen,selected,layer->sortid);
   else if(layer->kind==2)spriteq_add_box(x,y,2,2,layer->z,(int)layer->color,@PRIMITIVE@);
   else if(layer->kind==3)spriteq_add_line(x,y,x+2,y+2,layer->z,(int)layer->color,@PRIMITIVE@);
   else spriteq_add_dot(x,y,layer->z,(int)layer->color,@PRIMITIVE@);
   assert(spritequeue_len==i+1 && queue[i].z==layer->z);
   if(selected)assert(!memcmp(&queue[i].drawmethod,selected,sizeof(*selected)));
   else assert(!queue[i].drawmethod.flag);
   memset(methods+i,0,sizeof(methods[i]));
  }
  if(control->lock_prefix==control->count)spriteq_lock();
  qstruct retained[4];memcpy(retained,queue,(size_t)control->count*sizeof(*queue));
'''
    # Legacy primitive enqueue takes alpha, constructing its own method. Its
    # queue record is checked separately from frame/screen method copies.
    if not method_api:
        setup=setup.replace('if(selected)assert(!memcmp(&queue[i].drawmethod,selected,sizeof(*selected)));\n   else assert(!queue[i].drawmethod.flag);', '''if(layer->kind<=1){
    if(selected)assert(!memcmp(&queue[i].drawmethod,selected,sizeof(*selected)));
    else assert(!queue[i].drawmethod.flag);
   }else{int alpha=selected && selected->flag?selected->alpha:0;
    assert(queue[i].drawmethod.alpha==alpha && !!queue[i].drawmethod.flag==(alpha>0));}''')
    color=''
    if channels:color+='   methods[i].channelr=layer->rgb[0];methods[i].channelg=layer->rgb[1];methods[i].channelb=layer->rgb[2];\n'
    if tint:color+='   methods[i].tintmode=layer->tint[0];methods[i].tintcolor=layer->tint[1];\n'
    setup=setup.replace('@CAPACITY@',str(expected_capacity)).replace('@COLOR@',color).replace('@PRIMITIVE@','selected' if method_api else 'selected && selected->flag?selected->alpha:0')
    replace(marker,setup+marker)
    replace('  putsprite(test->x,test->y,frame,dest,&method);tracking=0;',
            '  spriteq_draw(dest,control->newonly,control->minz,control->maxz,control->dx,control->dy);tracking=0;')
    old='r==(unsigned)test->expected_route'
    if code.count(old)!=2:raise ValueError('Both native queue route expectations required')
    code=code.replace(old,'control->routes[r]')
    marker='  free(encoded_copy);free(original_bitmap);free(frame);free(bitmap);free(dest);'
    replace(marker,'''  assert(!memcmp(retained,queue,(size_t)control->count*sizeof(*queue)));
  assert(!memcmp(source_copy,source_screen,source_bytes));
  for(int i=0;i<control->count;++i)assert(order[i]==queue+control->order[i]);
  spriteq_clear();assert(spritequeue_len==(control->lock_prefix<0?0:control->lock_prefix));
  spriteq_unlock();spriteq_clear();assert(!spritequeue_len && !spriteq_islocked());
  free(source_copy);free(source_screen);
'''+marker)
    return code
