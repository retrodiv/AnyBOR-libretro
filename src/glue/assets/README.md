# Preparation backgrounds

The single `OpenBOR_Logo_3200x1800.png` master adapts the OpenBOR engine artwork in
build 7123, upstream commit
`81049d95c50c4c26e2637cc89ab3056bfcc77d16`, published with BSD-3-Clause terms.
The original logo design is credited to Fightn' Words in upstream commit
`5af02b76cd2601faf02f057d00e56ddab737e83f` (7 May 2008).

The preparation layout was adapted for AnyBOR in 2026, leaving room below the
artwork for an animated indicator. The OpenBOR name identifies the underlying
engine. AnyBOR is an independent adaptation; no upstream endorsement is claimed.
The accompanying `LICENSE` preserves the upstream terms and notices.

The build derives 320x240, 480x272 and 640x480 backgrounds from this master
with centred cover cropping and Lanczos3 filtering. These embedded versions
are used directly at matching native resolutions. Other sizes use the master
with centred cover cropping and antialiased Lanczos3 filtering at runtime.
Runtime resizes exist only in memory until native video takes over; they are
not cached or written to disk.

`tools/embed_loading_background.py` uses Pillow on the build host to generate
the losslessly compressed RGB header for each compilation. The generated
source copy also supports hosts without Pillow when its master and generator
hashes still match. Changing either input requires Pillow to regenerate that
copy. No smaller PNGs need to be maintained.

The existing miniz implementation decodes the
chosen asset in memory. The core draws the indicator separately and needs no
external image file. Preparation and gameplay use the same video presentation
and CRT adjustment path.
