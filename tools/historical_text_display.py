"""Render native text drawing through the complete native font unit.

The bounded queue observer records glyph identity and positions, not pixels.
Only literal and escaped-percent original format strings are admitted.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_text_display(*, revisions, draw, plainmethod, physical_fixed,
                        slots, font_tokens, cases):
    if (not isinstance(revisions,list) or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions) or
        revisions!=sorted(set(revisions))):
        raise ValueError('Explicit bounded native revisions required')
    if (not isinstance(draw,str) or not 0<len(draw)<=32768 or '\0'in draw or
        not re.match(r'\s*void\s+draw_textobjs\s*\(',draw)):
        raise ValueError('Complete native text drawing function required')
    if (not isinstance(plainmethod,str) or not 0<len(plainmethod)<=8192 or
        '\0'in plainmethod or not re.match(
            r'\s*const\s+s_drawmethod\s+plainmethod\s*=',plainmethod)):
        raise ValueError('Native plain drawmethod declaration required')
    if (type(physical_fixed)is not bool or type(slots)is not int or not 4<=slots<=128 or
        font_tokens not in ('inline','indexed','atlas')):
        raise ValueError('Explicit native table and font storage required')
    if not isinstance(cases,list) or not 0<len(cases)<=32:
        raise ValueError('Bounded native display cases required')

    def integer(n,lo=-10000,hi=10000):return type(n)is int and lo<=n<=hi
    def text(data):
        if not isinstance(data,list) or len(data)>128 or any(not integer(n,1,255)for n in data):
            return False
        i=0
        while i<len(data):
            if data[i]==37:
                if i+1==len(data) or data[i+1]!=37:return False
                i+=2
            else:i+=1
        return True
    def fields(data):
        return (isinstance(data,dict) and set(data)=={'x','y','z','font','t'} and
            all(integer(data[k])for k in ('x','y','z')) and
            integer(data['font'],0,127) and integer(data['t'],0,0xffffffff))
    def objects(data,expected=False):
        if not isinstance(data,list) or len(data)>slots:return False
        seen=set()
        for obj in data:
            if (not isinstance(obj,dict) or set(obj)!={'index','fields','text'} or
                not integer(obj['index'],0,slots-1) or obj['index']in seen or
                not fields(obj['fields']) or not(obj['text']is None or text(obj['text']))):
                return False
            seen.add(obj['index'])
        return True

    declarations=[];runs=[]
    for number,case in enumerate(cases):
        if (not isinstance(case,dict) or set(case)!={'level_present','objects','ticks'} or
            type(case['level_present'])is not bool or not objects(case['objects']) or
            not isinstance(case['ticks'],list) or not 0<len(case['ticks'])<=8 or
            not case['level_present'] and case['objects']):
            raise ValueError('Explicit level, objects and bounded ticks required')
        body=['fixture_seed('+str(int(case['level_present']))+');']
        if case['objects'] and not physical_fixed:body.append('fixture_table();')
        for obj in case['objects']:
            index=str(obj['index']);name='seed_'+str(number)+'_'+index
            for field,value in obj['fields'].items():body.append('level->textobjs['+index+'].'+field+'='+str(value)+'u;'if field=='t'else'level->textobjs['+index+'].'+field+'='+str(value)+';')
            if obj['text']is not None:
                declarations.append('static const unsigned char '+name+'[]={'+','.join(map(str,obj['text']+[0]))+'};')
                body.append('fixture_text('+index+','+name+',sizeof('+name+'));')
        for tick_number,tick in enumerate(case['ticks']):
            if (not isinstance(tick,dict) or set(tick)!=
                {'now','glyphs','released','objects'} or not integer(tick['now'],0,0xffffffff) or
                not isinstance(tick['glyphs'],list) or len(tick['glyphs'])>256 or
                not isinstance(tick['released'],list) or
                any(not integer(i,0,slots-1)for i in tick['released']) or
                tick['released']!=sorted(set(tick['released'])) or
                not objects(tick['objects'],True) or
                not case['level_present'] and (tick['released']or tick['objects'])):
                raise ValueError('Independent bounded glyph, release and field snapshots required')
            body+=['fixture_time='+str(tick['now'])+'u;queued=0;draw_textobjs();',
                   'CHECK(queued=='+str(len(tick['glyphs']))+',"native glyph count");']
            for n,glyph in enumerate(tick['glyphs']):
                if (not isinstance(glyph,list)or len(glyph)!=5 or
                    any(not integer(v)for v in glyph[:3])or
                    not integer(glyph[3],0,127)or not integer(glyph[4],0,255)):
                    raise ValueError('Native glyph x/y/layer-offset/font/byte required')
                x,y,z,font,byte=glyph
                body.append('CHECK(queue['+str(n)+'].x=='+str(x)+'&&queue['+str(n)+'].y=='+str(y)+
                    '&&queue['+str(n)+'].z==0x0fffffff+'+str(z)+
                    '&&queue['+str(n)+'].font=='+str(font)+'&&queue['+str(n)+'].byte=='+str(byte)+
                    ',"native queued glyph");')
            for i in range(slots):
                body.append('CHECK(released['+str(i)+']=='+str(int(i in tick['released']))+',"native release snapshot");')
            for obj in tick['objects']:
                index=str(obj['index']);prefix='level->textobjs['+index+']'
                for field,value in obj['fields'].items():
                    body.append('CHECK('+prefix+'.'+field+'=='+str(value)+('u'if field=='t'else'')+',"native text field '+field+'");')
                if obj['text']is None:body.append('CHECK(!'+prefix+'.text,"native absent text");')
                else:
                    name='expected_'+str(number)+'_'+str(tick_number)+'_'+index
                    declarations.append('static const unsigned char '+name+'[]={'+','.join(map(str,obj['text']+[0]))+'};')
                    body.append('CHECK('+prefix+'.text==owned['+index+']&&!memcmp('+prefix+'.text,'+name+',sizeof('+name+')),"native retained text identity and bytes");')
        body+=['fixture_retire();++checks;']
        declarations.append('static void case_'+str(number)+'(void){\n'+'\n'.join(body)+'\n}')
        runs.append('case_'+str(number)+'();')

    source=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "font.c"
#include "openbor.h"
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Text display: %s at line %d\n",m,__LINE__);abort();}}while(0)
#ifdef NDEBUG
#error Native text display checks must stay active
#endif
uint32_t obor_profile_build;
static u32 fixture_time;
s_level *level;
@PLAINMETHOD@
static unsigned checks,queued;
static char *owned[@SLOTS@];
static unsigned released[@SLOTS@];
static s_sprite glyphs[MAX_FONTS][256],atlases[MAX_FONTS];
static s_font fixture_fonts[MAX_FONTS];
static s_font *fixture_sets[MAX_FONTS][256];
static struct {int x,y,z,font,byte;} queue[256];
void *checkAlloc(void *p,size_t bytes,const char *function,const char *file,int line){
 (void)function;(void)file;(void)line;CHECK(!bytes||p,"native allocation");return p;
}
void exitIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(v,"native assertion");
}
void abortIfFalse(int v,const char *condition,const char *function,const char *file,int line){exitIfFalse(v,condition,function,file,line);}
void spriteq_add_frame(int x,int y,int z,s_sprite *frame,s_drawmethod *method,int sortid){
 CHECK(queued<256&&sortid==0,"bounded native glyph queue");
 int found_font=-1,found_byte=-1;
 @IDENTIFY@
 CHECK(found_font>=0&&found_byte>=0&&found_byte<256,"fixture glyph identity");
 queue[queued].x=x;queue[queued].y=y;queue[queued].z=z;
 queue[queued].font=found_font;queue[queued].byte=found_byte;++queued;
}
static void tracked_release(void *p){
 if(!p)return;
 for(unsigned i=0;i<@SLOTS@;++i)if(owned[i]==p){
  CHECK(!released[i],"text released once");released[i]=1;free(p);return;
 }
 CHECK(0,"release belongs to its text object");
}
#define free tracked_release
#undef time
#define time fixture_time
@DRAW@
#undef time
#undef free
static void fixture_seed(int active){
 memset(owned,0,sizeof(owned));memset(released,0,sizeof(released));
 memset(fonts,0,sizeof(fonts));memset(fixture_fonts,0,sizeof(fixture_fonts));
 memset(fixture_sets,0,sizeof(fixture_sets));
 CHECK(MAX_FONTS>=2&&MAX_FONTS<=128,"bounded native font slots");
 for(int f=0;f<MAX_FONTS;++f){
  @SETUP@
 }
 level=active?calloc(1,sizeof(*level)):NULL;
 CHECK(!active||level,"fixture level allocation");
 if(level){@FIXED_TABLE@}
}
static void fixture_table(void){@TABLE@}
static void fixture_text(unsigned index,const unsigned char *bytes,size_t length){
 CHECK(level&&index<@SLOTS@&&length&&length<=129&&!owned[index],"bounded native fixture text");
 owned[index]=malloc(length);CHECK(owned[index],"fixture text allocation");
 memcpy(owned[index],bytes,length);level->textobjs[index].text=owned[index];
}
static void fixture_retire(void){
 if(!level)return;
 if(@TABLE_PRESENT@)for(unsigned i=0;i<@SLOTS@;++i){
  if(owned[i]&&!released[i]){CHECK(level->textobjs[i].text==owned[i],"retained native owner");tracked_release(owned[i]);}
  CHECK(!level->textobjs[i].text||released[i],"text ownership accounted");
 }
 @RETIRE_TABLE@
 free(level);level=NULL;
}
@CASES@
int main(void){const uint32_t revisions[]={@REVISIONS@};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i){obor_profile_build=revisions[i];@RUN@}
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",(unsigned)(sizeof(revisions)/sizeof(*revisions)),checks);return 0;
}
'''
    identify=('''CHECK(!method,"indexed native font has no drawmethod");
 for(int f=0;f<MAX_FONTS;++f)for(int c=0;c<256;++c)
  if(frame==&glyphs[f][c]){found_font=f;found_byte=c;}''' if font_tokens!='atlas'else
    '''CHECK(method&&method->clipx==x&&method->clipy==y&&method->clipw==8&&method->cliph==9,"native atlas glyph clipping");
 for(int f=0;f<MAX_FONTS;++f)if(frame==&atlases[f]){found_font=f;found_byte=(method->centery/9)*16+method->centerx/8;}''')
    setup=('''fonts[f].font_loaded=1;
 for(int c=0;c<256;++c){glyphs[f][c].width=8;glyphs[f][c].height=9;fonts[f].token[c]=&glyphs[f][c];fonts[f].token_width[c]=3+f%2;}''' if font_tokens=='inline'else
    '''fonts[f]=fixture_sets[f];fixture_sets[f][0]=&fixture_fonts[f];
 fixture_fonts[f].width=8;fixture_fonts[f].height=9;
 @TOKENS@
 for(int c=0;c<256;++c)fixture_fonts[f].token_width[c]=3+f%2;''')
    setup=setup.replace('@TOKENS@','fixture_fonts[f].token=&atlases[f];'if font_tokens=='atlas'else
        'for(int c=0;c<256;++c){glyphs[f][c].width=8;glyphs[f][c].height=9;fixture_fonts[f].token[c]=&glyphs[f][c];}')
    values=dict(PLAINMETHOD=plainmethod,SLOTS=str(slots),IDENTIFY=identify,DRAW=draw,SETUP=setup,
        FIXED_TABLE='CHECK(LEVEL_MAX_TEXTOBJS=='+str(slots)+',"native fixed text extent");'if physical_fixed else'',
        TABLE=''if physical_fixed else
        'level->numtextobjs='+str(slots)+';level->textobjs=calloc('+str(slots)+',sizeof(*level->textobjs));CHECK(level->textobjs,"fixture table allocation");',
        TABLE_PRESENT='1'if physical_fixed else'level->textobjs!=NULL',
        RETIRE_TABLE=''if physical_fixed else'free(level->textobjs);',CASES='\n'.join(declarations),
        REVISIONS=','.join(str(n)+'u'for n in revisions),RUN=''.join(runs))
    result=re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],source)
    if len(result)>4<<20:raise ValueError('Split excessive native text display cases')
    return result
