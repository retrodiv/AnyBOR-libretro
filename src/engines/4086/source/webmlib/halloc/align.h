/* AnyBOR modification record: 2026-10-19.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Import the native 4153 media component, retaining its upstream authorship
 * and license notices.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 *	Copyright (c) 2004-2010 Alex Pankratov. All rights reserved.
 *
 *	Hierarchical memory allocator, 1.2.1
 *	http://swapped.cc/halloc
 */

/*
 *	The program is distributed under terms of BSD license.
 *	You can obtain the copy of the license by visiting:
 *
 *	http://www.opensource.org/licenses/bsd-license.php
 */

#ifndef _LIBP_ALIGN_H_
#define _LIBP_ALIGN_H_

#ifdef _MSC_VER

/*
 * MSVC defines max_align_t as a double.
 */
typedef double max_align_t;

#elif !defined(__CLANG_MAX_ALIGN_T_DEFINED) && !defined(_GCC_MAX_ALIGN_T)

/*
 *	a type with the most strict alignment requirements
 */
union max_align
{
	char   c;
	short  s;
	long   l;
	int    i;
	float  f;
	double d;
	void * v;
	void (*q)(void);
};

typedef union max_align max_align_t;

#endif

#endif

