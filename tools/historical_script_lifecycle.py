"""Render source-defined script copy and disposal observations.

The original functions and declarations remain intact. Interpreter evaluation,
local-variable storage and variant callbacks are reduced, instrumented fixtures;
this is not an interpreter or a whole model/entity execution test.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


PARTS = {'script', 'container', 'alloc_script', 'Script_Init', 'Script_Copy',
         'Script_Clear', 'alloc_all_scripts', 'clear_all_scripts',
         'copy_all_scripts', 'free_all_scripts'}


def render(parts, *, pointer_container, allocation_magic, cleanup_safe, labels,
           includes='', support=''):
    if (not isinstance(parts, dict) or set(parts) != PARTS or any(not isinstance(v, str) or not v.strip()
                                  or len(v) > 32768 for v in parts.values())):
        raise ValueError('Exact bounded nonempty script source components required')
    if any(type(x) is not bool for x in (pointer_container, allocation_magic, cleanup_safe)):
        raise ValueError('Explicit source representation and cleanup expectations required')
    if any(not isinstance(x, str) or len(x) > 32768 for x in (includes, support)):
        raise ValueError('Bounded explicit include and support fragments required')
    if (not isinstance(labels, list) or not 0 < len(labels) <= 256
            or any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,127}', x)
                   for x in labels) or len(set(labels)) != len(labels)):
        raise ValueError('Unique bounded source identifiers required')
    if bool(re.search(r'alloc_all_scripts\s*\(\s*s_scripts\s*\*\s*\*',
                      parts['alloc_all_scripts'])) != pointer_container:
        raise ValueError('Source container representation differs')
    if bool(re.search(r'pscript->magic\s*=\s*script_magic', parts['alloc_script'])) != allocation_magic:
        raise ValueError('Source allocation magic differs')
    if not cleanup_safe and not pointer_container:
        raise ValueError('Unsafe cleanup requires an explicit pointer container')
    members = re.findall(r'\bScript\s*\*\s*(\w+)\s*;', parts['container'])
    if not 0 < len(members) <= 128 or len(set(members)) != len(members):
        raise ValueError('Bounded distinct script container members required')
    # Refuse a reduced declaration that silently drops or changes member types.
    body = re.search(r'\{([\s\S]*)\}', parts['container'])
    if body is None:
        raise ValueError('Complete script container declaration required')
    stripped = re.sub(r'/\*[\s\S]*?\*/|//[^\n]*', '', body[1])
    if re.sub(r'\s|Script\s*\*\s*\w+\s*;', '', stripped):
        raise ValueError('Container must contain only explicit script pointers')
    observation = {'status': 'PASS', 'sources': len(labels),
                   'pointer_container': pointer_container,
                   'allocation_magic': allocation_magic,
                   'source_cleanup_executed': cleanup_safe,
                   'slots': len(members)}
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
@INCLUDES@
typedef int32_t LONG;
enum {VT_EMPTY,VT_INTEGER};
#define FALSE 0
#define FAILED(x) ((x)<0)
#define script_magic ((int)0x73636f)
typedef struct {int vt;LONG lVal;} ScriptVariant;
typedef struct {void *pClearEntry,*pCurrentInstruction;int bReset;
 struct {char name[32];} theSymbolTable;} Interpreter;
@SCRIPT@
@CONTAINER@
static int max_script_vars=3,theFunctionList;
static const size_t scripts_membercount=sizeof(s_scripts)/sizeof(Script*);
static Script *pcurrentscript;
static unsigned evaluated,resets,interpreter_clears,local_clears,local_sets,local_unsets;
static int expected_method,last_method;
static Script *expected_script;
static void ScriptVariant_Init(ScriptVariant *v) {*v=(ScriptVariant){0};}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {v->vt=type;v->lVal=0;}
static void ScriptVariant_Clear(ScriptVariant *v) {*v=(ScriptVariant){0};}
static void Interpreter_Init(Interpreter *p,char *name,int *list) {
 assert(list==&theFunctionList);*p=(Interpreter){0};
 assert(strlen(name)<sizeof(p->theSymbolTable.name));strcpy(p->theSymbolTable.name,name);
}
static void Interpreter_Clear(Interpreter *p) {assert(p);++interpreter_clears;}
static void Interpreter_Reset(Interpreter *p) {
 assert(p && pcurrentscript==expected_script);++resets;p->bReset=1;
}
static int Interpreter_EvaluateCall(Interpreter *p) {
 assert(p && pcurrentscript==expected_script);
 assert(p->pCurrentInstruction==p->pClearEntry && p->pClearEntry);
 assert(last_method==expected_method);++evaluated;return 0;
}
static void Script_Set_Local_Variant(Script *s,const char *name,ScriptVariant *v) {
 assert(s==pcurrentscript && !strcmp(name,"localclear"));
 if(v->vt==VT_INTEGER) {last_method=(int)v->lVal;++local_sets;}
 else {assert(v->vt==VT_EMPTY);++local_unsets;}
}
static void Script_Local_Clear(Script *s) {assert(s);++local_clears;}
static void shutdown(int status,const char *format,...) {
 (void)status;(void)format;assert(!"Unexpected interpreter evaluation failure");abort();
}
void Script_Clear(Script*,int);
@SUPPORT@
@ALLOC@
@INIT@
@COPY@
@CLEAR@
@ALLOC_ALL@
@CLEAR_ALL@
@COPY_ALL@
@FREE_ALL@
static Script **slots(s_scripts *s) {return (Script**)s;}
static void reset_counts(void) {
 evaluated=resets=interpreter_clears=local_clears=local_sets=local_unsets=0;
 expected_script=NULL;expected_method=last_method=-1;
}
static void enable_callback(Script *s,int method) {
 static int entry;expected_script=s;expected_method=method;
 s->pinterpreter->pClearEntry=&entry;
}
static void initialize(Script *s,const char *comment) {
 Script_Init(s,"fixture",(char*)comment,0);
 assert(s->initialized==1 && s->interpreterowner==1 && s->pinterpreter);
 assert(!strcmp(s->pinterpreter->theSymbolTable.name,"fixture"));
 assert((comment==NULL)==(s->comment==NULL));
 if(comment) assert(!strcmp(s->comment,comment) && s->comment!=comment);
}
static void direct_checks(void) {
 for(int count=0;count<=3;count+=3) {
  max_script_vars=count;
  Script s;memset(&s,0xa5,sizeof(s));
  Script_Init(&s,NULL,NULL,1);
  assert(s.magic==script_magic && !s.initialized && !s.pinterpreter && !s.comment);
  assert((s.vars!=NULL)==(count>0));
  for(int i=0;i<count;++i) assert(s.vars[i].vt==VT_EMPTY);
  ScriptVariant *vars=s.vars;
  Script_Init(&s,"",NULL,0);assert(s.vars==vars && !s.initialized);
  initialize(&s,"owned comment");assert(s.vars==vars);
  reset_counts();Script saved={0};pcurrentscript=&saved;
  enable_callback(&s,1);Script_Clear(&s,1);
  assert(pcurrentscript==&saved && !s.initialized && s.vars==vars);
  assert(evaluated==1 && resets==1 && local_sets==1 && local_unsets==1);
  assert(interpreter_clears==1 && local_clears==1 && !s.comment && !s.pinterpreter);
  reset_counts();Script_Clear(&s,2);
  assert(!s.vars && !s.initialized && evaluated==0 && interpreter_clears==0);
 }
 max_script_vars=3;
 for(int method=0;method<=2;++method) for(int comment=0;comment<=1;++comment) {
  Script *owner=alloc_script(),*copy=alloc_script(),*other=alloc_script();
  assert(owner && copy && other && owner->vars && copy->vars && other->vars);
  assert(owner->magic==(@MAGIC@?script_magic:0));
  assert(owner->vars!=copy->vars && owner->vars!=other->vars && copy->vars!=other->vars);
  initialize(owner,comment?"shared comment":NULL);
  ScriptVariant *copy_vars=copy->vars;
  copy->vars[0]=(ScriptVariant){VT_INTEGER,91};
  reset_counts();Script_Copy(copy,other,method);
  assert(!copy->initialized && copy->vars==copy_vars && copy->vars[0].lVal==91);
  Script_Copy(copy,owner,method);
  assert(copy->initialized && !copy->interpreterowner && copy->vars==copy_vars);
  assert(copy->pinterpreter==owner->pinterpreter && copy->comment==owner->comment);
  assert(copy->vars[0].lVal==91 && !owner->vars[0].lVal);
  Script saved={0};pcurrentscript=&saved;enable_callback(copy,method);
  Script_Clear(copy,method);
  assert(pcurrentscript==&saved && !copy->initialized);
  assert(copy->vars==(method==2?NULL:copy_vars));
  assert(evaluated==1 && resets==1 && local_sets==1 && local_unsets==1);
  assert(local_clears==(unsigned)(method!=0) && interpreter_clears==0);
  assert(owner->initialized && owner->interpreterowner && owner->pinterpreter->bReset==0);
  if(comment) assert(!strcmp(owner->comment,"shared comment"));
  owner->pinterpreter->pClearEntry=NULL;Script_Clear(owner,2);
  assert(interpreter_clears==1 && !owner->vars);
  Script_Clear(copy,2);Script_Clear(other,2);
  free(copy);free(other);free(owner);
 }
 // Replacing an initialized destination clears its owned interpreter while
 // retaining independent variables, then borrows the source payload.
 for(int method=0;method<=1;++method) {
  Script *src=alloc_script(),*dest=alloc_script();initialize(src,"source");initialize(dest,"old");
  ScriptVariant *vars=dest->vars;reset_counts();
  Script_Copy(dest,src,method);
  assert(interpreter_clears==1 && local_clears==(unsigned)method);
  assert(dest->vars==vars && dest->comment==src->comment && !dest->interpreterowner);
  Script_Clear(dest,2);Script_Clear(src,2);free(dest);free(src);
 }
 pcurrentscript=NULL;
}
static void release_container(s_scripts **s) {
 @DISPOSE@
}
static void container_checks(void) {
 @CONTAINER_INIT@
 assert(parent && child && parent!=child);
 @ALLOC_CONTAINERS@
 for(size_t i=0;i<scripts_membercount;++i) {
  assert(slots(parent)[i] && slots(child)[i] && slots(parent)[i]!=slots(child)[i]);
  initialize(slots(parent)[i],"parent");
 }
 reset_counts();copy_all_scripts(parent,child,1);
 for(size_t i=0;i<scripts_membercount;++i) {
  Script *p=slots(parent)[i],*c=slots(child)[i];
  assert(p->vars!=c->vars && p->pinterpreter==c->pinterpreter && p->comment==c->comment);
  assert(p->interpreterowner && !c->interpreterowner);
 }
 clear_all_scripts(child,1);assert(interpreter_clears==0 && local_clears==scripts_membercount);
 for(size_t i=0;i<scripts_membercount;++i) assert(!slots(child)[i]->initialized && slots(child)[i]->vars);
 copy_all_scripts(parent,child,1);clear_all_scripts(child,2);release_container(&child);
 assert(interpreter_clears==0);
 for(size_t i=0;i<scripts_membercount;++i) assert(slots(parent)[i]->initialized);
 clear_all_scripts(parent,2);release_container(&parent);
 assert(interpreter_clears==scripts_membercount);
 @CONTAINER_END@
}
int main(void) {
 @CHECKS@
 puts(@OBSERVATION@);return 0;
}
'''
    if pointer_container:
        init = 's_scripts *parent=NULL,*child=NULL;\nalloc_all_scripts(&parent);alloc_all_scripts(&child);'
        alloc = ('s_scripts *saved=parent;Script *first=slots(parent)[0];'
                 'alloc_all_scripts(&parent);assert(parent==saved && slots(parent)[0]==first);')
        end = 'assert(!parent && !child);'
        dispose = ('free_all_scripts(s);' if cleanup_safe else
                   'for(size_t i=0;i<scripts_membercount;++i) {free(slots(*s)[i]);}\nfree(*s);*s=NULL;')
    else:
        init = 's_scripts p={0},c={0};s_scripts *parent=&p,*child=&c;'
        alloc = 'alloc_all_scripts(parent);alloc_all_scripts(child);'
        end = 'for(size_t i=0;i<scripts_membercount;++i) assert(!slots(parent)[i] && !slots(child)[i]);'
        dispose = 'free_all_scripts(*s);'
    values = {'SCRIPT': parts['script'], 'CONTAINER': parts['container'],
              'INCLUDES': includes, 'SUPPORT': support,
              'ALLOC': parts['alloc_script'], 'INIT': parts['Script_Init'],
              'COPY': parts['Script_Copy'], 'CLEAR': parts['Script_Clear'],
              'ALLOC_ALL': parts['alloc_all_scripts'], 'CLEAR_ALL': parts['clear_all_scripts'],
              'COPY_ALL': parts['copy_all_scripts'], 'FREE_ALL': parts['free_all_scripts'],
              'MAGIC': str(int(allocation_magic)), 'DISPOSE': dispose,
              'CONTAINER_INIT': init, 'ALLOC_CONTAINERS': alloc, 'CONTAINER_END': end,
              'CHECKS': '\n'.join('direct_checks();container_checks();' for _ in labels),
              'OBSERVATION': json.dumps(json.dumps(observation))}
    return re.sub(r'@('+'|'.join(values)+r')@', lambda m: values[m[1]], code)


def render_release_observation(parts, *, payload_retained, **options):
    """Observe release choices with storage retained until the observation ends.

    This records ownership decisions; it deliberately does not execute against
    actually retired storage or establish that such an order is source-defined.
    """
    if type(payload_retained) is not bool:
        raise ValueError('Explicit payload retention expectation required')
    text = render(parts, **options)
    tracker = r'''
static void *released[128];
static unsigned released_count;
static int release_recorded(void *p) {
 for(unsigned i=0;i<released_count;++i) if(released[i]==p) return 1;
 return 0;
}
static void recorded_free(void *p) {
 if(!p) return;
 assert(!release_recorded(p) && released_count<128);
 released[released_count++]=p;
}
#define free recorded_free
'''
    first, last = parts['alloc_script'], parts['free_all_scripts']
    if text.count(first) != 1 or text.count(last) != 1:
        raise ValueError('Ambiguous allocation or disposal source placement')
    text = text.replace(first, tracker+first, 1).replace(last, last+'\n#undef free\n', 1)
    # The test-owned main is replaced, never a source function or declaration.
    marker = 'int main(void) {'
    if text.count(marker) != 1:
        raise ValueError('Ambiguous authored main')
    observation = {'status': 'PASS', 'sources': len(options['labels']),
                   'payload_retained_until_last_reference': payload_retained,
                   'storage_physically_retained_during_observation': True}
    check = r'''
static void release_observation(void) {
 Script *owner=alloc_script(),*borrower=alloc_script();
 initialize(owner,"shared payload");Script_Copy(borrower,owner,1);
 Interpreter *interpreter=owner->pinterpreter;char *comment=owner->comment;
 assert(interpreter && comment && borrower->pinterpreter==interpreter && borrower->comment==comment);
 reset_counts();released_count=0;
 Script_Clear(owner,2);
 assert(borrower->initialized && borrower->pinterpreter==interpreter && borrower->comment==comment);
 assert(release_recorded(interpreter)==!@RETAINED@ && release_recorded(comment)==!@RETAINED@);
 assert(interpreter_clears==(unsigned)!@RETAINED@);
 // Recorded releases keep their storage alive here. This is an observation of
 // the source's disposal choices, not a safe-execution oracle for this order.
 Script_Clear(borrower,2);
 assert(release_recorded(interpreter) && release_recorded(comment) && interpreter_clears==1);
 assert(!owner->vars && !borrower->vars);
 free(owner);free(borrower);
 for(unsigned i=0;i<released_count;++i) free(released[i]);
 released_count=0;
}
int main(void) {
 @CHECKS@
 puts(@OBSERVATION@);return 0;
}
'''
    values = {'RETAINED': str(int(payload_retained)),
              'CHECKS': '\n'.join('release_observation();' for _ in options['labels']),
              'OBSERVATION': json.dumps(json.dumps(observation))}
    return text[:text.index(marker)] + re.sub(r'@('+'|'.join(values)+r')@',
                                            lambda m: values[m[1]], check)


def render_owned(parts, **options):
    """Execute real releases in both orders against a prepared implementation.

    The original interpreter/local/variant fixtures remain reduced. No allocator
    interception or deferred physical release is used in these ownership checks.
    """
    text = render(parts, **options)
    marker = 'int main(void) {'
    if text.count(marker) != 1:
        raise ValueError('Ambiguous authored main')
    checks = r'''
static void owned_order_checks(void) {
 for(int method=0;method<=2;++method) for(int owner_first=0;owner_first<=1;++owner_first) {
  Script *owner=alloc_script(),*copy=alloc_script();initialize(owner,"shared");
  Script_Copy(copy,owner,1);Interpreter *interpreter=owner->pinterpreter;
  char *comment=owner->comment;ScriptVariant *owner_vars=owner->vars,*copy_vars=copy->vars;
  owner_vars[0]=(ScriptVariant){VT_INTEGER,31};copy_vars[0]=(ScriptVariant){VT_INTEGER,47};
  assert(owner->obor_interpreter==copy->obor_interpreter);
  assert(owner->obor_comment==copy->obor_comment);
  assert(owner->obor_interpreter->references==2 && owner->obor_comment->references==2);
  Script saved={0};pcurrentscript=&saved;reset_counts();
  Script *first=owner_first?owner:copy,*last=owner_first?copy:owner;
  enable_callback(first,method);Script_Clear(first,method);
  assert(pcurrentscript==&saved && !first->initialized && !first->obor_interpreter && !first->obor_comment);
  assert(interpreter_clears==0 && evaluated==1 && local_clears==(unsigned)(method!=0));
  assert(last->initialized && last->pinterpreter==interpreter && last->comment==comment);
  assert(!strcmp(comment,"shared") && interpreter->bReset==0);
  assert(last->obor_interpreter->references==1 && last->obor_comment->references==1);
  assert(last->vars==(owner_first?copy_vars:owner_vars));
  assert(last->vars[0].lVal==(owner_first?47:31));
  enable_callback(last,method);Script_Clear(last,method);
  assert(pcurrentscript==&saved && interpreter_clears==1 && evaluated==2);
  assert(local_sets==2 && local_unsets==2 && local_clears==2*(unsigned)(method!=0));
  Script_Clear(first,2);Script_Clear(last,2);free(owner);free(copy);
 }
 pcurrentscript=NULL;
}
static void owned_reinitialization_checks(void) {
 for(int replace_comment=0;replace_comment<=1;++replace_comment) {
  Script *owner=alloc_script(),*copy=alloc_script();initialize(owner,"kept comment");
  Script_Copy(copy,owner,1);Interpreter *old=owner->pinterpreter;char *comment=owner->comment;
  ScriptVariant *vars=owner->vars;owner->vars[0]=(ScriptVariant){VT_INTEGER,73};reset_counts();
  Script_Init(owner,"replacement",replace_comment?"replacement comment":NULL,0);
  assert(!evaluated && !interpreter_clears && owner->vars==vars && owner->vars[0].lVal==73);
  assert(owner->initialized && owner->interpreterowner && owner->pinterpreter!=old);
  assert(!strcmp(owner->pinterpreter->theSymbolTable.name,"replacement"));
  assert(copy->pinterpreter==old && copy->comment==comment && !strcmp(copy->comment,"kept comment"));
  assert(owner->comment==(replace_comment?owner->obor_comment->value:comment));
  assert(!strcmp(owner->comment,replace_comment?"replacement comment":"kept comment"));
  if(replace_comment) assert(owner->comment!=comment);
  else assert(owner->obor_comment==copy->obor_comment && owner->obor_comment->references==2);
  Interpreter *current=owner->pinterpreter;obor_script_reference *reference=owner->obor_interpreter;
  Script_Init(owner,NULL,NULL,0);Script_Init(owner,"",NULL,0);
  assert(owner->pinterpreter==current && owner->obor_interpreter==reference && !evaluated);
  enable_callback(copy,2);Script_Clear(copy,2);assert(interpreter_clears==1);
  assert(owner->initialized && !strcmp(owner->comment,replace_comment?"replacement comment":"kept comment"));
  enable_callback(owner,2);Script_Clear(owner,2);assert(interpreter_clears==2);
  free(owner);free(copy);
 }
 pcurrentscript=NULL;
}
static void owned_replacement_checks(void) {
 for(int method=0;method<=2;++method) {
  Script *src=alloc_script(),*dest=alloc_script(),*oldcopy=alloc_script();
  initialize(src,"source");initialize(dest,"destination");Script_Copy(oldcopy,dest,1);
  Interpreter *old=dest->pinterpreter;ScriptVariant *vars=dest->vars;
  reset_counts();enable_callback(dest,method);Script_Copy(dest,src,method);
  assert(evaluated==1 && !interpreter_clears && !dest->interpreterowner);
  assert(dest->pinterpreter==src->pinterpreter && dest->comment==src->comment);
  assert(dest->vars==(method==2?NULL:vars) && oldcopy->pinterpreter==old);
  assert(!strcmp(oldcopy->comment,"destination"));
  enable_callback(oldcopy,2);Script_Clear(oldcopy,2);assert(interpreter_clears==1);
  Script_Clear(dest,2);Script_Clear(src,2);assert(interpreter_clears==2);
  free(oldcopy);free(dest);free(src);
 }
 Script *script=alloc_script();initialize(script,NULL);
 Interpreter *interpreter=script->pinterpreter;reset_counts();
 Script_Copy(script,script,2);Script_Copy(NULL,script,1);Script_Copy(script,NULL,1);
 assert(script->pinterpreter==interpreter && script->initialized && !interpreter_clears && !evaluated);
 Script_Clear(script,2);assert(interpreter_clears==1);free(script);
 pcurrentscript=NULL;
}
int main(void) {
 @CHECKS@
 puts(@OBSERVATION@);return 0;
}
'''
    values = {'CHECKS': '\n'.join('direct_checks();container_checks();owned_order_checks();'
                                  'owned_reinitialization_checks();owned_replacement_checks();'
                                  for _ in options['labels']),
              'OBSERVATION': json.dumps(json.dumps({'status': 'PASS',
                  'sources': len(options['labels']), 'both_disposal_orders': True,
                  'independent_replacement': True, 'real_storage_release': True}))}
    return text[:text.index(marker)] + re.sub(r'@('+'|'.join(values)+r')@',
                                            lambda m: values[m[1]], checks)
