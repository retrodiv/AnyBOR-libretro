"""Run a complete native level release against bounded text-only records.

Other level resources are empty. Script clearing observes the five native level
script addresses; it does not run a script disposer or a complete VM unload.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_text_release(*, source, revisions, physical_fixed, slots,
                        script_fields, helpers=''):
    if (not isinstance(source, str) or not 0 < len(source) <= 65536 or
            '\0' in source or not re.match(r'\s*void\s+free_level\s*\(', source)):
        raise ValueError('Complete bounded native level release required')
    if (not isinstance(revisions, list) or not 0 < len(revisions) <= 128 or
            any(type(n) is not int or not 0 < n <= 0xffffffff for n in revisions) or
            revisions != sorted(set(revisions))):
        raise ValueError('Explicit bounded unique profile revisions required')
    if (type(physical_fixed) is not bool or type(slots) is not int or
            not 4 <= slots <= 128):
        raise ValueError('Explicit bounded native text storage required')
    if (not isinstance(script_fields, list) or not 0 < len(script_fields) <= 16 or
            any(not isinstance(f, str) or not re.fullmatch(r'[A-Za-z_]\w*', f)
                for f in script_fields) or len(set(script_fields)) != len(script_fields)):
        raise ValueError('Distinct native level script field names required')
    if (not isinstance(helpers, str) or len(helpers) > 16384 or '\0' in helpers):
        raise ValueError('Bounded complete native support functions required')
    code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef malloc
#undef calloc
#undef free
#undef printf
#ifdef NDEBUG
#error Text release checks must remain enabled
#endif
#define CHECK(c) do {if(!(c)){fputs("Text release: ownership snapshot\n",stderr);abort();}} while(0)
uint32_t obor_profile_build;
static s_screen *background;
static void *owned[132];
static unsigned released[132],owned_count,release_count;
static unsigned level_slot,table_slot;
static int text_slot[@SLOTS@];
static void *scripts[16];
static unsigned cleared[16],script_count;
static unsigned checks;
static void *own(size_t bytes) {
 CHECK(bytes && bytes<(1u<<24) && owned_count<132);
 void *p=calloc(1,bytes);CHECK(p);owned[owned_count]=p;
 released[owned_count++]=0;return p;
}
static void tracked_release(void *p) {
 if(!p)return;
 unsigned index=owned_count;
 for(unsigned i=0;i<owned_count;++i)if(owned[i]==p){CHECK(index==owned_count);index=i;}
 CHECK(index<owned_count && !released[index]);
 if(index==table_slot || index==level_slot)
  for(unsigned i=0;i<@SLOTS@;++i)
   if(text_slot[i]>=0)CHECK(released[(unsigned)text_slot[i]]==1);
 if(index==level_slot && table_slot!=level_slot)CHECK(released[table_slot]==1);
 ++released[index];++release_count;
}
static void observe_clear(void *address,int mode) {
 CHECK(mode==2);unsigned index=script_count;
 for(unsigned i=0;i<script_count;++i)if(scripts[i]==address){CHECK(index==script_count);index=i;}
 CHECK(index<script_count && !cleared[index]);++cleared[index];
}
#define free tracked_release
#define Script_Clear observe_clear
@HELPERS@
@SOURCE@
#undef Script_Clear
#undef free
static void fixture(int kind) {
 owned_count=release_count=script_count=0;
 memset(cleared,0,sizeof(cleared));
 for(unsigned i=0;i<@SLOTS@;++i)text_slot[i]=-1;
 level_slot=owned_count;
 s_level *lv=own(sizeof(*lv));
 @SCRIPT_ADDRESSES@
 @TABLE@
 const unsigned indices[]={0,1,@SLOTS@-1};
 for(unsigned j=0;j<3;++j) {
  unsigned i=indices[j];
  if(kind==1 || (kind==2 && j) || (kind==3 && j==1))continue;
  if(kind==0)continue;
  text_slot[i]=(int)owned_count;
  lv->textobjs[i].text=own(4);
  memcpy(lv->textobjs[i].text,j==1?"":"abc",j==1?1:4);
  lv->textobjs[i].x=17;lv->textobjs[i].y=-9;lv->textobjs[i].z=3;
  lv->textobjs[i].font=1;lv->textobjs[i].t=42;
 }
 free_level(NULL);CHECK(!release_count);
 for(unsigned i=0;i<script_count;++i)CHECK(!cleared[i]);
 free_level(lv);CHECK(release_count==owned_count);
 for(unsigned i=0;i<script_count;++i)CHECK(cleared[i]==1);
 for(unsigned j=0;j<3;++j)if(text_slot[indices[j]]>=0)
  CHECK(!lv->textobjs[indices[j]].text);
 for(unsigned i=0;i<owned_count;++i){CHECK(released[i]==1);free(owned[i]);owned[i]=NULL;}
 ++checks;
}
int main(void) {
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n) {
  obor_profile_build=revisions[n];
  for(int kind=0;kind<5;++kind)fixture(kind);
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),checks);return 0;
}
'''
    table = 'CHECK(sizeof(lv->textobjs)/sizeof(*lv->textobjs)==@SLOTS@);table_slot=level_slot;'
    if not physical_fixed:
        table = ('table_slot=level_slot;\n'
                 'if(kind) {table_slot=owned_count;lv->numtextobjs=@SLOTS@;'
                 'lv->textobjs=own(@SLOTS@*sizeof(*lv->textobjs));}')
    return (code.replace('@SLOTS@', str(slots)).replace('@TABLE@', table.replace('@SLOTS@', str(slots)))
            .replace('@SCRIPT_ADDRESSES@', '\n'.join(
                'scripts[script_count++]=&lv->%s;' % f for f in script_fields))
            .replace('@HELPERS@', helpers).replace('@SOURCE@', source)
            .replace('@REVISIONS@', ','.join(map(str, revisions))))
