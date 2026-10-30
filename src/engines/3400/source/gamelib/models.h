/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the profile-aware model registry traversal, sorting and detachment
 * helpers.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * Licensed under the BSD license, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#include "openbor.h"

void createModelList(void);
void freeModelList(void);
void addModel(s_model* model);
void deleteModel(char* modelname);
s_model* findmodel(char* modelname);
s_model* getFirstModel(void);
s_model* getCurrentModel(void);
s_model* getNextModel(void);
int isLastModel(void);

int detachModel(s_model* model);
void sortModels(void);
s_model* getModelAt(int index);
s_model* getLastModel(void);
