"""Observe native rendering map expressions with bounded typed model fields.

These controls isolate pointer selection and the KO predicate. They do not
render pixels, reproduce full model layout or accept complete caller execution.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def extract_render_colourmaps(functions):
    """Retain exact expressions and the complete source KO conditional block."""
    definitions={name:functions[name]for name in
        ('predrawstatus','display_ents','common_lie','checkdamageeffects')}
    specifications=[
        ('hud','predrawstatus',r'drawmethod\.table','player[i].colourmap',True),
        ('remap','display_ents',r'drawmethod->table','drawmethod->remap',False),
        ('dying','display_ents',r'drawmethod->table','e->dying',False),
        ('ko','common_lie',r'self->colourmap','maps.ko',False),
        ('frozen','checkdamageeffects',r'self->colourmap','maps.frozen',False),
        ('attack','checkdamageeffects',r'self->colourmap','_remap',False),
    ]
    lookups=[]
    for name,caller,destination,marker,zero in specifications:
        candidates=re.findall(r'(?m)'+destination+r'\s*=\s*([^;\r\n]+);',definitions[caller])
        expressions={text.strip()for text in candidates if marker in text}
        if len(expressions)!=1:raise ValueError('One exact native rendering expression required: '+name)
        expression=expressions.pop()
        if name=='hud':
            compact=re.sub(r'\s+','',expression)
            if compact=='model->colourmap[player[i].colourmap-1]':zero=False
            elif (compact=='model_get_colourmap(model,player[i].colourmap)'or
                  compact=='player[i].colourmap?model->colourmap[player[i].colourmap-1]:model->palette'):
                zero=True
            else:raise ValueError('Explicit native HUD zero-domain source review required')
        lookups.append(dict(name=name,expression=expression,zero_defined=zero))
    lie=definitions['common_lie']
    start=re.search(r'\bif\s*\(\s*self->modeldata\.maps\.ko\s*\)\s*(?://[^\n]*\n\s*)?\{',lie)
    if not start:raise ValueError('Native KO conditional block required')
    opening=start.end()-1;prefix='void native_map_block(void)'
    wrapped=function(prefix+lie[opening:],'native_map_block').removesuffix('\n')
    block=lie[start.start():opening]+wrapped[len(prefix):]
    return dict(lookups=lookups,ko_block=block)


def render_colourmap_selection(*,revisions,lookups,ko_block,helper,counter,
                              fixed_table,fixed_limit,policy,models,mode='valid'):
    if (not isinstance(revisions,list)or not 0<len(revisions)<=128 or
            any(type(value)is not int or not 0<value<=0xffffffff for value in revisions)or
            len(set(revisions))!=len(revisions)or type(fixed_table)is not bool or
            type(fixed_limit)is not int or not 1<=fixed_limit<=127 or
            policy not in ('raw','loaded')or mode not in ('valid','all')):
        raise ValueError('Bounded own-source revisions, table layout and lookup policy required')
    if (not isinstance(counter,str)or len(counter)>128 or not re.fullmatch(
            r'\s*(?:(?:signed|unsigned)\s+)?(?:char|short|int|long)\s+maps_loaded\s*(?::\s*[0-9]+)?\s*;\s*',counter)):
        raise ValueError('An exact bounded native loaded-counter declaration required')
    if (not isinstance(helper,str)or len(helper)>8192 or '\0'in helper or
            helper and not re.match(r'\s*unsigned\s+char\s*\*\s*model_get_colourmap\s*\(',helper)):
        raise ValueError('Exact native model-map helper or explicit absence required')
    if (not isinstance(ko_block,str)or not 0<len(ko_block)<=4096 or '\0'in ko_block or
            not re.match(r'\s*if\s*\(\s*self->modeldata\.maps\.ko\s*\)',ko_block)):
        raise ValueError('Bounded exact native KO predicate required')
    if not isinstance(lookups,list)or not 0<len(lookups)<=8:
        raise ValueError('Bounded source lookup expressions required')
    names=set();cases=[]
    for row in lookups:
        if (not isinstance(row,dict)or set(row)!={'name','expression','zero_defined'}or
                not isinstance(row['name'],str)or not re.fullmatch(r'[A-Za-z_]\w{0,63}',row['name'])or
                row['name']in names or type(row['zero_defined'])is not bool or
                not isinstance(row['expression'],str)or not 0<len(row['expression'])<=2048 or
                any(c in row['expression']for c in ';{}#\0\r\n\\\"\'')):
            raise ValueError('Distinct exact native expressions and defined-domain flags required')
        names.add(row['name']);cases.append('case %d:return %s;'%(len(cases),row['expression']))
    if not isinstance(models,list)or not 0<len(models)<=8:
        raise ValueError('Bounded explicit model extents required')
    for row in models:
        if (not isinstance(row,dict)or set(row)!={'slots','loaded'}or
                type(row['slots'])is not int or not 1<=row['slots']<=127 or
                type(row['loaded'])is not int or not 0<=row['loaded']<=row['slots']or
                fixed_table and row['slots']!=fixed_limit):
            raise ValueError('Model extents must retain defined native table reads')
    if mode=='all'and(fixed_table or not helper):
        raise ValueError('Safety controls need a supplied checked helper and dynamic prepared table')
    code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Render colourmap mismatch: %s\n",m);abort();}}while(0)
#ifdef NDEBUG
#error Map-selection observations require active assertions
#endif
#define MAX_COLOUR_MAPS @LIMIT@
static uint32_t obor_profile_build;
typedef struct{
 unsigned char *palette;
 @TABLE@
 @COUNTER@
 unsigned colourmap_capacity;
 struct{signed char ko,frozen,kotype;}maps;
}s_model;
static struct{ s_model modeldata;unsigned char *colourmap;int dying,animating;} entity_storage;
static __typeof__(entity_storage) *e=&entity_storage,*self=&entity_storage;
static s_model *model=&entity_storage.modeldata;
static struct{int colourmap;}player[1];
static struct{int remap;unsigned char *table;}drawmethod_storage,*drawmethod=&drawmethod_storage;
static int i,_remap;
static unsigned char colours[4],*tables[127];
static unsigned observations;
@HELPER@
static unsigned char *select_map(unsigned lookup){
 switch(lookup){@CASES@}
 CHECK(0,"declared lookup");return NULL;
}
static void apply_ko(void){@KO_BLOCK@}
static void seed(unsigned slots,unsigned loaded){
 memset(&entity_storage,0,sizeof(entity_storage));memset(tables,0,sizeof(tables));
 model->palette=&colours[0];tables[0]=&colours[1];
 @SEED_TABLE@
 model->colourmap_capacity=slots;model->maps_loaded=(int)loaded;
}
static void select_index(unsigned value){
 player[0].colourmap=(int)value;drawmethod->remap=(int)value;
 e->dying=(int)value;self->modeldata.maps.ko=(signed char)value;
 self->modeldata.maps.frozen=(signed char)value;_remap=(int)value;
}
static unsigned char *expected(unsigned which,unsigned loaded){
 if(!which || (@LOADED@ && which>loaded))return &colours[0];
 return tables[which-1];
}
static const struct{unsigned slots,loaded;}models[]={@MODELS@};
static const unsigned zero_defined[]={@ZERO@};
static void valid(void){
 for(unsigned m=0;m<sizeof(models)/sizeof(*models);++m){
  unsigned slots=models[m].slots,loaded=models[m].loaded;seed(slots,loaded);
  for(unsigned lookup=0;lookup<sizeof(zero_defined)/sizeof(*zero_defined);++lookup)
   for(unsigned which=zero_defined[lookup]?0:1;which<=slots;++which){
    select_index(which);
    CHECK(select_map(lookup)==expected(which,loaded),"native selected map pointer");++observations;
   }
  for(unsigned which=1;which<=slots;++which)
   for(int kind=0;kind<2;++kind)for(int animating=0;animating<2;++animating){
    select_index(which);self->modeldata.maps.kotype=(signed char)kind;
    self->animating=animating;self->colourmap=&colours[3];apply_ko();
    unsigned char *want=(!kind || !animating)?expected(which,loaded):&colours[3];
    CHECK(self->colourmap==want,"native KO application predicate and pointer");++observations;
   }
 }
}
@SAFETY@
static const uint32_t revisions[]={@REVISIONS@};
int main(void){
 for(unsigned context=0;context<sizeof(revisions)/sizeof(*revisions);++context){
  obor_profile_build=revisions[context];valid();@RUN_SAFETY@
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"cases\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),observations);return 0;
}
'''
    safety=r'''
static void safety(void){
 seed(3,1);
 CHECK(!model_get_colourmap(NULL,1),"absent model");++observations;
 CHECK(model_get_colourmap(model,0)==model->palette,"zero palette");++observations;
 unsigned char *outside=@LOADED@?model->palette:NULL;
 CHECK(model_get_colourmap(model,UINT32_MAX)==outside,"unrepresentable table index");++observations;
 CHECK(model_get_colourmap(model,MAX_COLOUR_MAPS+1)==outside,"beyond fixed extent");++observations;
 model->colourmap=NULL;
 CHECK(!model_get_colourmap(model,1),"absent backing table");++observations;
 model->colourmap=tables;model->colourmap_capacity=0;
 CHECK(!model_get_colourmap(model,1),"absent physical capacity");++observations;
}
'''
    replacements={'@LIMIT@':str(fixed_limit),'@TABLE@':'unsigned char *colourmap[MAX_COLOUR_MAPS];'
        if fixed_table else'unsigned char **colourmap;', '@COUNTER@':counter,'@HELPER@':helper,
        '@CASES@':'\n'.join(cases),'@KO_BLOCK@':ko_block,
        '@SEED_TABLE@':'for(unsigned n=0;n<slots;++n)model->colourmap[n]=tables[n];'
            if fixed_table else'model->colourmap=tables;',
        '@LOADED@':'1'if policy=='loaded'else'0',
        '@MODELS@':','.join('{%d,%d}'%(row['slots'],row['loaded'])for row in models),
        '@ZERO@':','.join('1'if row['zero_defined']else'0'for row in lookups),
        '@SAFETY@':safety if mode=='all'else'', '@RUN_SAFETY@':'safety();'if mode=='all'else'',
        '@REVISIONS@':','.join(str(value)+'u'for value in revisions)}
    # Safety uses the same explicit policy token as valid selection.
    for key,value in replacements.items():code=code.replace(key,value)
    return code.replace('@LOADED@','1'if policy=='loaded'else'0')
