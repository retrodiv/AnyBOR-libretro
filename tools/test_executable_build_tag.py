"""Read synthetic executable banners as data, without executing a binary.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import unittest
from test_historical_behavior import native
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
GLUE = Path(os.environ.get('OBOR_GLUE_SOURCE', ROOT / 'src/glue/libretro.cpp'))


class ExecutableBuildTagTests(unittest.TestCase):
    def test_blank_or_invalid_build_blocks_date_inference_at_every_file_position(self):
        native(r'''
#include <assert.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned date_calls;
static int date_to_build(int year,int month){
    assert(year==2023 && month==5);++date_calls;return 4242;
}
@READER@
static void check(const char *bytes,int expected,unsigned dates){
    FILE *file=fopen("banner.bin","wb");assert(file);
    assert(fwrite(bytes,1,strlen(bytes),file)==strlen(bytes));assert(!fclose(file));
    date_calls=0;int actual=build_from_exe("banner.bin");
    if(actual!=expected)fprintf(stderr,"banner=%s actual=%d expected=%d\n",bytes,actual,expected);
    assert(actual==expected);assert(date_calls==dates);
}
int main(void){
    check("OpenBOR v3.0 Build , Compile Date: May 12 2023",0,0);
    check("Compile Date: May 12 2023......Build ",0,0);
    check("OpenBOR Build not-a-number, Compile Date: May 12 2023",0,0);
    check("OpenBOR Build 999999999999999999999, Compile Date: May 12 2023",0,0);
    check("OpenBOR Build 6391, Compile Date: May 12 2023",6391,0);
    check("Build 6391",6391,0);
    check("OpenBOR Build 0000006391",6391,0);
    check("Compile Date: May 12 2023",4242,1);
    check("Compile Date: May 12 999999999999999999999",0,0);
    check("Build ",0,0);check("",0,0);
    assert(build_from_exe("missing.bin")==0);
}
'''.replace('@READER@', function(GLUE.read_text(), 'build_from_exe')))


if __name__ == '__main__':
    unittest.main()
