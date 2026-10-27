/* AnyBOR modification record: 2026-10-26.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Select native First/Follow sets by production name while keeping table
 * construction within its declared bounds.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3842.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#include "ParserSet.h"
#include "FirstFollow.h"
#include <string.h>
#include <stdint.h>
extern uint32_t obor_profile_build;
#include "ProfileGrammar.h"

void ParserSet_Buildup(ParserSet* pset)
{
	MY_TOKEN_TYPE* ptr = NULL;
	int i = 0;

	ptr = first;
	pset->FirstSet[i] = ptr;
	do{
		ptr++;
		if((*ptr)==END_OF_TOKENS) {
			i++;
			if(i < NUMPRODUCTIONS) pset->FirstSet[i] = ++ptr;
		}
	}while(i < NUMPRODUCTIONS);
	i = 0;
	ptr = follow;
	pset->FollowSet[i] = ptr;
	do{
		ptr++;
		if((*ptr)==END_OF_TOKENS) {
			i++;
			if(i < NUMPRODUCTIONS) pset->FollowSet[i] = ++ptr;
		}
	}while(i < NUMPRODUCTIONS);
    obor_profile_parser_sets(pset);
}



void ParserSet_Clear(ParserSet* pset)
{
	memset(pset, 0, sizeof(ParserSet));
}


BOOL ParserSet_First(ParserSet* pset, PRODUCTION theProduction, MY_TOKEN_TYPE theToken)
{
	MY_TOKEN_TYPE* ptr = NULL;
	ptr = pset->FirstSet[theProduction];
	while((*ptr)!=END_OF_TOKENS)
	{
		if(*ptr == theToken) return TRUE;
		ptr++;
	}
	return FALSE;
}

BOOL ParserSet_Follow(ParserSet* pset, PRODUCTION theProduction, MY_TOKEN_TYPE theToken)
{
	MY_TOKEN_TYPE* ptr = NULL;
	ptr = pset->FollowSet[theProduction];
	while((*ptr)!=END_OF_TOKENS)
	{
		if(*ptr == theToken) return TRUE;
		ptr++;
	}
	return FALSE;
}

