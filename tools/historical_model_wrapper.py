"""Native model-change wrapper and linked switch decision contract.

Native records and both complete functions are retained. Script operations are
data-only callback observations; this is not VM, ownership or gameplay evidence.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_model_switch import render_model_switch


def render_model_wrapper(parts, *, contract, wrapper_contract, revision,
                         native_capacity, scripts_pointer, factor_layout,
                         function_arity=None, unused_graphics_inlines=False,
                         unused_inline_declarations=None, helpers=''):
    if (not isinstance(parts,dict) or set(parts)!={'model_switch','wrapper','reserve'} or
            any(not isinstance(v,str) or len(v)>65536 or (k!='reserve' and not v.strip())
                for k,v in parts.items())):
        raise ValueError('Bounded complete model switch, wrapper and optional native reserve required')
    keys={'legacy_routes','copy_entity_factors','copy_weapon_count','modelcopy_hooks','tracks_platforms'}
    if (not isinstance(wrapper_contract,dict) or set(wrapper_contract)!=keys or
            any(type(v) is not bool for v in wrapper_contract.values())):
        raise ValueError('Explicit source-defined wrapper contract required')
    if type(scripts_pointer) is not bool or factor_layout not in ('parallel','record'):
        raise ValueError('Explicit native scripts and factor representation required')
    if (native_capacity and not parts['reserve'].strip()) or (
            factor_layout=='parallel' and wrapper_contract['copy_entity_factors']):
        raise ValueError('Native reserve and factor representation must match the contract')
    base=render_model_switch(parts['model_switch'],contract=contract,revision=revision,
        native_capacity=native_capacity,function_arity=function_arity,
        unused_graphics_inlines=unused_graphics_inlines,
        unused_inline_declarations=unused_inline_declarations,helpers=helpers)
    marker='static unsigned cases;'
    insertion='#define ent_set_model model_switch_under_test\n'
    if base.count(marker)!=1 or base.count(insertion)!=1:
        raise ValueError('One authored model fixture entry required')
    prefix=base.split(marker)[0]
    # Inherited animation entries can have different identities from authored
    # destination entries; retain the selected table's actual native pointer.
    prefix=prefix.replace('assert(ent->animation==&custom_anim);',
        'assert(ent->animation==new_model.animation[ent->animnum]);')
    setup=r'''
enum {FACTOR_COUNT=16,LEGACY_ROUTES=@LEGACY_ROUTES@,
 COPY_FACTORS=@COPY_ENTITY_FACTORS@,COPY_WEAPON_COUNT=@COPY_WEAPON_COUNT@,
 MODEL_COPY_HOOKS=@MODELCOPY_HOOKS@};
static int fixture_max_animations=MAX_ANIS+32,fixture_max_attack_types=FACTOR_COUNT;
static struct {s_model *model;} fixture_model_cache[1];
static s_scripts source_scripts,destination_scripts;
static s_anim inherited_anim;
static unsigned script_queries,script_copies,script_clears;
static float source_offense[FACTOR_COUNT],destination_offense[FACTOR_COUNT],
             prior_offense[FACTOR_COUNT];
@FACTOR_DECLARATIONS@
static void observed_clear_scripts(void *scripts,int mode) {
 assert(scripts==@SCRIPT_DESTINATION@ && mode==0);++script_clears;event(8);
}
static void observed_copy_scripts(void *from,void *to,int mode) {
 assert(from==@SCRIPT_SOURCE@ && to==@SCRIPT_DESTINATION@ && mode==0);
 assert(subject.modeldata.type==old_model.type);++script_copies;event(9);
 *(s_scripts*)to=*(s_scripts*)from;
}
static int observed_script_initialized(void *script) {
 (void)script;++script_queries;return 0;
}
static void refused_modelcopy_callback(entity *ent,entity *previous) {
 (void)ent;(void)previous;fputs("Unexpected active script in quiet wrapper contract\n",stderr);abort();
}
#undef max_animations
#undef max_attack_types
#undef model_cache
#define max_animations fixture_max_animations
#define max_attack_types fixture_max_attack_types
#define model_cache fixture_model_cache
#define clear_all_scripts observed_clear_scripts
#define copy_all_scripts observed_copy_scripts
#define Script_IsInitialized observed_script_initialized
#define execute_onmodelcopy_script refused_modelcopy_callback
#undef realloc
@RESERVE@
'''
    suffix=r'''
#define ent_set_model model_switch_under_test
#define set_model_ex model_wrapper_under_test
@WRAPPER@
#undef set_model_ex
#undef ent_set_model
static unsigned cases;
static void wrapper_case(unsigned mask,int route,int flag,int slot,int position) {
 memset(&old_model,0,sizeof(old_model));memset(&new_model,0,sizeof(new_model));
 memset(&subject,0,sizeof(subject));memset(old_table,0,sizeof(old_table));
 memset(&source_scripts,0,sizeof(source_scripts));memset(&destination_scripts,0,sizeof(destination_scripts));
 memset(prior_offense,0,sizeof(prior_offense));
 new_table=calloc(MAX_ANIS+32,sizeof(*new_table));assert(new_table);
 const int custom_id=MAX_ANIS+7;
 custom_anim.numframes=inherited_anim.numframes=3;spawn_anim.numframes=idle_anim.numframes=3;
 old_table[custom_id]=&inherited_anim;
 new_table[ANI_IDLE]=&idle_anim;new_table[ANI_SPAWN]=&spawn_anim;
 if(slot)new_table[custom_id]=&custom_anim;
 old_model.animation=old_table;new_model.animation=new_table;
 @NATIVE_CAPACITY@
 old_model.name="previous";new_model.name="next";
 old_model.type=TYPE_PLAYER;new_model.type=TYPE_ENEMY;
 new_model.model_flag=((mask&1)?MODEL_NO_COPY:0)|((mask&2)?MODEL_NO_WEAPON_COPY:0)|
                      ((mask&4)?MODEL_NO_SCRIPT_COPY:0);
 __typeof__(*new_model.weapon) old_weapons[2],new_weapons[3];
 memset(old_weapons,0,sizeof(old_weapons));memset(new_weapons,0,sizeof(new_weapons));
 old_model.weapon=old_weapons;old_model.weapnum=1;old_model.numweapons=2;
 new_model.weapon=(mask&8)?new_weapons:NULL;new_model.weapnum=2;new_model.numweapons=3;
 old_model.speed=2;old_model.runspeed=3;old_model.runjumpheight=4;old_model.runjumpdist=5;
 old_model.runupdown=1;old_model.runhold=1;
 new_model.speed=(mask&16)?0:7;new_model.runspeed=(mask&16)?0:7;
 new_model.runjumpheight=(mask&16)?0:7;new_model.runjumpdist=(mask&16)?0:7;
 new_model.runupdown=(mask&16)?0:1;new_model.runhold=(mask&16)?0:1;
 @HISTORICAL_DEFAULTS@
 @SCRIPT_SETUP@
 @FACTOR_SETUP@
 for(unsigned i=0;i<FACTOR_COUNT;++i) {
  prior_offense[i]=0.5f;source_offense[i]=2;destination_offense[i]=0.25f;
 }
 old_model.offense_factors=prior_offense;new_model.offense_factors=source_offense;
 subject.model=&old_model;subject.modeldata=old_model;subject.offense_factors=destination_offense;
 @ENTITY_FACTOR_SETUP@
 @ENTITY_SCRIPT_SETUP@
 subject.animation=&inherited_anim;subject.animnum=custom_id;subject.animpos=position;
 subject.attacking=1;subject.map=17;subject.nextanim=501;
 @PLATFORM_FLAGS@
 fixture_clock=100;fixture_select=fixture_screen=0;fixture_platforms=10;
 fixture_model_cache[0].model=&new_model;event_count=0;
 selected_animation=update_position=delay_position=-99;
 script_queries=script_copies=script_clears=0;
 unsigned char before[sizeof(subject)];memcpy(before,&subject,sizeof(subject));
 model_wrapper_under_test(&subject,"previous",-1,&old_model,flag);
 assert(!memcmp(before,&subject,sizeof(subject)) && event_count==0);
 model_wrapper_under_test(&subject,"next",route==1?0:-1,route==0?&new_model:NULL,flag);
 assert(subject.model==&new_model && subject.modeldata.type==old_model.type);
 assert(subject.modeldata.animation==new_model.animation);
 int copied=!(mask&1),effective_slot=slot||copied;
 assert(new_model.animation[custom_id]==(slot?&custom_anim:copied?&inherited_anim:NULL));
 assert(fixture_platforms==10+TRACKS_PLATFORMS);
 int helper=LEGACY_ROUTES?flag:1;
 unsigned at=0;
 if(route==2)assert(events[at++]==1);
 if(helper)assert(events[at++]==1);
 assert(events[at++]==2);
 if(helper)assert(events[at++]==3);
 int sync=!LEGACY_ROUTES && flag && effective_slot;
 if(sync) {
  assert(subject.animation==new_model.animation[custom_id] && subject.attacking==1);
  if(EFFECT==2)assert(events[at++]==5 && update_position==position);
  else if(EFFECT>=3) {
   assert(events[at++]==6 && delay_position==(position>=3?2:position));
   assert(subject.nextanim==117 && subject.animpos==(__typeof__(+subject.animpos))(position>=3?2:position));
  }
 } else if(helper) {
  assert(events[at++]==4 && selected_animation==ANI_SPAWN && subject.attacking==0);
 } else assert(subject.attacking==1 && subject.animation==new_model.animation[custom_id]);
 if(mask&4)assert(events[at++]==8);
 assert(events[at++]==9 && events[at++]==3 && at==event_count);
 assert(script_copies==1 && script_clears==!!(mask&4));
 if(script_queries!=(MODEL_COPY_HOOKS?2u:0u)) {
  fputs("Unexpected model wrapper callback queries\n",stderr);abort();
 }
 if(memcmp(destination_offense,COPY_FACTORS?source_offense:expected_offense,sizeof(destination_offense))) {
  fputs("Unexpected model wrapper offense values\n",stderr);abort();
 }
 @FACTOR_CHECK@
 assert(new_model.speed==((copied&&(mask&16))?2:((mask&16)?0:7)));
 assert(new_model.runspeed==((copied&&(mask&16))?3:((mask&16)?0:7)));
 if(copied && !(mask&2)) {
  assert(new_model.weapnum==1);
  assert(new_model.weapon==((mask&8)?new_weapons:old_weapons));
  assert(new_model.numweapons==((COPY_WEAPON_COUNT && !(mask&8))?2:3));
 } else assert(new_model.weapnum==2 && new_model.weapon==((mask&8)?new_weapons:NULL));
 @DEFAULT_CHECKS@
 free(new_model.animation);new_table=NULL;++cases;
}
int main(void) {
 assert(MAX_ANIS>0 && MAX_ANIS<4096);
 for(unsigned mask=0;mask<32;++mask)for(int route=0;route<3;++route)
 for(int flag=0;flag<2;++flag)for(int slot=0;slot<2;++slot)
 for(int position=1;position<=7;position+=6) {
  int effective_slot=slot||!(mask&1);
  if(!effective_slot && ((LEGACY_ROUTES && !flag)||(!LEGACY_ROUTES && flag && !CHECKS_SLOT)))continue;
  wrapper_case(mask,route,flag,slot,position);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''
    fields=('factor','pain','knockdown','blockpower','blockthreshold','blockratio','blocktype')
    native_fields=('defense_factors','defense_pain','defense_knockdown','defense_blockpower',
                   'defense_blockthreshold','defense_blockratio','defense_blocktype')
    defaults=('icon.def','icon.pain','icon.get','icon.die','shadow','knife','pshotno','bomb',
              'star','flash','bflash','dust[0]','dust[1]','diesound')
    flags={k.upper():str(int(v)) for k,v in wrapper_contract.items()}
    if factor_layout=='parallel':
        declarations='static float prior_defense[7][FACTOR_COUNT],source_defense[7][FACTOR_COUNT],destination_defense[7][FACTOR_COUNT],expected_defense[7][FACTOR_COUNT];'
        setup_factors='for(unsigned f=0;f<7;++f)for(unsigned i=0;i<FACTOR_COUNT;++i) {prior_defense[f][i]=0.5f;source_defense[f][i]=2;destination_defense[f][i]=expected_defense[f][i]=0.25f;}\n'
        setup_factors+='\n'.join('old_model.%s=prior_defense[%d];new_model.%s=source_defense[%d];'%(field,n,field,n) for n,field in enumerate(native_fields))
        entity_factors='\n'.join('subject.%s=destination_defense[%d];'%(field,n) for n,field in enumerate(native_fields))
    else:
        declarations='static s_defense prior_defense[FACTOR_COUNT],source_defense[FACTOR_COUNT],destination_defense[FACTOR_COUNT],expected_defense[FACTOR_COUNT];'
        setup_factors='memset(prior_defense,0,sizeof(prior_defense));memset(source_defense,0,sizeof(source_defense));memset(destination_defense,0,sizeof(destination_defense));\n'
        setup_factors+='for(unsigned i=0;i<FACTOR_COUNT;++i) {'+'\n'.join('prior_defense[i].%s=0;source_defense[i].%s=2;destination_defense[i].%s=1;'%(f,f,f) for f in fields)+'}\nmemcpy(expected_defense,destination_defense,sizeof(destination_defense));\nold_model.defense=prior_defense;new_model.defense=source_defense;'
        entity_factors='subject.defense=destination_defense;'
    values=flags|dict(WRAPPER=parts['wrapper'],RESERVE=parts['reserve'],
        FACTOR_DECLARATIONS=declarations+'\nstatic float expected_offense[FACTOR_COUNT];',
        FACTOR_SETUP=setup_factors,ENTITY_FACTOR_SETUP=entity_factors,
        FACTOR_CHECK='if(memcmp(destination_defense,COPY_FACTORS?source_defense:expected_defense,sizeof(destination_defense))) {fputs("Unexpected model wrapper defense values\\n",stderr);abort();}',
        SCRIPT_SOURCE='new_model.scripts' if scripts_pointer else '&new_model.scripts',
        SCRIPT_DESTINATION='subject.scripts' if scripts_pointer else '&subject.scripts',
        SCRIPT_SETUP='old_model.scripts=&destination_scripts;new_model.scripts=&source_scripts;' if scripts_pointer else 'old_model.scripts=destination_scripts;new_model.scripts=source_scripts;',
        ENTITY_SCRIPT_SETUP='subject.scripts=&destination_scripts;' if scripts_pointer else 'subject.scripts=destination_scripts;',
        NATIVE_CAPACITY='old_model.animation_capacity=new_model.animation_capacity=MAX_ANIS+32;' if native_capacity else '',
        PLATFORM_FLAGS='old_model.hasPlatforms=0;new_model.hasPlatforms=1;' if wrapper_contract['tracks_platforms'] else '',
        HISTORICAL_DEFAULTS='\n'.join('old_model.%s=7;new_model.%s=(mask&16)?-1:3;'%(field,field) for field in defaults),
        DEFAULT_CHECKS='\n'.join('assert(new_model.%s==((copied&&(mask&16))?7:((mask&16)?-1:3)));'%field for field in defaults))
    # Record the independent entity offense baseline before the real wrapper.
    suffix=suffix.replace('old_model.offense_factors=prior_offense;',
        'memcpy(expected_offense,destination_offense,sizeof(destination_offense));\n old_model.offense_factors=prior_offense;')
    for key,value in values.items():
        setup=setup.replace('@'+key+'@',value);suffix=suffix.replace('@'+key+'@',value)
    return prefix.replace(insertion,setup+'\n'+insertion)+suffix
