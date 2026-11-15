/* OpenBOR - Copyright (c) 2004 - 2013 OpenBOR Team.
 * BSD-3-Clause; retain the distributed OpenBOR licence.
 * LNS enhancements: Hechelion and Gonzalo MVP.
 * Own source cfb4f3a676613714757d4539275482f7c323d6ad, engine/openbor.c. */
int lns_original_projectile_wall_collision(entity *ent)
{
    int blocking_wall;
    entity *blocking_obstacle = NULL;
    s_collision_attack *attack = NULL;
    int attack_min_y = 0;
    int attack_max_y = 0;
    int hit_pos_x = 0;
    int hit_pos_y = 0;
    int hit_pos_z = 0;
    bool use_attack_anim = true;

    // skip if the projectile is forced to ignore wall collisions
    if(ent->modeldata.ignore_projectile_wall_collision || ent->hitwall)
    {
       return 0; 
    }

    // skip if there is no attack collider enabled
    if(ent->animation &&
        ent->animation->collision_attack &&
        ent->animation->collision_attack[ent->animpos] &&
        ent->animation->collision_attack[ent->animpos]->instance)
    {
        attack = ent->animation->collision_attack[ent->animpos]->instance[0];
    }
    else
    {
        return 0;
    }

    // Calculate attack collider min and max height positions
    attack_min_y = ent->position.y - attack->coords->height;
    attack_max_y = ent->position.y - attack->coords->y;

    blocking_wall = check_block_wall(self);
    if(blocking_wall >= 0)
    {
        // Check wall height
        if(attack_min_y > level->walls[blocking_wall].height)
        {
            blocking_wall = -1;
        }

         // Some walls should be ignored
        if(blocking_wall >= 0 && level->walls[blocking_wall].ignore_projectile_wall_collision)
        {
            blocking_wall = -1;
        }
    }

    if(blocking_wall < 0)
    {
        blocking_obstacle = check_block_obstacle(self);

        if(blocking_obstacle)
        {
            // Check obstacle height
            if(attack_max_y < blocking_obstacle->position.y ||
            attack_min_y > blocking_obstacle->position.y + blocking_obstacle->animation->platform[blocking_obstacle->animpos][PLATFORM_HEIGHT])
            {
                blocking_obstacle = NULL;
            }

            // Some obstacles should be ignored
            if(blocking_obstacle &&
            (blocking_obstacle->modeldata.ignore_projectile_wall_collision || blocking_obstacle->modeldata.type == TYPE_OBSTACLE))
            {
                blocking_obstacle = NULL;
            }
        }        
    }

    if(blocking_wall >= 0 || blocking_obstacle)
    {
        // disable next wall collision checks for this entity
        ent->hitwall = 1;

        // The following code is copying the projectile behavior when its attack hits a target

        if(ent->pausetime < _time || (inair(ent) && !equalairpause))        // if equalairpause is set, inair(e) is nolonger a condition for extra pausetime
        {
            // Adds pause to the current animation
            ent->toss_time += attack->pause_add;      // So jump height pauses in midair
            ent->nextmove += attack->pause_add;      // xdir, zdir
            ent->nextanim += attack->pause_add;       //Pause animation for a bit
            ent->nextthink += attack->pause_add;      // So anything that auto moves will pause
            ent->pausetime = _time + attack->pause_add ; //UT: temporary solution
        }

        // farthest attack collider margin
        if(ent->direction == DIRECTION_LEFT)
        {
            hit_pos_x = ent->position.x - attack->coords->width;
        }
        else
        {
            hit_pos_x = ent->position.x + attack->coords->width;
        }
        hit_pos_y = (attack_min_y + attack_max_y) * 0.5; // middle attack collider height
        hit_pos_y = hit_pos_y - 17; // sprite offset adjustment
        hit_pos_z =  ent->position.z + 1; // changed so flashes always spawn in front

        entity *flash = spawn(hit_pos_x, hit_pos_z, hit_pos_y, 0, NULL, 2, NULL);
        if(flash)
        {
            flash->spawntype = SPAWN_TYPE_FLASH;
            execute_onspawn_script(flash);
            if(flash->modeldata.toflip)
            {
                flash->direction = (ent->direction == DIRECTION_LEFT);    // Now the flash will flip depending on which side the attacker is on
            }
            flash->base = hit_pos_y;
            flash->autokill = 2;
        }

        // projectiles with a followup animation
        if(ent->animation->followup.animation)
        {
            int current_follow_id = animfollows[ent->animation->followup.animation - 1];
            if(validanim(ent, current_follow_id))
            {
                if(!ent->modeldata.animation[current_follow_id]->attackone)
                {
                    ent->modeldata.animation[current_follow_id]->attackone = ent->animation->attackone;
                }
                ent_set_anim(ent, current_follow_id, 1);          // Then go to it!
                use_attack_anim = false; // if there is a folloup anim we don't need to use the attack anim
            }
        }
        // bombs
        if(ent->toexplode == 1)
        {
            ent->toexplode = 2;    // Used so the bomb type entity explodes when hitting
            use_attack_anim = false; // attack anim will be set during bomb_move
        }

        if(use_attack_anim)
        {
            if(validanim(ent, ANI_ATTACK2))
            {
                ent_set_anim(ent, ANI_ATTACK2, 0);
            }
            else if (validanim(ent, ANI_ATTACK1))
            {
                ent_set_anim(ent, ANI_ATTACK1, 0);
            }
        }

        // play a block sound
        sound_play_sample(SAMPLE_BLOCK, 0, savedata.effectvol, savedata.effectvol, 100);
        
        // if the projectile is configured to be removed on attack, kill it immediately
        if(ent->remove_on_attack)
        {
            kill_entity(ent);
        }
        
        return 1;
    }
    
    // Did not collide, so return false.
    return 0;
}
