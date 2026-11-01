/* Original OpenBOR layer command and post-load controls.
 * SPDX-License-Identifier: LicenseRef-OpenBOR-NoSale AND BSD-3-Clause
 * Original code: Copyright (c) 2004 - 2011 OpenBOR Team.
 * See LICENSES/OpenBOR-3400.txt at the published repository root.
 * Fixture wrappers: Copyright (c) 2026 retrodiv <retrodiv@proton.me>.
 * The BSD grant covers only those original wrappers; upstream terms remain.
 */
static int reference_background_0(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_BACKGROUND:
				value = GET_ARG(1);
				strncpy(bgPath, value, strlen(value)+1);
				level->bglayers[0].type = bg_screen;
				level->bglayers[0].bgspeedratio = 1;

				level->bglayers[0].xratio = GET_FLOAT_ARG(2); // x ratio
				level->bglayers[0].zratio = GET_FLOAT_ARG(3); // z ratio
				level->bglayers[0].xoffset = GET_INT_ARG(4); // x start
				level->bglayers[0].zoffset = GET_INT_ARG(5); // z start
				level->bglayers[0].xspacing = GET_INT_ARG(6); // x spacing
				level->bglayers[0].zspacing = GET_INT_ARG(7); // z spacing
				level->bglayers[0].xrepeat = GET_INT_ARG(8); // x repeat
				level->bglayers[0].zrepeat = GET_INT_ARG(9); // z repeat
				// unused
				level->bglayers[0].transparency = GET_INT_ARG(10); // transparency
				level->bglayers[0].alpha = GET_INT_ARG(11); // alpha
				level->bglayers[0].watermode = GET_INT_ARG(12); // amplitude
				level->bglayers[0].amplitude = GET_INT_ARG(13); // amplitude
				level->bglayers[0].wavelength = GET_INT_ARG(14); // wavelength
				level->bglayers[0].wavespeed = GET_FLOAT_ARG(15); // waterspeed
				level->bglayers[0].enabled = 1; // enabled

				if((value=GET_ARG(2))[0]==0) level->bglayers[0].xratio = 0.5;
				if((value=GET_ARG(3))[0]==0) level->bglayers[0].zratio = 0.5;

				if((value=GET_ARG(8))[0]==0) level->bglayers[0].xrepeat = 5000;
				if((value=GET_ARG(9))[0]==0) level->bglayers[0].zrepeat = 5000;

				if(level->numbglayers==0) level->numbglayers = 1;
				break;
			
    default: abort();
    }
    return 0;
}

static int reference_bglayer_0(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_BGLAYER:
				if(level->numbglayers >= LEVEL_MAX_BGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_BGLAYERS)!";
					goto lCleanup;
				}
				if(level->numbglayers==0) level->numbglayers = 1; // reserve for background

				level->bglayers[level->numbglayers].xratio = GET_FLOAT_ARG(2); // x ratio
				level->bglayers[level->numbglayers].zratio = GET_FLOAT_ARG(3); // z ratio
				level->bglayers[level->numbglayers].xoffset = GET_INT_ARG(4); // x start
				level->bglayers[level->numbglayers].zoffset = GET_INT_ARG(5); // z start
				level->bglayers[level->numbglayers].xspacing = GET_INT_ARG(6); // x spacing
				level->bglayers[level->numbglayers].zspacing = GET_INT_ARG(7); // z spacing
				level->bglayers[level->numbglayers].xrepeat = GET_INT_ARG(8); // x repeat
				level->bglayers[level->numbglayers].zrepeat = GET_INT_ARG(9); // z repeat
				level->bglayers[level->numbglayers].transparency = GET_INT_ARG(10); // transparency
				level->bglayers[level->numbglayers].alpha = GET_INT_ARG(11); // alpha
				level->bglayers[level->numbglayers].watermode = GET_INT_ARG(12); // amplitude
				level->bglayers[level->numbglayers].amplitude = GET_INT_ARG(13); // amplitude
				level->bglayers[level->numbglayers].wavelength = GET_INT_ARG(14); // wavelength
				level->bglayers[level->numbglayers].wavespeed = GET_FLOAT_ARG(15); // waterspeed
				level->bglayers[level->numbglayers].bgspeedratio = GET_FLOAT_ARG(16); // moving
				level->bglayers[level->numbglayers].enabled = 1; // enabled

				if((value=GET_ARG(2))[0]==0) level->bglayers[level->numbglayers].xratio = 0.5;
				if((value=GET_ARG(3))[0]==0) level->bglayers[level->numbglayers].zratio = 0.5;

				if((value=GET_ARG(8))[0]==0) level->bglayers[level->numbglayers].xrepeat = 5000; // close enough to infinite, lol
				if((value=GET_ARG(9))[0]==0) level->bglayers[level->numbglayers].zrepeat = 5000;

				if(blendfx_is_set==0 && level->bglayers[level->numbglayers].alpha) blendfx[level->bglayers[level->numbglayers].alpha-1] = 1;

				load_bglayer(GET_ARG(1), level->numbglayers);
				level->numbglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static int reference_fglayer_0(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_FGLAYER:
				if(level->numfglayers >= LEVEL_MAX_FGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_FGLAYERS)!";
					goto lCleanup;
				}

				level->fglayers[level->numfglayers].z = GET_INT_ARG(2); // z
				level->fglayers[level->numfglayers].xratio = GET_FLOAT_ARG(3); // x ratio
				level->fglayers[level->numfglayers].zratio = GET_FLOAT_ARG(4); // z ratio
				level->fglayers[level->numfglayers].xoffset = GET_INT_ARG(5); // x start
				level->fglayers[level->numfglayers].zoffset = GET_INT_ARG(6); // z start
				level->fglayers[level->numfglayers].xspacing = GET_INT_ARG(7); // x spacing
				level->fglayers[level->numfglayers].zspacing = GET_INT_ARG(8); // z spacing
				level->fglayers[level->numfglayers].xrepeat = GET_INT_ARG(9); // x repeat

				level->fglayers[level->numfglayers].zrepeat = GET_INT_ARG(10); // z repeat
				level->fglayers[level->numfglayers].transparency = GET_INT_ARG(11); // transparency
				level->fglayers[level->numfglayers].alpha = GET_INT_ARG(12); // alpha
				level->fglayers[level->numfglayers].watermode = GET_INT_ARG(13); // amplitude
				level->fglayers[level->numfglayers].amplitude = GET_INT_ARG(14); // amplitude
				level->fglayers[level->numfglayers].wavelength = GET_INT_ARG(15); // wavelength
				level->fglayers[level->numfglayers].wavespeed = GET_FLOAT_ARG(16); // waterspeed
				level->fglayers[level->numfglayers].bgspeedratio = GET_FLOAT_ARG(17); // moving
				level->fglayers[level->numfglayers].enabled = 1;

				if((value=GET_ARG(2))[0]==0) level->fglayers[level->numfglayers].xratio = 1.5;
				if((value=GET_ARG(3))[0]==0) level->fglayers[level->numfglayers].zratio = 1.5;

				if((value=GET_ARG(8))[0]==0) level->fglayers[level->numfglayers].xrepeat = 5000; // close enough to infinite, lol
				if((value=GET_ARG(9))[0]==0) level->fglayers[level->numfglayers].zrepeat = 5000;

				if(blendfx_is_set==0 && level->fglayers[level->numfglayers].alpha) blendfx[level->fglayers[level->numfglayers].alpha-1] = 1;

				load_fglayer(GET_ARG(1), level->numfglayers);
				level->numfglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static int reference_water_0(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_WATER:
				load_texture(GET_ARG(1));
				i = GET_INT_ARG(2);
				if(i<1) i = 1;
				texture_set_wave((float)i);
				break;
			
    default: abort();
    }
    return 0;
}

static void reference_post_0(void) {
 int i; s_drawmethod *dm;

}

static int reference_background_1(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_BACKGROUND:
				value = GET_ARG(1);
				strncpy(bgPath, value, strlen(value)+1);
				level->bglayers[0].type = bg_screen;
				level->bglayers[0].bgspeedratio = 1;

				level->bglayers[0].xratio = GET_FLOAT_ARG(2); // x ratio
				level->bglayers[0].zratio = GET_FLOAT_ARG(3); // z ratio
				level->bglayers[0].xoffset = GET_INT_ARG(4); // x start
				level->bglayers[0].zoffset = GET_INT_ARG(5); // z start
				level->bglayers[0].xspacing = GET_INT_ARG(6); // x spacing
				level->bglayers[0].zspacing = GET_INT_ARG(7); // z spacing
				level->bglayers[0].xrepeat = GET_INT_ARG(8); // x repeat
				level->bglayers[0].zrepeat = GET_INT_ARG(9); // z repeat
				// unused
				level->bglayers[0].transparency = GET_INT_ARG(10); // transparency
				level->bglayers[0].alpha = GET_INT_ARG(11); // alpha
				level->bglayers[0].watermode = GET_INT_ARG(12); // amplitude
				level->bglayers[0].amplitude = GET_INT_ARG(13); // amplitude
				level->bglayers[0].wavelength = GET_INT_ARG(14); // wavelength
				level->bglayers[0].wavespeed = GET_FLOAT_ARG(15); // waterspeed
				level->bglayers[0].enabled = 1; // enabled

				if((value=GET_ARG(2))[0]==0) level->bglayers[0].xratio = 0.5;
				if((value=GET_ARG(3))[0]==0) level->bglayers[0].zratio = 0.5;

				if((value=GET_ARG(8))[0]==0) level->bglayers[0].xrepeat = -1;
				if((value=GET_ARG(9))[0]==0) level->bglayers[0].zrepeat = -1;

				if(level->numbglayers==0) level->numbglayers = 1;
				break;
			
    default: abort();
    }
    return 0;
}

static int reference_bglayer_1(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_BGLAYER:
				if(level->numbglayers >= LEVEL_MAX_BGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_BGLAYERS)!";
					goto lCleanup;
				}
				if(level->numbglayers==0) level->numbglayers = 1; // reserve for background

				level->bglayers[level->numbglayers].xratio = GET_FLOAT_ARG(2); // x ratio
				level->bglayers[level->numbglayers].zratio = GET_FLOAT_ARG(3); // z ratio
				level->bglayers[level->numbglayers].xoffset = GET_INT_ARG(4); // x start
				level->bglayers[level->numbglayers].zoffset = GET_INT_ARG(5); // z start
				level->bglayers[level->numbglayers].xspacing = GET_INT_ARG(6); // x spacing
				level->bglayers[level->numbglayers].zspacing = GET_INT_ARG(7); // z spacing
				level->bglayers[level->numbglayers].xrepeat = GET_INT_ARG(8); // x repeat
				level->bglayers[level->numbglayers].zrepeat = GET_INT_ARG(9); // z repeat
				level->bglayers[level->numbglayers].transparency = GET_INT_ARG(10); // transparency
				level->bglayers[level->numbglayers].alpha = GET_INT_ARG(11); // alpha
				level->bglayers[level->numbglayers].watermode = GET_INT_ARG(12); // amplitude
				level->bglayers[level->numbglayers].amplitude = GET_INT_ARG(13); // amplitude
				level->bglayers[level->numbglayers].wavelength = GET_INT_ARG(14); // wavelength
				level->bglayers[level->numbglayers].wavespeed = GET_FLOAT_ARG(15); // waterspeed
				level->bglayers[level->numbglayers].bgspeedratio = GET_FLOAT_ARG(16); // moving
				level->bglayers[level->numbglayers].enabled = 1; // enabled

				if((value=GET_ARG(2))[0]==0) level->bglayers[level->numbglayers].xratio = 0.5;
				if((value=GET_ARG(3))[0]==0) level->bglayers[level->numbglayers].zratio = 0.5;

				if((value=GET_ARG(8))[0]==0) level->bglayers[level->numbglayers].xrepeat = -1;
				if((value=GET_ARG(9))[0]==0) level->bglayers[level->numbglayers].zrepeat = -1;

				if(blendfx_is_set==0 && level->bglayers[level->numbglayers].alpha) blendfx[level->bglayers[level->numbglayers].alpha-1] = 1;

				load_bglayer(GET_ARG(1), level->numbglayers);
				level->numbglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static int reference_fglayer_1(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_FGLAYER:
				if(level->numfglayers >= LEVEL_MAX_FGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_FGLAYERS)!";
					goto lCleanup;
				}

				level->fglayers[level->numfglayers].z = GET_INT_ARG(2); // z
				level->fglayers[level->numfglayers].xratio = GET_FLOAT_ARG(3); // x ratio
				level->fglayers[level->numfglayers].zratio = GET_FLOAT_ARG(4); // z ratio
				level->fglayers[level->numfglayers].xoffset = GET_INT_ARG(5); // x start
				level->fglayers[level->numfglayers].zoffset = GET_INT_ARG(6); // z start
				level->fglayers[level->numfglayers].xspacing = GET_INT_ARG(7); // x spacing
				level->fglayers[level->numfglayers].zspacing = GET_INT_ARG(8); // z spacing
				level->fglayers[level->numfglayers].xrepeat = GET_INT_ARG(9); // x repeat

				level->fglayers[level->numfglayers].zrepeat = GET_INT_ARG(10); // z repeat
				level->fglayers[level->numfglayers].transparency = GET_INT_ARG(11); // transparency
				level->fglayers[level->numfglayers].alpha = GET_INT_ARG(12); // alpha
				level->fglayers[level->numfglayers].watermode = GET_INT_ARG(13); // amplitude
				level->fglayers[level->numfglayers].amplitude = GET_INT_ARG(14); // amplitude
				level->fglayers[level->numfglayers].wavelength = GET_INT_ARG(15); // wavelength
				level->fglayers[level->numfglayers].wavespeed = GET_FLOAT_ARG(16); // waterspeed
				level->fglayers[level->numfglayers].bgspeedratio = GET_FLOAT_ARG(17); // moving
				level->fglayers[level->numfglayers].enabled = 1;

				if((value=GET_ARG(2))[0]==0) level->fglayers[level->numfglayers].xratio = 1.5;
				if((value=GET_ARG(3))[0]==0) level->fglayers[level->numfglayers].zratio = 1.5;

				if((value=GET_ARG(8))[0]==0) level->fglayers[level->numfglayers].xrepeat = -1;
				if((value=GET_ARG(9))[0]==0) level->fglayers[level->numfglayers].zrepeat = -1;

				if(blendfx_is_set==0 && level->fglayers[level->numfglayers].alpha) blendfx[level->fglayers[level->numfglayers].alpha-1] = 1;

				load_fglayer(GET_ARG(1), level->numfglayers);
				level->numfglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static void reference_post_1(void) {
 int i; s_drawmethod *dm;
	if(level->numbglayers) load_bglayer(NULL, 0);

}

static int reference_water_1(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_WATER:
				if(level->numbglayers >= LEVEL_MAX_BGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_BGLAYERS)!";
					goto lCleanup;
				}
				if(level->numbglayers==0) level->numbglayers = 1; // reserve for background

				level->bglayers[level->numbglayers].xratio = 0.5; // x ratio
				level->bglayers[level->numbglayers].zratio = 0.5; // z ratio
				level->bglayers[level->numbglayers].xoffset = 0; // x start
				level->bglayers[level->numbglayers].zoffset = 1234567890; // z start
				level->bglayers[level->numbglayers].xspacing = 0; // x spacing
				level->bglayers[level->numbglayers].zspacing = 0; // z spacing
				level->bglayers[level->numbglayers].xrepeat = -1; // x repeat
				level->bglayers[level->numbglayers].zrepeat = 1; // z repeat
				level->bglayers[level->numbglayers].transparency = 0; // transparency
				level->bglayers[level->numbglayers].alpha = 0; // alpha
				level->bglayers[level->numbglayers].watermode = 2; // amplitude
				level->bglayers[level->numbglayers].amplitude = GET_INT_ARG(2); // amplitude
				level->bglayers[level->numbglayers].wavelength = 40; // wavelength
				level->bglayers[level->numbglayers].wavespeed = 1; // waterspeed
				level->bglayers[level->numbglayers].bgspeedratio = 0; // moving
				level->bglayers[level->numbglayers].enabled = 1; // enabled

				if(level->bglayers[level->numbglayers].amplitude<1) level->bglayers[level->numbglayers].amplitude = 1;

				load_bglayer(GET_ARG(1), level->numbglayers);
				level->numbglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static void reference_post_2(void) {
 int i; s_drawmethod *dm;
	if(level->numbglayers) {
		load_bglayer(NULL, 0); // initialize background height and width and looping
		
		for(i=1; i<level->numbglayers; i++){
			if(level->bglayers[i].zoffset == 1234567890){ // default water hack
				level->bglayers[i].zoffset = level->bglayers[0].height;
				if(level->rocking) {
					level->bglayers[i].watermode =3;
					level->bglayers[i].wavelength =10;
					level->bglayers[i].wavespeed =0;
					level->bglayers[i].bgspeedratio =2;
				}
			}
		}

	}

}

static int reference_background_2(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_BACKGROUND:
				value = GET_ARG(1);
				strncpy(bgPath, value, strlen(value)+1);

				dm = &(level->bglayers[0].drawmethod);
				*dm = plainmethod;

				level->bglayers[0].type = bg_screen;
				level->bglayers[0].bgspeedratio = 1;

				level->bglayers[0].xratio = GET_FLOAT_ARG(2); // x ratio
				level->bglayers[0].zratio = GET_FLOAT_ARG(3); // z ratio
				level->bglayers[0].xoffset = GET_INT_ARG(4); // x start
				level->bglayers[0].zoffset = GET_INT_ARG(5); // z start
				level->bglayers[0].xspacing = GET_INT_ARG(6); // x spacing
				level->bglayers[0].zspacing = GET_INT_ARG(7); // z spacing
				level->bglayers[0].xrepeat = GET_INT_ARG(8); // x repeat
				level->bglayers[0].zrepeat = GET_INT_ARG(9); // z repeat
				// unused
				dm->transbg = GET_INT_ARG(10); // transparency
				dm->alpha = GET_INT_ARG(11); // alpha
				dm->water.watermode = GET_INT_ARG(12); // amplitude
				if(dm->water.watermode==3){
					dm->water.beginsize = GET_FLOAT_ARG(13); // beginsize
					dm->water.endsize = GET_FLOAT_ARG(14); // endsize
					dm->water.perspective = GET_INT_ARG(15); // waterspeed
				}else{
					dm->water.amplitude = GET_INT_ARG(13); // amplitude
					dm->water.wavelength = GET_INT_ARG(14); // wavelength
					dm->water.wavespeed = GET_FLOAT_ARG(15); // waterspeed
				}
				level->bglayers[0].enabled = 1; // enabled

				if((value=GET_ARG(2))[0]==0) level->bglayers[0].xratio = 0.5;
				if((value=GET_ARG(3))[0]==0) level->bglayers[0].zratio = 0.5;

				if((value=GET_ARG(8))[0]==0) level->bglayers[0].xrepeat = -1;
				if((value=GET_ARG(9))[0]==0) level->bglayers[0].zrepeat = -1;

				if(level->numbglayers==0) level->numbglayers = 1;
				break;
			
    default: abort();
    }
    return 0;
}

static int reference_bglayer_2(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_BGLAYER:
				if(level->numbglayers >= LEVEL_MAX_BGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_BGLAYERS)!";
					goto lCleanup;
				}
				if(level->numbglayers==0) level->numbglayers = 1; // reserve for background

				dm = &(level->bglayers[level->numbglayers].drawmethod);
				*dm = plainmethod;

				level->bglayers[level->numbglayers].xratio = GET_FLOAT_ARG(2); // x ratio
				level->bglayers[level->numbglayers].zratio = GET_FLOAT_ARG(3); // z ratio
				level->bglayers[level->numbglayers].xoffset = GET_INT_ARG(4); // x start
				level->bglayers[level->numbglayers].zoffset = GET_INT_ARG(5); // z start
				level->bglayers[level->numbglayers].xspacing = GET_INT_ARG(6); // x spacing
				level->bglayers[level->numbglayers].zspacing = GET_INT_ARG(7); // z spacing
				level->bglayers[level->numbglayers].xrepeat = GET_INT_ARG(8); // x repeat
				level->bglayers[level->numbglayers].zrepeat = GET_INT_ARG(9); // z repeat
				dm->transbg = GET_INT_ARG(10); // transparency
				dm->alpha = GET_INT_ARG(11); // alpha
				dm->water.watermode = GET_INT_ARG(12); // amplitude
				if(dm->water.watermode==3){
					dm->water.beginsize = GET_FLOAT_ARG(13); // beginsize
					dm->water.endsize = GET_FLOAT_ARG(14); // endsize
					dm->water.perspective = GET_INT_ARG(15); // amplitude
				}else{
					dm->water.amplitude = GET_INT_ARG(13); // amplitude
					dm->water.wavelength = GET_INT_ARG(14); // wavelength
					dm->water.wavespeed = GET_FLOAT_ARG(15); // waterspeed
				}
				level->bglayers[level->numbglayers].bgspeedratio = GET_FLOAT_ARG(16); // moving
				level->bglayers[level->numbglayers].enabled = 1; // enabled

				if((value=GET_ARG(2))[0]==0) level->bglayers[level->numbglayers].xratio = 0.5;
				if((value=GET_ARG(3))[0]==0) level->bglayers[level->numbglayers].zratio = 0.5;

				if((value=GET_ARG(8))[0]==0) level->bglayers[level->numbglayers].xrepeat = -1;
				if((value=GET_ARG(9))[0]==0) level->bglayers[level->numbglayers].zrepeat = -1;

				if(blendfx_is_set==0 && dm->alpha) blendfx[dm->alpha-1] = 1;

				load_bglayer(GET_ARG(1), level->numbglayers);
				level->numbglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static int reference_fglayer_2(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_FGLAYER:
				if(level->numfglayers >= LEVEL_MAX_FGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_FGLAYERS)!";
					goto lCleanup;
				}

				dm = &(level->fglayers[level->numfglayers].drawmethod);
				*dm = plainmethod;

				level->fglayers[level->numfglayers].z = GET_INT_ARG(2); // z
				level->fglayers[level->numfglayers].xratio = GET_FLOAT_ARG(3); // x ratio
				level->fglayers[level->numfglayers].zratio = GET_FLOAT_ARG(4); // z ratio
				level->fglayers[level->numfglayers].xoffset = GET_INT_ARG(5); // x start
				level->fglayers[level->numfglayers].zoffset = GET_INT_ARG(6); // z start
				level->fglayers[level->numfglayers].xspacing = GET_INT_ARG(7); // x spacing
				level->fglayers[level->numfglayers].zspacing = GET_INT_ARG(8); // z spacing
				level->fglayers[level->numfglayers].xrepeat = GET_INT_ARG(9); // x repeat

				level->fglayers[level->numfglayers].zrepeat = GET_INT_ARG(10); // z repeat
				dm->transbg = GET_INT_ARG(11); // transparency
				dm->alpha = GET_INT_ARG(12); // alpha
				dm->water.watermode = GET_INT_ARG(13); // watermode
				if(dm->water.watermode==3){
					dm->water.beginsize = GET_FLOAT_ARG(14); // beginsize
					dm->water.endsize = GET_FLOAT_ARG(15); // endsize
					dm->water.perspective = GET_INT_ARG(16); // amplitude
				}else{
					dm->water.amplitude = GET_INT_ARG(14); // amplitude
					dm->water.wavelength = GET_INT_ARG(15); // wavelength
					dm->water.wavespeed = GET_FLOAT_ARG(16); // waterspeed
				}
				level->fglayers[level->numfglayers].bgspeedratio = GET_FLOAT_ARG(17); // moving
				level->fglayers[level->numfglayers].enabled = 1;

				if((value=GET_ARG(2))[0]==0) level->fglayers[level->numfglayers].xratio = 1.5;
				if((value=GET_ARG(3))[0]==0) level->fglayers[level->numfglayers].zratio = 1.5;

				if((value=GET_ARG(8))[0]==0) level->fglayers[level->numfglayers].xrepeat = -1;
				if((value=GET_ARG(9))[0]==0) level->fglayers[level->numfglayers].zrepeat = -1;

				if(blendfx_is_set==0 && dm->alpha) blendfx[dm->alpha-1] = 1;

				load_fglayer(GET_ARG(1), level->numfglayers);
				level->numfglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static int reference_water_2(int cmd) {
    char *value, *errormessage = NULL;
    int i;
    s_drawmethod *dm;
    switch(cmd) {
case CMD_LEVEL_WATER:
				if(level->numbglayers >= LEVEL_MAX_BGLAYERS) {
					errormessage = "Too many bg layers in level (check LEVEL_MAX_BGLAYERS)!";
					goto lCleanup;
				}
				if(level->numbglayers==0) level->numbglayers = 1; // reserve for background
				dm = &(level->bglayers[level->numbglayers].drawmethod);
				*dm = plainmethod;

				level->bglayers[level->numbglayers].xratio = 0.5; // x ratio
				level->bglayers[level->numbglayers].zratio = 0.5; // z ratio
				level->bglayers[level->numbglayers].xoffset = 0; // x start
				level->bglayers[level->numbglayers].zoffset = 1234567890; // z start
				level->bglayers[level->numbglayers].xspacing = 0; // x spacing
				level->bglayers[level->numbglayers].zspacing = 0; // z spacing
				level->bglayers[level->numbglayers].xrepeat = -1; // x repeat
				level->bglayers[level->numbglayers].zrepeat = 1; // z repeat
				dm->transbg = 0; // transparency
				dm->alpha = 0; // alpha
				dm->water.watermode = 2; // amplitude
				dm->water.amplitude = GET_INT_ARG(2); // amplitude
				dm->water.wavelength = 40; // wavelength
				dm->water.wavespeed = 1.0; // waterspeed
				level->bglayers[level->numbglayers].bgspeedratio = 0; // moving
				level->bglayers[level->numbglayers].enabled = 1; // enabled

				if(dm->water.amplitude<1)dm->water.amplitude = 1;

				load_bglayer(GET_ARG(1), level->numbglayers);
				level->numbglayers++;
				break;
			
    default: abort();
    }
    return 0;
lCleanup:
    parser_error = errormessage;
    return -1;
}

static void reference_post_3(void) {
 int i; s_drawmethod *dm;
	if(level->numbglayers) {
		load_bglayer(NULL, 0); // initialize background height and width and looping
		
		for(i=1; i<level->numbglayers; i++){
			if(level->bglayers[i].zoffset == 1234567890){ // default water hack
				level->bglayers[i].zoffset = level->bglayers[0].height;
				dm = &(level->bglayers[i].drawmethod);
				if(level->rocking) {
					dm->water.watermode =3;
					dm->water.beginsize = 1.0;
					dm->water.endsize = 1 + level->bglayers[0].height/11.0;
					dm->water.perspective = 0;
					level->bglayers[i].bgspeedratio =2;
				}
			}
		}

	}

}
