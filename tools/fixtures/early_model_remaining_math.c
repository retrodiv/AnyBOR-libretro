/* Original field and command controls: OpenBOR Team, 2011.
 * Source identities are recorded in profile-early-model-remaining.json.
 * OpenBOR License (No Sale): see LICENSES/OpenBOR-3400.txt.
 * Wrapper contributions: Copyright (c) 2026 retrodiv <retrodiv@proton.me>,
 * BSD-3-Clause. Original command bodies are unchanged.
 */
typedef struct
{
	unsigned char* table;
	void* fp;
	unsigned fillcolor;
	int flag:1;
	int alpha:8;
	int remap:8;
	int flipx:1;
	int flipy:1;
	int transbg:1;
	int fliprotate:1; // entity only, whether the flip is affected by the entity's facing(not the sprite's flip )
	int rotate:11; // 360 degrees
	int scalex;
	int scaley;
	int shiftx;
	int centerx;   // shift centerx
	int centery;   //shift centery
}reference_drawmethod;
static reference_drawmethod reference_draw_0(ArgList arglist,int blendfx_is_set){
reference_drawmethod drawmethod={0};char *filename="fixture.txt",*command="drawmethod";
switch(CMD_MODEL_DRAWMETHOD){
				case CMD_MODEL_DRAWMETHOD:
					// special effects
					drawmethod.scalex = GET_INT_ARG(1);
					drawmethod.scaley = GET_INT_ARG(2);
					drawmethod.flipx = GET_INT_ARG(3);
					drawmethod.flipy = GET_INT_ARG(4);
					drawmethod.shiftx = GET_INT_ARG(5);
					drawmethod.alpha = GET_INT_ARG(6);
					if(!blendfx_is_set)
					{
						if(drawmethod.alpha>0 && drawmethod.alpha<=MAX_BLENDINGS)
						{
							blendfx[drawmethod.alpha-1] = 1;
						}
					}
					drawmethod.remap = GET_INT_ARG(7);
					drawmethod.fillcolor = parsecolor(GET_ARG(8));
					drawmethod.rotate = GET_INT_ARG(9);
					drawmethod.fliprotate = GET_INT_ARG(10)%360;
					if(drawmethod.scalex<0) {drawmethod.scalex = -drawmethod.scalex;drawmethod.flipx = !drawmethod.flipx;}
					if(drawmethod.scaley<0) {drawmethod.scaley = - drawmethod.scaley;drawmethod.flipy = !drawmethod.flipy;}
					if(drawmethod.rotate)
					{
						if(drawmethod.rotate<0) drawmethod.rotate += 360;
					}
					drawmethod.flag = 1;
					break;
default:abort();}
return drawmethod;
}
static reference_drawmethod reference_draw_1(ArgList arglist,int blendfx_is_set){
reference_drawmethod drawmethod={0};char *filename="fixture.txt",*command="drawmethod";
switch(CMD_MODEL_DRAWMETHOD){
				case CMD_MODEL_DRAWMETHOD:
					// special effects
					drawmethod.scalex = GET_INT_ARG(1);
					drawmethod.scaley = GET_INT_ARG(2);
					drawmethod.flipx = GET_INT_ARG(3);
					drawmethod.flipy = GET_INT_ARG(4);
					drawmethod.shiftx = GET_INT_ARG(5);
					drawmethod.alpha = GET_INT_ARG(6);
					if(!blendfx_is_set)
					{
						if(drawmethod.alpha>0 && drawmethod.alpha<=MAX_BLENDINGS)
						{
							blendfx[drawmethod.alpha-1] = 1;
						}
					}
					drawmethod.remap = GET_INT_ARG(7);
					drawmethod.fillcolor = parsecolor(GET_ARG(8));
					drawmethod.rotate = GET_INT_ARG(9);
					drawmethod.fliprotate = GET_INT_ARG(10);
					if(drawmethod.scalex<0) {drawmethod.scalex = -drawmethod.scalex;drawmethod.flipx = !drawmethod.flipx;}
					if(drawmethod.scaley<0) {drawmethod.scaley = -drawmethod.scaley;drawmethod.flipy = !drawmethod.flipy;}
					if(drawmethod.rotate)
					{
						drawmethod.rotate = (drawmethod.rotate%360 + 360)%360;
					}
					drawmethod.flag = 1;
					break;
default:abort();}
return drawmethod;
}
static void reference_map_0(ArgList arglist,s_model *newchar,s_attack *out,int newanim){
s_attack attack=*out,*pattack;char *filename="fixture.txt",*command="forcemap";
switch(CMD_MODEL_FORCEMAP){
				case CMD_MODEL_FORCEMAP:
					// force color map change for specified time
					pattack = (!newanim && newchar->smartbomb)?newchar->smartbomb:&attack;
					pattack->forcemap = GET_INT_ARG(1);
					pattack->maptime = GET_INT_ARG(2) * GAME_SPEED;
					break;
default:abort();}
*out=attack;
}
static void reference_map_1(ArgList arglist,s_model *newchar,s_attack *out,int newanim){
s_attack attack=*out,*pattack;char *filename="fixture.txt",*command="forcemap";
switch(CMD_MODEL_FORCEMAP){
				case CMD_MODEL_FORCEMAP:
					// force color map change for specified time
					pattack = (!newanim && newchar->smartbomb)?newchar->smartbomb:&attack;
					pattack->forcemap = GET_INT_ARG(1);
					pattack->maptime = GET_FLOAT_ARG(2) * GAME_SPEED;
					break;
default:abort();}
*out=attack;
}
