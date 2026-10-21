"""Exercise panel-order binding with loaded, absent and repeated panels.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import unittest

from test_historical_behavior import native

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class PanelOrderTests(unittest.TestCase):
    def test_absent_panels_preserve_slots_and_loaded_layer_bindings(self):
        for engine in ('3741', '3842', '4086', '4432', '6391', '7142', '7533', '8023'):
            with self.subTest(engine=engine):
                self.check_source((ROOT / 'src/engines' / engine / 'openbor.c').read_text(),
                                  legacy_xoffset=engine in ('3741', '3842'))

    def check_source(self, source, *, legacy_xoffset):
        start = source.index('for', source.index('//panels, normal neon screen'))
        opening = source.index('{', start)
        depth = 1
        end = opening + 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        block = source[start:end]
        native(r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
    int token, xoffset;
    struct { int x; } offset;
} s_layer;
typedef struct {
    int numpanels, numlayers, numlayersref;
    s_layer *layers, *layersref;
    s_layer *(*panels)[3];
} s_level;
static int panel_width = 320;
#define __realloc(p, n) do { \
    void *replacement = realloc((p), ((size_t)(n) + 1) * sizeof(*(p))); \
    assert(replacement); (p) = replacement; \
    memset((p) + (n), 0, sizeof(*(p))); \
} while (0)
static void bind_panels(s_level *level, int (*panels)[3],
                const int *order, int panelcount) {
    int i, j;
    s_layer *bgl;
    (void)panelcount;
    BLOCK
}
static void init(s_level *level, int count) {
    memset(level, 0, sizeof(*level));
    level->numpanels = count;
    level->numlayers = 5;
    level->layers = calloc(5, sizeof(*level->layers));
    level->panels = calloc((size_t)count, sizeof(*level->panels));
    level->layersref = calloc(1, sizeof(*level->layersref));
    assert(level->layers && level->panels && level->layersref);
    for(int n=0;n<5;++n) level->layers[n].token=100+n;
    level->layersref[0].token=999;
    level->numlayersref=1;
}
static void clear(s_level *level) {
    free(level->layers); free(level->layersref); free(level->panels);
}
int main(void) {
    s_level level;
    int (*panels)[3]=calloc(2,sizeof(*panels));
    assert(panels);
    panels[0][0]=1;panels[0][1]=2;
    panels[1][0]=3;panels[1][2]=4;
    int order[]={1,0,1};
    init(&level,3);
    bind_panels(&level,panels,order,2);
    const int tokens[]={999,103,104,101,102,103,104};
    assert(level.numpanels==3 && level.numlayersref==7);
    for(int n=0;n<7;++n) assert(level.layersref[n].token==tokens[n]);
    for(int n=1;n<7;++n) assert(XOFFSET(level.layersref[n])==320*((n-1)/2));
    assert((intptr_t)level.panels[0][0]==1 && !level.panels[0][1]);
    assert((intptr_t)level.panels[0][2]==2);
    assert((intptr_t)level.panels[1][0]==3 && (intptr_t)level.panels[1][1]==4);
    assert((intptr_t)level.panels[2][0]==5 && (intptr_t)level.panels[2][2]==6);
    clear(&level);free(panels);

    /* One loaded panel followed by absent slots must not read beyond it. */
    panels=calloc(1,sizeof(*panels));assert(panels);panels[0][0]=1;
    int sparse[]={0,1,-1,INT_MAX,0};
    init(&level,5);
    bind_panels(&level,panels,sparse,1);
    assert(level.numpanels==5 && level.numlayersref==3);
    assert(level.layersref[1].token==101 && level.layersref[2].token==101);
    assert(XOFFSET(level.layersref[1])==0 && XOFFSET(level.layersref[2])==1280);
    for(int n=1;n<4;++n) for(int j=0;j<3;++j) assert(!level.panels[n][j]);
    assert((intptr_t)level.panels[0][0]==1 && (intptr_t)level.panels[4][0]==2);
    clear(&level);free(panels);

    int absent[]={0,25};
    init(&level,2);
    bind_panels(&level,NULL,absent,0);
    assert(level.numpanels==2 && level.numlayersref==1);
    assert(level.layersref[0].token==999);
    for(int n=0;n<2;++n) for(int j=0;j<3;++j) assert(!level.panels[n][j]);
    clear(&level);
    return 0;
}
'''.replace('BLOCK', block).replace(
            '#include <assert.h>', '#define XOFFSET(v) ((v).' +
            ('xoffset' if legacy_xoffset else 'offset.x') + ')\n#include <assert.h>'))


if __name__ == '__main__':
    unittest.main()
