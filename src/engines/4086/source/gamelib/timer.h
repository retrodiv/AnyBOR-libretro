/* AnyBOR modification record: 2026-10-19.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the shared platform microsecond clock used by native media
 * playback.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2014 OpenBOR Team
 */

#ifndef TIMER_H
#define TIMER_H

#include "types.h"

void borTimerInit();
void borTimerExit();

/*
;----------------------------------------------------------------
; Proc:		timer_getinterval
; In:		ECX = frequency (1 to 1193181 Hz)
; Returns:	EAX = units passed since last call
; Destroys:	EBX ECX EDX
; Description:	Returns the time that passed since the last call,
;		measured in the specified frequency.
;		This function is extremely accurate, since all
;		rounding errors are compensatred for.
;		Only use for very short intervals!
;----------------------------------------------------------------
*/
unsigned timer_getinterval(unsigned freq);
unsigned timer_gettick();

/* Microsecond clock supplied by the shared platform adapter. */
u64 timer_uticks(void);

#endif
