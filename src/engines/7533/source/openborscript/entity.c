/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Translate native entity property names, numeric IDs and animation values
 * for each logical profile.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved. See LICENSE in OpenBOR root for license details.
 *
 * Copyright (c)  OpenBOR Team
 */

 #include "scriptcommon.h"

static int obor_profile_entity_property_end(void)
{
    return (int)ENTITY_PROPERTY_END - (obor_profile_build < 7553u)
         - (obor_profile_build < 7475u) - (obor_profile_build < 7445u);
}

int mapstrings_entity_property(ScriptVariant **varlist, int paramCount)
{
    char *propname;
    int prop;
    static const char *names[] =
    {
        "ai_disable",
        "ai_target_entity",
        "alternate_idle",
        "alternate_walk",
        "animation",
        "animation_frame",
        "animation_id",
        "animation_id_previous",
        "animation_state",
        "animation_time",
        "arrow_state",
        "attack_id_incoming",
        "attack_id_outgoing",
        "attack_state",
        "autokill",
        "back_hit_direction",
        "bind",
        "blast_state",
        "blink",
        "block_state",
        "boss",
        "charge_state",
        "child",
        "colorset_default",
        "colorset_dying_health_1",
        "colorset_dying_health_2",
        "colorset_dying_index_1",
        "colorset_dying_index_2",
        "colorset_table",
        "colorset_time",
        "combo_step",
        "combo_time",
        "command_time",
        "damage_on_landing",
        "dead",
        "defense_collection",
        "destination_x",
        "destination_z",
        "die_on_landing",
        "drawmethod",
        "drop",
        "duck_state",
        "entvar_collection",
        "escape_count",
        "exists",
        "explode",
        "fall_state",
        "freeze_state",
        "freeze_time",
        "function_take_action",
        "function_take_damage",
        "function_think",
        "function_try_move",
        "get_state",
        "grab_target",
        "grab_walk_state",
        "guard_time",
        "hp",
        "hp_old",
        "idle_state",
        "in_pain",
        "in_pain_back",
        "invincible_state",
        "invincible_time",
        "item_data",
        "jump_animation_id",
        "jump_state",
        "jump_velocity_x",
        "jump_velocity_y",
        "jump_velocity_z",
        "knockdown_count",
        "knockdown_time",
        "last_damage_type",
        "last_hit",
        "lifespan",
        "link",
        "model",
        "model_data",
        "model_default",
        "move_time",
        "move_x",
        "move_z",
        "mp",
        "mp_charge_time",
        "mp_old",
        "mp_time",
        "name",
        "next_attack_time",
        "next_hit_time",
        "nograb",
        "nograb_default",
        "obstructed",
        "obstruction_overhead",
        "offense_collection",
        "opponent",
        "owner",
        "parent",
        "path_obstructed_wait",
        "pause_time",
        "platform_land",
        "player_index",
        "position_base",
        "position_base_alternate",
        "position_direction",
        "position_x",
        "position_y",
        "position_z",
        "projectile_prime",
        "recursive_damage",
        "release_time",
        "rise_attack_delay",
        "rise_attack_time",
        "rise_delay",
        "rise_state",
        "run_state",
        "rush",
        "script_collection",
        "seal_energy",
        "seal_time",
        "sleep_time",
        "sort_id",
        "space_other",
        "spawn_type",
        "speed_multiplier",
        "stall_time",
        "think_time",
        "timestamp",
        "to_cost",
        "toss_time",
        "turn_state",
        "turn_time",
        "update_mark",
        "velocity_x",
        "velocity_y",
        "velocity_z",
        "walk_state",
        "waypoint_collection",
        "waypoint_count",
        "weapon_item",
        "weapon_state",
    };

    if (obor_profile_build >= 7445u || paramCount < 2)
    {
        return 1;
    }

    MAPSTRINGS(varlist[1], names, sizeof(names) / sizeof(names[0]),
               "\n\n Error: '%s' is not a known entity property.\n");
    return 1;
}

static e_entity_properties obor_entity_property_native_id(unsigned int profile_index)
{
    if (profile_index >= (unsigned int)obor_profile_entity_property_end())
    {
        profile_index = ENTITY_PROPERTY_END;
    }
    else
    {
        // Translate the original selector across the subsequent insertions.
        if (obor_profile_build < 7445u && profile_index >= ENTITY_PROPERTY_FACTION)
        {
            ++profile_index;
        }
        if (obor_profile_build < 7553u && profile_index >= ENTITY_PROPERTY_GUARD_POINTS)
        {
            ++profile_index;
        }
        if (obor_profile_build < 7475u && profile_index >= ENTITY_PROPERTY_SHADOW_CONFIG_FLAGS)
        {
            ++profile_index;
        }
    }
    return (e_entity_properties)profile_index;
}

const s_property_access_map entity_get_property_map(const void* acting_object_param, const unsigned int property_index_param)
{
    s_property_access_map property_map;
    const entity* acting_object = acting_object_param;
    const e_entity_properties property_index = obor_entity_property_native_id(property_index_param);

	switch (property_index)
	{

	case ENTITY_PROPERTY_AI_DISABLE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->noaicontrol;
		property_map.id_string = "ENTITY_PROPERTY_AI_DISABLE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_AI_TARGET_ENTITY:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->custom_target;
		property_map.id_string = "ENTITY_PROPERTY_AI_TARGET_ENTITY";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_ALTERNATE_IDLE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->idlemode;
		property_map.id_string = "ENTITY_PROPERTY_ALTERNATE_IDLE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ALTERNATE_WALK:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->walkmode;
		property_map.id_string = "ENTITY_PROPERTY_ALTERNATE_WALK";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ANIMATION:

		property_map.config_flags = obor_profile_build < 7504u
            ? PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT : PROPERTY_ACCESS_CONFIG_READ;
		property_map.field = &acting_object->animation;
		property_map.id_string = "ENTITY_PROPERTY_ANIMATION";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_ANIMATION_FRAME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->animpos;
		property_map.id_string = "ENTITY_PROPERTY_ANIMATION_FRAME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ANIMATION_ID:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->animnum;
		property_map.id_string = "ENTITY_PROPERTY_ANIMATION_ID";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ANIMATION_ID_PREVIOUS:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->animnum_previous;
		property_map.id_string = "ENTITY_PROPERTY_ANIMATION_ID_PREVIOUS";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ANIMATION_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->animating;
		property_map.id_string = "ENTITY_PROPERTY_ANIMATION_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ANIMATION_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->nextanim;
		property_map.id_string = "ENTITY_PROPERTY_ANIMATION_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ARROW_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->arrowon;
		property_map.id_string = "ENTITY_PROPERTY_ARROW_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ATTACK_ID_INCOMING:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->attack_id_incoming;
		property_map.id_string = "ENTITY_PROPERTY_ATTACK_ID_INCOMING";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_ATTACK_ID_OUTGOING:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->attack_id_outgoing;
		property_map.id_string = "ENTITY_PROPERTY_ATTACK_ID_OUTGOING";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ATTACK_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->attacking;
		property_map.id_string = "ENTITY_PROPERTY_ATTACK_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_AUTOKILL:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->autokill;
		property_map.id_string = "ENTITY_PROPERTY_AUTOKILL";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_BACK_HIT_DIRECTION:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->normaldamageflipdir;
		property_map.id_string = "ENTITY_PROPERTY_BACK_HIT_DIRECTION";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_BIND:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->binding;
		property_map.id_string = "ENTITY_PROPERTY_BIND";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_BLAST_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->projectile;
		property_map.id_string = "ENTITY_PROPERTY_BLAST_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_BLINK:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->blink;
		property_map.id_string = "ENTITY_PROPERTY_BLINK";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_BLOCK_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->blocking;
		property_map.id_string = "ENTITY_PROPERTY_BLOCK_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_BOSS:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->boss;
		property_map.id_string = "ENTITY_PROPERTY_BOSS";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_CHARGE_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->charging;
		property_map.id_string = "ENTITY_PROPERTY_CHARGE_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_CHILD:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->subentity;
		property_map.id_string = "ENTITY_PROPERTY_CHILD";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_COLORSET_DEFAULT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->map;
		property_map.id_string = "ENTITY_PROPERTY_COLORSET_DEFAULT";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_COLORSET_DYING_HEALTH_1:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->per1;
		property_map.id_string = "ENTITY_PROPERTY_COLORSET_DYING_HEALTH_1";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_COLORSET_DYING_HEALTH_2:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->per2;
		property_map.id_string = "ENTITY_PROPERTY_COLORSET_DYING_HEALTH_2";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_COLORSET_DYING_INDEX_1:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->dying;
		property_map.id_string = "ENTITY_PROPERTY_COLORSET_DYING_INDEX_1";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_COLORSET_DYING_INDEX_2:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->dying2;
		property_map.id_string = "ENTITY_PROPERTY_COLORSET_DYING_INDEX_2";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_COLORSET_TABLE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->colourmap;
		property_map.id_string = "ENTITY_PROPERTY_COLORSET_TABLE";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_COLORSET_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->maptime;
		property_map.id_string = "ENTITY_PROPERTY_COLORSET_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_COMBO_STEP:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->combostep;
		property_map.id_string = "ENTITY_PROPERTY_COMBO_STEP";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_COMBO_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->combotime;
		property_map.id_string = "ENTITY_PROPERTY_COMBO_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_COMMAND_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->movetime;
		property_map.id_string = "ENTITY_PROPERTY_COMMAND_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_DAMAGE_ON_LANDING:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->damage_on_landing;
		property_map.id_string = "ENTITY_PROPERTY_DAMAGE_ON_LANDING";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_DEATH_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->death_state;
		property_map.id_string = "ENTITY_PROPERTY_DEATH_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_DEFENSE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_READ;
		property_map.field = &acting_object->defense;
		property_map.id_string = "ENTITY_PROPERTY_DEFENSE";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_DESTINATION_X:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->destx;
		property_map.id_string = "ENTITY_PROPERTY_DESTINATION_X";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_DESTINATION_Z:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->destz;
		property_map.id_string = "ENTITY_PROPERTY_DESTINATION_Z";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_DIE_ON_LANDING:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->die_on_landing;
		property_map.id_string = "ENTITY_PROPERTY_DIE_ON_LANDING";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_DRAWMETHOD:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->drawmethod;
		property_map.id_string = "ENTITY_PROPERTY_DRAWMETHOD";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_DROP:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->drop;
		property_map.id_string = "ENTITY_PROPERTY_DROP";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_DUCK_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->ducking;
		property_map.id_string = "ENTITY_PROPERTY_DUCK_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ENTVAR_COLLECTION:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->varlist;
		property_map.id_string = "ENTITY_PROPERTY_ENTVAR_COLLECTION";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_ESCAPE_COUNT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->escapecount;
		property_map.id_string = "ENTITY_PROPERTY_ESCAPE_COUNT";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_EXISTS:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->exists;
		property_map.id_string = "ENTITY_PROPERTY_EXISTS";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_EXPLODE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->toexplode;
		property_map.id_string = "ENTITY_PROPERTY_EXPLODE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_FACTION:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->faction;
		property_map.id_string = "ENTITY_PROPERTY_FACTION";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_FALL_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->falling;
		property_map.id_string = "ENTITY_PROPERTY_FALL_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_FREEZE_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->frozen;
		property_map.id_string = "ENTITY_PROPERTY_FREEZE_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_FREEZE_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->freezetime;
		property_map.id_string = "ENTITY_PROPERTY_FREEZE_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_FUNCTION_TAKE_ACTION:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->takeaction;
		property_map.id_string = "ENTITY_PROPERTY_FUNCTION_TAKE_ACTION";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_FUNCTION_TAKE_DAMAGE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->takedamage;
		property_map.id_string = "ENTITY_PROPERTY_FUNCTION_TAKE_DAMAGE";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_FUNCTION_THINK:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->think;
		property_map.id_string = "ENTITY_PROPERTY_FUNCTION_THINK";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_FUNCTION_TRY_MOVE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->trymove;
		property_map.id_string = "ENTITY_PROPERTY_FUNCTION_TRY_MOVE";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_GET_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->getting;
		property_map.id_string = "ENTITY_PROPERTY_GET_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_GRAB_TARGET:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->grabbing;
		property_map.id_string = "ENTITY_PROPERTY_GRAB_TARGET";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_GRAB_WALK_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->grabwalking;
		property_map.id_string = "ENTITY_PROPERTY_GRAB_WALK_STATE";
		property_map.type = VT_INTEGER;
		break;

    case ENTITY_PROPERTY_GUARD_POINTS:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->guardpoints;
        property_map.id_string = "ENTITY_PROPERTY_GUARD_POINTS";
        property_map.type = VT_INTEGER;
        break;

	case ENTITY_PROPERTY_GUARD_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->guardtime;
		property_map.id_string = "ENTITY_PROPERTY_GUARD_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_HP:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->energy_state.health_current;
		property_map.id_string = "ENTITY_PROPERTY_HP";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_HP_OLD:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->energy_state.health_old;
		property_map.id_string = "ENTITY_PROPERTY_HP_OLD";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_IDLE_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->idling;
		property_map.id_string = "ENTITY_PROPERTY_IDLE_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_IN_PAIN:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->inpain;
		property_map.id_string = "ENTITY_PROPERTY_IN_PAIN";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_IN_PAIN_BACK:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->inbackpain;
		property_map.id_string = "ENTITY_PROPERTY_IN_PAIN_BACK";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_INVINCIBLE_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->invincible;
		property_map.id_string = "ENTITY_PROPERTY_INVINCIBLE_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_INVINCIBLE_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->invinctime;
		property_map.id_string = "ENTITY_PROPERTY_INVINCIBLE_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_ITEM_DATA:

		property_map.config_flags = obor_profile_build < 7504u
            ? (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER)
            : PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->item_properties;
		property_map.id_string = "ENTITY_PROPERTY_ITEM_DATA";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_JUMP_ANIMATION_ID:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->jump.animation_id;
		property_map.id_string = "ENTITY_PROPERTY_JUMP_ANIMATION_ID";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_JUMP_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->jumping;
		property_map.id_string = "ENTITY_PROPERTY_JUMP_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_JUMP_VELOCITY_X:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->jump.velocity.x;
		property_map.id_string = "ENTITY_PROPERTY_JUMP_VELOCITY_X";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_JUMP_VELOCITY_Y:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->jump.velocity.y;
		property_map.id_string = "ENTITY_PROPERTY_JUMP_VELOCITY_Y";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_JUMP_VELOCITY_Z:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->jump.velocity.z;
		property_map.id_string = "ENTITY_PROPERTY_JUMP_VELOCITY_Z";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_KNOCKDOWN_COUNT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->knockdowncount;
		property_map.id_string = "ENTITY_PROPERTY_KNOCKDOWN_COUNT";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_KNOCKDOWN_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->knockdowntime;
		property_map.id_string = "ENTITY_PROPERTY_KNOCKDOWN_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_LAST_DAMAGE_TYPE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->last_damage_type;
		property_map.id_string = "ENTITY_PROPERTY_LAST_DAMAGE_TYPE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_LAST_HIT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->lasthit;
		property_map.id_string = "ENTITY_PROPERTY_LAST_HIT";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_LIFESPAN:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->lifespancountdown;
		property_map.id_string = "ENTITY_PROPERTY_LIFESPAN";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_LINK:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->link;
		property_map.id_string = "ENTITY_PROPERTY_LINK";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_MODEL:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->model;
		property_map.id_string = "ENTITY_PROPERTY_MODEL";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_MODEL_DATA:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->modeldata;
		property_map.id_string = "ENTITY_PROPERTY_MODEL_DATA";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_MODEL_DEFAULT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->defaultmodel;
		property_map.id_string = "ENTITY_PROPERTY_MODEL_DATA";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_MOVE_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->nextmove;
		property_map.id_string = "ENTITY_PROPERTY_MOVE_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_MOVE_X:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->movex;
		property_map.id_string = "ENTITY_PROPERTY_MOVE_X";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_MOVE_Z:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->movez;
		property_map.id_string = "ENTITY_PROPERTY_MOVE_Z";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_MP:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->energy_state.mp_current;
		property_map.id_string = "ENTITY_PROPERTY_MP";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_MP_CHARGE_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->mpchargetime;
		property_map.id_string = "ENTITY_PROPERTY_MP_CHARGE_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_MP_OLD:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->energy_state.mp_old;
		property_map.id_string = "ENTITY_PROPERTY_MP_OLD";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_MP_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->magictime;
		property_map.id_string = "ENTITY_PROPERTY_MP_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_NAME:
		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT | PROPERTY_ACCESS_CONFIG_STATIC_LENGTH);
		property_map.field = &acting_object->name;
		property_map.id_string = "ENTITY_PROPERTY_NAME";
		property_map.type = VT_STR;
		break;

	case ENTITY_PROPERTY_NEXT_ATTACK_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->nextattack;
		property_map.id_string = "ENTITY_PROPERTY_NEXT_ATTACK_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_NEXT_HIT_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->next_hit_time;
		property_map.id_string = "ENTITY_PROPERTY_NEXT_HIT_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_NOGRAB:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->nograb;
		property_map.id_string = "ENTITY_PROPERTY_NOGRAB";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_NOGRAB_DEFAULT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->nograb_default;
		property_map.id_string = "ENTITY_PROPERTY_NOGRAB_DEFAULT";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_OBSTRUCTED:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->hitwall;
		property_map.id_string = "ENTITY_PROPERTY_OBSTRUCTED";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_OBSTRUCTION_OVERHEAD:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->hithead;
		property_map.id_string = "ENTITY_PROPERTY_OBSTRUCTION_OVERHEAD";
		property_map.type = obor_profile_build < 7504u ? VT_PTR : VT_INTEGER;
		break;

	case ENTITY_PROPERTY_OFFENSE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->offense;
		property_map.id_string = "ENTITY_PROPERTY_OFFENSE";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_OPPONENT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->opponent;
		property_map.id_string = "ENTITY_PROPERTY_OPPONENT";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_OWNER:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->owner;
		property_map.id_string = "ENTITY_PROPERTY_OWNER";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_PARENT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->parent;
		property_map.id_string = "ENTITY_PROPERTY_PARENT";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_PATH_OBSTRUCTED_WAIT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->pathblocked;
		property_map.id_string = "ENTITY_PROPERTY_PATH_OBSTRUCTED_WAIT";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_PAUSE_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->pausetime;
		property_map.id_string = "ENTITY_PROPERTY_PAUSE_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_PLATFORM_LAND:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->landed_on_platform;
		property_map.id_string = "ENTITY_PROPERTY_PLATFORM_LAND";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_PLAYER_INDEX:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->playerindex;
		property_map.id_string = "ENTITY_PROPERTY_PLAYER_INDEX";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_POSITION_BASE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->base;
		property_map.id_string = "ENTITY_PROPERTY_POSITION_BASE";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_POSITION_BASE_ALTERNATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->altbase;
		property_map.id_string = "ENTITY_PROPERTY_POSITION_BASE_ALTERNATE";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_POSITION_DIRECTION:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->direction;
		property_map.id_string = "ENTITY_PROPERTY_POSITION_DIRECTION";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_POSITION_X:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->position.x;
		property_map.id_string = "ENTITY_PROPERTY_POSITION_X";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_POSITION_Y:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->position.y;
		property_map.id_string = "ENTITY_PROPERTY_POSITION_Y";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_POSITION_Z:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->position.z;
		property_map.id_string = "ENTITY_PROPERTY_POSITION_Z";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_PROJECTILE_PRIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->projectile_prime;
		property_map.id_string = "ENTITY_PROPERTY_PROJECTILE_PRIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_RECURSIVE_DAMAGE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->recursive_damage;
		property_map.id_string = "ENTITY_PROPERTY_RECURSIVE_DAMAGE";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_RELEASE_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->releasetime;
		property_map.id_string = "ENTITY_PROPERTY_RELEASE_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_RISE_ATTACK_DELAY:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->staydown.riseattack;
		property_map.id_string = "ENTITY_PROPERTY_RISE_ATTACK_DELAY";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_RISE_ATTACK_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->staydown.riseattack_stall;
		property_map.id_string = "ENTITY_PROPERTY_RISE_ATTACK_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_RISE_DELAY:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->staydown.rise;
		property_map.id_string = "ENTITY_PROPERTY_RISE_DELAY";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_RISE_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->rising;
		property_map.id_string = "ENTITY_PROPERTY_RISE_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_RUN_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->running;
		property_map.id_string = "ENTITY_PROPERTY_RUN_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_RUSH:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->rush;
		property_map.id_string = "ENTITY_PROPERTY_RUSH";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_SCRIPT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->scripts;
		property_map.id_string = "ENTITY_PROPERTY_SCRIPT";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_SEAL_ENERGY:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->seal;
		property_map.id_string = "ENTITY_PROPERTY_SEAL_ENERGY";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_SEAL_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->sealtime;
		property_map.id_string = "ENTITY_PROPERTY_SEAL_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_SHADOW_CONFIG_FLAGS:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->shadow_config_flags;
		property_map.id_string = "ENTITY_PROPERTY_SHADOW_CONFIG_FLAGS";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_SLEEP_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->sleeptime;
		property_map.id_string = "ENTITY_PROPERTY_SLEEP_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_SORT_ID:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->sortid;
		property_map.id_string = "ENTITY_PROPERTY_SORT_ID";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_SPACE_OTHER:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->collided_entity;
		property_map.id_string = "ENTITY_PROPERTY_SPACE_OTHER";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_SPAWN_TYPE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->spawntype;
		property_map.id_string = "ENTITY_PROPERTY_SPAWN_TYPE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_SPEED_MULTIPLIER:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->speedmul;
		property_map.id_string = "ENTITY_PROPERTY_SPEED_MULTIPLIER";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_STALL_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->stalltime;
		property_map.id_string = "ENTITY_PROPERTY_STALL_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_THINK_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->nextthink;
		property_map.id_string = "ENTITY_PROPERTY_THINK_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_TIMESTAMP:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->timestamp;
		property_map.id_string = "ENTITY_PROPERTY_TIMESTAMP";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_TO_COST:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->tocost;
		property_map.id_string = "ENTITY_PROPERTY_TO_COST";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_TOSS_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->toss_time;
		property_map.id_string = "ENTITY_PROPERTY_TOSS_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_TURN_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->turning;
		property_map.id_string = "ENTITY_PROPERTY_TURN_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_TURN_TIME:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->turntime;
		property_map.id_string = "ENTITY_PROPERTY_TURN_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_UPDATE_MARK:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->update_mark;
        property_map.id_string = obor_profile_build >= 7534
            ? "ENTITY_PROPERTY_UPDATE_MARK" : "ENTITY_PROPERTY_TURN_TIME";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_VELOCITY_X:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->velocity.x;
		property_map.id_string = "ENTITY_PROPERTY_VELOCITY_X";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_VELOCITY_Y:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->velocity.y;
		property_map.id_string = "ENTITY_PROPERTY_VELOCITY_Y";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_VELOCITY_Z:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->velocity.z;
		property_map.id_string = "ENTITY_PROPERTY_VELOCITY_Z";
		property_map.type = VT_DECIMAL;
		break;

	case ENTITY_PROPERTY_WALK_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->walking;
		property_map.id_string = "ENTITY_PROPERTY_WALK_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_WAYPOINT:

		property_map.config_flags = obor_profile_build < 7504u ? PROPERTY_ACCESS_CONFIG_READ
                                                               : PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->waypoints;
		property_map.id_string = "ENTITY_PROPERTY_WAYPOINT";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_WAYPOINT_COUNT:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->numwaypoints;
		property_map.id_string = "ENTITY_PROPERTY_WAYPOINT_COUNT";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_WEAPON_ITEM:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->weapent;
		property_map.id_string = "ENTITY_PROPERTY_WEAPON_ITEM";
		property_map.type = VT_PTR;
		break;

	case ENTITY_PROPERTY_WEAPON_STATE:

		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->weapon_state;
		property_map.id_string = "ENTITY_PROPERTY_WEAPON_STATE";
		property_map.type = VT_INTEGER;
		break;

	case ENTITY_PROPERTY_END:
	default:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_NONE;
		property_map.field = NULL;
		property_map.id_string = "Entity";
		property_map.type = VT_EMPTY;
		break;
	}

	return property_map;
}

/*
* Caskey, Damon  V.
* 2023-03-03
*
* Return a property. Requires
* a object pointer and property
* constant to access.
*/
/* The original accessors converted the member value using its C type. */
static int obor_legacy_entity_scalar(entity *actor, e_entity_properties property,
                                    ScriptVariant *output, ScriptVariant *input)
{
    #define ENTITY_SCALAR(member, kind, c_type, storage_type, converter, value_field) \
        do { \
            if (input) { \
                c_type value; \
                if (SUCCEEDED(converter(input, &value))) { actor->member = (storage_type)value; } \
            } else { \
                ScriptVariant_ChangeType(output, kind); \
                output->value_field = (c_type)actor->member; \
            } \
            return 1; \
        } while (0)
    #define ENTITY_INT(member) ENTITY_SCALAR(member, VT_INTEGER, LONG, LONG, ScriptVariant_IntegerValue, lVal)
    #define ENTITY_TIMER(member) ENTITY_SCALAR(member, VT_INTEGER, LONG, u32, ScriptVariant_IntegerValue, lVal)
    #define ENTITY_DECIMAL(member) ENTITY_SCALAR(member, VT_DECIMAL, DOUBLE, DOUBLE, ScriptVariant_DecimalValue, dblVal)

    switch (property)
    {
        case ENTITY_PROPERTY_DEATH_STATE:
            if (obor_profile_build < 7488u)
            {
                if (input)
                {
                    LONG value;
                    if (SUCCEEDED(ScriptVariant_IntegerValue(input, &value)))
                    {
                        obor_entity_dead_script_set(actor, value);
                    }
                }
                else
                {
                    ScriptVariant_ChangeType(output, VT_INTEGER);
                    output->lVal = obor_entity_dead_script_get(actor);
                }
                return 1;
            }
            ENTITY_INT(death_state);
        case ENTITY_PROPERTY_SHADOW_CONFIG_FLAGS: ENTITY_INT(shadow_config_flags);
        case ENTITY_PROPERTY_AI_DISABLE: ENTITY_INT(noaicontrol);
        case ENTITY_PROPERTY_ALTERNATE_IDLE: ENTITY_INT(idlemode);
        case ENTITY_PROPERTY_ALTERNATE_WALK: ENTITY_INT(walkmode);
        case ENTITY_PROPERTY_ANIMATION_FRAME: ENTITY_INT(animpos);
        case ENTITY_PROPERTY_ANIMATION_ID: ENTITY_INT(animnum);
        case ENTITY_PROPERTY_ANIMATION_ID_PREVIOUS: ENTITY_INT(animnum_previous);
        case ENTITY_PROPERTY_ANIMATION_STATE: ENTITY_INT(animating);
        case ENTITY_PROPERTY_ANIMATION_TIME: ENTITY_TIMER(nextanim);
        case ENTITY_PROPERTY_ARROW_STATE: ENTITY_INT(arrowon);
        case ENTITY_PROPERTY_ATTACK_ID_OUTGOING: ENTITY_INT(attack_id_outgoing);
        case ENTITY_PROPERTY_ATTACK_STATE: ENTITY_INT(attacking);
        case ENTITY_PROPERTY_AUTOKILL: ENTITY_INT(autokill);
        case ENTITY_PROPERTY_BACK_HIT_DIRECTION: ENTITY_INT(normaldamageflipdir);
        case ENTITY_PROPERTY_BLAST_STATE: ENTITY_INT(projectile);
        case ENTITY_PROPERTY_BLINK: ENTITY_INT(blink);
        case ENTITY_PROPERTY_BLOCK_STATE: ENTITY_INT(blocking);
        case ENTITY_PROPERTY_BOSS: ENTITY_INT(boss);
        case ENTITY_PROPERTY_CHARGE_STATE: ENTITY_INT(charging);
        case ENTITY_PROPERTY_COLORSET_DEFAULT: ENTITY_INT(map);
        case ENTITY_PROPERTY_COLORSET_DYING_HEALTH_1: ENTITY_INT(per1);
        case ENTITY_PROPERTY_COLORSET_DYING_HEALTH_2: ENTITY_INT(per2);
        case ENTITY_PROPERTY_COLORSET_DYING_INDEX_1: ENTITY_INT(dying);
        case ENTITY_PROPERTY_COLORSET_DYING_INDEX_2: ENTITY_INT(dying2);
        case ENTITY_PROPERTY_COLORSET_TIME: ENTITY_TIMER(maptime);
        case ENTITY_PROPERTY_COMBO_TIME: ENTITY_TIMER(combotime);
        case ENTITY_PROPERTY_COMMAND_TIME: ENTITY_TIMER(movetime);
        case ENTITY_PROPERTY_DESTINATION_X: ENTITY_DECIMAL(destx);
        case ENTITY_PROPERTY_DESTINATION_Z: ENTITY_DECIMAL(destz);
        case ENTITY_PROPERTY_DIE_ON_LANDING: ENTITY_INT(die_on_landing);
        case ENTITY_PROPERTY_DROP: ENTITY_INT(drop);
        case ENTITY_PROPERTY_DUCK_STATE: ENTITY_INT(ducking);
        case ENTITY_PROPERTY_ESCAPE_COUNT: ENTITY_INT(escapecount);
        case ENTITY_PROPERTY_EXISTS: ENTITY_INT(exists);
        case ENTITY_PROPERTY_EXPLODE: ENTITY_INT(toexplode);
        case ENTITY_PROPERTY_FALL_STATE: ENTITY_INT(falling);
        case ENTITY_PROPERTY_FREEZE_STATE: ENTITY_INT(frozen);
        case ENTITY_PROPERTY_FREEZE_TIME: ENTITY_TIMER(freezetime);
        case ENTITY_PROPERTY_GET_STATE: ENTITY_INT(getting);
        case ENTITY_PROPERTY_GRAB_WALK_STATE: ENTITY_INT(grabwalking);
        case ENTITY_PROPERTY_GUARD_TIME: ENTITY_TIMER(guardtime);
        case ENTITY_PROPERTY_HP: ENTITY_INT(energy_state.health_current);
        case ENTITY_PROPERTY_HP_OLD: ENTITY_INT(energy_state.health_old);
        case ENTITY_PROPERTY_IDLE_STATE: ENTITY_INT(idling);
        case ENTITY_PROPERTY_IN_PAIN: ENTITY_INT(inpain);
        case ENTITY_PROPERTY_IN_PAIN_BACK: ENTITY_INT(inbackpain);
        case ENTITY_PROPERTY_INVINCIBLE_STATE: ENTITY_INT(invincible);
        case ENTITY_PROPERTY_INVINCIBLE_TIME: ENTITY_TIMER(invinctime);
        case ENTITY_PROPERTY_JUMP_ANIMATION_ID: ENTITY_INT(jump.animation_id);
        case ENTITY_PROPERTY_JUMP_STATE: ENTITY_INT(jumping);
        case ENTITY_PROPERTY_JUMP_VELOCITY_X: ENTITY_DECIMAL(jump.velocity.x);
        case ENTITY_PROPERTY_JUMP_VELOCITY_Y: ENTITY_DECIMAL(jump.velocity.y);
        case ENTITY_PROPERTY_JUMP_VELOCITY_Z: ENTITY_DECIMAL(jump.velocity.z);
        case ENTITY_PROPERTY_KNOCKDOWN_COUNT: ENTITY_INT(knockdowncount);
        case ENTITY_PROPERTY_KNOCKDOWN_TIME: ENTITY_TIMER(knockdowntime);
        case ENTITY_PROPERTY_LAST_DAMAGE_TYPE: ENTITY_INT(last_damage_type);
        case ENTITY_PROPERTY_LIFESPAN: ENTITY_INT(lifespancountdown);
        case ENTITY_PROPERTY_MOVE_TIME: ENTITY_TIMER(nextmove);
        case ENTITY_PROPERTY_MOVE_X: ENTITY_DECIMAL(movex);
        case ENTITY_PROPERTY_MOVE_Z: ENTITY_DECIMAL(movez);
        case ENTITY_PROPERTY_MP: ENTITY_INT(energy_state.mp_current);
        case ENTITY_PROPERTY_MP_CHARGE_TIME: ENTITY_TIMER(mpchargetime);
        case ENTITY_PROPERTY_MP_OLD: ENTITY_INT(energy_state.mp_old);
        case ENTITY_PROPERTY_MP_TIME: ENTITY_TIMER(magictime);
        case ENTITY_PROPERTY_NEXT_ATTACK_TIME: ENTITY_TIMER(nextattack);
        case ENTITY_PROPERTY_NEXT_HIT_TIME: ENTITY_TIMER(next_hit_time);
        case ENTITY_PROPERTY_NOGRAB: ENTITY_INT(nograb);
        case ENTITY_PROPERTY_NOGRAB_DEFAULT: ENTITY_INT(nograb_default);
        case ENTITY_PROPERTY_OBSTRUCTED: ENTITY_INT(hitwall);
        case ENTITY_PROPERTY_PATH_OBSTRUCTED_WAIT: ENTITY_INT(pathblocked);
        case ENTITY_PROPERTY_PAUSE_TIME: ENTITY_TIMER(pausetime);
        case ENTITY_PROPERTY_PLAYER_INDEX: ENTITY_INT(playerindex);
        case ENTITY_PROPERTY_POSITION_BASE: ENTITY_DECIMAL(base);
        case ENTITY_PROPERTY_POSITION_BASE_ALTERNATE: ENTITY_DECIMAL(altbase);
        case ENTITY_PROPERTY_POSITION_DIRECTION: ENTITY_INT(direction);
        case ENTITY_PROPERTY_POSITION_X: ENTITY_DECIMAL(position.x);
        case ENTITY_PROPERTY_POSITION_Y: ENTITY_DECIMAL(position.y);
        case ENTITY_PROPERTY_POSITION_Z: ENTITY_DECIMAL(position.z);
        case ENTITY_PROPERTY_PROJECTILE_PRIME:
            if (input)
            {
                LONG value;
                if (SUCCEEDED(ScriptVariant_IntegerValue(input, &value)))
                {
                    actor->projectile_prime = (e_projectile_prime)obor_projectile_prime_from_script((uint32_t)value);
                }
            }
            else
            {
                ScriptVariant_ChangeType(output, VT_INTEGER);
                output->lVal = (LONG)obor_projectile_prime_to_script(actor->projectile_prime);
            }
            return 1;
        case ENTITY_PROPERTY_RELEASE_TIME: ENTITY_TIMER(releasetime);
        case ENTITY_PROPERTY_RISE_ATTACK_DELAY: ENTITY_INT(staydown.riseattack);
        case ENTITY_PROPERTY_RISE_ATTACK_TIME: ENTITY_INT(staydown.riseattack_stall);
        case ENTITY_PROPERTY_RISE_DELAY: ENTITY_INT(staydown.rise);
        case ENTITY_PROPERTY_RISE_STATE: ENTITY_INT(rising);
        case ENTITY_PROPERTY_RUN_STATE: ENTITY_INT(running);
        case ENTITY_PROPERTY_SEAL_ENERGY: ENTITY_INT(seal);
        case ENTITY_PROPERTY_SEAL_TIME: ENTITY_TIMER(sealtime);
        case ENTITY_PROPERTY_SLEEP_TIME: ENTITY_TIMER(sleeptime);
        case ENTITY_PROPERTY_SORT_ID: ENTITY_INT(sortid);
        case ENTITY_PROPERTY_SPAWN_TYPE: ENTITY_INT(spawntype);
        case ENTITY_PROPERTY_SPEED_MULTIPLIER: ENTITY_DECIMAL(speedmul);
        case ENTITY_PROPERTY_STALL_TIME: ENTITY_TIMER(stalltime);
        case ENTITY_PROPERTY_THINK_TIME: ENTITY_TIMER(nextthink);
        case ENTITY_PROPERTY_TIMESTAMP: ENTITY_TIMER(timestamp);
        case ENTITY_PROPERTY_TO_COST: ENTITY_INT(tocost);
        case ENTITY_PROPERTY_TOSS_TIME: ENTITY_TIMER(toss_time);
        case ENTITY_PROPERTY_TURN_STATE: ENTITY_INT(turning);
        case ENTITY_PROPERTY_TURN_TIME: ENTITY_TIMER(turntime);
        case ENTITY_PROPERTY_UPDATE_MARK: ENTITY_INT(update_mark);
        case ENTITY_PROPERTY_VELOCITY_X: ENTITY_DECIMAL(velocity.x);
        case ENTITY_PROPERTY_VELOCITY_Y: ENTITY_DECIMAL(velocity.y);
        case ENTITY_PROPERTY_VELOCITY_Z: ENTITY_DECIMAL(velocity.z);
        case ENTITY_PROPERTY_WALK_STATE: ENTITY_INT(walking);
        case ENTITY_PROPERTY_WAYPOINT_COUNT: ENTITY_INT(numwaypoints);
        case ENTITY_PROPERTY_WEAPON_STATE: ENTITY_INT(weapon_state);
        default: return 0;
    }

    #undef ENTITY_DECIMAL
    #undef ENTITY_TIMER
    #undef ENTITY_INT
    #undef ENTITY_SCALAR
}


static void obor_report_legacy_entity_property_usage(int setting, int unsupported)
{
    static const char *const usage[][2] =
    {
        {
            "You must provide a valid handle and property name: openbor_get_entity_property(void handle, char property)\n",
            "You must provide a valid handle, property, and new value: openbor_set_entity_property(void handle, char property, value)\n"
        },
        {
            "You must provide a valid handle and property constant: openbor_get_entity_property(void handle, int property)\n",
            "You must provide a valid handle, property, and new value: openbor_set_entity_property(void handle, int property, value)\n"
        },
        {
            "\nYou must provide a valid pointer and property constant: openbor_get_entity_property(void entity, int property)\n",
            "\nYou must provide a valid pointer, property constant, and new value: openbor_set_entity_property(void entity, int property, value)\n"
        }
    };
    const unsigned int format = obor_profile_build >= 7465u ? 2u : obor_profile_build >= 7445u;
    if (unsupported)
    {
        printf("%s", !setting && obor_profile_build >= 7445u ? "Unknwon property.\n" : "Unsupported property.\n");
    }
    printf("%s", usage[format][setting != 0]);
}

HRESULT openbor_get_entity_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount)
{
	const char* SELF_NAME = "openbor_get_entity_property(void entity, int property)";
	const unsigned int ARG_OBJECT = 0;
	const unsigned int ARG_PROPERTY = 1;

	/*
	* Clear pass by reference argument used to send
	* property data back to calling script.
	*/
	ScriptVariant_Clear(*pretvar);

    mapstrings_entity_property(varlist, paramCount);

	/*
	* Should at least be a pointer to the
	* acting object and a property id.
	*/
	if (paramCount < 2 || varlist[ARG_OBJECT]->vt != VT_PTR
        || varlist[ARG_OBJECT]->ptrVal == NULL || varlist[ARG_PROPERTY]->vt != VT_INTEGER) {
        if (obor_profile_build < 7504u)
        {
            obor_report_legacy_entity_property_usage(0, 0);
        }
        else
        {
    		printf("\n\n Script error: %s. You must provide a valid object pointer and property id.\n\n", SELF_NAME);
        }
        if (obor_profile_build < 7504u)
        {
            *pretvar = NULL;
        }
		return E_FAIL;
	}

	/*
	* Now let's make sure the object type is
	* correct (ex. entity vs. model) so we
	* can shut down gracefully if there's
	* a mismatch.
	*/

	const entity* const acting_object = (const entity* const)varlist[ARG_OBJECT]->ptrVal;

	if (acting_object->object_type != OBJECT_TYPE_ENTITY) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;

	const e_entity_properties property_id = (e_entity_properties)(property_id_param);
	const s_property_access_map property_map = entity_get_property_map(acting_object, property_id);

	/*
	* If property id is in range, we send
	* the property map and return parameter
	* for population, then ext.
	*/

	if (property_id_param >= 0 && property_id_param < obor_profile_entity_property_end()) {
        if (obor_profile_build < 7504u)
        {
            const e_entity_properties native_id = obor_entity_property_native_id(property_id);
            if (obor_legacy_entity_scalar((entity *)acting_object, native_id, *pretvar, NULL))
            {
                return S_OK;
            }
            if (!acting_object->custom_target &&
                (native_id == ENTITY_PROPERTY_AI_TARGET_ENTITY || native_id == ENTITY_PROPERTY_GRAB_TARGET))
            {
                return S_OK;
            }
            if (property_map.field == &acting_object->varlist && !acting_object->varlist)
            {
                return S_OK;
            }
            if (property_map.type == VT_PTR)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                if (property_map.config_flags & PROPERTY_ACCESS_CONFIG_STATIC_POINTER)
                {
                    (*pretvar)->ptrVal = (void *)property_map.field;
                }
                else
                {
                    // Entity members use the engine's packed layout.
                    memcpy(&(*pretvar)->ptrVal, property_map.field, sizeof((*pretvar)->ptrVal));
                }
                return S_OK;
            }
        }
		property_access_get_member(&property_map, *pretvar);
		return S_OK;
	}

	/*
	* Is this a dump request? If not, then
	* the property id is invalid.
	*/

	if (obor_profile_build >= 7504u && property_id_param == PROPERTY_ACCESS_DUMP) {
		property_access_dump_members(entity_get_property_map, obor_profile_entity_property_end(), acting_object);
	}
	else {
        if (obor_profile_build < 7504u)
        {
            obor_report_legacy_entity_property_usage(0, 1);
            *pretvar = NULL;
        }
        else
        {
            printf("\n\nScript error: %s. Unknown property id (%d). \n\n", SELF_NAME, property_id_param);
        }
		return E_FAIL;
	}

	return S_OK;
}


/*
* Caskey, Damon  V.
* 2018-04-03
*
* Mutate a property. Requires
* the object pointer, a property
* id, and new value.
*/
HRESULT openbor_set_entity_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount)
{
	const char* SELF_NAME = "openbor_set_entity_property(void entity, int property, <mixed> value)";
	const unsigned int ARG_OBJECT = 0;
	const unsigned int ARG_PROPERTY = 1;
	const unsigned int ARG_VALUE = 2;
	const unsigned int ARG_MINIMUM = 3;

    mapstrings_entity_property(varlist, paramCount);

	/*
	* Should at least be a pointer to the
	* acting object, a property id, and
	* a new value.
	*/

	if (paramCount < ARG_MINIMUM || varlist[ARG_OBJECT]->vt != VT_PTR
        || varlist[ARG_OBJECT]->ptrVal == NULL || varlist[ARG_PROPERTY]->vt != VT_INTEGER) {
        if (obor_profile_build < 7504u)
        {
            obor_report_legacy_entity_property_usage(1, 0);
        }
        else
        {
    		printf("\n\n Script error: %s. You must provide a valid object pointer, property id, and new value.\n\n", SELF_NAME);
        }
		*pretvar = NULL;
		return E_FAIL;
	}

	/*
	* Now let's make sure the object type is
	* correct (ex. entity vs. model) so we
	* can shut down gracefully if there's
	* a mismatch.
	*/

	const entity* const acting_object = (const entity* const)varlist[ARG_OBJECT]->ptrVal;

	if (acting_object->object_type != OBJECT_TYPE_ENTITY) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;
	const e_entity_properties property_id = (e_entity_properties)(property_id_param);

    if (obor_profile_build < 7504u &&
        (property_id_param < 0 || property_id_param >= obor_profile_entity_property_end())) {
        obor_report_legacy_entity_property_usage(1, 1);
		return E_FAIL;
	}

	/*
	* Get map of property. This is a struct
	* that contains the property variable
	* type, reference to the acting object's
	* appropriate data member, text name,
	* read only, etc.
	*/

	const s_property_access_map property_map = entity_get_property_map(acting_object, property_id);

    if (obor_profile_build < 7504u)
    {
        const e_entity_properties native_id = obor_entity_property_native_id(property_id);
        ScriptVariant *value = varlist[ARG_VALUE];
        if (obor_legacy_entity_scalar((entity *)acting_object, native_id, NULL, value))
        {
            return S_OK;
        }
        if (native_id == ENTITY_PROPERTY_DEFENSE || native_id == ENTITY_PROPERTY_OFFENSE)
        {
            if (value->vt != VT_PTR && value->vt != VT_EMPTY)
            {
                return E_FAIL;
            }
            return obor_entity_set_combat_collection((entity *)acting_object,
                value->vt == VT_PTR ? value->ptrVal : NULL, native_id == ENTITY_PROPERTY_DEFENSE) ? S_OK : E_FAIL;
        }
        if (native_id == ENTITY_PROPERTY_PLATFORM_LAND)
        {
            if (value->vt == VT_PTR || value->vt == VT_EMPTY)
            {
                ((entity *)acting_object)->parent = value->vt == VT_PTR ? value->ptrVal : NULL;
            }
            return S_OK;
        }
        if (native_id == ENTITY_PROPERTY_NAME)
        {
            if (value->vt == VT_STR)
            {
                const char *name = (const char *)StrCache_Get(value->strVal);
                if (name)
                {
                    snprintf(((entity *)acting_object)->name, sizeof(acting_object->name), "%s", name);
                }
            }
            return S_OK;
        }
        if (!(property_map.config_flags & PROPERTY_ACCESS_CONFIG_WRITE))
        {
            return S_OK;
        }
        if (property_map.type == VT_PTR && property_map.field != &acting_object->varlist)
        {
            if (value->vt == VT_PTR || value->vt == VT_EMPTY)
            {
                void *pointer = value->vt == VT_PTR ? value->ptrVal : NULL;
                memcpy((void *)property_map.field, &pointer, sizeof(pointer));
            }
            return S_OK;
        }
    }

	/*
	* Populate the property value on
	* acting object and return OK/FAIL.
	*/

	if(property_map.field == &acting_object->varlist &&
	   (property_map.config_flags & PROPERTY_ACCESS_CONFIG_WRITE))
	{
		obor_entity_varlist_set((entity *)acting_object, varlist[ARG_VALUE]->ptrVal);
		return S_OK;
	}
	return property_access_set_member(acting_object, &property_map, varlist[ARG_VALUE]);

	return S_OK;
}

/*
* Caskey, Damon V.
* 2021-08-04
*
* Return an attack ID array element value.
*/
HRESULT openbor_get_attack_id_value(ScriptVariant** varlist, ScriptVariant** pretvar, int paramCount)
{
#define SELF_NAME       "get_attack_id_value(void handle, int element)"
#define ARG_MINIMUM     2   // Minimum required arguments.
#define ARG_OBJECT      0   // Handle (pointer to property structure).
#define ARG_ELEMENT		1   // Array element to access.

	LONG* handle = NULL; // Property handle.
	int  element = 0;    // Property argument.

	/*
	* Clear pass by reference argument used to send
	* property data back to calling script.
	*/
	ScriptVariant_Clear(*pretvar);

	/*
	* Verify arguments.There should at least
	* be a pointer for the property handle and an integer
	* to determine which element of the array is accessed.
	*/
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_ELEMENT]->vt != VT_INTEGER)
	{
		*pretvar = NULL;
		goto error_local;
	}
	else
	{
		// Populate local vars for readability.
		handle = (LONG*)varlist[ARG_OBJECT]->ptrVal;
		element = (LONG)varlist[ARG_ELEMENT]->lVal;
	}

	/* Don't allow an out of bounds element. */
	if (element < 0 || element > MAX_ATTACK_IDS)
	{
		element = 0;
	}

	ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
	(*pretvar)->lVal = (LONG)handle[element];

	return S_OK;

error_local:

	printf("%sYou must provide a valid handle and element: " SELF_NAME "\n", obor_profile_build >= 7465u ? "\n" : "");
	*pretvar = NULL;

	return E_FAIL;

#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_ELEMENT
}

/*
* Caskey, Damon  V.
* 2018-04-03
*
* Mutate an entity property. Requires
* the entity handle, a string property
* name, and new value.
*/
HRESULT openbor_set_attack_id_value(ScriptVariant** varlist, ScriptVariant** pretvar, int paramCount)
{
#define SELF_NAME           "set_attack_id_value(void handle, char property, value)"
#define ARG_MINIMUM         3   // Minimum required arguments.
#define ARG_OBJECT          0   // Handle (pointer to property structure).
#define ARG_ELEMENT        1	// Element to access.
#define ARG_VALUE           2   // New value to apply.

	int     result = S_OK; // Success or error?
	LONG*	handle = NULL; // Property handle.
	int		element = 0;    // Array element to access.

	/*
	* Value carriers to apply on properties after
	* taken from argument.
	*/
	LONG    temp_int;

	/*
	* Verify incoming arguments. There should at least
	* be a pointer for the property handle and an integer
	* to determine which property is accessed.
	*/
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_ELEMENT]->vt != VT_INTEGER)
	{
		*pretvar = NULL;
		goto error_local;
	}

	// Populate local handle and property vars.
	handle = (LONG*)varlist[ARG_OBJECT]->ptrVal;
	element = (LONG)varlist[ARG_ELEMENT]->lVal;

	/* Don't allow an out of bounds element. */
	if (element < 0 || element > MAX_ATTACK_IDS)
	{
		element = 0;
	}

	if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
	{
		handle[element] = temp_int;
	}

	return result;

	/* Error trapping. */
error_local:

	printf("%sYou must provide a valid handle, element, and new value: " SELF_NAME "\n", obor_profile_build >= 7465u ? "\n" : "");

	result = E_FAIL;
	return result;

#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_OBJECT
#undef ARG_ELEMENT
#undef ARG_VALUE
}
