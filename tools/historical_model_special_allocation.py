"""Pair native constructor values with the initial special-allocation contract.

The allocation ordinal and expected load-stop response are explicit source
contracts. The valid constructor cases still run in full. Script allocation,
cache lookup and shutdown are observations; full model disposal is separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_model_initialization import render_model_initialization


def render_model_special_allocation(parts, *, constructor, failed_ordinal,
                                    expected_shutdown):
    if (not isinstance(constructor, dict) or
            type(failed_ordinal) is not int or not 1 <= failed_ordinal < 64 or
            type(expected_shutdown) is not bool):
        raise ValueError('Explicit bounded constructor, ordinal and load-stop contract required')
    try:
        code = render_model_initialization(parts, **constructor)
    except TypeError as error:
        raise ValueError('Declared native constructor options required') from error

    def replace_once(before, after):
        nonlocal code
        if code.count(before) != 1:
            raise ValueError('Maintained constructor observation protocol changed')
        code = code.replace(before, after, 1)

    replace_once('#include <assert.h>\n', '#include <assert.h>\n#include <setjmp.h>\n')
    replace_once('static unsigned allocated,script_calls,lookup_position;',
                 '''static unsigned allocated,script_calls,lookup_position;
static unsigned fault_enabled,allocation_attempts,fault_calls,shutdown_calls;
static unsigned valid_cases,valid_checks;
static s_model *constructor_result;
static jmp_buf constructor_stop;
enum {FAILED_ORDINAL=%d,EXPECTED_SHUTDOWN=%d};
_Static_assert(FREESPECIAL_COUNT>=MAX_SPECIALS,"Configured special count below native minimum");'''
                 % (failed_ordinal, expected_shutdown))
    replace_once('_Static_assert(FREESPECIAL_COUNT>=MAX_SPECIALS,"Configured special count below native minimum");',
                 '''_Static_assert(FREESPECIAL_COUNT>=MAX_SPECIALS,"Configured special count below native minimum");
_Static_assert(ANIMATION_COUNT>=MAX_ANIS,"Configured animation count below native minimum");''')
    allocator = '''static void *observed_calloc(size_t count,size_t size) {
 assert(allocated<64 && size && count && count<=(1u<<20)/size);
 void *pointer=calloc(count,size);assert(pointer);
 allocations[allocated]=pointer;allocation_sizes[allocated++]=count*size;return pointer;
}'''
    replace_once(allocator, '''static void *observed_calloc(size_t count,size_t size) {
 assert(allocated<64 && size && count && count<=(1u<<20)/size);
 if(fault_enabled && allocation_attempts++==FAILED_ORDINAL) {
  assert(count*size==SPECIAL_ELEMENTS*sizeof(s_com));
  ++fault_calls;return NULL;
 }
 void *pointer=calloc(count,size);assert(pointer);
 allocations[allocated]=pointer;allocation_sizes[allocated++]=count*size;return pointer;
}''')
    replace_once('''static void observed_shutdown(int status,const char *format,...) {
 (void)status;(void)format;fputs("Unexpected constructor shutdown\\n",stderr);abort();
}''', '''static void observed_shutdown(int status,const char *format,...) {
 assert(fault_enabled && status==1 && !strcmp(format,"native allocation failure"));
 ++shutdown_calls;longjmp(constructor_stop,1);
}''')
    replace_once('int main(void) {', 'static int valid_constructor_main(void) {')
    replace_once(''' printf("{\\"status\\":\\"PASS\\",\\"cases\\":%u,\\"checks\\":%u}\\n",
        (unsigned)(sizeof(cases)/sizeof(*cases)),checks);return 0;''',
                 ''' valid_cases=(unsigned)(sizeof(cases)/sizeof(*cases));
 valid_checks=checks;return 0;''')
    code += r'''
static void constructor_with_stop(void) {
 if(setjmp(constructor_stop)==0)
  constructor_result=init_model(cases[0].cacheindex,cases[0].unload);
}
int main(void) {
 assert(!fault_enabled && valid_constructor_main()==0);
 const struct constructor_case *test=&cases[0];
 allocated=script_calls=lookup_position=0;script_argument=NULL;
 allocation_attempts=fault_calls=shutdown_calls=0;constructor_result=NULL;
 fixture_magic=test->magic_type;fixture_jumpheight=test->jumpheight;
 fixture_jumpspeed=test->jumpspeed;fixture_grabdistance=test->grabdistance;
 fixture_noatk_duration=test->duration;
 fault_enabled=1;phase="native allocation response";constructor_with_stop();
 phase="special allocation result";
 assert(fault_calls==1 && allocation_attempts>FAILED_ORDINAL);
 assert(shutdown_calls==EXPECTED_SHUTDOWN);
 if(EXPECTED_SHUTDOWN) {
  assert(!constructor_result && !script_calls && !lookup_position);
 } else {
  assert(constructor_result && !constructor_result->special && script_calls==1);
  assert(lookup_position==sizeof(lookup_sequence)/sizeof(*lookup_sequence));
 }
 /* Retire only allocations observed from this isolated constructor. This
  * does not replace or validate the native model/script disposer. */
 for(unsigned i=0;i<allocated;++i)free(allocations[i]);
 printf("{\"status\":\"PASS\",\"valid_cases\":%u,\"valid_checks\":%u,\"failure_cases\":1,\"shutdown\":%u}\n",
        valid_cases,valid_checks,shutdown_calls);return 0;
}
'''
    return code
