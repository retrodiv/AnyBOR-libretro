/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Retain imported entry points as direct instruction pointers.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * Licensed under the BSD license, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2013 OpenBOR Team
 */

#ifndef IMPORTCACHE_H
#define IMPORTCACHE_H

struct ImportNode;
typedef struct ImportNode ImportNode;

void ImportCache_Init();
ImportNode *ImportCache_ImportFile(const char *path);
void ImportCache_Clear();
Instruction *ImportList_GetFunctionPointer(List *list, const char *name);

#endif

