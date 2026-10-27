"""Explicitly refuse unused native inline functions in isolated contracts.

This provides no renderer or VM implementation. Callers must bind the native
headers and declarations, and include a negative unexpected-call control.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def inline_refusals(unused_inline_declarations=None, *, forbidden_names=()):
    declarations=[] if unused_inline_declarations is None else unused_inline_declarations
    if not isinstance(declarations,list) or len(declarations)>128:
        raise ValueError('Bounded explicit unused native inline declarations required')
    refusal_definitions=[]
    names=set(forbidden_names)|{'main','Interpreter_Call','Interpreter_EvalInstruction'}
    for declaration in declarations:
        match=re.fullmatch(
            r'inline[ \t]+([A-Za-z_][A-Za-z_0-9 \t*]*[ \t*]+)'
            r'([A-Za-z_]\w*)\(([A-Za-z_0-9, \t*]*)\)[ \t]*;',
            declaration) if isinstance(declaration,str) and len(declaration)<=1024 else None
        if not match or match[2] in names:
            raise ValueError('Unique simple native inline declarations required')
        result,name,arguments=match.groups();names.add(name)
        if arguments.strip() not in ('','void'):
            for argument in arguments.split(','):
                if not re.fullmatch(r'[ \t]*[A-Za-z_][A-Za-z_0-9 \t*]*[ \t*]+'
                                    r'[A-Za-z_]\w*[ \t]*',argument):
                    raise ValueError('Native refusal fixture needs named simple arguments')
        else:
            arguments='void'
        refusal_definitions.append(result+name+'('+arguments+') {'+
            'fputs("Unexpected native inline call outside frame-storage contract\\n",stderr);abort();}')
    return '\n'.join(refusal_definitions)


def graphics_refusals(enabled=False):
    if type(enabled) is not bool:
        raise ValueError('Explicit native graphics-header declaration context required')
    # Some original headers expose inline raster declarations even when no
    # raster implementation is linked. This contract never executes raster
    # code. Define only explicit refusal fixtures, retaining the native types
    # and packing rather than suppressing compiler diagnostics globally.
    unused_graphics=''
    if enabled:
        unused_graphics=r'''
static void unexpected_raster_call(void) {
 fputs("Unexpected raster call outside frame-storage contract\n",stderr);abort();
}
#define REFUSE_RASTER(name) \
 void name(s_screen *dest,gfx_entry *src,int x,int y,int centerx,int centery,s_drawmethod *method) { \
 (void)dest;(void)src;(void)x;(void)y;(void)centerx;(void)centery;(void)method;unexpected_raster_call();}
REFUSE_RASTER(gfx_draw_rotate)
REFUSE_RASTER(gfx_draw_scale)
REFUSE_RASTER(gfx_draw_water)
REFUSE_RASTER(gfx_draw_plane)
#undef REFUSE_RASTER
void src_seek(int x,int y) {(void)x;(void)y;unexpected_raster_call();}
void dest_seek(int x,int y) {(void)x;(void)y;unexpected_raster_call();}
void src_line_inc(void) {unexpected_raster_call();}
void src_line_dec(void) {unexpected_raster_call();}
void src_inc(void) {unexpected_raster_call();}
void src_dec(void) {unexpected_raster_call();}
void dest_line_inc(void) {unexpected_raster_call();}
void dest_line_dec(void) {unexpected_raster_call();}
void dest_inc(void) {unexpected_raster_call();}
void dest_dec(void) {unexpected_raster_call();}
void write_pixel(void) {unexpected_raster_call();}
void init_gfx_global_draw_stuff(s_screen *dest,gfx_entry *src,s_drawmethod *method) {
 (void)dest;(void)src;(void)method;unexpected_raster_call();
}
'''
    return unused_graphics
