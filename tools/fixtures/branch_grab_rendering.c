/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */

#include "openbor.h"
#include <assert.h>
#include <limits.h>

uint32_t obor_profile_build;
static int min_y, max_y;

int testmove(entity *subject, float old_x, float old_z, float x, float z)
{
    assert(old_x == subject->position.x && old_z == subject->position.z);
    assert(x >= 0 && z >= 0);
    return 1;
}

void draw_box_on_entity(entity *subject, int left, int top, int z, int right,
                        int bottom, int offset, int color, s_drawmethod *drawmethod)
{
    assert(left == 2 && right == 9 && z == subject->position.z + 1);
    assert(offset == -1 && color == 0xff00 && drawmethod);
    min_y = top;
    max_y = bottom;
}

@METHODS@

static int draw_order(entity *e)
{
    int sortid = e->sortid;
    int z;
    @ORDER@
    assert(z == e->position.z);
    return sortid;
}

static void draw_range(entity *subject)
{
    entity *entity = subject;
    s_drawmethod drawmethod = {0};
    const int LOCAL_COLOR_GREEN = 0xff00;
    @RANGE@
}

int main(void)
{
    const unsigned profiles[] = {6997, 7039, 7086, 7091, 7123, 7142};
    for(size_t p = 0; p < sizeof(profiles) / sizeof(profiles[0]); ++p)
    {
        obor_profile_build = profiles[p];
        const int early = profiles[p] == 6997 || profiles[p] == 7039;
        for(int back = 0; back <= 1; ++back)
        {
            entity actor = {0}, target = {0};
            actor.position.x = 10;
            target.position.x = 25;
            actor.sortid = 70;
            target.sortid = 100;
            actor.modeldata.grabback = back;
            actor.grabbing = &target;
            actor.link = &target;
            assert(adjust_grabposition(&actor, &target, 10, 1));
            assert(actor.position.x == 10 && target.position.x == 20);
            assert(target.sortid == (early ? 100 : back ? 71 : 69));
            assert(draw_order(&actor) == (early ? back ? 99 : 101 : 70));
            actor.link = NULL;
            assert(draw_order(&actor) == 70);
        }

        s_anim animation = {0};
        entity actor = {0};
        animation.range.x.min = 2;
        animation.range.x.max = 9;
        animation.range.y.min = 3;
        animation.range.y.max = 12;
        actor.position.z = 20;
        actor.animation = &animation;
        draw_range(&actor);
        assert(min_y == (early ? 3 : -12));
        assert(max_y == (early ? 12 : -3));
    }
}
