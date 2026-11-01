/* Actual image-reference ownership functions with controlled image providers.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#undef free
static s_level owner_room;
static s_screen **owner_slot,*owner_live[2];
static unsigned char owner_palette[1024],owner_external_palette[1024];
static int owner_open_ok,owner_alloc_ok,owner_read_ok,owner_assertion,owner_explicit;
static int owner_opens,owner_allocs,owner_reads,owner_closes,owner_frees,owner_active;
static int owner_res[2]={2,3};
static jmp_buf owner_stop;
static s_screen *owner_get(void) {s_screen *value;memcpy(&value,(const void *)owner_slot,sizeof(value));return value;}
static void owner_put(s_screen *value) {memcpy((void *)owner_slot,&value,sizeof(value));}
static void owner_free(void *pointer) {
 int found=0;
 for(int i=0;i<2;++i)if(owner_live[i]==pointer){owner_live[i]=NULL;found=1;break;}
 assert(pointer && found && owner_active>0);--owner_active;++owner_frees;free(pointer);
}
static s_screen *owner_allocscreen(int width,int height,int format) {
 ++owner_allocs;if(!owner_alloc_ok)return NULL;
 s_screen *value=calloc(1,sizeof(*value)+64);assert(value);
 value->width=width;value->height=height;value->pixelformat=format;value->palette=owner_palette;
 int slot=owner_live[0]?1:0;assert(!owner_live[slot]);owner_live[slot]=value;++owner_active;return value;
}
static int owner_openimage(char *name,char *pack) {
 assert(!strcmp(name,"fixture.img") && !strcmp(pack,"fixture.pak"));++owner_opens;return owner_open_ok;
}
static int owner_readimage(unsigned char *pixels,unsigned char *palette,int width,int height) {
 s_screen *value=owner_get();assert(value && owner_active==1 && pixels==value->data && width==2 && height==3);
 assert(palette==(owner_explicit?owner_external_palette:owner_palette));++owner_reads;
 if(owner_read_ok)memset(pixels,42,6);
 return owner_read_ok;
}
static void owner_closeimage(void) {++owner_closes;}
static void owner_image_assert(int site) {
 assert(!owner_get() && !owner_active);owner_assertion=site;longjmp(owner_stop,1);
}
#undef free
#define free owner_free
#define freescreen owner_freescreen
@OWNED_FREE@
#undef free
#undef freescreen
#define freescreen owner_freescreen
#define loadscreen owner_loadscreen
#define allocscreen owner_allocscreen
#define openimage owner_openimage
#define readimage owner_readimage
#define closeimage owner_closeimage
#define obor_early_image_assert owner_image_assert
#define res owner_res
@OWNED_LOAD@
#undef freescreen
#undef loadscreen
#undef allocscreen
#undef openimage
#undef readimage
#undef closeimage
#undef obor_early_image_assert
#undef res
static void owner_checks(void) {
 s_screen **slots[]={&owner_room.bglayers[0].screen,&owner_room.bglayers[1].screen,
                    &owner_room.fglayers[0].screen,&owner_room.fglayers[1].screen};
 int formats[]={PIXEL_8,PIXEL_x8,PIXEL_16,PIXEL_32};
 for(unsigned place=0;place<sizeof(slots)/sizeof(*slots);++place)
 for(unsigned f=0;f<sizeof(formats)/sizeof(*formats);++f)
 for(int existing=0;existing<2;++existing)for(int outcome=0;outcome<4;++outcome)
 for(owner_explicit=0;owner_explicit<2;++owner_explicit) {
  owner_slot=slots[place];owner_put(NULL);assert(!owner_active);
  owner_alloc_ok=1;
  if(existing)owner_put(owner_allocscreen(1,1,formats[f]));
  owner_open_ok=outcome!=1;owner_alloc_ok=outcome!=2;owner_read_ok=outcome!=3;
  owner_opens=owner_allocs=owner_reads=owner_closes=owner_frees=0;owner_assertion=-1;
  int status=-1;
  if(!setjmp(owner_stop))status=owner_loadscreen("fixture.img","fixture.pak",
      owner_explicit?owner_external_palette:NULL,formats[f],owner_slot);
  assert(owner_opens==1);
  assert(owner_allocs==(outcome!=1));assert(owner_reads==(outcome==0 || outcome==3));
  assert(owner_closes==(outcome!=1));
  assert(owner_assertion==(outcome==2?0:outcome==3?1:-1));
  if(!outcome) {
   s_screen *value=owner_get();assert(status==1 && value && owner_active==1 && value->pixelformat==formats[f]);
   assert(value->width==2 && value->height==3);
   for(int i=0;i<6;++i)assert(value->data[i]==42);
  } else {assert(!owner_get() && !owner_active);if(outcome==1)assert(status==0);}
  assert(owner_frees==existing+(outcome==3));
  owner_freescreen(owner_slot);assert(!owner_get() && !owner_active);
 }
 owner_freescreen(NULL);
 assert(!owner_loadscreen("fixture.img","fixture.pak",NULL,PIXEL_8,NULL));
}
