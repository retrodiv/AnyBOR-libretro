/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Frontend-only regression: retain a valid buffer, deliberately request an
 * undersized capture, then behave like a caller that ignores false and loads
 * its complete allocation. Keep200 frames of untouched continuation between
 * refusal and a subsequent valid load. No core fault-injection hook. */
#ifndef OBOR_CAPTURE_FAILURE_PROBE_H
#define OBOR_CAPTURE_FAILURE_PROBE_H
static unsigned char *failed_capture_buffer;
static size_t failed_capture_size;
static int failed_capture_started, failed_capture_recovered;
static int capture_failure_after_frame(size_t (*capacity)(void),
                                      bool (*save)(void *,size_t),
                                      bool (*load)(const void *,size_t))
{
    const char *option=getenv("OBOR_FAILED_CAPTURE_AT");
    if(!option)return 1;
    char *end;
    long start=strtol(option,&end,10);
    if(!*option || *end || start<0 || start>INT_MAX-200)return 0;
    if(g_frame==start){
        failed_capture_size=capacity();
        if(failed_capture_size<16 || failed_capture_size>UINT32_MAX ||
           failed_capture_size>SIZE_MAX-16)return 0;
        failed_capture_buffer=malloc(failed_capture_size+16);
        if(!failed_capture_buffer)return 0;
        memset(failed_capture_buffer,0xa5,failed_capture_size+16);
        unsigned char *payload=failed_capture_buffer+8;
        if(!save(payload,failed_capture_size))return 0;
        uint32_t magic=0;
        memcpy(&magic,payload,4);
        if(magic!=UINT32_C(0x3153424f) && magic!=UINT32_C(0x3143424f))return 0;
        if(save(payload,4)){
            fprintf(stderr,"undersized failed-capture probe unexpectedly succeeded\n");return 0;
        }
        memcpy(&magic,payload,4);
        int stale_loaded=load(payload,failed_capture_size);
        if(magic || stale_loaded){
            fprintf(stderr,"failed capture left a stale frontend buffer: magic=0x%x load=%d\n",
                    (unsigned)magic,stale_loaded);return 0;
        }
        for(size_t i=0;i<8;i++)
            if(failed_capture_buffer[i]!=0xa5 ||
               failed_capture_buffer[failed_capture_size+8+i]!=0xa5)return 0;
        if(!save(payload,failed_capture_size))return 0;
        failed_capture_started=1;
        printf("failed_capture_invalidated=1 stale_load_refused=1 frame=%d\n",g_frame);
    }
    if(g_frame==start+200){
        if(!failed_capture_started || !load(failed_capture_buffer+8,failed_capture_size)){
            fprintf(stderr,"valid capture did not recover after failed capture/load\n");return 0;
        }
        failed_capture_recovered=1;
        free(failed_capture_buffer);failed_capture_buffer=NULL;
        printf("failed_capture_valid_recovery=1 continuation_frames=200\n");
    }
    return 1;
}
static int capture_failure_finish(void)
{
    int enabled=getenv("OBOR_FAILED_CAPTURE_AT")!=NULL;
    free(failed_capture_buffer);failed_capture_buffer=NULL;
    return !enabled || (failed_capture_started && failed_capture_recovered);
}
#endif
