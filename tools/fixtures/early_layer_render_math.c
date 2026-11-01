/* Original OpenBOR layer arithmetic and dispatch controls.
 * SPDX-License-Identifier: LicenseRef-OpenBOR-NoSale AND BSD-3-Clause
 * Original code: Copyright (c) 2004 - 2011 OpenBOR Team.
 * See LICENSES/OpenBOR-3400.txt at the published repository root.
 * Renamed fixture entry points: Copyright (c) 2026 retrodiv <retrodiv@proton.me>.
 * The BSD grant covers only those original adaptations; upstream terms remain.
 */
void reference_bg_0(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox)
		 bgtravelled += (((time-traveltime)*level->bgspeed/30*4) + ((level->rocking)?((time-traveltime)/(GAME_SPEED/30)):0)); // no like in real life, maybe
	else
		 texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		//if(level->bgdir==0) // count from left
		//{
			x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - (int)(bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio)%width);
		//}
		//else //count from right, complex
		//{
		//    x = videomodes.hRes1 - (level->width-videomodes.hRes1-advancex)*(bglayer->xratio) - bglayer->xoffset - width*bglayer->xrepeat + bglayer->xspacing + (int)(bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio)%width;
		//}

		if(level->scrolldir&SCROLL_UP)
		{
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		}
		else
		{
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);
		}

		if(x<0)
		{
			i = (-x)/width;
			x %= width;
		}
		else i=0;
		if(z<0)
		{
			j = (-z)/height;
			z %= height;
		}
		else j=0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
				{
					if(bglayer->watermode && bglayer->amplitude)
						 putscreen_water(pbgscreen, bglayer->screen, l, z, bglayer->amplitude, (float)bglayer->wavelength, (int)(timevar*bglayer->wavespeed), bglayer->watermode, &screenmethod);
					else
						 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				}
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

			}
		}
	}

	traveltime = time;
}

void reference_bg_1(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox)
		 bgtravelled += (((time-traveltime)*level->bgspeed/30*4) + ((level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0)); // no like in real life, maybe
	else
		 texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		//if(level->bgdir==0) // count from left
		//{
			x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - (int)(bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio)%width);
		//}
		//else //count from right, complex
		//{
		//    x = videomodes.hRes1 - (level->width-videomodes.hRes1-advancex)*(bglayer->xratio) - bglayer->xoffset - width*bglayer->xrepeat + bglayer->xspacing + (int)(bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio)%width;
		//}

		if(level->scrolldir&SCROLL_UP)
		{
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		}
		else
		{
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);
		}

		if(x<0)
		{
			i = (-x)/width;
			x %= width;
		}
		else i=0;
		if(z<0)
		{
			j = (-z)/height;
			z %= height;
		}
		else j=0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
				{
					if(bglayer->watermode && bglayer->amplitude)
						 putscreen_water(pbgscreen, bglayer->screen, l, z, bglayer->amplitude, (float)bglayer->wavelength, (int)(timevar*bglayer->wavespeed), bglayer->watermode, &screenmethod);
					else
						 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				}
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("#\n");

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_bg_2(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox)
		 bgtravelled += (((time-traveltime)*level->bgspeed/30*4) + ((level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0)); // no like in real life, maybe
	else
		 texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		//if(level->bgdir==0) // count from left
		//{
			x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio);
		//}
		//else //count from right, complex
		//{
		//    x = videomodes.hRes1 - (level->width-videomodes.hRes1-advancex)*(bglayer->xratio) - bglayer->xoffset - width*bglayer->xrepeat + bglayer->xspacing + (int)(bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio)%width;
		//}

		if(level->scrolldir&SCROLL_UP)
		{
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		}
		else
		{
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);
		}

		if(x<0){
			i = (-x)/width;
			x %= width;
		}else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		}else j = 0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
				{
					if(bglayer->watermode && bglayer->amplitude)
						 putscreen_water(pbgscreen, bglayer->screen, l, z, bglayer->amplitude, (float)bglayer->wavelength, (int)(timevar*bglayer->wavespeed), bglayer->watermode, &screenmethod);
					else
						 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				}
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("# %d %d %d %d %d\n", (int)bglayer->xoffset , (int)bglayer->xrepeat, (int)bglayer->xspacing, l, z);

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_bg_3(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox)
		 bgtravelled += (((time-traveltime)*level->bgspeed/30*4) + ((level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0)); // no like in real life, maybe
	else
		 texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		//if(level->bgdir==0) // count from left
		//{
			x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio);
		//}
		//else //count from right, complex
		//{
		//    x = videomodes.hRes1 - (level->width-videomodes.hRes1-advancex)*(bglayer->xratio) - bglayer->xoffset - width*bglayer->xrepeat + bglayer->xspacing + (int)(bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio)%width;
		//}

		if(level->scrolldir&SCROLL_UP)
		{
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		}
		else
		{
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);
		}

		if(x<0) i = (-x)/width;
		else i = 0;

		x %= width;
		if(x>0) x -= width;

		if(z<0) j = (-z)/height;
		else j = 0;

		z %= height;
		if(z>0) z -= height; // make it loop?

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
				{
					if(bglayer->watermode && bglayer->amplitude)
						 putscreen_water(pbgscreen, bglayer->screen, l, z, bglayer->amplitude, (float)bglayer->wavelength, (int)(timevar*bglayer->wavespeed), bglayer->watermode, &screenmethod);
					else
						 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				}
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("# %d %d %d %d %d\n", (int)bglayer->xoffset , (int)bglayer->xrepeat, (int)bglayer->xspacing, l, z);

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_bg_4(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	int width, height;
	s_drawmethod screenmethod;
	gfx_entry gfx;

	if(!textbox)
		 bgtravelled += (((time-traveltime)*level->bgspeed/30*4) + ((level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0)); // no like in real life, maybe
	else
		 texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
		{
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		}
		else
		{
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);
		}

		if(x<0) i = (-x)/width;
		else i = 0;

		x %= width;
		if(x>0) x -= width;

		if(z<0) j = (-z)/height;
		else j = 0;

		z %= height;
		if(z>0) z -= height; // make it loop?

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		screenmethod.water.wavelength = (float)bglayer->wavelength;
		screenmethod.water.amplitude =  bglayer->amplitude;
		screenmethod.water.wavetime =  (int)(timevar*bglayer->wavespeed);
		screenmethod.water.watermode =  bglayer->watermode;
		if(bglayer->type==bg_screen) {
			gfx.type = gfx_screen;
			gfx.screen = bglayer->screen;
		}else if(bglayer->type==bg_sprite){
			gfx.type = gfx_screen;
			gfx.sprite = bglayer->sprite;
		} else continue;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
					 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("# %d %d %d %d %d\n", (int)bglayer->xoffset , (int)bglayer->xrepeat, (int)bglayer->xspacing, l, z);

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_bg_5(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	float rocktravel;
	int width, height;
	s_drawmethod screenmethod;
	gfx_entry gfx;

	if(!textbox){
		rocktravel = (level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0; // no like in real life, maybe
		if(level->bgspeed<0) rocktravel = -rocktravel;
		bgtravelled += (time-traveltime)*level->bgspeed/30*2 + rocktravel;
	}else texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		else
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);

		if(x<0) {
			i = (-x)/width;
			x %= width;
		} else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		} else j = 0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		screenmethod.water.wavelength = (float)bglayer->wavelength;
		screenmethod.water.amplitude =  bglayer->amplitude;
		screenmethod.water.wavetime =  (int)(timevar*bglayer->wavespeed);
		screenmethod.water.watermode =  bglayer->watermode;
		if(bglayer->type==bg_screen) {
			gfx.type = gfx_screen;
			gfx.screen = bglayer->screen;
		}else if(bglayer->type==bg_sprite){
			gfx.type = gfx_screen;
			gfx.sprite = bglayer->sprite;
		} else continue;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
					 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("# %d %d %d %d %d\n", (int)bglayer->xoffset , (int)bglayer->xrepeat, (int)bglayer->xspacing, l, z);

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_bg_6(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	float rocktravel;
	int width, height;
	s_drawmethod screenmethod;
	gfx_entry gfx;

	if(!textbox){
		rocktravel = (level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0; // no like in real life, maybe
		if(level->bgspeed<0) rocktravel = -rocktravel;
		bgtravelled += (time-traveltime)*level->bgspeed/30*4 + rocktravel;
	}else texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		else
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);

		if(x<0) {
			i = (-x)/width;
			x %= width;
		} else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		} else j = 0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		screenmethod.water.wavelength = (float)bglayer->wavelength;
		screenmethod.water.amplitude =  bglayer->amplitude;
		screenmethod.water.wavetime =  (int)(timevar*bglayer->wavespeed);
		screenmethod.water.watermode =  bglayer->watermode;
		if(bglayer->type==bg_screen) {
			gfx.type = gfx_screen;
			gfx.screen = bglayer->screen;
		}else if(bglayer->type==bg_sprite){
			gfx.type = gfx_screen;
			gfx.sprite = bglayer->sprite;
		} else continue;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
					 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("# %d %d %d %d %d\n", (int)bglayer->xoffset , (int)bglayer->xrepeat, (int)bglayer->xspacing, l, z);

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_bg_7(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	float rocktravel;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox){
		rocktravel = (level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0; // no like in real life, maybe
		if(level->bgspeed<0) rocktravel = -rocktravel;
		bgtravelled += (time-traveltime)*level->bgspeed/30*4 + rocktravel;
	}else texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		else
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);

		if(x<0) {
			i = (-x)/width;
			x %= width;
		} else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		} else j = 0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = bglayer->alpha;
		screenmethod.transbg = bglayer->transparency;
		screenmethod.water.wavelength = (float)bglayer->wavelength;
		screenmethod.water.amplitude =  bglayer->amplitude;
		screenmethod.water.wavetime =  (int)(timevar*bglayer->wavespeed);
		screenmethod.water.watermode =  bglayer->watermode;
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + bglayer->amplitude*2; l+=width, k++)
			{
				if(bglayer->type==bg_screen)
					 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("#%d %d %d %d %d %d\n", level->numbglayers, (int)bglayer->xoffset , (int)bglayer->xrepeat, (int)bglayer->xspacing, l, z);

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_bg_8(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_bglayer* bglayer;
	float rocktravel;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox){
		rocktravel = (level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0; // no like in real life, maybe
		if(level->bgspeed<0) rocktravel = -rocktravel;
		bgtravelled += (time-traveltime)*level->bgspeed/30*4 + rocktravel;
	}else texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numbglayers; index++)
	{
		bglayer = level->bglayers+index;


		if(!bglayer->xrepeat || !bglayer->zrepeat || !bglayer->enabled) continue;

		width = bglayer->width + bglayer->xspacing;
		height = bglayer->height + bglayer->zspacing;

		x = (int)(bglayer->xoffset + (advancex)*(bglayer->xratio) - advancex - bgtravelled * (1-bglayer->xratio) * bglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
			z = (int)(4 + videomodes.vRes + (advancey+4)*bglayer->zratio - bglayer->zoffset - height*bglayer->zrepeat + height + bglayer->zspacing);
		else
			z = (int)(4 + bglayer->zoffset + (advancey-4)* bglayer->zratio - advancey);

		if(x<0) {
			i = (-x)/width;
			x %= width;
		} else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		} else j = 0;

		screenmethod=bglayer->drawmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.water.wavetime =  (int)(timevar*screenmethod.water.wavespeed);
		for(; j<bglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<bglayer->xrepeat && l<videomodes.hRes + (screenmethod.water.watermode==3?0:screenmethod.water.amplitude*2); l+=width, k++)
			{
				if(bglayer->type==bg_screen)
					 putscreen(pbgscreen, bglayer->screen, l, z, &screenmethod);
				else if(bglayer->type==bg_sprite)
					putsprite(l, z, bglayer->sprite, pbgscreen, &screenmethod);

				//printf("#%d %d %d %d %d %d\n", level->numbglayers, (int)bglayer->xoffset , (int)bglayer->xrepeat, (int)bglayer->xspacing, l, z);

			}
		}
	}
	
	//printf("**************\n");
	traveltime = time;
}

void reference_fg_0(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l;
	s_fglayer* fglayer;
	int width, height;
	s_drawmethod screenmethod;

	for(index = 0; index < level->numfglayers; index++)
	{
		fglayer = level->fglayers+index;


		if(!fglayer->xrepeat || !fglayer->zrepeat || !fglayer->enabled) continue;

		width = fglayer->width + fglayer->xspacing;
		height = fglayer->height + fglayer->zspacing;

		//if(level->bgdir==0) // count from left
		//{
			x = (int)(fglayer->xoffset + (advancex)*(fglayer->xratio) - advancex - (int)(bgtravelled * (1-fglayer->xratio) * fglayer->bgspeedratio)%width);
		//}
		//else //count from right, complex
		//{
		//    x = videomodes.hRes1 - (level->width-videomodes.hRes1-advancex)*(fglayer->xratio) - fglayer->xoffset - width*fglayer->xrepeat + fglayer->xspacing + (int)(bgtravelled * (1-fglayer->xratio) * fglayer->bgspeedratio)%width;
		//}

		if(level->scrolldir&SCROLL_UP)
		{
			z = (int)(4 + videomodes.vRes + (advancey+4)*fglayer->zratio - fglayer->zoffset - height*fglayer->zrepeat + height + fglayer->zspacing);
		}
		else
		{
			z = (int)(4 + fglayer->zoffset + (advancey-4)* fglayer->zratio - advancey);
		}

		if(x<0)
		{
			i = (-x)/width;
			x %= width;
		}
		else i=0;
		if(z<0)
		{
			j = (-z)/height;
			z %= height;
		}
		else j=0;


		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = fglayer->alpha;
		screenmethod.transbg = fglayer->transparency;
		for(; j<fglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<fglayer->xrepeat && l<videomodes.hRes + fglayer->amplitude*2; l+=width, k++)
			{
					spriteq_add_frame(l, z, FRONTPANEL_Z + fglayer->z, fglayer->sprite, &screenmethod, 0);

			}
		}
	}
}

void reference_fg_1(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_fglayer* fglayer;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox)
		 bgtravelled += (((time-traveltime)*level->bgspeed/30*4) + ((level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0)); // no like in real life, maybe
	else
		 texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numfglayers; index++)
	{
		fglayer = level->fglayers+index;


		if(!fglayer->xrepeat || !fglayer->zrepeat || !fglayer->enabled) continue;

		width = fglayer->width + fglayer->xspacing;
		height = fglayer->height + fglayer->zspacing;

		x = (int)(fglayer->xoffset + (advancex)*(fglayer->xratio) - advancex - bgtravelled * (1-fglayer->xratio) * fglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
		{
			z = (int)(4 + videomodes.vRes + (advancey+4)*fglayer->zratio - fglayer->zoffset - height*fglayer->zrepeat + height + fglayer->zspacing);
		}
		else
		{
			z = (int)(4 + fglayer->zoffset + (advancey-4)* fglayer->zratio - advancey);
		}

		if(x<0) i = (-x)/width;
		else i = 0;

		x %= width;
		if(x>0) x -= width;

		if(z<0) j = (-z)/height;
		else j = 0;

		z %= height;
		if(z>0) z -= height; // make it loop?

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = fglayer->alpha;
		screenmethod.transbg = fglayer->transparency;
		screenmethod.water.wavelength = (float)fglayer->wavelength;
		screenmethod.water.amplitude =  fglayer->amplitude;
		screenmethod.water.wavetime =  (int)(timevar*fglayer->wavespeed);
		screenmethod.water.watermode =  fglayer->watermode;
		for(; j<fglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<fglayer->xrepeat && l<videomodes.hRes + fglayer->amplitude*2; l+=width, k++)
			{
				if(fglayer->type==fg_screen)
					 spriteq_add_screen(l, z, FRONTPANEL_Z + fglayer->z, fglayer->screen, &screenmethod, 0);
				else if(fglayer->type==fg_sprite)
					spriteq_add_frame(l, z, FRONTPANEL_Z + fglayer->z, fglayer->sprite, &screenmethod, 0);

			}
		}
	}
}

void reference_fg_2(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_fglayer* fglayer;
	float rocktravel;
	int width, height;
	s_drawmethod screenmethod;

	if(!textbox){
		rocktravel = (level->rocking)?((time-traveltime)/((float)GAME_SPEED/30)):0; // no like in real life, maybe
		if(level->bgspeed<0) rocktravel = -rocktravel;
		bgtravelled += (time-traveltime)*level->bgspeed/30*2 + rocktravel;
	}else texttime += time-traveltime;

	timevar = time - texttime;

	for(index = 0; index < level->numfglayers; index++)
	{
		fglayer = level->fglayers+index;


		if(!fglayer->xrepeat || !fglayer->zrepeat || !fglayer->enabled) continue;

		width = fglayer->width + fglayer->xspacing;
		height = fglayer->height + fglayer->zspacing;

		x = (int)(fglayer->xoffset + (advancex)*(fglayer->xratio) - advancex - bgtravelled * (1-fglayer->xratio) * fglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
			z = (int)(4 + videomodes.vRes + (advancey+4)*fglayer->zratio - fglayer->zoffset - height*fglayer->zrepeat + height + fglayer->zspacing);
		else
			z = (int)(4 + fglayer->zoffset + (advancey-4)* fglayer->zratio - advancey);

		if(x<0) {
			i = (-x)/width;
			x %= width;
		} else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		} else j = 0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = fglayer->alpha;
		screenmethod.transbg = fglayer->transparency;
		screenmethod.water.wavelength = (float)fglayer->wavelength;
		screenmethod.water.amplitude =  fglayer->amplitude;
		screenmethod.water.wavetime =  (int)(timevar*fglayer->wavespeed);
		screenmethod.water.watermode =  fglayer->watermode;
		for(; j<fglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<fglayer->xrepeat && l<videomodes.hRes + fglayer->amplitude*2; l+=width, k++)
			{
				if(fglayer->type==fg_screen)
					 spriteq_add_screen(l, z, FRONTPANEL_Z + fglayer->z, fglayer->screen, &screenmethod, 0);
				else if(fglayer->type==fg_sprite)
					spriteq_add_frame(l, z, FRONTPANEL_Z + fglayer->z, fglayer->sprite, &screenmethod, 0);

			}
		}
	}
}

void reference_fg_3(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_fglayer* fglayer;
	int width, height;
	s_drawmethod screenmethod;

	timevar = time - texttime;

	for(index = 0; index < level->numfglayers; index++)
	{
		fglayer = level->fglayers+index;


		if(!fglayer->xrepeat || !fglayer->zrepeat || !fglayer->enabled) continue;

		width = fglayer->width + fglayer->xspacing;
		height = fglayer->height + fglayer->zspacing;

		x = (int)(fglayer->xoffset + (advancex)*(fglayer->xratio) - advancex - bgtravelled * (1-fglayer->xratio) * fglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
			z = (int)(4 + videomodes.vRes + (advancey+4)*fglayer->zratio - fglayer->zoffset - height*fglayer->zrepeat + height + fglayer->zspacing);
		else
			z = (int)(4 + fglayer->zoffset + (advancey-4)* fglayer->zratio - advancey);

		if(x<0) {
			i = (-x)/width;
			x %= width;
		} else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		} else j = 0;

		screenmethod=plainmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.alpha = fglayer->alpha;
		screenmethod.transbg = fglayer->transparency;
		screenmethod.water.wavelength = (float)fglayer->wavelength;
		screenmethod.water.amplitude =  fglayer->amplitude;
		screenmethod.water.wavetime =  (int)(timevar*fglayer->wavespeed);
		screenmethod.water.watermode =  fglayer->watermode;
		for(; j<fglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<fglayer->xrepeat && l<videomodes.hRes + fglayer->amplitude*2; l+=width, k++)
			{
				if(fglayer->type==fg_screen)
					 spriteq_add_screen(l, z, FRONTPANEL_Z + fglayer->z, fglayer->screen, &screenmethod, 0);
				else if(fglayer->type==fg_sprite)
					spriteq_add_frame(l, z, FRONTPANEL_Z + fglayer->z, fglayer->sprite, &screenmethod, 0);

			}
		}
	}
}

void reference_fg_4(s_screen* pbgscreen)
{
	int index, x, z, i, j, k, l, timevar;
	s_fglayer* fglayer;
	int width, height;
	s_drawmethod screenmethod;

	timevar = time - texttime;

	for(index = 0; index < level->numfglayers; index++)
	{
		fglayer = level->fglayers+index;


		if(!fglayer->xrepeat || !fglayer->zrepeat || !fglayer->enabled) continue;

		width = fglayer->width + fglayer->xspacing;
		height = fglayer->height + fglayer->zspacing;

		x = (int)(fglayer->xoffset + (advancex)*(fglayer->xratio) - advancex - bgtravelled * (1-fglayer->xratio) * fglayer->bgspeedratio);

		if(level->scrolldir&SCROLL_UP)
			z = (int)(4 + videomodes.vRes + (advancey+4)*fglayer->zratio - fglayer->zoffset - height*fglayer->zrepeat + height + fglayer->zspacing);
		else
			z = (int)(4 + fglayer->zoffset + (advancey-4)* fglayer->zratio - advancey);

		if(x<0) {
			i = (-x)/width;
			x %= width;
		} else i = 0;

		if(z<0){
			j = (-z)/height;
			z %= height;
		} else j = 0;

		screenmethod=fglayer->drawmethod;
		screenmethod.table = (pixelformat==PIXEL_x8)?(current_palette>0?(level->palettes[current_palette-1]):NULL):NULL;
		screenmethod.water.wavetime =  (int)(timevar*screenmethod.water.wavespeed);
		for(; j<fglayer->zrepeat && z<videomodes.vRes; z+=height, j++)
		{
			for(k=i, l=x; k<fglayer->xrepeat && l<videomodes.hRes + (screenmethod.water.watermode==3?0:screenmethod.water.amplitude*2); l+=width, k++)
			{
				if(fglayer->type==fg_screen)
					 spriteq_add_screen(l, z, FRONTPANEL_Z + fglayer->z, fglayer->screen, &screenmethod, 0);
				else if(fglayer->type==fg_sprite)
					spriteq_add_frame(l, z, FRONTPANEL_Z + fglayer->z, fglayer->sprite, &screenmethod, 0);

			}
		}
	}
}
