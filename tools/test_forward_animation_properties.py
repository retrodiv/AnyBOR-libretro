"""Execute historical animation property bodies through native API bindings.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers
from test_early_system_callbacks import block

FIXTURE=Path(__file__).with_name('fixtures')/'profile-forward-animation-properties-contracts.json'


def program(data,engine):
    script=(engine/'openborscript.c').read_text()
    core=(engine/'openbor.c').read_text()
    variants=(engine/'source/scriptlib/ScriptVariant.c').read_text()
    methods='\n'.join(function(script,name) for name in
        ('Script_GetFunctionName','Script_GetStringMapFunction','Script_LoadSystemFunctions'))
    selected={'openbor_getanimationproperty','openbor_changeanimationproperty','mapstrings_animationproperty'}
    symbols=set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)',methods))
    if not selected<=symbols or not 8<=len(symbols)<=512:
        raise ValueError('Complete bounded native registry required')
    unused={name:'unselected_'+name for name in symbols-selected}
    properties=data['scalar_properties']
    field_set=[]
    field_get=[]
    for index,row in enumerate(properties):
        if not re.fullmatch(r'[a-z_]+',row['field']):
            raise ValueError('Explicit scalar field required')
        field_set.append('case %d: target.%s=value;break;'%(index,row['field']))
        field_get.append('case %d: return target.%s;'%(index,row['field']))
    frame_set=[]
    frame_get=[]
    frame_rows=[]
    for index,row in enumerate(data['frame_properties']):
        if not re.fullmatch(r'[a-z_]+(?:\[[0-7]\])*(?:\.[a-z_]+)?',row['field']):
            raise ValueError('Explicit owned frame fixture field required')
        if not re.fullmatch(r'[a-z_]+',row['member']):
            raise ValueError('Explicit native frame table required')
        frame_set.append('case %d: %s=value;break;'%(index,row['field']))
        frame_get.append('case %d: return %s;'%(index,row['field']))
        frame_rows.append('{%d,%s,%s,%s,%d,%d,%d,%s,%s,%.17g,%s,%s}'%(
            row['min_revision'],json.dumps(row['property']),json.dumps(row['leaf']),
            'VT_DECIMAL' if row['result_type']=='decimal' else 'VT_INTEGER',
            row['search'],row['zero_refusal'],row['zero_get'],json.dumps(row['get_frame_error']),
            json.dumps(row['set_frame_error']),row['written'],
            'INT_MIN' if row['absent_get'] is None else str(row['absent_get']),
            'INT_MIN' if row['absent_set'] is None else str(row['absent_set'])))
    contexts=[]
    for row in data['sources']:
        indices=[row['scalar_indices'][p['name']] for p in properties] if row['rich'] or row['partial'] else [0]*len(properties)
        contexts.append('{%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,{%s},%s,%s,%s}'%(row['revision'],row['rich'],row['change_binding'],
            row.get('attack_index',0),row.get('type_index',0),row.get('fastattack_exact',False),
            row['spritea'],
            row['rotation_float'],row['partial'],row['draw_full'],row['classic_revised'],row['classic_clears'],
            ','.join(map(str,indices)),json.dumps(row['getter_argument_error']),
            json.dumps(row.get('attack_argument_error','')),json.dumps(row['dropv_trace'])))
    old_start=script.index('typedef enum animationprop_enum')
    new_start=script.index('/* Native animation property bodies',old_start)
    new_end=script.index('static int obor_forward_mapstrings_animationproperty(',new_start)
    macro_start=script.index('#define MAPSTRINGS(')
    pieces=dict(
        HEADER='#include '+json.dumps(str(engine/'openbor.h')),
        LIST='#include '+json.dumps(str(engine/'source/scriptlib/List.c')),
        NAMESPACES=script[old_start:new_end],
        SEARCH=function((engine/'source/utils.c').read_text(),'searchList'),
        VARIANTS='\n'.join(function(variants,name) for name in
            ('ScriptVariant_Init','ScriptVariant_Clear','ScriptVariant_ChangeType',
             'ScriptVariant_DecimalValue','ScriptVariant_IntegerValue','StrCache_GetIfPresent')),
        CACHE_TYPE=re.search(r'typedef struct\s*\{[^}]+\}\s*Varstr;',variants)[0],
        MACRO=script[macro_start:script.index('\n\n',macro_start)],
        ACTOR_SCOPE=re.search(r'struct obor_animation_actor_scope\s*\{[^}]+\};\s*'
            r'static struct obor_animation_actor_scope \*obor_animation_actors;',core)[0],
        OWNERS='\n'.join(function(core,name) for name in
            ('obor_script_animation_owner','obor_script_current_animation','obor_script_model_animation')),
        GUARDS=script[script.index('/* Checked native animation argument access'):
            script.index('static HRESULT obor_forward_changeanimationproperty_impl(')],
        FRAME_FUNCTIONS='\n'.join(function(core,name) for name in
            ('obor_animation_alloc_table','obor_animation_reserve_frames','obor_animation_set_numframes')),
        APIS='\n'.join(function(script,name) for name in
            ('obor_forward_mapstrings_animationproperty','obor_forward_changeanimationproperty_impl',
             'obor_forward_getanimationproperty_impl','obor_forward_animation_dispatch',
             'openbor_changeanimationproperty','obor_forward_getanimationproperty',
             'mapstrings_animationproperty','openbor_getanimationproperty')),
        STUBS='\n'.join('static void '+name+'(void){}' for name in sorted(unused.values())),
        METHODS=rename_identifiers(methods,unused),
        CONTEXTS=','.join(contexts),
        PROPERTIES=','.join('{%s,%.17g,%.17g,%s,%.17g}'%(json.dumps(row['name']),
            row['input'],row['expected_field'],
            'VT_DECIMAL' if row['result_type']=='decimal' else 'VT_INTEGER',row['expected_get'])
            for row in properties),
        SET_FIELD='\n'.join(field_set),GET_FIELD='\n'.join(field_get),
        OWNER_CASES=','.join(json.dumps(name) for name in data['owner_cases']),
        MISSING_ROOTS=','.join(json.dumps(name) for name in data['missing_arg_roots']),
        EXTRA_COUNTS=','.join(str(n) for n in data['extra_argument_counts']))
    pieces.update(FRAME_CASES=','.join(frame_rows),
        SET_FRAME_FIELD='\n'.join(frame_set),GET_FRAME_FIELD='\n'.join(frame_get),
        FRAME_OWNERS='\n'.join('case %d:return target.%s;'%(index,row['member'])
                              for index,row in enumerate(data['frame_properties'])),
        SET_FRAME_OWNER='\n'.join('case %d:target.%s=value;return;'%(index,row['member'])
                                 for index,row in enumerate(data['frame_properties'])),
        FRAME_STRIDES='\n'.join('case %d:return sizeof(*target.%s);'%(index,row['member'])
                               for index,row in enumerate(data['frame_properties'])))
    fixed_set=[];fixed_get=[];fixed_rows=[]
    for index,row in enumerate(data['fixed_properties']):
        if not re.fullmatch(r'[a-z_]+\[[0-4]\]',row['field']) or not re.fullmatch(r'[a-z_]+',row['member']):
            raise ValueError('Explicit fixed-record fixture field required')
        fixed_set.append('case %d:%s=value;return;'%(index,row['field']))
        fixed_get.append('case %d:return %s;'%(index,row['field']))
        fixed_rows.append('{%s,%s,%s,%.17g}'%(json.dumps(row['property']),json.dumps(row['leaf']),
            'VT_DECIMAL' if row['result_type']=='decimal' else 'VT_INTEGER',row['written']))
    pieces.update(FIXED_CASES=','.join(fixed_rows),SET_FIXED_FIELD='\n'.join(fixed_set),
        GET_FIXED_FIELD='\n'.join(fixed_get),
        FIXED_OWNERS='\n'.join('case %d:return target.%s;'%(index,row['member']) for index,row in enumerate(data['fixed_properties'])),
        SET_FIXED_OWNER='\n'.join('case %d:target.%s=value;return;'%(index,row['member']) for index,row in enumerate(data['fixed_properties'])),
        FIXED_SHORT='\n'.join('case %d:return %d*sizeof(*target.%s);'%(index,row['index'],row['member']) for index,row in enumerate(data['fixed_properties'])),
        SPRITE_OWNERS=','.join(json.dumps(name) for name in data['sprite_owner_cases']))
    draw_start=re.search(r'(?m)^enum[ \t]+drawmethod_enum\s*\{',script)[0]
    draw_start=script.index(draw_start)
    draw_end=script.index('static int obor_drawmethod_property_native(')
    pieces.update(DRAW_NAMESPACE=script[draw_start:draw_end],
        DRAW_APIS='\n'.join(function(script,name) for name in
            ('obor_drawmethod_property_native','mapstrings_drawmethodproperty',
             'openbor_changedrawmethod','openbor_setdrawmethod')),
        ROTATION_LAYOUT=data['rotation_layout_control'])
    def decimal(value):
        text=format(value,'.17g')
        return text if any(c in text for c in '.eE') else text+'.0'
    pieces['ROTATION_VALUES']=','.join('{'+','.join(decimal(row[key]) for key in
        ('value','integer','floating','integer_mirror','floating_mirror',
         'integer_normalized','floating_normalized','legacy_normalized',
         'parser_integer','parser_floating'))+'}'
        for row in data['rotation_values'])
    routes=[]
    for path in ('source/gamelib/screen.c','source/gamelib/sprite.c'):
        text=(engine/path).read_text()
        matches=re.findall(r'else if\((obor_drawmethod_rotation\(drawmethod\))\)',text)
        if len(matches)!=1:raise ValueError('One native rotation dispatch predicate required')
        routes.append(matches[0])
    pieces.update(SCREEN_ROTATION_ROUTE=routes[0],SPRITE_ROTATION_ROUTE=routes[1])
    parser=function(core,'load_cached_model')
    positions=[]
    for slot in (9,2):
        expression=r'\(void\)obor_drawmethod_store_rotation\(&drawmethod, GET_INT_ARG\('+str(slot)+r'\)\);'
        matches=list(re.finditer(expression,parser))
        if len(matches)!=1:raise ValueError('One native parser rotation write required')
        positions.append(matches[0][0])
    normal=block(parser,parser.index('if(obor_drawmethod_rotation(&drawmethod))'))
    mirror=block(core,core.index('if(drawmethod->fliprotate && obor_drawmethod_rotation(drawmethod))'))
    copies=re.findall(r'obor_drawmethod_copy_rotation\(&shadowmethod, drawmethod\);',core)
    if len(copies)!=1:raise ValueError('One native shadow rotation copy required')
    pieces.update(PARSER_ROTATION_FIRST=positions[0],PARSER_ROTATION_SECOND=positions[1],
        PARSER_ROTATION_NORMALIZE=normal,NATIVE_ROTATION_MIRROR=mirror,NATIVE_ROTATION_COPY=copies[0])
    numeric=[];numeric_values=[];numeric_args=[];numeric_set=[];numeric_get=[]
    for index,row in enumerate(data['numeric_properties']):
        field=row['field']
        if not re.fullmatch(r'(?:hit|target|movement|fixed_spawn|fixed_summon)(?:\[[0-5]\])?(?:\.[a-z_]+(?:\[[0-5]\])?)*',field):
            raise ValueError('Explicit numeric native field required')
        start=len(numeric_values)
        for value in row['values']:
            numeric_values.append('{%s,%s,%s,%d}'%(decimal(value['input']),decimal(value['stored']),decimal(value['get']),value['get_refused']))
        numeric.append('{%d,%d,%d,%d,%d,%s}'%(row['min_revision'],start,len(row['values']),row['conversion']=='unsigned',
            row['conversion']=='signed-float' and row['result_type']=='integer',
            'VT_DECIMAL' if row['result_type']=='decimal' else 'VT_INTEGER'))
        statements=[]
        for position,arg in enumerate(row['arguments'],2):
            if isinstance(arg,str):statements.append('text_value(values+%d,%d,%s);'%(position,position,json.dumps(arg)))
            elif type(arg) is int:statements.append('values[%d].vt=VT_INTEGER;values[%d].lVal=%d;'%(position,position,arg))
            else:raise ValueError('Typed numeric argument required')
        numeric_args.append('case %d:%s return %d;'%(index,''.join(statements),len(row['arguments'])+2))
        numeric_set.append('case %d:%s=value;return;'%(index,field))
        numeric_get.append('case %d:return %s;'%(index,field))
    pieces.update(NUMERIC_FIELDS=','.join(numeric),NUMERIC_VALUES=','.join(numeric_values),
        NUMERIC_ARGS='\n'.join(numeric_args),NUMERIC_SET='\n'.join(numeric_set),NUMERIC_GET='\n'.join(numeric_get),
        WAVE_VALUES=','.join('{%s,%s,%d,%d}'%(decimal(row['input']),decimal(row['speed']),row['expected'],row['refused']) for row in data['wave_values']))
    records=[];record_args=[];record_set=[];record_get=[]
    for index,row in enumerate(data['record_properties']):
        field=row['field']
        if not re.fullmatch(r'(?:hit|target|drawing)(?:\[[0-2]\])?(?:\.[a-z_]+)*',field):
            raise ValueError('Explicit compound native field required')
        statements=[]
        for position,arg in enumerate(row['arguments'],2):
            if isinstance(arg,str):statements.append('text_value(values+%d,%d,%s);'%(position,position,json.dumps(arg)))
            elif type(arg) is int:statements.append('values[%d].vt=VT_INTEGER;values[%d].lVal=%d;'%(position,position,arg))
            else:raise ValueError('Typed record argument required')
        record_args.append('case %d:%s return %d;'%(index,''.join(statements),len(row['arguments'])+2))
        record_set.append('case %d:%s=value;return;'%(index,field))
        record_get.append('case %d:return %s;'%(index,field))
        records.append('{%s,%s,%s,%s,%d,%d,%d,%d,%d,%s,%s}'%(
            'VT_DECIMAL' if row['result_type']=='decimal' else 'VT_INTEGER',
            decimal(row['input']),decimal(row['stored']),decimal(row['alias_get']),row['min_revision'],row['arguments'][0]=='attack',row['integer_input'],row['arguments'][0]=='drawmethods',row['arguments'][:2]==['attack','dropv'],
            json.dumps(row['get_error']),json.dumps(row['set_error'])))
    pieces.update(RECORD_FIELDS=','.join(records),RECORD_ARGS='\n'.join(record_args),
        RECORD_SET='\n'.join(record_set),RECORD_GET='\n'.join(record_get))
    classic=[];classic_set=[]
    for index,row in enumerate(data['classic_properties']):
        if not re.fullmatch(r'[a-z_]+(?:\.[a-z_]+)*',row['field']):
            raise ValueError('Explicit classic animation field required')
        classic.append('{%d,%d,%d,%s}'%(row['index'],row['revised_index'],-1 if row['leaf'] is None else row['leaf'],
            'VT_DECIMAL' if row['result_type']=='decimal' else 'VT_INTEGER'))
        classic_set.append('case %d:legacy.%s=value;target.%s=value+10;return;'%(index,row['field'],row['field']))
    pieces.update(CLASSIC_LAST=str(data['classic_last']),CLASSIC_FIELDS=','.join(classic),
        CLASSIC_SET='\n'.join(classic_set),CLASSIC_UNIMPLEMENTED=','.join('{%d,%d,%s}'%(row['index'],row['revised_index'],json.dumps(row['error'])) for row in data['classic_unimplemented']))
    text=Path(__file__).with_name('forward_animation_properties_contract.c.in').read_text()
    for key,value in pieces.items():text=text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):raise ValueError('Unresolved animation property input')
    return text


class ForwardAnimationPropertyTests(unittest.TestCase):
    def test_native_scalar_bodies_aliases_and_failure_order(self):
        data=load_contract_fixture(FIXTURE)
        revisions={row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions),len(data['sources']))
        self.assertEqual((min(revisions),max(revisions)),tuple(data['range']))
        self.assertTrue(set(data['boundary_controls'])<=revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'],data['engine'])
            self.assertIs(type(row['rich']),bool)
            self.assertIn(row['change_binding'],(0,1,2))
            if row['rich']:
                self.assertEqual(set(row['scalar_indices']),{p['name'] for p in data['scalar_properties']})
        for profile in contract_profiles(data,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision=int(profile.get('revision',profile['build']))
            if profile['engine']==data['engine'] and data['range'][0]<=revision<=data['range'][1]:
                self.assertIn(revision,revisions)
        engine=Path(os.environ.get('OBOR_ANIMATION_PROPERTIES_ENGINE',ROOT/'src/engines'/data['engine']))
        actual=[json.loads(line) for line in native_output(program(data,engine),data,engine_source=engine).splitlines()]
        self.assertEqual(actual,[dict(revision=row['revision'],status='PASS') for row in data['sources']])

    def test_selected_native_headers_cannot_fall_back_to_another_engine(self):
        data=load_contract_fixture(FIXTURE)
        with tempfile.TemporaryDirectory(prefix='anybor-native-header-refusal-') as folder:
            with self.assertRaisesRegex(ValueError,'Selected native engine headers are unavailable'):
                native_output('int main(void){return 0;}',data,engine_source=folder)


if __name__=='__main__':unittest.main()
