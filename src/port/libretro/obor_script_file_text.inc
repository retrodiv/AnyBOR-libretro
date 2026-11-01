/* Source-defined script-file text with bounded table traversal.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Included after obor_script_file32.inc and the engine's variable tables.
 */
static int obor_script_text_value(FILE *stream, const ScriptVariant *value)
{
    const unsigned char *text;
    if(!stream || !value) return 0;
    switch(value->vt) {
    case VT_STR:
        text = (const unsigned char *)StrCache_GetIfPresent(value->strVal);
        if(!text || fputc('"', stream) == EOF) return 0;
        for(; *text; ++text) {
            switch(*text) {
            case '\n': if(fputs("\\n", stream) == EOF) return 0; break;
            case '\r': if(fputs("\\r", stream) == EOF) return 0; break;
            case '\\': if(fputs("\\\\", stream) == EOF) return 0; break;
            default: if(fputc(*text, stream) == EOF) return 0; break;
            }
        }
        return fputc('"', stream) != EOF;
    case VT_DECIMAL:
        return fprintf(stream, "%lf", (double)value->dblVal) >= 0;
    case VT_INTEGER:
        return fprintf(stream, "%ld", (long)value->lVal) >= 0;
    default:
        return fputs("NULL()", stream) != EOF;
    }
}

static int obor_script_file_text_write(FILE *stream)
{
    size_t named, indexed, active, i;
    const s_variantnode *node;
    if(!stream || !obor_script32_tables(&named, &indexed) ||
       max_global_var_index < -1) return 0;
    active = max_global_var_index < 0 ? 0 : (size_t)max_global_var_index + 1;
    if(active > named || (size_t)max_indexed_vars > indexed) return 0;
    if(fputs("void main() {\n", stream) == EOF) return 0;
    for(i = 0; i < active; ++i) {
        node = global_var_list[i];
        if(!node) return 0;
        if(node->owner || node->value.vt == VT_PTR) continue;
        if(!node->key) return 0;
        if(obor_profile_build >= 3421 &&
           (!node->key[0] || node->value.vt == VT_EMPTY)) continue;
        if(fputs("\tsetglobalvar(\"", stream) == EOF ||
           fputs(node->key, stream) == EOF || fputs("\",", stream) == EOF ||
           !obor_script_text_value(stream, &node->value) ||
           fputs(");\n", stream) == EOF) return 0;
    }
    for(i = 0; i < (size_t)max_indexed_vars; ++i) {
        if(indexed_var_list[i].vt == VT_PTR ||
           indexed_var_list[i].vt == VT_EMPTY) continue;
        if(fprintf(stream, "\tsetindexedvar(%d,", (int)i) < 0 ||
           !obor_script_text_value(stream, indexed_var_list + i) ||
           fputs(");\n", stream) == EOF) return 0;
    }
    return fputs("}\n", stream) != EOF && !ferror(stream);
}
