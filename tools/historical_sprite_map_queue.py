"""Observe native sprite-map enqueue, shared centers and loader requests.

The typed image-provider observer returns an owned, genuinely encoded sprite.
It establishes the queue caller protocol, not image I/O or resource lifetime.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_sprite_queue import render_sprite_queue


def render_sprite_map_queue(*, cases, **queue_options):
    if not isinstance(cases,list) or not 1<=len(cases)<=2048:
        raise ValueError('Bounded mapped queue observations required')
    rows=[];normal=[]
    for row in cases:
        if (not isinstance(row,dict) or not isinstance(row.get('maps'),dict) or
                not isinstance(row.get('queue'),dict)):
            raise ValueError('Explicit mapped entry/cache/center contract required')
        maps=row['maps'];layers=row.get('queue',{}).get('layers',[])
        if (set(maps)!={'mapped','cached','nodes','centers','final_center'} or
                not isinstance(layers,list) or not 1<=len(layers)<=4 or
                any(not isinstance(layer,dict) for layer in layers) or
                any(not isinstance(maps[k],list) or len(maps[k])!=len(layers) for k in ('mapped','cached','nodes','centers')) or
                any(type(v) is not bool for k in ('mapped','cached') for v in maps[k]) or
                any(type(v) is not int or not 0<=v<4 for v in maps['nodes']) or
                not any(maps['mapped'])):
            raise ValueError('One explicit map state per bounded queue layer required')
        for mapped,cached,center,layer in zip(maps['mapped'],maps['cached'],maps['centers'],layers):
            if (mapped and layer.get('kind')!='sprite' or not mapped and not cached or
                    not isinstance(center,list) or len(center)!=2 or
                    any(type(v) is not int or not -4<=v<=4 for v in center)):
                raise ValueError('Mapped sprites and finite original centers required')
        states={}
        for node,cached in zip(maps['nodes'],maps['cached']):
            if node in states and states[node]!=cached:
                raise ValueError('Shared nodes require one consistent initial cache state')
            states[node]=cached
        if (not isinstance(maps['final_center'],list) or len(maps['final_center'])!=2 or
                any(type(v) is not int or not -4<=v<=4 for v in maps['final_center'])):
            raise ValueError('Explicit observed final shared-frame center required')
        def values(items):return '{'+','.join(str(int(v)) for v in items)+'}'
        rows.append('{'+','.join([values(maps['mapped']),values(maps['cached']),values(maps['nodes']),
            '{'+','.join(values(center) for center in maps['centers'])+'}',values(maps['final_center'])])+'}')
        normal.append({k:v for k,v in row.items() if k!='maps'})
    code=render_sprite_queue(cases=normal,**queue_options)
    def replace(old,new):
        nonlocal code
        if code.count(old)!=1:raise ValueError('One native mapped integration point required: '+old)
        code=code.replace(old,new)
    declarations='''struct mapped_control {int mapped[4],cached[4],nodes[4],centers[4][2],final_center[2];};
static const struct mapped_control mapped_controls[]={'''+',\n'.join(rows)+'''};
static s_sprite_map probe_maps[4];
s_sprite_map *sprite_map=probe_maps;
static s_sprite_list probe_nodes[4];
static char probe_names[4][8]={"node0","node1","node2","node3"};
static unsigned probe_load_calls[4];
static s_sprite *probe_loaded_frame;
/* Typed caller-protocol observer only; no file preparation or cache manager. */
s_sprite *loadsprite2(char *filename,int *width,int *height){
 assert(!width && !height && probe_loaded_frame);
 unsigned index=0;while(index<4 && filename!=probe_names[index])++index;
 assert(index<4);++probe_load_calls[index];return probe_loaded_frame;
}
static void prepare_maps(const struct mapped_control *maps,s_sprite *frame,int count){
 memset(probe_maps,0,sizeof(probe_maps));memset(probe_nodes,0,sizeof(probe_nodes));
 memset(probe_load_calls,0,sizeof(probe_load_calls));probe_loaded_frame=frame;
 for(int i=0;i<count;++i){
  int node=maps->nodes[i];
  probe_maps[i].node=probe_nodes+node;probe_maps[i].centerx=maps->centers[i][0];
  probe_maps[i].centery=maps->centers[i][1];probe_nodes[node].filename=probe_names[node];
  probe_nodes[node].sprite=maps->cached[i]?frame:NULL;probe_nodes[node].ref=10+node;
 }
}
'''
    replace('struct queue_layer {',declarations+'struct queue_layer {')
    marker='  s_drawmethod methods[4];'
    setup='''  const struct mapped_control *maps=mapped_controls+active_case;
  prepare_maps(maps,frame,control->count);
  if(active_case==0){
   int index=0;while(index<control->count && !maps->mapped[index])++index;
   assert(index<control->count);
   for(int n=0;n<MAXQSPRITES;++n)spriteq_add_frame(0,0,0,frame,NULL,0);
   assert(spritequeue_len==MAXQSPRITES);qstruct last=queue[MAXQSPRITES-1];
   int node=maps->nodes[index];probe_nodes[node].sprite=NULL;
   spriteq_add_sprite(0,0,0,index,NULL,0);
   assert(spritequeue_len==MAXQSPRITES && !memcmp(&last,queue+MAXQSPRITES-1,sizeof(last)));
   assert(probe_load_calls[node]==1 && probe_nodes[node].sprite==frame);
   spriteq_unlock();spriteq_clear();prepare_maps(maps,frame,control->count);
  }
'''
    replace(marker,setup+marker)
    replace('if(layer->kind==0)spriteq_add_frame(x,y,layer->z,frame,selected,layer->sortid);', '''if(layer->kind==0){
    if(maps->mapped[i])spriteq_add_sprite(x,y,layer->z,i,selected,layer->sortid);
    else spriteq_add_frame(x,y,layer->z,frame,selected,layer->sortid);
   }''')
    marker='  qstruct retained[4];'
    before='''  unsigned expected_requests[4]={0};
  for(int i=0;i<control->count;++i){
   int node=maps->nodes[i];
   if(maps->mapped[i] && !maps->cached[i])expected_requests[node]=1;
   assert(probe_nodes[node].sprite==frame && probe_nodes[node].ref==10+node);
   if(maps->mapped[i])assert(queue[i].params[0]==1 &&
    queue[i].params[1]==maps->centers[i][0] && queue[i].params[2]==maps->centers[i][1]);
   probe_maps[i].centerx=-3;probe_maps[i].centery=3;
  }
  for(unsigned n=0;n<4;++n)assert(probe_load_calls[n]==expected_requests[n]);
  s_sprite_map maps_copy[4];s_sprite_list nodes_copy[4];
  memcpy(maps_copy,probe_maps,sizeof(probe_maps));memcpy(nodes_copy,probe_nodes,sizeof(probe_nodes));
'''
    replace(marker,before+marker)
    marker='  spriteq_draw(dest,control->newonly,control->minz,control->maxz,control->dx,control->dy);tracking=0;'
    after='''
  assert(frame->centerx==maps->final_center[0] && frame->centery==maps->final_center[1]);
  assert(!memcmp(maps_copy,probe_maps,sizeof(probe_maps)) && !memcmp(nodes_copy,probe_nodes,sizeof(probe_nodes)));
  frame->centerx=test->anchor[0];frame->centery=test->anchor[1];
'''
    replace(marker,marker+after)
    marker='  free(source_copy);free(source_screen);'
    replace(marker,'''  memset(probe_maps,0,sizeof(probe_maps));memset(probe_nodes,0,sizeof(probe_nodes));
  probe_loaded_frame=NULL;
'''+marker)
    return code
