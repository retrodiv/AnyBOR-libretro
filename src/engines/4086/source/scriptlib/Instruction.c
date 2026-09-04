/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2013 OpenBOR Team
 */

#include "Instruction.h"
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void Instruction_InitViaToken(Instruction *pins, OpCode code, Token *pToken )
{
    memset(pins, 0, sizeof(Instruction));
    pins->OpCode = code;
    pins->storageType = INSTRUCTION_SOURCE_TOKEN;
    pins->theToken = malloc(sizeof(Token));
    memset(pins->theToken, 0, sizeof(Token));
    if(pToken)
    {
        *(pins->theToken) = *pToken;
    }
    else
    {
        pins->theToken->theType = END_OF_TOKENS;
    }
}

void Instruction_InitViaLabel(Instruction *pins, OpCode code, LPCSTR label )
{
    memset(pins, 0, sizeof(Instruction));
    pins->OpCode = code;
    pins->storageType = INSTRUCTION_SOURCE_LABEL;
    pins->Label = malloc(sizeof(CHAR) * (MAX_STR_LEN + 1));
    strcpy(pins->Label, label);
}

void Instruction_Init(Instruction *pins)
{
    memset(pins, 0, sizeof(Instruction));
    pins->storageType = INSTRUCTION_SOURCE_TOKEN;
    pins->theToken = malloc(sizeof(Token));
    memset(pins->theToken, 0, sizeof(Token));
    pins->theToken->theType = END_OF_TOKENS;
}

int Instruction_OwnsValue(const Instruction *pins)
{
    if(!pins) return 0;
    return pins->OpCode != JUMPR && pins->OpCode != Branch_FALSE &&
           pins->OpCode != Branch_TRUE && pins->OpCode != Branch_EQUAL;
}

ScriptVariant **Instruction_FirstReferenceAddress(Instruction *pins)
{
    if(!pins) return NULL;
    switch(pins->OpCode)
    {
    case JUMPR:
    case Branch_FALSE:
    case Branch_TRUE:
    case Branch_EQUAL:
        return &pins->theVal;
    case LOAD:
    case SAVE:
    case INC:
    case DEC:
    case POS:
    case NEG:
    case NOT:
    case MUL:
    case DIV:
    case MOD:
    case ADD:
    case SUB:
    case SHL:
    case SHR:
    case GE:
    case LE:
    case LT:
    case GT:
    case EQ:
    case NE:
    case OR:
    case AND:
    case BIT_OR:
    case XOR:
    case BIT_AND:
        return &pins->theRef;
    default:
        return NULL;
    }
}

void Instruction_Clear(Instruction *pins)
{
    if(Instruction_OwnsValue(pins) && pins->theVal)
    {
        ScriptVariant_Clear(pins->theVal);
        free((void *)pins->theVal);
    }
    if(pins->OpCode == CALL && pins->theRefList)
    {
        if(pins->referenceStorageType == INSTRUCTION_REFERENCE_COMPACT)
            free(pins->callReferences);
        else
        {
            List_Clear(pins->theRefList);
            free(pins->theRefList);
        }
    }
    if(pins->storageType == INSTRUCTION_SOURCE_LABEL && pins->Label)
    {
        free(pins->Label);
    }
    if(pins->storageType == INSTRUCTION_SOURCE_TOKEN && pins->theToken)
    {
        free(pins->theToken);
    }
    memset(pins, 0, sizeof(Instruction));
}

int Instruction_CompactCallReferences(Instruction *pins)
{
    List *source;
    CallReferenceList *compact;
    int count;
    size_t bytes;
    if(!pins || pins->OpCode != CALL || !pins->theRefList ||
       pins->referenceStorageType == INSTRUCTION_REFERENCE_COMPACT) return 1;
    source = pins->theRefList;
    count = List_GetSize(source);
    if(count < 0 || (count > 0 && !source->solidlist) ||
       (size_t)count > (SIZE_MAX - sizeof(*compact)) / sizeof(compact->values[0])) return 0;
    bytes = sizeof(*compact) + (size_t)count * sizeof(compact->values[0]);
    compact = malloc(bytes);
    if(!compact) return 0;
    compact->index = 0;
    compact->size = count;
    if(count) memcpy(compact->values, source->solidlist,
                     (size_t)count * sizeof(compact->values[0]));
    List_Clear(source);
    free(source);
    pins->callReferences = compact;
    pins->referenceStorageType = INSTRUCTION_REFERENCE_COMPACT;
    return 1;
}

int Instruction_CallReferenceCount(const Instruction *pins)
{
    if(!pins || pins->OpCode != CALL || !pins->theRefList) return 0;
    return pins->referenceStorageType == INSTRUCTION_REFERENCE_COMPACT ?
           pins->callReferences->size : List_GetSize(pins->theRefList);
}

ScriptVariant **Instruction_CallReferenceValues(const Instruction *pins)
{
    if(!pins || pins->OpCode != CALL || !pins->theRefList) return NULL;
    return pins->referenceStorageType == INSTRUCTION_REFERENCE_COMPACT ?
           (ScriptVariant **)pins->callReferences->values :
           (ScriptVariant **)pins->theRefList->solidlist;
}

int *Instruction_CallReferenceIndex(Instruction *pins)
{
    if(!pins || pins->OpCode != CALL || !pins->theRefList) return NULL;
    return pins->referenceStorageType == INSTRUCTION_REFERENCE_COMPACT ?
           &pins->callReferences->index : &pins->theRefList->index;
}


int htoi(const char *src)
{
    int len;
    int temp, ret;
    const char *ptr;

    len = strlen(src);
    if(len < 3 || src[0] != '0' || (src[1] != 'x' && src[1] != 'X'))
    {
        return 0;
    }

    ptr = src + len - 1;
    if(*ptr == 'U' || *ptr == 'u' ||
            *ptr == 'l' || *ptr == 'L')
    {
        ptr--;
    }

    for(temp = 1, ret = 0; ptr != src + 1; ptr--)
    {
        if(*ptr <= '9' && *ptr >= '0')
        {
            ret += (*ptr - '9' + 9) * temp;
        }
        else if(*ptr <= 'f' && *ptr >= 'a')
        {
            ret += (*ptr - 'f' + 0xf) * temp;
        }
        else if(*ptr <= 'F' && *ptr >= 'A')
        {
            ret += (*ptr - 'F' + 0xf) * temp;
        }
        else
        {
            return 0;
        }
        temp *= 16;
    }
    return ret;

}

void Instruction_NewData(Instruction *pins)
{
    if(pins->theVal)
    {
        return;
    }
    pins->theVal = (ScriptVariant *)malloc(sizeof(ScriptVariant));
    ScriptVariant_Init( pins->theVal);
}

//'compile' constant to improve speed
void Instruction_ConvertConstant(Instruction *pins)
{
    ScriptVariant *pvar;
    CHAR *sc;
    if(pins->theVal)
    {
        return;    //already have the constant as a variant
    }
    if( pins->OpCode == CONSTDBL)
    {
        pvar = (ScriptVariant *)malloc(sizeof(ScriptVariant));
        ScriptVariant_Init(pvar);
        ScriptVariant_ChangeType(pvar, VT_DECIMAL);
        //Note: There shouldn't be any double constants added via a label,
        //      unless you added something I don't know...
        sc = pins->theToken->theSource;
        if(sc[0] == '!' || sc[0] == '-')
        {
            sc++;
        }
        pvar->dblVal = (DOUBLE)atof(sc);
        if(pins->theToken->theSource[0] == '!')
        {
            pvar->dblVal = (DOUBLE)(!pvar->dblVal);
        }
        else if(pins->theToken->theSource[0] == '-')
        {
            pvar->dblVal = -pvar->dblVal;
        }

    }
    else if( pins->OpCode == CONSTINT || pins->OpCode == CHECKARG)
    {
        pvar = (ScriptVariant *)malloc(sizeof(ScriptVariant));
        ScriptVariant_Init(pvar);
        ScriptVariant_ChangeType(pvar, VT_INTEGER);
        sc = pins->theToken->theSource;
        if (pins->storageType == INSTRUCTION_SOURCE_TOKEN &&
            pins->theToken->theType != END_OF_TOKENS)
        {
            sc = pins->theToken->theSource;
            if(sc[0] == '!' || sc[0] == '-')
            {
                sc++;
            }
            if(pins->theToken->theType == TOKEN_HEXCONSTANT)
            {
                pvar->lVal = (LONG)htoi(sc);
            }
            else
            {
                pvar->lVal = (LONG)atoi(sc);
            }
            if(pins->theToken->theSource[0] == '!')
            {
                pvar->lVal = (LONG)(!pvar->dblVal);
            }
            else if(pins->theToken->theSource[0] == '-')
            {
                pvar->lVal = -pvar->lVal;
            }
        }
        else
        {
            // Argument count is the only integer constant added via a label
            // check hex number just in case, though it is not possible
            // unless you add it manually...
            if(pins->Label[1] == 'x' || pins->Label[1] == 'X')
            {
                pvar->lVal = (LONG)htoi( pins->Label);
            }
            else
            {
                pvar->lVal = (LONG)atoi( pins->Label);
            }
        }
    }
    else if(pins->OpCode == CONSTSTR)
    {
        pvar = (ScriptVariant *)malloc(sizeof(ScriptVariant));
        ScriptVariant_Init(pvar);
        ScriptVariant_ParseStringConstant(pvar, pins->theToken->theSource);
    }
    else
    {
        return;
    }
    pins->theVal = pvar;
}


void Instruction_ToString(Instruction *pins, LPSTR strRep)
{
    strRep[0] = 0;

    switch( pins->OpCode )
    {
    case CONSTSTR:
        strcpy( strRep, "CONSTSTR " );
        break;
    case CONSTDBL:
        strcpy( strRep, "CONSTDBL " );
        break;
    case CONSTINT:
        strcpy( strRep, "CONSTINT " );
        break;
    case LOAD:
        strcpy( strRep, "LOAD " );
        break;
    case SAVE:
        strcpy( strRep, "SAVE " );
        break;
    case INC:
        strcpy( strRep, "INC " );
        break;
    case DEC:
        strcpy( strRep, "DEC " );
        break;
    case FIELD:
        strcpy( strRep, "FIELD " );
        break;
    case CALL:
        strcpy( strRep, "CALL " );
        break;
    case POS:
        strcpy( strRep, "POS " );
        break;
    case NEG:
        strcpy( strRep, "NEG " );
        break;
    case NOT:
        strcpy( strRep, "NOT " );
        break;
    case MUL:
        strcpy( strRep, "MUL " );
        break;
    case MOD:
        strcpy( strRep, "MOD " );
        break;
    case DIV:
        strcpy( strRep, "DIV " );
        break;
    case ERR:
        strcpy( strRep, "ERR " );
        break;
    case ADD:
        strcpy( strRep, "ADD " );
        break;
    case SUB:
        strcpy( strRep, "SUB " );
        break;
    case SHL:
        strcpy( strRep, "SHL " );
        break;
    case SHR:
        strcpy( strRep, "SHR " );
        break;
    case JUMP:
        strcpy( strRep, "JUMP " );
        break;
    case PJUMP:
        strcpy( strRep, "PJUMP " );
        break;
    case GE:
        strcpy( strRep, "GE " );
        break;
    case LE:
        strcpy( strRep, "LE " );
        break;
    case LT:
        strcpy( strRep, "LT " );
        break;
    case GT:
        strcpy( strRep, "GT " );
        break;
    case EQ:
        strcpy( strRep, "EQ " );
        break;
    case NE:
        strcpy( strRep, "NE " );
        break;
    case OR:
        strcpy( strRep, "OR " );
        break;
    case AND:
        strcpy( strRep, "AND " );
        break;
    case BIT_OR:
        strcpy( strRep, "BIT_OR " );
        break;
    case XOR:
        strcpy( strRep, "XOR " );
        break;
    case BIT_AND:
        strcpy( strRep, "BIT_AND " );
        break;
    case NOOP:
        strcpy( strRep, "NOOP " );
        break;
    case PUSH:
        strcpy( strRep, "PUSH " );
        break;
    case POP:
        strcpy( strRep, "POP " );
        break;
    case Branch_FALSE:
        strcpy( strRep, "Branch_FALSE " );
        break;
    case Branch_TRUE:
        strcpy( strRep, "Branch_TRUE " );
        break;
    case Branch_EQUAL:
        strcpy( strRep, "Branch_EQUAL " );
        break;
    case DATA:
        strcpy( strRep, "DATA " );
        break;
    case PARAM:
        strcpy( strRep, "PARAM " );
        break;
    case IMMEDIATE:
        strcpy( strRep, "IMMEDIATE " );
        break;
    case DEFERRED:
        strcpy( strRep, "DEFERRED " );
        break;
    case RET:
        strcpy( strRep, "RET " );
        break;
    case CHECKARG:
        strcpy( strRep, "CHECKARG " );
        break;
    case CLEAN:
        strcpy( strRep, "CLEAN " );
        break;
    case JUMPR:
        strcpy( strRep, "JUMPR " );
        break;
    case FUNCDECL:
        strcpy( strRep, "FUNCDECL " );
        break;
    default:
        strcpy( strRep, "[unknown] " );
        break;
    }

    //If the label isn't NULL, then copy that into the buffer as well
    if (pins->storageType == INSTRUCTION_SOURCE_LABEL && pins->Label && pins->Label[0])
    {
        strcat( strRep, pins->Label);
    }
    if (pins->storageType == INSTRUCTION_SOURCE_TOKEN && pins->theToken &&
        pins->theToken->theType != END_OF_TOKENS)
    {
        if(pins->OpCode == CONSTSTR)
        {
            strcat( strRep, "\"");
        }
        strcat( strRep, pins->theToken->theSource );
        if(pins->OpCode == CONSTSTR)
        {
            strcat( strRep, "\"");
        }
    }

}
