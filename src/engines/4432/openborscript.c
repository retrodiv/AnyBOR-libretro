/* AnyBOR modification record: 2026-10-22.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Keep the dormant constant-lowering diagnostic compatible with the single-
 * value instruction layout. Derive output names from the content basename
 * with explicit destination capacities, and reject overflowing output path
 * joins. Compact compiler-only instruction records after resolving value
 * ownership, preserving branch and export anchors, all mutable values and
 * exactly-once pool cleanup. Retain shared interpreters through the last
 * script reference while preserving independent variables, replacement and
 * native callbacks. Track diagnostic comments independently so interpreter
 * replacement can retain them. Resolve text-property names within the actual
 * table bounds while preserving native numeric selectors. Reuse each text
 * object's owned buffer when replacing its contents. Reject missing
 * colourtable indices and keep selector arithmetic and table reads defined.
 * Transfer loaded stream buffers through aligned local outputs while
 * preserving native record layout and results. Close owned input files after
 * stream loading and on buffer allocation failure. Bound string suffix
 * selection to the live source text. Enable the native empty-value result
 * and computed damage query from 4682. Expose the native game-over entry
 * point and preserve numeric level-property ordinals from 4642. Select the
 * mapped legacy terrain getter and setter behavior from 4682 and bound
 * basemap cell reads. Register the native typed drawing getter from 4455 and
 * preserve older system-variable ordinals when admitting the game timer from
 * 4456. Admit setopenborvariant from 4467 with the existing setter and
 * canonical reverse name, and preserve older ordinals when exposing
 * sets_count from 4477. Expose the native set handle lookup from 4478 with
 * its original empty result for an index outside the loaded sets. Preserve
 * native set property names, ordinals, result types, fallthrough results and
 * writable collection aliases by profile. Expose native layer handles and
 * the profile's scroll, boss slowdown and damage control constants. Expose
 * native typed level property names, numeric selectors, handle rules and
 * result values by profile. Register the native typed level setter and
 * preserve its scalar assignments and result handling by profile. Preserve
 * level collection and spawn view assignment by profile, including the early
 * background selector. Preserve typed level script assignment and shared
 * local variables while keeping executing interpreters live. Preserve the
 * platform aliases and animation and array script names by profile. Reject a
 * missing fourth platform coordinate and handle an empty cursor as no
 * movement. Preserve named action admission and numeric action slots around
 * the simple animation insertion. Retain the original entity property names,
 * ordinal values and lookup order across historical script profiles. Resolve
 * those ordinals before native property dispatch. Preserve the native entity
 * property reads, writes and argument handling around the historical weapon,
 * remap, block and boomerang changes. Preserve historical script wall-height
 * argument selection before querying the terrain. Preserve script reads and
 * writes of attack and body collision coordinates by profile while retaining
 * native conversions. Retain the profile's frame record or collection
 * reference and the identity behavior of native instance queries. Preserve
 * each profile's complete system-variable names and cached numeric
 * identifiers. Retain native basemap script-name availability, the
 * registered height alias and private helper result epochs. Preserve native
 * cell selection and initial map size by profile, checking owned map storage
 * before writes. Route the optional basemap generation argument by profile.
 * Register 4905 scalar binding properties and preserve the preceding entity-
 * property order. Preserve versioned attack property numbers, named
 * constants and the combined fall velocity view. Preserve recognized body
 * collision frame and instance pointer routes by profile. Expose source-
 * defined body collision property order, coordinate aliases and defense
 * references in 4905.
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

/* This file include all script methods used by openbor engine

 Notice: Make sure to null *pretvar when you about to return E_FAIL,
		 Or the engine might crash.

 Notice: Every new ScriptVariant must be initialized when you first alloc it by
		 ScriptVariant_Init immediately, memset it all to zero should also work by now,
		 unless VT_EMPTY is changed.

		 If you want to reset a ScriptVariant to empty, you must use ScriptVariant_Clear instead.
		 ScriptVariant_Init or memset must be called only ONCE, later you should use ScriptVariant_Clear.

		 Besure to call ScriptVariant_Clear if you want to use free to delete those variants.

		 If you want to copy a ScriptVariant from another, use ScriptVariant_Copy instead of assignment,
		 not because it is faster, but this method is neccessary for string types.

		 If you want to change types of an ScriptVariant, use ScriptVariant_ChangeType, don't change vt directly.

*/

#include <limits.h>
#include "openborscript.h"
#include "libretroport.h"
#include <stdint.h>
#include "openbor.h"
#include "soundmix.h"
#include "globals.h"
#include "ImportCache.h"
#include "models.h"
#include "anybor_resources.h"

#define _is_not_a_known_subproperty_of_  "'%s' is not a known subproperty of '%s'.\n"
#define _is_not_supported_by_ "'%s' is not supported by '%s'.\n"

// Define macro for string mapping
#define MAPSTRINGS(VAR, LIST, MAXINDEX, FAILMSG, args...) \
if(VAR->vt == VT_STR) { \
	propname = (char*)StrCache_Get(VAR->strVal); \
	prop = searchList(LIST, propname, MAXINDEX); \
	if(prop >= 0) { \
		ScriptVariant_ChangeType(VAR, VT_INTEGER); \
		VAR->lVal = prop; \
	} else { printf(FAILMSG, propname, ##args); return 0;} \
}

static int mapstrings_binding(ScriptVariant **varlist, int paramCount);
static HRESULT openbor_get_binding_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);
static HRESULT openbor_set_binding_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);

extern int			  PLAYER_MIN_Z;
extern int			  PLAYER_MAX_Z;
extern int			  BGHEIGHT;
extern int            MAX_WALL_HEIGHT;
extern int            max_attack_types;
extern int			  SAMPLE_GO;
extern int			  SAMPLE_BEAT;
extern int			  SAMPLE_BLOCK;
extern int			  SAMPLE_INDIRECT;
extern int			  SAMPLE_GET;
extern int			  SAMPLE_GET2;
extern int			  SAMPLE_FALL;
extern int			  SAMPLE_JUMP;
extern int			  SAMPLE_PUNCH;
extern int			  SAMPLE_1UP;
extern int			  SAMPLE_TIMEOVER;
extern int			  SAMPLE_BEEP;
extern int			  SAMPLE_BEEP2;
extern int			  SAMPLE_BIKE;
extern int            current_palette;
extern s_player       player[4];
extern s_level        *level;
extern s_filestream  *filestreams;
extern int			  numfilestreams;
extern entity         *self;
extern int            *animspecials;
extern int            *animattacks;
extern int            *animfollows;
extern int            *animpains;
extern int            *animfalls;
extern int            *animrises;
extern int            *animriseattacks;
extern int            *animdies;
extern int            *animidles;
extern int            *animwalks;
extern int            *animbackwalks;
extern int            *animups;
extern int            *animdowns;
extern int            *animbackpains;
extern int            *animbackfalls;
extern int            *animbackdies;

extern int            noshare;
extern int            credits;
extern char           musicname[128];
extern float          musicfade[2];
extern int            musicloop;
extern u32            musicoffset;
extern int            models_cached;
extern int endgame;
extern int useSave;
extern int useSet;


extern s_sprite_list *sprite_list;
extern s_sprite_map *sprite_map;

extern unsigned char *blendings[MAX_BLENDINGS];
extern int            current_palette;
extern s_collision_attack emptyattack;
Varlist global_var_list;
Script *pcurrentscript = NULL;//used by local script functions
List theFunctionList;
static List   scriptheap;
static s_spawn_entry spawnentry;
static s_drawmethod drawmethod;
static s_collision_attack attack ;

int            max_indexed_vars = 0;
int            max_entity_vars = 0;
int            max_script_vars = 0;
int			   no_nested_script = 0;

static void clear_named_var_list(List *list, int level)
{
    ScriptVariant *var;
    int i, size;
    size = List_GetSize(list);
    for(i = 0, List_Reset(list); i < size; i++)
    {
        var = (ScriptVariant *)List_Retrieve(list);
        ScriptVariant_Clear(var);
        free(var);
        List_Remove(list);
    }
    if(level)
    {
        List_Clear(list);
    }
}

void Varlist_Init(Varlist *varlist, int size)
{
    int i;
    if(!varlist || size < 0 || size == INT_MAX ||
       (size_t)size > (size_t)-1 / sizeof(*varlist->vars) - 1)
    {
        fprintf(stderr, "Invalid script variable capacity\n");
        borExit(1);
        return;
    }
    varlist->magic = varlist_magic;
    varlist->list = calloc(1, sizeof(*varlist->list));
    if(!varlist->list)
    {
        fprintf(stderr, "Unable to allocate script variable list\n");
        borExit(1);
        return;
    }
    List_Init(varlist->list);
    varlist->vars = calloc((size_t)size + 1, sizeof(*varlist->vars));
    if(!varlist->vars)
    {
        free(varlist->list);
        varlist->list = NULL;
        fprintf(stderr, "Unable to allocate script variable storage\n");
        borExit(1);
        return;
    }
    for(i = 0; i <= size; i++)
    {
        ScriptVariant_Init(varlist->vars + i);
        ScriptVariant_ChangeType(varlist->vars, VT_INTEGER);
        varlist->vars->lVal = (LONG)size;
    }
}

void Varlist_Clear(Varlist *varlist)
{
    int i;
    clear_named_var_list(varlist->list, 1);
    free(varlist->list);
    varlist->list = NULL;
    // the first one must be an integer variable, so it's safe to leave it alone
    for(i = 1; i <= varlist->vars->lVal; i++)
    {
        ScriptVariant_Clear(varlist->vars + i);
    }
    free(varlist->vars);
    varlist->vars = NULL;
    varlist->magic = 0;
}

void Varlist_Cleanup(Varlist *varlist)
{
    int i;
    clear_named_var_list(varlist->list, 0);
    for(i = 1; i <= varlist->vars->lVal; i++)
    {
        ScriptVariant_Clear(varlist->vars + i);
    }
}

ScriptVariant *Varlist_GetByName(Varlist *varlist, char *theName)
{
    if(!theName || !theName[0])
    {
        return NULL;
    }

    if(List_FindByName(varlist->list, theName))
    {
        return (ScriptVariant *)List_Retrieve(varlist->list);
    }

    return NULL;
}

int Varlist_SetByName(Varlist *varlist, char *theName, ScriptVariant *var)
{
    ScriptVariant *v;
    if(!varlist || !varlist->list || !var || !theName || !theName[0])
    {
        return 0;
    }
    if(List_FindByName(varlist->list, theName))
    {
        ScriptVariant_Copy((ScriptVariant *)List_Retrieve(varlist->list), var);
    }
    else
    {
        v = calloc(1, sizeof(*v));
        if(!v) return 0;
        ScriptVariant_Copy(v, var);
        List_InsertAfter(varlist->list, v, theName);
    }
    return 1;
}

ScriptVariant *Varlist_GetByIndex(Varlist *varlist, int index)
{
    if(index < 0 || index >= varlist->vars->lVal)
    {
        return NULL;
    }
    return varlist->vars + index + 1;
}

int Varlist_SetByIndex(Varlist *varlist, int index, ScriptVariant *var)
{
    if(!varlist || !varlist->vars || !var || index < 0 ||
       index > INT_MAX - 2 || varlist->vars->lVal < 0)
        return 0;
    if(index >= varlist->vars->lVal)
    {
        size_t old_slots = (size_t)varlist->vars->lVal + 1;
        size_t new_slots = (size_t)index + 2;
        size_t source_offset = SIZE_MAX;
        uintptr_t begin = (uintptr_t)varlist->vars;
        uintptr_t source = (uintptr_t)var;
        ScriptVariant *grown;
        if(new_slots > SIZE_MAX / sizeof(*grown)) return 0;
        /* A value can refer to an existing slot. Keep that slot identity
         * if realloc moves the table; read it after the native header update. */
        if(source >= begin && source - begin < old_slots * sizeof(*grown) &&
           (source - begin) % sizeof(*grown) == 0)
            source_offset = (size_t)(source - begin);
        grown = realloc(varlist->vars, new_slots * sizeof(*grown));
        if(!grown) return 0;
        memset(grown + old_slots, 0, (new_slots - old_slots) * sizeof(*grown));
        varlist->vars = grown;
        varlist->vars->lVal = index + 1;
        if(source_offset != SIZE_MAX)
            var = (ScriptVariant *)((char *)grown + source_offset);
    }
    ScriptVariant_Copy(varlist->vars + index + 1, var);
    return 1;
}

// By White Dragon
int Varlist_AddByIndex(Varlist *array, int index, ScriptVariant *var)
{
    if(index < 0 || index >= array->vars->lVal+1)
    {
        return 0;
    }
    else
    {
        int i = 0;
        int size = array->vars->lVal;

        __reallocto(array->vars, size+1, size+2);
        size = ++array->vars->lVal;

        for ( i = size-1; i > index; i-- )
        {
            ScriptVariant_Copy(array->vars+1+i, array->vars+1+i-1); // first value of array is his size!
        }
        ScriptVariant_Copy(array->vars+1+index, var);

        //printf("aaa: %s\n", (char*)StrCache_Get(elem->strVal) );
    }

    return 1;
}

// By White Dragon
int Varlist_DeleteByIndex(Varlist *array, int index)
{
    if(!array || !array->vars || index < 0 || index >= array->vars->lVal)
    {
        return 0;
    }
    else
    {
        int i = 0;
        int size = array->vars->lVal;
        ScriptVariant *elem;

        for ( i = index; i < size-1; i++ )
        {
            ScriptVariant_Copy(array->vars+1+i, array->vars+1+i+1); // first value of array is his size!
        }
        --array->vars->lVal;

        // set last element to NULL
        elem = array->vars+1+size-1;
        ScriptVariant_ChangeType(elem, VT_EMPTY);
        elem->ptrVal = NULL;

        //realloc mem
        ScriptVariant *resized_vars = realloc(array->vars,
            sizeof(*array->vars) * ((size_t)array->vars->lVal + 1));
        if(resized_vars) array->vars = resized_vars;

        //printf("aaa: %s\n", (char*)StrCache_Get(elem->strVal) );
    }

    return 1;
}

// By White Dragon
int Varlist_DeleteByName(Varlist *array, char *theName)
{
    if(!theName || !theName[0])
    {
        return 0;
    }
    if(List_FindByName(array->list, theName))
    {
        Node* node;
        Node* prev_node;
        Node* next_node;

        node = array->list->current;
        prev_node = node->prev;
        next_node = node->next;

        if ( prev_node ) prev_node->next = next_node;
        if ( next_node ) next_node->prev = prev_node;

        if ( array->list->last == node ) array->list->last = prev_node;
        if ( array->list->first == node ) array->list->first = next_node;
        if ( array->list->first == array->list->last && array->list->first == node ) {
            array->list->last = NULL;
            array->list->first = NULL;
        }

        --array->list->size;

        free(node);
    } else return 0;

    return 1;
}

//this function should be called before all script methods, for once
void Script_Global_Init()
{
    memset(&spawnentry, 0, sizeof(spawnentry));//clear up the spawn entry
    drawmethod = plainmethod;

    Varlist_Init(&global_var_list, max_indexed_vars);

    List_Init(&theFunctionList);
    Script_LoadSystemFunctions();
    *obor_script_cleanup_chain() = NULL;
    List_Init(&scriptheap);
    ImportCache_Init(&theFunctionList);
}

void _freeheapnode(void *ptr)
{
    Node *entry = List_GetCurrentNode(&scriptheap);
    const char *owner;
    if(!ptr || !entry || entry->value != ptr || obor_script_cleanup_active(ptr))
    {
        return;
    }
    owner = List_GetName(&scriptheap);
    if(owner && strcmp(owner, "openbor_allocscript") == 0 &&
       ((Script *)ptr)->magic == script_magic)
    {
        Script_Clear((Script *)ptr, 2);
    }
    else if(owner && strcmp(owner, "openbor_openanigif") == 0 &&
            ((anigif_info *)ptr)->magic == anigif_magic)
    {
        anigif_close((anigif_info *)ptr);
    }
    else if(owner && strcmp(owner, "openbor_array") == 0 &&
            ((Varlist *)ptr)->magic == varlist_magic)
    {
        Varlist_Clear((Varlist *)ptr);
    }
    else if(owner && strcmp(owner, "openbor_loadsprite") == 0 &&
            ((s_sprite *)ptr)->magic == sprite_magic)
    {
        if(((s_sprite *)ptr)->mask)
        {
            free(((s_sprite *)ptr)->mask);
        }
    }
    /* Shutdown can revisit this node after the callback moves the cursor. */
    entry->value = NULL;
    free(ptr);
}

//this function should only be called when the engine is shutting down
void Script_Global_Clear()
{
    int i, size;
    List_Clear(&theFunctionList);
    // dump all un-freed variants
    size = List_GetSize(&scriptheap);
    if(size > 0)
    {
        printf("\nWarning: %d script variants are not freed, dumping...\n", size);
    }
    for(i = 0, List_Reset(&scriptheap); i < size; List_GotoNext(&scriptheap), i++)
    {
        printf("%s\n", List_GetName(&scriptheap));
        _freeheapnode(List_Retrieve(&scriptheap));
    }
    List_Clear(&scriptheap);
    // clear the global list
    Varlist_Clear(&global_var_list);

    memset(&spawnentry, 0, sizeof(spawnentry));//clear up the spawn entry
    for(i = 0; i < numfilestreams; i++)
    {
        if(filestreams[i].buf)
        {
            free(filestreams[i].buf);
            filestreams[i].buf = NULL;
        }
    }
    if(filestreams)
    {
        free(filestreams);
    }
    filestreams = NULL;
    numfilestreams = 0;
    ImportCache_Clear();
    StrCache_Clear();
}

int Script_Save_Local_Variant(Script *cs, char *namelist[])
{
    return 0;
}

void Script_Load_Local_Variant(Script *cs, int handle)
{

}

Script *alloc_script()
{
    Script *pscript = calloc(1, sizeof(*pscript));
    if(!pscript)
    {
        fprintf(stderr, "Unable to allocate script storage\n");
        borExit(1);
        return NULL;
    }
    pscript->magic = script_magic;
    pscript->varlist = calloc(1, sizeof(*pscript->varlist));
    Varlist_Init(pscript->varlist, max_script_vars);
    return pscript;
}


static void obor_script_destroy_interpreter(void *value)
{
    Interpreter_Clear((Interpreter *)value);
    free(value);
}

static int obor_script_replace_interpreter(Script *script, char *name)
{
    Interpreter *replacement = malloc(sizeof(*replacement));
    obor_script_reference *reference;
    if(!replacement) return 0;
    Interpreter_Init(replacement, name, &theFunctionList);
    reference = obor_script_reference_new(replacement, obor_script_destroy_interpreter);
    if(!reference)
    {
        obor_script_destroy_interpreter(replacement);
        return 0;
    }
    if(!obor_script_reference_release(&script->obor_interpreter))
    {
        obor_script_reference_release(&reference);
        return 0;
    }
    script->obor_interpreter = reference;
    script->pinterpreter = replacement;
    return 1;
}

static void obor_script_destroy_comment(void *value)
{
    free(value);
}

static int obor_script_replace_comment(Script *script, const char *comment)
{
    char *replacement;
    obor_script_reference *reference;
    size_t length = strlen(comment);
    if(length == SIZE_MAX) return 0;
    replacement = malloc(length + 1);
    if(!replacement) return 0;
    memcpy(replacement, comment, length + 1);
    reference = obor_script_reference_new(replacement, obor_script_destroy_comment);
    if(!reference)
    {
        free(replacement);
        return 0;
    }
    if(!obor_script_reference_release(&script->obor_comment))
    {
        obor_script_reference_release(&reference);
        return 0;
    }
    script->obor_comment = reference;
    script->comment = replacement;
    return 1;
}

static int obor_script_share_references(Script *destination, Script *source)
{
    if(!source->obor_interpreter ||
       source->obor_interpreter->value != source->pinterpreter ||
       !obor_script_reference_retain(source->obor_interpreter)) return 0;
    if(source->obor_comment &&
       (source->obor_comment->value != source->comment ||
        !obor_script_reference_retain(source->obor_comment)))
    {
        obor_script_reference *rollback = source->obor_interpreter;
        obor_script_reference_release(&rollback);
        return 0;
    }

    destination->obor_interpreter = source->obor_interpreter;
    destination->obor_comment = source->obor_comment;
    return 1;
}

void Script_Init(Script *pscript, char *theName, char *comment, int first)
{
    if(!pscript)
    {
        fprintf(stderr, "Missing script storage\n");
        borExit(1);
        return;
    }
    if(first)
    {
        memset(pscript, 0, sizeof(*pscript));
        pscript->magic = script_magic;
        pscript->varlist = calloc(1, sizeof(*pscript->varlist));
        Varlist_Init(pscript->varlist, max_script_vars);
    }
    if(!theName || !theName[0])
    {
        return;    // if no name specified, only alloc the variants
    }

    if(!obor_script_replace_interpreter(pscript, theName))
    {
        shutdown(1, "Unable to allocate script interpreter.");
        return;
    }
    pscript->interpreterowner = 1; // this is the owner, important
    pscript->initialized = 1;
    if(comment && !obor_script_replace_comment(pscript, comment))
    {
        shutdown(1, "Unable to allocate script comment.");
        return;
    }
}

/* A running script can replace the record through which it was entered. */
typedef struct
{
    obor_script_reference *interpreter;
    Varlist *locals;
} obor_script_execution;

static obor_script_execution obor_script_pin_execution(const Script *script)
{
    obor_script_execution execution = {0};
    if(obor_profile_build < 4494) return execution;

    if(obor_script_reference_retain(script->obor_interpreter))
        execution.interpreter = script->obor_interpreter;
    if(script->varlist && script->varlist->obor_shared_owners < SIZE_MAX)
    {
        ++script->varlist->obor_shared_owners;
        execution.locals = script->varlist;
    }
    return execution;
}

static void obor_script_unpin_execution(obor_script_execution *execution)
{
    obor_script_reference_release(&execution->interpreter);
    if(execution->locals) obor_release_script_locals(execution->locals);
}

static void execute_init_method(Script *pdest, int iscopy, int localclear)
{
    Script *temp;
    ScriptVariant tempvar;
    //Execute init method
    if(pdest->initialized && pdest->pinterpreter->pInitEntry)
    {
        Interpreter *interpreter = pdest->pinterpreter;
        obor_script_execution executing = obor_script_pin_execution(pdest);
        temp = pcurrentscript;
        pcurrentscript = pdest;

        ScriptVariant_Init(&tempvar);
        ScriptVariant_ChangeType(&tempvar, VT_INTEGER);
        tempvar.lVal = (LONG)iscopy;
        Script_Set_Local_Variant(pdest, "iscopy", &tempvar);
        tempvar.lVal = (LONG)localclear;
        Script_Set_Local_Variant(pdest, "localclear", &tempvar);
        Interpreter_Reset(pdest->pinterpreter);
        pdest->pinterpreter->pCurrentInstruction = pdest->pinterpreter->pInitEntry;
        if(FAILED( Interpreter_EvaluateCall(pdest->pinterpreter)))
        {
            shutdown(1, "Fatal: failed to execute 'init' in script %s %s", interpreter->theSymbolTable.name, pdest->comment ? pdest->comment : "");
        }
        if(pdest->pinterpreter) pdest->pinterpreter->bReset = FALSE;
        ScriptVariant_Clear(&tempvar);
        Script_Set_Local_Variant(pdest, "iscopy", &tempvar);
        Script_Set_Local_Variant(pdest, "localclear", &tempvar);
        pcurrentscript = temp;
        obor_script_unpin_execution(&executing);
    }
}

//safe copy method
void Script_Copy(Script *pdest, Script *psrc, int localclear)
{
    if(!pdest || !psrc || pdest == psrc) return;
    if(!psrc->initialized)
    {
        return;
    }
    if(pdest->initialized)
    {
        Script_Clear(pdest, localclear);
    }
    if(!obor_script_share_references(pdest, psrc))
    {
        shutdown(1, "Unable to retain script interpreter.");
        return;
    }
    pdest->pinterpreter = psrc->pinterpreter;
    pdest->comment = psrc->comment;
    pdest->interpreterowner = 0; // dont own it
    pdest->initialized = psrc->initialized; //just copy, it should be 1
    execute_init_method(pdest, 1, localclear);
}

void Script_Clear(Script *pscript, int localclear)
{
    Script *temp;
    Varlist *pvars;

    ScriptVariant tempvar;
    if(!pscript || obor_script_cleanup_active(pscript)) return;
    //Execute clear method
    if(pscript->initialized && pscript->pinterpreter && pscript->pinterpreter->pClearEntry)
    {
        obor_script_cleanup **chain = obor_script_cleanup_chain();
        obor_script_cleanup scope = {pscript, *chain};
        *chain = &scope;
        temp = pcurrentscript;
        pcurrentscript = pscript;

        ScriptVariant_Init(&tempvar);
        ScriptVariant_ChangeType(&tempvar, VT_INTEGER);
        tempvar.lVal = (LONG)localclear;
        Script_Set_Local_Variant(pscript, "localclear", &tempvar);
        Interpreter_Reset(pscript->pinterpreter);
        pscript->pinterpreter->pCurrentInstruction = pscript->pinterpreter->pClearEntry;
        if(FAILED( Interpreter_EvaluateCall(pscript->pinterpreter)))
        {
            shutdown(1, "Fatal: failed to execute 'clear' in script %s %s", pscript->pinterpreter->theSymbolTable.name, pscript->comment ? pscript->comment : "");
        }
        pscript->pinterpreter->bReset = FALSE; // not needed, perhaps
        ScriptVariant_Clear(&tempvar);
        Script_Set_Local_Variant(pscript, "localclear", &tempvar);
        pcurrentscript = temp;
        *chain = scope.previous;
    }

    if(localclear && pscript->varlist)
    {
        if(localclear == 2)
        {
            obor_release_script_locals(pscript->varlist);
            pscript->varlist = NULL;
        }
        else
        {
            Varlist_Cleanup(pscript->varlist);
        }
    }
    if(!pscript->initialized)
    {
        return;
    }

    /* Shared values survive until their final script reference ends. */
    obor_script_reference_release(&pscript->obor_interpreter);
    pscript->pinterpreter = NULL;
    obor_script_reference_release(&pscript->obor_comment);
    pscript->comment = NULL;
    pvars = pscript->varlist; // in game clear(localclear!=2) just keep this value
    memset(pscript, 0, sizeof(*pscript));
    pscript->varlist = pvars; // copy it back
}

//append part of the script
//Because the script might not be initialized in 1 time.
int Script_AppendText(Script *pscript, char *text, char *path)
{
    int success;

    //printf(text);
    Interpreter_Reset(pscript->pinterpreter);

    success = SUCCEEDED(Interpreter_ParseText(pscript->pinterpreter, text, 1, path));

    return success;
}

//return name of function from pointer to function
static int obor_has_computed_damage(void)
{
    return obor_profile_build >= 4682 && obor_profile_build <= 4905;
}

const char *Script_GetFunctionName(void *functionRef)
{
    if (functionRef == ((void *)system_isempty))
    {
        return "isempty";
    }
    else if (functionRef == ((void *)system_exit))
    {
        return "exit";
    }
    else if (functionRef == ((void *)system_NULL))
    {
        return "NULL";
    }
    else if (functionRef == ((void *)system_rand))
    {
        return "rand";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4324) &&
             functionRef == ((void *)system_srand))
    {
        return "srand";
    }
    else if (functionRef == ((void *)system_getglobalvar))
    {
        return "getglobalvar";
    }
    else if (functionRef == ((void *)system_setglobalvar))
    {
        return "setglobalvar";
    }
    else if (functionRef == ((void *)system_getlocalvar))
    {
        return "getlocalvar";
    }
    else if (functionRef == ((void *)system_setlocalvar))
    {
        return "setlocalvar";
    }
    else if (functionRef == ((void *)system_clearglobalvar))
    {
        return "clearglobalvar";
    }
    else if (functionRef == ((void *)system_clearlocalvar))
    {
        return "clearlocalvar";
    }
    else if (functionRef == ((void *)system_free))
    {
        return "free";
    }
    else if (functionRef == ((void *)system_typeof))
    {
        return "typeof";
    }
    else if (functionRef == ((void *)math_sin))
    {
        return "sin";
    }
    else if (functionRef == ((void *)math_ssin))
    {
        return "ssin";
    }
    else if (functionRef == ((void *)math_cos))
    {
        return "cos";
    }
    else if (functionRef == ((void *)math_scos))
    {
        return "scos";
    }
    else if (functionRef == ((void *)math_sqrt))
    {
        return "sqrt";
    }
    else if (functionRef == ((void *)math_pow))
    {
        return "pow";
    }
    else if (functionRef == ((void *)math_asin))
    {
        return "asin";
    }
    else if (functionRef == ((void *)math_acos))
    {
        return "acos";
    }
    else if (functionRef == ((void *)math_atan))
    {
        return "atan";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4424) &&
             functionRef == ((void *)math_trunc))
    {
        return "trunc";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4424) &&
             functionRef == ((void *)math_round))
    {
        return "round";
    }
    else if (functionRef == ((void *)openbor_systemvariant))
    {
        return "openborvariant";
    }
    else if (functionRef == ((void *)openbor_changesystemvariant))
    {
        return "changeopenborvariant";
    }
    else if (functionRef == ((void *)openbor_drawstring))
    {
        return "drawstring";
    }
    else if (functionRef == ((void *)openbor_drawstringtoscreen))
    {
        return "drawstringtoscreen";
    }
    else if (functionRef == ((void *)openbor_log))
    {
        return "log";
    }
    else if (functionRef == ((void *)openbor_drawbox))
    {
        return "drawbox";
    }
    else if (functionRef == ((void *)openbor_drawboxtoscreen))
    {
        return "drawboxtoscreen";
    }
    else if (functionRef == ((void *)openbor_drawline))
    {
        return "drawline";
    }
    else if (functionRef == ((void *)openbor_drawlinetoscreen))
    {
        return "drawlinetoscreen";
    }
    else if (functionRef == ((void *)openbor_drawsprite))
    {
        return "drawsprite";
    }
    else if (functionRef == ((void *)openbor_drawspritetoscreen))
    {
        return "drawspritetoscreen";
    }
    else if (functionRef == ((void *)openbor_drawdot))
    {
        return "drawdot";
    }
    else if (functionRef == ((void *)openbor_drawdottoscreen))
    {
        return "drawdottoscreen";
    }
    else if (functionRef == ((void *)openbor_drawscreen))
    {
        return "drawscreen";
    }
    else if (functionRef == ((void *)openbor_changeplayerproperty))
    {
        return "changeplayerproperty";
    }
    else if (obor_profile_build >= 4905 && functionRef == ((void *)openbor_get_binding_property))
    {
        return "get_binding_property";
    }
    else if (obor_profile_build >= 4905 && functionRef == ((void *)openbor_set_binding_property))
    {
        return "set_binding_property";
    }
    else if (functionRef == ((void *)openbor_getplayerproperty))
    {
        return "getplayerproperty";
    }
    else if (functionRef == ((void *)openbor_changeentityproperty))
    {
        return "changeentityproperty";
    }
    else if (functionRef == ((void *)openbor_getentityproperty))
    {
        return "getentityproperty";
    }
    else if (functionRef == ((void *)openbor_get_animation_property))
    {
        return "get_animation_property";
    }
    else if (functionRef == ((void *)openbor_set_animation_property))
    {
        return "set_animation_property";
    }
    else if (functionRef == ((void *)openbor_get_attack_collection))
    {
        return "get_attack_collection";
    }
    else if (functionRef == ((void *)openbor_get_attack_instance))
    {
        return "get_attack_instance";
    }
    else if (functionRef == ((void *)openbor_get_attack_property))
    {
        return "get_attack_property";
    }
    else if (functionRef == ((void *)openbor_set_attack_property))
    {
        return "set_attack_property";
    }

    // Body collision (bbox)
    else if (functionRef == ((void *)openbor_get_body_collision_collection))
    {
        return "get_body_collision_collection";
    }
    else if (functionRef == ((void *)openbor_get_body_collision_instance))
    {
        return "get_body_collision_instance";
    }
    else if (functionRef == ((void *)openbor_get_body_collision_property))
    {
        return "get_body_collision_property";
    }
    else if (functionRef == ((void *)openbor_set_body_collision_property))
    {
        return "set_body_collision_property";
    }

    else if (functionRef == ((void *)openbor_tossentity))
    {
        return "tossentity";
    }
    else if (functionRef == ((void *)openbor_clearspawnentry))
    {
        return "clearspawnentry";
    }
    else if (functionRef == ((void *)openbor_setspawnentry))
    {
        return "setspawnentry";
    }
    else if (functionRef == ((void *)openbor_spawn))
    {
        return "spawn";
    }
    else if (functionRef == ((void *)openbor_projectile))
    {
        return "projectile";
    }
    else if (functionRef == ((void *)openbor_transconst))
    {
        return "openborconstant";
    }
    else if (functionRef == ((void *)openbor_playmusic))
    {
        return "playmusic";
    }
    else if (functionRef == ((void *)openbor_fademusic))
    {
        return "fademusic";
    }
    else if (functionRef == ((void *)openbor_setmusicvolume))
    {
        return "setmusicvolume";
    }
    else if (functionRef == ((void *)openbor_setmusictempo))
    {
        return "setmusictempo";
    }
    else if (functionRef == ((void *)openbor_pausemusic))
    {
        return "pausemusic";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4304) &&
             functionRef == ((void *)openbor_pausesamples))
    {
        return "pausesamples";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4423) &&
             functionRef == ((void *)openbor_pausesample))
    {
        return "pausesample";
    }
    else if (functionRef == ((void *)openbor_querychannel))
    {
        return "querychannel";
    }
    else if (functionRef == ((void *)openbor_stopchannel))
    {
        return "stopchannel";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4305) &&
             functionRef == ((void *)openbor_isactivesample))
    {
        return "isactivesample";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4308) &&
             functionRef == ((void *)openbor_sampleid))
    {
        return "sampleid";
    }
    else if (functionRef == ((void *)openbor_playsample))
    {
        return "playsample";
    }
    else if (functionRef == ((void *)openbor_loadsample))
    {
        return "loadsample";
    }
    else if (functionRef == ((void *)openbor_unloadsample))
    {
        return "unloadsample";
    }
    else if (functionRef == ((void *)openbor_fadeout))
    {
        return "fadeout";
    }
    else if (functionRef == ((void *)openbor_playerkeys))
    {
        return "playerkeys";
    }
    else if (functionRef == ((void *)openbor_changepalette))
    {
        return "changepalette";
    }
    else if (functionRef == ((void *)openbor_damageentity))
    {
        return "damageentity";
    }
    else if (obor_has_computed_damage() && functionRef == ((void *)openbor_getcomputeddamage))
    {
        return "getcomputeddamage";
    }
    else if (functionRef == ((void *)openbor_killentity))
    {
        return "killentity";
    }
    else if (functionRef == ((void *)openbor_dograb))
    {
        return "dograb";
    }
    else if (functionRef == ((void *)openbor_findtarget))
    {
        return "findtarget";
    }
    else if (functionRef == ((void *)openbor_checkrange))
    {
        return "checkrange";
    }
    else if (functionRef == ((void *)openbor_gettextobjproperty))
    {
        return "gettextobjproperty";
    }
    else if (functionRef == ((void *)openbor_changetextobjproperty))
    {
        return "changetextobjproperty";
    }
    else if (functionRef == ((void *)openbor_settextobj))
    {
        return "settextobj";
    }
    else if (functionRef == ((void *)openbor_cleartextobj))
    {
        return "cleartextobj";
    }
    else if (functionRef == ((void *)openbor_getlayerproperty))
    {
        return "getlayerproperty";
    }
    else if (functionRef == ((void *)openbor_changelayerproperty))
    {
        return "changelayerproperty";
    }
    else if (obor_profile_build >= 4476 && functionRef == ((void *)openbor_get_set_property))
    {
        return "get_set_property";
    }
    else if (obor_profile_build >= 4476 && functionRef == ((void *)openbor_set_set_property))
    {
        return "set_set_property";
    }
    else if (obor_profile_build >= 4478 && functionRef == ((void *)openbor_get_set_handle))
    {
        return "get_set_handle";
    }
    else if (obor_profile_build >= 4489 && functionRef == ((void *)openbor_get_layer_handle))
    {
        return "get_layer_handle";
    }
    else if (obor_profile_build >= 4475 && functionRef == ((void *)openbor_get_level_property))
    {
        return "get_level_property";
    }
    else if (obor_profile_build >= 4475 && functionRef == ((void *)openbor_set_level_property))
    {
        return "set_level_property";
    }
    else if (obor_profile_build < 4475 && functionRef == ((void *)openbor_getlevelproperty))
    {
        return "getlevelproperty";
    }
    else if (functionRef == ((void *)openbor_changelevelproperty))
    {
        return "changelevelproperty";
    }
    else if (functionRef == ((void *)openbor_checkhole))
    {
        return "checkhole";
    }
    else if (functionRef == ((void *)openbor_checkholeindex))
    {
        return "checkholeindex";
    }
    else if (functionRef == ((void *)openbor_checkwall))
    {
        return "checkwall";
    }
    else if (functionRef == ((void *)openbor_checkwallindex))
    {
        return "checkwallindex";
    }
    else if (functionRef == ((void *)openbor_checkplatformbelow))
    {
        return "checkplatformbelow";
    }
    else if (functionRef == ((void *)openbor_checkplatformabove))
    {
        return "checkplatformabove";
    }
    else if (functionRef == ((void *)openbor_checkplatformbetween))
    {
        return "checkplatformbetween";
    }
    else if (functionRef == ((void *)openbor_checkbasemap))
    {
        return "checkbasemap";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4290) &&
             functionRef == ((void *)openbor_checkbasemapindex))
    {
        return "checkbasemapindex";
    }
    else if (functionRef == ((void *)openbor_generatebasemap))
    {
        return "generatebasemap";
    }
    else if (functionRef == ((void *)openbor_openfilestream))
    {
        return "openfilestream";
    }
    else if (functionRef == ((void *)openbor_getfilestreamline))
    {
        return "getfilestreamline";
    }
    else if (functionRef == ((void *)openbor_getfilestreamargument))
    {
        return "getfilestreamargument";
    }
    else if (functionRef == ((void *)openbor_filestreamnextline))
    {
        return "filestreamnextline";
    }
    else if (functionRef == ((void *)openbor_getfilestreamposition))
    {
        return "getfilestreamposition";
    }
    else if (functionRef == ((void *)openbor_setfilestreamposition))
    {
        return "setfilestreamposition";
    }
    else if (functionRef == ((void *)openbor_filestreamappend))
    {
        return "filestreamappend";
    }
    else if (functionRef == ((void *)openbor_createfilestream))
    {
        return "createfilestream";
    }
    else if (functionRef == ((void *)openbor_closefilestream))
    {
        return "closefilestream";
    }
    else if (functionRef == ((void *)openbor_savefilestream))
    {
        return "savefilestream";
    }
    else if (functionRef == ((void *)openbor_getindexedvar))
    {
        return "getindexedvar";
    }
    else if (functionRef == ((void *)openbor_setindexedvar))
    {
        return "setindexedvar";
    }
    else if (functionRef == ((void *)openbor_getscriptvar))
    {
        return "getscriptvar";
    }
    else if (functionRef == ((void *)openbor_setscriptvar))
    {
        return "setscriptvar";
    }
    else if (functionRef == ((void *)openbor_getentityvar))
    {
        return "getentityvar";
    }
    else if (functionRef == ((void *)openbor_setentityvar))
    {
        return "setentityvar";
    }
    else if (functionRef == ((void *)openbor_shutdown))
    {
        return "shutdown";
    }
    else if (functionRef == ((void *)openbor_jumptobranch))
    {
        return "jumptobranch";
    }
    else if (functionRef == ((void *)openbor_changelight))
    {
        return "changelight";
    }
    else if (functionRef == ((void *)openbor_changeshadowcolor))
    {
        return "changeshadowcolor";
    }
    else if (functionRef == ((void *)openbor_bindentity))
    {
        return "bindentity";
    }
    else if (functionRef == ((void *)openbor_array))
    {
        return "array";
    }
    else if (functionRef == ((void *)openbor_size))
    {
        return "size";
    }
    else if (functionRef == ((void *)openbor_get))
    {
        return "get";
    }
    else if (functionRef == ((void *)openbor_set))
    {
        return "set";
    }
    else if (functionRef == ((void *)openbor_delete))
    {
        return "delete";
    }
    else if (functionRef == ((void *)openbor_add))
    {
        return "add";
    }
    else if (functionRef == ((void *)openbor_reset))
    {
        return "reset";
    }
    else if (functionRef == ((void *)openbor_next))
    {
        return "next";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4420) &&
             functionRef == ((void *)openbor_previous))
    {
        return "previous";
    }
    else if (functionRef == ((void *)openbor_key))
    {
        return "key";
    }
    else if (functionRef == ((void *)openbor_value))
    {
        return "value";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4420) &&
             functionRef == ((void *)openbor_islast))
    {
        return "islast";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4420) &&
             functionRef == ((void *)openbor_isfirst))
    {
        return "isfirst";
    }
    else if (functionRef == ((void *)openbor_allocscreen))
    {
        return "allocscreen";
    }
    else if (functionRef == ((void *)openbor_clearscreen))
    {
        return "clearscreen";
    }
    else if (functionRef == ((void *)openbor_setdrawmethod))
    {
        return "setdrawmethod";
    }
    else if (functionRef == ((void *)openbor_changedrawmethod))
    {
        return "changedrawmethod";
    }
    else if (obor_profile_build >= 4455 && functionRef == ((void *)openbor_getdrawmethod))
    {
        return "getdrawmethod";
    }
    else if (functionRef == ((void *)openbor_updateframe))
    {
        return "updateframe";
    }
    else if (functionRef == ((void *)openbor_performattack))
    {
        return "performattack";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4410) &&
             functionRef == ((void *)openbor_executeanimation))
    {
        return "executeanimation";
    }
    else if (functionRef == ((void *)openbor_setidle))
    {
        return "setidle";
    }
    else if (functionRef == ((void *)openbor_getentity))
    {
        return "getentity";
    }
    else if (functionRef == ((void *)openbor_hallfame))
    {
        return "hallfame";
    }
    else if (functionRef == ((void *)openbor_loadmodel))
    {
        return "loadmodel";
    }
    else if (functionRef == ((void *)openbor_loadsprite))
    {
        return "loadsprite";
    }
    else if (functionRef == ((void *)openbor_menu_options))
    {
        return "options";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4380) &&
             functionRef == ((void *)openbor_playwebm))
    {
        return "playwebm";
    }
    else if (functionRef == ((void *)openbor_playgif))
    {
        return "playgif";
    }
    else if (functionRef == ((void *)openbor_openanigif))
    {
        return "openanigif";
    }
    else if (functionRef == ((void *)openbor_decodeanigif))
    {
        return "decodeanigif";
    }
    else if (functionRef == ((void *)openbor_getanigifinfo))
    {
        return "getanigifinfo";
    }
    else if (functionRef == ((void *)openbor_strinfirst))
    {
        return "strinfirst";
    }
    else if (functionRef == ((void *)openbor_strinlast))
    {
        return "strinlast";
    }
    else if (functionRef == ((void *)openbor_strleft))
    {
        return "strleft";
    }
    else if (functionRef == ((void *)openbor_strlength))
    {
        return "strlength";
    }
    else if (functionRef == ((void *)openbor_strwidth))
    {
        return "strwidth";
    }
    else if (functionRef == ((void *)openbor_strright))
    {
        return "strright";
    }
    else if (functionRef == ((void *)openbor_getmodelproperty))
    {
        return "getmodelproperty";
    }
    else if (functionRef == ((void *)openbor_changemodelproperty))
    {
        return "changemodelproperty";
    }
    else if (functionRef == ((void *)openbor_rgbcolor))
    {
        return "rgbcolor";
    }
    else if (functionRef == ((void *)openbor_adjustwalkanimation))
    {
        return "adjustwalkanimation";
    }
    else if (functionRef == ((void *)openbor_finditem))
    {
        return "finditem";
    }
    else if (functionRef == ((void *)openbor_pickup))
    {
        return "pickup";
    }
    else if (functionRef == ((void *)openbor_waypoints))
    {
        return "waypoints";
    }
    else if (functionRef == ((void *)openbor_drawspriteq))
    {
        return "drawspriteq";
    }
    else if (functionRef == ((void *)openbor_clearspriteq))
    {
        return "clearspriteq";
    }
    else if (functionRef == ((void *)openbor_getgfxproperty))
    {
        return "getgfxproperty";
    }
    else if (functionRef == ((void *)openbor_allocscript))
    {
        return "allocscript";
    }
    else if (functionRef == ((void *)openbor_loadscript))
    {
        return "loadscript";
    }
    else if (functionRef == ((void *)openbor_compilescript))
    {
        return "compilescript";
    }
    else if (functionRef == ((void *)openbor_executescript))
    {
        return "executescript";
    }
    else if (functionRef == ((void *)openbor_loadgamefile))
    {
        return "loadgamefile";
    }
    else if (functionRef == ((void *)openbor_finishlevel))
    {
        return "finishlevel";
    }
    else if (obor_profile_build >= 4642 && obor_profile_build <= 4905 &&
             functionRef == ((void *)openbor_gameover))
    {
        return "gameover";
    }
    else if ((obor_profile_build < 4283 || obor_profile_build >= 4293) &&
             functionRef == ((void *)openbor_gotomainmenu))
    {
        return "gotomainmenu";
    }
    else if (functionRef == ((void *)openbor_playgame))
    {
        return "playgame";
    }
    else if (functionRef == ((void *)openbor_getrecordingstatus))
    {
        return "getrecordingstatus";
    }
    else if (functionRef == ((void *)openbor_recordinputs))
    {
        return "recordinputs";
    }
    else if (functionRef == ((void *)openbor_getsaveinfo))
    {
        return "getsaveinfo";
    }
    else
    {
        return "<unknown function>";
    }
}

//return string mapping function corresponding to a given function
void *Script_GetStringMapFunction(void *functionRef)
{
    if (functionRef == ((void *)openbor_systemvariant))
    {
        return (void *)mapstrings_systemvariant;
    }
    else if (functionRef == ((void *)openbor_changesystemvariant))
    {
        return (void *)mapstrings_systemvariant;
    }
    else if (functionRef == ((void *)openbor_getentityproperty))
    {
        return (void *)mapstrings_entityproperty;
    }
    else if (functionRef == ((void *)openbor_changeentityproperty))
    {
        return (void *)mapstrings_entityproperty;
    }
    else if (functionRef == ((void *)openbor_getplayerproperty))
    {
        return (void *)mapstrings_playerproperty;
    }
    else if (functionRef == ((void *)openbor_changeplayerproperty))
    {
        return (void *)mapstrings_playerproperty;
    }
    else if (obor_profile_build >= 4905 &&
             (functionRef == ((void *)openbor_get_binding_property) ||
              functionRef == ((void *)openbor_set_binding_property)))
    {
        return (void *)mapstrings_binding;
    }
    else if (functionRef == ((void *)openbor_setspawnentry))
    {
        return (void *)mapstrings_setspawnentry;
    }
    else if (functionRef == ((void *)openbor_transconst))
    {
        return (void *)mapstrings_transconst;
    }
    else if (functionRef == ((void *)openbor_playerkeys))
    {
        return (void *)mapstrings_playerkeys;
    }
    else if (functionRef == ((void *)openbor_gettextobjproperty))
    {
        return (void *)mapstrings_textobjproperty;
    }
    else if (functionRef == ((void *)openbor_changetextobjproperty))
    {
        return (void *)mapstrings_textobjproperty;
    }
    else if (functionRef == ((void *)openbor_getlayerproperty))
    {
        return (void *)mapstrings_layerproperty;
    }
    else if (functionRef == ((void *)openbor_changelayerproperty))
    {
        return (void *)mapstrings_layerproperty;
    }
    else if (functionRef == ((void *)openbor_changedrawmethod))
    {
        return (void *)mapstrings_drawmethodproperty;
    }
    else if (functionRef == ((void *)openbor_getgfxproperty))
    {
        return (void *)mapstrings_gfxproperty;
    }
    else if (functionRef == ((void *)openbor_getlevelproperty))
    {
        return (void *)mapstrings_levelproperty;
    }
    else if (functionRef == ((void *)openbor_changelevelproperty))
    {
        return (void *)mapstrings_levelproperty;
    }
    else
    {
        return NULL;
    }
}

/* Replace string constants with enum constants at compile time to speed up
   script execution. */
int Script_MapStringConstants(Instruction *pInstruction)
{
    ScriptVariant **params;
    int paramCount;
    int (*pMapstrings)(ScriptVariant **, int);

    if(pInstruction->jumpTargetType == INSTRUCTION_TARGET_FUNCTION &&
       pInstruction->functionRef)
    {
        params = Instruction_CallReferenceValues(pInstruction);
        paramCount = Instruction_CallReferenceCount(pInstruction);
        assert(paramCount <= 32);
        // Get the pointer to the correct mapstrings function, if one exists.
        pMapstrings = Script_GetStringMapFunction(pInstruction->functionRef);
        if(pMapstrings)
        {
            // Call the mapstrings function.
            if(!pMapstrings(params, paramCount))
            {
                return 0;
            }
        }
    }

    return 1;
}

//should be called only once after parsing text
int Script_Compile(Script *pscript)
{
    int result;
    if(!pscript || !pscript->pinterpreter)
    {
        return 1;
    }
    //Interpreter_OutputPCode(pscript->pinterpreter, "code");
    result = SUCCEEDED(Interpreter_CompileInstructions(pscript->pinterpreter, NULL));
    if(!result)
    {
        shutdown(1, "Can't compile script '%s' %s\n", pscript->pinterpreter->theSymbolTable.name, pscript->comment ? pscript->comment : "");
    }

    pscript->pinterpreter->bReset = FALSE;
    execute_init_method(pscript, 0, 1);
    return result;
}

int Script_IsInitialized(Script *pscript)
{
    if(!pscript) return 0;
    //if(pscript && pscript->initialized) pcurrentscript = pscript; //used by local script functions
    return pscript->initialized;
}

//execute the script
int Script_Execute(Script *pscript)
{
    int result, nested;
    extern int no_cmd_compatible;
    Script *temp = pcurrentscript;
    Interpreter tinter, *pinter = pscript->pinterpreter;
    obor_script_execution executing = obor_script_pin_execution(pscript);
    pcurrentscript = pscript; //used by local script functions
    nested = pscript->pinterpreter->bReset;
    if(no_nested_script && nested)
    {
        result = 1;
    }
    else
    {
        if(nested && no_cmd_compatible)
        {
            tinter = *pinter;
        }
        Interpreter_Reset(pinter);
        result = (int)SUCCEEDED(Interpreter_EvaluateImmediate(pinter));
        if(nested && no_cmd_compatible)
        {
            *pinter = tinter;
        }
        else if(nested)
        {
            pinter->bReset = FALSE;
        }
    }
    pcurrentscript = temp;
    if(!result)
    {
        shutdown(1, "There's an exception while executing script '%s' %s", pinter->theSymbolTable.name, pscript->comment ? pscript->comment : "");
    }
    obor_script_unpin_execution(&executing);
    return result;
}

#ifndef COMPILED_SCRIPT
//this method is for debug purpose
int Script_Call(Script *pscript, char *method, ScriptVariant *pretvar)
{
    int result;
    Script *temp = pcurrentscript;
    obor_script_execution executing = obor_script_pin_execution(pscript);
    pcurrentscript = pscript; //used by local script functions
    Interpreter_Reset(pscript->pinterpreter);
    result = (int)SUCCEEDED(Interpreter_Call(pscript->pinterpreter, method, pretvar));
    pcurrentscript = temp;
    obor_script_unpin_execution(&executing);
    return result;
}
#endif

//used by Script_Global_Init
void Script_LoadSystemFunctions()
{
    //printf("Loading system script functions....");
    //load system functions if we need
    List_Reset(&theFunctionList);

    List_InsertAfter(&theFunctionList,
                     (void *)system_isempty, "isempty");
    List_InsertAfter(&theFunctionList,
                     (void *)system_exit, "exit");
    List_InsertAfter(&theFunctionList,
                     (void *)system_NULL, "NULL");
    List_InsertAfter(&theFunctionList,
                     (void *)system_rand, "rand");
    if(obor_profile_build < 4283 || obor_profile_build >= 4324)
    {
        List_InsertAfter(&theFunctionList, (void *)system_srand, "srand");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)system_getglobalvar, "getglobalvar");
    List_InsertAfter(&theFunctionList,
                     (void *)system_setglobalvar, "setglobalvar");
    List_InsertAfter(&theFunctionList,
                     (void *)system_getlocalvar, "getlocalvar");
    List_InsertAfter(&theFunctionList,
                     (void *)system_setlocalvar, "setlocalvar");
    List_InsertAfter(&theFunctionList,
                     (void *)system_clearglobalvar, "clearglobalvar");
    List_InsertAfter(&theFunctionList,
                     (void *)system_clearlocalvar, "clearlocalvar");
    List_InsertAfter(&theFunctionList,
                     (void *)system_free, "free");
    List_InsertAfter(&theFunctionList,
                     (void *)system_typeof, "typeof");
    List_InsertAfter(&theFunctionList,
                     (void *)math_sin, "sin");
    List_InsertAfter(&theFunctionList,
                     (void *)math_ssin, "ssin");
    List_InsertAfter(&theFunctionList,
                     (void *)math_cos, "cos");
    List_InsertAfter(&theFunctionList,
                     (void *)math_scos, "scos");
    List_InsertAfter(&theFunctionList,
                     (void *)math_sqrt, "sqrt");
    List_InsertAfter(&theFunctionList,
                     (void *)math_pow, "pow");
    List_InsertAfter(&theFunctionList,
                     (void *)math_asin, "asin");
    List_InsertAfter(&theFunctionList,
                     (void *)math_acos, "acos");
    List_InsertAfter(&theFunctionList,
                     (void *)math_atan, "atan");
    if(obor_profile_build < 4283 || obor_profile_build >= 4424)
    {
        List_InsertAfter(&theFunctionList, (void *)math_trunc, "trunc");
    }
    if(obor_profile_build < 4283 || obor_profile_build >= 4424)
    {
        List_InsertAfter(&theFunctionList, (void *)math_round, "round");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_systemvariant, "openborvariant");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changesystemvariant, "changeopenborvariant");
    if(obor_profile_build >= 4467)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_changesystemvariant, "setopenborvariant");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawstring, "drawstring");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawstringtoscreen, "drawstringtoscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_log, "log");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawbox, "drawbox");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawboxtoscreen, "drawboxtoscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawline, "drawline");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawlinetoscreen, "drawlinetoscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawsprite, "drawsprite");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawspritetoscreen, "drawspritetoscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawdot, "drawdot");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawdottoscreen, "drawdottoscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawscreen, "drawscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changeplayerproperty, "changeplayerproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changeentityproperty, "changeentityproperty");
    if(obor_profile_build >= 4905)
    {
        List_InsertAfter(&theFunctionList,
                         (void *)openbor_get_binding_property, "get_binding_property");
        List_InsertAfter(&theFunctionList,
                         (void *)openbor_set_binding_property, "set_binding_property");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getplayerproperty, "getplayerproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get_animation_property, "get_animation_property");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_set_animation_property, "set_animation_property");

    // Attack properties
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get_attack_collection, "get_attack_collection");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get_attack_instance, "get_attack_instance");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get_attack_property, "get_attack_property");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_set_attack_property, "set_attack_property");

    // Body collision (bbox) properties.
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get_body_collision_collection, "get_body_collision_collection");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get_body_collision_instance, "get_body_collision_instance");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get_body_collision_property, "get_body_collision_property");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_set_body_collision_property, "set_body_collision_property");

    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getentityproperty, "getentityproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_tossentity, "tossentity");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_clearspawnentry, "clearspawnentry");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setspawnentry, "setspawnentry");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_spawn, "spawn");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_projectile, "projectile");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_transconst, "openborconstant");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_playmusic, "playmusic");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_fademusic, "fademusic");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setmusicvolume, "setmusicvolume");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setmusictempo, "setmusictempo");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_pausemusic, "pausemusic");
    if(obor_profile_build < 4283 || obor_profile_build >= 4304)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_pausesamples, "pausesamples");
    }
    if(obor_profile_build < 4283 || obor_profile_build >= 4423)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_pausesample, "pausesample");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_querychannel, "querychannel");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_stopchannel, "stopchannel");
    if(obor_profile_build < 4283 || obor_profile_build >= 4305)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_isactivesample, "isactivesample");
    }
    if(obor_profile_build < 4283 || obor_profile_build >= 4308)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_sampleid, "sampleid");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_playsample, "playsample");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_loadsample, "loadsample");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_unloadsample, "unloadsample");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_fadeout, "fadeout");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_playerkeys, "playerkeys");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changepalette, "changepalette");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_damageentity, "damageentity");
    if(obor_has_computed_damage())
    {
        List_InsertAfter(&theFunctionList,
                         (void *)openbor_getcomputeddamage, "getcomputeddamage");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_killentity, "killentity");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_dograb, "dograb");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_findtarget, "findtarget");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_checkrange, "checkrange");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_gettextobjproperty, "gettextobjproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changetextobjproperty, "changetextobjproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_settextobj, "settextobj");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_cleartextobj, "cleartextobj");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getlayerproperty, "getlayerproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changelayerproperty, "changelayerproperty");
    if(obor_profile_build >= 4476)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_get_set_property, "get_set_property");
        List_InsertAfter(&theFunctionList, (void *)openbor_set_set_property, "set_set_property");
    }
    if(obor_profile_build >= 4478)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_get_set_handle, "get_set_handle");
    }
    if(obor_profile_build >= 4489)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_get_layer_handle, "get_layer_handle");
    }
    if(obor_profile_build >= 4475)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_get_level_property, "get_level_property");
        List_InsertAfter(&theFunctionList, (void *)openbor_set_level_property, "set_level_property");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getlevelproperty, "getlevelproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changelevelproperty, "changelevelproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_checkhole, "checkhole");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_checkholeindex, "checkholeindex");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_checkwall, "checkwall");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_checkholeindex, "checkwallindex");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_checkplatformbelow, "checkplatformbelow");
    List_InsertAfter(&theFunctionList,
                     (void *)((obor_profile_build >= 4283 && obor_profile_build < 4411)
                                  ? openbor_checkplatformbelow : openbor_checkplatformabove), "checkplatformabove");
    List_InsertAfter(&theFunctionList,
                     (void *)((obor_profile_build >= 4283 && obor_profile_build < 4411)
                                  ? openbor_checkplatformbelow : openbor_checkplatformbetween), "checkplatformbetween");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_checkbasemap, "checkbasemap");
    if(obor_profile_build < 4283 || obor_profile_build >= 4290)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_checkbasemap, "checkbasemapindex");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_generatebasemap, "generatebasemap");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_openfilestream, "openfilestream");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getfilestreamline, "getfilestreamline");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getfilestreamargument, "getfilestreamargument");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_filestreamnextline, "filestreamnextline");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getfilestreamposition, "getfilestreamposition");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setfilestreamposition, "setfilestreamposition");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_filestreamappend, "filestreamappend");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_createfilestream, "createfilestream");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_closefilestream, "closefilestream");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_savefilestream, "savefilestream");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getindexedvar, "getindexedvar");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setindexedvar, "setindexedvar");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getscriptvar, "getscriptvar");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setscriptvar, "setscriptvar");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getentityvar, "getentityvar");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setentityvar, "setentityvar");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_shutdown, "shutdown");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_jumptobranch, "jumptobranch");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changelight, "changelight");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changeshadowcolor, "changeshadowcolor");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_bindentity, "bindentity");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_array, "array");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_size, "size");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_get, "get");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_set, "set");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_delete, "delete");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_add, "add");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_reset, "reset");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_next, "next");
    if(obor_profile_build < 4283 || obor_profile_build >= 4420)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_previous, "previous");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_key, "key");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_value, "value");
    if(obor_profile_build < 4283 || obor_profile_build >= 4420)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_islast, "islast");
    }
    if(obor_profile_build < 4283 || obor_profile_build >= 4420)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_isfirst, "isfirst");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_allocscreen, "allocscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_clearscreen, "clearscreen");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setdrawmethod, "setdrawmethod");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changedrawmethod, "changedrawmethod");
    if(obor_profile_build >= 4455)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_getdrawmethod, "getdrawmethod");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_updateframe, "updateframe");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_performattack, "performattack");
    if(obor_profile_build < 4283 || obor_profile_build >= 4410)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_executeanimation, "executeanimation");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_setidle, "setidle");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getentity, "getentity");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_loadmodel, "loadmodel");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_loadsprite, "loadsprite");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_hallfame, "hallfame");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_menu_options, "options");
    if(obor_profile_build < 4283 || obor_profile_build >= 4380)
    {
        List_InsertAfter(&theFunctionList, (void *)openbor_playwebm, "playwebm");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_playgif, "playgif");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_openanigif, "openanigif");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_decodeanigif, "decodeanigif");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getanigifinfo, "getanigifinfo");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_strinfirst, "strinfirst");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_strinlast, "strinlast");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_strleft, "strleft");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_strlength, "strlength");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_strwidth, "strwidth");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_strright, "strright");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getmodelproperty, "getmodelproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_changemodelproperty, "changemodelproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_rgbcolor, "rgbcolor");

    List_InsertAfter(&theFunctionList,
                     (void *)openbor_adjustwalkanimation, "adjustwalkanimation");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_finditem, "finditem");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_pickup, "pickup");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_waypoints, "waypoints");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_drawspriteq, "drawspriteq");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_clearspriteq, "clearspriteq");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getgfxproperty, "getgfxproperty");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_allocscript, "allocscript");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_loadscript, "loadscript");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_compilescript, "compilescript");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_executescript, "executescript");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_loadgamefile, "loadgamefile");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_finishlevel, "finishlevel");
    if(obor_profile_build >= 4642 && obor_profile_build <= 4905)
    {
        List_InsertAfter(&theFunctionList,
                         (void *)openbor_gameover, "gameover");
    }
    if(obor_profile_build < 4283 || obor_profile_build >= 4293)
    {
        List_InsertAfter(&theFunctionList,
                         (void *)openbor_gotomainmenu, "gotomainmenu");
    }
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_playgame, "playgame");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getrecordingstatus, "getrecordingstatus");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_recordinputs, "recordinputs");
    List_InsertAfter(&theFunctionList,
                     (void *)openbor_getsaveinfo, "getsaveinfo");

    //printf("Done!\n");

}

//////////////////////////////////////////////////////////
////////////   system functions
//////////////////////////////////////////////////////////
//isempty(var);
HRESULT system_isempty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(obor_profile_build < 4682 || obor_profile_build > 4905 || paramCount != 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = varlist[0]->vt == VT_EMPTY;

    return S_OK;
}
//NULL();
HRESULT system_NULL(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant_Clear(*pretvar);

    return S_OK;
}
HRESULT system_exit(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    *pretvar = NULL;
    pcurrentscript->pinterpreter->bReset = FALSE;
    return S_OK;
}
HRESULT system_rand(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)rand32();
    return S_OK;
}
HRESULT system_srand(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;

    *pretvar = NULL;
    if(paramCount != 1 || !varlist || !varlist[0])
    {
        return E_FAIL;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        return E_FAIL;
    }

    srand32(ltemp);
    return S_OK;
}
//getglobalvar(varname);
HRESULT system_getglobalvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    ScriptVariant *ptmpvar;

    if(paramCount != 1)
    {
        goto ggv_error;
    }

    if(varlist[0]->vt == VT_STR)
    {
        ptmpvar = Varlist_GetByName(&global_var_list, StrCache_Get(varlist[0]->strVal));
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        ptmpvar = Varlist_GetByIndex(&global_var_list, (int)ltemp);
    }
    else
    {
        goto ggv_error;
    }

    if(ptmpvar)
    {
        ScriptVariant_Copy(*pretvar,  ptmpvar);
    }
    else
    {
        ScriptVariant_Clear(*pretvar);
    }
    return S_OK;

ggv_error:
    *pretvar = NULL;
    return E_FAIL;
}
//setglobalvar(varname, value);
HRESULT system_setglobalvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(paramCount < 2)
    {
        goto sgv_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    if(varlist[0]->vt == VT_STR)
    {
        (*pretvar)->lVal = (LONG)Varlist_SetByName(&global_var_list, StrCache_Get(varlist[0]->strVal), varlist[1]);
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        (*pretvar)->lVal = (LONG)Varlist_SetByIndex(&global_var_list, (int)ltemp, varlist[1]);
    }
    else
    {
        goto sgv_error;
    }

    return S_OK;
sgv_error:
    *pretvar = NULL;
    return E_FAIL;
}
//getlocalvar(varname);
HRESULT system_getlocalvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    ScriptVariant *ptmpvar;

    if(paramCount != 1)
    {
        goto glv_error;
    }

    if(varlist[0]->vt == VT_STR)
    {
        ptmpvar = Varlist_GetByName(pcurrentscript->varlist, StrCache_Get(varlist[0]->strVal));
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        ptmpvar = Varlist_GetByIndex(pcurrentscript->varlist, (int)ltemp);
    }
    else
    {
        goto glv_error;
    }

    if(ptmpvar)
    {
        ScriptVariant_Copy(*pretvar,  ptmpvar);
    }
    else
    {
        ScriptVariant_Clear(*pretvar);
    }
    return S_OK;

glv_error:
    *pretvar = NULL;
    return E_FAIL;
}
//setlocalvar(varname, value);
HRESULT system_setlocalvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(paramCount < 2)
    {
        goto slv_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    if(varlist[0]->vt == VT_STR)
    {
        (*pretvar)->lVal = (LONG)Varlist_SetByName(pcurrentscript->varlist, StrCache_Get(varlist[0]->strVal), varlist[1]);
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        (*pretvar)->lVal = (LONG)Varlist_SetByIndex(pcurrentscript->varlist, (int)ltemp, varlist[1]);
    }
    else
    {
        goto slv_error;
    }

    return S_OK;
slv_error:
    *pretvar = NULL;
    return E_FAIL;
}
//clearlocalvar();
HRESULT system_clearlocalvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    *pretvar = NULL;
    Varlist_Cleanup(pcurrentscript->varlist);
    return S_OK;
}
//clearglobalvar();
HRESULT system_clearglobalvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    *pretvar = NULL;
    Varlist_Cleanup(&global_var_list);
    return S_OK;
}

//free();
HRESULT system_free(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar) return E_FAIL;
    *pretvar = NULL;
    if(paramCount < 1 || !varlist || !varlist[0] || !varlist[0]->ptrVal)
    {
        return E_FAIL;
    }
    if(obor_script_cleanup_active(varlist[0]->ptrVal)) return E_FAIL;
    if(List_Includes(&scriptheap, varlist[0]->ptrVal))
    {
        Node *entry = List_GetCurrentNode(&scriptheap);
        _freeheapnode(List_Retrieve(&scriptheap));
        /* Nested cleanup can move the cursor while this node is still live. */
        List_SetCurrent(&scriptheap, entry);
        List_Remove(&scriptheap);
        return S_OK;
    }
    return E_FAIL;
}

//typeof(v);
HRESULT system_typeof(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(paramCount < 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)varlist[0]->vt;
    return S_OK;
}

HRESULT math_sin(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = sin_table[(ltemp % 360 + 360) % 360];
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_cos(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = cos_table[(ltemp % 360 + 360) % 360];
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_ssin(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE dbltemp;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)))
    {
        double PI = 3.14159265;

        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)sin(dbltemp*PI/180.0);
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_scos(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE dbltemp;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)))
    {
        double PI = 3.14159265;

        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)cos(dbltemp*PI/180.0);
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_sqrt(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE dbltemp;
    float inv;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)))
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        inv = invsqrt((float)dbltemp);
        assert(inv != 0.0f);
        (*pretvar)->dblVal = (DOUBLE)1.0 / inv;
        return S_OK;
    }
    *pretvar = NULL;

    return E_FAIL;
}

HRESULT math_pow(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE dbltempA, dbltempB;

    if( SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltempA)) && SUCCEEDED(ScriptVariant_DecimalValue(varlist[1], &dbltempB)) )
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = pow((double)dbltempA,(double)dbltempB);
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_asin(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE dbltemp;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)))
    {
        double PI = 3.14159265;

        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)(asin((double)dbltemp) * 180.0 / PI);
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_acos(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE dbltemp;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)))
    {
        double PI = 3.14159265;

        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)(aacos((double)dbltemp) * 180.0 / PI);
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_atan(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE dbltemp;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)))
    {
        double PI = 3.14159265;

        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)(aatan((double)dbltemp) * 180.0 / PI);
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_trunc(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(paramCount < 1 || !varlist || !varlist[0])
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    DOUBLE dbltemp;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)) &&
       dbltemp > -2147483649.0 && dbltemp < 2147483648.0)
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)(trunc(dbltemp));
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT math_round(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(paramCount < 1 || !varlist || !varlist[0])
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    DOUBLE dbltemp;

    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[0], &dbltemp)))
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)(round(dbltemp));
        return S_OK;
    }
    *pretvar = NULL;
    return E_FAIL;
}


//////////////////////////////////////////////////////////
////////////   openbor functions
//////////////////////////////////////////////////////////

//check openborscript.h for systemvariant_enum

// arranged list, for searching
static const char *svlist[] =
{
    "background",
    "blockade",
    "branchname",
    "cheats",
    "count_enemies",
    "count_entities",
    "count_npcs",
    "count_players",
    "current_branch",
    "current_level",
    "current_palette",
    "current_scene",
    "current_set",
    "current_stage",
    "effectvol",
    "elapsed_time",
    "ent_max",
    "fps",
    "freeram",
    "game_paused",
    "game_speed",
    "game_time",
    "gfx_x_offset",
    "gfx_y_offset",
    "gfx_y_offset_adj",
    "hresolution",
    "in_cheat_options",
    "in_control_options",
    "in_enginecreditsscreen",
    "in_gameoverscreen",
    "in_halloffamescreen",
    "in_level",
    "in_load_game",
    "in_menuscreen",
    "in_new_game",
    "in_options",
    "in_selectscreen",
    "in_showcomplete",
    "in_sound_options",
    "in_start_game",
    "in_system_options",
    "in_titlescreen",
    "in_video_options",
    "lasthita",
    "lasthitc",
    "lasthitt",
    "lasthitx",
    "lasthity",
    "lasthitz",
    "levelheight",
    "levelpos",
    "levelwidth",
    "lightx",
    "lightz",
    "maxanimations",
    "maxattacktypes",
    "maxentityvars",
    "maxglobalvars",
    "maxindexedvars",
    "maxplayers",
    "maxscriptvars",
    "maxsoundchannels",
    "models_cached",
    "models_loaded",
    "musicvol",
    "nofadeout",
    "nogameover",
    "nohof",
    "nojoin",
    "nopause",
    "nosave",
    "noscreenshot",
    "noshowcomplete",
    "numbasemaps",
    "numholes",
    "numlayers",
    "numpalettes",
    "numwalls",
    "pakname",
    "pause",
    "pixelformat",
    "player",
    "player1",
    "player2",
    "player3",
    "player4",
    "player_max_z",
    "player_min_z",
    "porting",
    "sample_play_id",
    "scrollmaxx",
    "scrollmaxz",
    "scrollminx",
    "scrollminz",
    "self",
    "sets_count",
    "shadowalpha",
    "shadowcolor",
    "shadowopacity",
    "skiptoset",
    "slowmotion",
    "slowmotion_duration",
    "smartbomber",
    "soundvol",
    "textbox",
    "ticks",
    "totalram",
    "usedram",
    "viewporth",
    "viewportw",
    "viewportx",
    "viewporty",
    "vresolution",
    "vscreen",
    "waiting",
    "xpos",
    "ypos",
};


// ===== openborvariant =====
/* Native names remain sorted; translate only the profile's missing entries. */
static int obor_systemvariant_available(int property)
{
    if(property == _sv_game_time) return obor_profile_build >= 4456;
    if(property == _sv_sets_count) return obor_profile_build >= 4477;
    if(obor_profile_build < 4283) return 1;
    return (property != _sv_maxsoundchannels || obor_profile_build >= 4304) &&
           (property != _sv_noshowcomplete || obor_profile_build >= 4394) &&
           (property != _sv_porting || obor_profile_build >= 4345) &&
           (property != _sv_shadowopacity || obor_profile_build >= 4432);
}

static int obor_systemvariant_native(int property)
{
    if(property < 0 || property >= _sv_the_end) return _sv_the_end;
    if(!obor_systemvariant_available(_sv_game_time) && property >= _sv_game_time) ++property;
    if(!obor_systemvariant_available(_sv_maxsoundchannels) && property >= _sv_maxsoundchannels) ++property;
    if(!obor_systemvariant_available(_sv_noshowcomplete) && property >= _sv_noshowcomplete) ++property;
    if(!obor_systemvariant_available(_sv_porting) && property >= _sv_porting) ++property;
    if(!obor_systemvariant_available(_sv_sets_count) && property >= _sv_sets_count) ++property;
    if(!obor_systemvariant_available(_sv_shadowopacity) && property >= _sv_shadowopacity) ++property;
    return property < _sv_the_end ? property : _sv_the_end;
}

static int obor_systemvariant_logical(int property)
{
    int logical = property;
    if(!obor_systemvariant_available(_sv_game_time) && property > _sv_game_time) --logical;
    if(!obor_systemvariant_available(_sv_maxsoundchannels) && property > _sv_maxsoundchannels) --logical;
    if(!obor_systemvariant_available(_sv_noshowcomplete) && property > _sv_noshowcomplete) --logical;
    if(!obor_systemvariant_available(_sv_porting) && property > _sv_porting) --logical;
    if(!obor_systemvariant_available(_sv_sets_count) && property > _sv_sets_count) --logical;
    if(!obor_systemvariant_available(_sv_shadowopacity) && property > _sv_shadowopacity) --logical;
    return logical;
}

int mapstrings_systemvariant(ScriptVariant **varlist, int paramCount)
{
    int property;
    char *name;
    if(paramCount < 1 || !varlist || !varlist[0]) return 0;
    if(varlist[0]->vt != VT_STR) return 1;
    name = StrCache_GetIfPresent(varlist[0]->strVal);
    if(!name) return 0;
    property = searchList(svlist, name, _sv_the_end);
    if(property >= 0 && obor_systemvariant_available(property))
    {
        int logical = obor_systemvariant_logical(property);
        ScriptVariant_ChangeType(varlist[0], VT_INTEGER);
        varlist[0]->lVal = logical;
        return 1;
    }
    printf("openborvariant: System variable name not found: '%s'\n", name);
    return 0;
}

//sample function, used for getting a system variant
//openborvariant(varname);
HRESULT openbor_systemvariant(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    //used for getting the index from the enum of properties
    int variantindex = -1;
    //the paramCount used for checking.
    //check it first so the engine wont crash if the list is empty
    if(paramCount != 1)
    {
        goto systemvariant_error;
    }
    //call this function's mapstrings function to map string constants to enum values
    mapstrings_systemvariant(varlist, paramCount);
    //the variant name should be here
    //you can check the argument type if you like
    if(varlist[0]->vt == VT_INTEGER)
    {
        variantindex = obor_systemvariant_native(varlist[0]->lVal);
    }
    else
    {
        goto systemvariant_error;
    }
    ///////these should be your get method, ///////
    ScriptVariant_Clear(*pretvar);
    if(getsyspropertybyindex(*pretvar, variantindex))
    {
        return S_OK;
    }
    //else if
    //////////////////////////////////////////////
systemvariant_error:
    *pretvar = NULL;
    // we have finshed, so return
    return E_FAIL;
}


//used for changing a system variant
//changeopenborvariant(varname, value);
HRESULT openbor_changesystemvariant(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    //used for getting the enum constant corresponding to the desired variable
    int variantindex = 0;
    //reference to the arguments
    ScriptVariant *arg = NULL;
    //the paramCount used for checking.
    //check it first so the engine wont crash if the list is empty
    if(paramCount != 2)
    {
        goto changesystemvariant_error;
    }
    // map string constants to enum constants for speed
    mapstrings_systemvariant(varlist, paramCount);
    //get the 1st argument
    arg = varlist[0];
    //the variant name should be here
    //you can check the argument type if you like
    if(arg->vt == VT_INTEGER)
    {
        variantindex = obor_systemvariant_native(arg->lVal);
    }
    else
    {
        goto changesystemvariant_error;
    }

    if(changesyspropertybyindex(variantindex, varlist[1]))
    {
        return S_OK;
    }
changesystemvariant_error:
    *pretvar = NULL;
    // we have finshed, so return
    return E_FAIL;

}

// use font_printf to draw string
//drawstring(x, y, font, string, z);
HRESULT openbor_drawstring(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    char buf[256];
    LONG value[4];
    *pretvar = NULL;

    if(paramCount < 4)
    {
        goto drawstring_error;
    }

    for(i = 0; i < 3; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i)))
        {
            goto drawstring_error;
        }
    }
    if(paramCount > 4)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[4], value + 3)))
        {
            goto drawstring_error;
        }
    }
    else
    {
        value[3] = 0;
    }
    ScriptVariant_ToString(varlist[3], buf);
    font_printf((int)value[0], (int)value[1], (int)value[2], (int)value[3], "%s", buf);
    return S_OK;

drawstring_error:
    printf("First 3 values must be integer values and 4th value a string: drawstring(int x, int y, int font, value)\n");
    return E_FAIL;
}

//use screen_printf
//drawstringtoscreen(screen, x, y, font, string);
HRESULT openbor_drawstringtoscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    s_screen *scr;
    char buf[256];
    LONG value[3];
    *pretvar = NULL;

    if(paramCount != 5)
    {
        goto drawstring_error;
    }

    if(varlist[0]->vt != VT_PTR)
    {
        goto drawstring_error;
    }
    scr = (s_screen *)varlist[0]->ptrVal;
    if(!scr)
    {
        goto drawstring_error;
    }

    for(i = 0; i < 3; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i + 1], value + i)))
        {
            goto drawstring_error;
        }
    }

    ScriptVariant_ToString(varlist[4], buf);
    screen_printf(scr, (int)value[0], (int)value[1], (int)value[2], "%s", buf);
    return S_OK;

drawstring_error:
    printf("Function needs a valid screen handle, 3 integers and a string value: drawstringtoscreen(screen, int font, value)\n");
    return E_FAIL;
}

// debug purpose
//log(string);
HRESULT openbor_log(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    char buf[256];
    *pretvar = NULL;

    if(paramCount != 1)
    {
        goto drawstring_error;
    }

    ScriptVariant_ToString(varlist[0], buf);
    printf("%s", buf);
    return S_OK;

drawstring_error:
    printf("Function needs 1 parameter: log(value)\n");
    return E_FAIL;
}

//drawbox(x, y, width, height, z, color, lut);
HRESULT openbor_drawbox(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[6], l;
    *pretvar = NULL;
    s_drawmethod dm;

    if(paramCount < 6)
    {
        goto drawbox_error;
    }

    for(i = 0; i < 6; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i)))
        {
            goto drawbox_error;
        }
    }

    if(paramCount > 6)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[6], &l)))
        {
            goto drawbox_error;
        }
    }
    else
    {
        l = -1;
    }

    if(l >= 0)
    {
        l %= MAX_BLENDINGS + 1;
    }
    if(drawmethod.flag)
    {
        dm = drawmethod;
    }
    else
    {
        dm = plainmethod;
    }
    dm.alpha = l;
    spriteq_add_box((int)value[0], (int)value[1], (int)value[2], (int)value[3], (int)value[4], (int)value[5], &dm);

    return S_OK;

drawbox_error:
    printf("Function requires 6 integer values: drawbox(int x, int y, int width, int height, int z, int color, int lut)\n");
    return E_FAIL;
}

//drawboxtoscreen(screen, x, y, width, height, color, lut);
HRESULT openbor_drawboxtoscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    s_screen *s;
    LONG value[5], l;
    *pretvar = NULL;
    s_drawmethod dm;

    if(paramCount < 6)
    {
        goto drawbox_error;
    }

    s = (s_screen *)varlist[0]->ptrVal;

    if(!s)
    {
        goto drawbox_error;
    }

    for(i = 1; i < 6; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i - 1)))
        {
            goto drawbox_error;
        }
    }

    if(paramCount > 6)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[6], &l)))
        {
            goto drawbox_error;
        }
    }
    else
    {
        l = -1;
    }

    if(l >= 0)
    {
        l %= MAX_BLENDINGS + 1;
    }
    if(drawmethod.flag)
    {
        dm = drawmethod;
    }
    else
    {
        dm = plainmethod;
    }
    dm.alpha = l;

    putbox((int)value[0], (int)value[1], (int)value[2], (int)value[3], (int)value[4], s, &dm);

    return S_OK;

drawbox_error:
    printf("Function requires a screen handle and 5 integer values, 7th integer value is optional: drawboxtoscreen(screen, int x, int y, int width, int height, int color, int lut)\n");
    return E_FAIL;
}

//drawline(x1, y1, x2, y2, z, color, lut);
HRESULT openbor_drawline(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[6], l;
    *pretvar = NULL;
    s_drawmethod dm;

    if(paramCount < 6)
    {
        goto drawline_error;
    }

    for(i = 0; i < 6; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i)))
        {
            goto drawline_error;
        }
    }

    if(paramCount > 6)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[6], &l)))
        {
            goto drawline_error;
        }
    }
    else
    {
        l = -1;
    }

    if(l >= 0 )
    {
        l %= MAX_BLENDINGS + 1;
    }
    if(drawmethod.flag)
    {
        dm = drawmethod;
    }
    else
    {
        dm = plainmethod;
    }
    dm.alpha = l;
    spriteq_add_line((int)value[0], (int)value[1], (int)value[2], (int)value[3], (int)value[4], (int)value[5], &dm);

    return S_OK;

drawline_error:
    printf("Function requires 6 integer values, 7th integer value is optional: drawline(int x1, int y1, int x2, int y2, int z, int color, int lut)\n");
    return E_FAIL;
}

//drawlinetoscreen(screen, x1, y1, x2, y2, color, lut);
HRESULT openbor_drawlinetoscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[5], l;
    s_screen *s;
    *pretvar = NULL;
    s_drawmethod dm;

    if(paramCount < 6)
    {
        goto drawline_error;
    }

    s = (s_screen *)varlist[0]->ptrVal;

    if(!s)
    {
        goto drawline_error;
    }

    for(i = 1; i < 6; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i - 1)))
        {
            goto drawline_error;
        }
    }

    if(paramCount > 6)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[6], &l)))
        {
            goto drawline_error;
        }
    }
    else
    {
        l = -1;
    }

    if(l >= 0 )
    {
        l %= MAX_BLENDINGS + 1;
    }
    if(drawmethod.flag)
    {
        dm = drawmethod;
    }
    else
    {
        dm = plainmethod;
    }
    dm.alpha = l;
    putline((int)value[0], (int)value[1], (int)value[2], (int)value[3], (int)value[4], s, &dm);

    return S_OK;
drawline_error:
    printf("Function requires a screen handle and 5 integer values, 7th integer value is optional: drawlinetoscreen(screen, int x1, int y1, int x2, int y2, int color, int lut)\n");
    return E_FAIL;
}

//drawsprite(sprite, x, y, z, sortid);
HRESULT openbor_drawsprite(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[4];
    s_sprite *spr;
    *pretvar = NULL;

    if(paramCount < 4)
    {
        goto drawsprite_error;
    }
    if(varlist[0]->vt != VT_PTR)
    {
        goto drawsprite_error;
    }

    spr = varlist[0]->ptrVal;
    if(!spr)
    {
        goto drawsprite_error;
    }

    value[3] = (LONG)0;
    for(i = 1; i < paramCount && i < 5; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i - 1)))
        {
            goto drawsprite_error;
        }
    }

    spriteq_add_frame((int)value[0], (int)value[1], (int)value[2], spr, &drawmethod, (int)value[3]);

    return S_OK;

drawsprite_error:
    printf("Function requires a valid sprite handle 3 integer values, 5th integer value is optional: drawsprite(sprite, int x, int y, int z, int sortid)\n");
    return E_FAIL;
}

//drawspritetoscreen(sprite, screen, x, y);
HRESULT openbor_drawspritetoscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[2];
    s_sprite *spr;
    s_screen *scr;
    *pretvar = NULL;

    if(paramCount < 4)
    {
        goto drawsprite_error;
    }
    if(varlist[0]->vt != VT_PTR)
    {
        goto drawsprite_error;
    }
    spr = varlist[0]->ptrVal;
    if(!spr)
    {
        goto drawsprite_error;
    }

    if(varlist[1]->vt != VT_PTR)
    {
        goto drawsprite_error;
    }
    scr = varlist[1]->ptrVal;
    if(!scr)
    {
        goto drawsprite_error;
    }

    for(i = 2; i < paramCount && i < 4; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + (i - 2))))
        {
            goto drawsprite_error;
        }
    }

    putsprite((int)value[0], (int)value[1], spr, scr, &drawmethod);

    return S_OK;

drawsprite_error:
    printf("Function requires a valid sprite handle, a valid screen handle and 2 integer values: drawspritetoscreen(sprite, screen, int x, int y)\n");
    return E_FAIL;
}

//drawdot(x, y, z, color, lut);
HRESULT openbor_drawdot(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[4], l;
    *pretvar = NULL;
    s_drawmethod dm;

    if(paramCount < 4)
    {
        goto drawdot_error;
    }

    for(i = 0; i < 4; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i)))
        {
            goto drawdot_error;
        }
    }

    if(paramCount > 4)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[4], &l)))
        {
            goto drawdot_error;
        }
    }
    else
    {
        l = -1;
    }

    if(l >= 0 )
    {
        l %= MAX_BLENDINGS + 1;
    }
    if(drawmethod.flag)
    {
        dm = drawmethod;
    }
    else
    {
        dm = plainmethod;
    }
    dm.alpha = l;
    spriteq_add_dot((int)value[0], (int)value[1], (int)value[2], (int)value[3], &dm);

    return S_OK;

drawdot_error:
    printf("Function requires 4 integer values, 5th integer value is optional: drawdot(int x, int y, int z, int color, int lut)\n");
    return E_FAIL;
}

//drawdottoscreen(screen, x, y, color, lut);
HRESULT openbor_drawdottoscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[3], l;
    s_screen *s;
    *pretvar = NULL;
    s_drawmethod dm;

    if(paramCount < 4)
    {
        goto drawdot_error;
    }

    s = (s_screen *)varlist[0]->ptrVal;

    if(!s)
    {
        goto drawdot_error;
    }

    for(i = 1; i < 4; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i - 1)))
        {
            goto drawdot_error;
        }
    }

    if(paramCount > 4)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[4], &l)))
        {
            goto drawdot_error;
        }
    }
    else
    {
        l = -1;
    }

    if(l >= 0 )
    {
        l %= MAX_BLENDINGS + 1;
    }
    if(drawmethod.flag)
    {
        dm = drawmethod;
    }
    else
    {
        dm = plainmethod;
    }
    dm.alpha = l;

    putpixel((int)value[0], (int)value[1], (int)value[2], s, &dm);

    return S_OK;

drawdot_error:
    printf("Function requires a screen handle and 3 integer values, 5th integer value is optional: dottoscreen(screen, int x, int y, int color, int lut)\n");
    return E_FAIL;
}


//drawscreen(screen, x, y, z, lut);
HRESULT openbor_drawscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    LONG value[3], l;
    s_screen *s;
    s_drawmethod screenmethod;
    *pretvar = NULL;

    if(paramCount < 4)
    {
        goto drawscreen_error;
    }

    s = (s_screen *)varlist[0]->ptrVal;

    if(!s)
    {
        goto drawscreen_error;
    }

    for(i = 1; i < 4; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i - 1)))
        {
            goto drawscreen_error;
        }
    }

    if(paramCount > 4)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[4], &l)))
        {
            goto drawscreen_error;
        }
    }
    else
    {
        l = -1;
    }

    if(l >= 0 )
    {
        l %= MAX_BLENDINGS + 1;
    }
    if(paramCount <= 4)
    {
        screenmethod = drawmethod;
    }
    else
    {
        screenmethod = plainmethod;
        screenmethod.alpha = l;
        screenmethod.transbg = 1;
    }

    spriteq_add_screen((int)value[0], (int)value[1], (int)value[2], s, &screenmethod, 0);

    return S_OK;

drawscreen_error:
    printf("Function requires a screen handle and 3 integer values, 5th integer value is optional: drawscreen(screen, int x, int y, int z, int lut)\n");
    return E_FAIL;
}

//getindexedvar(int index);
HRESULT openbor_getindexedvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    return system_getglobalvar(varlist, pretvar, paramCount);
}

//setindexedvar(int index, var);
HRESULT openbor_setindexedvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    return system_setglobalvar(varlist, pretvar, paramCount);
}

//getscriptvar(int index);
HRESULT openbor_getscriptvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    return system_getlocalvar(varlist, pretvar, paramCount);
}

//setscriptvar(int index, var);
HRESULT openbor_setscriptvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    return system_setlocalvar(varlist, pretvar, paramCount);
}

//getentityvar(entity, int index);
HRESULT openbor_getentityvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    ScriptVariant *ptmpvar;
    entity *ent;

    if(paramCount < 2 || varlist[0]->vt != VT_PTR || !varlist[0]->ptrVal)
    {
        goto gev_error;
    }

    ent = (entity *)varlist[0]->ptrVal;

    if(varlist[1]->vt == VT_STR)
    {
        ptmpvar = Varlist_GetByName(ent->varlist, StrCache_Get(varlist[1]->strVal));
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)))
    {
        ptmpvar = Varlist_GetByIndex(ent->varlist, (int)ltemp);
    }
    else
    {
        goto gev_error;
    }

    if(ptmpvar)
    {
        ScriptVariant_Copy(*pretvar,  ptmpvar);
    }
    else
    {
        ScriptVariant_Clear(*pretvar);
    }
    return S_OK;

gev_error:
    *pretvar = NULL;
    return E_FAIL;
}

//setentityvar(int index, var);
HRESULT openbor_setentityvar(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    entity *ent;

    if(paramCount < 3 || varlist[0]->vt != VT_PTR || !varlist[0]->ptrVal)
    {
        goto sev_error;
    }

    ent = (entity *)varlist[0]->ptrVal;

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    if(varlist[1]->vt == VT_STR)
    {
        (*pretvar)->lVal = (LONG)Varlist_SetByName(ent->varlist, StrCache_Get(varlist[1]->strVal), varlist[2]);
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)))
    {
        (*pretvar)->lVal = (LONG)Varlist_SetByIndex(ent->varlist, (int)ltemp, varlist[2]);
    }
    else
    {
        goto sev_error;
    }

    return S_OK;
sev_error:
    *pretvar = NULL;
    return E_FAIL;
}

//strinfirst(char string, char search_string);
HRESULT openbor_strinfirst(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    char *tempstr = NULL;

    if(paramCount < 2)
    {
        goto sif_error;
    }

    if(varlist[0]->vt != VT_STR || varlist[1]->vt != VT_STR)
    {
        printf("\n Error, strinfirst({string}, {search string}): Strinfirst must be passed valid {string} and {search string}. \n");
        goto sif_error;
    }

    tempstr = strstr((char *)StrCache_Get(varlist[0]->strVal), (char *)StrCache_Get(varlist[1]->strVal));

    if (tempstr != NULL)
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, tempstr);
    }
    else
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = -1;
    }
    return S_OK;

sif_error:
    *pretvar = NULL;
    return E_FAIL;
}

//strinlast(char string, char search_string);
HRESULT openbor_strinlast(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    char *tempstr = NULL;

    if(paramCount < 2)
    {
        goto sil_error;
    }

    if(varlist[0]->vt != VT_STR || varlist[1]->vt != VT_STR)
    {
        printf("\n Error, strinlast({string}, {search string}): Strinlast must be passed valid {string} and {search string}. \n");
        goto sil_error;
    }

    tempstr = strrchr((char *)StrCache_Get(varlist[0]->strVal), varlist[1]->strVal);

    if (tempstr != NULL)
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, tempstr);
    }
    else
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = -1;
    }
    return S_OK;
sil_error:
    *pretvar = NULL;
    return E_FAIL;
}

//strleft(char string, int i);
HRESULT openbor_strleft(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(paramCount < 2)
    {
        goto sl_error;
    }

    if(varlist[0]->vt != VT_STR || varlist[1]->vt != VT_INTEGER)
    {
        printf("\n Error, strleft({string}, {characters}): Invalid or missing parameter. Strleft must be passed valid {string} and number of {characters}.\n");
        goto sl_error;
    }
    ScriptVariant_ChangeType(*pretvar, VT_STR);
    StrCache_NCopy((*pretvar)->strVal, (char *)StrCache_Get(varlist[0]->strVal), varlist[1]->lVal);

    return S_OK;
sl_error:
    *pretvar = NULL;
    return E_FAIL;
}

//strlength(char string);
HRESULT openbor_strlength(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(paramCount < 1 || varlist[0]->vt != VT_STR)
    {
        goto strlength_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = strlen((char *)StrCache_Get(varlist[0]->strVal));
    return S_OK;

strlength_error:
    printf("Error, strlength({string}): Invalid or missing parameter. Strlength must be passed a valid {string}.\n");
    *pretvar = NULL;
    return E_FAIL;
}

//strwidth(char string, int font);
HRESULT openbor_strwidth(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(paramCount < 2 || varlist[0]->vt != VT_STR ||
            FAILED(ScriptVariant_IntegerValue(varlist[1], &ltemp)))
    {
        goto strwidth_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = font_string_width((int)ltemp, (char *)StrCache_Get(varlist[0]->strVal));
    return S_OK;

strwidth_error:
    printf("Error, strwidth({string}, {font}): Invalid or missing parameter.\n");
    *pretvar = NULL;
    return E_FAIL;
}

//strright(char string, int i);
HRESULT openbor_strright(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    char *tempstr = NULL;

    if(!pretvar) return E_FAIL;
    if(paramCount < 2 || !varlist || !varlist[0] || !varlist[1] || !*pretvar)
    {
        goto sr_error;
    }

    if(varlist[0]->vt != VT_STR || varlist[1]->vt != VT_INTEGER)
    {
        printf("\n Error, strright({string}, {characters}): Invalid or missing parameter. Strright must be passed valid {string} and number of {characters}.\n");
        goto sr_error;
    }

    tempstr = StrCache_GetIfPresent(varlist[0]->strVal);
    if(!tempstr) goto sr_error;

    if(tempstr[0])
    {
        const LONG offset = varlist[1]->lVal;
        if(offset < 0 || (size_t)offset > strlen(tempstr)) goto sr_error;

        ScriptVariant saved = {.vt = VT_EMPTY};
        ScriptVariant_Copy(&saved, varlist[0]);
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, tempstr + offset);
        ScriptVariant_Clear(&saved);
    }
    else
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = -1;
    }

    return S_OK;
sr_error:
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT openbor_getmodelproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int iArg;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    if((varlist[0]->vt != VT_INTEGER && varlist[0]->vt != VT_STR) || varlist[1]->vt != VT_INTEGER)
    {
        printf("\n Error, getmodelproperty({model}, {property}): Invalid or missing parameter. Getmodelproperty must be passed valid {model} and {property} indexes.\n");
    }

    iArg = varlist[0]->vt == VT_INTEGER ? varlist[0]->lVal : get_cached_model_index(StrCache_Get(varlist[0]->strVal));

    if(iArg < 0 || iArg >= models_cached)
    {
        return E_FAIL;
    }

    switch (varlist[1]->lVal)
    {
    case 0:                                                    //Loaded?
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)model_cache[iArg].loadflag;
        break;
    }
    case 1:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)model_cache[iArg].model;
    }
    case 2:
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, model_cache[iArg].name);
        break;
    }
    case 3:
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, model_cache[iArg].path);
        break;
    }
    case 4:                                                    //Loaded?
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)model_cache[iArg].selectable;
        break;
    }
    }

    return S_OK;
}

HRESULT openbor_changemodelproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int iArg;
    LONG ltemp;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    if((varlist[0]->vt != VT_INTEGER && varlist[0]->vt != VT_STR) || varlist[1]->vt != VT_INTEGER)
    {
        printf("\n Error, changemodelproperty({model}, {property}, {value}): Invalid or missing parameter. Changemodelproperty must be passed valid {model}, {property} and {value}.\n");
    }

    iArg = varlist[0]->vt == VT_INTEGER ? varlist[0]->lVal : get_cached_model_index(StrCache_Get(varlist[0]->strVal));

    if(iArg < 0 || iArg >= models_cached)
    {
        return E_FAIL;
    }

    switch (varlist[1]->lVal)
    {
    case 0:                                                    //Loaded?
    {
        /*
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        	model_cache[iArg].loadflag = (int)ltemp;
        else (*pretvar)->lVal = (LONG)0;
        break;
        */
    }
    case 1:
    {
        /*
        if(varlist[2]->vt != VT_STR)
        {
        	printf("You must give a string value for {value}.\n");
        	goto changeentityproperty_error;
        }
        strcpy(model_cache[iArg].model, (char*)StrCache_Get(varlist[2]->strVal));
        (*pretvar)->lVal = (LONG)1;
        break;
        */
    }
    case 2:
    {
        /*
        if(varlist[2]->vt != VT_STR)
        {
        	printf("You must give a string value for {value}.\n");
        	goto changeentityproperty_error;
        }
        strcpy(model_cache[iArg].name, (char*)StrCache_Get(varlist[2]->strVal));
        (*pretvar)->lVal = (LONG)1;
        break;
        */
    }
    case 3:
    {
        /*
        if(varlist[2]->vt != VT_STR)
        {
        	printf("You must give a string value for {value}.\n");
        	goto changeentityproperty_error;
        }
        strcpy(model_cache[iArg].path, (char*)StrCache_Get(varlist[2]->strVal));
        (*pretvar)->lVal = (LONG)1;
        break;
        */
    }
    case 4:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            model_cache[iArg].selectable = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    }
    }

    return S_OK;
}

// ===== getentityproperty =====
enum entityproperty_enum
{
    _ep_a,
    _ep_aggression,
    _ep_aiattack,
    _ep_aiflag,
    _ep_aimove,
    _ep_alpha,
    _ep_animal,
    _ep_animating,
    _ep_animation,
    _ep_animation_handle,
    _ep_animationid,
    _ep_animheight,
    _ep_animhits,
    _ep_animnum,
    _ep_animpos,
    _ep_animvalid,
    _ep_antigrab,
    _ep_antigravity,
    _ep_attackid,
    _ep_attacking,
    _ep_attackthrottle,
    _ep_attackthrottletime,
    _ep_autokill,
    _ep_base,
    _ep_bbox,
    _ep_binding,
    _ep_blink,
    _ep_blockback,
    _ep_blockodds,
    _ep_blockpain,
    _ep_boomerang,
    _ep_boss,
    _ep_bounce,
    _ep_bound,
    _ep_candamage,
    _ep_chargerate,
    _ep_colourmap,
    _ep_colourtable,
    _ep_combostep,
    _ep_combotime,
    _ep_custom_target,
    _ep_damage_on_landing,
    _ep_dead,
    _ep_defaultmodel,
    _ep_defaultname,
    _ep_defense,
    _ep_destx,
    _ep_destz,
    _ep_detect,
    _ep_die_on_landing,
    _ep_direction,
    _ep_dot,
    _ep_dropframe,
    _ep_edelay,
    _ep_energycost,
    _ep_escapecount,
    _ep_escapehits,
    _ep_exists,
    _ep_facing,
    _ep_falldie,
    _ep_flash,
    _ep_freezetime,
    _ep_frozen,
    _ep_gfxshadow,
    _ep_grabbing,
    _ep_grabforce,
    _ep_guardpoints,
    _ep_hasplatforms,
    _ep_health,
    _ep_height,
    _ep_hitbyid,
    _ep_hitheadplatform,
    _ep_hitwall,
    _ep_hmapl,
    _ep_hmapu,
    _ep_hostile,
    _ep_icon,
    _ep_iconposition,
    _ep_invincible,
    _ep_invinctime,
    _ep_jugglepoints,
    _ep_jumpheight,
    _ep_jumpmovex,
    _ep_jumpmovez,
    _ep_jumpspeed,
    _ep_knockdowncount,
    _ep_komap,
    _ep_landedplatform,
    _ep_landframe,
    _ep_lifeposition,
    _ep_lifespancountdown,
    _ep_link,
    _ep_map,
    _ep_mapcount,
    _ep_mapdefault,
    _ep_maps,
    _ep_maptime,
    _ep_maxguardpoints,
    _ep_maxhealth,
    _ep_maxjugglepoints,
    _ep_maxmp,
    _ep_model,
    _ep_mp,
    _ep_mpdroprate,
    _ep_mprate,
    _ep_mpset,
    _ep_mpstable,
    _ep_mpstableval,
    _ep_name,
    _ep_nameposition,
    _ep_nextanim,
    _ep_nextmove,
    _ep_nextthink,
    _ep_no_adjust_base,
    _ep_noaicontrol,
    _ep_nodieblink,
    _ep_nodrop,
    _ep_nograb,
    _ep_nohithead,
    _ep_nolife,
    _ep_nopain,
    _ep_numweapons,
    _ep_offense,
    _ep_offscreen_noatk_factor,
    _ep_offscreenkill,
    _ep_opponent,
    _ep_owner,
    _ep_pain_time,
    _ep_parent,
    _ep_path,
    _ep_pathfindstep,
    _ep_playerindex,
    _ep_position,
    _ep_projectile,
    _ep_projectilehit,
    _ep_range,
    _ep_releasetime,
    _ep_running,
    _ep_rush_count,
    _ep_rush_tally,
    _ep_rush_time,
    _ep_score,
    _ep_scroll,
    _ep_seal,
    _ep_sealtime,
    _ep_setlayer,
    _ep_shadowbase,
    _ep_sortid,
    _ep_spawntype,
    _ep_speed,
    _ep_sprite,
    _ep_spritea,
    _ep_stalltime,
    _ep_stats,
    _ep_staydown,
    _ep_staydownatk,
    _ep_stealth,
    _ep_subentity,
    _ep_subject_to_basemap,
    _ep_subject_to_gravity,
    _ep_subject_to_hole,
    _ep_subject_to_maxz,
    _ep_subject_to_minz,
    _ep_subject_to_obstacle,
    _ep_subject_to_platform,
    _ep_subject_to_screen,
    _ep_subject_to_wall,
    _ep_subtype,
    _ep_takeaction,
    _ep_think,
    _ep_thold,
    _ep_throwdamage,
    _ep_throwdist,
    _ep_throwframewait,
    _ep_throwheight,
    _ep_tosstime,
    _ep_tossv,
    _ep_trymove,
    _ep_type,
    _ep_velocity,
    _ep_vulnerable,
    _ep_walkoffmovex,
    _ep_walkoffmovez,
    _ep_weapent,
    _ep_weaploss,
    _ep_weapnum,
    _ep_weapon,
    _ep_x,
    _ep_xdir,
    _ep_y,
    _ep_z,
    _ep_zdir,
    _ep_the_end,
};

// arranged list, for searching
static const char *eplist[] =
{
    "a",
    "aggression",
    "aiattack",
    "aiflag",
    "aimove",
    "alpha",
    "animal",
    "animating",
    "animation",
    "animation.handle",
    "animationid",
    "animheight",
    "animhits",
    "animnum",
    "animpos",
    "animvalid",
    "antigrab",
    "antigravity",
    "attackid",
    "attacking",
    "attackthrottle",
    "attackthrottletime",
    "autokill",
    "base",
    "bbox",
    "binding",
    "blink",
    "blockback",
    "blockodds",
    "blockpain",
    "boomerang",
    "boss",
    "bounce",
    "bound",
    "candamage",
    "chargerate",
    "colourmap",
    "colourtable",
    "combostep",
    "combotime",
    "custom_target",
    "damage_on_landing",
    "dead",
    "defaultmodel",
    "defaultname",
    "defense",
    "destx",
    "destz",
    "detect",
    "die_on_landing",
    "direction",
    "dot",
    "dropframe",
    "edelay",
    "energycost",
    "escapecount",
    "escapehits",
    "exists",
    "facing",
    "falldie",
    "flash",
    "freezetime",
    "frozen",
    "gfxshadow",
    "grabbing",
    "grabforce",
    "guardpoints",
    "hasplatforms",
    "health",
    "height",
    "hitbyid",
    "hitheadplatform",
    "hitwall",
    "hmapl",
    "hmapu",
    "hostile",
    "icon",
    "iconposition",
    "invincible",
    "invinctime",
    "jugglepoints",
    "jumpheight",
    "jumpmovex",
    "jumpmovez",
    "jumpspeed",
    "knockdowncount",
    "komap",
    "landedplatform",
    "landframe",
    "lifeposition",
    "lifespancountdown",
    "link",
    "map",
    "mapcount",
    "mapdefault",
    "maps",
    "maptime",
    "maxguardpoints",
    "maxhealth",
    "maxjugglepoints",
    "maxmp",
    "model",
    "mp",
    "mpdroprate",
    "mprate",
    "mpset",
    "mpstable",
    "mpstableval",
    "name",
    "nameposition",
    "nextanim",
    "nextmove",
    "nextthink",
    "no_adjust_base",
    "noaicontrol",
    "nodieblink",
    "nodrop",
    "nograb",
    "nohithead",
    "nolife",
    "nopain",
    "numweapons",
    "offense",
    "offscreennoatkfactor",
    "offscreenkill",
    "opponent",
    "owner",
    "pain_time",
    "parent",
    "path",
    "pathfindstep",
    "playerindex",
    "position",
    "projectile",
    "projectilehit",
    "range",
    "releasetime",
    "running",
    "rush_count",
    "rush_tally",
    "rush_time",
    "score",
    "scroll",
    "seal",
    "sealtime",
    "setlayer",
    "shadowbase",
    "sortid",
    "spawntype",
    "speed",
    "sprite",
    "spritea",
    "stalltime",
    "stats",
    "staydown",
    "staydownatk",
    "stealth",
    "subentity",
    "subject_to_basemap",
    "subject_to_gravity",
    "subject_to_hole",
    "subject_to_maxz",
    "subject_to_minz",
    "subject_to_obstacle",
    "subject_to_platform",
    "subject_to_screen",
    "subject_to_wall",
    "subtype",
    "takeaction",
    "think",
    "thold",
    "throwdamage",
    "throwdist",
    "throwframewait",
    "throwheight",
    "tosstime",
    "tossv",
    "trymove",
    "type",
    "velocity",
    "vulnerable",
    "walkoffmovex",
    "walkoffmovez",
    "weapent",
    "weaploss",
    "weapnum",
    "weapon",
    "x",
    "xdir",
    "y",
    "z",
    "zdir",
};

enum aiflag_enum
{
    _ep_aiflag_animating,
    _ep_aiflag_attacking,
    _ep_aiflag_autokill,
    _ep_aiflag_blink,
    _ep_aiflag_blocking,
    _ep_aiflag_charging,
    _ep_aiflag_dead,
    _ep_aiflag_drop,
    _ep_aiflag_falling,
    _ep_aiflag_frozen,
    _ep_aiflag_getting,
    _ep_aiflag_idlemode,
    _ep_aiflag_idling,
    _ep_aiflag_inbackpain,
    _ep_aiflag_inpain,
    _ep_aiflag_invincible,
    _ep_aiflag_jumpid,
    _ep_aiflag_jumping,
    _ep_aiflag_projectile,
    _ep_aiflag_running,
    _ep_aiflag_toexplode,
    _ep_aiflag_turning,
    _ep_aiflag_walking,
    _ep_aiflag_walkmode,
    _ep_aiflag_the_end,
};


static const char *eplist_aiflag[] =
{
    "animating",
    "attacking",
    "autokill",
    "blink",
    "blocking",
    "charging",
    "dead",
    "drop",
    "falling",
    "frozen",
    "getting",
    "idlemode",
    "idling",
    "inbackpain",
    "inpain",
    "invincible",
    "jumpid",
    "jumping",
    "projectile",
    "running",
    "toexplode",
    "turning",
    "walking",
    "walkmode",
};

// ===== changedrawmethod ======
enum drawmethod_enum
{
    _dm_alpha,
    _dm_amplitude,
    _dm_beginsize,
    _dm_centerx,
    _dm_centery,
    _dm_channelb,
    _dm_channelg,
    _dm_channelr,
    _dm_clip,
    _dm_cliph,
    _dm_clipw,
    _dm_clipx,
    _dm_clipy,
    _dm_enabled,
    _dm_endsize,
    _dm_fillcolor,
    _dm_flag,
    _dm_fliprotate,
    _dm_flipx,
    _dm_flipy,
    _dm_perspective,
    _dm_remap,
    _dm_reset,
    _dm_rotate,
    _dm_scalex,
    _dm_scaley,
    _dm_shiftx,
    _dm_table,
    _dm_tintcolor,
    _dm_tintmode,
    _dm_transbg,
    _dm_watermode,
    _dm_wavelength,
    _dm_wavespeed,
    _dm_wavetime,
    _dm_xrepeat,
    _dm_xspan,
    _dm_yrepeat,
    _dm_yspan,
    _dm_the_end,
};

enum _prop_dropframe_enum
{
    _PROP_DROPFRAME_FRAME,
    _PROP_DROPFRAME_VELOCITY_X,
    _PROP_DROPFRAME_VELOCITY_Y,
    _PROP_DROPFRAME_VELOCITY_Z,
    _PROP_DROPFRAME_THE_END
};

enum _prop_followup_enum
{
    _PROP_FOLLOWUP_ANIMATION,
    _PROP_FOLLOWUP_CONDITION,
    _PROP_FOLLOWUP_THE_END
};

enum _prop_jumpframe_enum
{
    _PROP_JUMPFRAME_FRAME,
    _PROP_JUMPFRAME_VELOCITY_X,
    _PROP_JUMPFRAME_VELOCITY_Y,
    _PROP_JUMPFRAME_VELOCITY_Z,
    _PROP_JUMPFRAME_THE_END
};

enum _prop_landframe_enum
{
    _PROP_LANDFRAME_FRAME,
    _PROP_LANDFRAME_VELOCITY_X,
    _PROP_LANDFRAME_VELOCITY_Y,
    _PROP_LANDFRAME_VELOCITY_Z,
    _PROP_LANDFRAME_THE_END
};

enum _prop_loop_enum
{
    _PROP_LOOP_FRAME_MAX,
    _PROP_LOOP_FRAME_MIN,
    _PROP_LOOP_MODE,
    _PROP_LOOP_THE_END
};

 enum _prop_move_enum
{
    _PROP_MOVE_BASE,
    _PROP_MOVE_X,
    _PROP_MOVE_Y,
    _PROP_MOVE_Z,
    _PROP_MOVE_THE_END
};

 enum _prop_offset_enum
{
    _PROP_OFFSET_X,
    _PROP_OFFSET_Y,
    _PROP_OFFSET_THE_END
};

 enum _prop_platform_enum
{
    _PROP_PLATFORM_ALT,
    _PROP_PLATFORM_DEPTH,
    _PROP_PLATFORM_LOWERLEFT,
    _PROP_PLATFORM_LOWERRIGHT,
    _PROP_PLATFORM_UPPERLEFT,
    _PROP_PLATFORM_UPPERRIGHT,
    _PROP_PLATFORM_X,
    _PROP_PLATFORM_Z,
    _PROP_PLATFORM_THE_END
};

enum _prop_projectile_enum
{
    _PROP_PROJECTILE_BOMB,
    _PROP_PROJECTILE_FLASH,
    _PROP_PROJECTILE_KNIFE,
    _PROP_PROJECTILE_SHOOTFRAME,
    _PROP_PROJECTILE_STAR,
    _PROP_PROJECTILE_THROWFRAME,
    _PROP_PROJECTILE_THROWPOSITION_BASE,
    _PROP_PROJECTILE_THROWPOSITION_X,
    _PROP_PROJECTILE_THROWPOSITION_Y,
    _PROP_PROJECTILE_THROWPOSITION_Z,
    _PROP_PROJECTILE_TOSSFRAME,
    _PROP_PROJECTILE_THE_END
};

enum _prop_quakeframe_enum
{
    _PROP_QUAKEFRAME_FRAMESTART,
    _PROP_QUAKEFRAME_INTENSITY,
    _PROP_QUAKEFRAME_REPEAT,
    _PROP_QUAKEFRAME_THE_END
};

enum _prop_range_enum
{
    _PROP_RANGEA_MAX,
    _PROP_RANGEA_MIN,
    _PROP_RANGEB_MAX,
    _PROP_RANGEB_MIN,
    _PROP_RANGEX_MAX,
    _PROP_RANGEX_MIN,
    _PROP_RANGEZ_MAX,
    _PROP_RANGEZ_MIN,
    _PROP_RANGE_THE_END
};

enum _prop_size_enum
{
    _PROP_SIZE_BASE,
    _PROP_SIZE_X,
    _PROP_SIZE_Y,
    _PROP_SIZE_Z,
    _PROP_SIZE_THE_END
};

 enum _prop_shadow_enum
{
    _PROP_FSHADOW,
    _PROP_SHADOW_COORDS_X,
    _PROP_SHADOW_COORDS_Y,
    _PROP_SHADOW_THE_END
};

enum _prop_spawnframe_enum
{
    _PROP_SPAWNFRAME_FRAME,
    _PROP_SPAWNFRAME_RELATIVE,
    _PROP_SPAWNFRAME_X,
    _PROP_SPAWNFRAME_Y,
    _PROP_SPAWNFRAME_Z,
    _PROP_SPAWNFRAME_THE_END
};

enum _prop_spritea_enum
{
    _PROP_SPRITEA_CENTERX,
    _PROP_SPRITEA_CENTERY,
    _PROP_SPRITEA_FILE,
    _PROP_SPRITEA_OFFSETX,
    _PROP_SPRITEA_OFFSETY,
    _PROP_SPRITEA_SPRITE,
    _PROP_SPRITEA_THE_END
};

enum _prop_summonframe_enum
{
    _PROP_SUMMONFRAME_FRAME,
    _PROP_SUMMONFRAME_RELATIVE,
    _PROP_SUMMONFRAME_X,
    _PROP_SUMMONFRAME_Y,
    _PROP_SUMMONFRAME_Z,
    _PROP_SUMMONFRAME_THE_END
};

enum _prop_weaponframe_enum
{
    _PROP_WEAPONFRAME_FRAME,
    _PROP_WEAPONFRAME_WEAPON,
    _PROP_WEAPONFRAME_THE_END
};

enum _ep_defense_enum
{
    _ep_defense_blockpower,
    _ep_defense_blockratio,
    _ep_defense_blockthreshold,
    _ep_defense_blocktype,
    _ep_defense_factor,
    _ep_defense_knockdown,
    _ep_defense_pain,
    _ep_defense_the_end,
};

enum gep_dot_enum
{
    _ep_dot_force,
    _ep_dot_mode,
    _ep_dot_owner,
    _ep_dot_rate,
    _ep_dot_time,
    _ep_dot_type,
    _ep_dot_the_end,
};

enum gep_edelay_enum
{
    _ep_edelay_cap_max,
    _ep_edelay_cap_min,
    _ep_edelay_factor,
    _ep_edelay_mode,
    _ep_edelay_range_max,
    _ep_edelay_range_min,
    _ep_edelay_the_end,
};

enum gep_energycost_enum
{
    _ep_energycost_cost,
    _ep_energycost_disable,
    _ep_energycost_mponly,
    _ep_energycost_the_end,
};

enum gep_flash_enum
{
    _ep_flash_block,
    _ep_flash_def,
    _ep_flash_noattack,
    _ep_flash_the_end,
};

enum gep_icon_enum
{
    _ep_icon_def,
    _ep_icon_die,
    _ep_icon_get,
    _ep_icon_mphigh,
    _ep_icon_mplow,
    _ep_icon_mpmed,
    _ep_icon_pain,
    _ep_icon_weapon,
    _ep_icon_x,
    _ep_icon_y,
    _ep_icon_the_end,
};

enum _ep_knockdowncount_enum
{
    _ep_knockdowncount_current,
    _ep_knockdowncount_max,
    _ep_knockdowncount_time,
    _ep_knockdowncount_the_end,
};

enum gep_landframe_enum
{
    _ep_landframe_ent,
    _ep_landframe_frame,
    _ep_landframe_the_end,
};

enum gep_maps_enum
{
    _ep_maps_count,
    _ep_maps_current,
    _ep_maps_default,
    _ep_maps_dying,
    _ep_maps_dying_critical,
    _ep_maps_dying_low,
    _ep_maps_frozen,
    _ep_maps_hide_end,
    _ep_maps_hide_start,
    _ep_maps_ko,
    _ep_maps_kotype,
    _ep_maps_table,
    _ep_maps_time,
    _ep_maps_the_end,
};

enum gep_range_enum
{
    _ep_range_amax,
    _ep_range_amin,
    _ep_range_bmax,
    _ep_range_bmin,
    _ep_range_xmax,
    _ep_range_xmin,
    _ep_range_zmax,
    _ep_range_zmin,
    _ep_range_the_end,
};

enum gep_running_enum
{
    _ep_running_jumpx,
    _ep_running_jumpy,
    _ep_running_land,
    _ep_running_movez,
    _ep_running_speed,
    _ep_running_the_end,
};

enum gep_spritea_enum
{
    _ep_spritea_centerx,
    _ep_spritea_centery,
    _ep_spritea_file,
    _ep_spritea_offsetx,
    _ep_spritea_offsety,
    _ep_spritea_sprite,
    _ep_spritea_the_end,
};

enum gep_staydown_enum
{
    _ep_staydown_rise,
    _ep_staydown_riseattack,
    _ep_staydown_riseattack_stall,
    _ep_staydown_the_end,
};

enum cep_hostile_candamage_enum
{
    _ep_hcd_ground,
    _ep_hcd_type_enemy,
    _ep_hcd_type_npc,
    _ep_hcd_type_obstacle,
    _ep_hcd_type_player,
    _ep_hcd_type_shot,
    _ep_hcd_the_end,
};

enum cep_takeaction_enum
{
    _ep_ta_bomb_explode,
    _ep_ta_common_animation_normal,
    _ep_ta_common_attack_proc,
    _ep_ta_common_block,
    _ep_ta_common_drop,
    _ep_ta_common_fall,
    _ep_ta_common_get,
    _ep_ta_common_grab,
    _ep_ta_common_grabattack,
    _ep_ta_common_grabbed,
    _ep_ta_common_jump,
    _ep_ta_common_land,
    _ep_ta_common_lie,
    _ep_ta_common_pain,
    _ep_ta_common_prejump,
    _ep_ta_common_rise,
    _ep_ta_common_spawn,
    _ep_ta_common_turn,
    _ep_ta_normal_prepare,
    _ep_ta_npc_warp,
    _ep_ta_player_blink,
    _ep_ta_suicide,
    _ep_ta_the_end,
};

enum cep_think_enum   // 2011_03_03, DC: Think types.
{
    _ep_th_common_think,
    _ep_th_player_think,
    _ep_th_steam_think,
    _ep_th_steamer_think,
    _ep_th_text_think,
    _ep_th_trap_think,
    _ep_th_the_end,
};

int mapstrings_animationproperty(ScriptVariant **varlist, int paramCount)
{
    return 0;
//    char *propname;
//    const char *aps;
//    int prop, ap; //int prop, i, ep, t;
//    int result = 1;
//
//    MAPSTRINGS(varlist[1], list_animation_prop, ANI_PROP_THE_END,
//               "Property name '%s' is not a supported animation property.\n");
//
//    if(paramCount < 3 || varlist[1]->vt != VT_INTEGER)
//    {
//        return result;
//    }
//    else
//    {
//        ap = varlist[1]->lVal;
//        aps = (ap < ANI_PROP_THE_END && ap >= 0) ? list_animation_prop[ap] : "";
//    }
//
//    return result;
}

static int obor_script_collision_coordinates(void)
{
    return obor_profile_build >= 4283 && obor_profile_build < 4358;
}

/* Preserve the original ordinal in script values and resolve it at dispatch. */
static const struct { int selector; unsigned introduced; } obor_entity_property_additions[] =
{
    {_ep_binding, 4905},
    {_ep_boomerang, 4405},
    {_ep_custom_target, 4414},
    {_ep_die_on_landing, 4665},
    {_ep_facing, 4306},
    {_ep_jumpmovex, 4303},
    {_ep_jumpmovez, 4303},
    {_ep_jumpspeed, 4327},
    {_ep_numweapons, 4400},
    {_ep_offscreen_noatk_factor, 4405},
    {_ep_offscreenkill, 4404},
    {_ep_subject_to_basemap, 4311},
    {_ep_walkoffmovex, 4303},
    {_ep_walkoffmovez, 4303},
    {_ep_weaploss, 4401},
    {_ep_weapnum, 4400},
};

static LONG obor_profile_subtype_value(int subtype)
{
    if(obor_profile_build >= 4283 && obor_profile_build < 4407 &&
       subtype >= SUBTYPE_TOUCH && subtype <= SUBTYPE_CHASE)
    {
        return subtype - 1;
    }
    return subtype;
}

static int obor_entity_property_uses_history(void)
{
    return obor_profile_build >= 4283 && obor_profile_build < 4665;
}

static int obor_resolve_entity_property(LONG ordinal)
{
    if(ordinal < 0 || ordinal >= _ep_the_end) return -1;
    if(obor_entity_property_uses_history())
    {
        /* The insertions are ordered by their position in the physical table. */
        for(size_t i = 0; i < sizeof(obor_entity_property_additions) / sizeof(*obor_entity_property_additions); ++i)
        {
            if(ordinal >= obor_entity_property_additions[i].selector &&
               obor_profile_build < obor_entity_property_additions[i].introduced)
                ++ordinal;
        }
    }
    else if(obor_profile_build < 4905 && ordinal >= _ep_binding)
    {
        ++ordinal;
    }
    return ordinal < _ep_the_end ? (int)ordinal : -1;
}

static const char *obor_entity_property_name(int selector)
{
    if(selector < 0 || selector >= _ep_the_end) return "";
    if(selector == _ep_boomerang && obor_entity_property_uses_history())
    {
        if(obor_profile_build < 4407) return "boomrangacc";
        if(obor_profile_build < 4408) return "boomrang";
    }
    return eplist[selector];
}

static int obor_map_entity_property_name(ScriptVariant *value)
{
    const char *name;
    int ordinal;
    if(value->vt != VT_STR) return 1;
    name = StrCache_Get(value->strVal);
    if(obor_profile_build < 4905)
    {
        const char *names[_ep_the_end];
        int count = 0;
        size_t addition = 0;
        const size_t additions = sizeof(obor_entity_property_additions) / sizeof(*obor_entity_property_additions);
        for(int selector = 0; selector < _ep_the_end; ++selector)
        {
            if(addition < additions && selector == obor_entity_property_additions[addition].selector)
            {
                const unsigned introduced = obor_entity_property_additions[addition++].introduced;
                if((selector == _ep_binding || obor_entity_property_uses_history()) &&
                   obor_profile_build < introduced) continue;
            }
            names[count++] = obor_entity_property_name(selector);
        }
        /* Preserve the native search even when a historical table is not sorted. */
        ordinal = searchList(names, name, count);
    }
    else
    {
        ordinal = searchList(eplist, name, _ep_the_end);
    }
    if(ordinal < 0)
    {
        printf("Property name '%s' is not supported by function getentityproperty.\n", name);
        return 0;
    }
    ScriptVariant_ChangeType(value, VT_INTEGER);
    value->lVal = ordinal;
    return 1;
}

static int obor_has_simple_animation_action(void)
{
    return obor_profile_build < 4283 || obor_profile_build >= 4409;
}

int mapstrings_entityproperty(ScriptVariant **varlist, int paramCount)
{
    char *propname;
    const char *eps;
    int prop, i, ep, t;

    static const char *proplist_defense[] =
    {
        "blockpower",
        "blockratio",
        "blockthreshold",
        "blocktype",
        "factor",
        "knockdown",
        "pain",
    };

    static const char *proplist_dot[] =
    {
        "force",
        "mode",
        "owner",
        "rate",
        "time",
        "type",
    };

    static const char *proplist_edelay[] =
    {
        "cap_max",
        "cap_min",
        "factor",
        "mode",
        "range_max",
        "range_min",
    };

    static const char *proplist_energycost[] =
    {
        "cost",
        "disable",
        "mponly",
    };

    static const char *proplist_flash[] =
    {
        "block",
        "default",
        "noattack",
    };

    static const char *proplist_icon[] =
    {
        "default",
        "die",
        "get",
        "mphigh",
        "mplow",
        "mpmed",
        "pain",
        "weapon",
        "x",
        "y",
    };

    static const char *proplist_knockdowncount[] =
    {
        "current",
        "max",
        "time",
    };

    static const char *proplist_landframe[] =
    {
        "ent",
        "frame",
    };

    static const char *proplist_maps[] =
    {
        "count",
        "current",
        "default",
        "dying",
        "dying_critical",
        "dying_low",
        "frozen",
        "hide_end",
        "hide_start",
        "ko",
        "kotype",
        "table",
        "time",
    };

    static const char *proplist_range[] =
    {
        "amax",
        "amin",
        "bmax",
        "bmin",
        "xmax",
        "xmin",
        "zmax",
        "zmin",
    };

    static const char *proplist_running[] =
    {
        "jumpx",
        "jumpy",
        "land",
        "movez",
        "speed",
    };

    static const char *proplist_spritea[] =
    {
        "centerx",
        "centery",
        "file",
        "offsetx",
        "offsety",
        "sprite",
    };

    static const char *proplist_staydown[] =
    {
        "rise",
        "riseattack",
        "riseattack_stall",
    };

    static const char *proplist_hostile_candamage[] =
    {
        "ground",
        "type_enemy",
        "type_npc",
        "type_obstacle",
        "type_player",
        "type_shot",
    };

    static const char *proplist_takeaction[] =
    {
        "bomb_explode",
        "common_animation_normal",
        "common_attack_proc",
        "common_block",
        "common_drop",
        "common_fall",
        "common_get",
        "common_grab",
        "common_grabattack",
        "common_grabbed",
        "common_jump",
        "common_land",
        "common_lie",
        "common_pain",
        "common_prejump",
        "common_rise",
        "common_spawn",
        "common_turn",
        "normal_prepare",
        "npc_warp",
        "player_blink",
        "suicide",
    };

    static const char *proplist_think[] =   // 2011_03_03, DC: Think types.
    {
        "common_think",
        "player_think",
        "steam_think",
        "steamer_think",
        "text_think",
        "trap_think",
    };

    if(paramCount < 2)
    {
        return 1;
    }

    // map entity properties
    if(!obor_map_entity_property_name(varlist[1])) return 0;

    if(paramCount < 3 || varlist[1]->vt != VT_INTEGER)
    {
        return 1;
    }

    ep = obor_resolve_entity_property(varlist[1]->lVal);
    eps = obor_entity_property_name(ep);

    switch (ep)
    {
    // deprecation warning for "a" property
    case _ep_a:
    {
        printf("\nNote: Property 'a' has been deprecated. Use 'y' to access the Y (vertical) axis property.\n");
        break;
    }
    // map subproperties of aiflag property
    case _ep_aiflag:
    {
        MAPSTRINGS(varlist[2], eplist_aiflag, _ep_aiflag_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }

    // map subproperties of defense property
    case _ep_defense:
    {
        if(paramCount >= 4 && varlist[3])
        {
            MAPSTRINGS(varlist[3], proplist_defense, _ep_defense_the_end,
                       _is_not_a_known_subproperty_of_, eps);
        }
        break;
    }
    // map subproperties of DOT
    case _ep_dot:
    {
        MAPSTRINGS(varlist[2], proplist_dot, _ep_dot_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Edelay property
    case _ep_edelay:
    {
        MAPSTRINGS(varlist[2], proplist_edelay, _ep_edelay_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Energycost
    case _ep_energycost:
    {
        MAPSTRINGS(varlist[2], proplist_energycost, _ep_energycost_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Flash
    case _ep_flash:
    {
        MAPSTRINGS(varlist[2], proplist_flash, _ep_flash_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Icon
    case _ep_icon:
    {
        MAPSTRINGS(varlist[2], proplist_icon, _ep_icon_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }

    // map subproperties of Knockdowncount
    case _ep_knockdowncount:
    {
        MAPSTRINGS(varlist[2], proplist_knockdowncount, _ep_knockdowncount_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Landframe
    case _ep_landframe:
    {
        MAPSTRINGS(varlist[2], proplist_landframe, _ep_landframe_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Maps
    case  _ep_maps:
    {
        MAPSTRINGS(varlist[2], proplist_maps, _ep_maps_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Range
    case _ep_range:
    {
        MAPSTRINGS(varlist[2], proplist_range, _ep_range_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Running
    case _ep_running:
    {
        MAPSTRINGS(varlist[2], proplist_running, _ep_running_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }

    // map subproperties of Spritea
    case _ep_spritea:
    {
        MAPSTRINGS(varlist[2], proplist_spritea, _ep_spritea_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    // map subproperties of Staydown
    case _ep_staydown:
    {
        MAPSTRINGS(varlist[2], proplist_staydown, _ep_running_the_end,
                   _is_not_a_known_subproperty_of_, eps);
        break;
    }
    //hostile, candamage, projectilehit
    case _ep_hostile:
    case _ep_candamage:
    case _ep_projectilehit:
    {
        for(i = 2; i < paramCount; i++)
        {
            if(!varlist[i]) continue;
            t = varlist[i]->vt;
            MAPSTRINGS(varlist[i], proplist_hostile_candamage, _ep_hcd_the_end,
                       _is_not_supported_by_, eps);

            if(varlist[i]->vt == VT_INTEGER && t == VT_STR)
            {
                varlist[i]->lVal |= 0x80000000;    //flag it
            }
        }
        break;
    }
    // action for takeaction
    case _ep_takeaction:
    {
        if(!obor_has_simple_animation_action() && varlist[2]->vt == VT_STR)
        {
            propname = (char *)StrCache_Get(varlist[2]->strVal);
            prop = searchList(proplist_takeaction, propname, _ep_ta_the_end);
            if(prop < 0 || prop == _ep_ta_common_animation_normal)
            {
                printf(_is_not_supported_by_, propname, eps);
                return 0;
            }
            ScriptVariant_ChangeType(varlist[2], VT_INTEGER);
            varlist[2]->lVal = prop - (prop > _ep_ta_common_animation_normal);
        }
        else
        {
            MAPSTRINGS(varlist[2], proplist_takeaction, _ep_ta_the_end,
                       _is_not_supported_by_, eps);
        }
        break;
    }
    // 2011_03_13, DC: Think sets for think.
    case _ep_think:
    {
        MAPSTRINGS(varlist[2], proplist_think, _ep_th_the_end,
                   _is_not_supported_by_, eps);
        break;
    }
    }

    return 1;
}

// Animation specific properties.
// Caskey, Damon V.
// 2016-10-20
//
// Access animation property by handle (pointer).
//
// set_animation_property(void handle, int property, value)
static int obor_uses_early_animation_properties(void)
{
    return obor_profile_build >= 4283 && obor_profile_build < 4414;
}

static e_animation_properties obor_native_animation_property(LONG property)
{
    if(obor_uses_early_animation_properties() && property >= ANI_PROP_IGNOREATTACKID &&
        property < ANI_PROP_WEAPONFRAME)
    {
        ++property;
    }
    return (e_animation_properties)property;
}

HRESULT openbor_set_animation_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME           "set_animation_property(void handle, int property, value)"
    #define ARG_MINIMUM         3   // Minimum required arguments.
    #define ARG_HANDLE          0   // Handle (pointer to property structure).
    #define ARG_PROPERTY        1   // Property to access.
    #define ARG_VALUE           2   // New value to apply.

    int                     result      = S_OK; // Success or error?
    s_anim                  *handle     = NULL; // Property handle.
    e_animation_properties  property    = 0;    // Property to access.

    // Value carriers to apply on properties after
    // taken from argument.
    int     temp_int;
    //DOUBLE  temp_float;

    // Verify incoming arguments. There must be a
    // pointer for the animation handle, an integer
    // property, and a new value to apply.
    if(paramCount < ARG_MINIMUM
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle      = (s_anim *)varlist[ARG_HANDLE]->ptrVal;
        property    = obor_native_animation_property(varlist[ARG_PROPERTY]->lVal);
    }

    // Which property to modify?
    switch(property)
    {
        case ANI_PROP_ANIMHITS:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->animhits = (int)temp_int;
            }

            break;

        case ANI_PROP_ANTIGRAV:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->antigrav = (int)temp_int;
            }

            break;

        case ANI_PROP_NUMFRAMES:
            if(obor_uses_early_animation_properties())
            {
                goto unsupported_animation_property;
            }
            if(handle && SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
                temp_int > 0 && (size_t)temp_int <= handle->obor_frame_capacity)
            {
                handle->numframes = (int)temp_int;
            }
            break;

        default:
        unsupported_animation_property:

            printf("Unsupported property.\n");
            goto error_local;

            break;
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle and property: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_PROPERTY
    #undef ARG_VALUE
}

// Animation specific properties.
// Caskey, Damon V.
// 2016-10-20
//
// Access animation property by handle (pointer).
//
// get_animation_property(void handle, int frame, int property)
HRESULT openbor_get_animation_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME       "get_animation_property(void handle, int property)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define ARG_HANDLE      0   // Handle (pointer to property structure).
    #define ARG_PROPERTY    1   // Property to access.


    int                     result      = S_OK; // Success or error?
    s_anim                  *handle     = NULL; // Property handle.
    e_animation_properties  property    = 0;    // Property argument.

    // Clear pass by reference argument used to send
    // property data back to calling script.     .
    ScriptVariant_Clear(*pretvar);

    // Verify incoming arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which property is accessed.
    if(paramCount < ARG_MINIMUM
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle      = (s_anim *)varlist[ARG_HANDLE]->ptrVal;
        property    = obor_native_animation_property(varlist[ARG_PROPERTY]->lVal);
    }

    // Which property to get?
    switch(property)
    {
        case ANI_PROP_ANIMHITS:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->animhits;
            break;

        case ANI_PROP_ANTIGRAV:

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)handle->antigrav;
            break;

        case ANI_PROP_ATTACK:

            // Verify animation has attacks.
            if(handle->collision_attack)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = (VOID *)handle->collision_attack;
            }

            break;

        case ANI_PROP_COLLISIONONE:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->attackone;
            break;

        case ANI_PROP_BODY_COLLISION:

            // Verify animation has any bbox.
            if(handle->collision_body)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = (VOID *)handle->collision_body;
            }

            break;

        case ANI_PROP_BOUNCE:

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)handle->bounce;

            break;

        case ANI_PROP_CANCEL:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->cancel;
            break;

        case ANI_PROP_CHARGETIME:

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)handle->chargetime;
            break;

        case ANI_PROP_COUNTERRANGE:

            // Verify animation has item.
            if(handle->counterrange)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = (VOID *)handle->counterrange;
            }

            break;

        case ANI_PROP_NUMFRAMES:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->numframes;
            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;
            break;
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle and property: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_PROPERTY
}



// Attack specific properties.
// Caskey, Damon V.
// 2016-10-20

// get_attack_collection(void handle, int frame)
//
// Get item handle for an animation frame. When
// multiple items per frame support is implemented,
// this will return the collection of items. It is therefore
// imperative this function NOT be used to access a single
// item handle directly. You should instead use
// get<item>instance(), and pass it the result from
// this function.
#include "anybor_attack_query.h"

HRESULT openbor_get_attack_collection(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME       "get_attack_collection(void handle, int frame)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define ARG_HANDLE      0   // Handle (pointer to property structure).
    #define ARG_FRAME       1   // Frame to access.


    int         result      = S_OK;     // Success or error?
    s_collision_attack_list **handle     = NULL;    // Property handle.
    int         frame       = 0;        // Property argument.

    // Clear pass by reference argument used to send
    // property data back to calling script.     .
    if(!pretvar || !*pretvar) return E_FAIL;
    ScriptVariant_Clear(*pretvar);

    // Verify incoming arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which frame is accessed.
    if(paramCount < ARG_MINIMUM
       || !varlist || !varlist[ARG_HANDLE] || !varlist[ARG_FRAME]
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_FRAME]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle  = (s_collision_attack_list **)varlist[ARG_HANDLE]->ptrVal;
        frame   = (LONG)varlist[ARG_FRAME]->lVal;
    }

    if(!obor_attack_frame_is_valid(handle, frame))
    {
        *pretvar = NULL;
        goto error_local;
    }

    // If this frame has property, send value back to user.
    if(handle[frame])
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        s_collision_attack_list *list = handle[frame];
        if(obor_profile_build >= 4283 && obor_profile_build < 4301)
        {
            s_collision_attack *record = list->obor_frame_record;
            if(!record && list->instance && list->obor_instance_capacity)
            {
                record = list->instance[0];
            }
            if(!record)
            {
                ScriptVariant_Clear(*pretvar);
                return result;
            }
            (*pretvar)->ptrVal = record;
        }
        else
        {
            (*pretvar)->ptrVal = list;
        }
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle and frame: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_FRAME
}

// get_attack_instance(void handle, int index)
//
// Get single item handle from item collection.
// As of 2016-10-30, this function is a placeholder and
// simply returns the handle given. It is in place for future
// support of multiple instances per frame.
HRESULT openbor_get_attack_instance(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME       "get_attack_instance(void handle, int index)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define ARG_HANDLE      0   // Handle (pointer to property structure).
    #define ARG_INDEX       1   // Index to access.

    int         result     = S_OK; // Success or error?
    s_collision_attack    *handle    = NULL; // Property handle.
    //int         index      = 0;    // Property argument.

    // Clear pass by reference argument used to send
    // property data back to calling script.     .
    if(!pretvar || !*pretvar) return E_FAIL;
    ScriptVariant_Clear(*pretvar);

    // Verify incoming arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which index is accessed.
    if(paramCount < ARG_MINIMUM
       || !varlist || !varlist[ARG_HANDLE] || !varlist[ARG_INDEX]
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_INDEX]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle  = (s_collision_attack *)varlist[ARG_HANDLE]->ptrVal;
        //index   = (LONG)varlist[ARG_INDEX]->lVal;
    }

    // If this index has property, send value back to user.
    //if(handle[index])
    //{
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        //(*pretvar)->ptrVal = handle[index];

        (*pretvar)->ptrVal = handle;
    //}

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle and index: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_INDEX
}

enum { OBOR_ATTACK_FALL_VELOCITY = ATTACK_PROP_TAG + 1 };

static LONG obor_attack_property_selector(LONG selector)
{
    static const int selectors[] =
    {
        ATTACK_PROP_BLOCK_COST,
        ATTACK_PROP_BLOCK_PENETRATE,
        -1, /* Reserved coordinates selector. */
        ATTACK_PROP_COUNTER,
        ATTACK_PROP_DAMAGE_FORCE,
        ATTACK_PROP_DAMAGE_LAND_FORCE,
        ATTACK_PROP_DAMAGE_LAND_MODE,
        ATTACK_PROP_DAMAGE_LETHAL_DISABLE,
        ATTACK_PROP_DAMAGE_RECURSIVE_FORCE,
        ATTACK_PROP_DAMAGE_RECURSIVE_INDEX,
        ATTACK_PROP_DAMAGE_RECURSIVE_MODE,
        ATTACK_PROP_DAMAGE_RECURSIVE_TIME_RATE,
        ATTACK_PROP_DAMAGE_RECURSIVE_TIME_EXPIRE,
        ATTACK_PROP_DAMAGE_STEAL,
        ATTACK_PROP_DAMAGE_TYPE,
        ATTACK_PROP_EFFECT_BLOCK_FLASH,
        ATTACK_PROP_EFFECT_BLOCK_SOUND,
        ATTACK_PROP_EFFECT_HIT_FLASH,
        ATTACK_PROP_EFFECT_HIT_FLASH_DISABLE,
        ATTACK_PROP_EFFECT_HIT_SOUND,
        ATTACK_PROP_INDEX,
        ATTACK_PROP_GROUND,
        ATTACK_PROP_MAP_INDEX,
        ATTACK_PROP_MAP_TIME,
        ATTACK_PROP_REACTION_FALL_FORCE,
        OBOR_ATTACK_FALL_VELOCITY,
        ATTACK_PROP_REACTION_FREEZE_MODE,
        ATTACK_PROP_REACTION_FREEZE_TIME,
        ATTACK_PROP_REACTION_INVINCIBLE_TIME,
        ATTACK_PROP_REACTION_REPOSITION_DIRECTION,
        ATTACK_PROP_REACTION_REPOSITION_DISTANCE,
        ATTACK_PROP_REACTION_REPOSITION_MODE,
        ATTACK_PROP_REACTION_PAIN_SKIP,
        ATTACK_PROP_REACTION_PAUSE_TIME,
        ATTACK_PROP_SEAL_COST,
        ATTACK_PROP_SEAL_TIME,
        ATTACK_PROP_STAYDOWN_RISE,
        ATTACK_PROP_STAYDOWN_RISEATTACK,
        ATTACK_PROP_TAG
    };

    if(obor_profile_build < 4905) return selector < OBOR_ATTACK_FALL_VELOCITY ? selector : -1;
    return selector >= 0 && (size_t)selector < sizeof(selectors) / sizeof(*selectors)
        ? selectors[selector] : -1;
}

// get_attack_property(void handle, int property)
HRESULT openbor_get_attack_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME       "get_attack_property(void handle, int property)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define OBOR_ATTACK_REQUIRE_HANDLE() \
        do { if(!handle) { *pretvar = NULL; goto error_local; } } while(0)
    #define ARG_HANDLE      0   // Handle (pointer to property structure).
    #define ARG_PROPERTY    1   // Property to access.

    int                     result      = S_OK; // Success or error?
    s_collision_attack                *handle     = NULL; // Property handle.
    LONG                    property    = 0;    // Property argument.

    // Clear pass by reference argument used to send
    // property data back to calling script.     .
    if(!pretvar || !*pretvar) return E_FAIL;
    ScriptVariant_Clear(*pretvar);

    // Verify incoming arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which property is accessed.
    if(paramCount < ARG_MINIMUM
       || !varlist || !varlist[ARG_HANDLE] || !varlist[ARG_PROPERTY]
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle      = (s_collision_attack *)varlist[ARG_HANDLE]->ptrVal;
        property    = obor_attack_property_selector(varlist[ARG_PROPERTY]->lVal);
    }

    // Which property to get?
    switch(property)
    {
        case ATTACK_PROP_BLOCK_COST:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->guardcost;
            break;

        case ATTACK_PROP_BLOCK_PENETRATE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->no_block;
            break;

        case ATTACK_PROP_COUNTER:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->counterattack;
            break;

        case ATTACK_PROP_DAMAGE_FORCE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->attack_force;
            break;

        case ATTACK_PROP_DAMAGE_LAND_FORCE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->damage_on_landing;
            break;

        case ATTACK_PROP_DAMAGE_LAND_MODE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->blast;
            break;

        case ATTACK_PROP_DAMAGE_LETHAL_DISABLE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->no_kill;
            break;

        case ATTACK_PROP_DAMAGE_STEAL:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->steal;
            break;

        case ATTACK_PROP_DAMAGE_TYPE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->attack_type;
            break;

//        case ATTACK_PROP_DAMAGE_RECURSIVE_FORCE:
//
//            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
//            (*pretvar)->lVal = (LONG)handle->dot_force;
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_INDEX:
//
//            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
//            (*pretvar)->lVal = (LONG)handle->dot_index;
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_MODE:
//
//            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
//            (*pretvar)->lVal = (LONG)handle->dot;
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_TIME_EXPIRE:
//
//            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
//            (*pretvar)->lVal = (LONG)handle->dot_time;
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_TIME_RATE:
//
//            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
//            (*pretvar)->lVal = (LONG)handle->dot_rate;
//            break;

        case ATTACK_PROP_EFFECT_BLOCK_FLASH:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->blockflash;
            break;

        case ATTACK_PROP_EFFECT_BLOCK_SOUND:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->blocksound;
            break;

        case ATTACK_PROP_EFFECT_HIT_FLASH:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->hitflash;
            break;

        case ATTACK_PROP_EFFECT_HIT_FLASH_DISABLE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->no_flash;
            break;

        case ATTACK_PROP_EFFECT_HIT_SOUND:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->hitsound;
            break;

        case ATTACK_PROP_GROUND:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->otg;
            break;

        case ATTACK_PROP_MAP_INDEX:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->forcemap;
            break;

        case ATTACK_PROP_MAP_TIME:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->maptime;
            break;

        case ATTACK_PROP_POSITION_X:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->x;
            }
            break;

        case ATTACK_PROP_POSITION_Y:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->y;
            }
            break;

        case ATTACK_PROP_REACTION_FALL_FORCE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->attack_drop;
            break;

        case ATTACK_PROP_REACTION_FALL_VELOCITY_X:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)handle->dropv.x;
            break;

        case ATTACK_PROP_REACTION_FALL_VELOCITY_Y:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)handle->dropv.y;
            break;

        case ATTACK_PROP_REACTION_FALL_VELOCITY_Z:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)handle->dropv.z;
            break;

        case ATTACK_PROP_REACTION_FREEZE_MODE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->freeze;
            break;

        case ATTACK_PROP_REACTION_FREEZE_TIME:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->freezetime;
            break;

        case ATTACK_PROP_REACTION_INVINCIBLE_TIME:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->pain_time;
            break;

        case ATTACK_PROP_REACTION_PAIN_SKIP:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->no_pain;
            break;

        case ATTACK_PROP_REACTION_PAUSE_TIME:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->pause_add;
            break;

        case ATTACK_PROP_REACTION_REPOSITION_DIRECTION:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->force_direction;
            break;

        case ATTACK_PROP_REACTION_REPOSITION_DISTANCE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->grab_distance;
            break;

        case ATTACK_PROP_REACTION_REPOSITION_MODE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->grab;
            break;

        case ATTACK_PROP_SEAL_COST:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->seal;
            break;

        case ATTACK_PROP_SEAL_TIME:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->sealtime;
            break;

        case OBOR_ATTACK_FALL_VELOCITY:
            OBOR_ATTACK_REQUIRE_HANDLE();
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = &handle->dropv;
            break;

        case ATTACK_PROP_SIZE_X:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->width;
            }
            break;

        case ATTACK_PROP_SIZE_Y:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->height;
            }
            break;

        case ATTACK_PROP_SIZE_Z_1:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->z1;
            }
            break;

        case ATTACK_PROP_SIZE_Z_2:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->z2;
            }
            break;

        case ATTACK_PROP_STAYDOWN_RISE:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->staydown.rise;
            break;

        case ATTACK_PROP_STAYDOWN_RISEATTACK:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->staydown.riseattack;
            break;

        case ATTACK_PROP_TAG:
            OBOR_ATTACK_REQUIRE_HANDLE();

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->tag;
            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;
            break;
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle and property: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef OBOR_ATTACK_REQUIRE_HANDLE
    #undef ARG_PROPERTY
}

// set_attack_property(void handle, int property, value)
HRESULT openbor_set_attack_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME           "set_attack_property(void handle, int property, value)"
    #define ARG_MINIMUM         3   // Minimum required arguments.
    #define ARG_HANDLE          0   // Handle (pointer to property structure).
    #define ARG_PROPERTY        1   // Property to access.
    #define ARG_VALUE           2   // New value to apply.

    int                     result      = S_OK; // Success or error?
    s_collision_attack                *handle     = NULL; // Property handle.
    LONG                    property    = 0;    // Property to access.

    // Value carriers to apply on properties after
    // taken from argument.
    int     temp_int;
    DOUBLE  temp_dbl;

    // Verify incoming arguments. There must be a
    // pointer for the animation handle, an integer
    // property, and a new value to apply.
    if(paramCount < ARG_MINIMUM
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle      = (s_collision_attack *)varlist[ARG_HANDLE]->ptrVal;
        property    = obor_attack_property_selector(varlist[ARG_PROPERTY]->lVal);
    }

    // Which property to modify?
    switch(property)
    {
        case ATTACK_PROP_BLOCK_COST:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->guardcost = temp_int;
            }
            break;

        case ATTACK_PROP_BLOCK_PENETRATE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->no_block = temp_int;
            }
            break;

        case ATTACK_PROP_COUNTER:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->counterattack = temp_int;
            }
            break;

        case ATTACK_PROP_DAMAGE_FORCE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->attack_force = temp_int;
            }
            break;

        case ATTACK_PROP_DAMAGE_LAND_FORCE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->damage_on_landing = temp_int;
            }
            break;

        case ATTACK_PROP_DAMAGE_LAND_MODE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->blast = temp_int;
            }
            break;

        case ATTACK_PROP_DAMAGE_LETHAL_DISABLE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->no_kill = temp_int;
            }
            break;

        case ATTACK_PROP_DAMAGE_STEAL:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->steal = temp_int;
            }
            break;

        case ATTACK_PROP_DAMAGE_TYPE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->attack_type = temp_int;
            }
            break;

//        case ATTACK_PROP_DAMAGE_RECURSIVE_FORCE:
//
//            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
//            {
//                handle->dot_force = temp_int;
//            }
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_INDEX:
//
//            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
//            {
//                handle->dot_index = temp_int;
//            }
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_MODE:
//
//            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
//            {
//                handle->dot = temp_int;
//            }
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_TIME_EXPIRE:
//
//            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
//            {
//                handle->dot_time = temp_int;
//            }
//            break;
//
//        case ATTACK_PROP_DAMAGE_RECURSIVE_TIME_RATE:
//
//            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
//            {
//                handle->dot_rate = temp_int;
//            }
//            break;

        case ATTACK_PROP_EFFECT_BLOCK_FLASH:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->blockflash = temp_int;
            }
            break;

        case ATTACK_PROP_EFFECT_BLOCK_SOUND:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->blocksound = temp_int;
            }
            break;

        case ATTACK_PROP_EFFECT_HIT_FLASH:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->hitflash = temp_int;
            }
            break;

        case ATTACK_PROP_EFFECT_HIT_FLASH_DISABLE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->no_flash = temp_int;
            }
            break;

        case ATTACK_PROP_EFFECT_HIT_SOUND:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->hitsound = temp_int;
            }
            break;

        case ATTACK_PROP_GROUND:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->otg = temp_int;
            }
            break;

        case ATTACK_PROP_MAP_INDEX:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->forcemap = temp_int;
            }
            break;

        case ATTACK_PROP_MAP_TIME:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->maptime = temp_int;
            }
            break;

        case ATTACK_PROP_POSITION_X:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->x = temp_int;
            }
            break;

        case ATTACK_PROP_POSITION_Y:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->y = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_FALL_FORCE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->attack_drop = temp_int;
            }

            break;

        case OBOR_ATTACK_FALL_VELOCITY:
            if(handle && varlist[ARG_VALUE] && varlist[ARG_VALUE]->vt == VT_PTR &&
               obor_allocation_contains(varlist[ARG_VALUE]->ptrVal, sizeof(handle->dropv)))
            {
                memmove(&handle->dropv, varlist[ARG_VALUE]->ptrVal, sizeof(handle->dropv));
            }
            break;

        case ATTACK_PROP_REACTION_FALL_VELOCITY_X:

            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[ARG_VALUE], &temp_dbl)))
            {
                handle->dropv.x = temp_dbl;
            }
            break;

        case ATTACK_PROP_REACTION_FALL_VELOCITY_Y:

            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[ARG_VALUE], &temp_dbl)))
            {
                handle->dropv.y = temp_dbl;
            }
            break;

        case ATTACK_PROP_REACTION_FALL_VELOCITY_Z:

            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[ARG_VALUE], &temp_dbl)))
            {
                handle->dropv.y = temp_dbl;
            }
            break;

        case ATTACK_PROP_REACTION_FREEZE_MODE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->freeze = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_FREEZE_TIME:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->freezetime = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_INVINCIBLE_TIME:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->pain_time = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_PAIN_SKIP:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->no_pain = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_PAUSE_TIME:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->pause_add = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_REPOSITION_DIRECTION:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->force_direction = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_REPOSITION_DISTANCE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->grab_distance = temp_int;
            }
            break;

        case ATTACK_PROP_REACTION_REPOSITION_MODE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->grab = temp_int;
            }
            break;

        case ATTACK_PROP_SEAL_COST:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->seal = temp_int;
            }
            break;

        case ATTACK_PROP_SEAL_TIME:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->sealtime = temp_int;
            }
            break;

        case ATTACK_PROP_SIZE_X:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->width = temp_int;
            }
            break;

        case ATTACK_PROP_SIZE_Y:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->height = temp_int;
            }
            break;

        case ATTACK_PROP_SIZE_Z_1:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->z1 = temp_int;
            }
            break;

        case ATTACK_PROP_SIZE_Z_2:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->z2 = temp_int;
            }
            break;

        case ATTACK_PROP_STAYDOWN_RISE:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->staydown.rise = temp_int;
            }
            break;

        case ATTACK_PROP_STAYDOWN_RISEATTACK:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->staydown.riseattack = temp_int;
            }
            break;

        case ATTACK_PROP_TAG:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->tag = temp_int;
            }
            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;
            break;
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle, property, and new value: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_PROPERTY
    #undef ARG_VALUE
}

// Body collision properties.
// Caskey, Damon V.
// 2016-10-31
//
// All body collision functions are identical to
// their attack property counterparts. See the attack
// versions of each for details.

// get_body_collision_collection(void handle, int frame)
static int obor_body_collision_frame_is_valid(const void *table, int frame)
{
    uintptr_t address = (uintptr_t)table;
    const s_anim_list *node;
    if(!table || frame < 0)
    {
        return 0;
    }
    for(node = anim_list; node; node = node->next)
    {
        const s_anim *animation = node->anim;
        uintptr_t start, offset;
        size_t element, slot;
        if(!animation || !animation->collision_body)
        {
            continue;
        }
        start = (uintptr_t)animation->collision_body;
        if(address < start)
        {
            continue;
        }
        element = sizeof(*animation->collision_body);
        offset = address - start;
        slot = offset / element;
        if(offset % element == 0 && slot < animation->obor_frame_capacity &&
           (size_t)frame < animation->obor_frame_capacity - slot)
        {
            return 1;
        }
    }
    return 0;
}

HRESULT openbor_get_body_collision_collection(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME       "get_body_collision_collection(void handle, int frame)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define ARG_HANDLE      0   // Handle (pointer to property structure).
    #define ARG_FRAME       1   // Frame to access.


    int         result      = S_OK; // Success or error?
    s_collision_body_list **handle    = NULL; // Property handle.
    int         frame       = 0;    // Property argument.

    // Clear pass by reference argument used to send
    // property data back to calling script.     .
    if(!pretvar || !*pretvar) return E_FAIL;
    ScriptVariant_Clear(*pretvar);

    // Verify incoming arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which frame is accessed.
    if(paramCount < ARG_MINIMUM
       || !varlist || !varlist[ARG_HANDLE] || !varlist[ARG_FRAME]
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_FRAME]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle  = (s_collision_body_list **)varlist[ARG_HANDLE]->ptrVal;
        frame   = (LONG)varlist[ARG_FRAME]->lVal;
    }

    if(!obor_body_collision_frame_is_valid(handle, frame))
    {
        *pretvar = NULL;
        goto error_local;
    }
    // If this frame has property, send value back to user.
    if(handle[frame])
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        s_collision_body_list *list = handle[frame];
        if(obor_profile_build >= 4283 && obor_profile_build < 4355)
        {
            if(!list->instance || !list->obor_instance_capacity || !list->instance[0])
            {
                ScriptVariant_Clear(*pretvar);
                return result;
            }
            (*pretvar)->ptrVal = list->instance[0];
        }
        else
        {
            (*pretvar)->ptrVal = list;
        }
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle and frame: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_FRAME
}

/* The original frame record has one pointer slot. An instance vector returned
 * from that slot then supports the indices owned by its animation frame. */
static int obor_body_collision_at(const void *handle, LONG index, void **selected)
{
    if(!handle || index < 0) return 0;

    for(const s_anim_list *node = anim_list; node; node = node->next)
    {
        const s_anim *animation = node->anim;
        if(!animation || !animation->collision_body) continue;
        for(size_t frame = 0; frame < animation->obor_frame_capacity; ++frame)
        {
            const s_collision_body_list *list = animation->collision_body[frame];
            if(!list) continue;
            if(handle == list)
            {
                if(index != 0) return 0;
                *selected = list->instance;
                return 1;
            }
            if(handle == list->instance)
            {
                if((size_t)index >= list->obor_instance_capacity) return 0;
                *selected = list->instance[index];
                return 1;
            }
        }
    }
    return 0;
}

// get_body_collision_instance(void handle, int index)
HRESULT openbor_get_body_collision_instance(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;
    ScriptVariant_Clear(*pretvar);

    if(paramCount < 2 || !varlist || !varlist[0] || !varlist[1] ||
       varlist[0]->vt != VT_PTR || varlist[1]->vt != VT_INTEGER)
        goto invalid;

    void *selected = varlist[0]->ptrVal;
    if(obor_profile_build >= 4905)
    {
        if(!obor_body_collision_at(selected, varlist[1]->lVal, &selected))
            goto invalid;
        if(!selected) return S_OK;
    }
    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = selected;
    return S_OK;

invalid:
    *pretvar = NULL;
    printf("You must provide a valid handle and index: "
           "get_body_collision_instance(void handle, int index)\n");
    return E_FAIL;
}

enum { OBOR_BODY_COLLISION_COORDINATES = BODY_COLLISION_PROP_TAG + 1 };

static LONG obor_body_property_selector(LONG selector)
{
    static const int selectors[] = {
        OBOR_BODY_COLLISION_COORDINATES, BODY_COLLISION_PROP_DEFENSE, BODY_COLLISION_PROP_TAG
    };
    if(obor_profile_build < 4905) return selector < OBOR_BODY_COLLISION_COORDINATES ? selector : -1;
    return selector >= 0 && (size_t)selector < sizeof(selectors) / sizeof(*selectors)
        ? selectors[selector] : -1;
}

static int obor_body_coords_is_live(const s_hitbox *coords)
{
    for(const s_anim_list *node = anim_list; node; node = node->next)
    {
        const s_anim *anim = node->anim;
        if(!anim || !anim->collision_body) continue;
        for(size_t frame = 0; frame < anim->obor_frame_capacity; ++frame)
        {
            const s_collision_body_list *list = anim->collision_body[frame];
            if(!list || !list->instance) continue;
            for(size_t slot = 0; slot < list->obor_instance_capacity; ++slot)
            {
                const s_collision_body *body = list->instance[slot];
                if(body && body->obor_owned_coords &&
                   (body->obor_owned_coords == coords || body->coords == coords))
                    return 1;
            }
        }
    }
    return 0;
}

static void obor_body_set_coords(s_collision_body *body, s_hitbox *coords)
{
    if(!body->obor_owned_coords || body->coords == coords ||
       (coords && !obor_body_coords_is_live(coords))) return;
    if(coords && coords != body->obor_owned_coords)
        ++((s_body_hitbox *)coords)->references;
    if(body->coords && body->coords != body->obor_owned_coords)
    {
        s_body_hitbox *old = (s_body_hitbox *)body->coords;
        if(--old->references == 0) free(old);
    }
    body->coords = coords;
}

// get_body_collision_property(void handle, int property)
HRESULT openbor_get_body_collision_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME       "get_body_collision_property(void handle, int property)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define ARG_HANDLE      0   // Handle (pointer to property structure).
    #define ARG_PROPERTY    1   // Property to access.

    int                         result      = S_OK; // Success or error?
    s_collision_body                      *handle     = NULL; // Property handle.
    LONG                        property    = 0;    // Property argument.

    // Clear pass by reference argument used to send
    // property data back to calling script.     .
    if(!pretvar || !*pretvar) return E_FAIL;
    ScriptVariant_Clear(*pretvar);

    // Verify incoming arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which property is accessed.
    if(paramCount < ARG_MINIMUM
       || !varlist || !varlist[ARG_HANDLE] || !varlist[ARG_PROPERTY]
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle      = (s_collision_body *)varlist[ARG_HANDLE]->ptrVal;
        property    = obor_body_property_selector(varlist[ARG_PROPERTY]->lVal);
    }

    if(obor_profile_build >= 4905 && (!handle || !obor_allocation_contains(handle, sizeof(*handle))))
    {
        *pretvar = NULL;
        goto error_local;
    }

    // Which property to get?
    switch(property)
    {
        case OBOR_BODY_COLLISION_COORDINATES:
            if(handle->coords)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = handle->coords;
            }
            break;

        case BODY_COLLISION_PROP_DEFENSE:
            if(obor_profile_build >= 4905 && handle->defense)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = handle->defense;
            }
            break;

        case BODY_COLLISION_PROP_POSITION_X:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->x;
            }
            break;

        case BODY_COLLISION_PROP_POSISTION_Y:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->y;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_X:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->width;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_Y:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->height;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_Z_1:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->z1;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_Z_2:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(obor_script_collision_coordinates() && handle && handle->coords)
            {
                (*pretvar)->lVal = (LONG)handle->coords->z2;
            }
            break;

        case BODY_COLLISION_PROP_TAG:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->tag;
            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;
            break;
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle and property: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_PROPERTY
}

// set_body_collision_property(void handle, int property, value)
HRESULT openbor_set_body_collision_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME           "set_body_collision_property(void handle, int property, value)"
    #define ARG_MINIMUM         3   // Minimum required arguments.
    #define ARG_HANDLE          0   // Handle (pointer to property structure).
    #define ARG_PROPERTY        1   // Property to access.
    #define ARG_VALUE           2   // New value to apply.

    int                         result      = S_OK; // Success or error?
    s_collision_body                      *handle     = NULL; // Property handle.
    LONG                        property    = 0;    // Property to access.


    // Value carriers to apply on properties after
    // taken from argument.
    int         temp_int;
    //s_defense   *temp_defense;

    // Verify incoming arguments. There must be a
    // pointer for the animation handle, an integer
    // property, and a new value to apply.
    if(!pretvar) return E_FAIL;
    if(paramCount < ARG_MINIMUM
       || !varlist || !varlist[ARG_HANDLE] || !varlist[ARG_PROPERTY] || !varlist[ARG_VALUE]
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        handle      = (s_collision_body *)varlist[ARG_HANDLE]->ptrVal;
        property    = obor_body_property_selector(varlist[ARG_PROPERTY]->lVal);
    }

    if(obor_profile_build >= 4905 && (!handle || !obor_allocation_contains(handle, sizeof(*handle))))
    {
        *pretvar = NULL;
        goto error_local;
    }

    // Which property to modify?
    switch(property)
    {
        case OBOR_BODY_COLLISION_COORDINATES:
            if(varlist[ARG_VALUE]->vt == VT_EMPTY)
                obor_body_set_coords(handle, NULL);
            else if(varlist[ARG_VALUE]->vt == VT_PTR)
                obor_body_set_coords(handle, varlist[ARG_VALUE]->ptrVal);
            break;

        case BODY_COLLISION_PROP_DEFENSE:
            if(obor_profile_build >= 4905)
            {
                if(varlist[ARG_VALUE]->vt == VT_EMPTY)
                    handle->defense = NULL;
                else if(varlist[ARG_VALUE]->vt == VT_PTR &&
                        (!varlist[ARG_VALUE]->ptrVal ||
                         obor_allocation_contains(varlist[ARG_VALUE]->ptrVal, sizeof(*handle->defense))))
                    handle->defense = varlist[ARG_VALUE]->ptrVal;
            }
            break;

        case BODY_COLLISION_PROP_POSITION_X:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->x = temp_int;
            }
            break;

        case BODY_COLLISION_PROP_POSISTION_Y:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->y = temp_int;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_X:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->width = temp_int;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_Y:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->height = temp_int;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_Z_1:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->z1 = temp_int;
            }
            break;

        case BODY_COLLISION_PROP_SIZE_Z_2:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)) &&
               obor_script_collision_coordinates() && handle && handle->coords)
            {
                handle->coords->z2 = temp_int;
            }
            break;

        case BODY_COLLISION_PROP_TAG:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->tag = temp_int;
            }
            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;
            break;
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid handle, property, and new value: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_PROPERTY
    #undef ARG_VALUE
}



//getentityproperty(pentity, propname);
extern int sprite_map_max_items;
extern unsigned int sprites_loaded;
#include "anybor_resources.h"

static int obor_script_sprite_name_readable(const char *name, size_t limit)
{
    size_t capacity;
    if(!name || !obor_allocation_query(name, NULL, &capacity)) return 0;
    if(capacity > limit + 1) capacity = limit + 1;
    return memchr(name, 0, capacity) != NULL;
}

static int obor_script_sprite_name_store(char *destination, int key)
{
    const char *source = StrCache_GetIfPresent(key);
    size_t capacity, length;
    if(!source || !destination ||
       !obor_allocation_query(destination, NULL, &capacity)) return 0;
    length = strlen(source);
    if(length >= capacity) return 0;
    memmove(destination, source, length + 1);
    return 1;
}

HRESULT openbor_getentityproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar) return E_FAIL;
    if(paramCount >= 2 && (!*pretvar || !varlist || !varlist[0] || !varlist[1] ||
        (paramCount >= 3 && !varlist[2] &&
         !((varlist[1]->vt == VT_INTEGER &&
            obor_resolve_entity_property(varlist[1]->lVal) == _ep_defense) ||
           (varlist[1]->vt == VT_STR && StrCache_GetIfPresent(varlist[1]->strVal) &&
            !stricmp(StrCache_GetIfPresent(varlist[1]->strVal), "defense"))))))
        { *pretvar = NULL; return E_FAIL; }

    entity *ent			= NULL;
    char *tempstr		= NULL;
    ScriptVariant *arg	= NULL;
    ScriptVariant *arg1	= NULL;
    s_sprite *spr;
    LONG ltemp, ltemp2;
    int i				= 0;
    int propind ;
    int tempint			= 0;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_Clear(*pretvar);
    mapstrings_entityproperty(varlist, paramCount);

    arg = varlist[0];
    if(arg->vt != VT_PTR && arg->vt != VT_EMPTY)
    {
        printf("Function getentityproperty must have a valid entity handle.\n");
        *pretvar = NULL;
        return E_FAIL;
    }
    ent = (entity *)arg->ptrVal; //retrieve the entity
    if(!ent)
    {
        return S_OK;
    }

    arg = varlist[1];
    if(arg->vt != VT_INTEGER)
    {
        printf("Function getentityproperty must have a string property name.\n");
    }

    propind = obor_resolve_entity_property(arg->lVal);

    switch(propind)
    {
    case _ep_a:
    case _ep_y:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->position.y;
        break;
    }
    case _ep_aggression:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.aggression;
        break;
    }
    case _ep_aiattack:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.aiattack;
        break;
    }
    case _ep_aiflag:
    {
        if(paramCount < 3)
        {
            break;
        }
        arg = varlist[2];
        if(arg->vt != VT_INTEGER)
        {
            printf("You must give a string name for aiflag.\n");
            return E_FAIL;
        }
        ltemp = arg->lVal;

        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        switch(ltemp)
        {
        case _ep_aiflag_dead:
            (*pretvar)->lVal = (LONG)ent->dead;
            break;
        case _ep_aiflag_jumpid:
            (*pretvar)->lVal = (LONG)ent->jump.id;
            break;
        case _ep_aiflag_jumping:
            (*pretvar)->lVal = (LONG)ent->jumping;
            break;
        case _ep_aiflag_idling:
            (*pretvar)->lVal = (LONG)ent->idling;
            break;
        case _ep_aiflag_drop:
            (*pretvar)->lVal = (LONG)ent->drop;
            break;
        case _ep_aiflag_attacking:
            (*pretvar)->lVal = (LONG)ent->attacking;
            break;
        case _ep_aiflag_getting:
            (*pretvar)->lVal = (LONG)ent->getting;
            break;
        case _ep_aiflag_turning:
            (*pretvar)->lVal = (LONG)ent->turning;
            break;
        case _ep_aiflag_charging:
            (*pretvar)->lVal = (LONG)ent->charging;
            break;
        case _ep_aiflag_blocking:
            (*pretvar)->lVal = (LONG)ent->blocking;
            break;
        case _ep_aiflag_falling:
            (*pretvar)->lVal = (LONG)ent->falling;
            break;
        case _ep_aiflag_running:
            (*pretvar)->lVal = (LONG)ent->running;
            break;
        case _ep_aiflag_inpain:
            (*pretvar)->lVal = (LONG)ent->inpain;
            break;
        case _ep_aiflag_inbackpain:
            (*pretvar)->lVal = (LONG)ent->inbackpain;
            break;
        case _ep_aiflag_projectile:
            (*pretvar)->lVal = (LONG)ent->projectile;
            break;
        case _ep_aiflag_frozen:
            (*pretvar)->lVal = (LONG)ent->frozen;
            break;
        case _ep_aiflag_toexplode:
            (*pretvar)->lVal = (LONG)ent->toexplode;
            break;
        case _ep_aiflag_animating:
            (*pretvar)->lVal = (LONG)ent->animating;
            break;
        case _ep_aiflag_blink:
            (*pretvar)->lVal = (LONG)ent->blink;
            break;
        case _ep_aiflag_invincible:
            (*pretvar)->lVal = (LONG)ent->invincible;
            break;
        case _ep_aiflag_autokill:
            (*pretvar)->lVal = (LONG)ent->autokill;
            break;
        case _ep_aiflag_idlemode:
            (*pretvar)->lVal = (LONG)ent->idlemode;
            break;
        case _ep_aiflag_walkmode:
            (*pretvar)->lVal = (LONG)ent->walkmode;
            break;
        case _ep_aiflag_walking:
            (*pretvar)->lVal = (LONG)ent->walking;
            break;
        default:
            ScriptVariant_Clear(*pretvar);
            return E_FAIL;
        }
        break;
    }
    case _ep_aimove:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.aimove;
        break;
    }
    case _ep_alpha:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.alpha;
        break;
    }
    case _ep_animal:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.animal;
        break;
    }
    case _ep_animating:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->animating;
        break;
    }
    case _ep_animation_handle:
    {
        #define ARG_ANIMATION_ID 2

        // Did the user provide an animation id?
        if(paramCount > 2)
        {
            arg = varlist[ARG_ANIMATION_ID];

            // If the argument is invalid, use current animation ID instead.
            if(FAILED(ScriptVariant_IntegerValue(arg, &ltemp)))
            {
                ltemp = (LONG)ent->animnum;
            }
        }
        else
        {
            ltemp = (LONG)ent->animnum;
        }

        // If the animation exists, get the handle.
        if(validanim(ent, ltemp))
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->modeldata.animation[ltemp];
        }

        break;

        #undef ARG_ANIMATION_ID
    }
    /*
    case _ep_animationid: See animnum.
    */
    case _ep_animheight:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->animation->size.x;
        break;
    }
    case _ep_animhits:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->animation->animhits;
        break;
    }
    case _ep_animnum:
    case _ep_animationid:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->animnum;
        break;
    }
    case _ep_animpos:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->animpos;
        break;
    }
    case _ep_animvalid:
    {
        ltemp = 0;
        if(paramCount == 3)
        {
            arg = varlist[2];
            if(FAILED(ScriptVariant_IntegerValue(arg, &ltemp)))
            {
                ltemp = (LONG)0;
            }
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)validanim(ent, ltemp);
        break;
    }
    case _ep_antigrab:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.antigrab;
        break;
    }
    case _ep_antigravity:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.antigravity;
        break;
    }
    case _ep_attacking:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->attacking;
        break;
    }
    case _ep_attackid:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->attack_id;
        break;
    }
    case _ep_autokill:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->autokill;
        break;
    }
    case _ep_base:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->base;
        break;
    }
    case _ep_vulnerable:
    {
        if(paramCount == 2)
        {
            i		= ent->animnum;
            tempint	= ent->animpos;
        }
        else if(paramCount < 4
                || !varlist[2] || !varlist[3]
                || varlist[2]->vt != VT_INTEGER
                || varlist[3]->vt != VT_INTEGER)
        {
            printf("\n Error, getentityproperty({ent}, \"vulnerable\", {animation}, {frame}): parameters missing or invalid. \n");
            *pretvar = NULL;
            return E_FAIL;
        }
        else
        {
            i		= varlist[2]->lVal;												//Animation parameter.
            tempint	= varlist[3]->lVal;												//Frame parameter.
        }
        /* AnyBOR: use only declared frames backed by native owned storage. */
        s_anim *selected_animation;
        if(i < 0 || tempint < 0 || !ent->modeldata.animation ||
           i >= ent->modeldata.animation_capacity ||
           (size_t)i >= obor_allocation_size(ent->modeldata.animation) /
                        sizeof(*ent->modeldata.animation)) break;
        selected_animation = ent->modeldata.animation[i];
        if(!selected_animation ||
           obor_allocation_size(selected_animation) < sizeof(*selected_animation) ||
           tempint >= selected_animation->numframes ||
           !selected_animation->vulnerable ||
           (size_t)tempint >= obor_allocation_size(selected_animation->vulnerable) /
                              sizeof(*selected_animation->vulnerable)) break;
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)selected_animation->vulnerable[tempint];
        break;
    }
    case _ep_blink:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->blink;
        break;
    }
    case _ep_blockback:
    {
        if(obor_profile_build >= 4283 && obor_profile_build < 4407)
        {
            if(paramCount >= 3 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
                ent->modeldata.blockback = (int)ltemp;
            break;
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.blockback;
        break;
    }
    case _ep_blockodds:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.blockodds;
        break;
    }
    case _ep_blockpain:
    {
        if(obor_profile_build >= 4283 && obor_profile_build < 4407)
        {
            if(paramCount >= 3 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
                ent->modeldata.blockpain = (int)ltemp;
            break;
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.blockpain;
        break;
    }
    case _ep_boomerang:
    {
        const char *name = obor_entity_property_name(_ep_boomerang);
        if(obor_profile_build >= 4405 && obor_profile_build < 4407)
        {
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)ent->modeldata.boomerang_acc;
            break;
        }
        if(paramCount < 3)
        {
            printf("You must specify a flag value for %s property (0 = acceleration, 1 = distance_x).\n", name);
            *pretvar = NULL;
            return E_FAIL;
        }
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            printf("You must specify a flag value for %s property (0 = acceleration, 1 = distance_x).\n", name);
            *pretvar = NULL;
            return E_FAIL;
        }
        (*pretvar)->dblVal = (DOUBLE)(ltemp == 0 ? ent->modeldata.boomerang_acc : ent->modeldata.boomerang_distx);
        break;
    }
    case _ep_boss:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->boss;
        break;
    }
    case _ep_bounce:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.bounce;
        break;
    }
    case _ep_binding:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)&ent->binding;
        break;
    }
    case _ep_bound:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)ent->binding.ent;
        break;
    }
    case _ep_candamage:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.candamage;
        break;
    }
    case _ep_combostep:
    {
        if(paramCount >= 3)
        {
            if(FAILED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
            {
                *pretvar = NULL;
                return E_FAIL;
            }
        }
        else
        {
            ltemp2 = 0;
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->combostep[(int)ltemp2];
        break;
    }
    case _ep_combotime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->combotime;
        break;
    }
    case _ep_hostile:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.hostile;
        break;
    }
    case _ep_projectilehit:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.projectilehit;
        break;
    }
    case _ep_chargerate:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.chargerate;
        break;
    }
    case _ep_colourmap:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)(ent->colourmap);
        break;
    }
    case _ep_colourtable:
    {
        if(paramCount < 3) break;
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID*)model_get_colourmap(&ent->modeldata,
            (unsigned)varlist[2]->lVal + 1u);
        break;
    }
    case _ep_damage_on_landing:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        if(obor_profile_build >= 4642 && obor_profile_build <= 4905 && paramCount >= 3)
        {
            if(FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp2)) || ltemp2 < 0 || ltemp2 > 1)
            {
                printf("You must specify the index (0 or 1).\n");
                *pretvar = NULL;
                return E_FAIL;
            }
            (*pretvar)->lVal = ltemp2 == 0 ? ent->damage_on_landing : ent->damage_on_landing_type;
        }
        else
        {
            (*pretvar)->lVal = (LONG)ent->damage_on_landing;
        }
        break;
    }
    case _ep_dead:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->dead;
        break;
    }
    case _ep_defaultmodel:
    case _ep_defaultname:
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, ent->defaultmodel->name);
        break;
    }
    case _ep_defense:
    {
        if(paramCount < 3) break; /* No defined original subselector. */
        ltemp = 0;
        if(paramCount >= 3)
        {
            if(FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
            {
                printf("You must specify an attack type for your defense property.\n");
                *pretvar = NULL;
                return E_FAIL;
            }
            ltemp2 = _ep_defense_factor;
        }

        if(paramCount >= 4)
        {
            if(FAILED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
            {
                *pretvar = NULL;
                return E_FAIL;
            }
        }
        if(ltemp < 0 || ltemp >= max_attack_types || !ent->defense) break;
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);

        switch(ltemp2)
        {
        case _ep_defense_factor:
        {
            (*pretvar)->dblVal = (DOUBLE)ent->defense[(int)ltemp].factor;
            break;
        }
        case _ep_defense_blockpower:
        {
            (*pretvar)->dblVal = (DOUBLE)ent->defense[(int)ltemp].blockpower;
            break;
        }
        case _ep_defense_blockratio:
        {
            (*pretvar)->dblVal = (DOUBLE)ent->defense[(int)ltemp].blockratio;
            break;
        }
        case _ep_defense_blockthreshold:
        {
            (*pretvar)->dblVal = (DOUBLE)ent->defense[(int)ltemp].blockthreshold;
            break;
        }
        case _ep_defense_blocktype:
        {
            (*pretvar)->dblVal = (DOUBLE)ent->defense[(int)ltemp].blocktype;
            break;
        }
        case _ep_defense_knockdown:
        {
            (*pretvar)->dblVal = (DOUBLE)ent->defense[(int)ltemp].knockdown;
            break;
        }
        case _ep_defense_pain:
        {
            (*pretvar)->dblVal = (DOUBLE)ent->defense[(int)ltemp].pain;
            break;
        }
        default:
            *pretvar = NULL;
            return E_FAIL;
        }
        break;
    }
    case _ep_destx:
    case _ep_destz:
    {
        if(obor_profile_build < 4283 || obor_profile_build >= 4303)
        {
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        }
        (*pretvar)->dblVal = (DOUBLE)(propind == _ep_destx ? ent->destx : ent->destz);
        break;
    }
    case _ep_detect:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.stealth.detect;
        break;
    }
    case _ep_die_on_landing:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->die_on_landing;
        break;
    }
    case _ep_direction:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->direction;
        break;
    }
    case _ep_dot:
    {
        if(paramCount < 4)
        {
            break;
        }

        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            i = (int)ltemp;
        }

        arg = varlist[3];
        if(arg->vt != VT_INTEGER)
        {
            printf("You must provide a string name for dot subproperty.\n\
	~'time'\n\
	~'mode'\n\
	~'force'\n\
	~'rate'\n\
	~'type'\n\
	~'owner'\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        switch(arg->lVal)
        {
        case _ep_dot_time:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->dot_time[i];
            break;
        }
        case _ep_dot_mode:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->dot[i];
            break;
        }
        case _ep_dot_force:

        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->dot_force[i];
            break;
        }
        case _ep_dot_rate:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->dot_rate[i];
            break;
        }
        case _ep_dot_type:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->dot_atk[i];
            break;
        }
        case _ep_dot_owner:
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->dot_owner[i];
            break;
        }
        break;
        }
    }
    case _ep_dropframe:
    {
        ltemp = 0;
        if(paramCount == 3)
        {
            arg = varlist[2];
            if(FAILED(ScriptVariant_IntegerValue(arg, &ltemp)))
            {
                ltemp = 0;
            }
        }

        if(ltemp < 0 || ltemp >= ent->modeldata.animation_capacity ||
                !ent->modeldata.animation[ltemp])
        {
            break;
        }

        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        if(obor_profile_build >= 4283 && obor_profile_build < 4372)
        {
            (*pretvar)->lVal = -1;
        }

        if(ent->modeldata.animation[ltemp]->dropframe)
        {
            (*pretvar)->lVal = ent->modeldata.animation[ltemp]->dropframe->frame;
        }

        break;
    }
    case _ep_edelay:
    {
        arg = varlist[2];
        if(arg->vt != VT_INTEGER)
        {
            printf("You must provide a string name for edelay subproperty.\n\
	~'cap_max'\n\
	~'cap_min'\n\
	~'factor'\n\
	~'mode'\n\
	~'range_max'\n\
	~'range_min'\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp = arg->lVal;
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        switch(ltemp)
        {
        case _ep_edelay_mode:
        {
            (*pretvar)->lVal = (LONG)ent->modeldata.edelay.mode;
            break;
        }
        case _ep_edelay_factor:
        {
            (*pretvar)->dblVal = (float)ent->modeldata.edelay.factor;
            break;
        }
        case _ep_edelay_cap_min:
        {
            (*pretvar)->lVal = (LONG)ent->modeldata.edelay.cap.min;
            break;
        }
        case _ep_edelay_cap_max:
        {
            (*pretvar)->lVal = (LONG)ent->modeldata.edelay.cap.max;
            break;
        }
        case _ep_edelay_range_min:
        {
            (*pretvar)->lVal = (LONG)ent->modeldata.edelay.range.min;
            break;
        }
        case _ep_edelay_range_max:
        {
            (*pretvar)->lVal = (LONG)ent->modeldata.edelay.range.max;
            break;
        }
        default:
            *pretvar = NULL;
            return E_FAIL;
        }
        break;
    }
    case _ep_energycost:
    {
        if(paramCount < 4)
        {
            break;
        }

        if(varlist[2]->vt != VT_INTEGER)
        {
            printf("You must provide a string name for energycost.\n\
	~'cost'\n\
	~'disable'\n\
	~'mponly'\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp	= varlist[2]->lVal;												//Subproperty.
        i		= varlist[3]->lVal;												//Animation.

        if(!validanim(ent, i))													//Verify animation.
        {
            break;
        }

        switch(ltemp)
        {
        case _ep_energycost_cost:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(ent->modeldata.animation[i]->energycost)
            {
                (*pretvar)->lVal = ent->modeldata.animation[i]->energycost->cost;
            }

            break;
        case _ep_energycost_disable:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(ent->modeldata.animation[i]->energycost)
            {
                (*pretvar)->lVal = ent->modeldata.animation[i]->energycost->disable;
            }
            break;
        case _ep_energycost_mponly:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            if(ent->modeldata.animation[i]->energycost)
            {
                (*pretvar)->lVal = ent->modeldata.animation[i]->energycost->mponly;
            }
            break;
        default:
            *pretvar = NULL;
            return E_FAIL;
        }
        break;
    }
    case _ep_escapecount:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->escapecount;
        break;
    }
    case _ep_escapehits:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.escapehits;
        break;
    }
    case _ep_exists:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->exists;
        break;
    }
    case _ep_facing:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.facing;
        break;
    }
    case _ep_falldie:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.falldie;
        break;
    }
    case _ep_flash:
    {
        arg = varlist[2];
        if(arg->vt != VT_INTEGER)
        {
            printf("You must give a string name for flash property.\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp = arg->lVal;
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        switch(ltemp)
        {
        case _ep_flash_block:
        {
            i = ent->modeldata.bflash;
            break;
        }
        case _ep_flash_def:
        {
            i = ent->modeldata.flash;
            break;
        }
        case _ep_flash_noattack:
        {
            i = ent->modeldata.noatflash;
            break;
        }
        default:
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)i;
        break;
    }
    case _ep_pain_time:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->pain_time;
        break;
    }
    case _ep_freezetime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->freezetime;
        break;
    }
    case _ep_frozen:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->frozen;
        break;
    }
    case _ep_gfxshadow:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.gfxshadow;
        break;
    }
    case _ep_shadowbase:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.shadowbase;
        break;
    }
    case _ep_grabbing:
    {
        if(ent->grabbing) // always return an empty var if it is NULL
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->grabbing;
        }
        break;
    }
    case _ep_grabforce:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.grabforce;
        break;
    }
    case _ep_guardpoints:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.guardpoints.current;
        break;
    }
    case _ep_hasplatforms:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.hasPlatforms;
        break;
    }
    case _ep_health:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->health;
        break;
    }
    case _ep_height:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.size.y;
        break;
    }
    case _ep_hitbyid:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->hit_by_attack_id;
        break;
    }
    case _ep_hitheadplatform:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)ent->hithead;
        break;
    }
    case _ep_landedplatform:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)ent->landed_on_platform;
        break;
    }
    case _ep_hitwall:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->hitwall;
        break;
    }
    case _ep_hmapl:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.maps.hide_start;
        break;
    }
    case _ep_hmapu:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.maps.hide_end;
        break;
    }
    case _ep_icon:
    {
        arg = varlist[2];
        if(arg->vt != VT_INTEGER)
        {
            printf("You must provide a string name for icon subproperty:\n\
	getentityproperty({ent}, 'icon', {subproperty});\n\
	~'default'\n\
	~'die'\n\
	~'get'\n\
	~'mphigh'\n\
	~'mplow'\n\
	~'mpmed'\n\
	~'pain'\n\
	~'weapon'\n\
	~'x'\n\
	~'y'\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp = arg->lVal;
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        switch(ltemp)
        {
        case _ep_icon_def:
        {
            i = ent->modeldata.icon.def;
            break;
        }
        case _ep_icon_die:
        {
            i = ent->modeldata.icon.die;
            break;
        }
        case _ep_icon_get:
        {
            i = ent->modeldata.icon.get;
            break;
        }
        case _ep_icon_mphigh:
        {
            i = ent->modeldata.icon.mphigh;
            break;
        }
        case _ep_icon_mplow:
        {
            i = ent->modeldata.icon.mplow;
            break;
        }
        case _ep_icon_mpmed:
        {
            i = ent->modeldata.icon.mpmed;
            break;
        }
        case _ep_icon_pain:
        {
            i = ent->modeldata.icon.pain;
            break;
        }
        case _ep_icon_weapon:
        {
            i = ent->modeldata.icon.weapon;
            break;
        }
        case _ep_icon_x:
        {
            i = ent->modeldata.icon.position.x;
            break;
        }
        case _ep_icon_y:
        {
            i = ent->modeldata.icon.position.y;
            break;
        }
        default:
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        }

        if (i >= 0)
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            spr = sprite_map[i].node->sprite;
            spr->centerx = sprite_map[i].centerx;
            spr->centery = sprite_map[i].centery;
            (*pretvar)->ptrVal = (VOID *)(spr);
        }
        else
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = -1;
        }
        break;
    }
    case _ep_invincible:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->invincible;
        break;
    }
    case _ep_invinctime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->invinctime;
        break;
    }
    case _ep_jugglepoints:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.jugglepoints.current;
        break;
    }
    case _ep_jumpheight:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.jumpheight;
        break;
    }
    case _ep_jumpmovex:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.jumpmovex;
        break;
    }
    case _ep_jumpmovez:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.jumpmovez;
        break;
    }
    case _ep_jumpspeed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.jumpspeed;
        break;
    }
    case _ep_knockdowncount:
    {
        /*
        2011_04_14, DC: Backward compatability; default to current if subproperty not provided.
        */
        if(paramCount < 3)
        {
            ltemp = _ep_knockdowncount_current;
        }
        else
        {
            arg = varlist[2];

            if(arg->vt != VT_INTEGER)
            {
                printf("You must provide a string name for knockdowncount subproperty:\n\
		getentityproperty({ent}, 'knockdowncount', {subproperty})\n\
		~'current'\n\
		~'max'\n\
		~'time'\n");
                *pretvar = NULL;
                return E_FAIL;
            }

            ltemp = arg->lVal;
        }

        switch(ltemp)
        {
        case _ep_knockdowncount_current:
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)ent->knockdowncount;
            break;
        case _ep_knockdowncount_max:
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)ent->modeldata.knockdowncount;
            break;
        case _ep_knockdowncount_time:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->knockdowncount;
            break;
        default:
            *pretvar = NULL;
            return E_FAIL;
        }
        break;
    }
    case _ep_komap:
    {
        if(paramCount < 2)
        {
            break;
        }

        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.maps.ko;
        break;
    }
    case _ep_landframe:
    {
        if(paramCount < 4)
        {
            break;
        }

        if(varlist[2]->vt != VT_INTEGER
                || varlist[3]->vt != VT_INTEGER)
        {
            printf("\n Error, getentityproperty({ent}, 'landframe', {sub property}, {animation}): {Sub property} or {Animation} parameter is missing or invalid. \n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp	= varlist[2]->lVal;												//Subproperty.
        i		= varlist[3]->lVal;												//Animation.

        if(!validanim(ent, i))													//Verify animation.
        {
            break;
        }

        switch(ltemp)
        {
        case _ep_landframe_ent:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->landframe.ent;
            break;
        case _ep_landframe_frame:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->landframe.frame;
            break;
        default:
            *pretvar = NULL;
            return E_FAIL;
        }
        break;
    }
    case _ep_lifespancountdown:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->lifespancountdown;
        break;
    }
    case _ep_attackthrottle:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.attackthrottle;
        break;
    }
    case _ep_attackthrottletime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.attackthrottletime;
        break;
    }
    case _ep_link:
    {
        if(ent->link) // always return an empty var if it is NULL
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->link;
        }
        break;
    }
    case _ep_map:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)0;
        for(i = 0; i < ent->modeldata.maps_loaded; i++)
        {
            if(ent->colourmap == ent->modeldata.colourmap[i])
            {
                (*pretvar)->lVal = (LONG)(i + 1);
                break;
            }
        }
        break;
    }
    case _ep_mapcount:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)(ent->modeldata.maps_loaded + 1);
        break;
    }
    case _ep_mapdefault:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)(ent->map);
        break;
    }
    case _ep_maps:
    {
        arg = paramCount >= 3 ? varlist[2] : NULL;
        if(!arg || arg->vt != VT_INTEGER)
        {
            printf("You must give a string name for maps property.\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp = arg->lVal;
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        switch(ltemp)
        {
        case _ep_maps_count:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->modeldata.maps_loaded + 1);
            break;
        }

        case _ep_maps_current:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)0;
            for(i = 0; i < ent->modeldata.maps_loaded; i++)
            {
                if(ent->colourmap == ent->modeldata.colourmap[i])
                {
                    (*pretvar)->lVal = (LONG)(i + 1);
                    break;
                }
            }
            break;
        }
        case _ep_maps_dying:
        {
            (*pretvar)->lVal = (LONG)((obor_profile_build >= 4283 && obor_profile_build < 4405) ?
                                     ent->dying : ent->dying2);
            break;
        }
        case _ep_maps_dying_critical:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->per2);
            break;
        }
        case _ep_maps_dying_low:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->per1);
            break;
        }
        case _ep_maps_frozen:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->modeldata.maps.frozen);
            break;
        }
        case _ep_maps_hide_end:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->modeldata.maps.hide_end);
            break;
        }
        case _ep_maps_hide_start:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->modeldata.maps.hide_start);
            break;
        }
        case _ep_maps_ko:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->modeldata.maps.ko);
            break;
        }
        case _ep_maps_kotype:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->modeldata.maps.kotype);
            break;
        }
        case _ep_maps_table:
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)(ent->colourmap);
            break;
        }
        case _ep_maps_time:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)(ent->maptime);
            break;
        }
        default:
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        }
        break;
    }
    case _ep_maxguardpoints:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.guardpoints.max;
        break;
    }
    case _ep_maxhealth:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.health;
        break;
    }
    case _ep_maxjugglepoints:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.jugglepoints.max;
        break;
    }
    case _ep_maxmp:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.mp;
        break;
    }
    case _ep_model:
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, ent->model->name);
        break;
    }
    case _ep_mp:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->mp;
        break;
    }
    case _ep_mpdroprate:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.mpdroprate;
        break;
    }
    case _ep_mprate:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.mprate;
        break;
    }
    case _ep_mpstable:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.mpstable;
        break;
    }
    case _ep_mpstableval:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.mpstableval;
        break;
    }
    case _ep_name:
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, ent->name);
        break;
    }
    case _ep_nextanim:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->nextanim;
        break;
    }
    case _ep_nextmove:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->nextmove;
        break;
    }
    case _ep_nextthink:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->nextthink;
        break;
    }
    case _ep_no_adjust_base:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.no_adjust_base;
        break;
    }
    case _ep_noaicontrol:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->noaicontrol;
        break;
    }
    case _ep_nodieblink:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.nodieblink;
        break;
    }
    case _ep_nodrop:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.nodrop;
        break;
    }
    case _ep_nograb:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->nograb;
        break;
    }
    case _ep_nohithead:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.nohithead;
        break;
    }
    case _ep_nolife:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.nolife;
        break;
    }
    case _ep_nopain:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.nopain;
        break;
    }
    case _ep_offense:
    {
        ltemp = 0;
        if(paramCount >= 3)
        {
            arg = varlist[2];
            if(FAILED(ScriptVariant_IntegerValue(arg, &ltemp)))
            {
                ltemp = (LONG)0;
            }
        }
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->offense_factors[(int)ltemp];
        break;
    }
    case _ep_offscreen_noatk_factor:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.offscreen_noatk_factor;
        break;
    }
    case _ep_offscreenkill:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.offscreenkill;
        break;
    }
    case _ep_opponent:
    {
        if(ent->opponent) // always return an empty var if it is NULL
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->opponent;
        }
        break;
    }
    case _ep_custom_target:
    {
        if(ent->custom_target) // always return an empty var if it is NULL
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->custom_target;
        }
        break;
    }
    case _ep_owner:
    {
        if(ent->owner) // always return an empty var if it is NULL
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->owner;
        }
        break;
    }
    case _ep_parent:
    {
        if(ent->parent) // always return an empty var if it is NULL
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->parent;
        }
        break;
    }
    case _ep_path:
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        tempstr = ent->modeldata.path;

        StrCache_Copy((*pretvar)->strVal, tempstr);
        break;
    }
    case _ep_pathfindstep:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.pathfindstep;
        //printf("%d %s %d\n", ent->sortid, ent->name, ent->playerindex);
        break;
    }
    case _ep_playerindex:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->playerindex;
        //printf("%d %s %d\n", ent->sortid, ent->name, ent->playerindex);
        break;
    }
    case _ep_projectile:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->projectile;
        break;
    }
    case _ep_range:
    {
        if(paramCount < 4)
        {
            break;
        }

        if(varlist[2]->vt != VT_INTEGER
                || varlist[3]->vt != VT_INTEGER)
        {
            printf("\n Error, getentityproperty({ent}, 'range', {sub property}, {animation}): {Sub property} or {Animation} parameter is missing or invalid. \n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp	= varlist[2]->lVal;												//Subproperty.
        i		= varlist[3]->lVal;												//Animation.

        if(!validanim(ent, i))													//Verify animation.
        {
            break;
        }

        switch(ltemp)
        {
        case _ep_range_amax:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.max.y;
            break;
        case _ep_range_amin:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.min.y;
            break;
        case _ep_range_bmax:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.max.base;
            break;
        case _ep_range_bmin:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.min.base;
            break;
        case _ep_range_xmax:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.max.x;
            break;
        case _ep_range_xmin:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.min.x;
            break;
        case _ep_range_zmax:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.max.z;
            break;
        case _ep_range_zmin:
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.animation[i]->range.min.z;
            break;
        default:
            *pretvar = NULL;
            return E_FAIL;
        }
        break;
    }
    case _ep_running:
    {
        if(paramCount < 3)
        {
            break;
        }
        arg = varlist[2];
        if(arg->vt != VT_INTEGER)
        {
            printf("You must give a string name for running property.\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp = arg->lVal;
        switch(ltemp)
        {
        case _ep_running_speed:
        {
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)ent->modeldata.runspeed;
            break;
        }
        case _ep_running_jumpy:
        {
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)ent->modeldata.runjumpheight;
            break;
        }
        case _ep_running_jumpx:
        {
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (DOUBLE)ent->modeldata.runjumpdist;
            break;
        }
        case _ep_running_land:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.runhold;
            break;
        }
        case _ep_running_movez:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.runupdown;
            break;
        }
        }
        break;
    }
    case _ep_rush_count:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->rush.count.current;
        break;
    }
    case _ep_rush_tally:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->rush.count.max;
        break;
    }
    case _ep_rush_time:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->rush.time;
        break;
    }
    case _ep_score:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.score;
        break;
    }
    case _ep_scroll:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.scroll;
        break;
    }
    case _ep_seal:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->seal;
        break;
    }
    case _ep_sealtime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->sealtime;
        break;
    }
    case _ep_setlayer:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.setlayer;
        break;
    }
    case _ep_sortid:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->sortid;
        break;
    }
    case _ep_spawntype:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->spawntype;
        break;
    }
    case _ep_speed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.speed;
        break;
    }
    case _ep_sprite:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        i = ent->animation->sprite[ent->animpos];
        spr = sprite_map[i].node->sprite;
        spr->centerx = sprite_map[i].centerx;
        spr->centery = sprite_map[i].centery;
        (*pretvar)->ptrVal = (VOID *)(spr);
        break;
    }
    case _ep_spritea:
    {
        if(paramCount < 5 || !varlist[2] || !varlist[3] || !varlist[4] ||
           varlist[2]->vt != VT_INTEGER || varlist[3]->vt != VT_INTEGER || varlist[4]->vt != VT_INTEGER ||
           varlist[3]->lVal < 0 || (uint64_t)varlist[3]->lVal > INT_MAX ||
           varlist[4]->lVal < 0 || (uint64_t)varlist[4]->lVal > INT_MAX ||
           !ent->modeldata.animation) break;

        /*
        2011_04_17, DC: Modder can now specify animation and frame to return sprite from.
        To retain backward compatibility, sprite from current animation/frame is returned
        when animation and/or frame parameters are not provided.
        */

        ltemp   = varlist[2]->lVal;
        arg     = varlist[3];
        arg1    = varlist[4];

        /*
        Request from animation or frame that doesn't exist = shutdown.
        Let's be more user friendly then that; return empty so modder can evaluate
        and take action accordingly.*/
        if(!validanim(ent, arg->lVal) || (arg1->lVal >= ent->modeldata.animation[arg->lVal]->numframes))
        {
            break;
        }

        if(!ent->modeldata.animation[arg->lVal]->sprite) break;
        i = ent->modeldata.animation[arg->lVal]->sprite[arg1->lVal];
        if(!sprite_map || i < 0 || i >= sprite_map_max_items || (uint64_t)i >= sprites_loaded) break;

        switch(ltemp)
        {
        case _ep_spritea_centerx:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)sprite_map[i].centerx;
            break;
        }
        case _ep_spritea_centery:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)sprite_map[i].centery;
            break;
        }
        case _ep_spritea_file:
        {
                if(!sprite_map[i].node || !obor_script_sprite_name_readable(sprite_map[i].node->filename, INT_MAX)) break;
            ScriptVariant_ChangeType(*pretvar, VT_STR);
            StrCache_Copy((*pretvar)->strVal, sprite_map[i].node->filename);
            break;
        }
        case _ep_spritea_offsetx:
        {
                if(!sprite_map[i].node || !sprite_map[i].node->sprite) break;
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)sprite_map[i].node->sprite->offsetx;
            break;
        }
        case _ep_spritea_offsety:
        {
                if(!sprite_map[i].node || !sprite_map[i].node->sprite) break;
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)sprite_map[i].node->sprite->offsety;
            break;
        }
        case _ep_spritea_sprite:
        {
                if(!sprite_map[i].node || !sprite_map[i].node->sprite) break;
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            spr = sprite_map[i].node->sprite;
            spr->centerx = sprite_map[i].centery;
            spr->centery = sprite_map[i].centery;
            (*pretvar)->ptrVal = (VOID *)(spr);
            break;
        }
        default:
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        }

        break;

    }
    case _ep_stalltime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->stalltime;
        break;
    }
    case _ep_releasetime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->releasetime;
        break;
    }
    case _ep_stats:
    {
        if(paramCount < 4)
        {
            break;
        }
        arg = varlist[2];
        arg1 = varlist[3];

        if(arg->vt != VT_INTEGER || arg1->vt != VT_INTEGER)
        {
            printf("Incorrect parameters: getentityproperty({ent}, 'stats', {type}, {index}) \n {type}: \n 0 = Model. \n 1 = Entity. \n");
            *pretvar = NULL;
            return E_FAIL;
        }

        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);

        switch(arg->lVal)
        {
        default:
            if (ent->modeldata.stats[arg1->lVal])
            {
                (*pretvar)->dblVal = (DOUBLE)ent->modeldata.stats[arg1->lVal];
            }
            break;
        case 1:
            if (ent->stats[arg1->lVal])
            {
                (*pretvar)->dblVal = (DOUBLE)ent->stats[arg1->lVal];
            }
            break;
        }
        break;
    }
    case _ep_staydown:
    {
        arg = varlist[2];
        if(arg->vt != VT_INTEGER)
        {

            printf("You must provide a string name for staydown property:\n\
	getentityproperty({ent}, 'staydown', {subproperty})\n\
	~'rise'\n\
	~'riseattack'\n\
	~'riseattack_stall' \n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ltemp = arg->lVal;
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        switch(ltemp)
        {
        case _ep_staydown_rise:
        {
            i = ent->staydown.rise;
            break;
        }
        case _ep_staydown_riseattack:
        {
            i = ent->staydown.riseattack;
            break;
        }
        case _ep_staydown_riseattack_stall:
        {
            i = ent->staydown.riseattack_stall;
            break;
        }
        default:
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)i;
        break;
    }
    case _ep_stealth:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.stealth.hide;
        break;
    }
    case _ep_subentity:
    {
        if(ent->subentity) // always return an empty var if it is NULL
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent->subentity;
        }
        break;
    }
    case _ep_subject_to_basemap:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_basemap;
        break;
    }
    case _ep_subject_to_gravity:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_gravity;
        break;
    }
    case _ep_subject_to_hole:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_hole;
        break;
    }
    case _ep_subject_to_maxz:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_maxz;
        break;
    }
    case _ep_subject_to_minz:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_minz;
        break;
    }
    case _ep_subject_to_obstacle:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_obstacle;
        break;
    }
    case _ep_subject_to_platform:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_platform;
        break;
    }
    case _ep_subject_to_screen:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_screen;
        break;
    }
    case _ep_subject_to_wall:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.subject_to_wall;
        break;
    }
    case _ep_subtype:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = obor_profile_subtype_value(ent->modeldata.subtype);
        break;
    }
    case _ep_thold:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.thold;
        break;
    }
    case _ep_throwdamage:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.throwdamage;
        break;
    }
    case _ep_throwdist:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.throwdist;
        break;
    }
    case _ep_throwframewait:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.throwframewait;
        break;
    }
    case _ep_throwheight:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->modeldata.throwheight;
        break;
    }
    case _ep_tosstime:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->toss_time;
        break;
    }
    case _ep_tossv:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->velocity.y;
        break;
    }
    case _ep_type:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.type;
        break;
    }
    case _ep_walkoffmovex:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.walkoffmovex;
        break;
    }
    case _ep_walkoffmovez:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.walkoffmovez;
        break;
    }
    case _ep_weapent:
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)ent->weapent;
        break;
    }
    case _ep_numweapons:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.numweapons;
        break;
    }
    case _ep_weapnum:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)ent->modeldata.weapnum;
        break;
    }
    case _ep_weaploss:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        if(paramCount >= 3)
        {
            if(FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
            {
                printf("You must specify the flag value.\n");
                *pretvar = NULL;
                return E_FAIL;
            }

            if (ltemp == 0) (*pretvar)->lVal = (LONG)ent->modeldata.weaploss[0];
            else (*pretvar)->lVal = (LONG)ent->modeldata.weaploss[1];
        }
        else (*pretvar)->lVal = (LONG)ent->modeldata.weaploss[0];

        break;
    }
    case _ep_x:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->position.x;
        break;
    }
    case _ep_xdir:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->velocity.x;
        break;
    }
    case _ep_z:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->position.z;
        break;
    }
    case _ep_zdir:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)ent->velocity.z;
        break;
    }
    default:
        //printf("Property name '%s' is not supported by function getentityproperty.\n", propname);
        *pretvar = NULL;
        return E_FAIL;
        break;
    }

    return S_OK;
}


static s_energycost *obor_script_animation_energycost(s_anim *animation)
{
    if(!animation->energycost && obor_profile_build >= 4283 &&
            (obor_profile_build < 4374 || obor_profile_build == 4375))
    {
        animation->energycost = calloc(1, sizeof(*animation->energycost));
    }
    return animation->energycost;
}


//changeentityproperty(pentity, propname, value1[ ,value2, value3, ...]);
HRESULT openbor_changeentityproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar) return E_FAIL;
    if(paramCount >= 3 && (!varlist || !varlist[0] || !varlist[1] || !varlist[2]))
    { *pretvar = NULL; return E_FAIL; }

    entity *ent = NULL;
    s_model *tempmodel ;
    char *tempstr = NULL;
    LONG ltemp, ltemp2;
    DOUBLE dbltemp;
    int propind;
    int i = 0;

    static const void *actions[] =   // for takeaction
    {
        bomb_explode,
        common_animation_normal,
        common_attack_proc,
        common_block,
        common_drop,
        common_fall,
        common_get,
        common_grab,
        common_grabattack,
        common_grabbed,
        common_jump,
        common_land,
        common_lie,
        common_pain,
        common_prejump,
        common_rise,
        common_spawn,
        common_turn,
        normal_prepare,
        npc_warp,
        player_blink,
        suicide,
    };

    static const int entitytypes[] =
    {
        0, // "ground"; not a real entity type
        TYPE_ENEMY,
        TYPE_NPC,
        TYPE_OBSTACLE,
        TYPE_PLAYER,
        TYPE_SHOT,

    };

    static const void *think[] =   // 2011_03_03, DC: Think types.
    {
        common_think,
        player_think,
        steam_think,
        steamer_think,
        text_think,
        trap_think,
    };

    *pretvar = NULL;

    if(paramCount < 3)
    {
        printf("Function changeentityproperty must have have at least 3 parameters.");
        goto changeentityproperty_error;
    }

    mapstrings_entityproperty(varlist, paramCount);

    if(varlist[0]->vt != VT_PTR && varlist[0]->vt != VT_EMPTY)
    {
        printf("Function changeentityproperty must have a valid entity handle.");
        goto changeentityproperty_error;
    }
    ent = (entity *)varlist[0]->ptrVal; //retrieve the entity
    if(!ent)
    {
        return S_OK;
    }

    if(varlist[1]->vt != VT_INTEGER)
    {
        if(varlist[1]->vt != VT_STR)
        {
            printf("Function changeentityproperty must have a string property name.\n");
        }
        goto changeentityproperty_error;
    }

    propind = obor_resolve_entity_property(varlist[1]->lVal);

    switch(propind)
    {
    case _ep_aggression:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.aggression = (int)ltemp;
        }
        break;
    }
    case _ep_aiattack:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.aiattack = (int)ltemp;
        }
        break;
    }
    case _ep_aiflag:
    {
        if(varlist[2]->vt != VT_INTEGER)
        {
            if(varlist[2]->vt != VT_STR)
            {
                printf("You must give a string value for AI flag name.\n");
            }
            goto changeentityproperty_error;
        }
        if(paramCount < 4)
        {
            break;
        }

        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            switch(varlist[2]->lVal)
            {
            case _ep_aiflag_dead:
                ent->dead = (int)ltemp;
                break;
            case _ep_aiflag_jumpid:
                ent->jump.id = (int)ltemp;
                break;
            case _ep_aiflag_jumping:
                ent->jumping = (int)ltemp;
                break;
            case _ep_aiflag_idling:
                ent->idling = (int)ltemp;
                break;
            case _ep_aiflag_drop:
                ent->drop = (int)ltemp;
                break;
            case _ep_aiflag_attacking:
                ent->attacking = (int)ltemp;
                break;
            case _ep_aiflag_getting:
                ent->getting = (int)ltemp;
                break;
            case _ep_aiflag_turning:
                ent->turning = (int)ltemp;
                break;
            case _ep_aiflag_charging:
                ent->charging = (int)ltemp;
                break;
            case _ep_aiflag_blocking:
                ent->blocking = (int)ltemp;
                break;
            case _ep_aiflag_falling:
                ent->falling = (int)ltemp;
                break;
            case _ep_aiflag_running:
                ent->running = (int)ltemp;
                break;
            case _ep_aiflag_inpain:
                ent->inpain = (int)ltemp;
                break;
            case _ep_aiflag_inbackpain:
                ent->inbackpain = (int)ltemp;
                break;
            case _ep_aiflag_projectile:
                ent->projectile = (int)ltemp;
                break;
            case _ep_aiflag_frozen:
                ent->frozen = (int)ltemp;
                break;
            case _ep_aiflag_toexplode:
                ent->toexplode = (int)ltemp;
                break;
            case _ep_aiflag_animating:
                ent->animating = (int)ltemp;
                break;
            case _ep_aiflag_blink:
                ent->blink = (int)ltemp;
                break;
            case _ep_aiflag_invincible:
                ent->invincible = (int)ltemp;
                break;
            case _ep_aiflag_autokill:
                ent->autokill = (int)ltemp;
                break;
            case _ep_aiflag_idlemode:
                ent->idlemode = (int)ltemp;
                break;
            case _ep_aiflag_walkmode:
                ent->walkmode = (int)ltemp;
                break;
            case _ep_aiflag_walking:
                ent->walking = (int)ltemp;
                break;
            default:
                printf("Unknown AI flag.\n");
                goto changeentityproperty_error;
            }
        }
        break;
    }
    case _ep_aimove:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.aimove = (int)ltemp;
        }
        break;
    }
    case _ep_alpha:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.alpha = (int)ltemp;
        }
        break;
    }
    case _ep_animation:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ltemp2 = (LONG)1;
            if(paramCount < 4 || SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
            {
                ent_set_anim(ent, (int)ltemp, (int)ltemp2);
            }
        }
        break;
    }
    case _ep_animhits:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->animation->animhits = (int)ltemp;
        }
        break;
    }
    case _ep_animpos:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->animpos = (int)ltemp;
        }
        break;
    }
    case _ep_antigrab:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.antigrab = (int)ltemp;
        }
        break;
    }
    case _ep_antigravity:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.antigravity = (float)dbltemp;
        }
        break;
    }

    case _ep_attacking:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->attacking = (int)ltemp;
        }
        break;
    }
    case _ep_attackid:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->attack_id = (int)ltemp;
        }
        break;
    }
    case _ep_autokill:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->autokill = (int)ltemp;
        }
        break;
    }
    case _ep_base:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->base = (float)dbltemp;
        }
        break;
    }
    case _ep_blink:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->blink = (int)ltemp;
        }
        break;
    }
    case _ep_blockback:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.blockback = (int)ltemp;
        }
        break;
    }
    case _ep_blockodds:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.blockodds = (int)ltemp;
        }
        break;
    }
    case _ep_blockpain:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.blockpain = (int)ltemp;
        }
        break;
    }
    case _ep_boomerang:
    {
        const char *name = obor_entity_property_name(_ep_boomerang);
        if(obor_profile_build >= 4405 && obor_profile_build < 4407)
        {
            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
                ent->modeldata.boomerang_acc = (float)dbltemp;
            break;
        }
        DOUBLE distance;
        if(paramCount < 4 || FAILED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)) ||
           FAILED(ScriptVariant_DecimalValue(varlist[3], &distance)))
        {
            printf("You must specify 2 float values to change %s property (acceleration anddistance_x).\n", name);
            *pretvar = NULL;
            return E_FAIL;
        }
        ent->modeldata.boomerang_acc = (float)dbltemp;
        ent->modeldata.boomerang_distx = (float)distance;
        break;
    }
    case _ep_boss:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->boss = (int)ltemp;
        }
        break;
    }
    case _ep_bounce:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.bounce = (int)ltemp;
        }
        break;
    }
    case _ep_candamage:
    {
        ent->modeldata.candamage = 0;

        for(i = 2; i < paramCount; i++)
        {
            if(varlist[i] && varlist[i]->vt == VT_INTEGER) // known entity type
            {
                ltemp = varlist[i]->lVal;
                /* AnyBOR: validate collision selector extent. */
                if((ltemp & 0x80000000) && (unsigned int)(ltemp & 0x7fffffff) >= sizeof(entitytypes) / sizeof(*entitytypes))
                {
                    printf("You must pass one or more string constants for candamage entity type.\n");
                    goto changeentityproperty_error;
                }
                /* AnyBOR: native collision value follows. */

                if(ltemp == (_ep_hcd_ground | 0x80000000)) // "ground" - not needed?
                {
                    ent->modeldata.ground = 1;
                }
                else if(ltemp & 0x80000000)
                {
                    ent->modeldata.candamage |= entitytypes[ltemp & 0x7fffffff];
                }
                else
                {
                    ent->modeldata.candamage |= ltemp;
                }
            }
            else
            {
                printf("You must pass one or more string constants for candamage entity type.\n");
                goto changeentityproperty_error;
            }
        }
        break;
    }
    case _ep_combostep:
    {
        if(paramCount >= 4 &&
                SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) &&
                SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
        {
            ent->combostep[(int)ltemp] = (int)ltemp2;
        }
        break;
    }
    case _ep_combotime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->combotime = (int)ltemp;
        }
        break;
    }
    case _ep_colourmap:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->colourmap = (VOID *)model_get_colourmap(&(ent->modeldata), ltemp);
        }
        break;
    }
    case _ep_damage_on_landing:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->damage_on_landing = (int)ltemp;
        }
        if(obor_profile_build >= 4642 && obor_profile_build <= 4905 && paramCount >= 4 &&
           SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
        {
            if(ltemp2 == 0)
            {
                ent->damage_on_landing = 0;
            }
            else if(ltemp2 == 1)
            {
                ent->damage_on_landing_type = 1;
            }
        }
        break;
    }
    case _ep_dead:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->dead = (int)ltemp;
        }
        break;
    }
    case _ep_defaultname:
    {
        if(varlist[2]->vt != VT_STR)
        {
            printf("You must give a string value for entity name.\n");
            goto changeentityproperty_error;
        }
        tempmodel = findmodel((char *)StrCache_Get(varlist[2]->strVal));
        if(!tempmodel)
        {
            printf("Use must give an existing model's name for entity's default model name.\n");
            goto changeentityproperty_error;
        }
        ent->defaultmodel = tempmodel;
        break;
    }
    case _ep_defense:
    {
        if((ltemp2 =
                    (paramCount >= 4 &&
                     SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) &&
                     ltemp < (LONG)MAX_ATKS && ltemp >= (LONG)0 &&
                     SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
           ))
        {
            ent->defense[(int)ltemp].factor = (float)dbltemp;
        }

        if(paramCount >= 5 && ltemp2 && (ltemp2 = SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp))))
        {
            ent->defense[(int)ltemp].pain = (float)dbltemp;
        }
        if(paramCount >= 6 && ltemp2 && (ltemp2 = SUCCEEDED(ScriptVariant_DecimalValue(varlist[5], &dbltemp))))
        {
            ent->defense[(int)ltemp].knockdown = (float)dbltemp;
        }
        if(paramCount >= 7 && ltemp2 && (ltemp2 = SUCCEEDED(ScriptVariant_DecimalValue(varlist[6], &dbltemp))))
        {
            ent->defense[(int)ltemp].blockpower = (float)dbltemp;
        }
        if(paramCount >= 8 && ltemp2 && (ltemp2 = SUCCEEDED(ScriptVariant_DecimalValue(varlist[7], &dbltemp))))
        {
            ent->defense[(int)ltemp].blockthreshold = (float)dbltemp;
        }
        if(paramCount >= 9 && ltemp2 && (ltemp2 = SUCCEEDED(ScriptVariant_DecimalValue(varlist[8], &dbltemp))))
        {
            ent->defense[(int)ltemp].blockratio = (float)dbltemp;
        }
        if(paramCount >= 10 && ltemp2 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[9], &dbltemp)))
        {
            ent->defense[(int)ltemp].blocktype = dbltemp;
        }

        break;
    }
    case _ep_destx:
    case _ep_destz:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            float *destination = propind == _ep_destx ? &ent->destx : &ent->destz;
            if(obor_profile_build >= 4283 && obor_profile_build < 4303)
            {
                if(dbltemp > (double)INT_MIN - 1.0 && dbltemp < (double)INT_MAX + 1.0)
                {
                    *destination = (int)dbltemp;
                }
            }
            else
            {
                *destination = (float)dbltemp;
            }
        }
        break;
    }
    case _ep_detect:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.stealth.detect = (int)ltemp;
        }
        break;
    }
    case _ep_direction:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->direction = (int)dbltemp;
        }
        break;
    }
    case _ep_dot:
    {
        if((SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp))))
        {
            i = (int)ltemp;
            if(paramCount >= 4 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
            {
                ent->dot_time[i] = (int)dbltemp;
            }
            if(paramCount >= 5 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp)))
            {
                ent->dot[i] = (int)dbltemp;
            }
            if(paramCount >= 6 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[5], &dbltemp)))
            {
                ent->dot_force[i] = (int)dbltemp;
            }
            if(paramCount >= 7 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[6], &dbltemp)))
            {
                ent->dot_rate[i] = (int)dbltemp;
            }
            if(paramCount >= 8 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[7], &dbltemp)))
            {
                ent->dot_atk[i] = (int)dbltemp;
            }
            if(paramCount >= 9)
            {
                ent->dot_owner[i] = (entity *)varlist[8]->ptrVal;
            }
        }
        break;
    }
    case _ep_edelay:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.edelay.mode = (int)ltemp;
        }
        if(paramCount >= 3 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            ent->modeldata.edelay.factor = (float)dbltemp;
        }
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[4], &ltemp)))
        {
            ent->modeldata.edelay.cap.min = (int)ltemp;
        }
        if(paramCount >= 5 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[5], &ltemp)))
        {
            ent->modeldata.edelay.cap.max = (int)ltemp;
        }
        if(paramCount >= 6 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[6], &ltemp)))
        {
            ent->modeldata.edelay.range.min = (int)ltemp;
        }
        if(paramCount >= 7 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[7], &ltemp)))
        {
            ent->modeldata.edelay.range.max = (int)ltemp;
        }

        break;
    }
    case _ep_energycost:
    {
        if(paramCount != 5)
        {
            printf("\n Error, changeentityproperty({ent}, 'energycost', {subproperty}, {animation}, {value}): Invalid or missing parameter. \n");
            goto changeentityproperty_error;
        }

        if(FAILED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            printf("\n Error, changeentityproperty has invalid animation id.\n");
            goto changeentityproperty_error;
        }

        i = (int)ltemp;

        if(!validanim(ent, i))
        {
            printf("\n Error, changeentityproperty({ent}, 'energycost', {subproperty}, {animation}, {value}): {animation} parameter invalid. Make sure the animation exists. \n");
            goto changeentityproperty_error;
        }

        if(varlist[2]->vt != VT_INTEGER)
        {
            printf("You must give a string value for energycost flag name.\n");
            goto changeentityproperty_error;
        }

        switch(varlist[2]->lVal)
        {
        case _ep_energycost_cost:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[4], &ltemp)))
            {
                s_energycost *cost = obor_script_animation_energycost(ent->modeldata.animation[i]);
                if(cost)
                {
                    cost->cost = ltemp;
                }

            }
            break;
        }
        case _ep_energycost_disable:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[4], &ltemp)))
            {
                s_energycost *cost = obor_script_animation_energycost(ent->modeldata.animation[i]);
                if(cost)
                {
                    cost->disable = ltemp;
                }
            }
            break;
        }
        case _ep_energycost_mponly:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[4], &ltemp)))
            {
                s_energycost *cost = obor_script_animation_energycost(ent->modeldata.animation[i]);
                if(cost)
                {
                    cost->mponly = ltemp;
                }
            }
            break;
        }
        default:
            printf("Unknown Energycost flag.\n");
            goto changeentityproperty_error;
        }
        break;
    }
    case _ep_escapecount:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->escapecount = (int)ltemp;
        }
        break;
    }
    case _ep_escapehits:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.escapehits = (int)ltemp;
        }
        break;
    }
    case _ep_facing:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.facing = (int)ltemp;
        }
        break;
    }
    case _ep_falldie:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.falldie = (int)ltemp;
        }
        break;
    }
    case _ep_playerindex:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->playerindex = (int)ltemp;
        }
        break;
    }
    case _ep_pain_time:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->pain_time = (int)ltemp;
        }
        break;
    }
    case _ep_freezetime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->freezetime = (int)ltemp;
        }
        break;
    }
    case _ep_frozen:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->frozen = (int)ltemp;
        }
        break;
    }
    case _ep_gfxshadow:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.gfxshadow = (int)ltemp;
        }
        break;
    }
    case _ep_shadowbase:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.shadowbase = (int)ltemp;
        }
        break;
    }
    case _ep_grabforce:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.grabforce = (int)ltemp;
        }
        break;
    }
    case _ep_guardpoints:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.guardpoints.current = (int)ltemp;
        }
        break;
    }
    case _ep_hasplatforms:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.hasPlatforms = (int)ltemp;
        }
        break;
    }
    case _ep_health:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->health = (int)ltemp;
            if(ent->health > ent->modeldata.health)
            {
                ent->health = ent->modeldata.health;
            }
            else if(ent->health < 0)
            {
                ent->health = 0;
            }
        }
        break;
    }
    case _ep_hitbyid:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->hit_by_attack_id = (int)ltemp;
        }
        break;
    }
    case _ep_hitheadplatform:
    {
        ent->hithead = (entity *)varlist[2]->ptrVal;
        break;
    }
    case _ep_landedplatform:
    {
        ent->landed_on_platform = (entity *)varlist[2]->ptrVal;
        break;
    }
    case _ep_hitwall:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->hitwall = (int)ltemp;
        }
        break;
    }
    case _ep_hmapl:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.maps.hide_start = ltemp;
        }
        break;
    }
    case _ep_hmapu:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.maps.hide_end = ltemp;
        }
        break;
    }
    case _ep_hostile:
    {
        ent->modeldata.hostile = 0;
        for(i = 2; i < paramCount; i++)
        {
            if(varlist[i] && varlist[i]->vt == VT_INTEGER) // known entity type
            {
                ltemp = varlist[i]->lVal;
                /* AnyBOR: validate collision selector extent. */
                if((ltemp & 0x80000000) && (unsigned int)(ltemp & 0x7fffffff) >= sizeof(entitytypes) / sizeof(*entitytypes))
                {
                    printf("You must pass one or more string constants for hostile entity type.\n");
                    goto changeentityproperty_error;
                }
                /* AnyBOR: native collision value follows. */

                if(ltemp & 0x80000000)
                {
                    ent->modeldata.hostile |= entitytypes[ltemp & 0x7fffffff];
                }
                else
                {
                    ent->modeldata.hostile |= ltemp;
                }
            }
            else
            {
                printf("You must pass one or more string constants for hostile entity type.\n");
                goto changeentityproperty_error;
            }
        }

        break;
    }
    case _ep_iconposition:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.icon.position.x = (int)ltemp;
        }
        if(paramCount > 3 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            ent->modeldata.icon.position.y = (int)ltemp;
        }
        break;
    }
    case _ep_invincible:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->invincible = (int)ltemp;
        }
        break;
    }
    case _ep_invinctime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->invinctime = (int)ltemp;
        }
        break;
    }
    case _ep_jugglepoints:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.jugglepoints.current = (int)ltemp;
        }
        break;
    }
    case _ep_jumpheight:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.jumpheight = (float)dbltemp;
        }
        break;
    }
    case _ep_jumpmovex:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.jumpmovex = (int)ltemp;
        }
        break;
    }
    case _ep_jumpmovez:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.jumpmovex = (int)ltemp;
        }
        break;
    }
    case _ep_jumpspeed:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.jumpspeed = (float)dbltemp;
        }
        break;
    }
    case _ep_knockdowncount:
    {
        if(varlist[2]->vt != VT_INTEGER)
        {
            if(varlist[2]->vt != VT_STR)
                printf("You must provide a string value for Knockdowncount subproperty:\n\
                    changeentityproperty({ent}, 'knockdowncount', {subproperty}, {value})\n\
                    ~'current'\n\
                    ~'max'\n\
                    ~'time'\n");
            goto changeentityproperty_error;
        }

        switch(varlist[2]->lVal)
        {
        case _ep_knockdowncount_current:
        {
            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
            {
                ent->knockdowncount = (float)dbltemp;
            }
            break;
        }
        case _ep_knockdowncount_max:
        {
            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
            {
                ent->modeldata.knockdowncount = (float)dbltemp;
            }
            break;
            case _ep_knockdowncount_time:
                if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
                {
                    ent->knockdowntime = (int)ltemp;
                }
                break;
            }
        default:
            printf("Unknown knockdowncount subproperty.\n");
            goto changeentityproperty_error;
        }
        break;
    }
    case _ep_komap:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.maps.ko = (int)ltemp;
        }
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            ent->modeldata.maps.kotype = (int)ltemp;
        }
        break;
    }
    case _ep_lifeposition:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.hpx = (int)ltemp;
        }
        if(paramCount > 3 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            ent->modeldata.hpy = (int)ltemp;
        }
        break;
    }
    case _ep_lifespancountdown:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->lifespancountdown = (int)ltemp;
        }
        break;
    }
    case _ep_attackthrottle:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.attackthrottle = (float)dbltemp;
        }
        break;
    }
    case _ep_attackthrottletime:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.attackthrottletime = (float)dbltemp;
        }
        break;
    }
    case _ep_map:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent_set_colourmap(ent, (int)ltemp);
        }
        break;
    }
    case _ep_maptime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->maptime = (int)ltemp;
        }
        break;
    }
    case _ep_maxguardpoints:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.guardpoints.max = (int)ltemp;
        }
        break;
    }
    case _ep_maxhealth:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.health = (int)ltemp;
            if(ent->modeldata.health < 0)
            {
                ent->modeldata.health = 0;    //OK, no need to have ot below 0
            }
        }
        break;
    }
    case _ep_maxjugglepoints:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.jugglepoints.max = (int)ltemp;
        }
        break;
    }
    case _ep_maxmp:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.mp = (int)ltemp;
            if(ent->modeldata.mp < 0)
            {
                ent->modeldata.mp = 0;    //OK, no need to have ot below 0
            }
        }
        break;
    }
    case _ep_model:
    {
        if(varlist[2]->vt != VT_STR)
        {
            printf("You must give a string value for model name.\n");
            goto changeentityproperty_error;
        }
        tempstr = (char *)StrCache_Get(varlist[2]->strVal);
        if(paramCount > 3 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            set_model_ex(ent, tempstr, -1, NULL, (int)ltemp);
            if(!ent->weapent)
            {
                ent->weapent = ent;
            }
        }
        break;
    }
    case _ep_mp:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->mp = (int)ltemp;
            if(ent->mp > ent->modeldata.mp)
            {
                ent->mp = ent->modeldata.mp;
            }
            else if(ent->mp < 0)
            {
                ent->mp = 0;
            }
        }
        break;
    }
    case _ep_mpset:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.mp = (int)dbltemp;
        }
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            ent->modeldata.mpstable = (int)dbltemp;
        }
        if(paramCount >= 5 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp)))
        {
            ent->modeldata.mpstableval = (int)dbltemp;
        }
        if(paramCount >= 6 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[5], &dbltemp)))
        {
            ent->modeldata.mprate = (int)dbltemp;
        }
        if(paramCount >= 7 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[6], &dbltemp)))
        {
            ent->modeldata.mpdroprate = (int)dbltemp;
        }
        if(paramCount >= 8 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[7], &dbltemp)))
        {
            ent->modeldata.chargerate = (int)dbltemp;
        }
        break;
    }
    case _ep_name:
    {
        if(varlist[2]->vt != VT_STR)
        {
            printf("You must give a string value for entity name.\n");
            goto changeentityproperty_error;
        }
        obor_profile_copy_name(ent->name, StrCache_Get(varlist[2]->strVal));
        break;
    }
    case _ep_nameposition:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.namex = (int)ltemp;
        }
        if(paramCount > 3 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            ent->modeldata.namey = (int)ltemp;
        }
        break;
    }
    case _ep_nextanim:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->nextanim = (int)ltemp;
        }
        break;
    }
    case _ep_nextmove:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->nextmove = (int)ltemp;
        }
        break;
    }
    case _ep_nextthink:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->nextthink = (int)ltemp;
        }
        break;
    }
    case _ep_no_adjust_base:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.no_adjust_base = (int)ltemp;
        }
        break;
    }
    case _ep_noaicontrol:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->noaicontrol = (int)ltemp;
        }
        break;
    }
    case _ep_nodieblink:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.nodieblink = (int)ltemp;
        }
        break;
    }
    case _ep_nodrop:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.nodrop = (int)ltemp;
        }
        break;
    }
    case _ep_nograb:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->nograb = (int)ltemp;
        }
        break;
    }
    case _ep_nohithead:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.nohithead = (int)ltemp;
        }
        break;
    }
    case _ep_nolife:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.nolife = (int)ltemp;
        }
        break;
    }
    case _ep_nopain:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.nopain = (int)ltemp;
        }
        break;
    }
    case _ep_offense:
    {
        if(paramCount >= 4 &&
                SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) &&
                ltemp < (LONG)MAX_ATKS && ltemp >= (LONG)0 &&
                SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            ent->offense_factors[(int)ltemp] = (float)dbltemp;
        }
        break;
    }
    case _ep_offscreen_noatk_factor:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.offscreen_noatk_factor = (float)dbltemp;
        }
        break;
    }
    case _ep_offscreenkill:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.offscreenkill = (int)ltemp;
        }
        break;
    }
    case _ep_opponent:
    {
        ent->opponent = (entity *)varlist[2]->ptrVal;
        break;
    }
    case _ep_custom_target:
    {
        ent->custom_target = (entity *)varlist[2]->ptrVal;
        break;
    }
    case _ep_owner:
    {
        ent->owner = (entity *)varlist[2]->ptrVal;
        break;
    }
    case _ep_parent:
    {
        ent->parent = (entity *)varlist[2]->ptrVal;
        break;
    }
    case _ep_pathfindstep:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.pathfindstep = (float)dbltemp;
        }
        break;
    }
    case _ep_position:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->position.x = (float)dbltemp;
        }
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            ent->position.z = (float)dbltemp;
        }
        if(paramCount >= 5 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp)))
        {
            ent->position.y = (float)dbltemp;
        }
        break;
    }
    case _ep_x:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->position.x = (float)dbltemp;
        }
        break;
    }
    case _ep_z:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->position.z = (float)dbltemp;
        }
        break;
    }
    case _ep_a:
    case _ep_y:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->position.y = (float)dbltemp;
        }
        break;
    }
    case _ep_projectile:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->projectile = (int)ltemp;
        }
        break;
    }
    case _ep_projectilehit:
    {
        ent->modeldata.projectilehit = 0;

        for(i = 2; i < paramCount; i++)
        {
            if(varlist[i] && varlist[i]->vt == VT_INTEGER) // known entity type
            {
                ltemp = varlist[i]->lVal;
                /* AnyBOR: validate collision selector extent. */
                if((ltemp & 0x80000000) && (unsigned int)(ltemp & 0x7fffffff) >= sizeof(entitytypes) / sizeof(*entitytypes))
                {
                    printf("You must pass one or more string constants for projectilehit entity type.\n");
                    goto changeentityproperty_error;
                }
                /* AnyBOR: native collision value follows. */

                if(ltemp & 0x80000000)
                {
                    ent->modeldata.projectilehit |= entitytypes[ltemp & 0x7fffffff];
                }
                else
                {
                    ent->modeldata.projectilehit |= ltemp;
                }
            }
            else
            {
                printf("You must pass one or more string constants for projectilehit entity type.\n");
                goto changeentityproperty_error;
            }
        }

        break;
    }
    case _ep_running:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.runspeed = (float)dbltemp;
        }
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            ent->modeldata.runjumpheight = (float)dbltemp;
        }
        if(paramCount >= 5 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp)))
        {
            ent->modeldata.runjumpdist = (float)dbltemp;
        }
        if(paramCount >= 6 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[5], &dbltemp)))
        {
            ent->modeldata.runhold = (int)dbltemp;
        }
        if(paramCount >= 7 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[6], &dbltemp)))
        {
            ent->modeldata.runupdown = (int)dbltemp;
        }

        break;
    }
    case _ep_rush_count:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->rush.count.current = (int)ltemp;
        }
        break;
    }
    case _ep_rush_tally:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->rush.count.max = (int)ltemp;
        }
        break;
    }
    case _ep_rush_time:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->rush.time = (int)ltemp;
        }
        break;
    }
    case _ep_score:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.score = (int)ltemp;
        }
        break;
    }
    case _ep_scroll:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.scroll = (float)dbltemp;
        }
        break;
    }
    case _ep_seal:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->seal = (int)ltemp;
        }
        break;
    }
    case _ep_sealtime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->sealtime = (int)ltemp;
        }
        break;
    }
    case _ep_setlayer:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.setlayer = (int)ltemp;
        }
        break;
    }
    case _ep_sortid:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->sortid = (int)ltemp;
        }
        break;
    }
    case _ep_speed:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.speed = (float)dbltemp;
        }
        break;
    }
    case _ep_spritea:
    {
        if(varlist[2]->vt != VT_INTEGER)
        {
            if(varlist[2]->vt != VT_STR)
                printf("You must provide a string value for Sprite Array subproperty:\n\
                    changeentityproperty({ent}, 'spritea', {subproperty}, {animation ID}, {frame}, {value})\n\
                    ~'centerx'\n\
                    ~'centery'\n\
                    ~'file'\n\
                    ~'offsetx'\n\
                    ~'sprite'\n");
            goto changeentityproperty_error;
        }

        ltemp   = varlist[2]->lVal;
        if(paramCount < 5 || !varlist[3] || !varlist[4] ||
           varlist[3]->vt != VT_INTEGER || varlist[4]->vt != VT_INTEGER ||
           varlist[3]->lVal < 0 || (uint64_t)varlist[3]->lVal > INT_MAX ||
           varlist[4]->lVal < 0 || (uint64_t)varlist[4]->lVal > INT_MAX ||
           !ent->modeldata.animation) break;


        /*
        Failsafe checks. Any attempt to access a sprite property on invalid frame would cause instant shutdown.
        */
        if(!validanim(ent, varlist[3]->lVal) || (varlist[4]->lVal >= ent->modeldata.animation[varlist[3]->lVal]->numframes) || paramCount < 5)
        {
            break;
        }

        if(!ent->modeldata.animation[varlist[3]->lVal]->sprite) break;
        i = ent->modeldata.animation[varlist[3]->lVal]->sprite[varlist[4]->lVal];
        if(!sprite_map || i < 0 || i >= sprite_map_max_items || (uint64_t)i >= sprites_loaded) break;   //Get sprite index.

        switch(ltemp)
        {
        case _ep_spritea_centerx:
        {
                if(paramCount < 6 || !varlist[5]) break;
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[5], &ltemp)))
            {
                sprite_map[i].centerx = (int)ltemp;
            }

            break;
        }
        case _ep_spritea_centery:
        {
                if(paramCount < 6 || !varlist[5]) break;
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[5], &ltemp)))
            {
                sprite_map[i].centery = (int)ltemp;
            }
            break;
        }
        case _ep_spritea_file:
        {
                if(paramCount < 6 || !varlist[5]) break;
            if(varlist[5]->vt != VT_STR)
            {
                printf("You must provide a string value for file name.\n");
                goto changeentityproperty_error;
            }
            if(!sprite_map[i].node || !obor_script_sprite_name_store(sprite_map[i].node->filename, varlist[5]->strVal)) break;
            break;
        }
        /*
        case _ep_spritea_offsetx:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[5], &ltemp)))
            {
                sprite_map[i].ofsx = (int)ltemp;
                (*pretvar)->lVal = (LONG)1;
            }
            break;
        }
        case _ep_spritea_offsety:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
            {
                sprite_map[i].ofsy = (int)ltemp;
                (*pretvar)->lVal = (LONG)1;
            }
            break;
        }*/
        case _ep_spritea_sprite:
        {
                if(paramCount < 6 || !varlist[5]) break;
                if(varlist[5]->vt != VT_PTR && varlist[5]->vt != VT_EMPTY) break;
            if(!sprite_map[i].node) break;
            sprite_map[i].node->sprite = (VOID *)varlist[5]->ptrVal;

            break;
        }
        default:
            printf("Unknown Sprite Array subproperty.\n");
            goto changeentityproperty_error;
        }
        break;
    }
    case _ep_stalltime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->stalltime = (int)ltemp;
        }
        break;
    }
    case _ep_releasetime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->releasetime = (int)ltemp;
        }
        break;
    }
    case _ep_stats:
    {
        if(paramCount < 4)
        {
            break;
        }

        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
        {
            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp)))
            {
                switch(varlist[2]->lVal)
                {
                default:
                    ent->modeldata.stats[(int)ltemp] = (float)dbltemp;
                    break;
                case 1:
                    ent->stats[(int)ltemp] = (float)dbltemp;
                    break;
                }
            }
        }
        break;
    }
    case _ep_staydown:
    {
        if(varlist[2]->vt != VT_INTEGER)
        {
            if(varlist[2]->vt != VT_STR)
                printf("You must provide a string value for Staydown subproperty:\n\
                    changeentityproperty({ent}, 'staydown', {subproperty}, {value})\n\
                    ~'rise'\n\
                    ~'riseattack'\n\
                    ~'riseattack_stall'\n");
            goto changeentityproperty_error;
        }
        if(paramCount < 4)
        {
            break;
        }

        switch(varlist[2]->lVal)
        {
        case _ep_staydown_rise:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
            {
                ent->staydown.rise = (int)ltemp;
            }
            break;
        }
        case _ep_staydown_riseattack:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
            {
                ent->staydown.riseattack = (int)ltemp;
            }
            break;
        }
        case _ep_staydown_riseattack_stall:
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
            {
                ent->staydown.riseattack_stall = (int)ltemp;
            }
            break;
        }
        default:
            printf("Unknown Staydown subproperty.\n");
            goto changeentityproperty_error;
        }
        break;
    }
    case _ep_stealth:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.stealth.hide = (int)ltemp;
        }
        break;
    }
    case _ep_subentity:
    {
        if(ent->subentity)
        {
            ent->subentity->parent = NULL;
        }
        ent->subentity = (entity *)varlist[2]->ptrVal;
        if(ent->subentity)
        {
            ent->subentity->parent = ent;
        }
        break;
    }
    case _ep_subject_to_basemap:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_basemap = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_gravity:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_gravity = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_hole:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_hole = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_maxz:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_maxz = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_minz:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_minz = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_obstacle:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_obstacle = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_platform:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_platform = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_screen:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_screen = (int)ltemp;
        }
        break;
    }
    case _ep_subject_to_wall:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subject_to_wall = (int)ltemp;
        }
        break;
    }
    case _ep_subtype:
    {
        if(obor_profile_build >= 4283 && obor_profile_build < 4413) goto changeentityproperty_error;
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.subtype = (int)ltemp;
        }
        break;
    }
    case _ep_takeaction:
    {
        //if(varlist[2]->vt == VT_STRING)
        if(varlist[2]->vt == VT_EMPTY)
        {
            // UT: changed this to only accept NULL(), otherwise the log file is filled with warnings
            ent->takeaction = NULL;
            break;
        }
        else if(varlist[2]->vt != VT_INTEGER)
        {
            printf("You must give a string value for action type.\n");
            goto changeentityproperty_error;
        }

        // otherwise, the parameter is a known action
        ltemp = varlist[2]->lVal;
        const int legacy_action_table = !obor_has_simple_animation_action();
        if(ltemp >= 0 && ltemp < _ep_ta_the_end - legacy_action_table)
        {
            const int action_index = (int)ltemp + (legacy_action_table && ltemp >= _ep_ta_common_animation_normal);
            ent->takeaction = actions[action_index];
        }

        break;
    }
    case _ep_think:
    {
        //if(varlist[2]->vt == VT_STRING)
        if(varlist[2]->vt == VT_EMPTY)
        {
            // UT: changed this to only accept NULL(), otherwise the log file is filled with warnings
            break;
        }
        else if(varlist[2]->vt != VT_INTEGER)
        {
            printf("You must give a string value for think type.\n");
            goto changeentityproperty_error;
        }

        // otherwise, the parameter is a known action
        ltemp = varlist[2]->lVal;
        if((ltemp >= 0) && (ltemp < _ep_th_the_end))
        {
            ent->think = think[(int)ltemp];
        }

        break;
    }
    case _ep_thold:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.thold = (int)ltemp;
        }
        break;
    }
    case _ep_throwdamage:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.throwdamage = (int)ltemp;
        }
        break;
    }
    case _ep_throwdist:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.throwdist = (float)dbltemp;
        }
        break;
    }
    case _ep_throwframewait:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.throwframewait = (int)ltemp;
        }
        break;
    }
    case _ep_throwheight:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->modeldata.throwheight = (float)dbltemp;
        }
        break;
    }
    case _ep_tosstime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->toss_time = (int)ltemp;
        }
        break;
    }
    case _ep_trymove:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            if(ltemp == 1)
            {
                ent->trymove = common_trymove;
            }
            else if(ltemp == 2)
            {
                ent->trymove = player_trymove;
            }
            else
            {
                ent->trymove = NULL;
            }
        }
        break;
    }
    case _ep_type:
    {
        if(varlist[2]->vt != VT_INTEGER)
        {
            printf("You must provide a type constant for type.\n");
            goto changeentityproperty_error;
        }

        ltemp = varlist[2]->lVal;
        ent->modeldata.type = (int)ltemp;

        break;
    }
    case _ep_velocity:
    {
        if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
        {
            ent->velocity.x = (float)dbltemp;
        }
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            ent->velocity.z = (float)dbltemp;
        }
        if(paramCount >= 5 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp)))
        {
            ent->velocity.y = (float)dbltemp;
        }
        break;
    }
    case _ep_walkoffmovex:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.walkoffmovex = (int)ltemp;
        }
        break;
    }
    case _ep_walkoffmovez:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.walkoffmovez = (int)ltemp;
        }
        break;
    }
    case _ep_weapnum:
    {
        if(obor_profile_build >= 4283 && obor_profile_build < 4401) goto changeentityproperty_error;
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.weapnum = (int)ltemp;
        }
        break;
    }
    case _ep_weaploss:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ent->modeldata.weaploss[0] = (int)ltemp;
        }

        if(paramCount >= 4)
        {
            if(FAILED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
            {
                printf("You must specify the flag value.\n");
                *pretvar = NULL;
                return E_FAIL;
            }
            ent->modeldata.weaploss[1] = (int)ltemp2;
        }
        break;
    }
    case _ep_weapon:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            ltemp2 = (LONG)0;
            if(paramCount < 4 ||  SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
            {
                set_weapon(ent, (int)ltemp, (int)ltemp2);
            }
        }
        break;
    }
    default:
        //printf("Property name '%s' is not supported by function changeentityproperty.\n", propname);
        goto changeentityproperty_error;
        break;
    }

    return S_OK;
changeentityproperty_error:
    return E_FAIL;
}

//tossentity(entity, height, speedx, speedz)
HRESULT openbor_tossentity(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    entity *ent = NULL;
    DOUBLE height = 0, speedx = 0, speedz = 0;

    if(!pretvar) return E_FAIL;
    if(paramCount < 1)
    {
        goto toss_error;
    }

    ent = varlist && varlist[0] && varlist[0]->vt == VT_PTR
        ? (entity *)varlist[0]->ptrVal : NULL; //retrieve the entity
    if(!ent)
    {
        goto toss_error;
    }

    if(!*pretvar) return E_FAIL;
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)1;

    if(paramCount >= 2)
    {
        ScriptVariant_DecimalValue(varlist[1], &height);
    }
    if(paramCount >= 3)
    {
        ScriptVariant_DecimalValue(varlist[2], &speedx);
    }
    if(paramCount >= 4)
    {
        ScriptVariant_DecimalValue(varlist[3], &speedz);
    }

    ent->velocity.x = (float)speedx;
    ent->velocity.z = (float)speedz;
    toss(ent, (float)height);
    return S_OK;

toss_error:
    printf("Function tossentity(entity,height, speedx, speedz) requires at least a valid entity handle.\n");
    *pretvar = NULL;
    return E_FAIL;
}

// ===== getplayerproperty =====
enum playerproperty_enum
{
    _pp_colourmap,
    _pp_combokey,
    _pp_combostep,
    _pp_credits,
    _pp_disablekeys,
    _pp_ent,
    _pp_entity,
    _pp_hasplayed,
    _pp_hmapl,
    _pp_hmapu,
    _pp_inputtime,
    _pp_joining,
    _pp_keys,
    _pp_lives,
    _pp_mapcount,
    _pp_name,
    _pp_newkeys,
    _pp_numweapons,
    _pp_playkeys,
    _pp_releasekeys,
    _pp_score,
    _pp_spawnhealth,
    _pp_spawnmp,
    _pp_weapnum,
    _pp_weapon,
    _pp_the_end
};

static int obor_uses_early_player_properties(void)
{
    return obor_profile_build >= 4283 && obor_profile_build < 4400;
}

static int obor_player_property_native(int property)
{
    if(obor_uses_early_player_properties() && property >= _pp_numweapons)
    {
        return property < _pp_the_end - 1 ? property + 1 : _pp_the_end;
    }
    return property;
}

int mapstrings_playerproperty(ScriptVariant **varlist, int paramCount)
{
    char *propname;
    int prop;

    static const char *proplist[] =
    {
        "colourmap",
        "combokey",
        "combostep",
        "credits",
        "disablekeys",
        "ent",
        "entity",
        "hasplayed",
        "hmapl",
        "hmapu",
        "inputtime",
        "joining",
        "keys",
        "lives",
        "mapcount",
        "name",
        "newkeys",
        "numweapons",
        "playkeys",
        "releasekeys",
        "score",
        "spawnhealth",
        "spawnmp",
        "weapnum",
        "weapon",
    };

    if(paramCount < 2)
    {
        return 1;
    }

    if(!varlist || !varlist[1])
    {
        return 0;
    }
    if(varlist[1]->vt != VT_STR)
    {
        return 1;
    }

    propname = (char *)StrCache_GetIfPresent(varlist[1]->strVal);
    if(!propname)
    {
        return 0;
    }
    prop = searchList(proplist, propname, _pp_the_end);
    const int legacy = obor_uses_early_player_properties();
    if(prop < 0 || (legacy && prop == _pp_numweapons))
    {
        printf("Player property name '%s' is not supported yet.\n", propname);
        return 0;
    }

    ScriptVariant_ChangeType(varlist[1], VT_INTEGER);
    varlist[1]->lVal = prop - (legacy && prop > _pp_numweapons);
    return 1;
}

//getplayerproperty(index, propname);
HRESULT openbor_getplayerproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    int index;
    entity *ent = NULL;
    int prop = -1;
    ScriptVariant *arg = NULL;

    if(!pretvar) return E_FAIL;
    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    if(!varlist || !varlist[0] || !varlist[1] || !*pretvar ||
       (varlist[1]->vt == VT_STR && !StrCache_GetIfPresent(varlist[1]->strVal)))
    {
        *pretvar = NULL;
        return E_FAIL;
    }
    mapstrings_playerproperty(varlist, paramCount);
    ScriptVariant_Clear(*pretvar);

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &ltemp)))
    {
        index = 0;
    }
    else
    {
        index = (int)ltemp;
    }


    if(index < 0 || index >= MAX_PLAYERS)
    {
        *pretvar = NULL;
        return E_FAIL;
    }
    ent = player[index].ent;

    arg = varlist[1];
    if(arg->vt != VT_INTEGER)
    {
        if(arg->vt != VT_STR)
        {
            printf("Function call getplayerproperty has invalid propery name parameter, it must be a string value.\n");
        }
        *pretvar = NULL;
        return E_FAIL;
    }
    prop = obor_player_property_native(arg->lVal);

    switch(prop)
    {
    case _pp_ent:
    case _pp_entity:
    {
        if(!ent)
        {
            ScriptVariant_Clear(*pretvar);    // player not spawned
        }
        else
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)ent;
        }
        break;
    }
    case _pp_name:
    {
        if(!memchr(player[index].name, 0, sizeof(player[index].name)))
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        if(!StrCache_GetIfPresent((*pretvar)->strVal))
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        StrCache_Copy((*pretvar)->strVal, (char *)player[index].name);
        break;
    }
    case _pp_colourmap:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].colourmap;
        break;
    }
    case _pp_score:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].score;
        break;
    }
    case _pp_hasplayed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].hasplayed;
        break;
    }
    case _pp_spawnhealth:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].spawnhealth;
        break;
    }
    case _pp_spawnmp:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].spawnmp;
        break;
    }
    case _pp_lives:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].lives;
        break;
    }
    case _pp_disablekeys:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].disablekeys;
        break;
    }
    case _pp_playkeys:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].playkeys;
        break;
    }
    case _pp_keys:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].keys;
        break;
    }
    case _pp_newkeys:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].newkeys;
        break;
    }
    case _pp_releasekeys:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].releasekeys;
        break;
    }
    case _pp_credits:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        if(noshare)
        {
            (*pretvar)->lVal = (LONG)player[index].credits;
        }
        else
        {
            (*pretvar)->lVal = credits;
        }
        break;
    }
    case _pp_weapnum:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].weapnum;
        break;
    }
    case _pp_numweapons:
    {
        int cacheindex = -1;
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = 0;
        if(model_cache && player[index].name[0] &&
           memchr(player[index].name, 0, sizeof(player[index].name)))
        {
            cacheindex = get_cached_model_index(player[index].name);
        }
        if(cacheindex >= 0 && cacheindex < models_cached && model_cache[cacheindex].model)
        {
            (*pretvar)->lVal = (LONG)model_cache[cacheindex].model->numweapons;
        }
        break;
    }
    case _pp_joining:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].joining;
        break;
    }
    case _pp_combokey:
    {
        ScriptVariant *frm = NULL;
        frm = paramCount > 2 ? varlist[2] : NULL;
        if(!frm || frm->vt != VT_INTEGER || frm->lVal < 0 ||
           (size_t)frm->lVal >= sizeof(player[index].combokey) / sizeof(player[index].combokey[0]))
        {
            printf("%s", obor_uses_early_player_properties() ?
                   "Need a frame number for this property.\n" :
                   "Need a combostep value number for this property.\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].combokey[frm->lVal];
        break;
    }
    case _pp_combostep:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].combostep;
        break;
    }
    case _pp_inputtime:
    {
        ScriptVariant *frm = NULL;
        frm = paramCount > 2 ? varlist[2] : NULL;
        if(!frm || frm->vt != VT_INTEGER || frm->lVal < 0 ||
           (size_t)frm->lVal >= sizeof(player[index].inputtime) / sizeof(player[index].inputtime[0]))
        {
            printf("%s", obor_uses_early_player_properties() ?
                   "Need a frame number for this property.\n" :
                   "Need a combostep value number for this property.\n");
            *pretvar = NULL;
            return E_FAIL;
        }
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)player[index].inputtime[frm->lVal];
        break;
    }
    case _pp_hmapl:
    {
        int cacheindex;

        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        if ( stricmp(player[index].name,"") != 0 ) {
            cacheindex = get_cached_model_index(player[index].name);
            if ( cacheindex == -1 )
            {
               (*pretvar)->lVal = (LONG)0;
               break;
            }
        } else
        {
           (*pretvar)->lVal = (LONG)0;
           break;
        }

        (*pretvar)->lVal = (LONG)model_cache[cacheindex].model->maps.hide_start;
        break;
    }
    case _pp_hmapu:
    {
        int cacheindex;

        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        if ( stricmp(player[index].name,"") != 0 ) {
            cacheindex = get_cached_model_index(player[index].name);
            if ( cacheindex == -1 )
            {
               (*pretvar)->lVal = (LONG)0;
               break;
            }
        } else
        {
           (*pretvar)->lVal = (LONG)0;
           break;
        }

        (*pretvar)->lVal = (LONG)model_cache[cacheindex].model->maps.hide_end;
        break;
    }
    case _pp_mapcount:
    {
        int cacheindex;

        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

        if ( stricmp(player[index].name,"") != 0 ) {
            cacheindex = get_cached_model_index(player[index].name);
            if ( cacheindex == -1 )
            {
               (*pretvar)->lVal = (LONG)0;
               break;
            }
        } else
        {
           (*pretvar)->lVal = (LONG)0;
           break;
        }

        (*pretvar)->lVal = (LONG)(model_cache[cacheindex].model->maps_loaded + 1);
        break;
    }
    //this property is not known
    //default:{
    //  .....
    //}
    }
    return S_OK;
}


//changeplayerproperty(index, propname, value[, value2, value3,...]);
HRESULT openbor_changeplayerproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp, ltemp2;
    int index;
    entity *ent = NULL;
    int prop = -1;
    char *tempstr = NULL;
    static char buffer[64];
    ScriptVariant *arg = NULL;

    if(!pretvar) return E_FAIL;
    *pretvar = NULL;
    if(paramCount < 3)
    {
        printf("Function changeplayerproperty must have at least 3 arguments.\n");
        return E_FAIL;
    }

    if(!varlist || !varlist[0] || !varlist[1] ||
       (varlist[1]->vt == VT_STR && !StrCache_GetIfPresent(varlist[1]->strVal)))
    {
        *pretvar = NULL;
        return E_FAIL;
    }
    mapstrings_playerproperty(varlist, paramCount);
    arg = varlist[0];

    if(FAILED(ScriptVariant_IntegerValue(arg, &ltemp)))
    {
        index = 0;
    }
    else
    {
        index = (int)ltemp;
    }

    if(index < 0 || index >= MAX_PLAYERS)
    {
        *pretvar = NULL;
        return E_FAIL;
    }
    ent = player[index].ent;

    if(varlist[1]->vt != VT_INTEGER)
    {
        if(varlist[1]->vt != VT_STR)
        {
            printf("You must give a string value for player property name.\n");
        }
        return E_FAIL;
    }
    prop = obor_player_property_native(varlist[1]->lVal);

    arg = varlist[2];
    if(!arg)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    //change the model
    switch(prop)
    {
    case _pp_ent:
    case _pp_entity:
    {
        if(arg->vt == VT_PTR || arg->vt == VT_EMPTY)
        {
            player[index].ent = (entity *)arg->ptrVal;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_weapon:
    {
        if(ent)
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
            {
                if(paramCount > 3)
                {
                    if(!varlist[3] || FAILED(ScriptVariant_IntegerValue(varlist[3], &ltemp2)))
                    {
                        goto cpperror;
                    }
                }
                else
                {
                    ltemp2 = (LONG)0;
                }
                set_weapon(player[index].ent, (int)ltemp, (int)ltemp2);
            }
            else
            {
                goto cpperror;
            }
        }
        break;
    }
    case _pp_weapnum:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].weapnum = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_name:
    {
        if(arg->vt != VT_STR)
        {
            goto cpperror;
        }
        tempstr = (char *)StrCache_GetIfPresent(arg->strVal);
        if(!tempstr || strlen(tempstr) > (size_t)obor_profile_name_limit())
        {
            *pretvar = NULL;
            return E_FAIL;
        }
        strcpy(player[index].name, tempstr);
        break;
    }
    case _pp_colourmap:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].colourmap = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_score:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            if(ltemp < 0)
            {
                ltemp = 0;
            }
            else if(ltemp > 999999999)
            {
                ltemp = 999999999;
            }
            player[index].score = (unsigned int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_hasplayed:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].hasplayed = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_spawnhealth:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].spawnhealth = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_spawnmp:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].spawnmp = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_lives:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].lives = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_disablekeys:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].disablekeys = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_playkeys:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].playkeys = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_keys:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].keys = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_newkeys:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg,&ltemp)))
        {
            player[index].newkeys = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_credits:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            if(noshare)
            {
                player[index].credits = (int)ltemp;
            }
            else
            {
                credits = (int)ltemp;
            }
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_joining:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg,&ltemp)))
        {
            player[index].joining = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_releasekeys:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg,&ltemp)))
        {
            player[index].releasekeys = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_combokey:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg,&ltemp)))
        {
            ScriptVariant *value = paramCount > 3 ? varlist[3] : NULL;
            if(!value || value->vt != VT_INTEGER || ltemp < 0 ||
               (size_t)ltemp >= sizeof(player[index].combokey) / sizeof(player[index].combokey[0]))
            {
                printf("%s", obor_uses_early_player_properties() ?
                       "Need a value and frame number for this property.\n" :
                       "Need a value and combostep value for this property.\n");
                *pretvar = NULL;
                return E_FAIL;
            }
            player[index].combokey[ltemp] = (int)value->lVal;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_combostep:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg,&ltemp)))
        {
            player[index].combostep = (int)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    case _pp_inputtime:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg,&ltemp)))
        {
            ScriptVariant *value = paramCount > 3 ? varlist[3] : NULL;
            if(!value || value->vt != VT_INTEGER || ltemp < 0 ||
               (size_t)ltemp >= sizeof(player[index].inputtime) / sizeof(player[index].inputtime[0]))
            {
                printf("%s", obor_uses_early_player_properties() ?
                       "Need a value and frame number for this property.\n" :
                       "Need a value and combostep value number for this property.\n");
                *pretvar = NULL;
                return E_FAIL;
            }
            player[index].inputtime[ltemp] = (int)value->lVal;
        }
        else
        {
            goto cpperror;
        }
        break;
    }
    default:
        printf("Invalid property name for function changeplayerproperty.\n");
        return E_FAIL;
    }

    return S_OK;
cpperror:
    tempstr = arg->vt == VT_STR ? (char *)StrCache_GetIfPresent(arg->strVal) : NULL;
    {
    switch( arg->vt )
    {
    case VT_EMPTY:
        snprintf(buffer, sizeof(buffer), "<VT_EMPTY>   Unitialized" );
        break;
    case VT_INTEGER:
        snprintf(buffer, sizeof(buffer), "%d", arg->lVal);
        break;
    case VT_DECIMAL:
        snprintf(buffer, sizeof(buffer), "%lf", arg->dblVal );
        break;
    case VT_PTR:
        snprintf(buffer, sizeof(buffer), "#%ld", (long)(arg->ptrVal));
        break;
    case VT_STR:
        snprintf(buffer, sizeof(buffer), "%s", tempstr ? tempstr : "<invalid string>");
        break;
    default:
        snprintf(buffer, sizeof(buffer), "<Unprintable VARIANT type.>" );
        break;
    }
}

    printf("Function changeplayerproperty receives an invalid value: %s.\n", buffer);
    return E_FAIL;
}

//checkhole(x,z,a), return 1 if there's hole here
HRESULT openbor_checkhole(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z, a;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)0;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    if ( paramCount >= 3 )
    {
        arg = varlist[2];
        if(FAILED(ScriptVariant_DecimalValue(arg, &a)))
        {
            return S_OK;
        }

        (*pretvar)->lVal = (LONG)(checkhole_in((float)x, (float)z, (float)a) && checkwall((float)x, (float)z) < 0);
    }
    else (*pretvar)->lVal = (LONG)(checkhole((float)x, (float)z) && checkwall((float)x, (float)z) < 0);

    return S_OK;
}

//checkholeindex(x,z,a), return hole index if there's hole here, else it returns -1
HRESULT openbor_checkholeindex(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z, a;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)-1;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    if ( checkwall((float)x, (float)z) < 0 )
    {
        if ( paramCount >= 3 )
        {
            arg = varlist[2];
            if(FAILED(ScriptVariant_DecimalValue(arg, &a)))
            {
                return S_OK;
            }

            (*pretvar)->lVal = (LONG)checkholeindex_in((float)x, (float)z, (float)a);
        }
        else (*pretvar)->lVal = (LONG)checkhole_index((float)x, (float)z);
    }

    return S_OK;
}

//checkwall(x,z), return wall height, or 0 | accept checkwall(x,z,y) too
HRESULT openbor_checkwall(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z, y;
    int wall;
    float h = 100000;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
    (*pretvar)->dblVal = (DOUBLE)0;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    if (paramCount > 2)
    {
        arg = varlist[2];
        if(FAILED(ScriptVariant_DecimalValue(arg, &y)))
        {
            return S_OK;
        }
        if(obor_profile_build >= 4283 && obor_profile_build < 4411)
        {
            /* The original wrapper read the stored representation after conversion. */
            DOUBLE stored;
            memcpy(&stored, &arg->dblVal, sizeof(stored));
            h = (float)stored;
        }
        else
        {
            h = (float)y;
        }
    }

    if((wall = checkwall_below((float)x, (float)z, (float)h)) >= 0)
    {
        (*pretvar)->dblVal = (DOUBLE)level->walls[wall].height;
    }
    return S_OK;
}

//checkwallindex(x,z), return wall index, or -1 | accept checkwallindex(x,z,y) too
HRESULT openbor_checkwallindex(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z, y;
    int wall;
    float h = 100000;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)-1;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    if (paramCount > 2)
    {
        arg = varlist[2];
        if(FAILED(ScriptVariant_DecimalValue(arg, &y)))
        {
            return S_OK;
        }
        h = (float)arg->dblVal;
    }

    if((wall = checkwall_below((float)x, (float)z, (float)h)) >= 0)
    {
        (*pretvar)->lVal = (LONG)wall;
    }
    return S_OK;
}

//checkplatformbelow(x,z,a), return the highest platfrom entity below
HRESULT openbor_checkplatformbelow(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z, a;

    if(paramCount < 3)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    //ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
    //(*pretvar)->dblVal = (DOUBLE)0;
    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)NULL;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    arg = varlist[2];
    if(FAILED(ScriptVariant_DecimalValue(arg, &a)))
    {
        return S_OK;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)check_platform_below((float)x, (float)z, (float)a, NULL);
    return S_OK;
}

//checkplatformabove(x,z,a), find a lowest platform above this altitude
HRESULT openbor_checkplatformabove(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z, a;

    if(paramCount < 3)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    //ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
    //(*pretvar)->dblVal = (DOUBLE)0;
    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)NULL;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    arg = varlist[2];
    if(FAILED(ScriptVariant_DecimalValue(arg, &a)))
    {
        return S_OK;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)check_platform_above((float)x, (float)z, (float)a, NULL);
    return S_OK;
}

//checkplatformbetween(x,z,a_min,a_max), find the first platform between these 2 altitudes
HRESULT openbor_checkplatformbetween(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z, amin, amax;

    if(paramCount < 3)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    //ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
    //(*pretvar)->dblVal = (DOUBLE)0;
    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)NULL;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    arg = varlist[2];
    if(FAILED(ScriptVariant_DecimalValue(arg, &amin)))
    {
        return S_OK;
    }

    if(paramCount < 4 || !varlist[3])
    {
        *pretvar = NULL;
        return E_FAIL;
    }
    arg = varlist[3];
    if(FAILED(ScriptVariant_DecimalValue(arg, &amax)))
    {
        return S_OK;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)check_platform_between((float)x, (float)z, (float)amin, (float)amax, NULL);
    return S_OK;
}

//checkbasemap(x,z), return basemap height (float)
HRESULT openbor_checkbasemap(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
    (*pretvar)->dblVal = (DOUBLE)0;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    (*pretvar)->dblVal = (DOUBLE)check_basemap((float)x, (float)z);

    return S_OK;
}

//checkbasemapindex(x,z), return basemap index in (x,z)
HRESULT openbor_checkbasemapindex(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    DOUBLE x, z;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
    (*pretvar)->dblVal = (DOUBLE)0;

    arg = varlist[0];
    if(FAILED(ScriptVariant_DecimalValue(arg, &x)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_DecimalValue(arg, &z)))
    {
        return S_OK;
    }

    if(obor_profile_build == 4290)
        (*pretvar)->dblVal = (DOUBLE)check_basemap((float)x, (float)z);
    else
        (*pretvar)->dblVal = (DOUBLE)check_basemap_index((float)x, (float)z);

    return S_OK;
}

//generatebasemap(int map_index, float rx, float rz, float x_size, float z_size, float min_y, float max_y, int x_cont) to generate an inclined terrain
HRESULT openbor_generatebasemap(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE rx, rz, x_size, z_size, min_y, max_y;
    LONG index;
    LONG x_cont = (LONG)0;

    if(paramCount < 7)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    if ( FAILED(ScriptVariant_IntegerValue(varlist[0], &index)) )
    {
        *pretvar = NULL;
        return E_FAIL;
    }
    if(paramCount > 7)
    {
        if ( FAILED(ScriptVariant_IntegerValue(varlist[7],
                obor_profile_build >= 4283 && obor_profile_build < 4390 ? &index : &x_cont)) )
        {
            *pretvar = NULL;
            return E_FAIL;
        }
    }
    if ( FAILED(ScriptVariant_DecimalValue(varlist[1], &rx)) || FAILED(ScriptVariant_DecimalValue(varlist[2], &rz)) ||
         FAILED(ScriptVariant_DecimalValue(varlist[3], &x_size)) || FAILED(ScriptVariant_DecimalValue(varlist[4], &z_size)) ||
         FAILED(ScriptVariant_DecimalValue(varlist[5], &min_y)) || FAILED(ScriptVariant_DecimalValue(varlist[6], &max_y))
    )
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    generate_basemap(index, rx, rz, x_size, z_size, min_y, max_y, x_cont);

    return S_OK;
}

HRESULT openbor_openfilestream(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    char *filename = NULL;
    ScriptVariant *arg = NULL;
    LONG location = 0;
    int fsindex;

    FILE *handle = NULL;
    char path[256] = {""};
    char tmpname[256] = {""};
    long size;

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    if(paramCount < 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    arg = varlist[0];
    if(arg->vt != VT_STR)
    {
        printf("Filename for openfilestream must be a string.\n");
        *pretvar = NULL;
        return E_FAIL;
    }

    filename = (char *)StrCache_Get(arg->strVal);

    if(paramCount > 1)
    {
        arg = varlist[1];
        if(FAILED(ScriptVariant_IntegerValue(arg, &location)))
        {
            *pretvar = NULL;
            return E_FAIL;
        }
    }

    for(fsindex = 0; fsindex < numfilestreams; fsindex++)
    {
        if(filestreams[fsindex].buf == NULL)
        {
            break;
        }
    }

    if(fsindex == numfilestreams)
    {
        __realloc(filestreams, numfilestreams); //warning, don't ++ here, its a macro
        numfilestreams++;
    }

    // Load file from saves directory if specified
    if(location)
    {
        getBasePath(path, "Saves", 0);
        getPakName(tmpname, sizeof(tmpname), -1);
        if(!obor_pak_path_append(path, sizeof(path), tmpname)) return E_FAIL;
        if(!obor_pak_path_append(path, sizeof(path), "/")) return E_FAIL;
        if(!obor_pak_path_append(path, sizeof(path), filename)) return E_FAIL;
        //printf("open path: %s", path);
#ifndef DC
        if(!(fileExists(path)))
        {
            /*
            2011_03_27, DC: Let's be a little more friendly about missing files; this will let a function evaluate if file exists and decide what to do.

            printf("Openfilestream - file specified does not exist.\n"); //Keep this for possible debug mode in the future.
            */
            (*pretvar)->lVal = -1;

            return S_OK;
        }
#endif
        handle = fopen(path, "rb");
        if(handle == NULL)
        {
            (*pretvar)->lVal = -1;
            return S_OK;
        }
        //printf("\nfile opened\n");
        fseek(handle, 0, SEEK_END);
        size = ftell(handle);
        //printf("\n file size %d fsindex %d\n", size, fsindex);
        rewind(handle);
        filestreams[fsindex].buf = malloc(sizeof(*filestreams[fsindex].buf) * (size + 1));
        if(filestreams[fsindex].buf == NULL)
        {
            fclose(handle);
            (*pretvar)->lVal = -1;
            return S_OK;
        }
        fread(filestreams[fsindex].buf, 1, size, handle);
        fclose(handle);
        filestreams[fsindex].buf[size] = 0;
        filestreams[fsindex].size = size;
    }
    else
    {
        s_filestream *obor_stream_slot = &(filestreams[fsindex]);
        char *obor_stream_buffer = obor_stream_slot->buf;
        size_t obor_stream_size = obor_stream_slot->size;
        int obor_stream_loaded = buffer_pakfile(filename,
            &obor_stream_buffer, &obor_stream_size);
        obor_stream_slot->buf = obor_stream_buffer;
        obor_stream_slot->size = obor_stream_size;
        if(obor_stream_loaded != 1)
        {
            printf("Invalid filename used in openfilestream.\n");
            (*pretvar)->lVal = -1;
            return S_OK;
        }
    }

    (*pretvar)->lVal = (LONG)fsindex;

    filestreams[fsindex].pos = 0;
    return S_OK;
}

HRESULT openbor_getfilestreamline(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int length;
    char *buf;
    ScriptVariant *arg = NULL;
    LONG filestreamindex;

    if(paramCount < 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)))
    {
        return S_OK;
    }

    ScriptVariant_ChangeType(*pretvar, VT_STR);

    length = 0;
    buf = filestreams[filestreamindex].buf + filestreams[filestreamindex].pos;
    while(buf[length] && buf[length] != '\n' && buf[length] != '\r')
    {
        ++length;
    }

    StrCache_NCopy((*pretvar)->strVal, buf, length);

    return S_OK;
}

HRESULT openbor_getfilestreamargument(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    LONG filestreamindex, argument;
    char *argtype = NULL;

    if(paramCount < 3)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_IntegerValue(arg, &argument)))
    {
        return S_OK;
    }
    ScriptVariant_Clear(*pretvar);

    if(varlist[2]->vt != VT_STR)
    {
        printf("You must give a string value specifying what kind of value you want the argument converted to.\n");
        return E_FAIL;
    }
    argtype = (char *)StrCache_Get(varlist[2]->strVal);

    if(stricmp(argtype, "string") == 0)
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, (char *)findarg(filestreams[filestreamindex].buf + filestreams[filestreamindex].pos, argument));
    }
    else if(stricmp(argtype, "int") == 0)
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)atoi(findarg(filestreams[filestreamindex].buf + filestreams[filestreamindex].pos, argument));
    }
    else if(stricmp(argtype, "float") == 0)
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)atof(findarg(filestreams[filestreamindex].buf + filestreams[filestreamindex].pos, argument));
    }
    else if(stricmp(argtype, "byte") == 0) // By White Dragon
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)(readByte(filestreams[filestreamindex].buf + filestreams[filestreamindex].pos));
    }
    else
    {
        printf("Invalid type for argument converted to (getfilestreamargument).\n");
        return E_FAIL;
    }

    return S_OK;
}

HRESULT openbor_filestreamnextline(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    char *buf;
    size_t pos;
    LONG filestreamindex;

    if(paramCount < 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)))
    {
        return S_OK;
    }
    pos = filestreams[filestreamindex].pos;
    buf = filestreams[filestreamindex].buf;
    while(buf[pos] && buf[pos] != '\n' && buf[pos] != '\r')
    {
        ++pos;
    }
    while(buf[pos] == '\n' || buf[pos] == '\r')
    {
        ++pos;
    }
    filestreams[filestreamindex].pos = pos;

    return S_OK;
}

HRESULT openbor_getfilestreamposition(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    LONG filestreamindex;

    if(paramCount < 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)))
    {
        return S_OK;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)filestreams[filestreamindex].pos;
    return S_OK;
}

HRESULT openbor_setfilestreamposition(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *arg = NULL;
    LONG filestreamindex, position;


    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)))
    {
        return S_OK;
    }

    arg = varlist[1];
    if(FAILED(ScriptVariant_IntegerValue(arg, &position)))
    {
        return S_OK;
    }

    filestreams[filestreamindex].pos = position;
    return S_OK;
}

HRESULT openbor_filestreamappend(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG filestreamindex;
    ScriptVariant *arg = NULL;
    LONG appendtype = -1;
    size_t len1, len2;
    char *temp;
    static char append[2048];

    *pretvar = NULL;
    if(paramCount < 2)
    {
        goto append_error;
    }

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)))
    {
        goto append_error;
    }

    if(paramCount >= 3)
    {
        arg = varlist[2];
        if(FAILED(ScriptVariant_IntegerValue(arg, &appendtype)))
        {
            goto append_error;
        }
    }

    arg = varlist[1];

    /*
     * By White Dragon to write a byte
     */
    if ( paramCount >= 4 )
    {
        char* argtype = NULL;
        unsigned char byte = (unsigned char)0x00;
        if ( varlist[3]->vt != VT_STR ) goto append_error;

        argtype = (char *)StrCache_Get(varlist[3]->strVal);

        if( stricmp(argtype, "byte") != 0 ) goto append_error;
        else
        {
            int inc = -1; // if buf > 0 (prev bytes) you need to begin from size-1 (index)

            len1 = 1+1; // +1 is the NULL to close the buffer
            len2 = filestreams[filestreamindex].size;

            filestreams[filestreamindex].buf = realloc( filestreams[filestreamindex].buf, sizeof(*temp)*(len1+len2+0) );

            byte = (unsigned char)varlist[1]->lVal;
            //printf("a:%s->%d->%d\n",filestreams[filestreamindex].buf,byte,filestreams[filestreamindex].size);

            if ( len2 <= 0 ) inc = 0;

            filestreams[filestreamindex].buf[filestreams[filestreamindex].size+inc] = byte; // overwrite 0x00 byte
            if (appendtype <= 1 || (obor_profile_build >= 4283 && obor_profile_build < 4399))
                filestreams[filestreamindex].buf[filestreams[filestreamindex].size+1+inc] = 0x00;
            //printf("b:%s\n",filestreams[filestreamindex].buf);

            filestreams[filestreamindex].size = len1 + len2;
        }
    } else
    {
        ScriptVariant_ToString(arg, append);

        len1 = strlen(append);
        len2 = filestreams[filestreamindex].size;

        filestreams[filestreamindex].buf = realloc(filestreams[filestreamindex].buf, sizeof(*temp) * (len1 + len2 + 4));

        if(appendtype == 0)
        {
            append[len1] = ' ';
            append[++len1] = '\0';
            strcpy(filestreams[filestreamindex].buf + len2, "\r\n");
            len2 += 2;
            strcpy(filestreams[filestreamindex].buf + len2, append);
        }
        else if(appendtype == 1)
        {
            append[len1] = ' ';
            append[++len1] = '\0';
            strcpy(filestreams[filestreamindex].buf + len2, append);
        }
        else
        {
            strcpy(filestreams[filestreamindex].buf + len2, append);
        }
        filestreams[filestreamindex].size = len1 + len2;
    }

    return S_OK;

append_error:
    return E_FAIL;

}

HRESULT openbor_createfilestream(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int fsindex;
    ScriptVariant_Clear(*pretvar);

    for(fsindex = 0; fsindex < numfilestreams; fsindex++)
    {
        if(filestreams[fsindex].buf == NULL)
        {
            break;
        }
    }

    if(fsindex == numfilestreams)
    {
        __realloc(filestreams, numfilestreams); //warning, don't ++ here, its a macro
        numfilestreams++;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)fsindex;

    // Initialize the new filestream
    filestreams[fsindex].pos = 0;
    filestreams[fsindex].size = 0;
    filestreams[fsindex].buf = malloc(sizeof(*filestreams[fsindex].buf) * 128);
    filestreams[fsindex].buf[0] = '\0';
    return S_OK;
}

HRESULT openbor_savefilestream(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i;
    const int path_index = obor_profile_build >= 4283 && obor_profile_build < 4399 ? 3 : 2;
    const int mode_index = path_index + 1;
    LONG filestreamindex;
    ScriptVariant *arg = NULL;
    char *bytearg = NULL, *patharg = NULL;
    FILE *handle = NULL;
    char path[256] = {""};
    char tmpname[256] = {""};

    if(!pretvar) return E_FAIL;
    *pretvar = NULL;

    if(paramCount < 2 || !varlist)
    {
        return E_FAIL;
    }

    arg = varlist[0];
    if(!arg || FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)) ||
        filestreamindex < 0 || filestreamindex >= numfilestreams ||
        !filestreams || !filestreams[filestreamindex].buf)
    {
        printf("You must give a valid filestrema handle for savefilestream!\n");
        return E_FAIL;
    }

    arg = varlist[1];
    if(!arg || arg->vt != VT_STR)
    {
        printf("Filename for savefilestream must be a string.\n");
        return E_FAIL;
    }

    if(paramCount > path_index)
    {
        ScriptVariant *pathname = varlist[path_index];
        if(!pathname || pathname->vt != VT_STR)
        {
            printf("The pathname parameter must be a string.\n");
            return E_FAIL;
        }
        patharg = (char *)StrCache_GetIfPresent(pathname->strVal);
        if(!patharg) return E_FAIL;
    }

    if(paramCount > mode_index)
    {
        ScriptVariant *mode = varlist[mode_index];
        if(!mode || mode->vt != VT_STR) return E_FAIL;
        bytearg = (char *)StrCache_GetIfPresent(mode->strVal);
        if(!bytearg) return E_FAIL;
        if(stricmp(bytearg, "byte") != 0)
        {
            printf("%s parameter does not exist.\n", bytearg);
            return E_FAIL;
        }
    }

    // Get the saves directory
    if ( paramCount <= 2 || patharg == NULL )
    {
        getBasePath(path, "Saves", 0);
        getPakName(tmpname, sizeof(tmpname), -1);
        if(!obor_pak_path_append(path, sizeof(path), tmpname)) return E_FAIL;
        // Add user's filename to path and write the filestream to it
        if(!obor_pak_path_append(path, sizeof(path), "/")) return E_FAIL;
    } else // By White Dragon
    {
        if(!obor_pak_path_append(path, sizeof(path), "./")) return E_FAIL;
        if(!obor_pak_path_append(path, sizeof(path), patharg)) return E_FAIL;
    }
    //printf("path:%s\n",path);

    if(!obor_pak_path_append(path, sizeof(path), (char *)StrCache_Get(arg->strVal))) return E_FAIL;

    for(i = strlen(path) - 1; i >= 0; i--)
    {

        if(path[i] == '/' || path[i] == '\\')
        {
            path[i] = 0;
            // Make folder if it doesn't exist
#ifndef DC
            dirExists(path, 1);
#endif
            path[i] = '/';
            break;
        }
    }

    //printf("save path: %s", path);
    handle = fopen(path, "wb");
    if(handle == NULL)
    {
        return E_FAIL;
    }
    fwrite(filestreams[filestreamindex].buf, 1, strlen(filestreams[filestreamindex].buf), handle);

    // add blank line so it can be read successfully
    if(!bytearg) fwrite("\r\n", 1, 2, handle);
    fclose(handle);

    return S_OK;
}

HRESULT openbor_closefilestream(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG filestreamindex;
    ScriptVariant *arg = NULL;

    *pretvar = NULL;

    if(paramCount < 1)
    {
        return E_FAIL;
    }

    arg = varlist[0];
    if(FAILED(ScriptVariant_IntegerValue(arg, &filestreamindex)))
    {
        return E_FAIL;
    }


    if(filestreams[filestreamindex].buf)
    {
        free(filestreams[filestreamindex].buf);
        filestreams[filestreamindex].buf = NULL;
    }
    return S_OK;
}
//damageentity(entity, other, force, drop, type)
HRESULT openbor_damageentity(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    entity *ent = NULL;
    entity *other = NULL;
    entity *temp = NULL;
    LONG force, drop, type;
    s_collision_attack atk;

    if(paramCount < 1)
    {
        printf("Function requires at least 1 parameter.\n");
        goto de_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)0;

    ent = (entity *)(varlist[0])->ptrVal; //retrieve the entity
    if(!ent)
    {
        printf("Invalid entity parameter.\n");
        goto de_error;
    }

    other = ent;

    if(paramCount >= 2 && varlist[1]->ptrVal)
    {
        other = (entity *)(varlist[1])->ptrVal;
    }

    if(paramCount >= 3 )
    {
        force = (LONG)1;
        drop = (LONG)0;
        type = (LONG)ATK_NORMAL;

        if(FAILED(ScriptVariant_IntegerValue((varlist[2]), &force)))
        {
            printf("Wrong force value.\n");
            goto de_error;
        }

        if(paramCount >= 4)
        {
            if(FAILED(ScriptVariant_IntegerValue((varlist[3]), &drop)))
            {
                printf("Wrong drop value.\n");
                goto de_error;
            }
        }
        if(paramCount >= 5)
        {
            if(FAILED(ScriptVariant_IntegerValue((varlist[4]), &type)))
            {
                printf("Wrong type value.\n");
                goto de_error;
            }
        }

        atk = emptyattack;
        atk.attack_force = force;
        atk.attack_drop = drop;
        if(drop)
        {
            atk.dropv.y = (float)DEFAULT_ATK_DROPV_Y;
            atk.dropv.x = (float)DEFAULT_ATK_DROPV_X;
            atk.dropv.z = (float)DEFAULT_ATK_DROPV_Z;
        }
        atk.attack_type = type;
    }
    else
    {
        atk = attack;
    }

    if(!ent->takedamage)
    {
        {
            int64_t remaining = (int64_t)ent->health - (int64_t)atk.attack_force;
            ent->health = remaining < INT_MIN ? INT_MIN : remaining > INT_MAX ? INT_MAX : (int)remaining;
        }
        if(ent->health <= 0)
        {
            kill(ent);
        }
        (*pretvar)->lVal = (LONG)1;
    }
    else
    {
        temp = self;
        self = ent;
        (*pretvar)->lVal = (LONG)self->takedamage(other, &atk);
        self = temp;
    }
    return S_OK;

de_error:
    *pretvar = NULL;
    return E_FAIL;
}

static entity *obor_computed_damage_actor(const ScriptVariant *argument)
{
    extern entity **ent_list;
    extern int ent_list_size;

    if(argument->vt != VT_PTR || !argument->ptrVal || !ent_list || ent_list_size <= 0 ||
       (size_t)ent_list_size > obor_allocation_size(ent_list) / sizeof(*ent_list))
    {
        return NULL;
    }
    for(int i = 0; i < ent_list_size; ++i)
    {
        if(ent_list[i] == argument->ptrVal)
        {
            return ent_list[i];
        }
    }
    return NULL;
}

// getcomputeddamage(defender, attacker, force, drop, type)
HRESULT openbor_getcomputeddamage(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    entity *defender, *previous;
    entity *attacker = NULL;
    LONG force, drop, type = ATK_NORMAL;
    s_collision_attack attack = emptyattack;

    if(!obor_has_computed_damage())
    {
        goto computed_damage_error;
    }
    if(paramCount < 3)
    {
        printf("Function requires at least 3 parameters.\n");
        goto computed_damage_error;
    }
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = 0;
    defender = obor_computed_damage_actor(varlist[0]);
    if(!defender)
    {
        printf("Invalid entity parameter.\n");
        goto computed_damage_error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[2], &force)))
    {
        printf("Wrong force value.\n");
        goto computed_damage_error;
    }
    if(paramCount >= 4 && FAILED(ScriptVariant_IntegerValue(varlist[3], &drop)))
    {
        printf("Wrong drop value.\n");
        goto computed_damage_error;
    }
    if(paramCount >= 5 && FAILED(ScriptVariant_IntegerValue(varlist[4], &type)))
    {
        printf("Wrong type value.\n");
        goto computed_damage_error;
    }
    if(type >= 0 && type < max_attack_types)
    {
        attacker = obor_computed_damage_actor(varlist[1]);
        if(!attacker ||
           (size_t)type >= obor_allocation_size(attacker->offense_factors) / sizeof(*attacker->offense_factors) ||
           (size_t)type >= obor_allocation_size(defender->defense) / sizeof(*defender->defense))
        {
            printf("Invalid entity parameter.\n");
            goto computed_damage_error;
        }
    }

    attack.attack_force = force;
    attack.attack_type = type;
    previous = self;
    self = defender;
    (*pretvar)->lVal = obor_force_damage(attacker, &attack);
    self = previous;
    return S_OK;

computed_damage_error:
    *pretvar = NULL;
    return E_FAIL;
}

//killentity(entity)
HRESULT openbor_killentity(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    entity *ent = NULL;

    if(paramCount < 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    ent = (entity *)(varlist[0])->ptrVal; //retrieve the entity
    if(ent == NULL)
    {
        (*pretvar)->lVal = (LONG)0;
        return S_OK;
    }
    kill(ent);
    (*pretvar)->lVal = (LONG)1;
    return S_OK;
}

// dograb
// Damon V. Caskey
// 2013-12-30
//
// Enables initiation of the engine's default grab state between attacker and
// target entities.
//
// dograb(ptr attacker, ptr target, int adjust);
//
// attacker: Entity attempting grab.
// target: Entity to be grabbed.
// adjustcheck: Engine's dograb adjust check flag.
HRESULT openbor_dograb(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME           "dograb(void attacker, void target, int adjust)"
    #define ARG_MINIMUM         2
    #define ARG_ATTACKER        0
    #define ARG_TARGET          1
    #define ARG_ADJUST          2
    #define ARG_ADJUST_DEFAULT  1

    int adjust          = ARG_ADJUST_DEFAULT;   // dograb adjust check.
    int result          = S_OK;                 // Function pass/fail result.
    entity *attacker    = NULL;                 // Attacker entity (attempting grab)
    entity *target      = NULL;                 // Target entity (to be grabbed)

    ScriptVariant_Clear(*pretvar);

    // Validate there are at least two parameters (attacker and target entities).
    if(paramCount < ARG_MINIMUM)
    {
        goto error_local;
    }

    // Get adjust check.
    if(paramCount > ARG_ADJUST)
    {
        ScriptVariant_IntegerValue(varlist[ARG_ADJUST], &adjust);
    }

    // Get attacking and target entity.
    attacker = (entity *)(varlist[ARG_ATTACKER])->ptrVal;
    target = (entity *)(varlist[ARG_TARGET])->ptrVal;

    // Validate entities.
    if(!attacker && !target)
    {
        goto error_local;
    }

    // Execute engine's grab function.
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = dograb(attacker, target, adjust);

    return result;

    // Error trap
    error_local:

    result = E_FAIL;
    printf("\nYou must provide valid entity handles and an optional adjustment: " SELF_NAME);

    // Return result.
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_ATTACKER
    #undef ARG_TARGET
    #undef ARG_ADJUST
    #undef ARG_ADJUST_DEFAULT
}

//findtarget(entity, int animation);
HRESULT openbor_findtarget(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i = 0;
    entity *ent = NULL;
    entity *tempself, *target;
    LONG anim = -1;

    if(paramCount > 2)
    {
        ScriptVariant_IntegerValue(varlist[2], &i);
    }

    if(paramCount < 1)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);

    ent = (entity *)(varlist[0])->ptrVal; //retrieve the entity
    if(!ent)
    {
        ScriptVariant_Clear(*pretvar);
        return S_OK;
    }
    if(paramCount > 1 && FAILED(ScriptVariant_IntegerValue(varlist[1], &anim)))
    {
        return E_FAIL;
    }
    tempself = self;
    self = ent;
    target = normal_find_target((int)anim, i);
    if(!target)
    {
        ScriptVariant_Clear(*pretvar);
    }
    else
    {
        (*pretvar)->ptrVal = (VOID *)target;
    }
    self = tempself;
    return S_OK;
}

//checkrange(entity, target, int ani);
HRESULT openbor_checkrange(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    entity *ent = NULL, *target = NULL;
    LONG ani = 0;
    extern int max_animations;

    if(paramCount < 2)
    {
        goto checkrange_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    if(varlist[0]->vt != VT_PTR || varlist[1]->vt != VT_PTR)
    {
        goto checkrange_error;
    }

    ent = (entity *)(varlist[0])->ptrVal; //retrieve the entity
    target = (entity *)(varlist[1])->ptrVal; //retrieve the target

    if(!ent || !target)
    {
        goto checkrange_error;
    }

    if(paramCount > 2 && FAILED(ScriptVariant_IntegerValue(varlist[2], &ani)))
    {
        goto checkrange_error;
    }
    else if(paramCount <= 2)
    {
        ani = ent->animnum;
    }

    if(ani < 0 || ani >= max_animations)
    {
        printf("Animation id out of range: %d / %d.\n", (int)ani, max_animations);
        goto checkrange_error;
    }

    (*pretvar)->lVal = check_range(ent, target, ani);

    return S_OK;

checkrange_error:
    printf("Function needs at least 2 valid entity handles, the third parameter is optional: checkrange(entity, target, int animnum)\n");
    *pretvar = NULL;
    return E_FAIL;
}

//clearspawnentry();
HRESULT openbor_clearspawnentry(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    *pretvar = NULL;
    memset(&spawnentry, 0, sizeof(spawnentry));
    spawnentry.index = spawnentry.itemindex = spawnentry.weaponindex = -1;
    return S_OK;
}

// ===== setspawnentry =====
enum setspawnentry_enum
{
    _sse_2phealth,
    _sse_2pitem,
    _sse_3phealth,
    _sse_3pitem,
    _sse_4phealth,
    _sse_4pitem,
    _sse_aggression,
    _sse_alias,
    _sse_alpha,
    _sse_boss,
    _sse_coords,
    _sse_credit,
    _sse_dying,
    _sse_flip,
    _sse_health,
    _sse_item,
    _sse_itemalias,
    _sse_itemhealth,
    _sse_itemmap,
    _sse_map,
    _sse_mp,
    _sse_multiple,
    _sse_name,
    _sse_nolife,
    _sse_parent,
    _sse_type,
    _sse_weapon,
    _sse_the_end,
};

int mapstrings_setspawnentry(ScriptVariant **varlist, int paramCount)
{
    char *propname;
    int prop;
    static const char *proplist[] =
    {
        "2phealth",
        "2pitem",
        "3phealth",
        "3pitem",
        "4phealth",
        "4pitem",
        "aggression",
        "alias",
        "alpha",
        "boss",
        "coords",
        "credit",
        "dying",
        "flip",
        "health",
        "item",
        "itemalias",
        "itemhealth",
        "itemmap",
        "map",
        "mp",
        "multiple",
        "name",
        "nolife",
        "parent",
        "type",
        "weapon",
    };

    MAPSTRINGS(varlist[0], proplist, _sse_the_end,
               "Property name '%s' is not supported by setspawnentry.\n");

    return 1;
}

//setspawnentry(propname, value1[, value2, value3, ...]);
HRESULT openbor_setspawnentry(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    s_model *tempmodel;
    DOUBLE dbltemp;
    int temp, prop;
    ScriptVariant *arg = NULL;

    if(paramCount < 2)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)1;

    mapstrings_setspawnentry(varlist, paramCount);
    if(varlist[0]->vt != VT_INTEGER)
    {
        if(varlist[0]->vt != VT_STR)
        {
            printf("You must give a string value for spawn entry property name.\n");
        }
        *pretvar = NULL;
        return E_FAIL;
    }

    prop = varlist[0]->lVal;

    arg = varlist[1];

    switch(prop)
    {
    case _sse_name:
        if(arg->vt != VT_STR)
        {
            printf("You must use a string value for spawn entry's name property: function setspawnentry.\n");
            goto setspawnentry_error;
        }
        spawnentry.model = findmodel((char *)StrCache_Get(arg->strVal));
        break;
    case _sse_alias:
        if(arg->vt != VT_STR)
        {
            goto setspawnentry_error;
        }
        obor_profile_copy_name(spawnentry.alias, StrCache_Get(arg->strVal));
        break;
    case _sse_item:
        if(arg->vt != VT_STR)
        {
            goto setspawnentry_error;
        }
        spawnentry.itemmodel = findmodel((char *)StrCache_Get(arg->strVal));
        spawnentry.item = spawnentry.itemmodel->name;
        spawnentry.itemindex = get_cached_model_index(spawnentry.item);
        spawnentry.itemplayer_count = 0;
        break;
    case _sse_2pitem:
        if(arg->vt != VT_STR)
        {
            goto setspawnentry_error;
        }
        tempmodel = findmodel((char *)StrCache_Get(arg->strVal));
        if(!tempmodel)
        {
            spawnentry.item = NULL;
        }
        else
        {
            spawnentry.item = tempmodel->name;
        }
        spawnentry.itemplayer_count = 1;
        break;
    case _sse_3pitem:
        if(arg->vt != VT_STR)
        {
            goto setspawnentry_error;
        }
        spawnentry.itemmodel = findmodel((char *)StrCache_Get(arg->strVal));
        spawnentry.itemplayer_count = 2;
        break;
    case _sse_4pitem:
        if(arg->vt != VT_STR)
        {
            goto setspawnentry_error;
        }
        spawnentry.itemmodel = findmodel((char *)StrCache_Get(arg->strVal));
        spawnentry.itemplayer_count = 3;
        break;
    case _sse_health:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.health[0] = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_itemhealth:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.itemhealth = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_itemalias:
        if(arg->vt != VT_STR)
        {
            return E_FAIL;
        }
        obor_profile_copy_name(spawnentry.itemalias, StrCache_Get(arg->strVal));
        break;
    case _sse_2phealth:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.health[1] = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_3phealth:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.health[2] = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_4phealth:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.health[3] = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_coords:
        temp = 1;
        if(SUCCEEDED(ScriptVariant_DecimalValue(arg, &dbltemp)))
        {
            spawnentry.position.x = (float)dbltemp;
        }
        else
        {
            temp = 0;
        }
        if(paramCount >= 3 && temp)
        {
            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &dbltemp)))
            {
                spawnentry.position.z = (float)dbltemp;
            }
            else
            {
                temp = 0;
            }
        }
        if(paramCount >= 4 && temp)
        {
            if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
            {
                spawnentry.position.y = (float)dbltemp;
            }
            else
            {
                temp = 0;
            }
        }
        (*pretvar)->lVal = (LONG)temp;
        break;
    case _sse_mp:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.mp = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_map:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.colourmap = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_itemmap:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.itemmap = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_alpha:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.alpha = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_multiple:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.multiple = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_dying:
        temp = 1;
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.dying = (int)ltemp;
        }
        else
        {
            temp = 0;
        }
        if(paramCount >= 3 && temp)
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
            {
                spawnentry.per1 = (int)ltemp;
            }
            else
            {
                temp = 0;
            }
        }
        if(paramCount >= 4 && temp)
        {
            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[3], &ltemp)))
            {
                spawnentry.per2 = (int)ltemp;
            }
            else
            {
                temp = 0;
            }
        }
        (*pretvar)->lVal = (LONG)temp;
        break;
    case _sse_nolife:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.nolife = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_boss:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.boss = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_flip:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.flip = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_credit:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.credit = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_aggression:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.aggression = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_parent:
        if( arg->vt == VT_PTR ) //&& arg->vt != VT_EMPTY
        {
            spawnentry.parent = (entity *)arg->ptrVal;
        }
        else
        {
            (*pretvar)->ptrVal = (VOID *)NULL;
        }
        break;
    case _sse_type:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            spawnentry.entitytype = (int)ltemp;
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        break;
    case _sse_weapon:
        if(arg->vt != VT_STR)
        {
            goto setspawnentry_error;
        }
        spawnentry.weaponmodel = findmodel((char *)StrCache_Get(arg->strVal));
        break;
    default:
        //printf("Property name '%s' is not supported by setspawnentry.\n", propname);
        goto setspawnentry_error;
    }

    return S_OK;
setspawnentry_error:
    *pretvar = NULL;
    return E_FAIL;
}

//spawn();
HRESULT openbor_spawn(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    entity *ent;

    if(spawnentry.boss && level)
    {
        level->bosses++;
    }

    ent = smartspawn(&spawnentry);

    if(ent)
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *) ent;
    }
    else
    {
        ScriptVariant_Clear(*pretvar);
    }

    return S_OK;
}

//entity * projectile([0/1], char *name, float x, float z, float a, int direction, int pytype, int type, int map);
HRESULT openbor_projectile(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE temp = 0;
    LONG ltemp = 0;
    entity *ent;
    char *name = NULL;
    float x = 0, z = 0, a = 0;
    int direction = DIRECTION_LEFT;
    int type = 0;
    int ptype = 0;
    int map = 0;

    int relative;

    if(paramCount >= 1 && varlist[0]->vt == VT_INTEGER && varlist[0]->lVal)
    {
        relative = 1;
        paramCount--;
        varlist++;
    }
    else
    {
        relative = 0;
    }

    if(paramCount >= 1 && varlist[0]->vt == VT_STR)
    {
        name = StrCache_Get(varlist[0]->strVal);
    }

    if(paramCount >= 2 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[1], &temp)))
    {
        x = (float)temp;
    }
    else if(relative)
    {
        x = 0;
    }
    else
    {
        x = self->position.x;
    }
    if(paramCount >= 3 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[2], &temp)))
    {
        z = (float)temp;
    }
    else if(relative)
    {
        z = 0;
    }
    else
    {
        z = self->position.z;
    }
    if(paramCount >= 4 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &temp)))
    {
        a = (float)temp;
    }
    else if(relative)
    {
        a  = self->animation->projectile.position.y;
    }
    else
    {
        a = self->position.y + self->animation->projectile.position.y;
    }
    if(paramCount >= 5 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[4], &ltemp)))
    {
        direction = (int)ltemp;
    }
    else if(relative)
    {
        direction  = DIRECTION_RIGHT;
    }
    else
    {
        direction = self->direction;
    }
    if(paramCount >= 6 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[5], &ltemp)))
    {
        ptype = (int)ltemp;
    }
    if(paramCount >= 7 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[6], &ltemp)))
    {
        type = (int)ltemp;
    }
    if(paramCount >= 8 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[7], &ltemp)))
    {
        map = (int)ltemp;
    }

    if(relative)
    {
        if(self->direction == DIRECTION_RIGHT)
        {
            x += self->position.x;
        }
        else
        {
            x = self->position.x - x;
            direction = !direction;
        }
        z += self->position.z;
        a += self->position.y;
    }

    switch(type)
    {
    default:
    case 0:
        ent = knife_spawn(name, -1, x, z, a, direction, ptype, map);
        break;
    case 1:
        ent = bomb_spawn(name, -1, x, z, a, direction, map);
        break;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *) ent;

    return S_OK;
}


// ===== openborconstant =====
#define IICMPCONST(x) \
if(stricmp(#x, constname)==0) {\
	v.lVal = (LONG)x;\
}


#define ICMPCONST(x) \
else if(stricmp(#x, constname)==0) {\
	v.lVal = (LONG)x;\
}

#define ICMPCOLLISIONPROP(x, slot) \
else if((obor_profile_build < 4905 || (slot) >= 0) && stricmp(#x, constname) == 0) \
{ \
    v.lVal = obor_profile_build < 4905 ? (LONG)(x) : (slot); \
}

#define ICMPCONST_4905(name, slot) \
else if(obor_profile_build >= 4905 && stricmp(#name, constname) == 0) \
{ \
    v.lVal = (slot); \
}

#define ICMPSUBTYPE(x) \
else if(stricmp(#x, constname)==0) {\
    v.lVal = obor_profile_subtype_value(x);\
}

#define ICMPSCONSTA(x, y) \
else if(strnicmp(constname, #x, sizeof(#x)-1)==0 && constname[sizeof(#x)-1] >= '1' && constname[sizeof(#x)-1]<='9') \
{ \
	v.lVal = (LONG)(y[atoi(constname+(sizeof(#x)-1))-1]);\
}

#define ICMPSCONSTB(x, y) \
else if(strnicmp(constname, #x, sizeof(#x)-1)==0 && constname[sizeof(#x)-1] >= '1' && constname[sizeof(#x)-1]<='9') \
{ \
	v.lVal = (LONG)(y[atoi(constname+(sizeof(#x)-1))+STA_ATKS-1]);\
}

#define ICMPSCONSTC(x) \
else if(strnicmp(constname, #x, sizeof(#x)-1)==0 && constname[sizeof(#x)-1] >= '1' && constname[sizeof(#x)-1]<='9') \
{ \
	v.lVal = (LONG)(atoi(constname+(sizeof(#x)-1))+STA_ATKS-1);\
}

#define ICMPCONST_FROM(x, version) \
else if((obor_profile_build < 4283 || obor_profile_build >= (version)) && stricmp(#x, constname) == 0) \
{ \
    v.lVal = (LONG)(x); \
}

#define ICMPCONST_LATE_LEVEL(x, version) \
else if(obor_profile_build >= (version) && !stricmp(#x, constname)) \
{ \
    v.lVal = (LONG)(x); \
}

#define ICMPSBACKCONST(x, table) \
else if((obor_profile_build < 4283 || obor_profile_build >= 4414) && \
        strnicmp(constname, #x, sizeof(#x) - 1) == 0 && \
        constname[sizeof(#x) - 1] >= '1' && constname[sizeof(#x) - 1] <= '9') \
{ \
    long slot = strtol(constname + sizeof(#x) - 1, NULL, 10); \
    if((table) && slot > 0 && slot <= max_attack_types) \
        v.lVal = (LONG)(table)[slot - 1]; \
    else \
        found = FALSE; \
}

#define ICMPANIMPROP(x) \
else if(stricmp(#x, constname) == 0) \
{ \
    v.lVal = (LONG)(x) - (obor_uses_early_animation_properties() && (x) > ANI_PROP_IGNOREATTACKID); \
}

static int obor_set_property_native(int index)
{
    static const int middle_order[] = {
        SET_PROP_CREDITS, SET_PROP_GAME_OVER_SKIP, SET_PROP_HOF_DISABLE,
        SET_PROP_COMPLETE_FLAG, SET_PROP_COMPLETE_SKIP, SET_PROP_CONTINUE_SCORE_TYPE,
        SET_PROP_LEVELSET_COUNT, SET_PROP_LEVELSET_COLLECTION
    };

    if(index < 0 || index >= OBOR_SET_PROP_COUNT) return -1;
    if(obor_profile_build < 4489)
    {
        if(index == 0) return SET_PROP_LEVELSET_COUNT;
        if(index == 1) return SET_PROP_LEVELSET_COLLECTION;
        return -1;
    }
    if(obor_profile_build < 4493 && (unsigned)index < sizeof(middle_order) / sizeof(middle_order[0]))
    {
        return middle_order[index];
    }
    return index;
}

static int obor_lookup_set_property(const char *name, LONG *value)
{
    static const char *const names[] = {
        [SET_PROP_COMPLETE_FLAG] = "SET_PROP_COMPLETE_FLAG",
        [SET_PROP_COMPLETE_SKIP] = "SET_PROP_COMPLETE_SKIP",
        [SET_PROP_CONTINUE_SCORE_TYPE] = "SET_PROP_CONTINUE_SCORE_TYPE",
        [SET_PROP_CREDITS] = "SET_PROP_CREDITS",
        [SET_PROP_GAME_OVER_SKIP] = "SET_PROP_GAME_OVER_SKIP",
        [SET_PROP_HOF_DISABLE] = "SET_PROP_HOF_DISABLE",
        [SET_PROP_LEVELSET_COLLECTION] = "SET_PROP_LEVELSET_COLLECTION",
        [SET_PROP_LEVELSET_COUNT] = "SET_PROP_LEVELSET_COUNT",
        [SET_PROP_LIVES] = "SET_PROP_LIVES",
        [SET_PROP_MP_RECOVER_TYPE] = "SET_PROP_MP_RECOVER_TYPE",
        [SET_PROP_MUSIC_FADE_TIME] = "SET_PROP_MUSIC_FADE_TIME",
        [SET_PROP_MUSIC_OVERLAP] = "SET_PROP_MUSIC_OVERLAP",
        [SET_PROP_NAME] = "SET_PROP_NAME",
        [SET_PROP_PLAYER_MAX] = "SET_PROP_PLAYER_MAX",
        [SET_PROP_SAVE_TYPE] = "SET_PROP_SAVE_TYPE",
        [SET_PROP_SELECT_DISABLE] = "SET_PROP_SELECT_DISABLE",
        [SET_PROP_SELECT_NO_SAME] = "SET_PROP_SELECT_NO_SAME",
    };

    if(obor_profile_build < 4476 || strnicmp(name, "SET_PROP_", sizeof("SET_PROP_") - 1)) return 0;
    for(int index = 0; index < OBOR_SET_PROP_COUNT; ++index)
    {
        int property = obor_set_property_native(index);
        if(property < 0) break;
        const char *label = names[property];
        if(obor_profile_build < 4493)
        {
            if(property == SET_PROP_LEVELSET_COUNT) label = "SET_PROP_LEVELS_COUNT";
            if(property == SET_PROP_LEVELSET_COLLECTION) label = "SET_PROP_LEVELS_HANDLE";
        }
        if(!stricmp(label, name))
        {
            *value = index;
            return 1;
        }
    }
    return 0;
}

/* Canonical property order from 4494. Earlier ordinals are translated below. */
enum
{
    LEVEL_PROP_AUTO_SCROLL_DIRECTION,
    LEVEL_PROP_AUTO_SCROLL_X,
    LEVEL_PROP_AUTO_SCROLL_Y,
    LEVEL_PROP_BASEMAP_COLLECTION,
    LEVEL_PROP_BASEMAP_COUNT,
    LEVEL_PROP_BOSS_COUNT,
    LEVEL_PROP_BOSS_MUSIC_NAME,
    LEVEL_PROP_BOSS_MUSIC_OFFSET,
    LEVEL_PROP_BOSS_SLOW,
    LEVEL_PROP_CAMERA_OFFSET_X,
    LEVEL_PROP_CAMERA_OFFSET_Z,
    LEVEL_PROP_COMPLETE_FORCE,
    LEVEL_PROP_DAMAGE_FROM_ENEMY,
    LEVEL_PROP_DAMAGE_FROM_PLAYER,
    LEVEL_PROP_FACING,
    LEVEL_PROP_GRAVITY,
    LEVEL_PROP_HOLE_COLLECTION,
    LEVEL_PROP_HOLE_COUNT,
    LEVEL_PROP_LAYER_BACKGROUND_DEFAULT_HANDLE,
    LEVEL_PROP_LAYER_BACKGROUND_COLLECTION,
    LEVEL_PROP_LAYER_BACKGROUND_COUNT,
    LEVEL_PROP_LAYER_COLLECTION,
    LEVEL_PROP_LAYER_COUNT,
    LEVEL_PROP_LAYER_FOREGROUND_COLLECTION,
    LEVEL_PROP_LAYER_FOREGROUND_COUNT,
    LEVEL_PROP_LAYER_FRONTPANEL_COLLECTION,
    LEVEL_PROP_LAYER_FRONTPANEL_COUNT,
    LEVEL_PROP_LAYER_GENERIC_COLLECTION,
    LEVEL_PROP_LAYER_GENERIC_COUNT,
    LEVEL_PROP_LAYER_PANEL_COLLECTION,
    LEVEL_PROP_LAYER_PANEL_COUNT,
    LEVEL_PROP_LAYER_REF_COLLECTION,
    LEVEL_PROP_LAYER_REF_COUNT,
    LEVEL_PROP_LAYER_WATER_COLLECTION,
    LEVEL_PROP_LAYER_WATER_COUNT,
    LEVEL_PROP_MAX_FALL_VELOCITY,
    LEVEL_PROP_MAX_TOSS_VELOCITY,
    LEVEL_PROP_MIRROR,
    LEVEL_PROP_NAME,
    LEVEL_PROP_PALETTE_BLENDING_COLLECTION,
    LEVEL_PROP_PALETTE_COLLECTION,
    LEVEL_PROP_PALETTE_COUNT,
    LEVEL_PROP_POSITION_X,
    LEVEL_PROP_QUAKE,
    LEVEL_PROP_QUAKE_TIME,
    LEVEL_PROP_ROCKING,
    LEVEL_PROP_SCRIPT_LEVEL_END,
    LEVEL_PROP_SCRIPT_LEVEL_START,
    LEVEL_PROP_SCRIPT_KEY,
    LEVEL_PROP_SCRIPT_UPDATE,
    LEVEL_PROP_SCRIPT_UPDATED,
    LEVEL_PROP_SCROLL_DIRECTION,
    LEVEL_PROP_SCROLL_VELOCITY,
    LEVEL_PROP_SIZE_X,
    LEVEL_PROP_SPAWN_COLLECTION,
    LEVEL_PROP_SPAWN_COUNT,
    LEVEL_PROP_SPAWN_PLAYER_COLLECTION,
    LEVEL_PROP_SPECIAL_DISABLE,
    LEVEL_PROP_TEXT_OBJECT_COLLECTION,
    LEVEL_PROP_TEXT_OBJECT_COUNT,
    LEVEL_PROP_TIME_ADVANCE,
    LEVEL_PROP_TIME_DISPLAY,
    LEVEL_PROP_TIME_RESET,
    LEVEL_PROP_TIME_SET,
    LEVEL_PROP_TYPE,
    LEVEL_PROP_WAITING,
    LEVEL_PROP_WALL_COLLECTION,
    LEVEL_PROP_WALL_COUNT,
    LEVEL_PROP_WEAPON,
    LEVEL_PROP_GAMEOVER,
    OBOR_LEVEL_PROP_COUNT
};

static int obor_level_property_native(int index)
{
    static const int early_order[] = {
        LEVEL_PROP_AUTO_SCROLL_X,
        LEVEL_PROP_AUTO_SCROLL_Y,
        LEVEL_PROP_BASEMAP_COUNT,
        LEVEL_PROP_BASEMAP_COLLECTION,
        LEVEL_PROP_LAYER_BACKGROUND_COUNT,
        LEVEL_PROP_LAYER_BACKGROUND_COLLECTION,
        LEVEL_PROP_CAMERA_OFFSET_X,
        LEVEL_PROP_CAMERA_OFFSET_Z,
        LEVEL_PROP_GRAVITY,
        LEVEL_PROP_HOLE_COUNT,
        LEVEL_PROP_HOLE_COLLECTION,
        LEVEL_PROP_LAYER_COUNT,
        LEVEL_PROP_LAYER_COLLECTION,
        LEVEL_PROP_MAX_FALL_VELOCITY,
        LEVEL_PROP_MAX_TOSS_VELOCITY,
        LEVEL_PROP_QUAKE,
        LEVEL_PROP_PALETTE_COUNT,
        LEVEL_PROP_PALETTE_COLLECTION,
        LEVEL_PROP_ROCKING,
        LEVEL_PROP_SCROLL_VELOCITY,
        LEVEL_PROP_TYPE,
        LEVEL_PROP_WALL_COUNT,
        LEVEL_PROP_WALL_COLLECTION,
    };
    static const int order_4490_middle[] = {
        LEVEL_PROP_QUAKE,
        LEVEL_PROP_QUAKE_TIME,
        LEVEL_PROP_PALETTE_BLENDING_COLLECTION,
        LEVEL_PROP_PALETTE_COLLECTION,
        LEVEL_PROP_PALETTE_COUNT,
        LEVEL_PROP_POSITION_X,
    };
    static const int order_4490_end[] = {
        LEVEL_PROP_TIME_SET,
        LEVEL_PROP_TIME_DISPLAY,
        LEVEL_PROP_TIME_RESET,
        LEVEL_PROP_TYPE,
        LEVEL_PROP_WALL_COLLECTION,
        LEVEL_PROP_WALL_COUNT,
        LEVEL_PROP_WEAPON,
        LEVEL_PROP_WAITING,
    };

    if(index < 0 || index >= OBOR_LEVEL_PROP_COUNT) return -1;
    if(obor_profile_build >= 4642 && obor_profile_build <= 4905)
    {
        if(index == LEVEL_PROP_DAMAGE_FROM_ENEMY) return LEVEL_PROP_GAMEOVER;
        return index > LEVEL_PROP_DAMAGE_FROM_ENEMY ? index - 1 : index;
    }
    if(index == LEVEL_PROP_GAMEOVER) return -1;
    if(obor_profile_build < 4490)
    {
        if(obor_profile_build < 4474) return -1;
        if(index >= 4)
        {
            // The background collection appeared before the count.
            if(obor_profile_build < 4486) index += 2;
            else if(obor_profile_build < 4489) ++index;
        }
        return index < (int)(sizeof(early_order) / sizeof(early_order[0])) ? early_order[index] : -1;
    }
    if(obor_profile_build < 4494)
    {
        if(index == 5) return LEVEL_PROP_LAYER_BACKGROUND_COLLECTION;
        if(index == 6) return LEVEL_PROP_LAYER_BACKGROUND_COUNT;
        if(index >= 7 && index <= 20) return index - 2;
    }
    if(obor_profile_build == 4490)
    {
        if(index >= 39 && index <= 44) return order_4490_middle[index - 39];
        if(index >= 61) return order_4490_end[index - 61];
    }
    return index;
}

static int obor_lookup_level_property(const char *name, LONG *value)
{
    static const char *const names[OBOR_LEVEL_PROP_COUNT] = {
        [LEVEL_PROP_AUTO_SCROLL_DIRECTION] = "LEVEL_PROP_AUTO_SCROLL_DIRECTION",
        [LEVEL_PROP_AUTO_SCROLL_X] = "LEVEL_PROP_AUTO_SCROLL_X",
        [LEVEL_PROP_AUTO_SCROLL_Y] = "LEVEL_PROP_AUTO_SCROLL_Y",
        [LEVEL_PROP_BASEMAP_COLLECTION] = "LEVEL_PROP_BASEMAP_COLLECTION",
        [LEVEL_PROP_BASEMAP_COUNT] = "LEVEL_PROP_BASEMAP_COUNT",
        [LEVEL_PROP_BOSS_COUNT] = "LEVEL_PROP_BOSS_COUNT",
        [LEVEL_PROP_BOSS_MUSIC_NAME] = "LEVEL_PROP_BOSS_MUSIC_NAME",
        [LEVEL_PROP_BOSS_MUSIC_OFFSET] = "LEVEL_PROP_BOSS_MUSIC_OFFSET",
        [LEVEL_PROP_BOSS_SLOW] = "LEVEL_PROP_BOSS_SLOW",
        [LEVEL_PROP_CAMERA_OFFSET_X] = "LEVEL_PROP_CAMERA_OFFSET_X",
        [LEVEL_PROP_CAMERA_OFFSET_Z] = "LEVEL_PROP_CAMERA_OFFSET_Z",
        [LEVEL_PROP_COMPLETE_FORCE] = "LEVEL_PROP_COMPLETE_FORCE",
        [LEVEL_PROP_DAMAGE_FROM_ENEMY] = "LEVEL_PROP_DAMAGE_FROM_ENEMY",
        [LEVEL_PROP_DAMAGE_FROM_PLAYER] = "LEVEL_PROP_DAMAGE_FROM_PLAYER",
        [LEVEL_PROP_FACING] = "LEVEL_PROP_FACING",
        [LEVEL_PROP_GRAVITY] = "LEVEL_PROP_GRAVITY",
        [LEVEL_PROP_HOLE_COLLECTION] = "LEVEL_PROP_HOLE_COLLECTION",
        [LEVEL_PROP_HOLE_COUNT] = "LEVEL_PROP_HOLE_COUNT",
        [LEVEL_PROP_LAYER_BACKGROUND_DEFAULT_HANDLE] = "LEVEL_PROP_LAYER_BACKGROUND_DEFAULT_HANDLE",
        [LEVEL_PROP_LAYER_BACKGROUND_COLLECTION] = "LEVEL_PROP_LAYER_BACKGROUND_COLLECTION",
        [LEVEL_PROP_LAYER_BACKGROUND_COUNT] = "LEVEL_PROP_LAYER_BACKGROUND_COUNT",
        [LEVEL_PROP_LAYER_COLLECTION] = "LEVEL_PROP_LAYER_COLLECTION",
        [LEVEL_PROP_LAYER_COUNT] = "LEVEL_PROP_LAYER_COUNT",
        [LEVEL_PROP_LAYER_FOREGROUND_COLLECTION] = "LEVEL_PROP_LAYER_FOREGROUND_COLLECTION",
        [LEVEL_PROP_LAYER_FOREGROUND_COUNT] = "LEVEL_PROP_LAYER_FOREGROUND_COUNT",
        [LEVEL_PROP_LAYER_FRONTPANEL_COLLECTION] = "LEVEL_PROP_LAYER_FRONTPANEL_COLLECTION",
        [LEVEL_PROP_LAYER_FRONTPANEL_COUNT] = "LEVEL_PROP_LAYER_FRONTPANEL_COUNT",
        [LEVEL_PROP_LAYER_GENERIC_COLLECTION] = "LEVEL_PROP_LAYER_GENERIC_COLLECTION",
        [LEVEL_PROP_LAYER_GENERIC_COUNT] = "LEVEL_PROP_LAYER_GENERIC_COUNT",
        [LEVEL_PROP_LAYER_PANEL_COLLECTION] = "LEVEL_PROP_LAYER_PANEL_COLLECTION",
        [LEVEL_PROP_LAYER_PANEL_COUNT] = "LEVEL_PROP_LAYER_PANEL_COUNT",
        [LEVEL_PROP_LAYER_REF_COLLECTION] = "LEVEL_PROP_LAYER_REF_COLLECTION",
        [LEVEL_PROP_LAYER_REF_COUNT] = "LEVEL_PROP_LAYER_REF_COUNT",
        [LEVEL_PROP_LAYER_WATER_COLLECTION] = "LEVEL_PROP_LAYER_WATER_COLLECTION",
        [LEVEL_PROP_LAYER_WATER_COUNT] = "LEVEL_PROP_LAYER_WATER_COUNT",
        [LEVEL_PROP_MAX_FALL_VELOCITY] = "LEVEL_PROP_MAX_FALL_VELOCITY",
        [LEVEL_PROP_MAX_TOSS_VELOCITY] = "LEVEL_PROP_MAX_TOSS_VELOCITY",
        [LEVEL_PROP_MIRROR] = "LEVEL_PROP_MIRROR",
        [LEVEL_PROP_NAME] = "LEVEL_PROP_NAME",
        [LEVEL_PROP_PALETTE_BLENDING_COLLECTION] = "LEVEL_PROP_PALETTE_BLENDING_COLLECTION",
        [LEVEL_PROP_PALETTE_COLLECTION] = "LEVEL_PROP_PALETTE_COLLECTION",
        [LEVEL_PROP_PALETTE_COUNT] = "LEVEL_PROP_PALETTE_COUNT",
        [LEVEL_PROP_POSITION_X] = "LEVEL_PROP_POSITION_X",
        [LEVEL_PROP_QUAKE] = "LEVEL_PROP_QUAKE",
        [LEVEL_PROP_QUAKE_TIME] = "LEVEL_PROP_QUAKE_TIME",
        [LEVEL_PROP_ROCKING] = "LEVEL_PROP_ROCKING",
        [LEVEL_PROP_SCRIPT_LEVEL_END] = "LEVEL_PROP_SCRIPT_LEVEL_END",
        [LEVEL_PROP_SCRIPT_LEVEL_START] = "LEVEL_PROP_SCRIPT_LEVEL_START",
        [LEVEL_PROP_SCRIPT_KEY] = "LEVEL_PROP_SCRIPT_KEY",
        [LEVEL_PROP_SCRIPT_UPDATE] = "LEVEL_PROP_SCRIPT_UPDATE",
        [LEVEL_PROP_SCRIPT_UPDATED] = "LEVEL_PROP_SCRIPT_UPDATED",
        [LEVEL_PROP_SCROLL_DIRECTION] = "LEVEL_PROP_SCROLL_DIRECTION",
        [LEVEL_PROP_SCROLL_VELOCITY] = "LEVEL_PROP_SCROLL_VELOCITY",
        [LEVEL_PROP_SIZE_X] = "LEVEL_PROP_SIZE_X",
        [LEVEL_PROP_SPAWN_COLLECTION] = "LEVEL_PROP_SPAWN_COLLECTION",
        [LEVEL_PROP_SPAWN_COUNT] = "LEVEL_PROP_SPAWN_COUNT",
        [LEVEL_PROP_SPAWN_PLAYER_COLLECTION] = "LEVEL_PROP_SPAWN_PLAYER_COLLECTION",
        [LEVEL_PROP_SPECIAL_DISABLE] = "LEVEL_PROP_SPECIAL_DISABLE",
        [LEVEL_PROP_TEXT_OBJECT_COLLECTION] = "LEVEL_PROP_TEXT_OBJECT_COLLECTION",
        [LEVEL_PROP_TEXT_OBJECT_COUNT] = "LEVEL_PROP_TEXT_OBJECT_COUNT",
        [LEVEL_PROP_TIME_ADVANCE] = "LEVEL_PROP_TIME_ADVANCE",
        [LEVEL_PROP_TIME_DISPLAY] = "LEVEL_PROP_TIME_DISPLAY",
        [LEVEL_PROP_TIME_RESET] = "LEVEL_PROP_TIME_RESET",
        [LEVEL_PROP_TIME_SET] = "LEVEL_PROP_TIME_SET",
        [LEVEL_PROP_TYPE] = "LEVEL_PROP_TYPE",
        [LEVEL_PROP_WAITING] = "LEVEL_PROP_WAITING",
        [LEVEL_PROP_WALL_COLLECTION] = "LEVEL_PROP_WALL_COLLECTION",
        [LEVEL_PROP_WALL_COUNT] = "LEVEL_PROP_WALL_COUNT",
        [LEVEL_PROP_WEAPON] = "LEVEL_PROP_WEAPON",
    };
    static const struct
    {
        const char *singular;
        const char *plural;
    } early_names[] = {
        [LEVEL_PROP_BASEMAP_COLLECTION] = {"LEVEL_PROP_BASEMAP_HANDLE", "LEVEL_PROP_BASEMAPS_HANDLE"},
        [LEVEL_PROP_BASEMAP_COUNT] = {"LEVEL_PROP_BASEMAP_COUNT", "LEVEL_PROP_BASEMAPS_COUNT"},
        [LEVEL_PROP_HOLE_COLLECTION] = {"LEVEL_PROP_HOLE_HANDLE", "LEVEL_PROP_HOLES_HANDLE"},
        [LEVEL_PROP_HOLE_COUNT] = {"LEVEL_PROP_HOLE_COUNT", "LEVEL_PROP_HOLES_COUNT"},
        [LEVEL_PROP_LAYER_BACKGROUND_COLLECTION] = {NULL, "LEVEL_PROP_BGLAYERS_HANDLE"},
        [LEVEL_PROP_LAYER_BACKGROUND_COUNT] = {NULL, "LEVEL_PROP_BGLAYERS_COUNT"},
        [LEVEL_PROP_LAYER_COLLECTION] = {"LEVEL_PROP_LAYER_HANDLE", "LEVEL_PROP_LAYERS_HANDLE"},
        [LEVEL_PROP_LAYER_COUNT] = {"LEVEL_PROP_LAYER_COUNT", "LEVEL_PROP_LAYERS_COUNT"},
        [LEVEL_PROP_PALETTE_COLLECTION] = {"LEVEL_PROP_PALETTE_HANDLE", "LEVEL_PROP_PALETTES_HANDLE"},
        [LEVEL_PROP_PALETTE_COUNT] = {"LEVEL_PROP_PALETTE_COUNT", "LEVEL_PROP_PALETTES_COUNT"},
        [LEVEL_PROP_WALL_COLLECTION] = {"LEVEL_PROP_WALL_HANDLE", "LEVEL_PROP_WALLS_HANDLE"},
        [LEVEL_PROP_WALL_COUNT] = {"LEVEL_PROP_WALL_COUNT", "LEVEL_PROP_WALLS_COUNT"},
        [OBOR_LEVEL_PROP_COUNT - 1] = {NULL, NULL}
    };

    if(obor_profile_build < 4474 || strnicmp(name, "LEVEL_PROP_", sizeof("LEVEL_PROP_") - 1)) return 0;
    for(int index = 0; index < OBOR_LEVEL_PROP_COUNT; ++index)
    {
        int property = obor_level_property_native(index);
        if(property < 0) break;
        const char *label = names[property];
        if(obor_profile_build < 4490 && early_names[property].plural)
        {
            label = obor_profile_build < 4476 ? early_names[property].singular : early_names[property].plural;
        }
        else if(obor_profile_build < 4494)
        {
            if(property == LEVEL_PROP_LAYER_BACKGROUND_COLLECTION) label = "LEVEL_PROP_BGLAYER_COLLECTION";
            if(property == LEVEL_PROP_LAYER_BACKGROUND_COUNT) label = "LEVEL_PROP_BGLAYER_COUNT";
        }
        if(label && !stricmp(label, name))
        {
            *value = index;
            return 1;
        }
    }
    return 0;
}

static int obor_level_property_has_early_getter(int property)
{
    switch(property)
    {
    case LEVEL_PROP_AUTO_SCROLL_X:
    case LEVEL_PROP_AUTO_SCROLL_Y:
    case LEVEL_PROP_BASEMAP_COUNT:
    case LEVEL_PROP_BASEMAP_COLLECTION:
    case LEVEL_PROP_LAYER_BACKGROUND_COUNT:
    case LEVEL_PROP_LAYER_BACKGROUND_COLLECTION:
    case LEVEL_PROP_CAMERA_OFFSET_X:
    case LEVEL_PROP_CAMERA_OFFSET_Z:
    case LEVEL_PROP_GRAVITY:
    case LEVEL_PROP_HOLE_COUNT:
    case LEVEL_PROP_HOLE_COLLECTION:
    case LEVEL_PROP_LAYER_COUNT:
    case LEVEL_PROP_LAYER_COLLECTION:
    case LEVEL_PROP_MAX_FALL_VELOCITY:
    case LEVEL_PROP_MAX_TOSS_VELOCITY:
    case LEVEL_PROP_QUAKE:
    case LEVEL_PROP_PALETTE_COUNT:
    case LEVEL_PROP_PALETTE_COLLECTION:
    case LEVEL_PROP_ROCKING:
    case LEVEL_PROP_SCROLL_VELOCITY:
    case LEVEL_PROP_TYPE:
    case LEVEL_PROP_WALL_COUNT:
    case LEVEL_PROP_WALL_COLLECTION:
    case LEVEL_PROP_NAME:
        return 1;
    default:
        return 0;
    }
}

int mapstrings_transconst(ScriptVariant **varlist, int paramCount)
{
    char *constname = NULL;
    int found = TRUE;
    ScriptVariant v;

    if(paramCount < 1)
    {
        return 1;
    }

    if(varlist[0]->vt == VT_STR)
    {
        ScriptVariant_Init(&v);
        ScriptVariant_ChangeType(&v, VT_INTEGER);
        constname = (char *)StrCache_Get(varlist[0]->strVal);

        IICMPCONST(COMPATIBLEVERSION)
        else if(obor_lookup_set_property(constname, &v.lVal)) { /* The value is mapped above. */ }
        else if(obor_lookup_level_property(constname, &v.lVal)) { /* The value is mapped above. */ }
        ICMPCONST_LATE_LEVEL(BOSS_SLOW_OFF, 4502)
        ICMPCONST_LATE_LEVEL(BOSS_SLOW_ON, 4502)
        ICMPCONST_LATE_LEVEL(DAMAGE_FROM_ENEMY_OFF, 4504)
        ICMPCONST_LATE_LEVEL(DAMAGE_FROM_ENEMY_ON, 4504)
        ICMPCONST_LATE_LEVEL(DAMAGE_FROM_PLAYER_OFF, 4504)
        ICMPCONST_LATE_LEVEL(DAMAGE_FROM_PLAYER_ON, 4504)
        ICMPCONST_LATE_LEVEL(SCROLL_BACK, 4501)
        ICMPCONST(DIRECTION_LEFT)
        ICMPCONST(DIRECTION_RIGHT)
        ICMPCONST(DIRECTION_ADJUST_LEFT)
        ICMPCONST(DIRECTION_ADJUST_NONE)
        ICMPCONST(DIRECTION_ADJUST_OPPOSITE)
        ICMPCONST(DIRECTION_ADJUST_RIGHT)
        ICMPCONST(DIRECTION_ADJUST_SAME)
        ICMPCONST(VT_EMPTY)
        ICMPCONST(VT_STR)
        ICMPCONST(VT_INTEGER)
        ICMPCONST(VT_DECIMAL)
        ICMPCONST(VT_PTR)
        ICMPCONST(MIN_INT)
        ICMPCONST(MAX_INT)
        ICMPCONST(PIXEL_8)
        ICMPCONST(PIXEL_x8)
        ICMPCONST(PIXEL_16)
        ICMPCONST(PIXEL_32)
        ICMPCONST(CV_SAVED_GAME)
        ICMPCONST(CV_HIGH_SCORE)
        ICMPCONST(THINK_SPEED)
        ICMPCONST(COUNTER_SPEED)
        ICMPCONST(MAX_ENTS)
        else if(stricmp(constname, "MAX_NAME_LEN")==0)
        {
            v.lVal = (LONG)obor_profile_name_limit();
        }
        ICMPCONST(MAX_SPECIALS)
        ICMPCONST(MAX_ATCHAIN)
        ICMPCONST(MAX_ATTACKS)
        ICMPCONST(MAX_FOLLOWS)
        ICMPCONST(MAX_PLAYERS)
        else if(stricmp(constname, "MAX_ARG_LEN")==0)
        {
            v.lVal = (LONG)((obor_profile_build >= 4283 && obor_profile_build < 4429) ? 511 : MAX_ARG_LEN);
        }
        ICMPCONST(FLAG_ESC)
        ICMPCONST(FLAG_START)
        ICMPCONST(FLAG_MOVELEFT)
        ICMPCONST(FLAG_MOVERIGHT)
        ICMPCONST(FLAG_MOVEUP)
        ICMPCONST(FLAG_MOVEDOWN)
        ICMPCONST(FLAG_ATTACK)
        ICMPCONST(FLAG_ATTACK2)
        ICMPCONST(FLAG_ATTACK3)
        ICMPCONST(FLAG_ATTACK4)
        ICMPCONST(FLAG_JUMP)
        ICMPCONST(FLAG_SPECIAL)
        ICMPCONST(FLAG_SCREENSHOT)
        ICMPCONST(FLAG_ANYBUTTON)
        ICMPCONST(FLAG_FORWARD)
        ICMPCONST(FLAG_BACKWARD)
        ICMPCONST(SDID_MOVEUP)
        ICMPCONST(SDID_MOVEDOWN)
        ICMPCONST(SDID_MOVELEFT)
        ICMPCONST(SDID_MOVERIGHT)
        ICMPCONST(SDID_SPECIAL)
        ICMPCONST(SDID_ATTACK)
        ICMPCONST(SDID_ATTACK2)
        ICMPCONST(SDID_ATTACK3)
        ICMPCONST(SDID_ATTACK4)
        ICMPCONST(SDID_JUMP)
        ICMPCONST(SDID_START)
        ICMPCONST(SDID_SCREENSHOT)
        ICMPCONST(TYPE_NONE)
        ICMPCONST(TYPE_PLAYER)
        ICMPCONST(TYPE_ENEMY)
        ICMPCONST(TYPE_ITEM)
        ICMPCONST(TYPE_OBSTACLE)
        ICMPCONST(TYPE_STEAMER)
        ICMPCONST(TYPE_SHOT)
        ICMPCONST(TYPE_TRAP)
        ICMPCONST(TYPE_TEXTBOX)
        ICMPCONST(TYPE_ENDLEVEL)
        ICMPCONST(TYPE_NPC)
        ICMPCONST(TYPE_PANEL)
        ICMPCONST(TYPE_MAX)
        ICMPCONST(TYPE_RESERVED)
        ICMPCONST(SUBTYPE_NONE)
        ICMPCONST(SUBTYPE_BIKER)
        ICMPCONST(SUBTYPE_NOTGRAB)
        ICMPCONST(SUBTYPE_ARROW)
        else if((obor_profile_build < 4283 || obor_profile_build >= 4414) &&
                stricmp("SUBTYPE_BOOMERANG", constname) == 0)
        {
            v.lVal = SUBTYPE_BOOMERANG;
        }
        ICMPSUBTYPE(SUBTYPE_TOUCH)
        ICMPSUBTYPE(SUBTYPE_WEAPON)
        ICMPSUBTYPE(SUBTYPE_NOSKIP)
        ICMPSUBTYPE(SUBTYPE_FLYDIE)
        ICMPSUBTYPE(SUBTYPE_BOTH)
        ICMPSUBTYPE(SUBTYPE_PROJECTILE)
        ICMPSUBTYPE(SUBTYPE_FOLLOW)
        ICMPSUBTYPE(SUBTYPE_CHASE)
        ICMPCONST(AIMOVE1_NORMAL)
        ICMPCONST(AIMOVE1_CHASE)
        ICMPCONST(AIMOVE1_CHASEZ)
        ICMPCONST(AIMOVE1_CHASEX)
        ICMPCONST(AIMOVE1_AVOID)
        ICMPCONST(AIMOVE1_AVOIDZ)
        ICMPCONST(AIMOVE1_AVOIDX)
        ICMPCONST(AIMOVE1_WANDER)
        ICMPCONST(AIMOVE1_NOMOVE)
        ICMPCONST(AIMOVE1_BIKER)
        ICMPCONST(AIMOVE1_STAR)
        ICMPCONST(AIMOVE1_ARROW)
        ICMPCONST(AIMOVE1_BOMB)
        ICMPCONST_FROM(AIMOVE1_BOOMERANG, 4414)
        ICMPCONST(AIMOVE2_NORMAL)
        ICMPCONST(AIMOVE2_IGNOREHOLES)
        ICMPCONST_FROM(AIMOVE2_NOTARGETIDLE, 4417)
        ICMPCONST(AIATTACK1_NORMAL)
        ICMPCONST(AIATTACK1_LONG)
        ICMPCONST(AIATTACK1_MELEE)
        ICMPCONST(AIATTACK1_NOATTACK)
        ICMPCONST(AIATTACK1_ALWAYS)
        ICMPCONST(AIATTACK2_NORMAL)
        ICMPCONST(AIATTACK2_DODGE)
        ICMPCONST(AIATTACK2_DODGEMOVE)
        ICMPCONST(FRONTPANEL_Z)
        ICMPCONST(HOLE_Z)
        ICMPCONST(NEONPANEL_Z)
        ICMPCONST(SHADOW_Z)
        ICMPCONST(SCREENPANEL_Z)
        ICMPCONST(PANEL_Z)
        ICMPCONST(MIRROR_Z)
        ICMPCONST(PIT_DEPTH)
        ICMPCONST(P2_STATS_DIST)
        ICMPCONST(CONTACT_DIST_H)
        ICMPCONST(CONTACT_DIST_V)
        ICMPCONST(GRAB_DIST)
        ICMPCONST(GRAB_STALL)
        ICMPCONST(ATK_NORMAL)
        ICMPCONST(ATK_NORMAL2)
        ICMPCONST(ATK_NORMAL3)
        ICMPCONST(ATK_NORMAL4)
        ICMPCONST(ATK_BLAST)
        ICMPCONST(ATK_BURN)
        ICMPCONST(ATK_FREEZE)
        ICMPCONST(ATK_SHOCK)
        ICMPCONST(ATK_STEAL)
        ICMPCONST(ATK_NORMAL5)
        ICMPCONST(ATK_NORMAL6)
        ICMPCONST(ATK_NORMAL7)
        ICMPCONST(ATK_NORMAL8)
        ICMPCONST(ATK_NORMAL9)
        ICMPCONST(ATK_NORMAL10)
        ICMPCONST(ATK_ITEM)
        ICMPCONST(ATK_LAND)
        ICMPCONST(ATK_PIT)
        ICMPCONST(ATK_LIFESPAN)
        ICMPCONST(ATK_TIMEOVER)
        ICMPCONST(SCROLL_RIGHT)
        ICMPCONST(SCROLL_DOWN)
        ICMPCONST(SCROLL_LEFT)
        ICMPCONST(SCROLL_UP)
        ICMPCONST(SCROLL_BOTH)
        ICMPCONST(SCROLL_LEFTRIGHT)
        ICMPCONST(SCROLL_RIGHTLEFT)
        ICMPCONST(SCROLL_INWARD)
        ICMPCONST(SCROLL_OUTWARD)
        ICMPCONST(SCROLL_INOUT)
        ICMPCONST(SCROLL_OUTIN)
        ICMPCONST(SCROLL_UPWARD)
        ICMPCONST(SCROLL_DOWNWARD)
        ICMPCONST(ANI_IDLE)
        ICMPCONST(ANI_WALK)
        ICMPCONST(ANI_JUMP)
        ICMPCONST(ANI_LAND)
        ICMPCONST(ANI_PAIN)
        ICMPCONST(ANI_FALL)
        ICMPCONST(ANI_RISE)
        ICMPCONST(ANI_UPPER)
        ICMPCONST(ANI_BLOCK)
        ICMPCONST(ANI_JUMPATTACK)
        ICMPCONST(ANI_JUMPATTACK2)
        ICMPCONST(ANI_GET)
        ICMPCONST(ANI_GRAB)
        ICMPCONST(ANI_GRABATTACK)
        ICMPCONST(ANI_GRABATTACK2)
        ICMPCONST(ANI_THROW)
        ICMPCONST(ANI_SPECIAL)
        ICMPCONST(ANI_SPAWN)
        ICMPCONST(ANI_DIE)
        ICMPCONST(ANI_PICK)
        ICMPCONST(ANI_JUMPATTACK3)
        ICMPCONST(ANI_UP)
        ICMPCONST(ANI_DOWN)
        ICMPCONST(ANI_SHOCK)
        ICMPCONST(ANI_BURN)
        ICMPCONST(ANI_SHOCKPAIN)
        ICMPCONST(ANI_BURNPAIN)
        ICMPCONST(ANI_GRABBED)
        ICMPCONST(ANI_SPECIAL2)
        ICMPCONST(ANI_RUN)
        ICMPCONST(ANI_RUNATTACK)
        ICMPCONST(ANI_RUNJUMPATTACK)
        ICMPCONST(ANI_ATTACKUP)
        ICMPCONST(ANI_ATTACKDOWN)
        ICMPCONST(ANI_ATTACKFORWARD)
        ICMPCONST(ANI_ATTACKBACKWARD)
        ICMPCONST(ANI_RISEATTACK)
        ICMPCONST(ANI_DODGE)
        ICMPCONST(ANI_ATTACKBOTH)
        ICMPCONST(ANI_GRABFORWARD)
        ICMPCONST(ANI_GRABFORWARD2)
        ICMPCONST(ANI_JUMPFORWARD)
        ICMPCONST(ANI_GRABDOWN)
        ICMPCONST(ANI_GRABDOWN2)
        ICMPCONST(ANI_GRABUP)
        ICMPCONST(ANI_GRABUP2)
        ICMPCONST(ANI_SELECT)
        ICMPCONST(ANI_DUCK)
        ICMPCONST(ANI_FAINT)
        ICMPCONST(ANI_CANT)
        ICMPCONST(ANI_THROWATTACK)
        ICMPCONST(ANI_CHARGEATTACK)
        ICMPCONST(ANI_JUMPCANT)
        ICMPCONST(ANI_JUMPSPECIAL)
        ICMPCONST(ANI_BURNDIE)
        ICMPCONST(ANI_SHOCKDIE)
        ICMPCONST(ANI_PAIN2)
        ICMPCONST(ANI_PAIN3)
        ICMPCONST(ANI_PAIN4)
        ICMPCONST(ANI_FALL2)
        ICMPCONST(ANI_FALL3)
        ICMPCONST(ANI_FALL4)
        ICMPCONST(ANI_DIE2)
        ICMPCONST(ANI_DIE3)
        ICMPCONST(ANI_DIE4)
        ICMPCONST(ANI_CHARGE)
        ICMPCONST(ANI_BACKWALK)
        ICMPCONST(ANI_SLEEP)
        ICMPCONST(ANI_PAIN5)
        ICMPCONST(ANI_PAIN6)
        ICMPCONST(ANI_PAIN7)
        ICMPCONST(ANI_PAIN8)
        ICMPCONST(ANI_PAIN9)
        ICMPCONST(ANI_PAIN10)
        ICMPCONST(ANI_FALL5)
        ICMPCONST(ANI_FALL6)
        ICMPCONST(ANI_FALL7)
        ICMPCONST(ANI_FALL8)
        ICMPCONST(ANI_FALL9)
        ICMPCONST(ANI_FALL10)
        ICMPCONST(ANI_DIE5)
        ICMPCONST(ANI_DIE6)
        ICMPCONST(ANI_DIE7)
        ICMPCONST(ANI_DIE8)
        ICMPCONST(ANI_DIE9)
        ICMPCONST(ANI_DIE10)
        ICMPCONST(ANI_TURN)
        ICMPCONST(ANI_RESPAWN)
        ICMPCONST(ANI_FORWARDJUMP)
        ICMPCONST(ANI_RUNJUMP)
        ICMPCONST(ANI_JUMPLAND)
        ICMPCONST(ANI_JUMPDELAY)
        ICMPCONST(ANI_HITWALL)
        ICMPCONST(ANI_GRABBACKWARD)
        ICMPCONST(ANI_GRABBACKWARD2)
        ICMPCONST(ANI_GRABWALK)
        ICMPCONST(ANI_GRABBEDWALK)
        ICMPCONST(ANI_GRABWALKUP)
        ICMPCONST(ANI_GRABBEDWALKUP)
        ICMPCONST(ANI_GRABWALKDOWN)
        ICMPCONST(ANI_GRABBEDWALKDOWN)
        ICMPCONST(ANI_GRABTURN)
        ICMPCONST(ANI_GRABBEDTURN)
        ICMPCONST(ANI_GRABBACKWALK)
        ICMPCONST(ANI_GRABBEDBACKWALK)
        ICMPCONST(ANI_SLIDE)
        ICMPCONST(ANI_RUNSLIDE)
        ICMPCONST(ANI_BLOCKPAIN)
        ICMPCONST(ANI_DUCKATTACK)
        else if(stricmp("MAX_ANIS", constname) == 0)
        {
            v.lVal = obor_profile_animation_base();
        }
        ICMPCONST(PLAYER_MIN_Z)
        ICMPCONST(PLAYER_MAX_Z)
        ICMPCONST(BGHEIGHT)
        ICMPCONST(MAX_WALL_HEIGHT)
        ICMPCONST(SAMPLE_GO)
        ICMPCONST(SAMPLE_BEAT)
        ICMPCONST(SAMPLE_BLOCK)
        ICMPCONST(SAMPLE_INDIRECT)
        ICMPCONST(SAMPLE_GET)
        ICMPCONST(SAMPLE_GET2)
        ICMPCONST(SAMPLE_FALL)
        ICMPCONST(SAMPLE_JUMP)
        ICMPCONST(SAMPLE_PUNCH)
        ICMPCONST(SAMPLE_1UP)
        ICMPCONST(SAMPLE_TIMEOVER)
        ICMPCONST(SAMPLE_BEEP)
        ICMPCONST(SAMPLE_BEEP2)
        ICMPCONST(SAMPLE_BIKE)
        ICMPCONST(ANI_RISE2)
        ICMPCONST(ANI_RISE3)
        ICMPCONST(ANI_RISE4)
        ICMPCONST(ANI_RISE5)
        ICMPCONST(ANI_RISE6)
        ICMPCONST(ANI_RISE7)
        ICMPCONST(ANI_RISE8)
        ICMPCONST(ANI_RISE9)
        ICMPCONST(ANI_RISE10)
        ICMPCONST(ANI_RISEB)
        ICMPCONST(ANI_RISES)
        ICMPCONST(ANI_BLOCKPAIN2)
        ICMPCONST(ANI_BLOCKPAIN3)
        ICMPCONST(ANI_BLOCKPAIN4)
        ICMPCONST(ANI_BLOCKPAIN5)
        ICMPCONST(ANI_BLOCKPAIN6)
        ICMPCONST(ANI_BLOCKPAIN7)
        ICMPCONST(ANI_BLOCKPAIN8)
        ICMPCONST(ANI_BLOCKPAIN9)
        ICMPCONST(ANI_BLOCKPAIN10)
        ICMPCONST(ANI_BLOCKPAINB)
        ICMPCONST(ANI_BLOCKPAINS)
        ICMPCONST(ANI_CHIPDEATH)
        ICMPCONST(ANI_GUARDBREAK)
        ICMPCONST(ANI_RISEATTACK2)
        ICMPCONST(ANI_RISEATTACK3)
        ICMPCONST(ANI_RISEATTACK4)
        ICMPCONST(ANI_RISEATTACK5)
        ICMPCONST(ANI_RISEATTACK6)
        ICMPCONST(ANI_RISEATTACK7)
        ICMPCONST(ANI_RISEATTACK8)
        ICMPCONST(ANI_RISEATTACK9)
        ICMPCONST(ANI_RISEATTACK10)
        ICMPCONST(ANI_RISEATTACKB)
        ICMPCONST(ANI_RISEATTACKS)
        ICMPCONST(ANI_SLIDE)
        ICMPCONST(ANI_RUNSLIDE)
        ICMPCONST(ANI_DUCKATTACK)
        ICMPCONST(ANI_WALKOFF)
        ICMPCONST(ANI_FREESPECIAL)
        ICMPCONST(ANI_ATTACK)
        ICMPCONST_FROM(ANI_BACKPAIN, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN2, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN3, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN4, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN5, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN6, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN7, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN8, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN9, 4414)
        ICMPCONST_FROM(ANI_BACKPAIN10, 4414)
        ICMPCONST_FROM(ANI_BACKFALL, 4414)
        ICMPCONST_FROM(ANI_BACKFALL2, 4414)
        ICMPCONST_FROM(ANI_BACKFALL3, 4414)
        ICMPCONST_FROM(ANI_BACKFALL4, 4414)
        ICMPCONST_FROM(ANI_BACKFALL5, 4414)
        ICMPCONST_FROM(ANI_BACKFALL6, 4414)
        ICMPCONST_FROM(ANI_BACKFALL7, 4414)
        ICMPCONST_FROM(ANI_BACKFALL8, 4414)
        ICMPCONST_FROM(ANI_BACKFALL9, 4414)
        ICMPCONST_FROM(ANI_BACKFALL10, 4414)
        ICMPCONST_FROM(ANI_BACKDIE, 4414)
        ICMPCONST_FROM(ANI_BACKDIE2, 4414)
        ICMPCONST_FROM(ANI_BACKDIE3, 4414)
        ICMPCONST_FROM(ANI_BACKDIE4, 4414)
        ICMPCONST_FROM(ANI_BACKDIE5, 4414)
        ICMPCONST_FROM(ANI_BACKDIE6, 4414)
        ICMPCONST_FROM(ANI_BACKDIE7, 4414)
        ICMPCONST_FROM(ANI_BACKDIE8, 4414)
        ICMPCONST_FROM(ANI_BACKDIE9, 4414)
        ICMPCONST_FROM(ANI_BACKDIE10, 4414)
        else if((obor_profile_build < 4283 || obor_profile_build >= 4414) &&
                stricmp("ANI_BACKRUN", constname) == 0)
        {
            v.lVal = ANI_BACKRUN;
        }
        ICMPCONST_FROM(ANI_HITOBSTACLE, 4414)
        ICMPCONST_FROM(ANI_HITPLATFORM, 4414)
        ICMPCONST(ANI_HITWALL)
        else if((obor_profile_build < 4283 || obor_profile_build >= 4414) &&
                stricmp("ANI_GETBOOMERANG", constname) == 0)
        {
            v.lVal = ANI_GETBOOMERANG;
        }
        else if((obor_profile_build < 4283 || obor_profile_build >= 4414) &&
                stricmp("ANI_GETBOOMERANGINAIR", constname) == 0)
        {
            v.lVal = ANI_GETBOOMERANGINAIR;
        }


        // for the extra animation ids
        ICMPSCONSTC(ATK_NORMAL)
        ICMPSCONSTA(ANI_DOWN, animdowns)
        ICMPSCONSTA(ANI_UP, animups)
        ICMPSCONSTA(ANI_BACKWALK, animbackwalks)
        ICMPSCONSTA(ANI_WALK, animwalks)
        ICMPSCONSTA(ANI_IDLE, animidles)
        ICMPSCONSTB(ANI_FALL, animfalls)
        ICMPSCONSTB(ANI_RISE, animrises)
        ICMPSCONSTB(ANI_RISEATTACK, animriseattacks)
        ICMPSCONSTB(ANI_PAIN, animpains)
        ICMPSCONSTB(ANI_DIE, animdies)
        ICMPSCONSTA(ANI_ATTACK, animattacks)
        ICMPSCONSTA(ANI_FOLLOW, animfollows)
        ICMPSCONSTA(ANI_FREESPECIAL, animspecials)
        ICMPSBACKCONST(ANI_BACKPAIN, animbackpains)
        ICMPSBACKCONST(ANI_BACKFALL, animbackfalls)
        ICMPSBACKCONST(ANI_BACKDIE, animbackdies)

        // Animation properties.
        ICMPANIMPROP(ANI_PROP_ANIMHITS)
        ICMPANIMPROP(ANI_PROP_ANTIGRAV)
        ICMPANIMPROP(ANI_PROP_ATTACK)
        ICMPANIMPROP(ANI_PROP_COLLISIONONE)
        ICMPANIMPROP(ANI_PROP_BODY_COLLISION)
        ICMPANIMPROP(ANI_PROP_BOUNCE)
        ICMPANIMPROP(ANI_PROP_CANCEL)
        ICMPANIMPROP(ANI_PROP_CHARGETIME)
        ICMPANIMPROP(ANI_PROP_COUNTERRANGE)
        ICMPANIMPROP(ANI_PROP_DELAY)
        ICMPANIMPROP(ANI_PROP_DRAWMETHODS)
        ICMPANIMPROP(ANI_PROP_DROPFRAME)
        ICMPANIMPROP(ANI_PROP_DROPV)
        ICMPANIMPROP(ANI_PROP_ENERGYCOST)
        ICMPANIMPROP(ANI_PROP_FLIPFRAME)
        ICMPANIMPROP(ANI_PROP_FOLLOWUP)
        ICMPANIMPROP(ANI_PROP_IDLE)
        ICMPANIMPROP(ANI_PROP_INDEX)
        ICMPANIMPROP(ANI_PROP_JUMPFRAME)
        ICMPANIMPROP(ANI_PROP_LANDFRAME)
        ICMPANIMPROP(ANI_PROP_LOOP)
        ICMPANIMPROP(ANI_PROP_MODEL_INDEX)
        ICMPANIMPROP(ANI_PROP_MOVE)
        ICMPANIMPROP(ANI_PROP_NUMFRAMES)
        ICMPANIMPROP(ANI_PROP_OFFSET)
        ICMPANIMPROP(ANI_PROP_PLATFORM)
        ICMPANIMPROP(ANI_PROP_PROJECTILE)
        ICMPANIMPROP(ANI_PROP_QUAKEFRAME)
        ICMPANIMPROP(ANI_PROP_RANGE)
        ICMPANIMPROP(ANI_PROP_SHADOW)
        ICMPANIMPROP(ANI_PROP_SIZE)
        ICMPANIMPROP(ANI_PROP_SOUNDTOPLAY)
        ICMPANIMPROP(ANI_PROP_SPAWNFRAME)
        ICMPANIMPROP(ANI_PROP_SPRITE)
        ICMPANIMPROP(ANI_PROP_SPRITEA)
        ICMPANIMPROP(ANI_PROP_SUBENTITY)
        ICMPANIMPROP(ANI_PROP_SUMMONFRAME)
        ICMPANIMPROP(ANI_PROP_SYNC)
        ICMPANIMPROP(ANI_PROP_UNSUMMONFRAME)
        ICMPANIMPROP(ANI_PROP_VULNERABLE)
        ICMPANIMPROP(ANI_PROP_WEAPONFRAME)

        // Attack properties
        ICMPCOLLISIONPROP(ATTACK_PROP_BLOCK_COST, 0)
        ICMPCOLLISIONPROP(ATTACK_PROP_BLOCK_PENETRATE, 1)
        ICMPCOLLISIONPROP(ATTACK_PROP_COUNTER, 3)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_FORCE, 4)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_LAND_FORCE, 5)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_LAND_MODE, 6)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_LETHAL_DISABLE, 7)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_RECURSIVE_FORCE, 8)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_RECURSIVE_INDEX, 9)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_RECURSIVE_MODE, 10)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_RECURSIVE_TIME_RATE, 11)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_RECURSIVE_TIME_EXPIRE, 12)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_STEAL, 13)
        ICMPCOLLISIONPROP(ATTACK_PROP_DAMAGE_TYPE, 14)
        ICMPCOLLISIONPROP(ATTACK_PROP_EFFECT_BLOCK_FLASH, 15)
        ICMPCOLLISIONPROP(ATTACK_PROP_EFFECT_BLOCK_SOUND, 16)
        ICMPCOLLISIONPROP(ATTACK_PROP_EFFECT_HIT_FLASH, 17)
        ICMPCOLLISIONPROP(ATTACK_PROP_EFFECT_HIT_FLASH_DISABLE, 18)
        ICMPCOLLISIONPROP(ATTACK_PROP_EFFECT_HIT_SOUND, 19)
        ICMPCOLLISIONPROP(ATTACK_PROP_GROUND, 21)
        ICMPCOLLISIONPROP(ATTACK_PROP_MAP_INDEX, 22)
        ICMPCOLLISIONPROP(ATTACK_PROP_MAP_TIME, 23)
        ICMPCOLLISIONPROP(ATTACK_PROP_POSITION_X, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_POSITION_Y, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_FALL_FORCE, 24)
        ICMPCONST_4905(ATTACK_PROP_REACTION_FALL_VELOCITY, 25)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_FALL_VELOCITY_X, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_FALL_VELOCITY_Y, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_FALL_VELOCITY_Z, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_FREEZE_MODE, 26)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_FREEZE_TIME, 27)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_INVINCIBLE_TIME, 28)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_REPOSITION_DIRECTION, 29)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_REPOSITION_DISTANCE, 30)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_REPOSITION_MODE, 31)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_PAIN_SKIP, 32)
        ICMPCOLLISIONPROP(ATTACK_PROP_REACTION_PAUSE_TIME, 33)
        ICMPCOLLISIONPROP(ATTACK_PROP_SEAL_COST, 34)
        ICMPCOLLISIONPROP(ATTACK_PROP_SEAL_TIME, 35)
        ICMPCOLLISIONPROP(ATTACK_PROP_SIZE_X, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_SIZE_Y, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_SIZE_Z_1, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_SIZE_Z_2, -1)
        ICMPCOLLISIONPROP(ATTACK_PROP_STAYDOWN_RISE, 36)
        ICMPCOLLISIONPROP(ATTACK_PROP_STAYDOWN_RISEATTACK, 37)
        ICMPCOLLISIONPROP(ATTACK_PROP_TAG, 38)

        // Collision coordinate constants. The 4905 script registry has no coordinate accessors.
        ICMPCONST_4905(COLLISION_COORDINATES_PROP_DEPTH_BACKGROUND, 0)
        ICMPCONST_4905(COLLISION_COORDINATES_PROP_DEPTH_FOREGROUND, 1)
        ICMPCONST_4905(COLLISION_COORDINATES_PROP_HEIGHT, 2)
        ICMPCONST_4905(COLLISION_COORDINATES_PROP_WIDTH, 3)
        ICMPCONST_4905(COLLISION_COORDINATES_PROP_X, 4)
        ICMPCONST_4905(COLLISION_COORDINATES_PROP_Y, 5)

        // Body Collision (bbox) properties.
        ICMPCONST_4905(BODY_COLLISION_PROP_COORDINATES, 0)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_DEFENSE, 1)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_POSITION_X, -1)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_POSISTION_Y, -1)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_SIZE_X, -1)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_SIZE_Y, -1)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_SIZE_Z_1, -1)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_SIZE_Z_2, -1)
        ICMPCOLLISIONPROP(BODY_COLLISION_PROP_TAG, 2)

        // Porting
        ICMPCONST_FROM(PORTING_ANDROID, 4347)
        ICMPCONST_FROM(PORTING_DARWIN, 4347)
        ICMPCONST_FROM(PORTING_DREAMCAST, 4347)
        ICMPCONST_FROM(PORTING_GPX2, 4347)
        ICMPCONST_FROM(PORTING_LINUX, 4347)
        ICMPCONST_FROM(PORTING_OPENDINGUX, 4347)
        ICMPCONST_FROM(PORTING_PSP, 4347)
        ICMPCONST_FROM(PORTING_UNKNOWN, 4347)
        ICMPCONST_FROM(PORTING_WII, 4347)
        ICMPCONST_FROM(PORTING_WINDOWS, 4347)
        ICMPCONST_FROM(PORTING_WIZ, 4347)
        ICMPCONST_FROM(PORTING_XBOX, 4349)

        else
        {
            found = FALSE;
        }

        if(found)
        {
            ScriptVariant_Copy(varlist[0], &v);
        }
        else
        {
            ScriptVariant_Clear(&v);
            printf("Can't find openbor constant '%s' \n", constname);
        }

        return found;
    }

    return 1;
}
//openborconstant(constname);
//translate a constant by string, used to retrieve a constant or macro of openbor
HRESULT openbor_transconst(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    static char buf[128];
    if(paramCount < 1)
    {
        goto transconst_error;
    }

    //if(varlist[0]->vt == VT_INTEGER) printf("debug: mapstring for openborconstant works!\n");

    mapstrings_transconst(varlist, paramCount);

    if(varlist[0]->vt == VT_INTEGER) // return value already determined by mapstrings
    {
        ScriptVariant_Copy((*pretvar), varlist[0]);
        return S_OK;
    }

transconst_error:
    ScriptVariant_ToString(varlist[0], buf);
    printf("Can't translate constant %s\n", buf);
    *pretvar = NULL;
    return E_FAIL;
}

//int rgbcolor(int r, int g, int b);
HRESULT openbor_rgbcolor(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG r, g, b;

    if(paramCount != 3)
    {
        goto rgbcolor_error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &r)))
    {
        goto rgbcolor_error;    // decimal/integer value for red?
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[1], &g)))
    {
        goto rgbcolor_error;    // decimal/integer value for green?
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[2], &b)))
    {
        goto rgbcolor_error;    // decimal/integer value for blue?
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = _makecolour(r, g, b);
    return S_OK;

rgbcolor_error:
    *pretvar = NULL;
    return E_FAIL;
}

// ===== playerkeys =====
enum playerkeys_enum
{
    _pk_anybutton,
    _pk_attack,
    _pk_attack2,
    _pk_attack3,
    _pk_attack4,
    _pk_esc,
    _pk_jump,
    _pk_movedown,
    _pk_moveleft,
    _pk_moveright,
    _pk_moveup,
    _pk_screenshot,
    _pk_special,
    _pk_start,
    _pk_the_end,
};

int mapstrings_playerkeys(ScriptVariant **varlist, int paramCount)
{
    char *propname = NULL;
    int i, prop;

    static const char *proplist[] = // for args 2+
    {
        "anybutton",
        "attack",
        "attack2",
        "attack3",
        "attack4",
        "esc",
        "jump",
        "movedown",
        "moveleft",
        "moveright",
        "moveup",
        "screenshot",
        "special",
        "start",
    };

    for(i = 2; i < paramCount; i++)
    {
        MAPSTRINGS(varlist[i], proplist, _pk_the_end,
                   "Button name '%s' is not supported by playerkeys.");
    }

    return 1;
}

//playerkeys(playerindex, newkey?, key1, key2, ...);
HRESULT openbor_playerkeys(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    int index, newkey;
    int i;
    u32 keys;
    ScriptVariant *arg = NULL;

    if(paramCount < 3)
    {
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)1;

    mapstrings_playerkeys(varlist, paramCount);

    if(FAILED(ScriptVariant_IntegerValue((varlist[0]), &ltemp)))
    {
        index = 0;
    }
    else
    {
        index = (int)ltemp;
    }

    if(SUCCEEDED(ScriptVariant_IntegerValue((varlist[1]), &ltemp)))
    {
        newkey = (int)ltemp;
    }
    else
    {
        newkey = 0;
    }

    if(newkey == 1)
    {
        keys = player[index].newkeys;
    }
    else if(newkey == 2)
    {
        keys = player[index].releasekeys;
    }
    else
    {
        keys = player[index].keys;
    }

    for(i = 2; i < paramCount; i++)
    {
        arg = varlist[i];
        if(arg->vt == VT_INTEGER)
        {
            switch(arg->lVal)
            {
            case _pk_jump:
                (*pretvar)->lVal = (LONG)(keys & FLAG_JUMP);
                break;
            case _pk_attack:
                (*pretvar)->lVal = (LONG)(keys & FLAG_ATTACK);
                break;
            case _pk_attack2:
                (*pretvar)->lVal = (LONG)(keys & FLAG_ATTACK2);
                break;
            case _pk_attack3:
                (*pretvar)->lVal = (LONG)(keys & FLAG_ATTACK3);
                break;
            case _pk_attack4:
                (*pretvar)->lVal = (LONG)(keys & FLAG_ATTACK4);
                break;
            case _pk_special:
                (*pretvar)->lVal = (LONG)(keys & FLAG_SPECIAL);
                break;
            case _pk_esc:
                (*pretvar)->lVal = (LONG)(keys & FLAG_ESC);
                break;
            case _pk_start:
                (*pretvar)->lVal = (LONG)(keys & FLAG_START);
                break;
            case _pk_moveleft:
                (*pretvar)->lVal = (LONG)(keys & FLAG_MOVELEFT);
                break;
            case _pk_moveright:
                (*pretvar)->lVal = (LONG)(keys & FLAG_MOVERIGHT);
                break;
            case _pk_moveup:
                (*pretvar)->lVal = (LONG)(keys & FLAG_MOVEUP);
                break;
            case _pk_movedown:
                (*pretvar)->lVal = (LONG)(keys & FLAG_MOVEDOWN);
                break;
            case _pk_screenshot:
                (*pretvar)->lVal = (LONG)(keys & FLAG_SCREENSHOT);
                break;
            case _pk_anybutton:
                (*pretvar)->lVal = (LONG)(keys & FLAG_ANYBUTTON);
                break;
            default:
                (*pretvar)->lVal = (LONG)0;
            }
        }
        else
        {
            (*pretvar)->lVal = (LONG)0;
        }
        if(!((*pretvar)->lVal))
        {
            break;
        }
    }

    return S_OK;
}

//playmusic(name, loop)
HRESULT openbor_playmusic(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int loop = 0;
    LONG offset = 0;
    char *thename = NULL;

    *pretvar = NULL;
    if(paramCount < 1)
    {
        sound_close_music();
        return S_OK;
    }
    if(varlist[0]->vt != VT_STR)
    {
        //printf("");
        return E_FAIL;
    }
    thename = StrCache_Get(varlist[0]->strVal);

    if(paramCount > 1)
    {
        loop = (int)ScriptVariant_IsTrue(varlist[1]);
    }

    if(paramCount > 2)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &offset)))
        {
            return E_FAIL;
        }
    }


    music(thename, loop, offset);
    return S_OK;
}

//fademusic(fade, name, loop, offset)
HRESULT openbor_fademusic(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    DOUBLE value = 0;
    LONG values[2] = {0, 0};
    *pretvar = NULL;
    if(paramCount < 1)
    {
        goto fademusic_error;
    }
    if(FAILED(ScriptVariant_DecimalValue(varlist[0], &value)))
    {
        goto fademusic_error;
    }
    musicfade[0] = value;
    musicfade[1] = (float)savedata.musicvol;

    if(paramCount == 4)
    {
        strncpy(musicname, StrCache_Get(varlist[1]->strVal), 128);
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &values[0])))
        {
            goto fademusic_error;
        }
        if(FAILED(ScriptVariant_IntegerValue(varlist[3], &values[1])))
        {
            goto fademusic_error;
        }
        musicloop = values[0];
        musicoffset = values[1];
    }
    return S_OK;

fademusic_error:
    printf("Function requires 1 value, with an optional 3 for music triggering: fademusic_error(float fade, char name, int loop, unsigned long offset)\n");
    return E_FAIL;
}

//setmusicvolume(left, right)
HRESULT openbor_setmusicvolume(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG channels[2];

    if(paramCount < 1)
    {
        return S_OK;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[0], channels)))
    {
        goto setmusicvolume_error;
    }

    if(paramCount > 1)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[1], channels + 1)))
        {
            goto setmusicvolume_error;
        }
    }
    else
    {
        channels[1] = channels[0];
    }

    sound_volume_music((int)channels[0], (int)channels[1]);
    return S_OK;

setmusicvolume_error:
    printf("values must be integers: setmusicvolume(int left, (optional)int right)\n");
    return E_FAIL;
}

//setmusicvolume(left, right)
HRESULT openbor_setmusictempo(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG new_tempo;

    if(paramCount < 1)
    {
        return S_OK;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &new_tempo)))
    {
        return E_FAIL;
    }

    sound_music_tempo(new_tempo);
    return S_OK;
}

//pausemusic(togglr)
HRESULT openbor_pausemusic(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int pause = 0;
    if(paramCount < 1)
    {
        return S_OK;
    }

    pause = (int)ScriptVariant_IsTrue(varlist[0]);

    sound_pause_music(pause);
    return S_OK;
}

//pausesamples(toggle)
HRESULT openbor_pausesamples(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int pause = 0;
    if(paramCount < 1 || !varlist || !varlist[0])
    {
        return S_OK;
    }

    pause = (int)ScriptVariant_IsTrue(varlist[0]);

    sound_pause_sample(pause);
    return S_OK;
}

//pausesample(toggle,channel)
HRESULT openbor_pausesample(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int pause = 0, channel = 0;
    if(paramCount < 2 || !varlist || !varlist[0] || !varlist[1])
    {
        return S_OK;
    }

    pause = (int)ScriptVariant_IsTrue(varlist[0]);
    if(FAILED(ScriptVariant_IntegerValue(varlist[1], &channel)))
    {
        return S_OK;
    }

    sound_pause_single_sample(pause,channel);
    return S_OK;
}

HRESULT openbor_querychannel(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        goto query_error;
    }
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = sound_query_channel((int)ltemp);

    query_error:
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT openbor_stopchannel(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    *pretvar = NULL;
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        goto sc_error;
    }
    sound_stop_sample((int)ltemp);

    sc_error:
    return E_FAIL;
}

//isactivesample(channel): returns 1 is sample is active, returns 0 otherwise
HRESULT openbor_isactivesample(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(paramCount < 1 || !varlist || !varlist[0])
    {
        goto error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        goto error;
    }
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = sound_is_active((int)ltemp);

    error:
    *pretvar = NULL;
    return E_FAIL;
}

//sampleid(channel): returns sample id in channel if sample is active, it returns -1 otherwise
HRESULT openbor_sampleid(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    if(paramCount < 1 || !varlist || !varlist[0])
    {
        goto error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        goto error;
    }
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = sound_id((int)ltemp);

    error:
    *pretvar = NULL;
    return E_FAIL;
}

//playsample(id, priority, lvolume, rvolume, speed, loop)
HRESULT openbor_playsample(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int i, result;
    LONG value[6] = { -1, 0, savedata.effectvol, savedata.effectvol, 100, 0};

    for(i = 0; i < 6 && i < paramCount; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i)))
        {
            goto playsample_error;
        }
    }
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    if((int)value[5])
    {
        result = sound_loop_sample((int)value[0], (unsigned int)value[1], (int)value[2], (int)value[3], (unsigned int)value[4]);
    }
    else
    {
        result = sound_play_sample((int)value[0], (unsigned int)value[1], (int)value[2], (int)value[3], (unsigned int)value[4]);
    }
    (*pretvar)->lVal = (LONG)result;
    return S_OK;

playsample_error:
    *pretvar = NULL;
    printf("Function requires 6 integer values: playsample(int id, unsigned int priority, int lvolume, int rvolume, unsigned int speed, int loop)\n");
    return E_FAIL;
}

// int loadsample(filename, log)
HRESULT openbor_loadsample(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int arg = 0;

    if(paramCount < 1)
    {
        goto loadsample_error;
    }
    if(varlist[0]->vt != VT_STR)
    {
        goto loadsample_error;
    }

    if(paramCount > 1)
    {
        if(varlist[1]->vt == VT_INTEGER)
        {
            arg = varlist[1]->lVal;
        }
        else
        {
            goto loadsample_error;
        }
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)sound_load_sample(StrCache_Get(varlist[0]->strVal), packfile, arg);
    return S_OK;

loadsample_error:
    printf("Function requires 1 string value and optional log value: loadsample(string {filename} integer {log})\n");
    *pretvar = NULL;
    return E_FAIL;
}

// void unloadsample(id)
HRESULT openbor_unloadsample(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG id;
    *pretvar = NULL;
    if(paramCount != 1 )
    {
        goto unloadsample_error;
    }

    if(FAILED(ScriptVariant_IntegerValue((varlist[0]), &id)))
    {
        goto unloadsample_error;
    }

    sound_unload_sample((int)id);
    return S_OK;

unloadsample_error:
    printf("Function requires 1 integer value: unloadsample(int id)\n");
    return E_FAIL;
}

//fadeout(type, speed);
HRESULT openbor_fadeout(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG type;
    LONG speed;
    *pretvar = NULL;
    if(paramCount < 1 )
    {
        goto fade_out_error;
    }

    if(FAILED(ScriptVariant_IntegerValue((varlist[0]), &type)))
    {
        goto fade_out_error;
    }
    if(FAILED(ScriptVariant_IntegerValue((varlist[1]), &speed)))

    {
        fade_out((int)type, (int)speed);
    }
    return S_OK;

fade_out_error:
    printf("Function requires 2 integer values: fade_out(int type, int speed)\n");
    return E_FAIL;
}

//changepalette(index);
HRESULT openbor_changepalette(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG index;

    *pretvar = NULL;

    if(paramCount < 1)
    {
        goto changepalette_error;
    }

    if(FAILED(ScriptVariant_IntegerValue((varlist[0]), &index)))
    {
        goto changepalette_error;
    }

    change_system_palette((int)index);

    return S_OK;

changepalette_error:
    printf("Function requires 1 integer value: changepalette(int index)\n");
    return E_FAIL;
}

//changelight(x, z);
HRESULT openbor_changelight(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG x, z;
    extern s_axis_i light;
    ScriptVariant *arg = NULL;

    *pretvar = NULL;
    if(paramCount < 2)
    {
        goto changelight_error;
    }

    arg = varlist[0];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &x)))
        {
            goto changelight_error;
        }
        light.x = (int)x;
    }

    arg = varlist[1];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &z)))
        {
            goto changelight_error;
        }
        light.y = (int)z;
    }

    return S_OK;
changelight_error:
    printf("Function requires 2 integer values: changepalette(int x, int z)\n");
    return E_FAIL;
}

//changeshadowcolor(color, alpha);
// color = 0 means no gfxshadow, -1 means don't fill the shadow with colour
// alpha default to 2, <=0 means no alpha effect
HRESULT openbor_changeshadowcolor(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG c, a;
    extern int            shadowcolor;
    extern int            shadowalpha;

    *pretvar = NULL;
    if(paramCount < 1)
    {
        goto changeshadowcolor_error;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &c)))
    {
        goto changeshadowcolor_error;
    }

    shadowcolor = (int)c;

    if(paramCount > 1)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[1], &a)))
        {
            goto changeshadowcolor_error;
        }
        shadowalpha = (int)a;
    }

    return S_OK;
changeshadowcolor_error:
    printf("Function requires at least 1 integer value, the 2nd integer parameter is optional: changepalette(int colorindex, int alpha)\n");
    return E_FAIL;
}

// ===== gettextobjproperty(name, value) =====
enum gtop_enum
{
    _top_a,
    _top_font,
    _top_text,
    _top_time,
    _top_x,
    _top_y,
    _top_z,
    _top_the_end,
};

static int obor_textobj_property(int property)
{
    static const int early[] =
    {
        _top_font, _top_text, _top_time, _top_x, _top_a, _top_y, _top_z
    };

    if(obor_profile_build >= 4283 && obor_profile_build < 4377 &&
        property >= 0 && property < _top_the_end)
        return early[property];

    return property;
}

int mapstrings_textobjproperty(ScriptVariant **varlist, int paramCount)
{
    char *propname = NULL;
    int prop;
    int first = 0;
    int count;
    const char **names;

    /* The original search through 4376 only reached these three names. */
    static const char *early[] = {"a", "y", "z"};
    static const char *merged[] = {"a", "font", "text", "timex", "y", "z"};

    static const char *proplist[] =
    {
        "a",
        "font",
        "text",
        "time",
        "x",
        "y",
        "z",
    };

    if(paramCount < 2)
    {
        return 1;
    }

    if(!varlist || !varlist[1]) return 1;
    if(varlist[1]->vt == VT_STR)
    {
        propname = (char *)StrCache_GetIfPresent(varlist[1]->strVal);
        if(!propname) return 1;
        names = proplist;
        count = (int)(sizeof(proplist) / sizeof(*proplist));
        if(obor_profile_build >= 4283 && obor_profile_build < 4377)
        {
            names = early;
            count = (int)(sizeof(early) / sizeof(*early));
            first = 3;
        }
        else if(obor_profile_build >= 4377 && obor_profile_build < 4382)
        {
            names = merged;
            count = (int)(sizeof(merged) / sizeof(*merged));
        }

        prop = searchList(names, propname, count);
        if(prop >= 0)
        {
            ScriptVariant_ChangeType(varlist[1], VT_INTEGER);
            varlist[1]->lVal = first + prop;
        }
        else
        {
            printf("'%s' is not a valid textobj property.\n", propname);
            return 0;
        }
    }

    return 1;
}

static int obor_textobj_index(int index, int grow)
{
    s_textobj *grown;
    int count;
    if(index < 0) return 0;
    if(!level) return -1;
    if(!grow && index >= level->numtextobjs) return 0;
    if(level->numtextobjs < 0 ||
        (level->numtextobjs && !level->textobjs)) return -1;
    count = level->numtextobjs;
    if(index < count) return 1;
    if(!grow) return 0;
    if(index == INT_MAX ||
        (size_t)(index + 1) > (size_t)-1 / sizeof(*grown)) return -1;
    if(level->obor_arrays)
        return obor_level_grow_array(level, OBOR_LEVEL_ARRAY_TEXT, index + 1) ? 1 : -1;
    grown = realloc(level->textobjs, (size_t)(index + 1) * sizeof(*grown));
    if(!grown) return -1;
    memset(grown + count, 0, (size_t)(index + 1 - count) * sizeof(*grown));
    level->textobjs = grown;
    level->numtextobjs = index + 1;
    return 1;
}

static int obor_textobj_store(s_textobj *object, const char *text)
{
    const char *end;
    char *stored;
    size_t length;
    if(!object || !text) return 0;
    end = memchr(text, 0, MAX_STR_VAR_LEN + 1);
    if(!end) return 0;
    length = (size_t)(end - text);
    stored = object->text;
    if(!stored)
    {
        stored = malloc(MAX_STR_VAR_LEN + 1);
        if(!stored) return 0;
    }
    memmove(stored, text, length);
    memset(stored + length, 0, MAX_STR_VAR_LEN + 1 - length);
    object->text = stored;
    return 1;
}

static int obor_textobj_format(ScriptVariant *value, char *buffer)
{
    int written;
    const char *text;
    if(!buffer) return 0;
    buffer[0] = 0;
    if(!value) return 0;
    switch(value->vt)
    {
    case VT_EMPTY:
        written = snprintf(buffer, MAX_STR_VAR_LEN + 1, "<VT_EMPTY>   Unitialized");
        break;
    case VT_INTEGER:
        written = snprintf(buffer, MAX_STR_VAR_LEN + 1, "%d", (int)value->lVal);
        break;
    case VT_DECIMAL:
        written = snprintf(buffer, MAX_STR_VAR_LEN + 1, "%lf", value->dblVal);
        break;
    case VT_PTR:
        written = snprintf(buffer, MAX_STR_VAR_LEN + 1, "#%ld", (long)value->ptrVal);
        break;
    case VT_STR:
        text = StrCache_GetIfPresent(value->strVal);
        if(!text || !memchr(text, 0, MAX_STR_VAR_LEN + 1)) return 0;
        written = snprintf(buffer, MAX_STR_VAR_LEN + 1, "%s", text);
        break;
    default:
        written = snprintf(buffer, MAX_STR_VAR_LEN + 1, "<Unprintable VARIANT type.>");
        break;
    }
    if(written < 0 || written > MAX_STR_VAR_LEN)
    {
        buffer[0] = 0;
        return 0;
    }
    return 1;
}

HRESULT openbor_gettextobjproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;

    LONG ind;
    int propind;
    int obor_index;

    if(paramCount < 2)
    {
        goto gettextobjproperty_error;
    }


    if(!varlist) { *pretvar = NULL; return E_FAIL; }
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ind)))
    {
        printf("Function's 1st argument must be a numeric value: gettextproperty(int index, \"property\")\n");
        goto gettextobjproperty_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    mapstrings_textobjproperty(varlist, paramCount);

    obor_index = obor_textobj_index(ind, 0);
    if(obor_index < 0) goto gettextobjproperty_error;
    if(!obor_index)
    {
        (*pretvar)->lVal = 0;
        return S_OK;
    }

    if(!varlist[1]) goto gettextobjproperty_error;
    if(varlist[1]->vt != VT_INTEGER)
    {
        if(varlist[1]->vt != VT_STR)
        {
            printf("Function gettextobjproperty must have a string property name.\n");
        }
        goto gettextobjproperty_error;
    }

    propind = obor_textobj_property(varlist[1]->lVal);

    switch(propind)
    {
    case _top_font:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->textobjs[ind].font;
        break;
    }
    case _top_text:
    {
        if(!level->textobjs[ind].text ||
            !memchr(level->textobjs[ind].text, 0, MAX_STR_VAR_LEN + 1))
            goto gettextobjproperty_error;
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, level->textobjs[ind].text);
        break;
    }
    case _top_time:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->textobjs[ind].time;
        break;
    }
    case _top_x:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->textobjs[ind].position.x;
        break;
    }
    case _top_y:
    case _top_a:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->textobjs[ind].position.y;
        break;
    }
    case _top_z:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->textobjs[ind].position.z;
        break;
    }
    default:
        //printf("Property name '%s' is not supported by function gettextobjproperty.\n", propname);
        goto gettextobjproperty_error;
        break;
    }

    return S_OK;

gettextobjproperty_error:
    *pretvar = NULL;
    return E_FAIL;
}

HRESULT openbor_changetextobjproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar) return E_FAIL;

    LONG ind;
    int propind;
    static char buf[MAX_STR_VAR_LEN + 1];
    LONG ltemp;
    const char *ctotext = "changetextobjproperty(int index, \"property\", value)";

    *pretvar = NULL;

    if(paramCount < 3)
    {
        printf("Function needs at last 3 parameters: %s\n", ctotext);
        return E_FAIL;
    }

    if(!varlist) return E_FAIL;
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ind)))
    {
        printf("Function's 1st argument must be a numeric value: %s\n", ctotext);
        return E_FAIL;
    }

    mapstrings_textobjproperty(varlist, paramCount);

    if(ind < 0)
    {
        printf("Invalid textobj index, must be >= 0\n");
        return E_FAIL;
    }
    else
    {
        if(obor_textobj_index(ind, 1) < 0) return E_FAIL;
    }

    if(!varlist[1]) return E_FAIL;
    if(varlist[1]->vt != VT_INTEGER)
    {
        printf("Invalid property type for changetextobjproperty.\n");
        return E_FAIL;
    }

    propind = obor_textobj_property(varlist[1]->lVal);

    switch(propind)
    {
    case _top_font:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            level->textobjs[ind].font = (int)ltemp;
        }
        else
        {
            goto changetextobjproperty_error;
        }
        break;
    }
    case _top_text:
    {
        if(!obor_textobj_format(varlist[2], buf) ||
            !obor_textobj_store(&level->textobjs[ind], buf))
            goto changetextobjproperty_error;
        break;
    }
    case _top_time:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            level->textobjs[ind].time = (int)ltemp;
        }
        else
        {
            goto changetextobjproperty_error;
        }
        break;
    }
    case _top_x:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            level->textobjs[ind].position.x = (int)ltemp;
        }
        else
        {
            goto changetextobjproperty_error;
        }
        break;
    }
    case _top_a:
    case _top_y:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            level->textobjs[ind].position.y = (int)ltemp;
        }
        else
        {
            goto changetextobjproperty_error;
        }
        break;
    }
    case _top_z:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[2], &ltemp)))
        {
            level->textobjs[ind].position.z = (int)ltemp;
        }
        else
        {
            goto changetextobjproperty_error;
        }
        break;
    }
    default:
        //printf("Property name '%s' is not supported by function changetextobjproperty.\n", propname);
        return E_FAIL;
        break;
    }

    return S_OK;

changetextobjproperty_error:
    if(!obor_textobj_format(varlist[2], buf)) buf[0] = 0;
    printf("Invalid textobj value: %s\n", buf);
    return E_FAIL;
}

// settextobj(int index, int x, int y, int font, int z, char text, int time {optional})
HRESULT openbor_settextobj(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar) return E_FAIL;

    LONG ind;
    LONG X, Y, Z, F, T = 0;
    static char buf[MAX_STR_VAR_LEN + 1];
    const char *stotext = "settextobj(int index, int x, int y, int font, int z, char text, int time {optional})";

    *pretvar = NULL;


    if(paramCount < 6)
    {
        printf("Function needs at least 6 parameters: %s\n", stotext);
        return E_FAIL;
    }

    if(!varlist) return E_FAIL;
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ind)))
    {
        printf("Function's 1st argument must be a numeric value: %s\n", stotext);
        return E_FAIL;
    }

    if(ind < 0)
    {
        printf("Invalid textobj index, must be >= 0\n");
        return E_FAIL;
    }
    else
    {
        if(obor_textobj_index(ind, 1) < 0) return E_FAIL;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[1], &X)))
    {
        goto settextobj_error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[2], &Y)))
    {
        goto settextobj_error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[3], &F)))
    {
        goto settextobj_error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[4], &Z)))
    {
        goto settextobj_error;
    }
    if(!obor_textobj_format(varlist[5], buf)) goto settextobj_error;
    if(paramCount >= 7 && FAILED(ScriptVariant_IntegerValue(varlist[6], &T)))
    {
        goto settextobj_error;
    }

    level->textobjs[ind].time = (int)T;
    level->textobjs[ind].position.x = (int)X;
    level->textobjs[ind].position.y = (int)Y;
    level->textobjs[ind].position.z = (int)Z;
    level->textobjs[ind].font = (int)F;

    if(!obor_textobj_store(&level->textobjs[ind], buf)) goto settextobj_error;

    return S_OK;

settextobj_error:
    printf("Invalid value(s) for settextobj: %s\n", stotext);
    return E_FAIL;
}

HRESULT openbor_cleartextobj(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar) return E_FAIL;

    LONG ind;
    int obor_index;
    const char *cltotext = "cleartextobj(int index)";

    *pretvar = NULL;

    if(paramCount < 1)
    {
        printf("Function needs at least 1 parameter: %s\n", cltotext);
        return E_FAIL;
    }

    if(!varlist) return E_FAIL;
    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ind)))
    {
        printf("Function's 1st argument must be a numeric value: %s\n", cltotext);
        return E_FAIL;
    }

    obor_index = obor_textobj_index(ind, 0);
    if(obor_index < 0) return E_FAIL;
    if(!obor_index)
    {
        return S_OK;
    }

    level->textobjs[ind].time = 0;
    level->textobjs[ind].position.x = 0;
    level->textobjs[ind].position.y = 0;
    level->textobjs[ind].font = 0;
    level->textobjs[ind].position.z = 0;
    if(level->textobjs[ind].text)
    {
        free(level->textobjs[ind].text);
    }
    level->textobjs[ind].text = NULL;
    return S_OK;
}

// ===== get layer type ======
enum getlt_enum
{
    _glt_background,
    _glt_bglayer,
    _glt_fglayer,
    _glt_frontpanel,
    _glt_generic,
    _glt_neon,
    _glt_panel,
    _glt_screen,
    _glt_water,
    _glt_the_end,
};


// ===== getbglayerproperty ======
enum getbglp_enum
{
    _glp_alpha,
    _glp_amplitude,
    _glp_bgspeedratio,
    _glp_enabled,
    _glp_neon,
    _glp_quake,
    _glp_transparency,
    _glp_watermode,
    _glp_wavelength,
    _glp_wavespeed,
    _glp_xoffset,
    _glp_xratio,
    _glp_xrepeat,
    _glp_xspacing,
    _glp_z,
    _glp_zoffset,
    _glp_zratio,
    _glp_zrepeat,
    _glp_zspacing,
    _glp_the_end,
};

int mapstrings_layerproperty(ScriptVariant **varlist, int paramCount)
{
    char *propname = NULL;
    int prop;

    static const char *proplist[] =
    {
        "alpha",
        "amplitude",
        "bgspeedratio",
        "enabled",
        "neon",
        "quake",
        "transparency",
        "watermode",
        "wavelength",
        "wavespeed",
        "xoffset",
        "xratio",
        "xrepeat",
        "xspacing",
        "z",
        "zoffset",
        "zratio",
        "zrepeat",
        "zspacing",
    };

    static const char *typelist[] =
    {
        "background",
        "bglayer",
        "fglayer",
        "frontpanel",
        "generic",
        "neon",
        "panel",
        "water",
    };

    if(paramCount < 3)
    {
        return 1;
    }
    MAPSTRINGS(varlist[0], typelist, _glt_the_end,
               "Type name '%s' is not supported by function getlayerproperty.\n");
    MAPSTRINGS(varlist[2], proplist, _glp_the_end,
               "Property name '%s' is not supported by function getlayerproperty.\n");

    return 1;
}

HRESULT _getlayerproperty(s_layer *layer, int propind, ScriptVariant **pretvar)
{

    switch(propind)
    {
    case _glp_alpha:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->drawmethod.alpha;
        break;
    }
    case _glp_amplitude:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->drawmethod.water.amplitude;
        break;
    }
    case _glp_bgspeedratio:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)layer->bgspeedratio;
        break;
    }
    case _glp_enabled:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->enabled;
        break;
    }
    case _glp_neon:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->neon;
        break;
    }
    case _glp_quake:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->quake;
        break;
    }
    case _glp_transparency:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->drawmethod.transbg;
        break;
    }
    case _glp_watermode:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->drawmethod.water.watermode;
        break;
    }

    case _glp_wavelength:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->drawmethod.water.wavelength;
        break;
    }
    case _glp_wavespeed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)layer->drawmethod.water.wavespeed;
        break;
    }
    case _glp_xoffset:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->offset.x;
        break;
    }
    case _glp_xratio:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)layer->ratio.x;
        break;
    }
    case _glp_xrepeat:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->drawmethod.xrepeat;
        break;
    }
    case _glp_xspacing:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->spacing.x;
        break;
    }
    case _glp_z:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->z;
        break;
    }
    case _glp_zoffset:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->offset.z;
        break;
    }
    case _glp_zratio:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)layer->ratio.z;
        break;
    }
    case _glp_zrepeat:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->drawmethod.yrepeat;
        break;
    }
    case _glp_zspacing:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)layer->spacing.z;
        break;
    }
    default:
        *pretvar = NULL;
        return E_FAIL;
    }
    return S_OK;
}

HRESULT _changelayerproperty(s_layer *layer, int propind, ScriptVariant *var)
{
    LONG temp;
    DOUBLE temp2;
    switch(propind)
    {
    case _glp_alpha:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->drawmethod.alpha = temp;
        break;
    }
    case _glp_amplitude:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->drawmethod.water.amplitude = temp;
        break;
    }
    case _glp_bgspeedratio:
    {
        if(FAILED(ScriptVariant_DecimalValue(var, &temp2)))
        {
            return E_FAIL;
        }
        layer->bgspeedratio = temp2;
        break;
    }
    case _glp_enabled:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->enabled = temp;
        break;
    }
    case _glp_neon:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->neon = temp;
        break;
    }
    case _glp_quake:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->quake = temp;
        break;
    }
    case _glp_transparency:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->drawmethod.transbg = temp;
        break;
    }
    case _glp_watermode:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->drawmethod.water.watermode = temp;
        break;
    }

    case _glp_wavelength:
    {
        if(FAILED(ScriptVariant_DecimalValue(var, &temp2)))
        {
            return E_FAIL;
        }
        layer->drawmethod.water.wavelength = temp2;
        break;
    }
    case _glp_wavespeed:
    {
        if(FAILED(ScriptVariant_DecimalValue(var, &temp2)))
        {
            return E_FAIL;
        }
        layer->drawmethod.water.wavespeed = temp2;
        break;
    }
    case _glp_xoffset:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->offset.x = temp;
        break;
    }
    case _glp_xratio:
    {
        if(FAILED(ScriptVariant_DecimalValue(var, &temp2)))
        {
            return E_FAIL;
        }
        layer->ratio.x = temp2;
        break;
    }
    case _glp_xrepeat:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->drawmethod.xrepeat = temp;
        break;
    }
    case _glp_xspacing:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->spacing.x = temp;
        break;
    }
    case _glp_z:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->z = temp;
        break;
    }
    case _glp_zoffset:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->offset.z = temp;
        break;
    }
    case _glp_zratio:
    {
        if(FAILED(ScriptVariant_DecimalValue(var, &temp2)))
        {
            return E_FAIL;
        }
        layer->ratio.z = temp2;
        break;
    }
    case _glp_zrepeat:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->drawmethod.yrepeat = temp;
        break;
    }
    case _glp_zspacing:
    {
        if(FAILED(ScriptVariant_IntegerValue(var, &temp)))
        {
            return E_FAIL;
        }
        layer->spacing.z = temp;
        break;
    }
    default:
        return E_FAIL;
    }
    return S_OK;
}

s_layer *_getlayer(int type, int ind)
{
    switch(type)
    {
    case _glt_background:
        return level->background;
    case _glt_bglayer:
        if(ind < 0 || ind >= level->numbglayers)
        {
            return NULL;
        }
        return level->bglayers[ind];
    case _glt_fglayer:
        if(ind < 0 || ind >= level->numfglayers)
        {
            return NULL;
        }
        return level->fglayers[ind];
    case _glt_frontpanel:
        if(ind < 0 || ind >= level->numfrontpanels)
        {
            return NULL;
        }
        return level->frontpanels[ind];
    case _glt_generic:
        if(ind < 0 || ind >= level->numgenericlayers)
        {
            return NULL;
        }
        return level->genericlayers[ind];
    case _glt_neon:
        if(ind < 0 || ind >= level->numpanels)
        {
            return NULL;
        }
        return level->panels[ind][1];
    case _glt_panel:
        if(ind < 0 || ind >= level->numpanels)
        {
            return NULL;
        }
        return level->panels[ind][0];
    case _glt_screen:
        if(ind < 0 || ind >= level->numpanels)
        {
            return NULL;
        }
        return level->panels[ind][2];
    case _glt_water:
        if(ind < 0 || ind >= level->numwaters)
        {
            return NULL;
        }
        return level->waters[ind];
    default:
        return NULL;
    }
}

// getlayerproperty(type, index, propertyname);
HRESULT openbor_getlayerproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ind;
    int propind, type;
    s_layer *layer = NULL;

    if(paramCount < 3)
    {
        goto getlayerproperty_error;
    }

    mapstrings_layerproperty(varlist, paramCount);

    type = varlist[0]->lVal;
    propind = varlist[2]->lVal;

    if(FAILED(ScriptVariant_IntegerValue(varlist[1], &ind)))
    {
        goto getlayerproperty_error2;
    }

    layer = _getlayer(type, (int)ind);

    if(layer == NULL)
    {
        goto getlayerproperty_error2;
    }

    if(FAILED(_getlayerproperty(layer, propind, pretvar)))
    {
        goto getlayerproperty_error3;
    }

    return S_OK;

getlayerproperty_error:
    *pretvar = NULL;
    printf("Function getlayerproperty must have 3 parameters: layertype, index and propertyname\n");
    return E_FAIL;
getlayerproperty_error2:
    *pretvar = NULL;
    printf("Layer not found!\n");
    return E_FAIL;
getlayerproperty_error3:
    *pretvar = NULL;
    printf("Bad property name or value.\n");
    return E_FAIL;
}

// changelayerproperty(type, index, propertyname);
HRESULT openbor_changelayerproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ind;
    int propind, type;
    s_layer *layer = NULL;
    *pretvar = NULL;

    if(paramCount < 4)
    {
        goto chglayerproperty_error;
    }

    mapstrings_layerproperty(varlist, paramCount);

    type = varlist[0]->lVal;
    propind = varlist[2]->lVal;

    if(FAILED(ScriptVariant_IntegerValue(varlist[1], &ind)))
    {
        goto chglayerproperty_error2;
    }

    layer = _getlayer(type, (int)ind);

    if(layer == NULL)
    {
        goto chglayerproperty_error2;
    }

    if(FAILED(_changelayerproperty(layer, propind, varlist[3])))
    {
        goto chglayerproperty_error3;
    }

    return S_OK;

chglayerproperty_error:
    printf("Function changelayerproperty must have 4 parameters: layertype, index, propertyname and value\n");
    return E_FAIL;
chglayerproperty_error2:
    printf("Layer not found!\n");
    return E_FAIL;
chglayerproperty_error3:
    printf("Layer property not understood or bad value.\n");
    return E_FAIL;
}


// ===== level properties ======
enum levelproperty_enum
{
    _lp_basemap,
    _lp_bgspeed,
    _lp_cameraxoffset,
    _lp_camerazoffset,
    _lp_gravity,
    _lp_hole,
    _lp_maxfallspeed,
    _lp_maxtossspeed,
    _lp_quake,
    _lp_rocking,
    _lp_scrollspeed,
    _lp_type,
    _lp_vbgspeed,
    _lp_wall,
    _lp_the_end,
};

enum basemap_enum
{
    _lp_bm_map,
    _lp_bm_x,
    _lp_bm_xsize,
    _lp_bm_z,
    _lp_bm_zsize,
    _lp_bm_the_end,
};

enum terrain_enum
{
    _lp_terrain_depth,
    _lp_terrain_height,
    _lp_terrain_lowerleft,
    _lp_terrain_lowerright,
    _lp_terrain_type,
    _lp_terrain_upperleft,
    _lp_terrain_upperright,
    _lp_terrain_x,
    _lp_terrain_z,
    _lp_terrain_the_end,
};

int mapstrings_levelproperty(ScriptVariant **varlist, int paramCount)
{
    char *propname = NULL;
    int prop;

    static const char *proplist[] =
    {
        "basemap",
        "bgspeed",
        "cameraxoffset",
        "camerazoffset",
        "gravity",
        "hole",
        "maxfallspeed",
        "maxtossspeed",
        "quake",
        "rocking",
        "scrollspeed",
        "type",
        "vbgspeed",
        "wall",
    };

    static const char *basemaplist[] =
    {
        "map",
        "x",
        "xsize",
        "z",
        "zsize",
    };

    static const char *terrainlist[] =
    {
        /*
        Walls and holes.
        */

        "depth",
        "height",
        "lowerleft",
        "lowerright",
        "type",
        "upperleft",
        "upperright",
        "x",
        "z",
    };

    if(paramCount < 1)
    {
        return 1;
    }
    MAPSTRINGS(varlist[0], proplist, _lp_the_end,
               "Level property '%s' is not supported.\n");

    if(paramCount >= 3 && varlist[0]->vt == VT_INTEGER && varlist[0]->lVal == _lp_basemap)
    {
        MAPSTRINGS(varlist[2], basemaplist, _lp_bm_the_end,
                   _is_not_supported_by_, "basemap");
    }

    if(paramCount >= 3 && varlist[0]->vt == VT_INTEGER && (varlist[0]->lVal == _lp_hole || varlist[0]->lVal == _lp_wall))
    {
        MAPSTRINGS(varlist[2], terrainlist, _lp_terrain_the_end,
                   _is_not_supported_by_, "wall/hole");
    }

    return 1;
}

static s_set_entry *obor_script_set_handle(const ScriptVariant *value)
{
    extern s_set_entry *levelsets;
    extern int num_difficulties;

    if(!value || value->vt != VT_PTR || !levelsets) return NULL;
    for(int index = 0; index < num_difficulties; ++index)
    {
        if(value->ptrVal == &levelsets[index]) return &levelsets[index];
    }
    return NULL;
}

static int obor_assign_levelorder(s_set_entry *set, s_level_entry *entries)
{
    extern s_set_entry *levelsets;
    extern int num_difficulties;

    if(!entries)
    {
        /* Expose the empty script view while keeping a usable level order for the engine. */
        set->levelorder_hidden = 1;
        return 1;
    }
    for(int index = 0; index < num_difficulties; ++index)
    {
        s_set_entry *owner = &levelsets[index];
        if(entries == obor_owned_levelorder(owner) && owner->numlevels >= set->numlevels)
        {
            if(!set->levelorder_replaced)
            {
                set->levelorder_owner = set->levelorder;
                set->levelorder_replaced = 1;
            }
            set->levelorder = entries;
            set->levelorder_hidden = 0;
            return 1;
        }
    }
    return 0;
}

HRESULT openbor_get_set_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    s_set_entry *handle;
    LONG value;

    if(!pretvar || !*pretvar) return E_FAIL;
    ScriptVariant_Clear(*pretvar);
    if(paramCount < 2 || !varlist || !(handle = obor_script_set_handle(varlist[0])) ||
       !varlist[1] || varlist[1]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error;
    }

    switch(obor_set_property_native(varlist[1]->lVal))
    {
        case SET_PROP_COMPLETE_FLAG: value = handle->ifcomplete; break;
        case SET_PROP_COMPLETE_SKIP:
        case SET_PROP_CONTINUE_SCORE_TYPE:
            /* These original cases fall through to the next terminating property. */
            value = obor_profile_build < 4493 ? handle->numlevels : handle->credits;
            break;
        case SET_PROP_CREDITS: value = handle->credits; break;
        case SET_PROP_GAME_OVER_SKIP: value = handle->noshowgameover; break;
        case SET_PROP_HOF_DISABLE: value = handle->noshowhof; break;
        case SET_PROP_LEVELSET_COLLECTION:
            if(handle->levelorder && !handle->levelorder_hidden)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = handle->levelorder;
            }
            return S_OK;
        case SET_PROP_LEVELSET_COUNT:
            if(obor_profile_build < 4478)
            {
                ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
                (*pretvar)->dblVal = 0;
                (*pretvar)->lVal = handle->numlevels;
                return S_OK;
            }
            value = handle->numlevels;
            break;
        case SET_PROP_LIVES: value = handle->lives; break;
        case SET_PROP_MP_RECOVER_TYPE: value = handle->typemp; break;
        case SET_PROP_MUSIC_FADE_TIME: value = handle->custfade; break;
        case SET_PROP_MUSIC_OVERLAP: value = handle->musicoverlap; break;
        case SET_PROP_NAME:
            if(handle->name)
            {
                ScriptVariant_ChangeType(*pretvar, VT_STR);
                StrCache_Copy((*pretvar)->strVal, handle->name);
            }
            return S_OK;
        case SET_PROP_PLAYER_MAX: value = handle->maxplayers; break;
        case SET_PROP_SAVE_TYPE: value = handle->saveflag; break;
        case SET_PROP_SELECT_DISABLE: value = handle->noselect; break;
        case SET_PROP_SELECT_NO_SAME: value = handle->nosame; break;
        default:
            printf("Unsupported property.\n");
            goto error;
    }
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = value;
    return S_OK;

error:
    printf("You must provide a valid handle and property: get_set_property(void handle, int property)\n");
    return E_FAIL;
}

HRESULT openbor_set_set_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    s_set_entry *handle;
    ScriptVariant *value;

    if(!pretvar || !*pretvar) return E_FAIL;
    if(paramCount < 3 || !varlist || !(handle = obor_script_set_handle(varlist[0])) ||
       !varlist[1] || varlist[1]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error;
    }
    if(obor_set_property_native(varlist[1]->lVal) != SET_PROP_LEVELSET_COLLECTION)
    {
        printf("Unsupported or read only property.\n");
        goto error;
    }
    value = varlist[2];
    if(!value || (value->vt != VT_PTR && value->vt != VT_EMPTY) ||
       !obor_assign_levelorder(handle, value->vt == VT_PTR ? value->ptrVal : NULL))
    {
        goto error;
    }
    return S_OK;

error:
    printf("You must provide a valid handle, property and value: set_set_property(void handle, int property, value)\n");
    return E_FAIL;
}

HRESULT openbor_get_layer_handle(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    extern s_level *level;
    LONG index;

    if(!pretvar || !*pretvar) return E_FAIL;
    if(paramCount != 2 || !varlist || !varlist[0] ||
       (varlist[0]->vt != VT_PTR && varlist[0]->vt != VT_EMPTY) ||
       FAILED(ScriptVariant_IntegerValue(varlist[1], &index)) || !level || varlist[0]->ptrVal != level)
    {
        printf("You must provide a valid handle and index: openbor_get_layer_handle(void level_handle, int index)\n");
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_Clear(*pretvar);
    if(level->layersref && index >= 0 && index < level->numlayers && index < level->numlayersref)
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = &level->layersref[index];
    }
    return S_OK;
}

HRESULT openbor_get_set_handle(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    extern s_set_entry *levelsets;
    extern int num_difficulties;
    LONG index;

    if(!pretvar || !*pretvar)
    {
        return E_FAIL;
    }
    if(paramCount != 1 || !varlist || FAILED(ScriptVariant_IntegerValue(varlist[0], &index)))
    {
        printf("You must provide a valid index: get_set_handle(int index)\n");
        *pretvar = NULL;
        return E_FAIL;
    }

    ScriptVariant_Clear(*pretvar);
    if(levelsets && index >= 0 && index < num_difficulties)
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = &levelsets[index];
    }
    return S_OK;
}

HRESULT openbor_get_level_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    extern s_level *level;
    ScriptVariant *result;
    s_level *handle;
    int property;

    if(!pretvar || !*pretvar) return E_FAIL;
    result = *pretvar;
    ScriptVariant_Clear(result);
    if(paramCount < 2 || !varlist || !varlist[0] || !varlist[1] ||
       varlist[1]->vt != VT_INTEGER ||
       (obor_profile_build < 4490 && varlist[0]->vt != VT_PTR))
    {
        *pretvar = NULL;
        goto error;
    }

    // A single level can be loaded at a time.
    handle = varlist[0]->vt == VT_PTR ? varlist[0]->ptrVal : level;
    if(!handle || handle != level)
    {
        *pretvar = NULL;
        goto error;
    }
    property = obor_level_property_native(varlist[1]->lVal);
    if(obor_profile_build == 4490 && property == LEVEL_PROP_PALETTE_COUNT)
    {
        ScriptVariant_ChangeType(result, VT_PTR);
        result->ptrVal = level;
        return S_OK;
    }
    if(obor_profile_build < 4491 &&
       ((obor_profile_build < 4490 && property == LEVEL_PROP_NAME) ||
        (property >= 0 && !obor_level_property_has_early_getter(property))))
    {
        property = -1;
    }

    // These early implementations return the next case's result.
    if(property >= LEVEL_PROP_SCRIPT_LEVEL_END && property <= LEVEL_PROP_SCRIPT_UPDATED)
    {
        property = LEVEL_PROP_SCROLL_DIRECTION;
    }
    if(property == LEVEL_PROP_SPAWN_COLLECTION) property = LEVEL_PROP_SPAWN_COUNT;
    if(property == LEVEL_PROP_SPAWN_PLAYER_COLLECTION) property = LEVEL_PROP_SPECIAL_DISABLE;
    if(property == LEVEL_PROP_TEXT_OBJECT_COLLECTION) property = LEVEL_PROP_TEXT_OBJECT_COUNT;

#define LEVEL_RESULT(tag, member, value) \
    do { ScriptVariant_ChangeType(result, tag); result->member = value; } while(0)
#define LEVEL_INTEGER(value) LEVEL_RESULT(VT_INTEGER, lVal, (LONG)(value))
#define LEVEL_DECIMAL(value) LEVEL_RESULT(VT_DECIMAL, dblVal, (DOUBLE)(value))
#define LEVEL_POINTER(value) \
    do { if(value) LEVEL_RESULT(VT_PTR, ptrVal, (VOID *)(value)); } while(0)
#define LEVEL_STRING(value) \
    do { ScriptVariant_ChangeType(result, VT_STR); StrCache_Copy(result->strVal, value); } while(0)
    switch(property)
    {
    case LEVEL_PROP_AUTO_SCROLL_DIRECTION:
        LEVEL_INTEGER(handle->bgdir);
        break;
    case LEVEL_PROP_AUTO_SCROLL_X:
        LEVEL_DECIMAL(handle->bgspeed);
        break;
    case LEVEL_PROP_AUTO_SCROLL_Y:
        LEVEL_DECIMAL(handle->vbgspeed);
        break;
    case LEVEL_PROP_BASEMAP_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_BASEMAP, handle->basemaps));
        break;
    case LEVEL_PROP_BASEMAP_COUNT:
        LEVEL_INTEGER(handle->numbasemaps);
        break;
    case LEVEL_PROP_BOSS_COUNT:
        LEVEL_INTEGER(handle->bosses);
        break;
    case LEVEL_PROP_BOSS_MUSIC_NAME:
        LEVEL_STRING(handle->bossmusic);
        break;
    case LEVEL_PROP_BOSS_MUSIC_OFFSET:
        LEVEL_INTEGER(handle->bossmusic_offset);
        break;
    case LEVEL_PROP_BOSS_SLOW:
        LEVEL_INTEGER(obor_profile_build < 4492 ? (LONG)handle->bossmusic_offset : handle->boss_slow);
        break;
    case LEVEL_PROP_CAMERA_OFFSET_X:
        LEVEL_INTEGER(handle->cameraxoffset);
        break;
    case LEVEL_PROP_CAMERA_OFFSET_Z:
        LEVEL_INTEGER(handle->camerazoffset);
        break;
    case LEVEL_PROP_COMPLETE_FORCE:
        LEVEL_INTEGER(handle->forcefinishlevel);
        break;
    case LEVEL_PROP_GAMEOVER:
        LEVEL_INTEGER(handle->force_gameover);
        break;
    case LEVEL_PROP_DAMAGE_FROM_ENEMY:
        LEVEL_INTEGER(handle->nohurt);
        break;
    case LEVEL_PROP_DAMAGE_FROM_PLAYER:
        LEVEL_INTEGER(handle->nohit);
        break;
    case LEVEL_PROP_FACING:
        LEVEL_INTEGER(handle->facing);
        break;
    case LEVEL_PROP_GRAVITY:
        LEVEL_DECIMAL(handle->gravity);
        break;
    case LEVEL_PROP_HOLE_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_HOLE, handle->holes));
        break;
    case LEVEL_PROP_HOLE_COUNT:
        LEVEL_INTEGER(handle->numholes);
        break;
    case LEVEL_PROP_LAYER_BACKGROUND_DEFAULT_HANDLE:
        LEVEL_POINTER(handle->background);
        break;
    case LEVEL_PROP_LAYER_BACKGROUND_COLLECTION:
        if(obor_profile_build < 4494)
        {
            if(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_BASEMAP, handle->basemaps))
                LEVEL_RESULT(VT_PTR, ptrVal, obor_level_script_array(handle, OBOR_LEVEL_ARRAY_BACKGROUND, handle->bglayers));
        }
        else
        {
            LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_BACKGROUND, handle->bglayers));
        }
        break;
    case LEVEL_PROP_LAYER_BACKGROUND_COUNT:
        LEVEL_INTEGER(handle->numbglayers);
        break;
    case LEVEL_PROP_LAYER_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_LAYER, handle->layers));
        break;
    case LEVEL_PROP_LAYER_COUNT:
        LEVEL_INTEGER(handle->numlayers);
        break;
    case LEVEL_PROP_LAYER_FOREGROUND_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_FOREGROUND, handle->fglayers));
        break;
    case LEVEL_PROP_LAYER_FOREGROUND_COUNT:
        LEVEL_INTEGER(handle->numfglayers);
        break;
    case LEVEL_PROP_LAYER_FRONTPANEL_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_FRONT, handle->frontpanels));
        break;
    case LEVEL_PROP_LAYER_FRONTPANEL_COUNT:
        LEVEL_INTEGER(handle->numfrontpanels);
        break;
    case LEVEL_PROP_LAYER_GENERIC_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_GENERIC, handle->genericlayers));
        break;
    case LEVEL_PROP_LAYER_GENERIC_COUNT:
        LEVEL_INTEGER(handle->numgenericlayers);
        break;
    case LEVEL_PROP_LAYER_PANEL_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_PANEL, handle->panels));
        break;
    case LEVEL_PROP_LAYER_PANEL_COUNT:
        LEVEL_INTEGER(handle->numpanels);
        break;
    case LEVEL_PROP_LAYER_REF_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_REFERENCE, handle->layersref));
        break;
    case LEVEL_PROP_LAYER_REF_COUNT:
        LEVEL_INTEGER(handle->numlayersref);
        break;
    case LEVEL_PROP_LAYER_WATER_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_WATER, handle->waters));
        break;
    case LEVEL_PROP_LAYER_WATER_COUNT:
        LEVEL_INTEGER(handle->numwaters);
        break;
    case LEVEL_PROP_MAX_FALL_VELOCITY:
        LEVEL_DECIMAL(handle->maxfallspeed);
        break;
    case LEVEL_PROP_MAX_TOSS_VELOCITY:
        LEVEL_DECIMAL(handle->maxtossspeed);
        break;
    case LEVEL_PROP_MIRROR:
        LEVEL_INTEGER(handle->mirror);
        break;
    case LEVEL_PROP_NAME:
        LEVEL_STRING(handle->name);
        break;
    case LEVEL_PROP_PALETTE_BLENDING_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_BLENDING, handle->blendings));
        break;
    case LEVEL_PROP_PALETTE_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_PALETTE, handle->palettes));
        break;
    case LEVEL_PROP_PALETTE_COUNT:
        LEVEL_INTEGER(handle->numpalettes);
        break;
    case LEVEL_PROP_POSITION_X:
        LEVEL_INTEGER(handle->pos);
        break;
    case LEVEL_PROP_QUAKE:
        LEVEL_INTEGER(handle->quake);
        break;
    case LEVEL_PROP_QUAKE_TIME:
        LEVEL_INTEGER(handle->quaketime);
        break;
    case LEVEL_PROP_ROCKING:
        LEVEL_INTEGER(handle->rocking);
        break;
    case LEVEL_PROP_SCROLL_DIRECTION:
        LEVEL_INTEGER(handle->scrolldir);
        break;
    case LEVEL_PROP_SCROLL_VELOCITY:
        // The original decimal tag is paired with an integer payload.
        LEVEL_DECIMAL(0.0);
        if(handle->scrollspeed >= INT32_MIN && (DOUBLE)handle->scrollspeed < (DOUBLE)INT32_MAX + 1.0)
        {
            result->lVal = (LONG)handle->scrollspeed;
        }
        break;
    case LEVEL_PROP_SIZE_X:
        LEVEL_INTEGER(handle->width);
        break;
    case LEVEL_PROP_SPAWN_COUNT:
        LEVEL_INTEGER(handle->numspawns);
        break;
    case LEVEL_PROP_SPECIAL_DISABLE:
        LEVEL_INTEGER(handle->nospecial);
        break;
    case LEVEL_PROP_TEXT_OBJECT_COUNT:
        LEVEL_INTEGER(handle->numtextobjs);
        break;
    case LEVEL_PROP_TIME_ADVANCE:
        LEVEL_INTEGER(handle->advancetime);
        break;
    case LEVEL_PROP_TIME_DISPLAY:
        LEVEL_INTEGER(handle->notime);
        break;
    case LEVEL_PROP_TIME_RESET:
        LEVEL_INTEGER(handle->noreset);
        break;
    case LEVEL_PROP_TIME_SET:
        LEVEL_INTEGER(handle->settime);
        break;
    case LEVEL_PROP_TYPE:
        LEVEL_INTEGER(handle->type);
        break;
    case LEVEL_PROP_WAITING:
        LEVEL_INTEGER(obor_profile_build < 4494 ? handle->numwalls : handle->waiting);
        break;
    case LEVEL_PROP_WALL_COLLECTION:
        LEVEL_POINTER(obor_level_script_array(handle, OBOR_LEVEL_ARRAY_WALL, handle->walls));
        break;
    case LEVEL_PROP_WALL_COUNT:
        LEVEL_INTEGER(handle->numwalls);
        break;
    case LEVEL_PROP_WEAPON:
        LEVEL_INTEGER(handle->setweap);
        break;
    default:
        printf("Unsupported property.\n");
        goto error;
    }
#undef LEVEL_STRING
#undef LEVEL_POINTER
#undef LEVEL_DECIMAL
#undef LEVEL_INTEGER
#undef LEVEL_RESULT
    return S_OK;

error:
    printf("You must provide a valid handle and property: get_level_property(void handle, int property)\n");
    return E_FAIL;
}

/* The typed assignment shares the original record without running init or clear. */
static Script *obor_level_script_source(s_level *level, const ScriptVariant *value)
{
    if((value->vt != VT_PTR && value->vt != VT_EMPTY) || !value->ptrVal) return NULL;
    Script *script = value->ptrVal;
    if(script == &level->endlevel_script || script == &level->level_script ||
       script == &level->key_script || script == &level->update_script ||
       script == &level->updated_script)
    {
        return script;
    }
    for(const Node *entry = scriptheap.first; entry; entry = entry->next)
    {
        if(entry->value == script && entry->name && !strcmp(entry->name, "openbor_allocscript"))
        {
            return script->magic == script_magic ? script : NULL;
        }
    }
    return NULL;
}

static int obor_assign_level_script(Script *destination, Script *source)
{
    if(!source) return 0;
    if(destination == source) return 1;
    if(obor_script_cleanup_active(destination)) return 0;

    Script shared = *source;
    if(shared.varlist && shared.varlist->obor_shared_owners == SIZE_MAX) return 0;
    if(shared.obor_interpreter && !obor_script_reference_retain(shared.obor_interpreter)) return 0;
    if(shared.obor_comment && !obor_script_reference_retain(shared.obor_comment))
    {
        obor_script_reference_release(&shared.obor_interpreter);
        return 0;
    }
    if(shared.varlist) ++shared.varlist->obor_shared_owners;

    obor_script_reference_release(&destination->obor_interpreter);
    obor_script_reference_release(&destination->obor_comment);
    if(destination->varlist) obor_release_script_locals(destination->varlist);
    *destination = shared;
    return 1;
}

HRESULT openbor_set_level_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    extern s_level *level;
    s_level *handle;
    ScriptVariant *value;
    LONG integer;
    DOUBLE decimal;
    int property;

    if(!pretvar || !*pretvar) return E_FAIL;
    if(paramCount < 3 || !varlist || !varlist[0] || varlist[0]->vt != VT_PTR ||
       !varlist[1] || varlist[1]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error;
    }
    handle = varlist[0]->ptrVal;
    value = varlist[2];
    if(!handle || handle != level || !value || handle->obor_releasing) goto error;

    if(obor_profile_build < 4494)
    {
        if(obor_profile_build >= 4487 &&
           obor_set_property_native(varlist[1]->lVal) == SET_PROP_LEVELSET_COLLECTION &&
           obor_level_set_array(handle, OBOR_LEVEL_ARRAY_BACKGROUND, value->ptrVal))
        {
            return S_OK;
        }
        printf("Unsupported property.\n");
        goto error;
    }

    property = obor_level_property_native(varlist[1]->lVal);

#define SET_LEVEL_INTEGER(field) \
    do { \
        if(FAILED(ScriptVariant_IntegerValue(value, &integer))) goto error; \
        handle->field = integer; \
    } while(0)
#define SET_LEVEL_DECIMAL(field) \
    do { \
        if(FAILED(ScriptVariant_DecimalValue(value, &decimal))) goto error; \
        handle->field = decimal; \
    } while(0)
#define SET_LEVEL_COLLECTION(property, id) \
    case LEVEL_PROP_##property##_COLLECTION: \
        if((value->vt != VT_PTR && value->vt != VT_EMPTY) || \
           !obor_level_set_array(handle, OBOR_LEVEL_ARRAY_##id, value->ptrVal)) goto error; \
        break
#define SET_LEVEL_COUNT(property, id) \
    case LEVEL_PROP_##property##_COUNT: \
        if(FAILED(ScriptVariant_IntegerValue(value, &integer)) || \
           !obor_level_set_array_count(handle, OBOR_LEVEL_ARRAY_##id, integer)) goto error; \
        break
    switch(property)
    {
    SET_LEVEL_COLLECTION(BASEMAP, BASEMAP);
    SET_LEVEL_COUNT(BASEMAP, BASEMAP);
    SET_LEVEL_COLLECTION(HOLE, HOLE);
    SET_LEVEL_COUNT(HOLE, HOLE);
    SET_LEVEL_COLLECTION(LAYER, LAYER);
    SET_LEVEL_COUNT(LAYER, LAYER);
    SET_LEVEL_COLLECTION(LAYER_BACKGROUND, BACKGROUND);
    SET_LEVEL_COUNT(LAYER_BACKGROUND, BACKGROUND);
    SET_LEVEL_COLLECTION(LAYER_FOREGROUND, FOREGROUND);
    SET_LEVEL_COUNT(LAYER_FOREGROUND, FOREGROUND);
    SET_LEVEL_COLLECTION(LAYER_FRONTPANEL, FRONT);
    SET_LEVEL_COUNT(LAYER_FRONTPANEL, FRONT);
    SET_LEVEL_COLLECTION(LAYER_GENERIC, GENERIC);
    SET_LEVEL_COUNT(LAYER_GENERIC, GENERIC);
    SET_LEVEL_COLLECTION(LAYER_PANEL, PANEL);
    SET_LEVEL_COUNT(LAYER_PANEL, PANEL);
    SET_LEVEL_COLLECTION(LAYER_REF, REFERENCE);
    SET_LEVEL_COUNT(LAYER_REF, REFERENCE);
    SET_LEVEL_COLLECTION(LAYER_WATER, WATER);
    SET_LEVEL_COUNT(LAYER_WATER, WATER);
    SET_LEVEL_COLLECTION(PALETTE, PALETTE);
    SET_LEVEL_COUNT(PALETTE, PALETTE);
    SET_LEVEL_COLLECTION(SPAWN, SPAWN);
    SET_LEVEL_COUNT(SPAWN, SPAWN);
    SET_LEVEL_COLLECTION(TEXT_OBJECT, TEXT);
    SET_LEVEL_COUNT(TEXT_OBJECT, TEXT);
    SET_LEVEL_COUNT(WALL, WALL);
    case LEVEL_PROP_LAYER_BACKGROUND_DEFAULT_HANDLE:
        if((value->vt != VT_PTR && value->vt != VT_EMPTY) ||
           !obor_level_set_background(handle, value->ptrVal)) goto error;
        break;
    case LEVEL_PROP_AUTO_SCROLL_DIRECTION:
        SET_LEVEL_INTEGER(bgdir);
        break;
    case LEVEL_PROP_AUTO_SCROLL_X:
        SET_LEVEL_DECIMAL(bgspeed);
        break;
    case LEVEL_PROP_AUTO_SCROLL_Y:
        SET_LEVEL_DECIMAL(vbgspeed);
        break;
    case LEVEL_PROP_BOSS_COUNT:
        SET_LEVEL_INTEGER(bosses);
        break;
    case LEVEL_PROP_BOSS_MUSIC_NAME:
    {
        const char *text = value->vt == VT_STR ? StrCache_GetIfPresent(value->strVal) : NULL;
        if(!text || strlen(text) >= sizeof(handle->bossmusic)) goto error;
        memcpy(handle->bossmusic, text, strlen(text) + 1);
        break;
    }
    case LEVEL_PROP_BOSS_MUSIC_OFFSET:
        SET_LEVEL_INTEGER(bossmusic_offset);
        break;
    case LEVEL_PROP_BOSS_SLOW:
        SET_LEVEL_INTEGER(boss_slow);
        break;
    case LEVEL_PROP_CAMERA_OFFSET_X:
        SET_LEVEL_INTEGER(cameraxoffset);
        break;
    case LEVEL_PROP_CAMERA_OFFSET_Z:
        SET_LEVEL_INTEGER(camerazoffset);
        break;
    case LEVEL_PROP_COMPLETE_FORCE:
        SET_LEVEL_INTEGER(forcefinishlevel);
        break;
    case LEVEL_PROP_GAMEOVER:
        SET_LEVEL_INTEGER(force_gameover);
        break;
    case LEVEL_PROP_DAMAGE_FROM_ENEMY:
        SET_LEVEL_INTEGER(nohurt);
        break;
    case LEVEL_PROP_DAMAGE_FROM_PLAYER:
        SET_LEVEL_INTEGER(nohit);
        break;
    case LEVEL_PROP_FACING:
        SET_LEVEL_INTEGER(facing);
        break;
    case LEVEL_PROP_GRAVITY:
        SET_LEVEL_DECIMAL(gravity);
        break;
    case LEVEL_PROP_MAX_FALL_VELOCITY:
        SET_LEVEL_DECIMAL(maxfallspeed);
        break;
    case LEVEL_PROP_MAX_TOSS_VELOCITY:
        SET_LEVEL_DECIMAL(maxtossspeed);
        break;
    case LEVEL_PROP_MIRROR:
        SET_LEVEL_INTEGER(mirror);
        break;
    case LEVEL_PROP_NAME:
    {
        const char *text = value->vt == VT_STR ? StrCache_GetIfPresent(value->strVal) : NULL;
        if(!text) goto error;
        size_t size = strlen(text) + 1;
        char *name = malloc(size);
        if(!name) goto error;
        memcpy(name, text, size);
        free(handle->name);
        handle->name = name;
        break;
    }
    case LEVEL_PROP_POSITION_X:
        SET_LEVEL_INTEGER(pos);
        break;
    case LEVEL_PROP_QUAKE:
        SET_LEVEL_INTEGER(quake);
        break;
    case LEVEL_PROP_QUAKE_TIME:
        SET_LEVEL_INTEGER(quaketime);
        break;
    case LEVEL_PROP_ROCKING:
        SET_LEVEL_INTEGER(rocking);
        break;
    case LEVEL_PROP_SCROLL_DIRECTION:
        SET_LEVEL_INTEGER(scrolldir);
        break;
    case LEVEL_PROP_SCROLL_VELOCITY:
        SET_LEVEL_DECIMAL(scrollspeed);
        break;
    case LEVEL_PROP_SIZE_X:
        SET_LEVEL_INTEGER(width);
        break;
    case LEVEL_PROP_SPAWN_PLAYER_COLLECTION:
    {
        if(obor_profile_build < 4496) break;
        if(value->vt != VT_PTR && value->vt != VT_EMPTY) goto error;
        if(!value->ptrVal)
        {
            handle->obor_spawn_view = NULL;
            break;
        }
        for(int offset = 0; offset < MAX_PLAYERS; ++offset)
        {
            if(value->ptrVal == &handle->spawn[offset] && handle->player_spawn_count <= MAX_PLAYERS - offset)
            {
                handle->obor_spawn_view = value->ptrVal;
                return S_OK;
            }
        }
        goto error;
    }
    case LEVEL_PROP_SPECIAL_DISABLE:
        SET_LEVEL_INTEGER(nospecial);
        break;
    case LEVEL_PROP_TIME_ADVANCE:
        SET_LEVEL_INTEGER(advancetime);
        break;
    case LEVEL_PROP_TIME_DISPLAY:
        SET_LEVEL_INTEGER(notime);
        break;
    case LEVEL_PROP_TIME_RESET:
        SET_LEVEL_INTEGER(noreset);
        break;
    case LEVEL_PROP_TIME_SET:
        SET_LEVEL_INTEGER(settime);
        break;
    case LEVEL_PROP_TYPE:
        SET_LEVEL_INTEGER(type);
        break;
    case LEVEL_PROP_WAITING:
        SET_LEVEL_INTEGER(waiting);
        break;
    case LEVEL_PROP_WALL_COLLECTION:
        if(handle->walls)
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = handle->walls;
        }
        break;
    case LEVEL_PROP_WEAPON:
        SET_LEVEL_INTEGER(setweap);
        break;
    case LEVEL_PROP_SCRIPT_LEVEL_END:
        if(!obor_assign_level_script(&handle->endlevel_script, obor_level_script_source(handle, value))) goto error;
        break;
    case LEVEL_PROP_SCRIPT_LEVEL_START:
        if(!obor_assign_level_script(&handle->level_script, obor_level_script_source(handle, value))) goto error;
        break;
    case LEVEL_PROP_SCRIPT_KEY:
        if(!obor_assign_level_script(&handle->key_script, obor_level_script_source(handle, value))) goto error;
        break;
    case LEVEL_PROP_SCRIPT_UPDATE:
        if(!obor_assign_level_script(&handle->update_script, obor_level_script_source(handle, value))) goto error;
        break;
    case LEVEL_PROP_SCRIPT_UPDATED:
        if(!obor_assign_level_script(&handle->updated_script, obor_level_script_source(handle, value))) goto error;
        break;
    case LEVEL_PROP_PALETTE_BLENDING_COLLECTION:
        goto error;
    default:
        break;
    }
#undef SET_LEVEL_COUNT
#undef SET_LEVEL_COLLECTION
#undef SET_LEVEL_DECIMAL
#undef SET_LEVEL_INTEGER
    return S_OK;

error:
    printf("You must provide a valid handle and property: set_level_property(void handle, int property, value)\n");
    return E_FAIL;
}

static int obor_terrain_query_selector(const ScriptVariant *selector, const char *collection)
{
    const int mapped = obor_profile_build >= 4682 && obor_profile_build <= 4905;
    if(mapped && selector->vt == VT_INTEGER)
    {
        return 1;
    }
    if(mapped || selector->vt != VT_STR)
    {
        printf("You must provide a string value for %s subproperty.\n", collection);
    }
    return 0;
}

HRESULT openbor_getlevelproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    DOUBLE dbltemp2, dbltemp3;
    mapstrings_levelproperty(varlist, paramCount);

    switch(varlist[0]->lVal)
    {
    case _lp_bgspeed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->lVal = (DOUBLE)level->bgspeed;
        break;
    }
    case _lp_vbgspeed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->lVal = (DOUBLE)level->vbgspeed;
        break;
    }
    case _lp_cameraxoffset:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->cameraxoffset;
        break;
    }
    case _lp_camerazoffset:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->camerazoffset;
        break;
    }
    case _lp_gravity:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)level->gravity;
        break;
    }
    case _lp_maxfallspeed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)level->maxfallspeed;
        break;
    }
    case _lp_maxtossspeed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)level->maxtossspeed;
        break;
    }
    case _lp_quake:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->quake;
        break;
    }
    case _lp_scrollspeed:
    {
        ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
        (*pretvar)->dblVal = (DOUBLE)level->scrollspeed;
        break;
    }
    case _lp_type:
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)level->type;
        break;
    }
    case _lp_hole:
    {

        if(paramCount > 2 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp))
                && ltemp >= 0 && ltemp < level->numholes)
        {

            if(!obor_terrain_query_selector(varlist[2], "hole"))
            {
                goto getlevelproperty_error;
            }

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);

            switch(varlist[2]->lVal)
            {
                case _lp_terrain_height:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].height;
                    break;
                }
                case _lp_terrain_depth:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].depth;
                    break;
                }
                case _lp_terrain_lowerleft:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].lowerleft;
                    break;
                }
                case _lp_terrain_lowerright:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].lowerright;
                    break;
                }
                case _lp_terrain_upperleft:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].upperleft;
                    break;
                }
                case _lp_terrain_upperright:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].upperright;
                    break;
                }
                case _lp_terrain_x:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].x;
                    break;
                }
                case _lp_terrain_z:
                {
                    (*pretvar)->dblVal = level->holes[ltemp].z;
                    break;
                }
                case _lp_terrain_type:
                {
                    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
                    (*pretvar)->lVal = level->holes[ltemp].type;
                    break;
                }
                default:
                {
                    printf("Invalid subproperty for hole.\n");
                    goto getlevelproperty_error;
                }
            }
        }
        else
        {
            printf("Error in wall property.\n");
            goto getlevelproperty_error;
        }
        break;

    }
    case _lp_wall:
    {
        if(paramCount > 2 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp))
                && ltemp >= 0 && ltemp < level->numwalls)
        {

            if(!obor_terrain_query_selector(varlist[2], "wall"))
            {
                goto getlevelproperty_error;
            }

            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);

            switch(varlist[2]->lVal)
            {
                case _lp_terrain_depth:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].depth;
                    break;
                }
                case _lp_terrain_height:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].height;
                    break;
                }
                case _lp_terrain_lowerleft:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].lowerleft;
                    break;
                }
                case _lp_terrain_lowerright:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].lowerright;
                    break;
                }
                case _lp_terrain_upperleft:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].upperleft;
                    break;
                }
                case _lp_terrain_upperright:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].upperright;
                    break;
                }
                case _lp_terrain_x:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].x;
                    break;
                }
                case _lp_terrain_z:
                {
                    (*pretvar)->dblVal = level->walls[ltemp].z;
                    break;
                }
                case _lp_terrain_type:
                {
                    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
                    (*pretvar)->lVal = level->walls[ltemp].type;
                    break;
                }
                default:
                {
                    printf("Invalid subproperty for wall.\n");
                    goto getlevelproperty_error;
                }
            }
        }
        else
        {
            printf("Error in wall property.\n");
            goto getlevelproperty_error;
        }
        break;
    }
    case _lp_basemap:
        if(paramCount >= 2 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)) &&
           ltemp >= 0 && ltemp < level->numbasemaps)
        {
            if(paramCount >= 3)
            {

                if(!obor_terrain_query_selector(varlist[2], "basemap"))
                {
                    goto getlevelproperty_error;
                }

                ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);

                switch(varlist[2]->lVal)
                {
                case _lp_bm_x:
                    (*pretvar)->dblVal = level->basemaps[ltemp].position.x;
                    break;
                case _lp_bm_xsize:
                    (*pretvar)->dblVal = level->basemaps[ltemp].size.x;
                    break;
                case _lp_bm_z:
                    (*pretvar)->dblVal = level->basemaps[ltemp].position.z;
                    break;
                case _lp_bm_zsize:
                    (*pretvar)->dblVal = level->basemaps[ltemp].size.z;
                    break;
                case _lp_bm_map:
                    if(paramCount >= 5 && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp2)) &&
                            SUCCEEDED(ScriptVariant_DecimalValue(varlist[4], &dbltemp3)) &&
                            dbltemp2 >= 0 && dbltemp2 < level->basemaps[ltemp].size.x && dbltemp3 >= 0 && dbltemp3 < level->basemaps[ltemp].size.z
                      )
                    {
                        if(!level->basemaps[ltemp].map)
                        {
                            (*pretvar)->dblVal = (DOUBLE)0;
                        }
                        else
                        {
                            const s_basemap *basemap = &level->basemaps[ltemp];
                            const double cell = dbltemp2 + dbltemp3 * basemap->size.x;
                            if(cell >= (double)INT_MAX + 1.0 ||
                               (size_t)cell >= obor_allocation_size(basemap->map) / sizeof(*basemap->map))
                            {
                                goto getlevelproperty_error;
                            }
                            (*pretvar)->dblVal = (DOUBLE)basemap->map[(size_t)cell];
                        }
                    }
                    else
                    {
                        goto getlevelproperty_error;
                    }
                    break;
                default:
                    goto getlevelproperty_error;
                }
            }
            else
            {
                goto getlevelproperty_error;
            }
        }
        else
        {
            goto getlevelproperty_error;
        }
        break;
    default:
        printf("Property is not supported by function getlevelproperty yet. %d\n", varlist[0]->lVal);
        goto getlevelproperty_error;
        break;
    }

    return S_OK;

getlevelproperty_error:
    *pretvar = NULL;
    return E_FAIL;
}

/* Older scripts converted the two coordinates separately. Later scripts
 * check the fractional coordinates and convert only the resulting cell. */
static int obor_basemap_set_cell(s_basemap *map, double x, double z, double height)
{
    const int legacy = obor_profile_build >= 4283 && obor_profile_build < 4390;
    const int width = map->size.x;
    const int depth = map->size.z;
    uint64_t cell;

    if(width <= 0 || depth <= 0)
        return 0;
    if(legacy)
    {
        if(!(x > -1.0 && x < width && z > -1.0 && z < depth))
            return 0;
        cell = (uint64_t)(int)z * width + (int)x;
    }
    else
    {
        double flat;
        if(!(x >= 0 && x < width && z >= 0 && z < depth))
            return 0;
        flat = x + z * width;
        if(flat >= (double)INT_MAX + 1.0)
            return 0;
        cell = (int)flat;
    }
    if(cell > INT_MAX)
        return 0;

    if(!map->map)
    {
        const unsigned padding = legacy ? 0 : 1;
        const uint64_t cells = ((uint64_t)width + padding) * ((uint64_t)depth + padding);
        const uint64_t limit = legacy ? SIZE_MAX : INT_MAX;
        if(cell >= cells || cells > limit / sizeof(*map->map))
            return 0;
        map->map = calloc((size_t)cells, sizeof(*map->map));
        if(!map->map)
            return 0;
    }
    else if(cell >= obor_allocation_size(map->map) / sizeof(*map->map))
    {
        return 0;
    }
    map->map[cell] = (float)height;
    return 1;
}

//changelevelproperty(name, value)
HRESULT openbor_changelevelproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp, ltemp1;
    DOUBLE dbltemp, dbltemp2, dbltemp3;
    static char buf[64];
    int i;
    ScriptVariant *arg = NULL;

    *pretvar = NULL;

    if(paramCount < 2)
    {
        printf("Function changelevelproperty(prop, value) need at least 2 parameters.\n");
        return E_FAIL;
    }

    mapstrings_levelproperty(varlist, paramCount);

    arg = varlist[1];

    switch(varlist[0]->lVal)
    {
    case _lp_rocking:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            level->rocking = (int)ltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_bgspeed:
        if(SUCCEEDED(ScriptVariant_DecimalValue(arg, &dbltemp)))
        {
            level->bgspeed = (float)dbltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_vbgspeed:
        if(SUCCEEDED(ScriptVariant_DecimalValue(arg, &dbltemp)))
        {
            level->vbgspeed = (float)dbltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_scrollspeed:
        if(SUCCEEDED(ScriptVariant_DecimalValue(arg, &dbltemp)))
        {
            level->scrollspeed = (float)dbltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_type:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            level->type = (int)ltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_cameraxoffset:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            level->cameraxoffset = (int)ltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_camerazoffset:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            level->camerazoffset = (int)ltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_gravity:
        if(SUCCEEDED(ScriptVariant_DecimalValue(arg, &dbltemp)))
        {
            level->gravity = (float)dbltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_maxfallspeed:
        if(SUCCEEDED(ScriptVariant_DecimalValue(arg, &dbltemp)))
        {
            level->maxfallspeed = (float)dbltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_maxtossspeed:
        if(SUCCEEDED(ScriptVariant_DecimalValue(arg, &dbltemp)))
        {
            level->maxtossspeed = (float)dbltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_quake:
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            level->quake = (int)ltemp;
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_basemap:
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)) && ltemp >= 0)
        {
            if(ltemp >= level->numbasemaps)
            {
                if(level->obor_arrays)
                {
                    if(ltemp == INT_MAX || !obor_level_grow_array(level, OBOR_LEVEL_ARRAY_BASEMAP, ltemp + 1))
                        goto clperror;
                }
                else
                {
                    __reallocto(level->basemaps, level->numbasemaps, ltemp + 1);
                    level->numbasemaps = ltemp + 1;
                }
            }
            if(paramCount >= 4)
            {
                switch(varlist[2]->lVal)
                {
                case _lp_bm_x:
                    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp2)) )
                    {
                        level->basemaps[ltemp].position.x = dbltemp2;
                    }
                    else
                    {
                        goto clperror;
                    }
                    break;
                case _lp_bm_xsize:
                    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp2)) )
                    {
                        level->basemaps[ltemp].size.x = dbltemp2;
                    }
                    else
                    {
                        goto clperror;
                    }
                    break;
                case _lp_bm_z:
                    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp2)) )
                    {
                        level->basemaps[ltemp].position.z = dbltemp2;
                    }
                    else
                    {
                        goto clperror;
                    }
                    break;
                case _lp_bm_zsize:
                    if(SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp2)) )
                    {
                        level->basemaps[ltemp].size.z = dbltemp2;
                    }
                    else
                    {
                        goto clperror;
                    }
                    break;
                case _lp_bm_map:
                    if(paramCount < 6 || FAILED(ScriptVariant_DecimalValue(varlist[3], &dbltemp2)) ||
                       FAILED(ScriptVariant_DecimalValue(varlist[4], &dbltemp3)) ||
                       FAILED(ScriptVariant_DecimalValue(varlist[5], &dbltemp)) ||
                       !obor_basemap_set_cell(&level->basemaps[ltemp], dbltemp2, dbltemp3, dbltemp))
                        goto clperror;
                    break;
                default:
                    goto clperror;
                }
            }
            else
            {
                goto clperror;
            }
        }
        else
        {
            goto clperror;
        }
        break;
    case _lp_hole:
    {
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)) && ltemp >= 0
           && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            if(!obor_terrain_query_selector(varlist[2], "hole"))
            {
                goto clperror;
            }

            if(ltemp >= level->numholes)
            {
                if(ltemp == INT_MAX) goto clperror;
                if(level->obor_arrays)
                {
                    if(!obor_level_grow_array(level, OBOR_LEVEL_ARRAY_HOLE, ltemp + 1))
                        goto clperror;
                }
                else
                {
                    __reallocto(level->holes, level->numholes, ltemp + 1);
                    level->numholes = ltemp + 1;
                }
            }

            switch(varlist[2]->lVal)
            {
                case _lp_terrain_height:
                {
                    level->holes[ltemp].height = dbltemp;
                    break;
                }
                case _lp_terrain_depth:
                {
                    level->holes[ltemp].depth = dbltemp;
                    break;
                }
                case _lp_terrain_lowerleft:
                {
                    level->holes[ltemp].lowerleft = dbltemp;
                    break;
                }
                case _lp_terrain_lowerright:
                {
                    level->holes[ltemp].lowerright = dbltemp;
                    break;
                }
                case _lp_terrain_upperleft:
                {
                    level->holes[ltemp].upperleft = dbltemp;
                    break;
                }
                case _lp_terrain_upperright:
                {
                    level->holes[ltemp].upperright = dbltemp;
                    break;
                }
                case _lp_terrain_x:
                {
                    level->holes[ltemp].x = dbltemp;
                    break;
                }
                case _lp_terrain_z:
                {
                    level->holes[ltemp].z = dbltemp;
                    break;
                }
                case _lp_terrain_type:
                {
                    if(FAILED(ScriptVariant_IntegerValue(varlist[3], &ltemp1)))
                    {
                        goto clperror;
                    }
                    level->holes[ltemp].type = ltemp1;
                    break;
                }
                default:
                {
                    printf("Invalid subproperty for hole.\n");
                    goto clperror;
                }
            }
        }
        else
        {
            goto clperror;
        }
        break;

    }
    case _lp_wall:
    {
        if(paramCount >= 4 && SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)) && ltemp >= 0
           && SUCCEEDED(ScriptVariant_DecimalValue(varlist[3], &dbltemp)))
        {
            if(!obor_terrain_query_selector(varlist[2], "wall"))
            {
                goto clperror;
            }

            if(ltemp >= level->numwalls)
            {
                if(ltemp == INT_MAX) goto clperror;
                if(level->obor_arrays)
                {
                    if(!obor_level_grow_array(level, OBOR_LEVEL_ARRAY_WALL, ltemp + 1))
                        goto clperror;
                }
                else
                {
                    __reallocto(level->walls, level->numwalls, ltemp + 1);
                    level->numwalls = ltemp + 1;
                }
            }

            switch(varlist[2]->lVal)
            {
                case _lp_terrain_depth:
                {
                    level->walls[ltemp].depth = dbltemp;
                    break;
                }
                case _lp_terrain_height:
                {
                    level->walls[ltemp].height = dbltemp;
                    break;
                }
                case _lp_terrain_lowerleft:
                {
                    level->walls[ltemp].lowerleft = dbltemp;
                    break;
                }
                case _lp_terrain_lowerright:
                {
                    level->walls[ltemp].lowerright = dbltemp;
                    break;
                }
                case _lp_terrain_upperleft:
                {
                    level->walls[ltemp].upperleft = dbltemp;
                    break;
                }
                case _lp_terrain_upperright:
                {
                    level->walls[ltemp].upperright = dbltemp;
                    break;
                }
                case _lp_terrain_x:
                {
                    level->walls[ltemp].x = dbltemp;
                    break;
                }
                case _lp_terrain_z:
                {
                    level->walls[ltemp].z = dbltemp;
                    break;
                }
                case _lp_terrain_type:
                {
                    if(FAILED(ScriptVariant_IntegerValue(varlist[3], &ltemp1)))
                    {
                        goto clperror;
                    }
                    level->walls[ltemp].type = ltemp1;
                    break;
                }
                default:
                {
                    printf("Invalid subproperty for wall.\n");
                    goto clperror;
                }
            }
        }
        else
        {
            goto clperror;
        }
        break;
    }
    default:
        printf("Invalid or read-only level property.\n");
        return E_FAIL;
        break;
    }

    return S_OK;
clperror:
    printf("Function changelevelproperty(prop, value) received invalid value(s). \n");
    printf("Dumping values: ");
    for(i = 1; i < paramCount; i++)
    {
        ScriptVariant_ToString(varlist[i], buf);
        printf("%s, ", buf);
    }
    printf("\n");
    return E_FAIL;
}


//shutdown(status, message)
HRESULT openbor_shutdown(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp = 0;

    *pretvar = NULL;

    if(paramCount > 0 && FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)))
    {
        goto shutdown_error;
    }
    if(paramCount > 1 && varlist[1]->vt != VT_STR)
    {
        goto shutdown_error;
    }

    shutdown((int)ltemp,  paramCount > 1 ? StrCache_Get(varlist[1]->strVal) : (DEFAULT_SHUTDOWN_MESSAGE));

    return S_OK;
shutdown_error:
    printf("shutdown(status, message): both parameters are optional but must be valid.\n");
    return E_FAIL;
}

//jumptobranch(name, immediate)
HRESULT openbor_jumptobranch(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    extern char branch_name[MAX_NAME_LEN + 1];
    *pretvar = NULL;
    if(paramCount < 1)
    {
        goto jumptobranch_error;
    }
    if(varlist[0]->vt != VT_STR)
    {
        goto jumptobranch_error;
    }

    obor_profile_copy_name(branch_name, StrCache_Get(varlist[0]->strVal));

    if(paramCount >= 2)
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)))
        {
            endgame = (int)ltemp;
            // 1 means goto that level immediately, or, wait until the level is complete
        }
        else
        {
            goto jumptobranch_error;
        }
    }

    return S_OK;
jumptobranch_error:
    printf("Function requires 1 string value, the second argument is optional(int): jumptobranch(name, immediate)\n");
    return E_FAIL;
}

/* Adapted from OpenBOR 4905 binding properties by Damon V. Caskey. */
enum obor_binding_property
{
    _binding_animation,
    _binding_bind_x,
    _binding_bind_y,
    _binding_bind_z,
    _binding_direction,
    _binding_entity,
    _binding_offset_x,
    _binding_offset_y,
    _binding_offset_z,
    _binding_sort_id,
    _binding_the_end
};

static int mapstrings_binding(ScriptVariant **varlist, int paramCount)
{
    static const char *properties[] =
    {
        "animation", "bind_x", "bind_y", "bind_z", "direction",
        "entity", "offset_x", "offset_y", "offset_z", "sort_id"
    };
    if(paramCount < 2 || !varlist || !varlist[1] || varlist[1]->vt != VT_STR)
        return 1;

    ScriptVariant *selector = varlist[1];
    const char *name = StrCache_GetIfPresent(selector->strVal);
    const int property = name ? searchList(properties, name, _binding_the_end) : -1;
    if(property < 0)
    {
        printf("Property name '%s' is not supported by binding.\n", name ? name : "");
        return 0;
    }
    ScriptVariant_ChangeType(selector, VT_INTEGER);
    selector->lVal = property;
    return 1;
}

static s_bind *obor_binding_handle(const ScriptVariant *value)
{
    if(!value || value->vt != VT_PTR || !value->ptrVal ||
       (uintptr_t)value->ptrVal % _Alignof(s_bind) ||
       !obor_allocation_contains(value->ptrVal, sizeof(s_bind)))
        return NULL;
    return value->ptrVal;
}

static HRESULT openbor_get_binding_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;

    ScriptVariant_Clear(*pretvar);
    mapstrings_binding(varlist, paramCount);
    const s_bind *binding = paramCount >= 2 && varlist ? obor_binding_handle(varlist[0]) : NULL;
    if(!binding || !varlist[1] || varlist[1]->vt != VT_INTEGER)
        goto invalid;

    LONG value;
    switch(varlist[1]->lVal)
    {
    case _binding_animation: value = binding->ani_bind; break;
    case _binding_bind_x: value = binding->offset_flag.x; break;
    case _binding_bind_y: value = binding->offset_flag.y; break;
    case _binding_bind_z: value = binding->offset_flag.z; break;
    case _binding_direction: value = binding->direction; break;
    case _binding_entity:
        if(binding->ent)
        {
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = binding->ent;
        }
        return S_OK;
    case _binding_offset_x: value = binding->offset.x; break;
    case _binding_offset_y: value = binding->offset.y; break;
    case _binding_offset_z: value = binding->offset.z; break;
    case _binding_sort_id: value = binding->sortid; break;
    default:
        printf("Unsupported property.\n");
        goto invalid;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = value;
    return S_OK;

invalid:
    printf("You must provide a valid binding handle and property name: "
           "openbor_get_binding_property(void handle, char property)\n");
    *pretvar = NULL;
    return E_FAIL;
}

static HRESULT openbor_set_binding_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    if(!pretvar) return E_FAIL;

    mapstrings_binding(varlist, paramCount);
    s_bind *binding = paramCount >= 3 && varlist ? obor_binding_handle(varlist[0]) : NULL;
    if(!binding || !varlist[1] || varlist[1]->vt != VT_INTEGER || !varlist[2])
    {
        *pretvar = NULL;
        goto invalid;
    }

    const LONG property = varlist[1]->lVal;
    if(property < 0 || property >= _binding_the_end)
    {
        printf("Unsupported property.\n");
        goto invalid;
    }
    if(property == _binding_entity)
    {
        if(varlist[2]->vt == VT_EMPTY)
            binding->ent = NULL;
        else if(varlist[2]->vt == VT_PTR &&
                (!varlist[2]->ptrVal || obor_allocation_contains(varlist[2]->ptrVal, sizeof(entity))))
            binding->ent = varlist[2]->ptrVal;
        return S_OK;
    }

    LONG value;
    if(FAILED(ScriptVariant_IntegerValue(varlist[2], &value))) return S_OK;
    switch(property)
    {
    case _binding_animation: binding->ani_bind = value; break;
    case _binding_bind_x: binding->offset_flag.x = value; break;
    case _binding_bind_y: binding->offset_flag.y = value; break;
    case _binding_bind_z: binding->offset_flag.z = value; break;
    case _binding_direction: binding->direction = (e_direction_adjust)value; break;
    case _binding_offset_x: binding->offset.x = value; break;
    case _binding_offset_y: binding->offset.y = value; break;
    case _binding_offset_z: binding->offset.z = value; break;
    case _binding_sort_id: binding->sortid = value; break;
    }
    return S_OK;

invalid:
    printf("You must provide a valid binding handle, property, and new value: "
           "set_binding_property(void handle, char property, value)\n");
    return E_FAIL;
}

//bindentity(entity, target, x, z, a, direction, binding.ani_bind);
//bindentity(entity, NULL()); // unbind
HRESULT openbor_bindentity(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    entity *ent = NULL;
    entity *other = NULL;
    ScriptVariant *arg = NULL;
    void adjust_bind(entity * e);
    LONG x = 0, z = 0, a = 0, dir = 0, anim = 0, sortid = -1;
    const int bind_sort = obor_profile_build < 4283 || obor_profile_build >= 4396;

    *pretvar = NULL;
    if(paramCount < 2)
    {
        return E_FAIL;
    }

    ent = (entity *)(varlist[0])->ptrVal; //retrieve the entity
    if(!ent)
    {
        return S_OK;
    }

    other = (entity *)(varlist[1])->ptrVal;
    if(!other)
    {
        ent->binding.ent = NULL;
        ent->binding.offset_flag.x = 0;
        ent->binding.offset_flag.z = 0;
        ent->binding.offset_flag.y = 0;
        return S_OK;
    }

    ent->binding.ent = other;
    if(bind_sort)
    {
        ent->binding.sortid = sortid;
    }

    if(paramCount < 3)
    {
        goto BIND;
    }
    // x
    arg = varlist[2];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &x)))
        {
            return E_FAIL;
        }

        ent->binding.offset.x = (int)x;
        ent->binding.offset_flag.x = 1;
    } else ent->binding.offset_flag.x = 0;
    if(paramCount < 4)
    {
        goto BIND;
    }
    // z
    arg = varlist[3];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &z)))
        {
            return E_FAIL;
        }
        ent->binding.offset.z = (int)z;
        ent->binding.offset_flag.z = 1;
    } else ent->binding.offset_flag.z = 0;
    if(paramCount < 5)
    {
        goto BIND;
    }
    // a
    arg = varlist[4];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &a)))
        {
            return E_FAIL;
        }
        ent->binding.offset.y = (int)a;
        ent->binding.offset_flag.y = 1;
    } else ent->binding.offset_flag.y = 0;
    if(paramCount < 6)
    {
        goto BIND;
    }
    // direction
    arg = varlist[5];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &dir)))
        {
            return E_FAIL;
        }
        ent->binding.direction = (int)dir;
    }
    if(paramCount < 7)
    {
        goto BIND;
    }
    // animation
    arg = varlist[6];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &anim)))
        {
            return E_FAIL;
        }
        ent->binding.ani_bind = (int)anim;
    }
    if(!bind_sort || paramCount < 8)
    {
        goto BIND;
    }
    // sortid
    arg = varlist[7];
    if(arg->vt != VT_EMPTY)
    {
        if(FAILED(ScriptVariant_IntegerValue(arg, &sortid)))
        {
            return E_FAIL;
        }
        ent->binding.sortid = (int)sortid;
    }

BIND:
    adjust_bind(ent);

    return S_OK;
}

//array(size);
HRESULT openbor_array(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG size;
    Varlist *array;

    if(!pretvar || !*pretvar) return E_FAIL;
    if(paramCount < 1 || !varlist || !varlist[0] ||
       FAILED(ScriptVariant_IntegerValue(varlist[0], &size)) || size < 0 || size == INT_MAX)
    {
        printf("Function requires 1 positive int value: array(int size)\n");
        goto array_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    array = malloc(sizeof(*array));
    (*pretvar)->ptrVal = (VOID *)array;

    if((*pretvar)->ptrVal == NULL)
    {
        printf("Not enough memory: array(%d)\n", (int)size);
        goto array_error;
    }

    Varlist_Init(array, size);

    List_InsertAfter(&scriptheap, (void *)(array), "openbor_array");
    return S_OK;

array_error:
    (*pretvar) = NULL;
    return E_FAIL;
}

//size(array)
HRESULT openbor_size(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto size_error;
    }

    // By White Dragon
    if( array->list->size != 0 ) //or array->list->first
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)array->list->size;
    }
    else
    {
        ScriptVariant_Copy(*pretvar, array->vars);
    }

    return S_OK;
size_error:
    printf("Function requires 1 array handle: %s(array)\n", "size");
    (*pretvar) = NULL;
    return E_FAIL;
}

//get(array, index);
HRESULT openbor_get(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *ptmpvar;
    Varlist *array;
    LONG ltemp;

    if(paramCount < 2 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto get_error;
    }

    if(varlist[1]->vt == VT_STR)
    {
        ptmpvar = Varlist_GetByName(array, StrCache_Get(varlist[1]->strVal));
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)))
    {
        ptmpvar = Varlist_GetByIndex(array, (int)ltemp);
    }
    else
    {
        goto get_error;
    }

    if(ptmpvar)
    {
        ScriptVariant_Copy(*pretvar,  ptmpvar);
    }
    else
    {
        ScriptVariant_Clear(*pretvar);
    }
    return S_OK;

get_error:
    printf("Function requires 1 array handle and 1 int value: get(array, int index)\n");
    (*pretvar) = NULL;
    return E_FAIL;
}

//set(array, index, value);
HRESULT openbor_set(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    LONG ltemp;

    *pretvar = NULL;
    if(paramCount < 3 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto set_error;
    }

    if(varlist[1]->vt == VT_STR)
    {
        Varlist_SetByName(array, StrCache_Get(varlist[1]->strVal), varlist[2]);
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &ltemp)))
    {
        Varlist_SetByIndex(array, (int)ltemp, varlist[2]);
    }
    else
    {
        goto set_error;
    }

    return S_OK;

set_error:
    printf("Function requires 1 array handle, 1 int value and 1 value: set(array, int index, value)\n");
    return E_FAIL;
}

//delete(array, index); // By White Dragon
HRESULT openbor_delete(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    LONG index;

    *pretvar = NULL;
    if(paramCount < 2 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto set_error;
    }

    if(varlist[1]->vt == VT_STR)
    {
        if ( !Varlist_DeleteByName(array, StrCache_Get(varlist[1]->strVal)) ) goto set_error;
    }
    else if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &index)))
    {
        if ( !Varlist_DeleteByIndex(array, (int)index) ) goto set_error;
    }
    else
    {
        goto set_error;
    }

    return S_OK;

set_error:
    printf("Function requires 1 array handle and 1 int value (index): delete(array, index)\n");
    return E_FAIL;
}

//add(array, index); // By White Dragon
HRESULT openbor_add(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    LONG index;

    if(!pretvar)
    {
        return E_FAIL;
    }

    *pretvar = NULL;
    if(paramCount < 3 || !varlist || !varlist[0] || !varlist[1] || !varlist[2] ||
       varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto add_error;
    }

    if((obor_profile_build < 4283 || obor_profile_build >= 4420) && varlist[1]->vt == VT_STR)
    {
        char *name = StrCache_GetIfPresent(varlist[1]->strVal);
        if(!name)
        {
            goto add_error;
        }
        Varlist_SetByName(array, name, varlist[2]);
    }
    else if( SUCCEEDED(ScriptVariant_IntegerValue(varlist[1], &index)) )
    {
        if ( !Varlist_AddByIndex(array, (int)index, varlist[2]) ) goto add_error;
    }
    else
    {
        goto add_error;
    }

    return S_OK;

add_error:
    printf("Function requires 1 array handle and 1 int value (index): add(array, index)\n");
    return E_FAIL;
}

//reset(array)
HRESULT openbor_reset(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto reset_error;
    }
    List_Reset(array->list);

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)(array->list->current != NULL);

    return S_OK;
reset_error:
    printf("Function requires 1 array handle: %s(array)\n", "reset");
    (*pretvar) = NULL;
    return E_FAIL;
}

//next(array)
HRESULT openbor_next(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto next_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)(List_GotoNext(array->list));

    return S_OK;
next_error:
    printf("Function requires 1 array handle: %s(array)\n", "next");
    (*pretvar) = NULL;
    return E_FAIL;
}

//previous(array)
HRESULT openbor_previous(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto previous_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)(array->list->current && List_GotoPrevious(array->list));

    return S_OK;
previous_error:
    printf("Function requires 1 array handle: %s(array)\n", "previous");
    (*pretvar) = NULL;
    return E_FAIL;
}

//islast(array)
HRESULT openbor_islast(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto islast_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)(  List_Retrieve(array->list) == List_GetLast(array->list) );

    return S_OK;
islast_error:
    printf("Function requires 1 array handle: %s(array)\n", "islast");
    (*pretvar) = NULL;
    return E_FAIL;
}

//isfirst(array)
HRESULT openbor_isfirst(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto isfirst_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)(  List_Retrieve(array->list) == List_GetFirst(array->list) );

    return S_OK;
isfirst_error:
    printf("Function requires 1 array handle: %s(array)\n", "isfirst");
    (*pretvar) = NULL;
    return E_FAIL;
}

//key(array)
HRESULT openbor_key(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    char *name;
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto key_error;
    }

    name = List_GetName(array->list);
    if(name)
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, name);
    }
    else
    {
        ScriptVariant_Clear(*pretvar);
    }

    return S_OK;
key_error:
    printf("Function requires 1 array handle: %s(array)\n", "key");
    (*pretvar) = NULL;
    return E_FAIL;
}

//value(array)
HRESULT openbor_value(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    ScriptVariant *var;
    Varlist *array;
    if(paramCount < 1 || varlist[0]->vt != VT_PTR || !(array = (Varlist *)varlist[0]->ptrVal) || array->magic != varlist_magic)
    {
        goto value_error;
    }

    var = List_Retrieve(array->list);
    if(var)
    {
        ScriptVariant_Copy(*pretvar, var);
    }
    else
    {
        ScriptVariant_Clear(*pretvar);
    }

    return S_OK;
value_error:
    printf("Function requires 1 array handle: %s(array)\n", "value");
    (*pretvar) = NULL;
    return E_FAIL;
}

//allocscreen(int w, int h);
HRESULT openbor_allocscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG w, h;
    s_screen *screen;

    if(paramCount < 2)
    {
        goto allocscreen_error;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &w)))
    {
        goto allocscreen_error;
    }
    if(FAILED(ScriptVariant_IntegerValue(varlist[1], &h)))
    {
        goto allocscreen_error;
    }


    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    screen = allocscreen((int)w, (int)h, screenformat);
    if(screen)
    {
        clearscreen(screen);
    }
    (*pretvar)->ptrVal = (VOID *)screen;

    if((*pretvar)->ptrVal == NULL)
    {
        printf("Not enough memory: allocscreen(%d, %d)\n", (int)w, (int)h);
        (*pretvar) = NULL;
        return E_FAIL;
    }
    List_InsertAfter(&scriptheap, (void *)((*pretvar)->ptrVal), "openbor_allocscreen");
    return S_OK;

allocscreen_error:
    printf("Function requires 2 int values: allocscreen(int width, int height)\n");
    (*pretvar) = NULL;
    return E_FAIL;
}

//clearscreen(s_screen* screen)
HRESULT openbor_clearscreen(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    s_screen *screen;

    *pretvar = NULL;
    if(paramCount != 1)
    {
        goto clearscreen_error;
    }
    if(varlist[0]->vt != VT_PTR)
    {
        goto clearscreen_error;
    }

    screen = (s_screen *)varlist[0]->ptrVal;

    if(screen == NULL)
    {
        printf("Error: NULL pointer passed to clearscreen(void screen)\n");
        *pretvar = NULL;
        return E_FAIL;
    }
    clearscreen(screen);
    return S_OK;

clearscreen_error:
    printf("Function requires a screen pointer: clearscreen(void screen)\n");
    return E_FAIL;
}

int mapstrings_drawmethodproperty(ScriptVariant **varlist, int paramCount)
{
    char *propname = NULL;
    int prop;

    static const char *proplist[] =
    {
        "alpha",
        "amplitude",
        "beginsize",
        "centerx",
        "centery",
        "channelb",
        "channelg",
        "channelr",
        "clip",
        "cliph",
        "clipw",
        "clipx",
        "clipy",
        "enabled",
        "endsize",
        "fillcolor",
        "flag",
        "fliprotate",
        "flipx",
        "flipy",
        "perspective",
        "remap",
        "reset",
        "rotate",
        "scalex",
        "scaley",
        "shiftx",
        "table",
        "tintcolor",
        "tintmode",
        "transbg",
        "watermode",
        "wavelength",
        "wavespeed",
        "wavetime",
        "xrepeat",
        "xspan",
        "yrepeat",
        "yspan",
    };


    if(paramCount < 2)
    {
        return 1;
    }
    MAPSTRINGS(varlist[1], proplist, _dm_the_end,
               "Property name '%s' is not supported by drawmethod.\n");

    return 1;
}

// changedrawmethod(entity, propertyname, value);
HRESULT openbor_changedrawmethod(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    entity *e;
    LONG temp = 0;
    DOUBLE ftemp = 0;
    s_drawmethod *pmethod;
    *pretvar = NULL;

    if(paramCount < 3)
    {
        goto changedm_error;
    }

    mapstrings_drawmethodproperty(varlist, paramCount);

    if(varlist[0]->vt == VT_EMPTY)
    {
        e = NULL;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto changedm_error;
    }

    if(e)
    {
        pmethod = &(e->drawmethod);
    }
    else
    {
        pmethod = &(drawmethod);
    }

    switch(varlist[1]->lVal)
    {

    case _dm_alpha:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->alpha = (int)temp;
        break;
    case _dm_amplitude:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->water.amplitude = (int)temp;
        break;
    case _dm_beginsize:
        if(FAILED(ScriptVariant_DecimalValue(varlist[2], &ftemp)))
        {
            return E_FAIL;
        }
        pmethod->water.beginsize = (float)ftemp;
        break;
    case _dm_centerx:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->centerx = (int)temp;
        break;
    case _dm_centery:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->centery = (int)temp;
        break;
    case _dm_channelb:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->channelb = (int)temp;
        break;
    case _dm_channelg:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->channelg = (int)temp;
        break;
    case _dm_channelr:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->channelr = (int)temp;
        break;
    case _dm_clip:
        if(paramCount < 6)
        {
            return E_FAIL;
        }
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->clipx = (int)temp;
        if(FAILED(ScriptVariant_IntegerValue(varlist[3], &temp)))
        {
            return E_FAIL;
        }
        pmethod->clipy = (int)temp;
        if(FAILED(ScriptVariant_IntegerValue(varlist[4], &temp)))
        {
            return E_FAIL;
        }
        pmethod->clipw = (int)temp;
        if(FAILED(ScriptVariant_IntegerValue(varlist[5], &temp)))
        {
            return E_FAIL;
        }
        pmethod->cliph = (int)temp;
        break;
    case _dm_clipx:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->clipx = (int)temp;
        break;
    case _dm_clipy:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->clipy = (int)temp;
        break;
    case _dm_clipw:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->clipw = (int)temp;
        break;
    case _dm_cliph:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->cliph = (int)temp;
        break;
    case _dm_enabled:
    case _dm_flag:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->flag = (int)temp;
        break;
    case _dm_endsize:
        if(FAILED(ScriptVariant_DecimalValue(varlist[2], &ftemp)))
        {
            return E_FAIL;
        }
        pmethod->water.endsize = (float)ftemp;
        break;
    case _dm_fillcolor:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->fillcolor = (int)temp;
        break;
    case _dm_fliprotate:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->fliprotate = (int)temp;
        break;
    case _dm_flipx:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->flipx = (int)temp;
        break;
    case _dm_flipy:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->flipy = (int)temp;
        break;
    case _dm_perspective:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->water.perspective = (int)temp;
        break;
    case _dm_remap:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->remap = (int)temp;
        break;
    case _dm_reset:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        if(temp)
        {
            *pmethod = plainmethod;
        }
        break;
    case _dm_rotate:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->rotate = (float)temp;
        break;
    case _dm_scalex:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->scalex = (int)temp;
        break;
    case _dm_scaley:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->scaley = (int)temp;
        break;
    case _dm_shiftx:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->shiftx = (int)temp;
        break;
    case _dm_table:
        if(varlist[2]->vt != VT_PTR && varlist[2]->vt != VT_EMPTY )
        {
            return E_FAIL;
        }
        pmethod->table = (void *)varlist[2]->ptrVal;
        break;
    case _dm_tintmode:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->tintmode = (int)temp;
        break;
    case _dm_tintcolor:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->tintcolor = (int)temp;
        break;
    case _dm_transbg:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->transbg = (int)temp;
        break;
    case _dm_watermode:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->water.watermode = (int)temp;
        break;
    case _dm_wavelength:
        if(FAILED(ScriptVariant_DecimalValue(varlist[2], &ftemp)))
        {
            return E_FAIL;
        }
        pmethod->water.wavelength = (float)ftemp;
        break;
    case _dm_wavespeed:
        if(FAILED(ScriptVariant_DecimalValue(varlist[2], &ftemp)))
        {
            return E_FAIL;
        }
        pmethod->water.wavespeed = (float)ftemp;
        break;
    case _dm_wavetime:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->water.wavetime = (int)(temp * pmethod->water.wavespeed);
        break;
    case _dm_xrepeat:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->xrepeat = (int)temp;
        break;
    case _dm_yrepeat:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->yrepeat = (int)temp;
        break;
    case _dm_xspan:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->xspan = (int)temp;
        break;
    case _dm_yspan:
        if(FAILED(ScriptVariant_IntegerValue(varlist[2], &temp)))
        {
            return E_FAIL;
        }
        pmethod->yspan = (int)temp;
        break;
    default:
        break;

    }

    return S_OK;

changedm_error:
    printf("Function changedrawmethod must have at least 3 parameters: entity, propertyname, value\n");
    return E_FAIL;
}

//getdrawmethod(<entity>, <property>)
HRESULT openbor_getdrawmethod(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    /*
    getdrawmethod
    Damon V. Caskey
    2013-11-09

    Allow module author to read current drawmethod settings.
    */
    entity *e;
    s_drawmethod *pmethod;

    if(!pretvar || !*pretvar)
    {
        return E_FAIL;
    }

    if(paramCount < 2 || !varlist || !varlist[0] || !varlist[1])
    {
        goto getdm_error;
    }

    ScriptVariant_Clear(*pretvar);
    mapstrings_drawmethodproperty(varlist, paramCount);

    if(varlist[0]->vt == VT_EMPTY)
    {
        e = NULL;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto getdm_error;
    }

    if(e)
    {
        pmethod = &(e->drawmethod);
    }
    else
    {
        pmethod = &(drawmethod);
    }

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    switch(varlist[1]->lVal)
    {
        case _dm_alpha:
            (*pretvar)->lVal = (int)pmethod->alpha;
            break;
        case _dm_amplitude:
            (*pretvar)->lVal = (int)pmethod->water.amplitude;
            break;
        case _dm_beginsize:
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (float)pmethod->water.beginsize;
            break;
        case _dm_centerx:
            (*pretvar)->lVal = (int)pmethod->centerx;
            break;
        case _dm_centery:
            (*pretvar)->lVal = (int)pmethod->centery;
            break;
        case _dm_channelb:
            (*pretvar)->lVal = (int)pmethod->channelb;
            break;
        case _dm_channelg:
            (*pretvar)->lVal = (int)pmethod->channelg;
            break;
        case _dm_channelr:
            (*pretvar)->lVal = (int)pmethod->channelr;
            break;
        case _dm_clipx:
            (*pretvar)->lVal = (int)pmethod->clipx;
            break;
        case _dm_clipy:
            (*pretvar)->lVal = (int)pmethod->clipy;
            break;
        case _dm_clipw:
            (*pretvar)->lVal = (int)pmethod->clipw;
            break;
        case _dm_cliph:
            (*pretvar)->lVal = (int)pmethod->cliph;
            break;
        case _dm_endsize:
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (float)pmethod->water.endsize;
            break;
        case _dm_fillcolor:
            (*pretvar)->lVal = (int)pmethod->fillcolor;
            break;
        case _dm_fliprotate:
            (*pretvar)->lVal = (int)pmethod->fliprotate;
            break;
        case _dm_flipx:
            (*pretvar)->lVal = (int)pmethod->flipx;
            break;
        case _dm_flipy:
            (*pretvar)->lVal = (int)pmethod->flipy;
            break;
        case _dm_perspective:
            (*pretvar)->lVal = (int)pmethod->water.perspective;
            break;
        case _dm_remap:
            (*pretvar)->lVal = (int)pmethod->remap;
            break;
        case _dm_rotate:
            (*pretvar)->lVal = (int)pmethod->rotate;
            break;
        case _dm_scalex:
            (*pretvar)->lVal = (int)pmethod->scalex;
            break;
        case _dm_scaley:
            (*pretvar)->lVal = (int)pmethod->scaley;
            break;
        case _dm_shiftx:
            (*pretvar)->lVal = (int)pmethod->shiftx;
            break;
        case _dm_table:
            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (void *)pmethod->table;
            break;
        case _dm_tintmode:
            (*pretvar)->lVal = (int)pmethod->tintmode;
            break;
        case _dm_tintcolor:
            (*pretvar)->lVal = (int)pmethod->tintcolor;
            break;
        case _dm_transbg:
            (*pretvar)->lVal = (int)pmethod->transbg;
            break;
        case _dm_watermode:
            (*pretvar)->lVal = (int)pmethod->water.watermode;
            break;
        case _dm_wavelength:
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (float)pmethod->water.wavelength;
            break;
        case _dm_wavespeed:
            ScriptVariant_ChangeType(*pretvar, VT_DECIMAL);
            (*pretvar)->dblVal = (float)pmethod->water.wavespeed;
            break;
        case _dm_wavetime:
            (*pretvar)->lVal = (int)pmethod->water.wavetime;
            break;
        case _dm_xrepeat:
            (*pretvar)->lVal = (int)pmethod->xrepeat;
            break;
        case _dm_yrepeat:
            (*pretvar)->lVal = (int)pmethod->yrepeat;
            break;
        case _dm_xspan:
            (*pretvar)->lVal = (int)pmethod->xspan;
            break;
        case _dm_yspan:
            (*pretvar)->lVal = pmethod->yspan;
            break;
        default:
        case _dm_enabled:
        case _dm_flag:
            (*pretvar)->lVal = (int)pmethod->flag;
            break;
    }

    return S_OK;

getdm_error:
    printf("Function getdrawmethod must have at least 2 parameters: entity, propertyname\n");
    *pretvar = NULL;
    return E_FAIL;
}

//deprecated
//setdrawmethod(entity, int flag, int scalex, int scaley, int flipx, int flipy, int shiftx, int alpha, int remap, int fillcolor, int rotate, int fliprotate, int transparencybg, void* colourmap, int centerx, int centery);
HRESULT openbor_setdrawmethod(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG value[14];
    entity *e;
    s_drawmethod *pmethod;
    int i;

    *pretvar = NULL;
    if(paramCount < 2)
    {
        goto setdrawmethod_error;
    }

    if(varlist[0]->vt == VT_EMPTY)
    {
        e = NULL;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto setdrawmethod_error;
    }

    if(e)
    {
        pmethod = &(e->drawmethod);
    }
    else
    {
        pmethod = &(drawmethod);
    }

    memset(value, 0, sizeof(value));
    for(i = 1; i < paramCount && i < 13; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i - 1)))
        {
            goto setdrawmethod_error;
        }
    }

    if(paramCount >= 14 && varlist[13]->vt != VT_PTR && varlist[13]->vt != VT_EMPTY)
    {
        goto setdrawmethod_error;
    }

    for(i = 14; i < paramCount && i < 16; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + (i - 2))))
        {
            goto setdrawmethod_error;
        }
    }

    pmethod->flag = (int)value[0];
    pmethod->scalex = (int)value[1];
    pmethod->scaley = (int)value[2];
    pmethod->flipx = (int)value[3];
    pmethod->flipy = (int)value[4];
    pmethod->shiftx = (int)value[5];
    pmethod->alpha = (int)value[6];
    pmethod->remap = (int)value[7];
    pmethod->fillcolor = (int)value[8];
    pmethod->rotate = ((int)value[9]) % 360;
    pmethod->fliprotate = (int)value[10];
    pmethod->transbg = (int)value[11];
    if(paramCount >= 14)
    {
        pmethod->table = (unsigned char *)varlist[13]->ptrVal;
    }
    pmethod->centerx = (int)value[12];
    pmethod->centery = (int)value[13];

    if(pmethod->rotate < 0)
    {
        pmethod->rotate += 360;
    }
    return S_OK;

setdrawmethod_error:
    printf("Function need a valid entity handle and at least 1 interger parameter, setdrawmethod(entity, int flag, int scalex, int scaley, int flipx, int flipy, int shiftx, int alpha, int remap, int fillcolor, int rotate, int fliprotate, int transparencybg, void* colourmap, centerx, centery)\n");
    return E_FAIL;
}

//updateframe(entity, int frame);
HRESULT openbor_updateframe(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG f;
    entity *e;
    void update_frame(entity * ent, int f);

    *pretvar = NULL;
    if(paramCount < 2)
    {
        goto updateframe_error;
    }

    if(varlist[0]->vt == VT_EMPTY)
    {
        e = NULL;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto updateframe_error;
    }

    if(!e)
    {
        goto updateframe_error;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[1], &f)))
    {
        goto updateframe_error;
    }

    update_frame(e, (int)f);

    return S_OK;

updateframe_error:
    printf("Function need a valid entity handle and at an interger parameter: updateframe(entity, int frame)\n");
    return E_FAIL;
}

//executeanimation(entity, int anim, int resetable);
HRESULT openbor_executeanimation(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG anim, resetable = 0;
    entity *e;

    *pretvar = NULL;
    if(paramCount < 1)
    {
        goto executeanimation_error;
    }

    if(varlist[0]->vt == VT_EMPTY)
    {
        e = NULL;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto executeanimation_error;
    }

    if(!e)
    {
        goto executeanimation_error;
    }

    e->takeaction = common_animation_normal;
    e->attacking = 0;
    e->idling = 0;
    e->drop = 0;
    e->falling = 0;
    e->inpain = 0;
    e->inbackpain = 0;
    e->blocking = 0;

    if(paramCount == 1)
    {
        return S_OK;
    }

    if(paramCount > 1 && FAILED(ScriptVariant_IntegerValue(varlist[1], &anim)))
    {
        goto executeanimation_error;
    }
    if(paramCount > 2 && FAILED(ScriptVariant_IntegerValue(varlist[2], &resetable)))
    {
        goto executeanimation_error;
    }
    ent_set_anim(e, (int)anim, (int)resetable);

    return S_OK;

executeanimation_error:
    printf("Function need a valid entity handle, the other 2 integer parameters are optional: performattack(entity, int anim, int resetable)\n");
    return E_FAIL;
}

//performattack(entity, int anim, int resetable);
HRESULT openbor_performattack(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG anim, resetable = 0;
    entity *e;

    *pretvar = NULL;
    if(paramCount < 1)
    {
        goto performattack_error;
    }

    if(varlist[0]->vt == VT_EMPTY)
    {
        e = NULL;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto performattack_error;
    }

    if(!e)
    {
        goto performattack_error;
    }

    e->takeaction = common_attack_proc;
    e->attacking = 1;
    e->idling = 0;
    e->drop = 0;
    e->falling = 0;
    e->inpain = 0;
    e->inbackpain = 0;
    e->blocking = 0;

    if(paramCount == 1)
    {
        return S_OK;
    }

    if(paramCount > 1 && FAILED(ScriptVariant_IntegerValue(varlist[1], &anim)))
    {
        goto performattack_error;
    }
    if(paramCount > 2 && FAILED(ScriptVariant_IntegerValue(varlist[2], &resetable)))
    {
        goto performattack_error;
    }
    ent_set_anim(e, (int)anim, (int)resetable);

    return S_OK;

performattack_error:
    printf("Function need a valid entity handle, the other 2 integer parameters are optional: performattack(entity, int anim, int resetable)\n");
    return E_FAIL;
}

//setidle(entity, int anim, int resetable, int stalladd);
HRESULT openbor_setidle(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG anim = 0, resetable = 0, stalladd = 0;
    entity *e;
    extern unsigned int time;

    *pretvar = NULL;
    if(paramCount < 1)
    {
        goto setidle_error;
    }

    if(varlist[0]->vt == VT_EMPTY)
    {
        e = NULL;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto setidle_error;
    }

    if(!e)
    {
        goto setidle_error;
    }

    e->takeaction = NULL;
    e->attacking = 0;
    e->idling = 1;
    e->drop = 0;
    e->falling = 0;
    e->inpain = 0;
    e->inbackpain = 0;
    e->blocking = 0;
    e->nograb = e->nograb_default; //e->nograb = 0;
    e->destx = e->position.x;
    e->destz = e->position.z;

    if(paramCount == 1)
    {
        return S_OK;
    }

    if(paramCount > 1 && FAILED(ScriptVariant_IntegerValue(varlist[1], &anim)))
    {
        goto setidle_error;
    }
    if(paramCount > 2 && FAILED(ScriptVariant_IntegerValue(varlist[2], &resetable)))
    {
        goto setidle_error;
    }
    if(paramCount > 3 && FAILED(ScriptVariant_IntegerValue(varlist[3], &stalladd)))
    {
        goto setidle_error;
    }
    ent_set_anim(e, (int)anim, (int)resetable);

    if(stalladd > 0)
    {
        e->stalltime = time + stalladd;
    }

    return S_OK;

setidle_error:
    printf("Function need a valid entity handle, the other 3 integer parameters are optional: setidle(entity, int anim, int resetable, int stalladd)\n");
    return E_FAIL;
}

//getentity(int index_from_list)
HRESULT openbor_getentity(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ind;
    extern entity **ent_list;
    extern int ent_list_size;

    if(paramCount != 1)
    {
        goto getentity_error;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ind)))
    {
        goto getentity_error;
    }

    ScriptVariant_Clear(*pretvar);

    if((int)ind < ent_list_size && (int)ind >= 0)
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)ent_list[(int)ind];
    }
    //else, it should return an empty value
    return S_OK;

getentity_error:
    printf("Function need an integer parameter: getentity(int index_in_list)\n");
    *pretvar = NULL;
    return E_FAIL;
}


//loadmodel(name)
HRESULT openbor_loadmodel(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG unload = 0;
    s_model *model;
    if(paramCount < 1)
    {
        goto loadmodel_error;
    }
    if(varlist[0]->vt != VT_STR)
    {
        goto loadmodel_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    if(paramCount >= 2)
        if(FAILED(ScriptVariant_IntegerValue(varlist[1], &unload)))
        {
            goto loadmodel_error;
        }

    model = load_cached_model(StrCache_Get(varlist[0]->strVal), "openbor_loadmodel", (char)unload);

    if(paramCount >= 3 && model)
    {
        model_cache[model->index].selectable = (char)ScriptVariant_IsTrue(varlist[2]);
    }

    (*pretvar)->ptrVal = (VOID *)model;

    //else, it should return an empty value
    return S_OK;

loadmodel_error:
    printf("Function needs a string and integer parameters: loadmodel(name, unload, selectable)\n");
    ScriptVariant_Clear(*pretvar);
    *pretvar = NULL;
    return E_FAIL;
}

// load a sprite which doesn't belong to the sprite_cache
// loadsprite(path, maskpath)
HRESULT openbor_loadsprite(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    extern s_sprite *loadsprite2(char * filename, int * width, int * height);
    s_sprite *spr, *mask;
    if(paramCount < 1)
    {
        goto loadsprite_error;
    }

    if(varlist[0]->vt != VT_STR)
    {
        goto loadsprite_error;
    }

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    if((spr = loadsprite2(StrCache_Get(varlist[0]->strVal), NULL, NULL)))
    {
        (*pretvar)->ptrVal = (VOID *)spr;
        if(paramCount > 1 && (mask = loadsprite2(StrCache_Get(varlist[1]->strVal), NULL, NULL)))
        {
            spr->mask = mask;
        }
        List_InsertAfter(&scriptheap, (void *)spr, "openbor_loadsprite");
    }
    //else, it should return an empty value
    return S_OK;

loadsprite_error:
    printf("Function need a string parameter: loadsprite(path)\n");
    ScriptVariant_Clear(*pretvar);
    *pretvar = NULL;
    return E_FAIL;
}

// Call options menu, blocked
HRESULT openbor_menu_options(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    //void menu_options();

    menu_options();

    *pretvar = NULL;
    return S_OK;
}

HRESULT openbor_hallfame(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    hallfame(0);

    *pretvar = NULL;
    return S_OK;
}

//playwebm(path, int noskip)
HRESULT openbor_playwebm(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG temp = 0; //noskip
    extern int playwebm(char * filename, int noskip); // avoid implicit declaration

    if(paramCount < 1 || !varlist || !varlist[0])
    {
        goto playwebm_error;
    }

    if(varlist[0]->vt != VT_STR)
    {
        goto playwebm_error;
    }

    if(paramCount > 1)
    {
        if(!varlist[1] || FAILED(ScriptVariant_IntegerValue(varlist[1], &temp)))
        {
            goto playwebm_error;
        }
    }

    #ifdef WEBM
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)playwebm(StrCache_Get(varlist[0]->strVal), (int)temp);
    #else
        printf("Skipping video %s; WebM playback not supported on this platform\n",
               StrCache_Get(varlist[0]->strVal));
        *pretvar = NULL;
    #endif

    return S_OK;

playwebm_error:
    printf("Function need a string parameter, other parameters are optional: playwebm(path, int noskip)\n");
    *pretvar = NULL;
    return E_FAIL;
}

//playgif(path, int x, int y, int noskip)
HRESULT openbor_playgif(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG temp[3] = {0, 0, 0}; //x,y,noskip
    int i;
    char *filename;
    const int early_result = obor_profile_build >= 4283 && obor_profile_build < 4380;
    extern unsigned char pal[1024];
    extern int playgif(char * filename, int x, int y, int noskip);

    if(!pretvar)
    {
        return E_FAIL;
    }

    if(paramCount < 1 || !varlist || !varlist[0] || !*pretvar)
    {
        goto playgif_error;
    }

    if(varlist[0]->vt != VT_STR)
    {
        goto playgif_error;
    }

    if(early_result)
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    }

    for(i = 0; i < 3 && i < paramCount - 1; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i + 1], temp + i)))
        {
            goto playgif_error;
        }
    }

    if(!early_result)
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    }

    filename = varlist[0]->vt == VT_STR ? StrCache_GetIfPresent(varlist[0]->strVal) : NULL;
    if(!filename)
    {
        goto playgif_error;
    }
    (*pretvar)->lVal = (LONG)playgif(filename, (int)(temp[0]), (int)(temp[1]), (int)(temp[2]));
    palette_set_corrected(pal, savedata.gamma, savedata.gamma, savedata.gamma, savedata.brightness, savedata.brightness, savedata.brightness);
    return S_OK;

playgif_error:
    printf("Function need a string parameter, other parameters are optional: playgif(path, int x, int y, int noskip)\n");
    *pretvar = NULL;
    return E_FAIL;
}

//open and return a handle
//TODO: error messages
HRESULT openbor_openanigif(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    anigif_info *info = NULL;

    if(varlist[0]->vt != VT_STR)
    {
        goto openanigif_error;
    }

    info = calloc(1, sizeof(*info));
    if(anigif_open(StrCache_Get(varlist[0]->strVal), packfile, info))
    {
        info->magic = anigif_magic;
        List_InsertAfter(&scriptheap, (void *)info, "openbor_openanigif");
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)info;
        return S_OK;
    }

openanigif_error:
    if(info)
    {
        free(info);
    }
    *pretvar = NULL;
    return E_FAIL;
}

//decode a frame if any
HRESULT openbor_decodeanigif(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    anigif_info *info = NULL;

    if(varlist[0]->vt != VT_PTR || !varlist[0]->ptrVal)
    {
        goto decodeanigif_error;
    }
    info = (anigif_info *) varlist[0]->ptrVal;

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)anigif_decode_frame(info);
    return S_OK;

decodeanigif_error:
    *pretvar = NULL;
    return E_FAIL;
}

//TODO mapstrings
HRESULT openbor_getanigifinfo(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    anigif_info *info = NULL;
    char *name;

    if(varlist[0]->vt != VT_PTR || !varlist[0]->ptrVal)
    {
        goto getanigifinfo_error;
    }
    info = (anigif_info *) varlist[0]->ptrVal;

    if(varlist[1]->vt != VT_STR)
    {
        goto getanigifinfo_error;
    }
    name = StrCache_Get(varlist[1]->strVal);
    if(0 == stricmp(name, "buffer"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        (*pretvar)->ptrVal = (VOID *)anigif_getbuffer(info);
    }
    else if(0 == stricmp(name, "done"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)info->done;
    }
    else if(0 == stricmp(name, "frame"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)info->frame;
    }
    else if(0 == stricmp(name, "isRGB"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)info->isRGB;
    }
    else if(0 == stricmp(name, "width"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)(info->gifbuffer[0] ? info->gifbuffer[0]->width : 0);
    }
    else if(0 == stricmp(name, "height"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)(info->gifbuffer[0] ? info->gifbuffer[0]->height : 0);
    }
    else if(0 == stricmp(name, "nextframe"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)info->info[0].nextframe;
    }
    else if(0 == stricmp(name, "lastdelay"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
        (*pretvar)->lVal = (LONG)info->info[0].lastdelay;
    }
    else
    {
        goto getanigifinfo_error;
    }

    return S_OK;

getanigifinfo_error:
    *pretvar = NULL;
    return E_FAIL;
}

// complex, so make a function for ai
// adjustwalkanimation(ent, target);
HRESULT openbor_adjustwalkanimation(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{

    entity *e, *t, *temp;

    *pretvar = NULL;

    if(paramCount < 1)
    {
        e = self;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto adjustwalkanimation_error;
    }

    if(paramCount < 2)
    {
        t = NULL;
    }
    else if(varlist[1]->vt == VT_PTR)
    {
        t = (entity *)varlist[1]->ptrVal;
    }
    else if(varlist[1]->vt == VT_EMPTY)
    {
        t = NULL;
    }
    else
    {
        goto adjustwalkanimation_error;
    }

    temp = self;

    self = e;
    adjust_walk_animation(t);
    self = temp;

    return S_OK;
adjustwalkanimation_error:
    printf("Function adjustwalkanimation(entity, target), both parameters are optional, but must be valid.");
    return E_FAIL;
}

//finditem(entity)
HRESULT openbor_finditem(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{

    entity *e, *t, *temp;

    if(paramCount < 1)
    {
        e = self;
    }
    else if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto finditem_error;
    }

    temp = self;

    self = e;
    t = normal_find_item();
    self = temp;

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)t;

    return S_OK;
finditem_error:

    *pretvar = NULL;
    printf("Function finditem(entity), entity is optional, but must be valid.");
    return E_FAIL;
}

//pickup(entity, item)
HRESULT openbor_pickup(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{

    entity *e, *t, *temp;

    *pretvar = NULL;

    if(paramCount < 2)
    {
        goto pickup_error;
    }

    if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto pickup_error;
    }

    if(varlist[1]->vt == VT_PTR)
    {
        t = (entity *)varlist[1]->ptrVal;
    }
    else
    {
        goto pickup_error;
    }

    if(!e || !t)
    {
        goto pickup_error;
    }

    temp = self;

    self = e;
    common_pickupitem(t);
    self = temp;

    return S_OK;
pickup_error:
    printf("Function pickup(entity, item), handles must be valid.");
    return E_FAIL;
}

//waypoints(ent, x1, z1, x2, z2, x3, z3, ...)
//zero length list means clear waypoints
HRESULT openbor_waypoints(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int num, i;
    s_axis_f *wp = NULL;
    DOUBLE x, z;

    entity *e;
    *pretvar = NULL;

    if(paramCount < 1)
    {
        goto wp_error;
    }

    if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto wp_error;
    }

    num = (paramCount - 1) / 2;
    if(num > 0)
    {
        //append
        wp = malloc(sizeof(*wp) * (num + e->numwaypoints));

        for(i = 0; i < num ; i++)
        {
            if(FAILED(ScriptVariant_DecimalValue(varlist[1], &x)))
            {
                goto wp_error;
            }

            if(FAILED(ScriptVariant_DecimalValue(varlist[2], &z)))
            {
                goto wp_error;
            }

            wp[num - i - 1].x = (float)x;
            wp[num - i - 1].z = (float)z;
        }
        if(e->numwaypoints)
        {
            for(i = 0; i < e->numwaypoints; i++)
            {
                wp[i + num] = e->waypoints[i];
            }
        }

        if(e->waypoints)
        {
            free(e->waypoints);
        }
        e->waypoints = wp;
        e->numwaypoints = num;
    }
    else
    {
        e->numwaypoints = 0;
        if(e->waypoints)
        {
            free(e->waypoints);
        }
        e->waypoints = NULL;
    }
    return S_OK;

wp_error:
    if(wp)
    {
        free(wp);
    }
    wp = NULL;
    printf("Function waypoints requires a valid entity handle and a list of x, z value pairs.");
    return E_FAIL;
}

//testmove(entity, x, z)
HRESULT openbor_testmove(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{

    entity *e;
    DOUBLE x, z;

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

    if(paramCount < 3)
    {
        goto testmove_error;
    }

    if(varlist[0]->vt == VT_PTR)
    {
        e = (entity *)varlist[0]->ptrVal;
    }
    else
    {
        goto testmove_error;
    }

    if(FAILED(ScriptVariant_DecimalValue(varlist[1], &x)))
    {
        goto testmove_error;
    }

    if(FAILED(ScriptVariant_DecimalValue(varlist[2], &z)))
    {
        goto testmove_error;
    }

    if(!e)
    {
        goto testmove_error;
    }

    (*pretvar)->lVal = (LONG) testmove(e, e->position.x, e->position.z, x, z);

    return S_OK;
testmove_error:
    *pretvar = NULL;
    printf("Function testmove(entity, x, z)");
    return E_FAIL;
}

//spriteq_draw(vscreen, 0, MIN_INT, MAX_INT, dx, dy)
HRESULT openbor_drawspriteq(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{

    LONG value[5] = {0, MIN_INT, MAX_INT, 0, 0};
    int i;
    s_screen *screen;
    extern s_screen *vscreen;

    *pretvar = NULL;

    if(paramCount < 1)
    {
        goto drawsq_error;
    }

    if(varlist[0]->vt != VT_PTR && varlist[0]->vt != VT_EMPTY)
    {
        goto drawsq_error;
    }

    if(varlist[0]->ptrVal)
    {
        screen = (s_screen *)varlist[0]->ptrVal;
    }
    else
    {
        screen = vscreen;
    }

    for(i = 1; i < paramCount && i <= 5; i++)
    {
        if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + i - 1)))
        {
            goto drawsq_error;
        }
    }

    spriteq_draw(screen, (int)value[0], (int)value[1], (int)value[2], (int)value[3], (int)value[4]);

    return S_OK;

drawsq_error:
    printf("Function drawspriteq needs a valid screen handle and all other paramaters must be integers.");
    return E_FAIL;

}

HRESULT openbor_clearspriteq(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    *pretvar = NULL;
    spriteq_clear();
    return S_OK;

}

// ===== gfxproperty ======
enum gfxproperty_enum
{
    _gfx_centerx,
    _gfx_centery,
    _gfx_height,
    _gfx_palette,
    _gfx_pixel,
    _gfx_pixelformat,
    _gfx_srcheight,
    _gfx_srcwidth,
    _gfx_width,
    _gfx_the_end,
};

int mapstrings_gfxproperty(ScriptVariant **varlist, int paramCount)
{
    char *propname = NULL;
    int prop;

    static const char *proplist[] =
    {
        "centerx",
        "centery",
        "height",
        "palette",
        "pixel",
        "pixelformat",
        "srcheight",
        "srcwidth",
        "width",
    };


    if(paramCount < 2)
    {
        return 1;
    }
    MAPSTRINGS(varlist[1], proplist, _gfx_the_end,
               "Property name '%s' is not supported by gfxproperty.\n");

    return 1;
}

// getgfxproperty(handle, propertyname, ...);
HRESULT openbor_getgfxproperty(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    s_screen *screen;
    s_sprite *sprite;
    s_bitmap *bitmap;
    LONG value[2] = {0, 0}, v;
    void *handle;
    int i, x, y;

    if(paramCount < 2)
    {
        goto ggp_error;
    }

    mapstrings_gfxproperty(varlist, paramCount);

    if(varlist[0]->vt != VT_PTR)
    {
        goto ggp_error;
    }

    handle = varlist[0]->ptrVal;

    if(!handle)
    {
        goto ggp_error;
    }

    screen = (s_screen *)handle;
    sprite = (s_sprite *)handle;
    bitmap = (s_bitmap *)handle;

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);


    switch(varlist[1]->lVal)
    {
    case _gfx_width:
        switch(screen->magic)
        {
        case screen_magic:
            (*pretvar)->lVal = screen->width;
            break;
        case sprite_magic:
            (*pretvar)->lVal = sprite->width;
            break;
        case bitmap_magic:
            (*pretvar)->lVal = bitmap->width;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_height:
        switch(screen->magic)
        {
        case screen_magic:
            (*pretvar)->lVal = screen->height;
            break;
        case sprite_magic:
            (*pretvar)->lVal = sprite->height;
            break;
        case bitmap_magic:
            (*pretvar)->lVal = bitmap->height;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_srcwidth:
        switch(screen->magic)
        {
        case sprite_magic:
            (*pretvar)->lVal = sprite->srcwidth;
            break;
        case screen_magic:
            (*pretvar)->lVal = screen->width;
            break;
        case bitmap_magic:
            (*pretvar)->lVal = bitmap->width;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_srcheight:
        switch(screen->magic)
        {
        case sprite_magic:
            (*pretvar)->lVal = sprite->srcheight;
            break;
        case screen_magic:
            (*pretvar)->lVal = screen->height;
            break;
        case bitmap_magic:
            (*pretvar)->lVal = bitmap->height;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_centerx:
        switch(screen->magic)
        {
        case screen_magic:
        case bitmap_magic:
            (*pretvar)->lVal = 0;
            break;
        case sprite_magic:
            (*pretvar)->lVal = sprite->centerx;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_centery:
        switch(screen->magic)
        {
        case screen_magic:
        case bitmap_magic:
            (*pretvar)->lVal = 0;
            break;
        case sprite_magic:
            (*pretvar)->lVal = sprite->centery;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_palette:
        ScriptVariant_ChangeType(*pretvar, VT_PTR);
        switch(screen->magic)
        {
        case screen_magic:
            (*pretvar)->ptrVal = (VOID *)screen->palette;
            break;
        case sprite_magic:
            (*pretvar)->ptrVal = (VOID *)sprite->palette;
            break;
        case bitmap_magic:
            (*pretvar)->ptrVal = (VOID *)bitmap->palette;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_pixelformat:
        switch(screen->magic)
        {
        case screen_magic:
            (*pretvar)->lVal = screen->pixelformat;
            break;
        case sprite_magic:
            (*pretvar)->lVal = sprite->pixelformat;
            break;
        case bitmap_magic:
            (*pretvar)->lVal = bitmap->pixelformat;
            break;
        default:
            goto ggp_error2;
        }
        break;
    case _gfx_pixel:
        if(paramCount < 4)
        {
            goto ggp_error3;
        }
        for(i = 2; i < 4; i++)
        {
            if(FAILED(ScriptVariant_IntegerValue(varlist[i], value + (i - 2))))
            {
                goto ggp_error4;
            }
        }
        x = value[0];
        y = value[1];
        switch(screen->magic)
        {
        case bitmap_magic: //As long as the two structures are identical...
        case screen_magic:
            if(x < 0 || x >= screen->width || y < 0 || y >= screen->height)
            {
                v = 0;
            }
            else
            {
                switch(screen->pixelformat)
                {
                case PIXEL_8:
                case PIXEL_x8:
                    v = (LONG)(((unsigned char *)screen->data)[y * screen->width + x]);
                    break;
                case PIXEL_16:
                    v = (LONG)(((unsigned short *)screen->data)[y * screen->width + x]);
                    break;
                case PIXEL_32:
                    v = (LONG)(((unsigned *)screen->data)[y * screen->width + x]);
                    break;
                default:
                    v = 0;
                }
            }
            break;
        case sprite_magic:
            if(x < 0 || x >= sprite->width || y < 0 || y >= sprite->height)
            {
                v = 0;
            }
            else
            {
                v = (LONG)sprite_get_pixel(sprite, x, y);
            }
            break;
        default:
            goto ggp_error2;
        }
        (*pretvar)->lVal = v;
        break;
    default:
        break;

    }

    return S_OK;

ggp_error:
    printf("Function getgfxproperty must have a valid handle and a property name.\n");
    *pretvar = NULL;
    return E_FAIL;
ggp_error2:
    printf("Function getgfxproperty encountered an invalid handle.\n");
    *pretvar = NULL;
    return E_FAIL;
ggp_error3:
    printf("You need to specify x, y value for getgfxproperty.\n");
    *pretvar = NULL;
    return E_FAIL;
ggp_error4:
    printf("Invalid x or y value for getgfxproperty.\n");
    *pretvar = NULL;
    return E_FAIL;
}

//allocscript(name, comment);
HRESULT openbor_allocscript(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Script *ns;
    char *name = NULL, *comment = NULL;

    ns = malloc(sizeof(Script));

    if(ns == NULL)
    {
        goto as_error;
    }

    if(paramCount >= 1 && varlist[0]->vt == VT_STR)
    {
        name = (char *)StrCache_Get(varlist[0]->strVal);
    }
    if(paramCount >= 2 && varlist[1]->vt == VT_STR)
    {
        comment = (char *)StrCache_Get(varlist[1]->strVal);
    }

    Script_Init(ns, name, comment, 1);

    List_InsertAfter(&scriptheap, (void *)ns, "openbor_allocscript");

    ScriptVariant_ChangeType(*pretvar, VT_PTR);
    (*pretvar)->ptrVal = (VOID *)ns;
    return S_OK;

as_error:
    printf("Function allocscript failed to alloc enough memory.\n");
    (*pretvar) = NULL;
    return E_FAIL;
}

//loadscript(handle, path);
HRESULT openbor_loadscript(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Script *ns = NULL;
    char *path = NULL;
    int load_script(Script * script, char * file);

    (*pretvar) = NULL;

    if(paramCount >= 1 && varlist[0]->vt == VT_PTR)
    {
        ns = (Script *)varlist[0]->ptrVal;
    }
    if(ns == NULL || ns->magic != script_magic)
    {
        goto ls_error;
    }
    if(paramCount >= 2 && varlist[1]->vt == VT_STR)
    {
        path = (char *)StrCache_Get(varlist[1]->strVal);
    }
    if(path == NULL)
    {
        goto ls_error;
    }

    load_script(ns, path);
    //Script_Init(ns, name, comment, 1);
    //if(!load_script(ns, path)) goto ls_error2;

    return S_OK;

ls_error:
    printf("Function loadscript requires a valid script handle and a path.\n");
    return E_FAIL;
}

//compilescript(handle);
HRESULT openbor_compilescript(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Script *ns = NULL;

    (*pretvar) = NULL;

    if(paramCount >= 1 && varlist[0]->vt == VT_PTR)
    {
        ns = (Script *)varlist[0]->ptrVal;
    }
    if(ns == NULL || ns->magic != script_magic)
    {
        goto cs_error;
    }

    Script_Compile(ns);

    return S_OK;

cs_error:
    printf("Function compilescript requires a valid script handle.\n");
    return E_FAIL;
}

//executescript(handle);
HRESULT openbor_executescript(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    Script *ns = NULL;

    (*pretvar) = NULL;

    if(paramCount >= 1 && varlist[0]->vt == VT_PTR)
    {
        ns = (Script *)varlist[0]->ptrVal;
    }
    if(ns == NULL || ns->magic != script_magic)
    {
        goto cs_error;
    }

    Script_Execute(ns);

    return S_OK;

cs_error:
    printf("Function executescript requires a valid script handle.\n");
    return E_FAIL;
}


//loadgamefile() //only reload saved level file from saves
HRESULT openbor_loadgamefile(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    loadGameFile();
    *pretvar = NULL;
    return S_OK;
}

//finishlevel()
HRESULT openbor_finishlevel(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    *pretvar = NULL;
    level->forcefinishlevel = 1;
    return S_OK;
}

//gameover()
HRESULT openbor_gameover(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    *pretvar = NULL;
    if(!level || obor_profile_build < 4642 || obor_profile_build > 4905)
    {
        return E_FAIL;
    }
    level->force_gameover = 1;
    return S_OK;
}

//gotomainmenu(flag); flag: 1 = no gameover, 2 = no halloffame, 4 = no intro.txt; you can use a combination like 1+2 = 3 or all 1+2+4 = 7
HRESULT openbor_gotomainmenu(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp = 0;

    *pretvar = NULL;

    if(paramCount >= 1 && FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)) )
    {
        return E_FAIL;
    }

    goto_mainmenu((int)ltemp);

    return S_OK;
}

//playgame(set, usesave?)
HRESULT openbor_playgame(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG lset = 0, lsave = -1;
    *pretvar = NULL;

    if(paramCount >= 1 && FAILED(ScriptVariant_IntegerValue(varlist[0], &lset)) )
    {
        goto pg_error;
    }
    if(paramCount >= 2 && FAILED(ScriptVariant_IntegerValue(varlist[1], &lsave)) )
    {
        goto pg_error;
    }


    useSave = lsave;
    useSet = lset;
    endgame = 1;

    return S_OK;

pg_error:
    *pretvar = NULL;
    return E_FAIL;
}

//getrecordingstatus() it returns 0 = stop, 1 = rec, 2 = play, 4 = free buffer
HRESULT openbor_getrecordingstatus(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount) {
    ScriptVariant_Clear(*pretvar);
    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    (*pretvar)->lVal = (LONG)playrecstatus->status;
    return S_OK;
}

//recordinputs(value) -> 0 = stop, 1 = rec, 2 = play, 4 = free buffer
HRESULT openbor_recordinputs(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    int ltemp;

    *pretvar = NULL;
    if( paramCount < 1 && varlist[0]->vt != VT_INTEGER )
    {
        return E_FAIL;
    }

    ltemp = (int)varlist[0]->lVal;
    switch(ltemp)
    {
        case A_REC_STOP:
            stopRecordInputs();
            break;
        case A_REC_REC:
            if( paramCount < 3 || varlist[1]->vt != VT_STR || varlist[2]->vt != VT_STR )
            {
                printf("Function recordinputs requires a pathname and filename parameters.\n");
                return E_FAIL;
            }
            strcpy(playrecstatus->path,(char*)StrCache_Get(varlist[1]->strVal));
            strcpy(playrecstatus->filename,(char*)StrCache_Get(varlist[2]->strVal));
            //debug_printf("%s/%s",(char*)StrCache_Get(varlist[1]->strVal),(char*)StrCache_Get(varlist[2]->strVal));
            stopRecordInputs();
            playrecstatus->status = A_REC_REC;
            recordInputs();
            break;
        case A_REC_PLAY:
            if( paramCount < 3 || varlist[1]->vt != VT_STR || varlist[2]->vt != VT_STR )
            {
                printf("Function recordinputs requires a pathname and filename parameters.\n");
                return E_FAIL;
            }
            strcpy(playrecstatus->path,(char*)StrCache_Get(varlist[1]->strVal));
            strcpy(playrecstatus->filename,(char*)StrCache_Get(varlist[2]->strVal));
            stopRecordInputs();
            playrecstatus->status = A_REC_PLAY;
            playRecordedInputs();
            break;
        case A_REC_FREE:
            freeRecordedInputs();
            break;
    }

    return S_OK;
}

//getsaveinfo(set, prop);
HRESULT openbor_getsaveinfo(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp;
    s_savelevel *slot;
    char *prop;
    if(paramCount < 2)
    {
        goto gsi_error;
    }

    if(FAILED(ScriptVariant_IntegerValue(varlist[0], &ltemp)) || varlist[1]->vt != VT_STR)
    {
        goto gsi_error;
    }

    if(!savelevel)
    {
        ScriptVariant_Clear(*pretvar);
        return S_OK;
    }

    slot = savelevel + ltemp;
    prop = (char *)StrCache_Get(varlist[1]->strVal);

    ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
    if(0 == stricmp(prop, "flag"))
    {
        (*pretvar)->lVal = (LONG)slot->flag;
    }
    else if(0 == stricmp(prop, "level"))
    {
        (*pretvar)->lVal = (LONG)slot->level;
    }
    else if(0 == stricmp(prop, "stage"))
    {
        (*pretvar)->lVal = (LONG)slot->stage;
    }
    else if(0 == stricmp(prop, "set"))
    {
        (*pretvar)->lVal = (LONG)slot->which_set;
    }
    else if(0 == stricmp(prop, "times_completed"))
    {
        (*pretvar)->lVal = (LONG)slot->times_completed;
    }
    else if(0 == stricmp(prop, "score"))
    {
        if(paramCount < 3 || FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) )
        {
            goto gsi_error;
        }
        (*pretvar)->lVal = (LONG)slot->pScores[ltemp];
    }
    else if(0 == stricmp(prop, "lives"))
    {
        if(paramCount < 3 || FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) )
        {
            goto gsi_error;
        }
        (*pretvar)->lVal = (LONG)slot->pLives[ltemp];
    }
    else if(0 == stricmp(prop, "credits"))
    {
        if(paramCount < 3 || FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) )
        {
            goto gsi_error;
        }
        (*pretvar)->lVal = (LONG)(noshare ? slot->credits : slot->pCredits[ltemp]);
    }
    else if(0 == stricmp(prop, "name"))
    {
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, slot->dName);
    }
    else if(0 == stricmp(prop, "playername"))
    {
        if(paramCount < 3 || FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) )
        {
            goto gsi_error;
        }
        ScriptVariant_ChangeType(*pretvar, VT_STR);
        StrCache_Copy((*pretvar)->strVal, slot->pName[ltemp]);
    }
    else if(0 == stricmp(prop, "health"))
    {
        if(paramCount < 3 || FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) )
        {
            goto gsi_error;
        }
        (*pretvar)->lVal = (LONG)slot->pSpawnhealth[ltemp];
    }
    else if(0 == stricmp(prop, "mp"))
    {
        if(paramCount < 3 || FAILED(ScriptVariant_IntegerValue(varlist[2], &ltemp)) )
        {
            goto gsi_error;
        }
        (*pretvar)->lVal = (LONG)slot->pSpawnmp[ltemp];
    }
    else
    {
        goto gsi_error;
    }
    return S_OK;

gsi_error:
    *pretvar = NULL;
    return E_FAIL;
}
