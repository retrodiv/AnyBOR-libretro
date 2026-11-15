/*
 * OpenBOR - Copyright (c) 2004 - 2013 OpenBOR Team.
 * BSD-3-Clause; retain the OpenBOR license distributed with this source.
 * LNS enhancements credited to Hechelion and Gonzalo MVP.
 * Original: AveyondFly/openbor-fflns
 * cfb4f3a676613714757d4539275482f7c323d6ad, engine/openbor.c.
 * Function names and the provider entity type are renamed for comparison.
 */
#define MAX_ATTACK_IDS 100
typedef struct {
    unsigned int attack_id_incoming[MAX_ATTACK_IDS];
    unsigned int attack_id_incoming_index;
} lns_reference_entity;

void reference_insert_attack_id_incoming(lns_reference_entity *e,  unsigned int attack_id_incoming)
{
    ++e->attack_id_incoming_index;
    if(e->attack_id_incoming_index >= MAX_ATTACK_IDS)
    {
        e->attack_id_incoming_index = 0;
    }
    e->attack_id_incoming[e->attack_id_incoming_index] = attack_id_incoming;
}

int reference_check_attack_id_incoming(lns_reference_entity *e,  unsigned int attack_id_incoming)
{
    int index = e->attack_id_incoming_index;

    for (int i = 0 ; i < MAX_ATTACK_IDS; ++i)
    {
        if(e->attack_id_incoming[index] == attack_id_incoming)
        {
            return 1;
        }
        else if(e->attack_id_incoming[index] == 0)
        {
            break;
        }
        --index;
        if(index < 0)
        {
            index = MAX_ATTACK_IDS - 1;
        }
    }

    return 0;
}
