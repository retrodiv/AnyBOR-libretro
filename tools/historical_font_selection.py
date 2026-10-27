"""Render native font selection checks using the complete font translation unit.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""


def render_font_selection(*, revisions, slots, inline_fonts):
    if (not isinstance(revisions, list) or not 0 < len(revisions) <= 128 or
        any(type(n) is not int or not 0 < n <= 0xffffffff for n in revisions) or
        revisions != sorted(set(revisions)) or type(slots) is not int or
        not 1 <= slots <= 256 or type(inline_fonts) is not bool):
        raise ValueError('Explicit revisions, native font capacity and storage required')
    source = r'''
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "font.c"
#undef printf
#define CHECK(c) do{if(!(c)){fprintf(stderr,"Font selection check, line %d\n",__LINE__);abort();}}while(0)
void *checkAlloc(void *p,size_t bytes,const char *function,const char *file,int line){
 (void)function;(void)file;(void)line;CHECK(!bytes||p);return p;
}
#ifdef NDEBUG
#error Native font assertions must remain active
#endif
uint32_t obor_profile_build;
static unsigned checks;
static void setup(void){
 CHECK(MAX_FONTS==@SLOTS@);
 for(int i=0;i<MAX_FONTS;++i){
  @SETUP@
 }
}
static void run(void){
 setup();
 const int special[]={-1,-MAX_FONTS,1-MAX_FONTS,-MAX_FONTS-1,
                      -2*MAX_FONTS,INT_MIN,INT_MAX};
 for(int n=0;n<2*MAX_FONTS+7;++n){
  int index=n<2*MAX_FONTS?n:special[n-2*MAX_FONTS];
  int selected=index%MAX_FONTS;
  int width=selected<0?0:2*(selected+1);
  CHECK(font_string_width(index,"%s","AB")==width);++checks;
  CHECK(font_string_width(index,"%%")==width/2);++checks;
  @DIMENSIONS@
  if(selected<0){font_unload(index);++checks;}
 }
 /* Negative exact multiples retain the original selection of slot zero. */
 font_unload(-MAX_FONTS);
 CHECK(font_string_width(0,"AB")==0);++checks;
 for(int i=0;i<MAX_FONTS;++i)font_unload(i);
}
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i){
  obor_profile_build=revisions[i];run();
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",
        (unsigned)(sizeof(revisions)/sizeof(*revisions)),checks);
 return 0;
}
'''
    setup = ('''fonts[i].font_loaded=1;
  for(int j=0;j<256;++j)fonts[i].token_width[j]=i+1;''' if inline_fonts else
             '''fonts[i]=calloc(1,sizeof(*fonts[i]));CHECK(fonts[i]);
  fonts[i][0]=calloc(1,sizeof(*fonts[i][0]));CHECK(fonts[i][0]);
  fonts[i][0]->width=i+11;fonts[i][0]->height=i+21;
  for(int j=0;j<256;++j)fonts[i][0]->token_width[j]=i+1;''')
    dimensions = '' if inline_fonts else '''
  CHECK(fontmonowidth(index)==(selected<0?0:selected+11));++checks;
  CHECK(fontheight(index)==(selected<0?0:selected+21));++checks;'''
    for key, value in dict(SLOTS=str(slots), SETUP=setup, DIMENSIONS=dimensions,
                           REVISIONS=','.join(str(n)+'u' for n in revisions)).items():
        source = source.replace('@'+key+'@', value)
    return source
