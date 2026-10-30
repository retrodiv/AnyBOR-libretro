"""Bind named allocation policy into probes for unrelated native contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path

from test_historical_player import function


def named_allocation_support(engine):
    """Use actual policy bodies with finite, discarded diagnostic providers.

    Append after the probe's profile variable and allocator providers. This
    preserves its allocator injection and the core's dispatch/zeroing. The
    dedicated allocation contract checks diagnostic contents separately.
    """
    engine = Path(engine)
    headers = [engine / 'source/utils.h', engine / 'source/scriptlib/List.h']
    if not any('obor_profile_malloc_named' in path.read_text() for path in headers):
        return ''
    source = (engine / 'source/utils.c').read_text()
    bodies = []
    for name in ('obor_profile_malloc_named', 'obor_profile_calloc_named',
                 'obor_profile_realloc_named'):
        body = function(source, name)
        body = body.replace('getFreeRam(BYTES)', 'obor_test_allocation_ram()')
        body = body.replace('writeToLogFile(', 'obor_test_allocation_log(')
        bodies.append(body)
    return '''
#include <stdlib.h>
#include <string.h>
static unsigned long long obor_test_allocation_ram(void) { return 0; }
static void obor_test_allocation_log(const char *format, ...) { (void)format; }
''' + '\n'.join(bodies) + '\n'


def bind_named_allocation_support(program, engine, *, marker=None):
    """Declare policy before cloned callers; place its bodies explicitly.

    The default appends outside probe-local allocator macro scopes. A probe
    that deliberately injects those allocators can supply one explicit marker.
    """
    if not isinstance(program, str):
        raise ValueError('Native probe source must be text')
    support = named_allocation_support(engine)
    if not support:
        return program
    declarations = '''#include <stddef.h>
void *obor_profile_malloc_named(const char *, size_t);
void *obor_profile_calloc_named(const char *, size_t);
void *obor_profile_realloc_named(void *, size_t);
'''
    if marker is not None:
        if not isinstance(marker, str) or not marker or program.count(marker) != 1:
            raise ValueError('One explicit named allocation policy marker required')
        return declarations + program.replace(marker, support)
    return declarations + program + support
