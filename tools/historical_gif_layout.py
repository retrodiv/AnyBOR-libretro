"""Render GIF wire and explicitly packed save-record layout checks.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import re


def render_gif_record_layout(engine, fixture):
    header = (engine / 'openbor.h').read_text()
    end = header.index('}s_savedata;')
    start = header.rindex('typedef struct', 0, end)
    records = header[start:header.index('}s_savescore;') + len('}s_savescore;')]
    packing = header[header.rfind('#pragma', 0, start):start].strip()
    if packing != '#pragma pack(push, 4)':
        raise ValueError('Persisted records need their own explicit packing scope')
    constants = []
    for name in ('MAX_PLAYERS', 'MAX_NAME_LEN'):
        constants.append(re.search(r'^#define\s+' + name + r'\s+[^\n]+', header, re.M)[0])
    digest = hashlib.sha256(records.encode()).hexdigest()
    for row in fixture['sources']:
        if row['records_sha256'] != digest or not row['record_packing_is_unconditional']:
            raise ValueError('Own-source saved-record declaration or packing differs')
    checks = '\n'.join('revision=%d;check();' % row['revision'] for row in fixture['sources'])
    layout = []
    for name, facts in fixture['native_layout'].items():
        layout.append('assert(sizeof(%s)==%d && _Alignof(%s)==%d);' % (
            name, facts['size'], name, facts['alignment']))
        layout.extend('assert(offsetof(%s,%s)==%d);' % (name, field, offset)
                      for field, offset in facts['offsets'].items())
    save_bytes = '\n'.join('assert(s[%s]==%d);' % (offset, value)
                           for offset, value in fixture['save_field_bytes'].items())
    config_bytes = '\n'.join('assert(c[%s]==%d);' % (offset, value)
                             for offset, value in fixture['config_field_bytes'].items())
    return r'''
#include <assert.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#pragma pack(push, 4)
struct BeforeGif {char tag;uint64_t value;};
#include "anigif.h"
struct AfterGif {char tag;uint64_t value;};
#pragma pack(pop)
@CONSTANTS@
#pragma pack(push, 4)
@RECORDS@
#pragma pack(pop)
static unsigned revision,cases;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"GIF/record layout profile=%u line=%d\n",revision,__LINE__);abort();}}while(0)
static void check(void) {
    ++cases;
    assert(CHAR_BIT==8 && sizeof(int)==4 && sizeof(short)==2);
    assert(sizeof(void*)==8);
    const uint16_t endian=1;assert(*(const unsigned char*)&endian==1);
    assert(sizeof(struct BeforeGif)==sizeof(struct AfterGif));
    assert(offsetof(struct AfterGif,value)==4);
    assert(sizeof_gifheaderstruct==13 && sizeof_iblock==9);
    assert(offsetof(gifheaderstruct,screenwidth)==6);
    assert(offsetof(gifheaderstruct,screenheight)==8);
    assert(offsetof(gifheaderstruct,flags)==10);
    assert(offsetof(gifheaderstruct,background)==11);
    assert(offsetof(gifheaderstruct,aspect)==12);
    assert(offsetof(gifblockstruct,left)==0 && offsetof(gifblockstruct,top)==2);
    assert(offsetof(gifblockstruct,width)==4 && offsetof(gifblockstruct,height)==6);
    assert(offsetof(gifblockstruct,flags)==8);
    const unsigned char wire_header[13]={'G','I','F','8','9','a',0x23,1,0x56,4,0x80,7,0};
    const unsigned char wire_block[9]={3,0,5,0,7,0,11,0,0x40};
    gifheaderstruct gh={0};gifblockstruct gb={0};
    memcpy(&gh,wire_header,sizeof_gifheaderstruct);
    memcpy(&gb,wire_block,sizeof_iblock);
    assert(!memcmp(gh.magic,"GIF89a",6) && gh.screenwidth==291 && gh.screenheight==1110);
    assert(gh.flags==0x80 && gh.background==7 && gh.aspect==0);
    assert(gb.left==3 && gb.top==5 && gb.width==7 && gb.height==11 && gb.flags==0x40);
    assert(MAX_PLAYERS==4 && MAX_NAME_LEN==40);
    @LAYOUT@
    s_savedata config={0};s_savelevel save={0};s_savescore score={0};
    config.compatibleversion=0x12345678;config.gamma=-3;config.brightness=7;
    config.soundrate=44100;config.keys[3][11]=0x23456789;config.screen[6][1]=9;
    save.compatibleversion=0x34567890;save.level=513;save.stage=1027;
    save.credits=9;save.times_completed=1291;save.which_set=1805;save.flag=1;
    save.pLives[3]=17;save.pScores[3]=0x456789ab;strcpy(save.pName[3],"fixture");
    save.pSpawnhealth[3]=123;save.pSpawnmp[3]=45;save.pWeapnum[3]=2;save.pColourmap[3]=3;
    score.compatibleversion=0x56789abc;score.highsc[9]=0x6789abcd;strcpy(score.hscoren[9],"score");
    const unsigned char *c=(const unsigned char*)&config,*s=(const unsigned char*)&save;
    @CONFIG_BYTES@
    @SAVE_BYTES@
    s_savedata restored_config={0};s_savelevel restored_save={0};s_savescore restored_score={0};
    FILE *file=tmpfile();assert(file);
    assert(fwrite(&config,sizeof(config),1,file)==1 && fwrite(&save,sizeof(save),1,file)==1);
    assert(fwrite(&score,sizeof(score),1,file)==1 && !fseek(file,0,SEEK_SET));
    assert(fread(&restored_config,sizeof(config),1,file)==1);
    assert(fread(&restored_save,sizeof(save),1,file)==1);
    assert(fread(&restored_score,sizeof(score),1,file)==1 && !fclose(file));
    assert(!memcmp(&config,&restored_config,sizeof(config)));
    assert(!memcmp(&save,&restored_save,sizeof(save)) && !memcmp(&score,&restored_score,sizeof(score)));
}
int main(void) {@CHECKS@printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;}
'''.replace('@CONSTANTS@', '\n'.join(constants)).replace('@RECORDS@', records).replace(
        '@CHECKS@', checks).replace('@LAYOUT@', '\n'.join(layout)).replace(
        '@SAVE_BYTES@', save_bytes).replace('@CONFIG_BYTES@', config_bytes)
