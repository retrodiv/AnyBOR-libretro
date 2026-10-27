/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Include the selected native unit once, retaining its own grammar tables. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef OBOR_ENGINE_BUILD
#error The parser fixture requires its physical engine build
#endif
uint32_t obor_profile_build = OBOR_ENGINE_BUILD;
#include "ParserSet.c"
#undef printf
/* Engine headers can redirect assert to the game's shutdown path. Keep
 * harness checks independent of that external runtime. */
#undef assert
#define assert(condition) do { if(!(condition)) abort(); } while(0)

static void verify(ParserSet *sets, MY_TOKEN_TYPE **table,
                   MY_TOKEN_TYPE *data, size_t count, int is_follow)
{
    int production, token;
    for(production = 0; production < NUMPRODUCTIONS; ++production) {
        uintptr_t address = (uintptr_t)table[production], base = (uintptr_t)data;
        size_t offset;
        unsigned char members[END_OF_TOKENS];
        assert(address >= base && address - base < count * sizeof(*data));
        assert((address - base) % sizeof(*data) == 0);
        offset = (address - base) / sizeof(*data);
        memset(members, 0, sizeof(members));
        while(offset < count && data[offset] != END_OF_TOKENS) {
            assert(data[offset] >= 0 && data[offset] < END_OF_TOKENS);
            members[data[offset]] = 1;
            ++offset;
        }
        assert(offset < count && data[offset] == END_OF_TOKENS);
        for(token = 0; token < END_OF_TOKENS; ++token) {
            BOOL found = is_follow ? ParserSet_Follow(sets, production, token) :
                                    ParserSet_First(sets, production, token);
            assert(!!found == !!members[token]);
        }
        assert(!(is_follow ? ParserSet_Follow(sets, production, (MY_TOKEN_TYPE)-1) :
                             ParserSet_First(sets, production, (MY_TOKEN_TYPE)-1)));
    }
}

int main(void)
{
    struct {
        uint64_t before;
        ParserSet sets;
        uint64_t after;
    } checked;
    memset(&checked, 0x5a, sizeof(checked));
    ParserSet_Buildup(&checked.sets);
    assert(checked.before == UINT64_C(0x5a5a5a5a5a5a5a5a));
    assert(checked.after == UINT64_C(0x5a5a5a5a5a5a5a5a));
    verify(&checked.sets, checked.sets.FirstSet, first, sizeof(first) / sizeof(*first), 0);
    verify(&checked.sets, checked.sets.FollowSet, follow, sizeof(follow) / sizeof(*follow), 1);
    ParserSet_Clear(&checked.sets);
    assert(checked.before == UINT64_C(0x5a5a5a5a5a5a5a5a));
    assert(checked.after == UINT64_C(0x5a5a5a5a5a5a5a5a));
    puts("{\"status\":\"PASS\",\"tables\":2}");
    return 0;
}
