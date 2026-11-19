/* AnyBOR modification record: 2026-10-24.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Select the native 6330 decimal negation fallthrough. Preserve native
 * signed32 integer conversion and truncated decimal results; refuse
 * unavailable arguments and non-representable decimal results before
 * conversion without changing result storage. Preserve the profile's sharing
 * of identical compiled string constants. Size concatenation results from
 * both formatted operands.
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

#include "ScriptVariant.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <limits.h>

typedef struct
{
    int len;
    int ref;
    CHAR *str;
} Varstr;

// use string cache to cut the memory usage down, because not all variants are string, no need to give each of them an array
#define STRCACHE_INC      64
Varstr *strcache = NULL;
int   strcache_size = 0;
int   strcache_top = -1;
int  *strcache_index = NULL;

//clear the string cache
void StrCache_Clear()
{
    int i;
    if(strcache)
    {
        for(i = 0; i < strcache_size; i++)
        {
            if(strcache[i].str)
            {
                free(strcache[i].str);
            }
            strcache[i].str = NULL;
        }
        free(strcache);
        strcache = NULL;
    }
    if(strcache_index)
    {
        free(strcache_index);
        strcache_index = NULL;
    }
    strcache_size = 0;
    strcache_top = -1;
}

// int the string cache
void StrCache_Init()
{
    int i;
    StrCache_Clear(); // just in case
    strcache = calloc(STRCACHE_INC, sizeof(*strcache));
    strcache_index = malloc(sizeof(*strcache_index) * STRCACHE_INC);
    for(i = 0; i < STRCACHE_INC; i++)
    {
        strcache[i].str = malloc(sizeof(CHAR) * (MAX_STR_VAR_LEN + 1));
        strcache[i].str[0] = 0;
        strcache[i].len = MAX_STR_VAR_LEN;
        strcache_index[i] = i;
    }
    strcache_size = STRCACHE_INC;
    strcache_top = strcache_size - 1;
}

void StrCache_Resize(int index, int size)
{
    //assert(index<strcache_size);
    //assert(size>0);
    strcache[index].str = realloc(strcache[index].str, size + 1);
    strcache[index].str[size] = 0;
    strcache[index].len = size;
}

void StrCache_Collect(int index)
{
    strcache[index].ref--;
    //assert(strcache[index].ref>=0);
    if(!strcache[index].ref)
    {
        //if(strcache[index].len > MAX_STR_VAR_LEN)
        //	StrCache_Resize(index, MAX_STR_VAR_LEN);
        //assert(strcache_top+1<strcache_size);
        strcache_index[++strcache_top] = index;
    }
}

int StrCache_Pop()
{
    int i;
    if(strcache_size == 0)
    {
        StrCache_Init();
    }
    if(strcache_top < 0) // realloc
    {
        __reallocto(strcache, strcache_size, strcache_size + STRCACHE_INC);
        __reallocto(strcache_index, strcache_size, strcache_size + STRCACHE_INC);
        for(i = 0; i < STRCACHE_INC; i++)
        {
            strcache_index[i] = strcache_size + i;
            strcache[i + strcache_size].str = malloc(sizeof(CHAR) * (MAX_STR_VAR_LEN + 1));
            strcache[i + strcache_size].str[0] = 0;
            strcache[i + strcache_size].len = MAX_STR_VAR_LEN;
        }

        //printf("debug: dumping string cache....\n");
        //for(i=0; i<strcache_size; i++)
        //	printf("\t\"%s\"  %d\n", strcache[i].str, strcache[i].ref);

        strcache_size += STRCACHE_INC;
        strcache_top += STRCACHE_INC;

        //printf("debug: string cache resized to %d \n", strcache_size);
    }
    i = strcache_index[strcache_top--];
    strcache[i].ref = 1;
    return i;
}

void StrCache_Copy(int index, CHAR *str)
{
    //assert(index<strcache_size);
    //assert(size>0);
    int len = strlen(str);
    if(strcache[index].len < len)
    {
        StrCache_Resize(index, len);
    }
    strcpy(strcache[index].str, str);
}

void StrCache_NCopy(int index, CHAR *str, int n)
{
    //assert(index<strcache_size);
    //assert(size>0);
    if(strcache[index].len < n)
    {
        StrCache_Resize(index, n);
    }
    strncpy(strcache[index].str, str, n);
    strcache[index].str[n] = 0;
}

CHAR *StrCache_Get(int index)
{
    //assert(index<strcache_size);
    return strcache[index].str;
}

CHAR *StrCache_GetIfPresent(int index)
{
    CHAR *text;
    size_t capacity;
    if(index < 0 || index >= strcache_size || !strcache)
        return NULL;
    text = StrCache_Get(index);
    if(!text) return NULL;
    if(strcache[index].len < 0) return NULL;
    capacity = (size_t)strcache[index].len + 1;
    return memchr(text, 0, capacity) ? text : NULL;
}

int StrCache_Len(int index)
{
    //assert(index<strcache_size);
    return strcache[index].len;
}

void StrCache_Grab(int index)
{
    ++strcache[index].ref;
}


void ScriptVariant_Clear(ScriptVariant *var)
{
    ScriptVariant_ChangeType(var, VT_EMPTY);
    var->ptrVal = NULL; // not sure, maybe this is the longest member in the union
}

void ScriptVariant_Init(ScriptVariant *var)
{
    //memset(var, 0, 8);
    var->ptrVal = NULL; // not sure, maybe this is the longest member in the union
    var->vt = VT_EMPTY;
}

void ScriptVariant_ChangeType(ScriptVariant *var, VARTYPE cvt)
{
    // Always collect make it safer for string copy
    // since now reference has been added.
    // String variables should never be changed
    // unless the engine is creating a new one
    if(var->vt == VT_STR)
    {
        StrCache_Collect(var->strVal);
    }
    if(cvt == VT_STR)
    {
        var->strVal = StrCache_Pop();
    }
    var->vt = cvt;

}

// find an existing constant before copy
void ScriptVariant_ParseStringConstant(ScriptVariant *var, CHAR *str, int share)
{
    if(share)
    {
        for(int i = 0; i < strcache_size; ++i)
        {
            if(strcache[i].ref && strcmp(str, strcache[i].str) == 0)
            {
                StrCache_Grab(i);
                ScriptVariant_Clear(var);
                var->strVal = i;
                var->vt = VT_STR;
                return;
            }
        }
    }

    ScriptVariant_ChangeType(var, VT_STR);
    StrCache_Copy(var->strVal, str);
}

HRESULT ScriptVariant_IntegerValue(ScriptVariant *var, LONG *pVal)
{
    if(!var || !pVal) return E_FAIL;

    if(var->vt == VT_INTEGER)
    {
        *pVal = var->lVal;
    }
    else if(var->vt == VT_DECIMAL)
    {
        /* Preserve truncation only when the native signed32 result is representable. */
        if(!(var->dblVal > -2147483649.0 && var->dblVal < 2147483648.0)) return E_FAIL;
        *pVal = (LONG)var->dblVal;
    }
    else
    {
        return E_FAIL;
    }

    return S_OK;
}

HRESULT ScriptVariant_DecimalValue(ScriptVariant *var, DOUBLE *pVal)
{
    if(!var || !pVal) return E_FAIL;
    if(var->vt == VT_INTEGER)
    {
        *pVal = (DOUBLE)var->lVal;
    }
    else if(var->vt == VT_DECIMAL)
    {
        *pVal = var->dblVal;
    }
    else
    {
        return E_FAIL;
    }

    return S_OK;
}


BOOL ScriptVariant_IsTrue(ScriptVariant *svar)
{
    switch(svar->vt)
    {
    case VT_STR:
        return StrCache_Get(svar->strVal)[0] != 0;
    case VT_INTEGER:
        return svar->lVal != 0;
    case VT_DECIMAL:
        return svar->dblVal != 0.0;
    case VT_PTR:
        return svar->ptrVal != 0;
    default:
        return 0;
    }
}

void ScriptVariant_ToString(ScriptVariant *svar, LPSTR buffer )
{
    switch( svar->vt )
    {
    case VT_EMPTY:
        sprintf( buffer, "<VT_EMPTY>   Unitialized" );
        break;
    case VT_INTEGER:
        sprintf( buffer, "%d", svar->lVal);
        break;
    case VT_DECIMAL:
        sprintf( buffer, "%lf", svar->dblVal );
        break;
    case VT_PTR:
        sprintf(buffer, "#%ld", (long)(svar->ptrVal));
        break;
    case VT_STR:
        sprintf(buffer, "%s", StrCache_Get(svar->strVal));
        break;
    default:
        sprintf(buffer, "<Unprintable VARIANT type.>" );
        break;
    }
}

// faster if it is not VT_STR
void ScriptVariant_Copy(ScriptVariant *svar, ScriptVariant *rightChild )
{
    // collect the str cache index
    if(svar->vt == VT_STR)
    {
        StrCache_Collect(svar->strVal);
    }
    switch( rightChild->vt )
    {
    case VT_INTEGER:
        svar->lVal = rightChild->lVal;
        break;
    case VT_DECIMAL:
        svar->dblVal = rightChild->dblVal;
        break;
    case VT_PTR:
        svar->ptrVal = rightChild->ptrVal;
        break;
    case VT_STR:
        svar->strVal = rightChild->strVal;
        StrCache_Grab(svar->strVal);
        break;
    default:
        //should not happen unless the variant is not intialized correctly
        //shutdown(1, "invalid variant type");
        svar->ptrVal = NULL;
        break;
    }
    svar->vt = rightChild->vt;
}

// light version, for compiled call, faster than above, but not safe in some situations
ScriptVariant *ScriptVariant_Assign(ScriptVariant *svar, ScriptVariant *rightChild )
{
    ScriptVariant_Copy(svar, rightChild);
    return rightChild;
}


ScriptVariant *ScriptVariant_MulAssign(ScriptVariant *svar, ScriptVariant *rightChild )
{
    ScriptVariant_Copy(svar, ScriptVariant_Mul(svar, rightChild));
    return svar;
}


ScriptVariant *ScriptVariant_DivAssign(ScriptVariant *svar, ScriptVariant *rightChild )
{
    ScriptVariant_Copy(svar, ScriptVariant_Div(svar, rightChild));
    return svar;
}


ScriptVariant *ScriptVariant_AddAssign(ScriptVariant *svar, ScriptVariant *rightChild )
{
    ScriptVariant_Copy(svar, ScriptVariant_Add(svar, rightChild));
    return svar;
}


ScriptVariant *ScriptVariant_SubAssign(ScriptVariant *svar, ScriptVariant *rightChild )
{
    ScriptVariant_Copy(svar, ScriptVariant_Sub(svar, rightChild));
    return svar;
}


ScriptVariant *ScriptVariant_ModAssign(ScriptVariant *svar, ScriptVariant *rightChild )
{
    ScriptVariant_Copy(svar, ScriptVariant_Mod(svar, rightChild));
    return svar;
}

//Logical Operations

ScriptVariant *ScriptVariant_Or( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};
    retvar.lVal = (ScriptVariant_IsTrue(svar) || ScriptVariant_IsTrue(rightChild));
    return &retvar;
}


ScriptVariant *ScriptVariant_And( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};
    retvar.lVal = (ScriptVariant_IsTrue(svar) && ScriptVariant_IsTrue(rightChild));
    return &retvar;
}

ScriptVariant *ScriptVariant_Bit_Or( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    LONG l1, l2;
    if(ScriptVariant_IntegerValue(svar, &l1) == S_OK &&
            ScriptVariant_IntegerValue(rightChild, &l2) == S_OK)
    {
        retvar.vt = VT_INTEGER;
        retvar.lVal = l1 | l2;
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}

ScriptVariant *ScriptVariant_Xor( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    LONG l1, l2;
    if(ScriptVariant_IntegerValue(svar, &l1) == S_OK &&
            ScriptVariant_IntegerValue(rightChild, &l2) == S_OK)
    {
        retvar.vt = VT_INTEGER;
        retvar.lVal = l1 ^ l2;
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}

ScriptVariant *ScriptVariant_Bit_And( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    LONG l1, l2;
    if(ScriptVariant_IntegerValue(svar, &l1) == S_OK &&
            ScriptVariant_IntegerValue(rightChild, &l2) == S_OK)
    {
        retvar.vt = VT_INTEGER;
        retvar.lVal = l1 & l2;
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}

ScriptVariant *ScriptVariant_Eq( ScriptVariant *svar, ScriptVariant *rightChild )
{
    DOUBLE dbl1, dbl2;
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};

    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        retvar.lVal = (dbl1 == dbl2);
    }
    else if(svar->vt == VT_STR && rightChild->vt == VT_STR)
    {
        retvar.lVal = !(strcmp(StrCache_Get(svar->strVal), StrCache_Get(rightChild->strVal)));
    }
    else if(svar->vt == VT_PTR && rightChild->vt == VT_PTR)
    {
        retvar.lVal = (svar->ptrVal == rightChild->ptrVal);
    }
    else if(svar->vt == VT_EMPTY && rightChild->vt == VT_EMPTY)
    {
        retvar.lVal = 1;
    }
    else
    {
        retvar.lVal = !(memcmp(svar, rightChild, sizeof(ScriptVariant)));
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Ne( ScriptVariant *svar, ScriptVariant *rightChild )
{
    DOUBLE dbl1, dbl2;
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};

    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        retvar.lVal = (dbl1 != dbl2);
    }
    else if(svar->vt == VT_STR && rightChild->vt == VT_STR)
    {
        retvar.lVal = strcmp(StrCache_Get(svar->strVal), StrCache_Get(rightChild->strVal));
    }
    else if(svar->vt == VT_PTR && rightChild->vt == VT_PTR)
    {
        retvar.lVal = (svar->ptrVal != rightChild->ptrVal);
    }
    else if(svar->vt == VT_EMPTY && rightChild->vt == VT_EMPTY)
    {
        retvar.lVal = 0;
    }
    else
    {
        retvar.lVal = (memcmp(svar, rightChild, sizeof(ScriptVariant)) != 0);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Lt( ScriptVariant *svar, ScriptVariant *rightChild )
{
    DOUBLE dbl1, dbl2;
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};

    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        retvar.lVal = (dbl1 < dbl2);
    }
    else if(svar->vt == VT_STR && rightChild->vt == VT_STR)
    {
        retvar.lVal = (strcmp(StrCache_Get(svar->strVal), StrCache_Get(rightChild->strVal)) < 0);
    }
    else if(svar->vt == VT_PTR && rightChild->vt == VT_PTR)
    {
        retvar.lVal = (svar->ptrVal < rightChild->ptrVal);
    }
    else if(svar->vt == VT_EMPTY || rightChild->vt == VT_EMPTY)
    {
        retvar.lVal = 0;
    }
    else
    {
        retvar.lVal = (memcmp(svar, rightChild, sizeof(ScriptVariant)) < 0);
    }

    return &retvar;
}



ScriptVariant *ScriptVariant_Gt( ScriptVariant *svar, ScriptVariant *rightChild )
{
    DOUBLE dbl1, dbl2;
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};

    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        retvar.lVal = (dbl1 > dbl2);
    }
    else if(svar->vt == VT_STR && rightChild->vt == VT_STR)
    {
        retvar.lVal = (strcmp(StrCache_Get(svar->strVal), StrCache_Get(rightChild->strVal)) > 0);
    }
    else if(svar->vt == VT_PTR && rightChild->vt == VT_PTR)
    {
        retvar.lVal = (svar->ptrVal > rightChild->ptrVal);
    }
    else if(svar->vt == VT_EMPTY || rightChild->vt == VT_EMPTY)
    {
        retvar.lVal = 0;
    }
    else
    {
        retvar.lVal = (memcmp(svar, rightChild, sizeof(ScriptVariant)) > 0);
    }

    return &retvar;
}



ScriptVariant *ScriptVariant_Ge( ScriptVariant *svar, ScriptVariant *rightChild )
{
    DOUBLE dbl1, dbl2;
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};

    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        retvar.lVal = (dbl1 >= dbl2);
    }
    else if(svar->vt == VT_STR && rightChild->vt == VT_STR)
    {
        retvar.lVal = (strcmp(StrCache_Get(svar->strVal), StrCache_Get(rightChild->strVal)) >= 0);
    }
    else if(svar->vt == VT_PTR && rightChild->vt == VT_PTR)
    {
        retvar.lVal = (svar->ptrVal >= rightChild->ptrVal);
    }
    else if(svar->vt == VT_EMPTY || rightChild->vt == VT_EMPTY)
    {
        retvar.lVal = 0;
    }
    else
    {
        retvar.lVal = (memcmp(svar, rightChild, sizeof(ScriptVariant)) >= 0);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Le( ScriptVariant *svar, ScriptVariant *rightChild )
{
    DOUBLE dbl1, dbl2;
    static ScriptVariant retvar = {{.lVal = 0}, VT_INTEGER};

    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        retvar.lVal = (dbl1 <= dbl2);
    }
    else if(svar->vt == VT_STR && rightChild->vt == VT_STR)
    {
        retvar.lVal = (strcmp(StrCache_Get(svar->strVal), StrCache_Get(rightChild->strVal)) <= 0);
    }
    else if(svar->vt == VT_PTR && rightChild->vt == VT_PTR)
    {
        retvar.lVal = (svar->ptrVal <= rightChild->ptrVal);
    }
    else if(svar->vt == VT_EMPTY || rightChild->vt == VT_EMPTY)
    {
        retvar.lVal = 0;
    }
    else
    {
        retvar.lVal = (memcmp(svar, rightChild, sizeof(ScriptVariant)) <= 0);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Shl( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    LONG l1, l2;
    if(ScriptVariant_IntegerValue(svar, &l1) == S_OK &&
            ScriptVariant_IntegerValue(rightChild, &l2) == S_OK)
    {
        retvar.vt = VT_INTEGER;
        retvar.lVal = ((ULONG)l1) << ((ULONG)l2);
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Shr( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    LONG l1, l2;
    if(ScriptVariant_IntegerValue(svar, &l1) == S_OK &&
            ScriptVariant_IntegerValue(rightChild, &l2) == S_OK)
    {
        retvar.vt = VT_INTEGER;
        retvar.lVal = ((ULONG)l1) >> ((ULONG)l2);
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}


static int ScriptVariant_FormatValue(const ScriptVariant *value, CHAR *buffer, size_t capacity)
{
    switch(value->vt)
    {
    case VT_EMPTY:
        return snprintf(buffer, capacity, "<VT_EMPTY>   Unitialized");
    case VT_INTEGER:
        return snprintf(buffer, capacity, "%d", value->lVal);
    case VT_DECIMAL:
        return snprintf(buffer, capacity, "%lf", value->dblVal);
    case VT_PTR:
        return snprintf(buffer, capacity, "#%ld", (long)value->ptrVal);
    case VT_STR:
    {
        const CHAR *text = StrCache_GetIfPresent(value->strVal);
        return text ? snprintf(buffer, capacity, "%s", text) : -1;
    }
    default:
        return snprintf(buffer, capacity, "<Unprintable VARIANT type.>");
    }
}

static void ScriptVariant_JoinText(ScriptVariant *result, ScriptVariant *left, ScriptVariant *right)
{
    const int left_length = ScriptVariant_FormatValue(left, NULL, 0);
    const int right_length = ScriptVariant_FormatValue(right, NULL, 0);
    if(left_length < 0 || right_length < 0 || left_length > INT_MAX - right_length)
    {
        ScriptVariant_Clear(result);
        return;
    }

    // Preserve an operand that is also the previous temporary addition result.
    ScriptVariant previous = {.vt = VT_EMPTY};
    if(left == result || right == result)
    {
        ScriptVariant_Copy(&previous, result);
        if(left == result) left = &previous;
        if(right == result) right = &previous;
    }

    const int length = left_length + right_length;
    ScriptVariant_ChangeType(result, VT_STR);
    Varstr *entry = &strcache[result->strVal];
    if(entry->len < length)
    {
        CHAR *expanded = realloc(entry->str, (size_t)length + 1);
        if(!expanded)
        {
            ScriptVariant_Clear(result);
            ScriptVariant_Clear(&previous);
            return;
        }
        entry->str = expanded;
        entry->len = length;
    }

    ScriptVariant_FormatValue(left, entry->str, (size_t)left_length + 1);
    ScriptVariant_FormatValue(right, entry->str + left_length, (size_t)right_length + 1);
    ScriptVariant_Clear(&previous);
}

ScriptVariant *ScriptVariant_Add( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    DOUBLE dbl1, dbl2;
    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        if(svar->vt == VT_DECIMAL || rightChild->vt == VT_DECIMAL)
        {
            ScriptVariant_ChangeType(&retvar, VT_DECIMAL);
            retvar.dblVal = dbl1 + dbl2;
        }
        else
        {
            ScriptVariant_ChangeType(&retvar, VT_INTEGER);
            retvar.lVal = (LONG)(dbl1 + dbl2);
        }
    }
    else if(svar->vt == VT_STR || rightChild->vt == VT_STR)
    {
        ScriptVariant_JoinText(&retvar, svar, rightChild);
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Sub( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    DOUBLE dbl1, dbl2;
    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        if(svar->vt == VT_DECIMAL || rightChild->vt == VT_DECIMAL)
        {
            retvar.vt = VT_DECIMAL;
            retvar.dblVal = dbl1 - dbl2;
        }
        else
        {
            retvar.vt = VT_INTEGER;
            retvar.lVal = (LONG)(dbl1 - dbl2);
        }
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Mul( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    DOUBLE dbl1, dbl2;
    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        if(svar->vt == VT_DECIMAL || rightChild->vt == VT_DECIMAL)
        {
            retvar.vt = VT_DECIMAL;
            retvar.dblVal = dbl1 * dbl2;
        }
        else
        {
            retvar.vt = VT_INTEGER;
            retvar.lVal = (LONG)(dbl1 * dbl2);
        }
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Div( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    DOUBLE dbl1, dbl2;
    if(ScriptVariant_DecimalValue(svar, &dbl1) == S_OK &&
            ScriptVariant_DecimalValue(rightChild, &dbl2) == S_OK)
    {
        if(dbl2 == 0)
        {
            ScriptVariant_Init(&retvar);
        }
        else if(svar->vt == VT_DECIMAL || rightChild->vt == VT_DECIMAL)
        {
            retvar.vt = VT_DECIMAL;
            retvar.dblVal = dbl1 / dbl2;
        }
        else
        {
            retvar.vt = VT_INTEGER;
            retvar.lVal = (LONG)(dbl1 / dbl2);
        }
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}


ScriptVariant *ScriptVariant_Mod( ScriptVariant *svar, ScriptVariant *rightChild )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    LONG l1, l2;
    if(ScriptVariant_IntegerValue(svar, &l1) == S_OK &&
            ScriptVariant_IntegerValue(rightChild, &l2) == S_OK)
    {
        retvar.vt = VT_INTEGER;
        retvar.lVal = l1 % l2;
    }
    else
    {
        ScriptVariant_Clear(&retvar);
    }

    return &retvar;
}

//Unary Operations
//++i

void ScriptVariant_Inc_Op(ScriptVariant *svar )
{
    switch(svar->vt)
    {
    case VT_DECIMAL:
        ++(svar->dblVal);
        break;
    case VT_INTEGER:
        ++(svar->lVal);
        break;
    default:
        break;
    }

    //Send back this ScriptVariant
    //return svar;
}

// i++

ScriptVariant *ScriptVariant_Inc_Op2(ScriptVariant *svar )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    ScriptVariant_Copy(&retvar, svar);

    switch(svar->vt)
    {
    case VT_DECIMAL:
        svar->dblVal++;
        break;
    case VT_INTEGER:
        svar->lVal++;
        break;
    default:
        ScriptVariant_Clear(&retvar);
        break;
    }

    return &retvar;
}

//--i

void ScriptVariant_Dec_Op(ScriptVariant *svar )
{
    switch(svar->vt)
    {
    case VT_DECIMAL:
        --(svar->dblVal);
        break;
    case VT_INTEGER:
        --(svar->lVal);
        break;
    default:
        break;
    }

    //Send back this ScriptVariant
    //return svar;
}

// i--

ScriptVariant *ScriptVariant_Dec_Op2(ScriptVariant *svar )
{
    static ScriptVariant retvar = {{.ptrVal = NULL}, VT_EMPTY};
    ScriptVariant_Copy(&retvar, svar);

    switch(svar->vt)
    {
    case VT_DECIMAL:
        svar->dblVal--;
        break;
    case VT_INTEGER:
        svar->lVal--;
        break;
    default:
        ScriptVariant_Clear(&retvar);
        break;
    }

    return &retvar;
}

//+i

void ScriptVariant_Pos( ScriptVariant *svar)
{
    /*
    static ScriptVariant retvar = {{.ptrVal=NULL}, VT_EMPTY};
    switch(svar->vt)
    {
    case VT_DECIMAL:retvar.vt=VT_DECIMAL;retvar.dblVal = +(svar->dblVal);
    case VT_INTEGER:retvar.vt=VT_INTEGER;retvar.lVal = +(svar->lVal);
    default:break;
    }
    ScriptVariant_Copy(svar, &retvar);
    return svar;*/
}

//-i

void ScriptVariant_Neg( ScriptVariant *svar)
{
    switch(svar->vt)
    {
    case VT_DECIMAL:
        svar->dblVal = -(svar->dblVal);
    case VT_INTEGER:
        svar->lVal = -(svar->lVal);
    default:
        break;
    }
    //return svar;
}


void ScriptVariant_Boolean_Not(ScriptVariant *svar )
{
    /*
    static ScriptVariant retvar = {{.lVal=0}, VT_INTEGER};
    retvar.lVal = !ScriptVariant_IsTrue(svar);
    ScriptVariant_Copy(svar, &retvar);
    return svar;*/
    BOOL b = !ScriptVariant_IsTrue(svar);
    ScriptVariant_ChangeType(svar, VT_INTEGER);
    svar->lVal = b;

}



