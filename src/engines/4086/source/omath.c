/* AnyBOR modification record: 2026-11-16.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Restore the original inverse-trigonometric helpers and their declarations
 * without replacing their source-defined numerical branches. Existing
 * inverse-square-root and angle lookup definitions remain in the original
 * utility unit.
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

#include "omath.h"

//#define PI 3.14159265358979323846264338327950288419716939937510
//#define PI 3.1415926535f


// Return a + b given |b| < |a|.
double2 Add112RightSmaller(double a, double b)
{
    double d0 = a + b, d1 = b - (d0 - a);
    return (double2) { d0, d1 };
}

// Return a + b with relative error below 2**-103 given |b| < |a|.
double2 Add212RightSmaller(double2 a, double b)
{
    double
        c0 = a.d0 + b,
        c1 = a.d0 - c0 + b + a.d1,
        d0 = c0 + c1,
        d1 = c0 - d0 + c1;
    return (double2) { d0, d1 };
}

/*	Return a + b with relative error below 2**-103 and then rounded to
    double given |b| < |a|.
*/
double Add221RightSmaller(double2 a, double2 b)
{
    double
        c0 = a.d0 + b.d0,
        c1 = a.d0 - c0 + b.d0 + b.d1 + a.d1,
        d0 = c0 + c1;
    return d0;
}

/*	Return a - b with relative error below 2**-103 and then rounded to a
    double given |b| < |a|.
*/
double Sub211RightSmaller(double2 a, double b)
{
    double
        c0 = a.d0 - b,
        c1 = a.d0 - c0 - b + a.d1,
        d0 = c0 + c1;
    return d0;
}


/*	Return a - b with relative error below 2**-103 and then rounded to
    double given |b| < |a|.
*/
double Sub221RightSmaller(double2 a, double2 b)
{
    double
        c0 = a.d0 - b.d0,
        c1 = a.d0 - c0 - b.d0 - b.d1 + a.d1,
        d0 = c0 + c1;
    return d0;
}

// Return a * b, given |a|, |b| < 2**970.
double2 Mul112(double a, double b)
{
    static const double c = 0x1p27 + 1;

    double
        ap = a * c,     bp = b * c,
        a0 = (a-ap)+ap, b0 = (b-bp)+bp,
        a1 = a - a0,    b1 = b - b0,
        d0 = a * b,
        d1 = a0*b0 - d0 + a0*b1 + a1*b0 + a1*b1;
    return (double2) { d0, d1 };
}

/*	Return approximately a * b - 1 given |a|, |b| < 2**970 and a * b is
    very near 1.
*/
double Mul121Special(double a, double2 b)
{
    static const double c = 0x1p27 + 1;

    double
        ap = a * c,     bp = b.d0 * c,
        a0 = (a-ap)+ap, b0 = (b.d0-bp)+bp,
        a1 = a - a0,    b1 = b.d0 - b0,
        m1 = a0*b0 - 1 + a0*b1 + a1*b0 + a1*b1 + a*b.d1;
    return m1;
}

// Return approximately a * b given |a|, |b| < 2**970.
double Mul221(double2 a, double2 b)
{
    static const double c = 0x1p27 + 1;

    double
        ap = a.d0 * c,     bp = b.d0 * c,
        a0 = (a.d0-ap)+ap, b0 = (b.d0-bp)+bp,
        a1 = a.d0 - a0,    b1 = b.d0 - b0,
        m0 = a.d0 * b.d0,
        m1 = a0*b0 - m0 + a0*b1 + a1*b0 + a1*b1 + (a.d0*b.d1 + a.d1*b.d0),
        d0 = m0 + m1;
    return d0;
}

// Return a * b with relative error below 2**-102 given |a|, |b| < 2**970.
double2 Mul222(double2 a, double2 b)
{
    static const double c = 0x1p27 + 1;

    double
        ap = a.d0 * c,     bp = b.d0 * c,
        a0 = (a.d0-ap)+ap, b0 = (b.d0-bp)+bp,
        a1 = a.d0 - a0,    b1 = b.d0 - b0,
        m0 = a.d0 * b.d0,
        m1 = a0*b0 - m0 + a0*b1 + a1*b0 + a1*b1 + (a.d0*b.d1 + a.d1*b.d0),
        d0 = m0 + m1,
        d1 = m0 - d0 + m1;
    return (double2) { d0, d1 };
}


// Return arcsine(x) given |x| <= .5, with the same properties as asin.
double Center(double x)
{
	if (-0x1.7137449123ef5p-26 <= x && x <= +0x1.7137449123ef5p-26)
		return -0x1p-1022 < x && x < +0x1p-1022
			// Generate underflow and inexact and return x.
			?  x - x*x
			// Generate inexact and return x.
			: x * (Tiny + 1);

	static const double p03 =  0.1666666666666558995379880;
	static const double p05 =  0.0750000000029696112392353;
	static const double p07 =  0.0446428568582815922683933;
	static const double p09 =  0.0303819580081956423799529;
	static const double p11 =  0.0223717830666671020710108;
	static const double p13 =  0.0173593516996479249428647;
	static const double p15 =  0.0138885410156894774969889;
	static const double p17 =  0.0121483892822292648695383;
	static const double p19 =  0.0066153165197009078340075;
	static const double p21 =  0.0192942786775238654913582;
	static const double p23 = -0.0158620440988475212803145;
	static const double p25 =  0.0316658385792867081040808;

	// Square x.
	double x2 = x * x;

	return ((((((((((((
		+ p25) * x2
		+ p23) * x2
		+ p21) * x2
		+ p19) * x2
		+ p17) * x2
		+ p15) * x2
		+ p13) * x2
		+ p11) * x2
		+ p09) * x2
		+ p07) * x2
		+ p05) * x2
		+ p03) * x2 * x + x;
}

// Return arcsine(x) given .5 < x, with the same properties as asin.
double Tail(double x)
{
	if (1 <= x)
		return 1 == x
			// If x is 1, generate inexact and return Pi/2 rounded down.
			?  0x3.243f6a8885a308d313198a2e03707344ap-1 + Tiny
			// If x is outside the domain, generate invalid and return NaN.
			: Infinity - Infinity;

	static const double p01 =  0.2145993335526539017488949;
	static const double p02 = -0.0890259194305537131666744;
	static const double p03 =  0.0506659694457588602631748;
	static const double p04 = -0.0331919619444009606270380;
	static const double p05 =  0.0229883479552557203133368;
	static const double p06 = -0.0156746038587246716524035;
	static const double p07 =  0.0097868293573384001221447;
	static const double p08 = -0.0052049731575223952626203;
	static const double p09 =  0.0021912255981979442677477;
	static const double p10 = -0.0006702485124770180942917;
	static const double p11 =  0.0001307564187657962919394;
	static const double p12 = -0.0000121189820098929624806;

	double polynomial = ((((((((((((
		+ p12) * x
		+ p11) * x
		+ p10) * x
		+ p09) * x
		+ p08) * x
		+ p07) * x
		+ p06) * x
		+ p05) * x
		+ p04) * x
		+ p03) * x
		+ p02) * x
		+ p01) * x;

	#if UseLongDouble
		static const long double HalfPi = 0x3.243f6a8885a308d313198a2ep-1L;
		static const long double p00 = -1.5707961988153774692344105L;

		return HalfPi + sqrtl(1-x) * (polynomial + p00);
	#else	// #if UseLongDouble
		static const double2
			HalfPi = { 0x1.921fb54442d18p+0, 0x1.1a62633145c07p-54 },
			p00 = { -0x1.921fb31e97d96p0, +0x1.eab77149ad27cp-54 };

		// Estimate 1 / sqrt(1-x).
		double e = 1 / sqrt(1-x);

		double2 ex = Mul112(e, 1-x);		// e * x.
		double e2x = Mul121Special(e, ex);	// e**2 * x - 1.

		// Set t0 to an improved approximation of sqrt(1-x) with Newton-Raphson.
		double2 t0 = Add212RightSmaller(ex, ex.d0 * -.5 * e2x);

		// Calculate pi/2 + sqrt(1-x) * p(x).
		return Add221RightSmaller(HalfPi, Mul222(
			t0,
			Add212RightSmaller(p00, polynomial)));
	#endif	// #if UseLongDouble
}


// Return arccosine(x) given .4 <= |x| <= .6, with the same properties as acos.
double Gap(double x)
{
	static const double p03 = + .1666666544260252354339083;
	static const double p05 = + .7500058936188719422797382e-1;
	static const double p07 = + .4462999611462664666589096e-1;
	static const double p09 = + .3054999576148835435598555e-1;
	static const double p11 = + .2090953485621966528477317e-1;
	static const double p13 = + .2626916834046217573905021e-1;
	static const double p15 = - .2496419961469848084029243e-1;
	static const double p17 = + .1336320190979444903198404;
	static const double p19 = - .2609082745402891409913617;
	static const double p21 = + .4154485118940996442799104;
	static const double p23 = - .3718481677216955169129325;
	static const double p25 = + .1791132167840254903934055;

	// Square x.
	double x2 = x * x;

	double poly = ((((((((((((
		+ p25) * x2
		+ p23) * x2
		+ p21) * x2
		+ p19) * x2
		+ p17) * x2
		+ p15) * x2
		+ p13) * x2
		+ p11) * x2
		+ p09) * x2
		+ p07) * x2
		+ p05) * x2
		+ p03) * x2 * x;

	#if UseLongDouble
		static const long double
			HalfPi = 0x3.243f6a8885a308d313198a2e03707344ap-1L;
		return HalfPi - (poly + (long double) x);
	#else	// #if UseLongDouble
		static const double2
			HalfPi = { 0x1.921fb54442d18p+0, 0x1.1a62633145c07p-54 };
		return Sub221RightSmaller(HalfPi, Add112RightSmaller(x, poly));
	#endif	// #if UseLongDouble
}


// Return arccosine(x) given +.6 < x, with the same properties as acos.
double pTail(double x)
{
	if (1 <= x)
		return 1 == x
			// If x is 1, return zero.
			? 0
			// If x is outside the domain, generate invalid and return NaN.
			: Infinity - Infinity;

	static const double p01 = - .2145900291823555067724496;
	static const double p02 = + .8895931658903454714161991e-1;
	static const double p03 = - .5037781062999805015401690e-1;
	static const double p04 = + .3235271184788013959507217e-1;
	static const double p05 = - .2125492340970560944012545e-1;
	static const double p06 = + .1307107321829037349021838e-1;
	static const double p07 = - .6921689208385164161272068e-2;
	static const double p08 = + .2912114685670939037614086e-2;
	static const double p09 = - .8899459104279910976564839e-3;
	static const double p10 = + .1730883544880830573920551e-3;
	static const double p11 = - .1594866672026418356538789e-4;

	double t0 = (((((((((((
		+ p11) * x
		+ p10) * x
		+ p09) * x
		+ p08) * x
		+ p07) * x
		+ p06) * x
		+ p05) * x
		+ p04) * x
		+ p03) * x
		+ p02) * x
		+ p01) * x;

	#if UseLongDouble
		static const long double p00 = +1.5707956046853235350824205L;
		return sqrtl(1-x) * (t0 + p00);
	#else	// #if UseLongDouble
		static const double2
			p00 = { 0x1.921fa926d2f24p0, +0x1.b4a23d0ecbb40p-59 };
			/*	p00.d1 might not be needed.  However, omitting it brings the
				sampled error to .872 ULP.  We would need to prove this is okay.
			*/

		// Estimate square root to double precision.
		double e = 1 / sqrt(1-x);

		// Refine estimate using Newton-Raphson.
		double2 ex = Mul112(e, 1-x);
		double e2x = Mul121Special(e, ex);
		double2 t1 = Add212RightSmaller(ex, ex.d0 * -.5 * e2x);

		// Return sqrt(1-x) * (t0 + p00).
		return Mul221(t1, Add212RightSmaller(p00, t0));
	#endif	// #if UseLongDouble
}


// Return arccosine(x) given x < -.6, with the same properties as acos.
double nTail(double x)
{
	if (x <= -1)
		return -1 == x
			// If x is -1, generate inexact and return pi rounded toward zero.
			? 0x3.243f6a8885a308d313198a2e03707344ap0 + Tiny
			// If x is outside the domain, generate invalid and return NaN.
			: Infinity - Infinity;

	static const double p00 = +1.5707956513160834076561054;
	static const double p01 = + .2145907003920708442108238;
	static const double p02 = + .8896369437915166409934895e-1;
	static const double p03 = + .5039488847935731213671556e-1;
	static const double p04 = + .3239698582040400391437898e-1;
	static const double p05 = + .2133501549935443220662813e-1;
	static const double p06 = + .1317423797769298396461497e-1;
	static const double p07 = + .7016307696008088925432394e-2;
	static const double p08 = + .2972670140131377611481662e-2;
	static const double p09 = + .9157019394367251664320071e-3;
	static const double p10 = + .1796407754831532447333023e-3;
	static const double p11 = + .1670402962434266380655447e-4;

	double poly = sqrt(1+x) * ((((((((((((
		+ p11) * x
		+ p10) * x
		+ p09) * x
		+ p08) * x
		+ p07) * x
		+ p06) * x
		+ p05) * x
		+ p04) * x
		+ p03) * x
		+ p02) * x
		+ p01) * x
		+ p00);

	#if UseLongDouble
		static const long double Pi = 0x3.243f6a8885a308d313198a2e03707344ap0L;
		return Pi - poly;
	#else	// #if UseLongDouble
		static const double2
			Pi = { 0x1.921fb54442d18p+1, 0x1.1a62633145c07p-53 };
		return Sub211RightSmaller(Pi, poly);
	#endif	// #if UseLongDouble
}

/*	Return arctangent(x) given that 0x1p-27 < |x| <= 1/2, with the same
	properties as atan.
*/
double atani0(double x)
{
	static const double p03 = -0x1.555555555551Bp-2;
	static const double p05 = +0x1.99999999918D8p-3;
	static const double p07 = -0x1.2492492179CA3p-3;
	static const double p09 = +0x1.C71C7096C2725p-4;
	static const double p11 = -0x1.745CF51795B21p-4;
	static const double p13 = +0x1.3B113F18AC049p-4;
	static const double p15 = -0x1.10F31279EC05Dp-4;
	static const double p17 = +0x1.DFE7B9674AE37p-5;
	static const double p19 = -0x1.A38CF590469ECp-5;
	static const double p21 = +0x1.56CDB5D887934p-5;
	static const double p23 = -0x1.C0EB85F543412p-6;
	static const double p25 = +0x1.4A9F5C4724056p-7;

	// Square x.
	double x2 = x * x;

	return ((((((((((((
		+ p25) * x2
		+ p23) * x2
		+ p21) * x2
		+ p19) * x2
		+ p17) * x2
		+ p15) * x2
		+ p13) * x2
		+ p11) * x2
		+ p09) * x2
		+ p07) * x2
		+ p05) * x2
		+ p03) * x2 * x + x;
}


/*	Return arctangent(x) given that 1/2 < x <= 3/4, with the same properties as
	atan.
*/
double atani1(double x)
{
	static const double p00 = +0x1.1E00BABDEFED0p-1;
	static const double p01 = +0x1.702E05C0B8155p-1;
	static const double p02 = -0x1.4AF2B78215A1Bp-2;
	static const double p03 = +0x1.5D0B7E9E69054p-6;
	static const double p04 = +0x1.A1247CA5D9475p-4;
	static const double p05 = -0x1.519E110F61B54p-4;
	static const double p06 = +0x1.A759263F377F2p-7;
	static const double p07 = +0x1.094966BE2B531p-5;
	static const double p08 = -0x1.09BC0AB7F914Cp-5;
	static const double p09 = +0x1.FF3B7C531AA4Ap-8;
	static const double p10 = +0x1.950E69DCDD967p-7;
	static const double p11 = -0x1.D88D31ABC3AE5p-7;
	static const double p12 = +0x1.10F3E20F6A2E2p-8;

	double y = x - 0x1.4000000000027p-1;

	return ((((((((((((
		+ p12) * y
		+ p11) * y
		+ p10) * y
		+ p09) * y
		+ p08) * y
		+ p07) * y
		+ p06) * y
		+ p05) * y
		+ p04) * y
		+ p03) * y
		+ p02) * y
		+ p01) * y
		+ p00;
}


/*	Return arctangent(x) given that 3/4 < x <= 1, with the same properties as
	atan.
*/
double atani2(double x)
{
	static const double p00 = +0x1.700A7C580EA7Ep-01;
	static const double p01 = +0x1.21FB781196AC3p-01;
	static const double p02 = -0x1.1F6A8499714A2p-02;
	static const double p03 = +0x1.41B15E5E8DCD0p-04;
	static const double p04 = +0x1.59BC93F81895Ap-06;
	static const double p05 = -0x1.63B543EFFA4EFp-05;
	static const double p06 = +0x1.C90E92AC8D86Cp-06;
	static const double p07 = -0x1.91F7E2A7A338Fp-08;
	static const double p08 = -0x1.AC1645739E676p-08;
	static const double p09 = +0x1.152311B180E6Cp-07;
	static const double p10 = -0x1.265EF51B17DB7p-08;
	static const double p11 = +0x1.CA7CDE5DE9BD7p-14;

	double y = x - 0x1.c0000000f4213p-1;

	return (((((((((((
		+ p11) * y
		+ p10) * y
		+ p09) * y
		+ p08) * y
		+ p07) * y
		+ p06) * y
		+ p05) * y
		+ p04) * y
		+ p03) * y
		+ p02) * y
		+ p01) * y
		+ p00;
}


/*	Return arctangent(x) given that 1 < x <= 4/3, with the same properties as
	atan.
*/
double atani3(double x)
{
	static const double p00 = +0x1.B96E5A78C5C40p-01;
	static const double p01 = +0x1.B1B1B1B1B1B3Dp-02;
	static const double p02 = -0x1.AC97826D58470p-03;
	static const double p03 = +0x1.3FD2B9F586A67p-04;
	static const double p04 = -0x1.BC317394714B7p-07;
	static const double p05 = -0x1.2B01FC60CC37Ap-07;
	static const double p06 = +0x1.73A9328786665p-07;
	static const double p07 = -0x1.C0B993A09CE31p-08;
	static const double p08 = +0x1.2FCDACDD6E5B5p-09;
	static const double p09 = +0x1.CBD49DA316282p-13;
	static const double p10 = -0x1.0120E602F6336p-10;
	static const double p11 = +0x1.A89224FF69018p-11;
	static const double p12 = -0x1.883D8959134B3p-12;

	double y = x - 0x1.2aaaaaaaaaa96p0;

	return ((((((((((((
		+ p12) * y
		+ p11) * y
		+ p10) * y
		+ p09) * y
		+ p08) * y
		+ p07) * y
		+ p06) * y
		+ p05) * y
		+ p04) * y
		+ p03) * y
		+ p02) * y
		+ p01) * y
		+ p00;
}


/*	Return arctangent(x) given that 4/3 < x <= 5/3, with the same properties as
	atan.
*/
double atani4(double x)
{
	static const double p00 = +0x1.F730BD281F69Dp-01;
	static const double p01 = +0x1.3B13B13B13B0Cp-02;
	static const double p02 = -0x1.22D719C06115Ep-03;
	static const double p03 = +0x1.C963C83985742p-05;
	static const double p04 = -0x1.135A0938EC462p-06;
	static const double p05 = +0x1.13A254D6E5B7Cp-09;
	static const double p06 = +0x1.DFAA5E77B7375p-10;
	static const double p07 = -0x1.F4AC1342182D2p-10;
	static const double p08 = +0x1.25BAD4D85CBE1p-10;
	static const double p09 = -0x1.E4EEF429EB680p-12;
	static const double p10 = +0x1.B4E30D1BA3819p-14;
	static const double p11 = +0x1.0280537F097F3p-15;

	double y = x - 0x1.8000000000003p0;

	return (((((((((((
		+ p11) * y
		+ p10) * y
		+ p09) * y
		+ p08) * y
		+ p07) * y
		+ p06) * y
		+ p05) * y
		+ p04) * y
		+ p03) * y
		+ p02) * y
		+ p01) * y
		+ p00;
}


/*	Return arctangent(x) given that 5/3 < x <= 2, with the same properties as
	atan.
*/
double atani5(double x)
{
	static const double p00 = +0x1.124A85750FB5Cp+00;
	static const double p01 = +0x1.D59AE78C11C49p-03;
	static const double p02 = -0x1.8AD3C44F10DC3p-04;
	static const double p03 = +0x1.2B090AAD5F9DCp-05;
	static const double p04 = -0x1.881EC3D15241Fp-07;
	static const double p05 = +0x1.8CB82A74E0699p-09;
	static const double p06 = -0x1.3182219E21362p-12;
	static const double p07 = -0x1.2B9AD13DB35A8p-12;
	static const double p08 = +0x1.10F884EAC0E0Ap-12;
	static const double p09 = -0x1.3045B70E93129p-13;
	static const double p10 = +0x1.00B6A460AC05Dp-14;

	double y = x - 0x1.d555555461337p0;

	return ((((((((((
		+ p10) * y
		+ p09) * y
		+ p08) * y
		+ p07) * y
		+ p06) * y
		+ p05) * y
		+ p04) * y
		+ p03) * y
		+ p02) * y
		+ p01) * y
		+ p00;
}

// See documentation above.
double aasin(double x)
{
	if (x < -.5)
		return -Tail(-x);
	else if (x <= .5)
		return Center(x);
	else
		return +Tail(+x);
}

double aacos(double x)
{
	if (x < -.4)
		if (x < -.6)
			return nTail(x);
		else
			return Gap(x);
	else if (x <= +.4)
		return Center(x);
	else
		if (x <= +.6)
			return Gap(x);
		else
			return pTail(x);
}


// See documentation above.
double aatan(double x)
{
	if (x < 0)
		if (x < -1)
			if (x < -5/3.)
				if (x < -2)
					return -Tail(-x);
				else
					return -atani5(-x);
			else
				if (x < -4/3.)
					return -atani4(-x);
				else
					return -atani3(-x);
		else
			if (x < -.5)
				if (x < -.75)
					return -atani2(-x);
				else
					return -atani1(-x);
			else
				if (x < -0x1.d12ed0af1a27fp-27)
					return atani0(x);
				else
					if (x <= -0x1p-1022)
						// Generate inexact and return x.
						return (Tiny + 1) * x;
					else
						if (x == 0)
							return x;
						else
							// Generate underflow and return x.
							return x*Tiny + x;
	else
		if (x <= +1)
			if (x <= +.5)
				if (x <= +0x1.d12ed0af1a27fp-27)
					if (x < +0x1p-1022)
						if (x == 0)
							return x;
						else
							// Generate underflow and return x.
							return x*Tiny + x;
					else
						// Generate inexact and return x.
						return (Tiny + 1) * x;
				else
					return atani0(x);
			else
				if (x <= +.75)
					return +atani1(+x);
				else
					return +atani2(+x);
		else
			if (x <= +5/3.)
				if (x <= +4/3.)
					return +atani3(+x);
				else
					return +atani4(+x);
			else
				if (x <= +2)
					return +atani5(+x);
				else
					return +Tail(+x);
}

