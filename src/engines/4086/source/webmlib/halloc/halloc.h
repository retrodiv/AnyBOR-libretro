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

#ifndef _LIBP_HALLOC_H_
#define _LIBP_HALLOC_H_

#include <stddef.h>  /* size_t */

/*
 *	Core API
 */
void * halloc (void * block, size_t len);
void   hattach(void * block, void * parent);

/*
 *	standard malloc/free api
 */
void * h_malloc (size_t len);
void * h_calloc (size_t n, size_t len);
void * h_realloc(void * p, size_t len);
void   h_free   (void * p);
char * h_strdup (const char * str);

/*
 *	the underlying allocator
 */
typedef void * (* realloc_t)(void * ptr, size_t len);

extern realloc_t halloc_allocator;

#endif

