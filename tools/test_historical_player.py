"""Exercise the historical player API at its actual script entry points.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', SOURCE / 'src/engines/3842'))


def player_fixture(members):
    """Authored script reproducing a rejected missing score without game data."""
    result = dict(members)
    result['data/script.txt'] = b'alwaysupdate 1\n'
    result['data/scripts/updated.c'] = b'''void main() {
    if(getglobalvar("hp_checked") == 1) return;
    setglobalvar("hp_checked", 1);
    void result = changeplayerproperty(0, "score", 17);
    if(result == 1) log("HISTORICAL_RETURN_ONE\\n");
    else if(result == NULL()) log("HISTORICAL_RETURN_VOID\\n");
    else log("HISTORICAL_BAD_RETURN\\n");
    log("HISTORICAL_BEFORE_REJECT\\n");
    result = changeplayerproperty(0, "score", getglobalvar("hp_missing"));
    if(result == 0 && getplayerproperty(0, "score") == 17)
        log("HISTORICAL_REJECTION_UNCHANGED\\n");
    else log("HISTORICAL_BAD_REJECTION\\n");
}
'''
    return result


def check_player_continuation(log, profile):
    """Require the native contract on both sides of the historical boundary."""
    legacy = int(profile) < 3797
    expected = ['HISTORICAL_RETURN_ONE' if legacy else 'HISTORICAL_RETURN_VOID',
                'HISTORICAL_BEFORE_REJECT']
    if legacy:
        expected.append('HISTORICAL_REJECTION_UNCHANGED')
    # Error dumps can contain the source and its string literals. Only actual
    # complete log records may establish that the continuation executed.
    markers = re.findall(r'(?m)^(?:\[(?:OpenBOR(?::[0-9]+)?|game)\][ \t]*)?'
                         r'(HISTORICAL_[A-Z_]+)[ \t]*\r?$', log)
    exception = "There's an exception while executing script" in log
    if markers != expected or exception == legacy:
        raise RuntimeError('Historical player rejected-value contract differs: ' + log)


def function(source, name):
    start = re.search(r'(?m)^[ \t]*(?!(?:if|else|while|return|switch|case)\b)'
                      r'[A-Za-z_]\w*(?:[ \t*]+[A-Za-z_]\w*)*[ \t*]+\b' + name +
                      r'\([^;{}]*?\)\s*(?://[^\n]*\n\s*)?\{', source)
    if start is None:
        raise AssertionError('Missing native function ' + name)
    # Braces in comments, strings and character constants are data. In
    # particular, model-loading code contains inline script delimiters.
    tokens = re.compile(r'/\*.*?\*/|//(?:\\(?:\r?\n|[\s\S])|[^\n\\])*|'
                        r'"(?:\\[\s\S]|[^"\\])*"|'
                        r"'(?:\\[\s\S]|[^'\\])*'|[{}]", re.S)
    depth = 1
    for token in tokens.finditer(source, start.end()):
        if token[0] == '{':
            depth += 1
        elif token[0] == '}':
            depth -= 1
            if depth == 0:
                return source[start.start():token.end()] + '\n'
    raise AssertionError('Unfinished native function ' + name)


class HistoricalPlayerTests(unittest.TestCase):
    def test_native_function_extraction_ignores_braces_in_data(self):
        sample = r'''int sample(void) {
    const char *text = "} quoted { \" }";
    char brace = '}'; /* } } { */
    // } followed by a continued comment \
    } {
    if(brace) { return text[0]; }
    return 0;
}
'''
        self.assertEqual(function(sample + 'int other(void) {return 7;}\n', 'sample'), sample)
        calls = '''int caller(void) {
    if(other() &&
                 sample()) {
        return sample();
    }
}
'''
        self.assertEqual(function(calls + sample, 'sample'), sample)
        crlf = sample.replace('\n', '\r\n')
        self.assertEqual(function(crlf, 'sample'), crlf.rstrip('\r\n') + '\n')
        with self.assertRaisesRegex(AssertionError, 'Unfinished'):
            function('int sample(void) { const char *text = "}";', 'sample')

    def test_runtime_check_requires_executed_continuation(self):
        legacy = '\n'.join('[OpenBOR] ' + marker for marker in (
            'HISTORICAL_RETURN_ONE', 'HISTORICAL_BEFORE_REJECT',
            'HISTORICAL_REJECTION_UNCHANGED'))
        modern = ('[OpenBOR] HISTORICAL_RETURN_VOID\n'
                  '[OpenBOR] HISTORICAL_BEFORE_REJECT\n'
                  "[OpenBOR] There's an exception while executing script 'updated'\n"
                  'log("HISTORICAL_REJECTION_UNCHANGED\\n");')
        check_player_continuation(legacy, '3780')
        check_player_continuation(modern, '3842')
        check_player_continuation(legacy.replace('[OpenBOR]', '[game]'), '3780')
        check_player_continuation(modern.replace('[OpenBOR]', '[game]'), '3842')
        for log, profile in ((modern, '3780'), (legacy, '3842'),
                             (legacy + '\n' + legacy, '3780'),
                             ('log("HISTORICAL_RETURN_ONE");', '3780')):
            with self.subTest(profile=profile), self.assertRaises(RuntimeError):
                check_player_continuation(log, profile)

    def test_names_numeric_ids_returns_rejections_and_mutation(self):
        source = (ENGINE / 'openborscript.c').read_text()
        variants = (ENGINE / 'source/scriptlib/ScriptVariant.c').read_text()
        enum = source[source.index('enum playerproperty_enum {'):]
        enum = enum[:enum.index('};') + 2]
        macro = source[source.index('#define MAPSTRINGS('):]
        macro = macro[:macro.index('\n\n')]
        methods = '\n'.join(function(source, name) for name in (
            'obor_player_property_native', 'mapstrings_playerproperty',
            'openbor_getplayerproperty', 'openbor_changeplayerproperty'))
        conversion = '\n'.join(function(variants, name) for name in (
            'ScriptVariant_ChangeType', 'ScriptVariant_Clear',
            'ScriptVariant_IntegerValue', 'ScriptVariant_ToString'))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef int LONG, HRESULT;
typedef double DOUBLE;
typedef void VOID;
typedef char *LPSTR;
typedef enum { VT_EMPTY=0, VT_INTEGER=1, VT_DECIMAL=2, VT_PTR=5, VT_STR=6 } VARTYPE;
typedef struct {
    union { LONG lVal; VOID *ptrVal; DOUBLE dblVal; int strVal; };
    VARTYPE vt;
} ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(value) ((value)>=0)
#define FAILED(value) ((value)<0)
#define MAX_STR_VAR_LEN 255
static uint32_t obor_profile_build;
typedef struct { int marker; } entity;
typedef struct {
    entity *ent;
    char name[24];
    int colourmap, spawnhealth, spawnmp, lives, playkeys, keys, credits, weapnum;
    unsigned int score;
} player_state;
static player_state player[4];
static entity subject;
static int noshare, credits, weapon_calls, weapon_value, weapon_extra;
static char strings[64][512];
static unsigned next_string;
static char *StrCache_Get(int index) { assert(index>=0 && index<64); return strings[index]; }
static int StrCache_Pop(void) { assert(next_string<64); return next_string++; }
static void StrCache_Collect(int index) { (void)index; }
static void set_weapon(entity *ent, int value, int extra) {
    assert(ent==&subject); ++weapon_calls; weapon_value=value; weapon_extra=extra;
}
static int searchList(const char **names, const char *name, int count) {
    for(int i=0;i<count;++i) if(!strcasecmp(names[i],name)) return i;
    return -1;
}
CONVERSION
ENUM
MACRO
METHODS
static ScriptVariant integer(int value) {
    ScriptVariant v={0}; v.vt=VT_INTEGER; v.lVal=value; return v;
}
static ScriptVariant text(const char *value) {
    ScriptVariant v={0}; ScriptVariant_ChangeType(&v,VT_STR);
    strcpy(StrCache_Get(v.strVal),value); return v;
}
static void reset(void) {
    memset(player,0,sizeof(player)); next_string=0;
    player[0].ent=&subject; player[0].score=731; player[0].colourmap=13;
    player[0].lives=17; player[0].credits=19; player[0].playkeys=23;
    player[0].keys=29; player[0].spawnhealth=31; player[0].spawnmp=37;
    player[0].weapnum=41; strcpy(player[0].name,"before");
    credits=43; noshare=0; weapon_calls=0; weapon_value=weapon_extra=-99;
}
static int set(ScriptVariant *property, ScriptVariant *value,
               ScriptVariant *extra, ScriptVariant *result, int *has_result) {
    ScriptVariant index=integer(0), *args[]={&index,property,value,extra}, *p=result;
    int status=openbor_changeplayerproperty(args,&p,extra?4:3);
    *has_result=p!=NULL; return status;
}
static void expect_result(ScriptVariant *r,int has,int value) {
    assert(has==(obor_profile_build<3797));
    if(has) assert(r->vt==VT_INTEGER && r->lVal==value);
}
int main(void) {
    /* IDs and spellings are independent observations of upstream 3780,
     * 3797, 3798, 3821 and 3842, not numbers derived from the adapter. */
    const unsigned profiles[]={3780,3783,3789,3793,3796,3797,3798,3805,
        3814,3818,3820,3821,3822,3824,3829,3831,3837,3839,3842};
    const char *base_names[]={"colourmap","credits","ent","entity","keys",
        "lives","name","playkeys","score"};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        for(int id=0;id<9;++id) {
            reset(); ScriptVariant prop=text(base_names[id]), *args[]={0,&prop};
            mapstrings_playerproperty(args,2);
            assert(prop.vt==VT_INTEGER && prop.lVal==id);
            mapstrings_playerproperty(args,2); assert(prop.lVal==id);
        }
        for(int by_name=0;by_name<2;++by_name) {
            /* A missing score returns false without changing any state only
             * before3797. It must neither become zero nor abort that script. */
            reset(); player_state before=player[0];
            ScriptVariant prop=by_name?text("score"):integer(8), empty={0}, r={0}; int has;
            int status=set(&prop,&empty,NULL,&r,&has);
            assert(!memcmp(&before,&player[0],sizeof(before)) && credits==43 && weapon_calls==0);
            if(obor_profile_build<3797) { assert(status==S_OK); expect_result(&r,has,0); }
            else assert(status==E_FAIL && !has);
            const int values[]={-17,0,83,999999999,1000000000};
            for(unsigned i=0;i<sizeof(values)/sizeof(*values);++i) {
                reset(); prop=by_name?text("score"):integer(8); ScriptVariant v=integer(values[i]);
                r=(ScriptVariant){0}; assert(set(&prop,&v,NULL,&r,&has)==S_OK);
                unsigned expected=values[i]<0?0:values[i]>999999999?999999999:values[i];
                assert(player[0].score==expected); expect_result(&r,has,1);
            }
            /* Numeric conversion uses the engine's actual variant function. */
            reset(); prop=integer(8); ScriptVariant decimal={0};
            decimal.vt=VT_DECIMAL; decimal.dblVal=51.75; r=(ScriptVariant){0};
            assert(set(&prop,&decimal,NULL,&r,&has)==S_OK && player[0].score==51);
            expect_result(&r,has,1);
        }
        /* All old nonfatal scalar rejections keep their destination intact. */
        const int scalars[]={0,1,5,7,8};
        for(unsigned i=0;i<sizeof(scalars)/sizeof(*scalars);++i) {
            reset(); player_state before=player[0];
            ScriptVariant prop=integer(scalars[i]), v={0}, r={0}; int has;
            int status=set(&prop,&v,NULL,&r,&has);
            assert(!memcmp(&before,&player[0],sizeof(before)) && credits==43);
            if(obor_profile_build<3797) { assert(status==S_OK); expect_result(&r,has,0); }
            else assert(status==E_FAIL && !has);
        }
        /* A string spelling a number is still not a numeric variant. */
        reset(); ScriptVariant score=integer(8), numeric_text=text("0"), number_result={0}; int number_has;
        int number_status=set(&score,&numeric_text,NULL,&number_result,&number_has);
        assert(player[0].score==731);
        if(obor_profile_build<3797) { assert(number_status==S_OK); expect_result(&number_result,number_has,0); }
        else assert(number_status==E_FAIL && !number_has);
        for(int resource=0;resource<2;++resource) {
            reset(); ScriptVariant prop=text(resource?"spawnmp":"spawnhealth");
            ScriptVariant value=integer(59), r={0}; int has;
            int status=set(&prop,&value,NULL,&r,&has);
            if(obor_profile_build<3797)
                assert(status==E_FAIL && !has && player[0].spawnhealth==31 && player[0].spawnmp==37);
            else {
                assert(status==S_OK && !has);
                assert((resource?player[0].spawnmp:player[0].spawnhealth)==59);
            }
        }
        for(int by_name=0;by_name<2;++by_name) {
            reset(); int legacy=obor_profile_build<3797, weapon_id=legacy?9:11;
            ScriptVariant prop=by_name?text("weapon"):integer(weapon_id);
            ScriptVariant value=integer(7), extra=integer(3), r={0}; int has;
            assert(set(&prop,&value,&extra,&r,&has)==S_OK);
            assert(weapon_calls==1 && weapon_value==7 && weapon_extra==3);
            expect_result(&r,has,1);
            /* Reusing the mapped constant must not translate it twice. */
            r=(ScriptVariant){0}; assert(set(&prop,&value,NULL,&r,&has)==S_OK);
            assert(weapon_calls==2 && weapon_extra==0); expect_result(&r,has,1);
            reset(); prop=integer(weapon_id); value=integer(7); extra=(ScriptVariant){0};
            r=(ScriptVariant){0}; int status=set(&prop,&value,&extra,&r,&has);
            assert(weapon_calls==0);
            if(legacy) { assert(status==S_OK); expect_result(&r,has,0); }
            else assert(status==E_FAIL && !has);
            reset(); player[0].ent=NULL; prop=integer(weapon_id); value=integer(7); r=(ScriptVariant){0};
            assert(set(&prop,&value,NULL,&r,&has)==S_OK && !weapon_calls);
            expect_result(&r,has,legacy?0:1);
        }
        /* The renamed weapon-number getter keeps its original numeric ID. */
        reset(); const char *name=obor_profile_build<3821?"weaponum":"weapnum";
        ScriptVariant prop=text(name), index=integer(0), r={0}, *result=&r, *args[]={&index,&prop};
        assert(openbor_getplayerproperty(args,&result,2)==S_OK && result==&r);
        assert(prop.lVal==(obor_profile_build<3797?10:12) && r.vt==VT_INTEGER && r.lVal==41);
        ScriptVariant v=integer(47); int has; r=(ScriptVariant){0};
        int status=set(&prop,&v,NULL,&r,&has);
        if(obor_profile_build<3797) { assert(status==S_OK && player[0].weapnum==41); expect_result(&r,has,1); }
        else if(obor_profile_build<3821) assert(status==E_FAIL && !has && player[0].weapnum==41);
        else { assert(status==S_OK && player[0].weapnum==47); expect_result(&r,has,1); }
        /* Keys became writable one revision after the player API expansion. */
        reset(); prop=integer(4); v=integer(53); r=(ScriptVariant){0}; status=set(&prop,&v,NULL,&r,&has);
        if(obor_profile_build<3797) { assert(status==S_OK && player[0].keys==29); expect_result(&r,has,1); }
        else if(obor_profile_build==3797) assert(status==E_FAIL && !has && player[0].keys==29);
        else assert(status==S_OK && !has && player[0].keys==53);
        /* Unsupported names and invalid name values remain safe errors. */
        reset(); prop=text("no_such_property"); v=integer(1); r=(ScriptVariant){0};
        assert(set(&prop,&v,NULL,&r,&has)==E_FAIL && !has);
        reset(); prop=integer(6); v=(ScriptVariant){0}; r=(ScriptVariant){0};
        assert(set(&prop,&v,NULL,&r,&has)==E_FAIL && !has && !strcmp(player[0].name,"before"));
        reset(); player_state before=player[0]; prop=integer(99); v=integer(1); r=(ScriptVariant){0};
        status=set(&prop,&v,NULL,&r,&has);
        assert(!memcmp(&before,&player[0],sizeof(before)));
        if(obor_profile_build<3797) { assert(status==S_OK); expect_result(&r,has,1); }
        else assert(status==E_FAIL && !has);
        ScriptVariant *short_args[]={&index,&prop}; result=&r;
        assert(openbor_changeplayerproperty(short_args,&result,2)==E_FAIL && result==NULL);
    }
    return 0;
}
'''
        program = program.replace('CONVERSION', conversion).replace('ENUM', enum)
        program = program.replace('MACRO', macro).replace('METHODS', methods)
        with tempfile.TemporaryDirectory(prefix='anybor-historical-player-') as temp:
            work = Path(temp)
            (work / 'probe.c').write_text(program)
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-g',
                '-fsanitize=address,undefined', str(work / 'probe.c'),
                '-o', str(work / 'probe')], check=True, timeout=60)
            subprocess.run([str(work / 'probe')], check=True, timeout=20,
                           stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
