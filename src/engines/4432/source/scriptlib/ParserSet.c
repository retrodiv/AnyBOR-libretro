/* AnyBOR modification record: 2026-10-22.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Keep terminal grammar-table writes within the declared production count
 * while retaining every valid native entry. Select complete native
 * first/follow memberships and error-recovery sets by profile.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4432.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2014 OpenBOR Team
 */

#include "ParserSet.h"
#include "FirstFollow.h"
#include <string.h>

extern unsigned int obor_profile_build;

/* Keep the complete native table shape for each historical grammar. */
static MY_TOKEN_TYPE obor_legacy_first[sizeof(first) / sizeof(*first)];
static MY_TOKEN_TYPE obor_legacy_follow[sizeof(follow) / sizeof(*follow)];

static int obor_parserset_keep_token(MY_TOKEN_TYPE token)
{
    switch(token)
    {
    case TOKEN_BITWISE_NOT:
    case TOKEN_LEFT_ASSIGN:
    case TOKEN_RIGHT_ASSIGN:
    case TOKEN_AND_ASSIGN:
    case TOKEN_XOR_ASSIGN:
    case TOKEN_OR_ASSIGN:
        return 0;
    default:
        return 1;
    }
}

static void obor_parserset_legacy_tables(void)
{
    size_t index, output = 0;
    for(index = 0; index < sizeof(first) / sizeof(*first); ++index)
        if(obor_parserset_keep_token(first[index]))
            obor_legacy_first[output++] = first[index];
    output = 0;
    for(index = 0; index < sizeof(follow) / sizeof(*follow); ++index)
        if(obor_parserset_keep_token(follow[index]))
            obor_legacy_follow[output++] = follow[index];
}

void ParserSet_Buildup(ParserSet *pset)
{
    MY_TOKEN_TYPE *ptr = NULL;
    int i = 0;

    int legacy = obor_profile_build >= 4283 && obor_profile_build < 4313;
    if(legacy) obor_parserset_legacy_tables();
    ptr = legacy ? obor_legacy_first : first;
    pset->FirstSet[i] = ptr;
    do
    {
        ptr++;
        if((*ptr) == END_OF_TOKENS)
        {
            i++;
            if(i < NUMPRODUCTIONS) pset->FirstSet[i] = ++ptr;
        }
    }
    while(i < NUMPRODUCTIONS);
    i = 0;
    ptr = legacy ? obor_legacy_follow : follow;
    pset->FollowSet[i] = ptr;
    do
    {
        ptr++;
        if((*ptr) == END_OF_TOKENS)
        {
            i++;
            if(i < NUMPRODUCTIONS) pset->FollowSet[i] = ++ptr;
        }
    }
    while(i < NUMPRODUCTIONS);
}



void ParserSet_Clear(ParserSet *pset)
{
    memset(pset, 0, sizeof(ParserSet));
}


BOOL ParserSet_First(ParserSet *pset, PRODUCTION theProduction, MY_TOKEN_TYPE theToken)
{
    MY_TOKEN_TYPE *ptr = NULL;
    ptr = pset->FirstSet[theProduction];
    while((*ptr) != END_OF_TOKENS)
    {
        if(*ptr == theToken)
        {
            return TRUE;
        }
        ptr++;
    }
    return FALSE;
}

BOOL ParserSet_Follow(ParserSet *pset, PRODUCTION theProduction, MY_TOKEN_TYPE theToken)
{
    MY_TOKEN_TYPE *ptr = NULL;
    ptr = pset->FollowSet[theProduction];
    while((*ptr) != END_OF_TOKENS)
    {
        if(*ptr == theToken)
        {
            return TRUE;
        }
        ptr++;
    }
    return FALSE;
}

