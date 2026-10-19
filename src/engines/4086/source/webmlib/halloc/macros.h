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

#ifndef _LIBP_MACROS_H_
#define _LIBP_MACROS_H_

#include <stddef.h>  /* offsetof */

/*
 	restore pointer to the structure by a pointer to its field
 */
#define structof(p,t,f) ((t*)(- (ptrdiff_t) offsetof(t,f) + (char*)(p)))

/*
 *	redefine for the target compiler
 */
#ifdef _WIN32
#define static_inline static __inline
#else
#define static_inline static __inline__
#endif


#endif

