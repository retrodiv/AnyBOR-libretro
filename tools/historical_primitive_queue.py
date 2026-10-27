"""Compose real primitive pixels through the complete native queue unit.

The included unit exposes its native queue records for retention checks.
Screen and sprite branches are explicit refusals, not rendering substitutes.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from historical_primitive_raster import render_primitive_raster


def render_primitive_queue(*, queue_source, queue_api, expected_capacity, controls,
                           perturb_queue=False, **raster_options):
    if (not isinstance(queue_source, str) or not queue_source.startswith('/') or
            not queue_source.endswith('.c') or len(queue_source) > 4096 or
            any(c in queue_source for c in ('\0', '\r', '\n')) or
            type(queue_api) is not bool or type(perturb_queue) is not bool or
            raster_options.get('method_api') is not queue_api or
            type(expected_capacity) is not int or not 1 <= expected_capacity <= 4096 or
            not isinstance(controls, list) or len(controls) != len(raster_options.get('cases', []))):
        raise ValueError('Explicit complete queue unit, API, capacity and per-image controls required')
    code = render_primitive_raster(**raster_options)
    rows = []
    for case, control in zip(raster_options['cases'], controls):
        fields = {'layers', 'lock_prefix', 'newonly', 'minz', 'maxz', 'dx', 'dy'}
        if (not isinstance(control, dict) or set(control) != fields or
                not isinstance(control['layers'], list) or not 1 <= len(control['layers']) <= 4 or
                type(control['lock_prefix']) is not int or not -1 <= control['lock_prefix'] <= len(control['layers']) or
                type(control['newonly']) is not bool or
                any(type(control[k]) is not int or not -8 <= control[k] <= 8 for k in ('minz', 'maxz')) or
                control['minz'] > control['maxz'] or
                any(type(control[k]) is not int or not -4 <= control[k] <= 4 for k in ('dx', 'dy'))):
            raise ValueError('Bounded layers, locking, depth interval and displacement required')
        layers = []
        maximum = {8: 255, 16: 65535, 32: 0xffffff}[case['bits']]
        for layer in control['layers']:
            if (not isinstance(layer, dict) or set(layer) != {'z', 'color'} or
                    type(layer['z']) is not int or not -8 <= layer['z'] <= 8 or
                    type(layer['color']) is not int or not 0 <= layer['color'] <= maximum):
                raise ValueError('Independent native depth and bounded layer color required')
            layers.append('{' + str(layer['z']) + ',' + str(layer['color']) + '}')
        if case['operation'] in ('line', 'pixel'):
            points = [case['coords'][:2]] + ([case['coords'][2:]] if case['operation'] == 'line' else [])
            if any(not (0 <= x + control['dx'] < case['width'] and
                        0 <= y + control['dy'] < case['height']) for x, y in points):
                raise ValueError('Displaced native point/line controls must remain in-image')
        rows.append('{' + ','.join(map(str, [len(layers), control['lock_prefix'], int(control['newonly']),
                                           control['minz'], control['maxz'], control['dx'], control['dy']])) +
                    ',{' + ','.join(layers) + '}}')
    include = '#include "draw.h"\n'
    if code.count(include) != 1:
        raise ValueError('One maintained native drawing include required')
    code = code.replace(include, include + '#include ' + json.dumps(queue_source) + '\n')
    start = code.index('static void invoke(')
    end = code.index('\nint main(void){', start)
    queue_driver = r'''
struct queue_layer {int z;unsigned color;};
struct queue_control {int count,lock_prefix,newonly,minz,maxz,dx,dy;struct queue_layer layers[4];};
static const struct queue_control controls[]={@CONTROLS@};
/* These unexercised branch providers refuse. They do not validate sprites,
 * screen composition, lazy loading or any engine allocation path. */
void putsprite(int x,int y,s_sprite *frame,s_screen *screen,s_drawmethod *method){
 (void)x;(void)y;(void)frame;(void)screen;(void)method;fprintf(stderr,"Unexpected queued sprite branch\n");abort();
}
void putscreen(s_screen *dest,s_screen *src,int x,int y,s_drawmethod *method){
 (void)dest;(void)src;(void)x;(void)y;(void)method;fprintf(stderr,"Unexpected queued screen branch\n");abort();
}
static void add_primitive(const struct raster_case *test,const struct queue_layer *layer,s_drawmethod *method){
 int x=test->coords[0],y=test->coords[1],a=test->coords[2],b=test->coords[3];
#if @QUEUE_API@
 if(test->operation==0)spriteq_add_box(x,y,a,b,layer->z,(int)layer->color,method);
 else if(test->operation==1)spriteq_add_line(x,y,a,b,layer->z,(int)layer->color,method);
 else spriteq_add_dot(x,y,layer->z,(int)layer->color,method);
#else
 int alpha=method && method->flag?test->alpha:0;
 if(test->operation==0)spriteq_add_box(x,y,a,b,layer->z,(int)layer->color,alpha);
 else if(test->operation==1)spriteq_add_line(x,y,a,b,layer->z,(int)layer->color,alpha);
 else spriteq_add_dot(x,y,layer->z,(int)layer->color,alpha);
#endif
}
static void verify_order_and_capacity(void){
 assert(MAXQSPRITES==@CAPACITY@);spriteq_unlock();spriteq_clear();assert(spritequeue_len==0);
 s_sprite frame;memset(&frame,0,sizeof(frame));
 const int z[]={2,-1,2,0},sortids[]={3,0,-2,1},expected[]={1,3,2,0};
 for(int i=0;i<4;++i)spriteq_add_frame(0,0,z[i],&frame,NULL,sortids[i]);
 spriteq_sort();for(int i=0;i<4;++i)assert(order[i]==queue+expected[i]);
 spriteq_clear();assert(spritequeue_len==0);
 const int ties[]={2,2,1},tie_order[]={2,1,0};
 for(int i=0;i<3;++i)spriteq_add_frame(0,0,ties[i],&frame,NULL,0);
 spriteq_sort();for(int i=0;i<3;++i)assert(order[i]==queue+tie_order[i]);
 spriteq_clear();assert(spritequeue_len==0);
 for(int i=0;i<MAXQSPRITES;++i)spriteq_add_frame(0,0,0,&frame,NULL,0);
 assert(spritequeue_len==MAXQSPRITES);qstruct last=queue[MAXQSPRITES-1];
 spriteq_add_frame(1,1,1,&frame,NULL,1);
 assert(spritequeue_len==MAXQSPRITES && memcmp(&last,queue+MAXQSPRITES-1,sizeof(last))==0);
 spriteq_clear();assert(spritequeue_len==0);
}
static void invoke(const struct raster_case *test,s_screen *screen,s_drawmethod *method){
 if(active_case==0)verify_order_and_capacity();
 const struct queue_control *control=controls+active_case;
 spriteq_unlock();spriteq_clear();assert(spritequeue_len==0);
 for(int i=0;i<control->count;++i){
  if(control->lock_prefix==i)spriteq_lock();
  add_primitive(test,control->layers+i,method);
 }
 if(control->lock_prefix==control->count)spriteq_lock();
 assert(spritequeue_len==control->count && spriteq_islocked()==(control->lock_prefix>=0));
 for(int i=0;i<control->count;++i){
  assert(queue[i].z==control->layers[i].z && queue[i].params[0]==(int)control->layers[i].color);
#if @QUEUE_API@
  if(method)assert(memcmp(&queue[i].drawmethod,method,sizeof(*method))==0);
  else assert(queue[i].drawmethod.flag==0);
#else
  int alpha=method && method->flag?test->alpha:0;
  assert(queue[i].drawmethod.alpha==alpha && !!queue[i].drawmethod.flag==(alpha>0));
#endif
 }
 qstruct retained[4];memcpy(retained,queue,(size_t)control->count*sizeof(*queue));
 s_drawmethod before;if(method){before=*method;method->alpha=0;method->flag=0;}
 if(@PERTURB@ && active_case==0)queue[0].params[0]^=1;
 spriteq_draw(screen,control->newonly,control->minz,control->maxz,control->dx,control->dy);
 if(memcmp(retained,queue,(size_t)control->count*sizeof(*queue))){
  fprintf(stderr,"Native primitive queue retention mismatch\n");abort();
 }
 if(method)*method=before;
 spriteq_clear();assert(spritequeue_len==(control->lock_prefix<0?0:control->lock_prefix));
 spriteq_unlock();spriteq_clear();assert(spritequeue_len==0 && !spriteq_islocked());
}
'''.replace('@CONTROLS@', ',\n'.join(rows)).replace('@QUEUE_API@', str(int(queue_api))).replace(
        '@CAPACITY@', str(expected_capacity)).replace('@PERTURB@', str(int(perturb_queue)))
    return code[:start] + queue_driver + code[end:]
