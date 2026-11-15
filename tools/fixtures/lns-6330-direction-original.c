/* OpenBOR: Copyright (c) 2004 - 2013 OpenBOR Team.
 * BSD-3-Clause; retain the OpenBOR license distributed with this source.
 * LNS enhancements credited to Hechelion and Gonzalo MVP.
 * LNS: AveyondFly/openbor-fflns, cfb4f3a676613714757d4539275482f7c323d6ad.
 * Official: DCurrent/openbor, 4b1705fa37457ab38bc5d0fcc561242019588e32.
 * Both complete checkdamageflip functions; only their names and the self
 * binding are changed for comparison. Provider records are declared by the test.
 */
#define self reference_self
void reference_lns_checkdamageflip(entity *other, s_collision_attack *attack)
{
    e_direction_adjust force_direction = DIRECTION_ADJUST_NONE;
    self->normaldamageflipdir = -1;

    if(other && attack)
    {
        force_direction =  attack->force_direction;

        // if override is set use next value instead of the attack value
        if(other->override_next_force_direction > 0)
        {
            force_direction = other->next_force_direction;

            // disable override if it was set to only override once
            if(other->override_next_force_direction == 1)
            {
                other->override_next_force_direction = 0;
            }
        }

        // save used force_direction for next time
        other->next_force_direction = force_direction;
    }

    if(other == NULL || other == self || (!self->drop && (attack->no_pain || self->modeldata.nopain || (self->defense[attack->attack_type].pain && attack->attack_force < self->defense[attack->attack_type].pain))))
    {
        return;
    }

    if(!self->frozen && !self->modeldata.noflip)// && !inair(self))
    {
        switch(force_direction)
        {
            case DIRECTION_ADJUST_NONE:
                if( !self->inbackpain )
                {
                    if(self->position.x < other->position.x)
                    {
                        self->direction = DIRECTION_RIGHT;
                    }
                    else if(self->position.x > other->position.x)
                    {
                        self->direction = DIRECTION_LEFT;
                    }
                }
                else
                {
                    if(self->position.x < other->position.x)
                    {
                        self->normaldamageflipdir = DIRECTION_RIGHT;
                    }
                    else if(self->position.x > other->position.x)
                    {
                        self->normaldamageflipdir = DIRECTION_LEFT;
                    }
                }
                break;

            case DIRECTION_ADJUST_SAME:

                self->direction = other->direction;
                break;

            case DIRECTION_ADJUST_OPPOSITE:

                self->direction = !other->direction;
                break;

            case DIRECTION_ADJUST_RIGHT:

                self->direction = DIRECTION_RIGHT;
                break;

            case DIRECTION_ADJUST_LEFT:

                self->direction = DIRECTION_LEFT;
                break;
        }
    }
}

void reference_official_checkdamageflip(entity *other, s_collision_attack *attack)
{
    self->normaldamageflipdir = -1;

    if(other == NULL || other == self || (!self->drop && (attack->no_pain || self->modeldata.nopain || (self->defense[attack->attack_type].pain && attack->attack_force < self->defense[attack->attack_type].pain))))
    {
        return;
    }

    if(!self->frozen && !self->modeldata.noflip)// && !inair(self))
    {
        switch(attack->force_direction)
        {
            case DIRECTION_ADJUST_NONE:
                if( !self->inbackpain )
                {
                    if(self->position.x < other->position.x)
                    {
                        self->direction = DIRECTION_RIGHT;
                    }
                    else if(self->position.x > other->position.x)
                    {
                        self->direction = DIRECTION_LEFT;
                    }
                }
                else
                {
                    if(self->position.x < other->position.x)
                    {
                        self->normaldamageflipdir = DIRECTION_RIGHT;
                    }
                    else if(self->position.x > other->position.x)
                    {
                        self->normaldamageflipdir = DIRECTION_LEFT;
                    }
                }
                break;

            case DIRECTION_ADJUST_SAME:

                self->direction = other->direction;
                break;

            case DIRECTION_ADJUST_OPPOSITE:

                self->direction = !other->direction;
                break;

            case DIRECTION_ADJUST_RIGHT:

                self->direction = DIRECTION_RIGHT;
                break;

            case DIRECTION_ADJUST_LEFT:

                self->direction = DIRECTION_LEFT;
                break;
        }
    }
}
#undef self
