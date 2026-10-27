/* AnyBOR modification record: 2026-10-26.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Retain historical grammar token sets with symbolic production mappings and
 * profile selection.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3842.md
 * at the source repository root. Original notices follow below.
 */

/* Historical grammar tables, expressed with physical production names.
 * Original table data: OpenBOR Team, BSD license;see engine LICENSE.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (profile selection).
 */
#ifndef OBOR_PROFILE_GRAMMAR_H
#define OBOR_PROFILE_GRAMMAR_H
static MY_TOKEN_TYPE obor_grammar_empty[] = {END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_0[] = {EPSILON, TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_1[] = {TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_2[] = {TOKEN_LPAREN, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_3[] = {TOKEN_RPAREN, TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_4[] = {TOKEN_ASSIGN, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_5[] = {TOKEN_COMMA, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_6[] = {TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_7[] = {TOKEN_LCURLY, TOKEN_IF, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_8[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_9[] = {TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_10[] = {TOKEN_LCURLY, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_11[] = {TOKEN_IF, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_12[] = {TOKEN_ELSE, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_13[] = {TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_14[] = {EPSILON, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_15[] = {TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_16[] = {TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_17[] = {TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_18[] = {TOKEN_OR_OP, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_19[] = {TOKEN_AND_OP, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_20[] = {TOKEN_EQ_OP, TOKEN_NE_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_21[] = {TOKEN_EQ_OP, TOKEN_NE_OP, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_22[] = {TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_23[] = {TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_24[] = {TOKEN_ADD, TOKEN_SUB, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_25[] = {TOKEN_ADD, TOKEN_SUB, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_26[] = {TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_27[] = {TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_28[] = {TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_29[] = {TOKEN_LPAREN, TOKEN_FIELD, TOKEN_INC_OP, TOKEN_DEC_OP, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_30[] = {TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_31[] = {TOKEN_EOF, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_32[] = {EPSILON, TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, TOKEN_EOF, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_33[] = {TOKEN_IDENTIFIER, TOKEN_COMMA, EPSILON, TOKEN_RPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_34[] = {TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_35[] = {TOKEN_SEMICOLON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_36[] = {TOKEN_COMMA, EPSILON, TOKEN_RPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_37[] = {TOKEN_RPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_38[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_39[] = {TOKEN_RCURLY, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_40[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, TOKEN_ELSE, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_41[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, TOKEN_ELSE, TOKEN_RPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_42[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, TOKEN_ELSE, TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, TOKEN_EOF, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_43[] = {EPSILON, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_44[] = {TOKEN_SEMICOLON, TOKEN_RPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_45[] = {TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_46[] = {END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_47[] = {TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_48[] = {TOKEN_OR_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_49[] = {TOKEN_AND_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_OR_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_50[] = {TOKEN_EQ_OP, TOKEN_NE_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_OR_OP, TOKEN_AND_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_51[] = {TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_52[] = {TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_53[] = {TOKEN_ADD, TOKEN_SUB, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_54[] = {TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, TOKEN_ADD, TOKEN_SUB, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_55[] = {TOKEN_LPAREN, TOKEN_FIELD, TOKEN_INC_OP, TOKEN_DEC_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, TOKEN_ADD, TOKEN_SUB, TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_56[] = {TOKEN_LCURLY, TOKEN_IF, TOKEN_SWITCH, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_57[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_SWITCH, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_58[] = {TOKEN_IF, TOKEN_SWITCH, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_59[] = {TOKEN_CASE, TOKEN_DEFAULT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_60[] = {TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_SWITCH, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_61[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_SWITCH, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, TOKEN_CASE, TOKEN_DEFAULT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_62[] = {TOKEN_RCURLY, TOKEN_CASE, TOKEN_DEFAULT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_63[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_SWITCH, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, TOKEN_ELSE, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_64[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_SWITCH, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, TOKEN_ELSE, TOKEN_RPAREN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_65[] = {EPSILON, TOKEN_LCURLY, TOKEN_IF, TOKEN_SWITCH, TOKEN_WHILE, TOKEN_DO, TOKEN_FOR, TOKEN_BREAK, TOKEN_CONTINUE, TOKEN_RETURN, TOKEN_INC_OP, TOKEN_DEC_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_BOOLEAN_NOT, TOKEN_IDENTIFIER, TOKEN_HEXCONSTANT, TOKEN_INTCONSTANT, TOKEN_FLOATCONSTANT, TOKEN_STRING_LITERAL, TOKEN_LPAREN, TOKEN_RCURLY, TOKEN_CASE, TOKEN_DEFAULT, TOKEN_ELSE, TOKEN_CONST, TOKEN_SIGNED, TOKEN_UNSIGNED, TOKEN_VOID, TOKEN_CHAR, TOKEN_SHORT, TOKEN_INT, TOKEN_LONG, TOKEN_FLOAT, TOKEN_DOUBLE, TOKEN_EOF, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_66[] = {TOKEN_COLON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_67[] = {TOKEN_CONDITIONAL, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_68[] = {TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_69[] = {TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_70[] = {TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_71[] = {TOKEN_CONDITIONAL, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_72[] = {TOKEN_OR_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_73[] = {TOKEN_AND_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_74[] = {TOKEN_EQ_OP, TOKEN_NE_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_75[] = {TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_76[] = {TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_77[] = {TOKEN_ADD, TOKEN_SUB, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_78[] = {TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, TOKEN_ADD, TOKEN_SUB, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_79[] = {TOKEN_LPAREN, TOKEN_FIELD, TOKEN_INC_OP, TOKEN_DEC_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, TOKEN_ADD, TOKEN_SUB, TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_80[] = {TOKEN_LEFT_OP, TOKEN_RIGHT_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_81[] = {TOKEN_LEFT_OP, TOKEN_RIGHT_OP, EPSILON, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_82[] = {TOKEN_LEFT_OP, TOKEN_RIGHT_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_83[] = {TOKEN_LEFT_OP, TOKEN_RIGHT_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_84[] = {TOKEN_ADD, TOKEN_SUB, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, TOKEN_LEFT_OP, TOKEN_RIGHT_OP, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_85[] = {TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, TOKEN_LEFT_OP, TOKEN_RIGHT_OP, TOKEN_ADD, TOKEN_SUB, END_OF_TOKENS};
static MY_TOKEN_TYPE obor_grammar_tokens_86[] = {TOKEN_LPAREN, TOKEN_FIELD, TOKEN_INC_OP, TOKEN_DEC_OP, EPSILON, TOKEN_SEMICOLON, TOKEN_RPAREN, TOKEN_COLON, TOKEN_COMMA, TOKEN_ASSIGN, TOKEN_MUL_ASSIGN, TOKEN_DIV_ASSIGN, TOKEN_MOD_ASSIGN, TOKEN_ADD_ASSIGN, TOKEN_SUB_ASSIGN, TOKEN_CONDITIONAL, TOKEN_OR_OP, TOKEN_AND_OP, TOKEN_EQ_OP, TOKEN_NE_OP, TOKEN_GE_OP, TOKEN_LE_OP, TOKEN_LT, TOKEN_GT, TOKEN_LEFT_OP, TOKEN_RIGHT_OP, TOKEN_ADD, TOKEN_SUB, TOKEN_MUL, TOKEN_DIV, TOKEN_MOD, END_OF_TOKENS};
static MY_TOKEN_TYPE *const obor_grammar_first_0[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_0,
    [external_decl] = obor_grammar_tokens_1,
    [decl_spec] = obor_grammar_tokens_1,
    [decl] = obor_grammar_tokens_1,
    [funcDecl] = obor_grammar_tokens_2,
    [funcDecl1] = obor_grammar_tokens_3,
    [initializer] = obor_grammar_tokens_4,
    [parm_decl] = obor_grammar_tokens_1,
    [param_list] = obor_grammar_tokens_1,
    [param_list2] = obor_grammar_tokens_5,
    [decl_list] = obor_grammar_tokens_1,
    [decl_list2] = obor_grammar_tokens_6,
    [stmt_list] = obor_grammar_tokens_7,
    [stmt_list2] = obor_grammar_tokens_8,
    [stmt] = obor_grammar_tokens_7,
    [expr_stmt] = obor_grammar_tokens_9,
    [comp_stmt] = obor_grammar_tokens_10,
    [comp_stmt2] = obor_grammar_tokens_6,
    [comp_stmt3] = obor_grammar_tokens_8,
    [select_stmt] = obor_grammar_tokens_11,
    [opt_else] = obor_grammar_tokens_12,
    [iter_stmt] = obor_grammar_tokens_13,
    [opt_expr_stmt] = obor_grammar_tokens_14,
    [defer_expr_stmt] = obor_grammar_tokens_14,
    [jump_stmt] = obor_grammar_tokens_15,
    [opt_expr] = obor_grammar_tokens_14,
    [expr] = obor_grammar_tokens_9,
    [assignment_op] = obor_grammar_tokens_16,
    [assignment_expr] = obor_grammar_tokens_9,
    [assignment_expr2] = obor_grammar_tokens_17,
    [const_expr] = obor_grammar_tokens_9,
    [log_or_expr] = obor_grammar_tokens_9,
    [log_or_expr2] = obor_grammar_tokens_18,
    [log_and_expr] = obor_grammar_tokens_9,
    [log_and_expr2] = obor_grammar_tokens_19,
    [eq_op] = obor_grammar_tokens_20,
    [equal_expr] = obor_grammar_tokens_9,
    [equal_expr2] = obor_grammar_tokens_21,
    [rel_op] = obor_grammar_tokens_22,
    [rel_expr] = obor_grammar_tokens_9,
    [rel_expr2] = obor_grammar_tokens_23,
    [add_op] = obor_grammar_tokens_24,
    [add_expr] = obor_grammar_tokens_9,
    [add_expr2] = obor_grammar_tokens_25,
    [mult_op] = obor_grammar_tokens_26,
    [mult_expr] = obor_grammar_tokens_9,
    [mult_expr2] = obor_grammar_tokens_27,
    [unary_expr] = obor_grammar_tokens_9,
    [postfix_expr] = obor_grammar_tokens_28,
    [postfix_expr2] = obor_grammar_tokens_29,
    [arg_expr_list] = obor_grammar_tokens_14,
    [arg_expr_list2] = obor_grammar_tokens_5,
    [primary_expr] = obor_grammar_tokens_28,
    [constant] = obor_grammar_tokens_30,
};
static MY_TOKEN_TYPE *const obor_grammar_follow_0[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_31,
    [external_decl] = obor_grammar_tokens_32,
    [decl_spec] = obor_grammar_tokens_33,
    [decl] = obor_grammar_tokens_34,
    [funcDecl] = obor_grammar_tokens_10,
    [funcDecl1] = obor_grammar_tokens_10,
    [initializer] = obor_grammar_tokens_35,
    [parm_decl] = obor_grammar_tokens_36,
    [param_list] = obor_grammar_tokens_37,
    [param_list2] = obor_grammar_tokens_37,
    [decl_list] = obor_grammar_tokens_38,
    [decl_list2] = obor_grammar_tokens_38,
    [stmt_list] = obor_grammar_tokens_39,
    [stmt_list2] = obor_grammar_tokens_39,
    [stmt] = obor_grammar_tokens_40,
    [expr_stmt] = obor_grammar_tokens_41,
    [comp_stmt] = obor_grammar_tokens_42,
    [comp_stmt2] = obor_grammar_tokens_38,
    [comp_stmt3] = obor_grammar_tokens_39,
    [select_stmt] = obor_grammar_tokens_40,
    [opt_else] = obor_grammar_tokens_40,
    [iter_stmt] = obor_grammar_tokens_40,
    [opt_expr_stmt] = obor_grammar_tokens_43,
    [defer_expr_stmt] = obor_grammar_tokens_37,
    [jump_stmt] = obor_grammar_tokens_40,
    [opt_expr] = obor_grammar_tokens_35,
    [expr] = obor_grammar_tokens_44,
    [assignment_op] = obor_grammar_tokens_9,
    [assignment_expr] = obor_grammar_tokens_45,
    [assignment_expr2] = obor_grammar_tokens_45,
    [const_expr] = obor_grammar_tokens_46,
    [log_or_expr] = obor_grammar_tokens_47,
    [log_or_expr2] = obor_grammar_tokens_47,
    [log_and_expr] = obor_grammar_tokens_48,
    [log_and_expr2] = obor_grammar_tokens_48,
    [eq_op] = obor_grammar_tokens_9,
    [equal_expr] = obor_grammar_tokens_49,
    [equal_expr2] = obor_grammar_tokens_49,
    [rel_op] = obor_grammar_tokens_9,
    [rel_expr] = obor_grammar_tokens_50,
    [rel_expr2] = obor_grammar_tokens_50,
    [add_op] = obor_grammar_tokens_9,
    [add_expr] = obor_grammar_tokens_51,
    [add_expr2] = obor_grammar_tokens_52,
    [mult_op] = obor_grammar_tokens_9,
    [mult_expr] = obor_grammar_tokens_53,
    [mult_expr2] = obor_grammar_tokens_53,
    [unary_expr] = obor_grammar_tokens_54,
    [postfix_expr] = obor_grammar_tokens_54,
    [postfix_expr2] = obor_grammar_tokens_54,
    [arg_expr_list] = obor_grammar_tokens_37,
    [arg_expr_list2] = obor_grammar_tokens_37,
    [primary_expr] = obor_grammar_tokens_55,
    [constant] = obor_grammar_tokens_55,
};
static MY_TOKEN_TYPE *const obor_grammar_first_1[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_0,
    [external_decl] = obor_grammar_tokens_1,
    [decl_spec] = obor_grammar_tokens_1,
    [decl] = obor_grammar_tokens_1,
    [funcDecl] = obor_grammar_tokens_2,
    [funcDecl1] = obor_grammar_tokens_3,
    [initializer] = obor_grammar_tokens_4,
    [parm_decl] = obor_grammar_tokens_1,
    [param_list] = obor_grammar_tokens_1,
    [param_list2] = obor_grammar_tokens_5,
    [decl_list] = obor_grammar_tokens_1,
    [decl_list2] = obor_grammar_tokens_6,
    [stmt_list] = obor_grammar_tokens_56,
    [stmt_list2] = obor_grammar_tokens_57,
    [stmt] = obor_grammar_tokens_56,
    [expr_stmt] = obor_grammar_tokens_9,
    [comp_stmt] = obor_grammar_tokens_10,
    [comp_stmt2] = obor_grammar_tokens_6,
    [comp_stmt3] = obor_grammar_tokens_57,
    [select_stmt] = obor_grammar_tokens_58,
    [opt_else] = obor_grammar_tokens_12,
    [switch_body] = obor_grammar_tokens_46,
    [case_label] = obor_grammar_tokens_59,
    [iter_stmt] = obor_grammar_tokens_13,
    [opt_expr_stmt] = obor_grammar_tokens_14,
    [defer_expr_stmt] = obor_grammar_tokens_14,
    [jump_stmt] = obor_grammar_tokens_15,
    [opt_expr] = obor_grammar_tokens_14,
    [expr] = obor_grammar_tokens_9,
    [assignment_op] = obor_grammar_tokens_16,
    [assignment_expr] = obor_grammar_tokens_9,
    [assignment_expr2] = obor_grammar_tokens_17,
    [const_expr] = obor_grammar_tokens_9,
    [log_or_expr] = obor_grammar_tokens_9,
    [log_or_expr2] = obor_grammar_tokens_18,
    [log_and_expr] = obor_grammar_tokens_9,
    [log_and_expr2] = obor_grammar_tokens_19,
    [eq_op] = obor_grammar_tokens_20,
    [equal_expr] = obor_grammar_tokens_9,
    [equal_expr2] = obor_grammar_tokens_21,
    [rel_op] = obor_grammar_tokens_22,
    [rel_expr] = obor_grammar_tokens_9,
    [rel_expr2] = obor_grammar_tokens_23,
    [add_op] = obor_grammar_tokens_24,
    [add_expr] = obor_grammar_tokens_9,
    [add_expr2] = obor_grammar_tokens_25,
    [mult_op] = obor_grammar_tokens_26,
    [mult_expr] = obor_grammar_tokens_9,
    [mult_expr2] = obor_grammar_tokens_27,
    [unary_expr] = obor_grammar_tokens_9,
    [postfix_expr] = obor_grammar_tokens_28,
    [postfix_expr2] = obor_grammar_tokens_29,
    [arg_expr_list] = obor_grammar_tokens_14,
    [arg_expr_list2] = obor_grammar_tokens_5,
    [primary_expr] = obor_grammar_tokens_28,
    [constant] = obor_grammar_tokens_30,
};
static MY_TOKEN_TYPE *const obor_grammar_follow_1[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_31,
    [external_decl] = obor_grammar_tokens_32,
    [decl_spec] = obor_grammar_tokens_33,
    [decl] = obor_grammar_tokens_60,
    [funcDecl] = obor_grammar_tokens_10,
    [funcDecl1] = obor_grammar_tokens_10,
    [initializer] = obor_grammar_tokens_35,
    [parm_decl] = obor_grammar_tokens_36,
    [param_list] = obor_grammar_tokens_37,
    [param_list2] = obor_grammar_tokens_37,
    [decl_list] = obor_grammar_tokens_61,
    [decl_list2] = obor_grammar_tokens_61,
    [stmt_list] = obor_grammar_tokens_62,
    [stmt_list2] = obor_grammar_tokens_62,
    [stmt] = obor_grammar_tokens_63,
    [expr_stmt] = obor_grammar_tokens_64,
    [comp_stmt] = obor_grammar_tokens_65,
    [comp_stmt2] = obor_grammar_tokens_61,
    [comp_stmt3] = obor_grammar_tokens_62,
    [select_stmt] = obor_grammar_tokens_63,
    [opt_else] = obor_grammar_tokens_63,
    [switch_body] = obor_grammar_tokens_39,
    [case_label] = obor_grammar_tokens_66,
    [iter_stmt] = obor_grammar_tokens_63,
    [opt_expr_stmt] = obor_grammar_tokens_43,
    [defer_expr_stmt] = obor_grammar_tokens_37,
    [jump_stmt] = obor_grammar_tokens_63,
    [opt_expr] = obor_grammar_tokens_35,
    [expr] = obor_grammar_tokens_44,
    [assignment_op] = obor_grammar_tokens_9,
    [assignment_expr] = obor_grammar_tokens_45,
    [assignment_expr2] = obor_grammar_tokens_45,
    [const_expr] = obor_grammar_tokens_46,
    [log_or_expr] = obor_grammar_tokens_47,
    [log_or_expr2] = obor_grammar_tokens_47,
    [log_and_expr] = obor_grammar_tokens_48,
    [log_and_expr2] = obor_grammar_tokens_48,
    [eq_op] = obor_grammar_tokens_9,
    [equal_expr] = obor_grammar_tokens_49,
    [equal_expr2] = obor_grammar_tokens_49,
    [rel_op] = obor_grammar_tokens_9,
    [rel_expr] = obor_grammar_tokens_50,
    [rel_expr2] = obor_grammar_tokens_50,
    [add_op] = obor_grammar_tokens_9,
    [add_expr] = obor_grammar_tokens_51,
    [add_expr2] = obor_grammar_tokens_52,
    [mult_op] = obor_grammar_tokens_9,
    [mult_expr] = obor_grammar_tokens_53,
    [mult_expr2] = obor_grammar_tokens_53,
    [unary_expr] = obor_grammar_tokens_54,
    [postfix_expr] = obor_grammar_tokens_54,
    [postfix_expr2] = obor_grammar_tokens_54,
    [arg_expr_list] = obor_grammar_tokens_37,
    [arg_expr_list2] = obor_grammar_tokens_37,
    [primary_expr] = obor_grammar_tokens_55,
    [constant] = obor_grammar_tokens_55,
};
static MY_TOKEN_TYPE *const obor_grammar_first_2[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_0,
    [external_decl] = obor_grammar_tokens_1,
    [decl_spec] = obor_grammar_tokens_1,
    [decl] = obor_grammar_tokens_1,
    [funcDecl] = obor_grammar_tokens_2,
    [funcDecl1] = obor_grammar_tokens_3,
    [initializer] = obor_grammar_tokens_4,
    [parm_decl] = obor_grammar_tokens_1,
    [param_list] = obor_grammar_tokens_1,
    [param_list2] = obor_grammar_tokens_5,
    [decl_list] = obor_grammar_tokens_1,
    [decl_list2] = obor_grammar_tokens_6,
    [stmt_list] = obor_grammar_tokens_56,
    [stmt_list2] = obor_grammar_tokens_57,
    [stmt] = obor_grammar_tokens_56,
    [expr_stmt] = obor_grammar_tokens_9,
    [comp_stmt] = obor_grammar_tokens_10,
    [comp_stmt2] = obor_grammar_tokens_6,
    [comp_stmt3] = obor_grammar_tokens_57,
    [select_stmt] = obor_grammar_tokens_58,
    [opt_else] = obor_grammar_tokens_12,
    [switch_body] = obor_grammar_tokens_46,
    [case_label] = obor_grammar_tokens_59,
    [iter_stmt] = obor_grammar_tokens_13,
    [opt_expr_stmt] = obor_grammar_tokens_14,
    [defer_expr_stmt] = obor_grammar_tokens_14,
    [jump_stmt] = obor_grammar_tokens_15,
    [opt_expr] = obor_grammar_tokens_14,
    [expr] = obor_grammar_tokens_9,
    [assignment_op] = obor_grammar_tokens_16,
    [assignment_expr] = obor_grammar_tokens_9,
    [assignment_expr2] = obor_grammar_tokens_17,
    [const_expr] = obor_grammar_tokens_9,
    [cond_expr] = obor_grammar_tokens_9,
    [cond_expr2] = obor_grammar_tokens_67,
    [log_or_expr] = obor_grammar_tokens_9,
    [log_or_expr2] = obor_grammar_tokens_18,
    [log_and_expr] = obor_grammar_tokens_9,
    [log_and_expr2] = obor_grammar_tokens_19,
    [eq_op] = obor_grammar_tokens_20,
    [equal_expr] = obor_grammar_tokens_9,
    [equal_expr2] = obor_grammar_tokens_21,
    [rel_op] = obor_grammar_tokens_22,
    [rel_expr] = obor_grammar_tokens_9,
    [rel_expr2] = obor_grammar_tokens_23,
    [add_op] = obor_grammar_tokens_24,
    [add_expr] = obor_grammar_tokens_9,
    [add_expr2] = obor_grammar_tokens_25,
    [mult_op] = obor_grammar_tokens_26,
    [mult_expr] = obor_grammar_tokens_9,
    [mult_expr2] = obor_grammar_tokens_27,
    [unary_expr] = obor_grammar_tokens_9,
    [postfix_expr] = obor_grammar_tokens_28,
    [postfix_expr2] = obor_grammar_tokens_29,
    [arg_expr_list] = obor_grammar_tokens_14,
    [arg_expr_list2] = obor_grammar_tokens_5,
    [primary_expr] = obor_grammar_tokens_28,
    [constant] = obor_grammar_tokens_30,
};
static MY_TOKEN_TYPE *const obor_grammar_follow_2[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_31,
    [external_decl] = obor_grammar_tokens_32,
    [decl_spec] = obor_grammar_tokens_33,
    [decl] = obor_grammar_tokens_60,
    [funcDecl] = obor_grammar_tokens_10,
    [funcDecl1] = obor_grammar_tokens_10,
    [initializer] = obor_grammar_tokens_35,
    [parm_decl] = obor_grammar_tokens_36,
    [param_list] = obor_grammar_tokens_37,
    [param_list2] = obor_grammar_tokens_37,
    [decl_list] = obor_grammar_tokens_61,
    [decl_list2] = obor_grammar_tokens_61,
    [stmt_list] = obor_grammar_tokens_62,
    [stmt_list2] = obor_grammar_tokens_62,
    [stmt] = obor_grammar_tokens_63,
    [expr_stmt] = obor_grammar_tokens_64,
    [comp_stmt] = obor_grammar_tokens_65,
    [comp_stmt2] = obor_grammar_tokens_61,
    [comp_stmt3] = obor_grammar_tokens_62,
    [select_stmt] = obor_grammar_tokens_63,
    [opt_else] = obor_grammar_tokens_63,
    [switch_body] = obor_grammar_tokens_39,
    [case_label] = obor_grammar_tokens_46,
    [iter_stmt] = obor_grammar_tokens_63,
    [opt_expr_stmt] = obor_grammar_tokens_43,
    [defer_expr_stmt] = obor_grammar_tokens_37,
    [jump_stmt] = obor_grammar_tokens_63,
    [opt_expr] = obor_grammar_tokens_35,
    [expr] = obor_grammar_tokens_68,
    [assignment_op] = obor_grammar_tokens_9,
    [assignment_expr] = obor_grammar_tokens_69,
    [assignment_expr2] = obor_grammar_tokens_69,
    [const_expr] = obor_grammar_tokens_46,
    [cond_expr] = obor_grammar_tokens_70,
    [cond_expr2] = obor_grammar_tokens_70,
    [log_or_expr] = obor_grammar_tokens_71,
    [log_or_expr2] = obor_grammar_tokens_71,
    [log_and_expr] = obor_grammar_tokens_72,
    [log_and_expr2] = obor_grammar_tokens_72,
    [eq_op] = obor_grammar_tokens_9,
    [equal_expr] = obor_grammar_tokens_73,
    [equal_expr2] = obor_grammar_tokens_73,
    [rel_op] = obor_grammar_tokens_9,
    [rel_expr] = obor_grammar_tokens_74,
    [rel_expr2] = obor_grammar_tokens_74,
    [add_op] = obor_grammar_tokens_9,
    [add_expr] = obor_grammar_tokens_75,
    [add_expr2] = obor_grammar_tokens_76,
    [mult_op] = obor_grammar_tokens_9,
    [mult_expr] = obor_grammar_tokens_77,
    [mult_expr2] = obor_grammar_tokens_77,
    [unary_expr] = obor_grammar_tokens_78,
    [postfix_expr] = obor_grammar_tokens_78,
    [postfix_expr2] = obor_grammar_tokens_78,
    [arg_expr_list] = obor_grammar_tokens_37,
    [arg_expr_list2] = obor_grammar_tokens_37,
    [primary_expr] = obor_grammar_tokens_79,
    [constant] = obor_grammar_tokens_79,
};
static MY_TOKEN_TYPE *const obor_grammar_first_3[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_0,
    [external_decl] = obor_grammar_tokens_1,
    [decl_spec] = obor_grammar_tokens_1,
    [decl] = obor_grammar_tokens_1,
    [funcDecl] = obor_grammar_tokens_2,
    [funcDecl1] = obor_grammar_tokens_3,
    [initializer] = obor_grammar_tokens_4,
    [parm_decl] = obor_grammar_tokens_1,
    [param_list] = obor_grammar_tokens_1,
    [param_list2] = obor_grammar_tokens_5,
    [decl_list] = obor_grammar_tokens_1,
    [decl_list2] = obor_grammar_tokens_6,
    [stmt_list] = obor_grammar_tokens_56,
    [stmt_list2] = obor_grammar_tokens_57,
    [stmt] = obor_grammar_tokens_56,
    [expr_stmt] = obor_grammar_tokens_9,
    [comp_stmt] = obor_grammar_tokens_10,
    [comp_stmt2] = obor_grammar_tokens_6,
    [comp_stmt3] = obor_grammar_tokens_57,
    [select_stmt] = obor_grammar_tokens_58,
    [opt_else] = obor_grammar_tokens_12,
    [switch_body] = obor_grammar_tokens_46,
    [case_label] = obor_grammar_tokens_59,
    [iter_stmt] = obor_grammar_tokens_13,
    [opt_expr_stmt] = obor_grammar_tokens_14,
    [defer_expr_stmt] = obor_grammar_tokens_14,
    [jump_stmt] = obor_grammar_tokens_15,
    [opt_expr] = obor_grammar_tokens_14,
    [expr] = obor_grammar_tokens_9,
    [assignment_op] = obor_grammar_tokens_16,
    [assignment_expr] = obor_grammar_tokens_9,
    [assignment_expr2] = obor_grammar_tokens_17,
    [const_expr] = obor_grammar_tokens_9,
    [cond_expr] = obor_grammar_tokens_9,
    [cond_expr2] = obor_grammar_tokens_67,
    [log_or_expr] = obor_grammar_tokens_9,
    [log_or_expr2] = obor_grammar_tokens_18,
    [log_and_expr] = obor_grammar_tokens_9,
    [log_and_expr2] = obor_grammar_tokens_19,
    [eq_op] = obor_grammar_tokens_20,
    [equal_expr] = obor_grammar_tokens_9,
    [equal_expr2] = obor_grammar_tokens_21,
    [rel_op] = obor_grammar_tokens_22,
    [rel_expr] = obor_grammar_tokens_9,
    [rel_expr2] = obor_grammar_tokens_23,
    [shift_op] = obor_grammar_tokens_80,
    [shift_expr] = obor_grammar_tokens_9,
    [shift_expr2] = obor_grammar_tokens_81,
    [add_op] = obor_grammar_tokens_24,
    [add_expr] = obor_grammar_tokens_9,
    [add_expr2] = obor_grammar_tokens_25,
    [mult_op] = obor_grammar_tokens_26,
    [mult_expr] = obor_grammar_tokens_9,
    [mult_expr2] = obor_grammar_tokens_27,
    [unary_expr] = obor_grammar_tokens_9,
    [postfix_expr] = obor_grammar_tokens_28,
    [postfix_expr2] = obor_grammar_tokens_29,
    [arg_expr_list] = obor_grammar_tokens_14,
    [arg_expr_list2] = obor_grammar_tokens_5,
    [primary_expr] = obor_grammar_tokens_28,
    [constant] = obor_grammar_tokens_30,
};
static MY_TOKEN_TYPE *const obor_grammar_follow_3[NUMPRODUCTIONS] = {
    [start] = obor_grammar_tokens_31,
    [external_decl] = obor_grammar_tokens_32,
    [decl_spec] = obor_grammar_tokens_33,
    [decl] = obor_grammar_tokens_60,
    [funcDecl] = obor_grammar_tokens_10,
    [funcDecl1] = obor_grammar_tokens_10,
    [initializer] = obor_grammar_tokens_35,
    [parm_decl] = obor_grammar_tokens_36,
    [param_list] = obor_grammar_tokens_37,
    [param_list2] = obor_grammar_tokens_37,
    [decl_list] = obor_grammar_tokens_61,
    [decl_list2] = obor_grammar_tokens_61,
    [stmt_list] = obor_grammar_tokens_62,
    [stmt_list2] = obor_grammar_tokens_62,
    [stmt] = obor_grammar_tokens_63,
    [expr_stmt] = obor_grammar_tokens_64,
    [comp_stmt] = obor_grammar_tokens_65,
    [comp_stmt2] = obor_grammar_tokens_61,
    [comp_stmt3] = obor_grammar_tokens_62,
    [select_stmt] = obor_grammar_tokens_63,
    [opt_else] = obor_grammar_tokens_63,
    [switch_body] = obor_grammar_tokens_39,
    [case_label] = obor_grammar_tokens_46,
    [iter_stmt] = obor_grammar_tokens_63,
    [opt_expr_stmt] = obor_grammar_tokens_43,
    [defer_expr_stmt] = obor_grammar_tokens_37,
    [jump_stmt] = obor_grammar_tokens_63,
    [opt_expr] = obor_grammar_tokens_35,
    [expr] = obor_grammar_tokens_68,
    [assignment_op] = obor_grammar_tokens_9,
    [assignment_expr] = obor_grammar_tokens_69,
    [assignment_expr2] = obor_grammar_tokens_69,
    [const_expr] = obor_grammar_tokens_46,
    [cond_expr] = obor_grammar_tokens_70,
    [cond_expr2] = obor_grammar_tokens_70,
    [log_or_expr] = obor_grammar_tokens_71,
    [log_or_expr2] = obor_grammar_tokens_71,
    [log_and_expr] = obor_grammar_tokens_72,
    [log_and_expr2] = obor_grammar_tokens_72,
    [eq_op] = obor_grammar_tokens_9,
    [equal_expr] = obor_grammar_tokens_73,
    [equal_expr2] = obor_grammar_tokens_73,
    [rel_op] = obor_grammar_tokens_9,
    [rel_expr] = obor_grammar_tokens_74,
    [rel_expr2] = obor_grammar_tokens_74,
    [shift_op] = obor_grammar_tokens_9,
    [shift_expr] = obor_grammar_tokens_75,
    [shift_expr2] = obor_grammar_tokens_76,
    [add_op] = obor_grammar_tokens_9,
    [add_expr] = obor_grammar_tokens_82,
    [add_expr2] = obor_grammar_tokens_83,
    [mult_op] = obor_grammar_tokens_9,
    [mult_expr] = obor_grammar_tokens_84,
    [mult_expr2] = obor_grammar_tokens_84,
    [unary_expr] = obor_grammar_tokens_85,
    [postfix_expr] = obor_grammar_tokens_85,
    [postfix_expr2] = obor_grammar_tokens_85,
    [arg_expr_list] = obor_grammar_tokens_37,
    [arg_expr_list2] = obor_grammar_tokens_37,
    [primary_expr] = obor_grammar_tokens_86,
    [constant] = obor_grammar_tokens_86,
};
static void obor_profile_parser_sets(ParserSet *pset)
{
    MY_TOKEN_TYPE *const *first_map, *const *follow_map;
    int i;
    if(obor_profile_build >= 3839) return;
    if(obor_profile_build >= 3833)
    {
        first_map = obor_grammar_first_3;
        follow_map = obor_grammar_follow_3;
    }
    else if(obor_profile_build >= 3816)
    {
        first_map = obor_grammar_first_2;
        follow_map = obor_grammar_follow_2;
    }
    else if(obor_profile_build >= 3810)
    {
        first_map = obor_grammar_first_1;
        follow_map = obor_grammar_follow_1;
    }
    else
    {
        first_map = obor_grammar_first_0;
        follow_map = obor_grammar_follow_0;
    }
    for(i=0; i<NUMPRODUCTIONS; ++i)
    {
        pset->FirstSet[i] = first_map[i] ? first_map[i] : obor_grammar_empty;
        pset->FollowSet[i] = follow_map[i] ? follow_map[i] : obor_grammar_empty;
    }
}
int obor_parser_production_number(PRODUCTION production)
{
    switch(production)
    {
    case start: return 0;
    case external_decl: return 1;
    case decl_spec: return 2;
    case decl: return 3;
    case funcDecl: return 4;
    case funcDecl1: return 5;
    case initializer: return 6;
    case parm_decl: return 7;
    case param_list: return 8;
    case param_list2: return 9;
    case decl_list: return 10;
    case decl_list2: return 11;
    case stmt_list: return 12;
    case stmt_list2: return 13;
    case stmt: return 14;
    case expr_stmt: return 15;
    case comp_stmt: return 16;
    case comp_stmt2: return 17;
    case comp_stmt3: return 18;
    case select_stmt: return 19;
    case opt_else: return 20;
    case iter_stmt: return 21;
    case opt_expr_stmt: return 22;
    case defer_expr_stmt: return 23;
    case jump_stmt: return 24;
    case opt_expr: return 25;
    case expr: return 26;
    case assignment_op: return 27;
    case assignment_expr: return 28;
    case assignment_expr2: return 29;
    case const_expr: return 30;
    case log_or_expr: return 31;
    case log_or_expr2: return 32;
    case log_and_expr: return 33;
    case log_and_expr2: return 34;
    case eq_op: return 35;
    case equal_expr: return 36;
    case equal_expr2: return 37;
    case rel_op: return 38;
    case rel_expr: return 39;
    case rel_expr2: return 40;
    case add_op: return 41;
    case add_expr: return 42;
    case add_expr2: return 43;
    case mult_op: return 44;
    case mult_expr: return 45;
    case mult_expr2: return 46;
    case unary_expr: return 47;
    case postfix_expr: return 48;
    case postfix_expr2: return 49;
    case arg_expr_list: return 50;
    case arg_expr_list2: return 51;
    case primary_expr: return 52;
    case constant: return 53;
    default: return -1;
    }
}
#endif
