"""Check complete profile registration and the actual option getter with native C++.

No engine or frontend is launched. Synthetic profile lists exercise the ABI boundary.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from test_historical_player import function
from runtime_evidence import record_process

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
GLUE = Path(os.environ.get('OBOR_OPTIONS_GLUE', ROOT / 'src/glue/libretro.cpp'))
HEADER = Path(os.environ.get('OBOR_OPTIONS_HEADER', ROOT / 'src/glue/anybor_engines.h'))
STATE = Path(os.environ.get('OBOR_STATE_CONFIG_HEADER',
                            ROOT / 'src/port/libretro/anybor_state_config.h'))


def program(glue, header):
    capacity = re.search(r'^#define RETRO_NUM_CORE_OPTION_VALUES_MAX\s+(\d+)\s*$',
                         (ROOT / 'src/third_party/libretro.h').read_text(), re.M)
    assert capacity is not None
    capacity = int(capacity[1])
    assert capacity >= 4
    start = header.index('typedef struct { int build; const char *name; const char *disp;')
    actual = header[start:header.index('\n};', start) + 3]
    macro = glue[glue.index('#define ENGINE_OPT_INFO '):
                 glue.index('\nvoid retro_set_environment(')]
    registration = function(glue, 'retro_set_environment')
    helpers = glue[glue.index('struct engine_option_group {'):glue.index('static bool g_analog')]
    option_readers = '\n'.join(function(glue, name) for name in ('opt_is_on', 'state_option'))
    fixtures = [('actual', actual)]
    for count in (0, 1, capacity - 3, capacity - 2):
        # Exercise empty groups and the last usable ABI slot, with long labels.
        entries = []
        for first in (3000, 3500, 3750, 4000, 5001):
            for i in range(count):
                build = first + i
                label = ('profile-' + str(build)).ljust(47, 'x')
                entries.append('{' + str(build) + ', "' + str(build) + '", ' + json.dumps(label) + '}')
        if not entries:
            entries = ['{3000, "3000", "only-first-group"}']
        declarations = ('struct profile_entry { int build; const char *name, *disp; };\n'
                        'static const profile_entry kProfiles[] = {\n' +
                        ',\n'.join(entries) + '\n};')
        fixtures.append(('list_' + str(count), declarations))
    fixtures.append(('endpoints', 'struct profile_entry { int build; const char *name, *disp; };\n'
        'static const profile_entry kProfiles[] = {' + ','.join(
            '{' + str(b) + ',"' + str(b) + '","boundary-' + str(b) + '"}'
            for b in (3000, 3499, 3500, 3749, 3750, 3999, 4000, 4999, 5001, 2147483647)) + '};'))
    source = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include <vector>
#include "libretro.h"
#include STATE_HEADER

struct option_snapshot {
    std::string key, default_value;
    std::vector<std::string> values;
    bool operator==(const option_snapshot &other) const {
        return key==other.key && default_value==other.default_value && values==other.values;
    }
};
struct frontend_fixture {
    unsigned version;
    bool version_available, categories, v2_expected;
    unsigned queries, registrations;
    std::vector<std::string> profiles;
    std::vector<option_snapshot> options;
    const retro_core_options_v2 *retained_v2;
    const retro_variable *retained_legacy;
    const char *selected, *option_value, *groups[5];
    std::vector<int> builds;
    bool visible[5], display_supported;
    unsigned display_calls;
    bool (*update_display)(void);
};
static frontend_fixture *active;
static unsigned registration_checks, selection_checks;
static const char *const expected_keys[]={
    "anybor_crt_tv","anybor_analog","anybor_rumble","anybor_macros","anybor_engine",
    "anybor_engine_3000_3499","anybor_engine_3500_3749","anybor_engine_3750_3999",
    "anybor_engine_4000_4999","anybor_engine_5000_plus",
    "anybor_state_content","anybor_state_compression","anybor_gamelog",
    "anybor_clear_local_data","anybor_clear_game_cache","anybor_clear_all_caches"
};

static std::vector<std::string> split(const char *text) {
    assert(text && *text);
    std::vector<std::string> result;
    const char *begin=text;
    for (;;) {
        const char *end=strchr(begin,'|');
        result.push_back(end?std::string(begin,end):std::string(begin));
        assert(!result.back().empty());
        if (!end) return result;
        begin=end+1;
    }
}
static int group_for(int build) {
    if (build>=3000 && build<=3499) return 0;
    if (build>=3500 && build<=3749) return 1;
    if (build>=3750 && build<=3999) return 2;
    if (build>=4000 && build<=4999) return 3;
    if (build>5000) return 4;
    assert(!"unassigned profile");return -1;
}
static int group_key(const char *key) {
    for (unsigned i=0;i<5;++i) if (!strcmp(key,expected_keys[5+i])) return (int)i;
    return -1;
}
static void check_values(const option_snapshot &option) {
    assert(!option.key.empty() && !option.values.empty());
    assert(option.key.compare(0,7,"anybor_")==0);
    assert(option.default_value==option.values[0]);
    if (option.key=="anybor_engine") {
        assert(option.default_value=="Auto");
        assert(option.values==std::vector<std::string>({"Auto","More"}));
    }
    int group=group_key(option.key.c_str());
    if (group>=0) {
        std::vector<std::string> expected={"None"};
        for (size_t i=0;i<active->profiles.size();++i)
            if (group_for(active->builds[i])==group) expected.push_back(active->profiles[i]);
        assert(option.default_value=="None" && option.values==expected);
    }
    if (option.key=="anybor_state_content") assert(option.default_value==OBOR_STATE_CONTENT_DEFAULT);
    if (option.key=="anybor_state_compression") assert(option.default_value==OBOR_STATE_COMPRESSION_DEFAULT);
}
static void read_v2(const retro_core_options_v2 *options) {
    assert(options && options->definitions && options->categories);
    static const char *categories[]={"video","input","system","development"};
    for (size_t i=0;i<sizeof(categories)/sizeof(*categories);++i)
        assert(options->categories[i].key && !strcmp(options->categories[i].key,categories[i]));
    assert(!options->categories[4].key);
    for (const retro_core_option_v2_definition *def=options->definitions;def->key;++def) {
        assert(def->desc && def->info && def->default_value);
        option_snapshot option; option.key=def->key; option.default_value=def->default_value;
        size_t i=0;
        for (;i<RETRO_NUM_CORE_OPTION_VALUES_MAX && def->values[i].value;++i)
            option.values.push_back(def->values[i].value);
        assert(i<RETRO_NUM_CORE_OPTION_VALUES_MAX && !def->values[i].label);
        assert(def->category_key);
        const char *category = !strcmp(def->key,"anybor_crt_tv") ? "video" :
            (!strcmp(def->key,"anybor_analog") || !strcmp(def->key,"anybor_rumble") || !strcmp(def->key,"anybor_macros")) ? "input" :
            !strncmp(def->key,"anybor_clear_",13) ? "development" : "system";
        assert(!strcmp(def->category_key,category));
        if (!strcmp(def->key,"anybor_engine")) {
            assert(def->values[0].label && !strcmp(def->values[0].label,"Auto (detect from file)"));
            assert(!strcmp(def->values[1].value,"More"));
            assert(def->values[1].label && !strcmp(def->values[1].label,"More..."));
        }
        if (group_key(def->key)>=0) {
            assert(!strcmp(def->default_value,"None") && !strcmp(def->values[0].value,"None"));
            assert(def->values[0].label && !strcmp(def->values[0].label,"-"));
        }
        check_values(option);
        active->options.push_back(option);
    }
    for (const auto &option : active->options) check_values(option);
}
static void read_legacy(const retro_variable *variables) {
    assert(variables);
    for (const retro_variable *var=variables;var->key;++var) {
        assert(var->value);
        const char *values=strstr(var->value,"; ");assert(values);
        option_snapshot option;option.key=var->key;option.values=split(values+2);
        // v0 has no separate labels; verify its visible spelling, then compare
        // the logical choices with v2's stable stored values.
        if (option.key=="anybor_engine") {
            assert(option.values==std::vector<std::string>({"Auto","More..."}));
            option.values[1]="More";
        }
        if (group_key(var->key)>=0) {
            assert(option.values[0]=="-");option.values[0]="None";
        }
        option.default_value=option.values[0];check_values(option);active->options.push_back(option);
    }
}
static bool environment(unsigned command,void *data) {
    assert(active);
    if (command==RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION) {
        ++active->queries;*(unsigned*)data=active->version;return active->version_available;
    }
    if (command==RETRO_ENVIRONMENT_SET_CORE_OPTIONS_V2) {
        assert(active->v2_expected);++active->registrations;
        active->retained_v2=(const retro_core_options_v2*)data;
        read_v2(active->retained_v2);
        // False means categories unsupported, not registration failure.
        return active->categories;
    }
    if (command==RETRO_ENVIRONMENT_SET_VARIABLES) {
        assert(!active->v2_expected);++active->registrations;
        active->retained_legacy=(const retro_variable*)data;
        read_legacy(active->retained_legacy);return true;
    }
    if (command==RETRO_ENVIRONMENT_GET_VARIABLE) {
        retro_variable *var=(retro_variable*)data;
        bool known=false;
        for (size_t i=0;i<sizeof(expected_keys)/sizeof(*expected_keys);++i)
            if (!strcmp(var->key,expected_keys[i])) known=true;
        int group=group_key(var->key);
        if (group>=0) {var->value=active->groups[group];return var->value!=NULL;}
        assert(known);
        var->value=!strcmp(var->key,"anybor_engine")?active->selected:active->option_value;
        return true;
    }
    if (command==RETRO_ENVIRONMENT_SET_CORE_OPTIONS_UPDATE_DISPLAY_CALLBACK) {
        active->update_display=((retro_core_options_update_display_callback*)data)->callback;
        return active->display_supported;
    }
    if (command==RETRO_ENVIRONMENT_SET_CORE_OPTIONS_DISPLAY) {
        const retro_core_option_display *display=(const retro_core_option_display*)data;
        int group=group_key(display->key);assert(group>=0);
        active->visible[group]=display->visible;++active->display_calls;
        return active->display_supported;
    }
    assert(!"unexpected environment call");return false;
}
'''.replace('STATE_HEADER', json.dumps(STATE.resolve().as_posix()))
    source += '\n' + macro + '\n'
    calls = []
    for name, declarations in fixtures:
        source += '\nnamespace ' + name + ' {\n' + declarations + '\n'
        source += 'static retro_environment_t env_cb;\n' + helpers + '\n' + registration + '\n' + option_readers
        source += r'''
void run(void) {
    char output[48];get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
    std::vector<std::string> profiles;
    std::vector<int> builds;
    for (size_t i=0;i<sizeof(kProfiles)/sizeof(*kProfiles);++i) {
        assert(strlen(kProfiles[i].disp)<sizeof(output));profiles.push_back(kProfiles[i].disp);builds.push_back(kProfiles[i].build);
    }
    std::vector<option_snapshot> baseline;
    static const unsigned versions[]={0,1,2,9,2};
    for (unsigned test=0;test<sizeof(versions)/sizeof(*versions);++test) {
        for (unsigned repeat=0;repeat<2;++repeat) {
            frontend_fixture fixture={};fixture.version=versions[test];
            fixture.version_available=test!=4;fixture.categories=test==2;fixture.profiles=profiles;
            fixture.builds=builds;fixture.display_supported=test!=1;
            fixture.v2_expected=test!=4 && versions[test]>=2;
            const char *manual=fixture.v2_expected?"More":"More...";
            const char *empty=fixture.v2_expected?"None":"-";
            for (unsigned g=0;g<5;++g) fixture.groups[g]=empty;
            fixture.selected=repeat?manual:"Auto";
            active=&fixture;retro_set_environment(environment);
            assert(fixture.queries==1 && fixture.registrations==1);
            assert(!fixture.options.empty());
            assert(fixture.options.size()==sizeof(expected_keys)/sizeof(*expected_keys));
            for (size_t i=0;i<fixture.options.size();++i) assert(fixture.options[i].key==expected_keys[i]);
            if (baseline.empty()) baseline=fixture.options;else assert(fixture.options==baseline);
            std::vector<option_snapshot> captured=fixture.options;fixture.options.clear();
            // Storage remains valid after registration returns and on repeated registration.
            if (fixture.retained_v2) read_v2(fixture.retained_v2);else read_legacy(fixture.retained_legacy);
            assert(fixture.options==captured);
            assert(fixture.update_display && fixture.display_calls==5);
            for (unsigned g=0;g<5;++g) assert(fixture.visible[g]==(repeat!=0));
            assert(!fixture.update_display());
            fixture.selected="Auto";fixture.update_display();
            fixture.selected=manual;
            assert(fixture.update_display()==fixture.display_supported);
            for (unsigned g=0;g<5;++g) assert(fixture.visible[g]);
            assert(!fixture.update_display());
            get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
            for (size_t i=0;i<profiles.size();++i) {
                int group=group_for(builds[i]);fixture.groups[group]=profiles[i].c_str();
                get_engine_option(output,sizeof(output));assert(profiles[i]==output);++selection_checks;
                fixture.groups[group]=kProfiles[i].name;
                get_engine_option(output,sizeof(output));assert(profiles[i]==output);
                // Auto always wins over hidden retained values.
                fixture.selected="Auto";assert(fixture.update_display()==fixture.display_supported);
                for (unsigned g=0;g<5;++g) assert(!fixture.visible[g]);
                get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
                fixture.selected=manual;fixture.update_display();fixture.groups[group]=empty;
            }
            // Conflicting selections choose the lowest occupied selector.
            for (size_t i=0;i<profiles.size();++i) {
                fixture.groups[group_for(builds[i])]=profiles[i].c_str();
                size_t winner=i;
                for (size_t j=0;j<i;++j) if(group_for(builds[j])>group_for(builds[winner])) winner=j;
                get_engine_option(output,sizeof(output));assert(profiles[winner]==output);
            }
            // Remove occupied groups from the bottom, checking each earlier choice survives.
            for (int group=4;group>=0;--group) {
                const char *expected="Auto";
                for (size_t i=0;i<profiles.size();++i)
                    if (group_for(builds[i])<=group) expected=profiles[i].c_str();
                get_engine_option(output,sizeof(output));assert(!strcmp(output,expected));
                fixture.groups[group]=empty;
            }
            fixture.selected=!strcmp(manual,"More")?"More...":"More";
            get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
            assert(!fixture.update_display());
            fixture.selected=manual;
            fixture.groups[0]="unknown";fixture.groups[1]=NULL;
            fixture.groups[2]="Auto";fixture.groups[3]="More";fixture.groups[4]=empty;
            get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
            // A profile stored in the wrong range is ignored.
            fixture.groups[(group_for(builds[0])+1)%5]=profiles[0].c_str();
            get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
            fixture.selected=NULL;get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
            fixture.selected="obsolete-value";get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
            get_engine_option(output,1);assert(!output[0]);get_engine_option(NULL,0);
            for (size_t i=0;i<fixture.options.size();++i) {
                const option_snapshot &option=fixture.options[i];
                if (option.key.compare(0,13,"anybor_engine")==0) continue;
                const bool state=option.key=="anybor_state_content" || option.key=="anybor_state_compression";
                fixture.option_value=NULL;
                if (state) {
                    assert(state_option(option.key.c_str(),option.values[0].c_str(),option.values[1].c_str())==OBOR_STATE_SETTING_DEFAULT);
                    fixture.option_value=option.values[0].c_str();
                    assert(state_option(option.key.c_str(),option.values[0].c_str(),option.values[1].c_str())==OBOR_STATE_SETTING_ON);
                    fixture.option_value=option.values[1].c_str();
                    assert(state_option(option.key.c_str(),option.values[0].c_str(),option.values[1].c_str())==OBOR_STATE_SETTING_OFF);
                    fixture.option_value="unknown";
                    assert(state_option(option.key.c_str(),option.values[0].c_str(),option.values[1].c_str())==OBOR_STATE_SETTING_DEFAULT);
                } else {
                    assert(opt_is_on(option.key.c_str(),true) && !opt_is_on(option.key.c_str(),false));
                    fixture.option_value="On";assert(opt_is_on(option.key.c_str(),false));
                    fixture.option_value="Off";assert(!opt_is_on(option.key.c_str(),true));
                }
            }
            ++registration_checks;
        }
    }
    env_cb=NULL;active=NULL;
}
}
'''
        calls.append(name + '::run();')
    source += '\nint main(void){\n' + '\n'.join(calls) + r'''
printf("registrations=%u selections=%u\n",registration_checks,selection_checks);
}
'''
    return source, len(fixtures) * 10


class CoreOptionTests(unittest.TestCase):
    def test_crt_option_order_checks_complete_grouped_registration(self):
        from test_crt import check_option_order
        keys = ['anybor_crt_tv', 'anybor_analog', 'anybor_rumble', 'anybor_macros',
                'anybor_engine', 'anybor_engine_3000_3499', 'anybor_engine_3500_3749',
                'anybor_engine_3750_3999', 'anybor_engine_4000_4999', 'anybor_engine_5000_plus',
                'anybor_state_content', 'anybor_state_compression', 'anybor_gamelog',
                'anybor_clear_local_data', 'anybor_clear_game_cache', 'anybor_clear_all_caches']
        for version in (0, 1, 2, 9):
            check_option_order('option_order=' + '|'.join(keys) + '\n', 252, 128, version)
            for bad in (keys[:-1], keys + ['unexpected'], keys[:4] + keys[5:],
                        keys[:5] + list(reversed(keys[5:])), keys + [keys[-1]]):
                with self.assertRaises(AssertionError):
                    check_option_order('option_order=' + '|'.join(bad) + '\n', 252, 128, version)
        with self.assertRaises(AssertionError):
            check_option_order('', 252, 128, 2)

    def test_complete_lists_defaults_lifetimes_and_getter_across_interface_boundary(self):
        inputs = [GLUE, HEADER, STATE, ROOT / 'src/third_party/libretro.h',
                  Path(__file__), Path(function.__code__.co_filename)]
        identities = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        source, registrations = program(GLUE.read_text(), HEADER.read_text())
        result, retired = None, []
        try:
            with tempfile.TemporaryDirectory(prefix='anybor-core-options-') as temp:
                work = Path(temp)
                try:
                    path = work / 'probe.cpp'
                    path.write_text(source)
                    result = subprocess.run(shlex.split(os.environ.get('HOST_CXX', 'c++')) + [
                        '-std=c++11', '-Wall', '-Wextra', '-Werror', '-g',
                        '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                        '-fno-sanitize-recover=undefined', '-I', str(ROOT / 'src/third_party'),
                        str(path), '-o', str(work / 'probe')], capture_output=True,
                        text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    result = subprocess.run([str(work / 'probe')], capture_output=True,
                                            text=True, timeout=20, cwd=work)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertRegex(result.stdout, r'^registrations=' + str(registrations) + r' selections=[1-9][0-9]*\n$')
                    self.assertEqual(result.stderr, '')
                    self.assertTrue(all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest
                                        for p, digest in identities.items()), 'Probe inputs changed')
                    print(result.stdout.strip())
                finally:
                    retired = [dict(path=str(p), bytes=p.stat().st_size,
                                    sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                               for p in sorted(work.iterdir()) if p.is_file()]
        finally:
            self.assertTrue(all(not Path(row['path']).exists() for row in retired))
            if result is not None:
                record_process('core-options', 'catalogue-boundary', result,
                               dict(inputs=identities, temporary_files=retired,
                                    temporary_files_retired=True, full_engine_acceptance=False))


if __name__ == '__main__':
    unittest.main()
