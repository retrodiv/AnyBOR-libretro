/* AnyBOR modification record: 2026-10-26.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the native production-number translation used by historical
 * diagnostics.
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

#ifndef PARSERSET_H
#define PARSERSET_H

#include "Lexer.h"
#include "Productions.h"

typedef struct ParserSet{
   MY_TOKEN_TYPE* FirstSet[NUMPRODUCTIONS] ;
   MY_TOKEN_TYPE* FollowSet[NUMPRODUCTIONS] ;
}ParserSet;


void ParserSet_Buildup(ParserSet* pset);
void ParserSet_Clear(ParserSet* pset);
int obor_parser_production_number(PRODUCTION production);
BOOL ParserSet_First(ParserSet* pset, PRODUCTION theProduction, MY_TOKEN_TYPE theToken);
BOOL ParserSet_Follow(ParserSet* pset, PRODUCTION theProduction, MY_TOKEN_TYPE theToken);
MY_TOKEN_TYPE LookupValue( CHAR* theToken);
#endif
