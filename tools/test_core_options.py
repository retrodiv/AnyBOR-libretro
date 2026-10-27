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
HEADER = Path(os.environ.get('OBOR_OPTIONS_HEADER', ROOT / 'src/glue/obor_engines.h'))
STATE = Path(os.environ.get('OBOR_STATE_CONFIG_HEADER',
                            ROOT / 'src/port/libretro/obor_state_config.h'))


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
    getter = function(glue, 'get_engine_option')
    fixtures = [('actual', actual)]
    for count in (1, capacity - 3, capacity - 2, capacity - 1,
                  capacity, capacity + 15, capacity * 2, capacity * 4):
        # Maximum permitted display length, deliberately different at the end.
        labels = [('profile-' + str(i)).ljust(47, 'x') for i in range(count)]
        declarations = ('struct profile_entry { const char *disp; };\n'
                        'static const profile_entry kProfiles[] = {\n' +
                        ',\n'.join('{' + json.dumps(label) + '}' for label in labels) + '\n};')
        fixtures.append(('list_' + str(count), declarations))
    source = r'''
#include <assert.h>
#include <stdint.h>
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
    const char *selected;
};
static frontend_fixture *active;
static unsigned registration_checks, selection_checks;

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
static void check_values(const option_snapshot &option) {
    assert(!option.key.empty() && !option.values.empty());
    assert(option.default_value==option.values[0]);
    if (option.key=="obor_engine") {
        assert(option.default_value=="Auto");
        assert(option.values.size()==active->profiles.size()+1);
        for (size_t i=0;i<active->profiles.size();++i)
            assert(option.values[i+1]==active->profiles[i]);
    }
    if (option.key=="obor_state_content") assert(option.default_value==OBOR_STATE_CONTENT_DEFAULT);
    if (option.key=="obor_state_compression") assert(option.default_value==OBOR_STATE_COMPRESSION_DEFAULT);
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
        check_values(option);active->options.push_back(option);
    }
}
static void read_legacy(const retro_variable *variables) {
    assert(variables);
    for (const retro_variable *var=variables;var->key;++var) {
        assert(var->value);
        const char *values=strstr(var->value,"; ");assert(values);
        option_snapshot option;option.key=var->key;option.values=split(values+2);
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
        assert(!strcmp(var->key,"obor_engine"));var->value=active->selected;return true;
    }
    assert(!"unexpected environment call");return false;
}
'''.replace('STATE_HEADER', json.dumps(STATE.resolve().as_posix()))
    source += '\n' + macro + '\n'
    calls = []
    for name, declarations in fixtures:
        source += '\nnamespace ' + name + ' {\n' + declarations + '\n'
        source += 'static retro_environment_t env_cb;\n' + registration + '\n' + getter
        source += r'''
void run(void) {
    char output[48];get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
    std::vector<std::string> profiles;
    for (size_t i=0;i<sizeof(kProfiles)/sizeof(*kProfiles);++i) {
        assert(strlen(kProfiles[i].disp)<sizeof(output));profiles.push_back(kProfiles[i].disp);
    }
    std::vector<option_snapshot> baseline;
    static const unsigned versions[]={0,1,2,9,2};
    for (unsigned test=0;test<sizeof(versions)/sizeof(*versions);++test) {
        for (unsigned repeat=0;repeat<2;++repeat) {
            frontend_fixture fixture={};fixture.version=versions[test];
            fixture.version_available=test!=4;fixture.categories=test==2;fixture.profiles=profiles;
            fixture.v2_expected=test!=4 && versions[test]>=2 && profiles.size()<=RETRO_NUM_CORE_OPTION_VALUES_MAX-2;
            active=&fixture;retro_set_environment(environment);
            assert(fixture.queries==1 && fixture.registrations==1);
            assert(!fixture.options.empty());
            if (baseline.empty()) baseline=fixture.options;else assert(fixture.options==baseline);
            std::vector<option_snapshot> captured=fixture.options;fixture.options.clear();
            // Storage remains valid after registration returns and on repeated registration.
            if (fixture.retained_v2) read_v2(fixture.retained_v2);else read_legacy(fixture.retained_legacy);
            assert(fixture.options==captured);
            for (size_t i=0;i<profiles.size();++i) {
                fixture.selected=profiles[i].c_str();memset(output,'?',sizeof(output));
                get_engine_option(output,sizeof(output));assert(profiles[i]==output);++selection_checks;
            }
            fixture.selected=NULL;get_engine_option(output,sizeof(output));assert(!strcmp(output,"Auto"));
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
