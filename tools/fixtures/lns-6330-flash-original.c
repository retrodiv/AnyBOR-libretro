/* SPDX-License-Identifier: BSD-3-Clause
 * OpenBOR - Copyright (c) 2004 - 2017 OpenBOR Team.
 * All rights reserved; see the distributed OpenBOR BSD-3-Clause licence.
 * LNS enhancements credited to Hechelion and Gonzalo MVP.
 * LNS cfb4f3a676613714757d4539275482f7c323d6ad; official 6330
 * 4b1705fa37457ab38bc5d0fcc561242019588e32. */
static int lns_original_flash(entity *ent, ScriptVariant **varlist, ScriptVariant **pretvar)
{
 ScriptVariant *arg; LONG ltemp;
 switch(_ep_flash) {
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

        switch(ltemp)
        {
        case _ep_flash_block:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.bflash;
            break;
        }
        case _ep_flash_def:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.flash;
            break;
        }
        case _ep_flash_noattack:
        {
            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)ent->modeldata.noatflash;
            break;
        }
        case _ep_flash_overridesource:
        {
            ScriptVariant_ChangeType(*pretvar, VT_STR);
            int model_index = ent->modeldata.flashoverridesource;
            if(model_index >= 0 && model_index < models_cached)
            {
                (*pretvar)->strVal = StrCache_CreateNewFrom(model_cache[model_index].name);
            }
            else
            {
                (*pretvar)->strVal = StrCache_CreateNewFrom("");
            }
            break;
        }
        case _ep_flash_overridetarget:
        {
            ScriptVariant_ChangeType(*pretvar, VT_STR);
            int model_index = ent->modeldata.flashoverridetarget;
            if(model_index >= 0 && model_index < models_cached)
            {
                (*pretvar)->strVal = StrCache_CreateNewFrom(model_cache[model_index].name);
            }
            else
            {
                (*pretvar)->strVal = StrCache_CreateNewFrom("");
            }
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

 }
 return S_OK;
}
static int lns_original_played(int index, ScriptVariant *arg)
{ LONG ltemp; switch(_pp_hasplayed) {
    case _pp_hasplayed:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].hasplayed = players[index] = (LONG)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }

 } return S_OK; cpperror: return E_FAIL; }
static int official_original_flash(entity *ent, ScriptVariant **varlist, ScriptVariant **pretvar)
{
 ScriptVariant *arg; LONG ltemp; int i;
 switch(_ep_flash) {
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

 }
 return S_OK;
}
static int official_original_played(int index, ScriptVariant *arg)
{ LONG ltemp; switch(_pp_hasplayed) {
    case _pp_hasplayed:
    {
        if(SUCCEEDED(ScriptVariant_IntegerValue(arg, &ltemp)))
        {
            player[index].hasplayed = (LONG)ltemp;
        }
        else
        {
            goto cpperror;
        }
        break;
    }

 } return S_OK; cpperror: return E_FAIL; }
