/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve profile-specific model ordering, lookup and detachment, with the
 * native sprite-map capacity policy.
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

#include <string.h>
#include <assert.h>
#include "models.h"
#include "List.h"
#include "utils.h"

#include <stdint.h>
extern uint32_t obor_profile_build;

static List* modellist;
static char convertbuf[1024];

#ifndef VERBOSE
extern s_sprite_map *sprite_map;
static size_t obor_profile_model_map_capacity;
#endif


void makelowercp(char* name) {
	assert(name);
	size_t len = strlen(name);
	assert(len < 1024);
	strncpy(convertbuf, name, 1024);
	lc(convertbuf, len);
}

void createModelList(void) {
	modellist = malloc(sizeof(List));
	List_Init(modellist);
}

void freeModelList(void) {
	List_Clear(modellist);
	free(modellist);
	modellist = NULL;
}

static Node* obor_model_node_at(int index) {
    Node* node = modellist->first;
    if(index < 0 || index >= modellist->size) return NULL;
    while(index--) node = node->next;
    return node;
}

s_model* getModelAt(int index) {
    Node* node = obor_model_node_at(index);
    return node ? (s_model*)node->value : NULL;
}

s_model* getLastModel(void) {
    List_GotoLast(modellist);
    return getCurrentModel();
}

void sortModels(void) {
    int changed;
    Node *node, *next;
#ifdef USE_INDEX
    List_FreeIndices(modellist);
#endif
    do {
        changed = 0;
        for(node = modellist->first; node && (next = node->next);) {
            if(stricmp(((s_model*)node->value)->name, ((s_model*)next->value)->name) > 0) {
                Node *previous = node->prev, *following = next->next;
                if(previous) previous->next = next;
                else modellist->first = next;
                next->prev = previous;
                next->next = node;
                node->prev = next;
                node->next = following;
                if(following) following->prev = node;
                else modellist->last = node;
                changed = 1;
            } else node = next;
        }
    } while(changed);
}

int detachModel(s_model* model) {
    Node *node, *previous, *following, *last;
    for(node = modellist->first; node && node->value != model; node = node->next) {}
    if(!node) return 0;
    previous = node->prev;
    following = node->next;
    last = modellist->last;
    List_SetCurrent(modellist, node);
    List_Remove(modellist);
    if(obor_profile_build < 3292 && following && following != last) {
        last->prev->next = NULL;
        modellist->last = last->prev;
        last->prev = previous;
        last->next = following;
        if(previous) previous->next = last;
        else modellist->first = last;
        following->prev = last;
        modellist->current = last;
    }
    return 1;
}

void addModel(s_model* model) {
	assert(model);
	assert(modellist);
#ifndef VERBOSE
    if(obor_profile_build >= 3039 && obor_profile_build < 3071 &&
       (!modellist->size || (size_t)modellist->size + 1 > obor_profile_model_map_capacity))
    {
        printf("%s %p\n", "add_model_map was", (void*)sprite_map);
        do {
            if(obor_profile_model_map_capacity > SIZE_MAX - 64)
            {
                obor_profile_model_map_capacity = SIZE_MAX;
                break;
            }
            obor_profile_model_map_capacity += 64;
        } while((size_t)modellist->size + 1 > obor_profile_model_map_capacity);
    }
#endif
	makelowercp(model->name);
	List_GotoLast(modellist);
	List_InsertAfter(modellist, (void*) model, convertbuf);
	if(obor_profile_build < 3122) sortModels();
}

void deleteModel(char* modelname) {
	s_model* temp;
	assert(modellist);
	assert(modelname);
	makelowercp(modelname);
	if(List_FindByName(modellist, convertbuf) && (temp=List_Retrieve(modellist))) {
		List_Remove(modellist);
		free(temp);
	}
}

s_model* findmodel(char* modelname) {
	s_model* temp = NULL;
	assert(modellist);
    if(obor_profile_build < 3292) {
        Node* node = NULL;
        if(obor_profile_build < 3122 && modellist->size) {
            int first = 0, last = modellist->size - 1;
            while(first < last) {
                int mid = (first + last) >> 1;
                int result;
                node = obor_model_node_at(mid);
                result = stricmp(((s_model*)node->value)->name, modelname);
                if(!result) break;
                if(result > 0) last = mid - 1;
                else first = mid + 1;
                node = NULL;
            }
            if(!node) node = obor_model_node_at(first);
            if(node && stricmp(((s_model*)node->value)->name, modelname)) node = NULL;
        } else {
            for(node = modellist->first; node; node = node->next)
                if(!stricmp(((s_model*)node->value)->name, modelname)) break;
        }
        if(node) List_SetCurrent(modellist, node);
        return node ? (s_model*)node->value : NULL;
    }
	makelowercp(modelname);
	if(List_FindByName(modellist, convertbuf))
		temp=List_Retrieve(modellist);
	return temp;
}

s_model* getFirstModel(void) {
	assert(modellist);
	List_GotoFirst(modellist);
	return getCurrentModel();

}

s_model* getCurrentModel(void) {
	assert(modellist);
	Node* n = List_GetCurrentNode(modellist);
	if(n)
		return (s_model*) n->value;
	else
		return NULL;
}

s_model* getNextModel(void) {
	assert(modellist);
	if (List_GotoNext(modellist))
		return getCurrentModel();
	else return NULL;
}

int isLastModel(void) {
	if (!modellist->current || modellist->current == modellist->last)
		return 1;
	return 0;
}
