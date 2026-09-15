# Source provenance

This distribution packages six pinned OpenBOR source snapshots with a shared
libretro platform layer. `src/pin.json` records the upstream repository,
full commit IDs and dependency archive SHA-256 hashes. Each engine has an
`ANYBOR-SOURCE.json` manifest identifying the original and distributed hash
of every retained upstream file. This makes the port's modifications
distinguishable from upstream code without importing upstream Git history.
The shared port, frontend glue and build tooling are included as source.

Engine imports in the public Git history include the portable circle and
fixed-width endian adaptations from their first appearance. Their inventories
retain the original upstream hashes separately from the distributed hashes;
these adapted imports are not unmodified upstream snapshots.

[MODIFICATIONS.md](MODIFICATIONS.md) explains the current differences from each
pinned OpenBOR build and the shared port's additions. Its generated per-engine
inventories link modified files to their original source and explain their
changes. The circle and endian adaptations are present from the first public
engine imports; the replaced implementations are not distributed.
The manifests also record omitted upstream engine files and their hashes;
unchanged files are identified without modification claims. These records are
documentation; the included sources build directly.

The source snapshots originate from the [OpenBOR repository](https://github.com/DCurrent/openbor).
The 2011 engine's original no-sale license remains in force for that included
snapshot. Later engine licenses are preserved separately. No later license
change is applied retroactively to the older engine.

The circle rasterizer in `src/port/libretro/obor_circle.h` is a new integer
geometry implementation for this port. It enumerates symmetric integer
coordinates using the circle equation and clips them to the target surface.
The engine wrappers preserve the original pixel-writing interface.
`obor_adpcm.c` implements IMA ADPCM's predictor, quantizer adaptation and
nibble packing for the OpenBOR audio API. Its algorithm is described by the
[IMA format reference linked from RFC 3551](https://www.rfc-editor.org/rfc/rfc3551#section-4.5.1).
`obor_endian.h` supplies fixed-width integer conversions for the engine APIs,
replacing the historical SDL-derived header and its assumption that an x86-64
`long` is 64 bits (which is false on Windows).
These original replacement implementations carry retrodiv's BSD-3-Clause notice.

Upstream implementation comments and credits are retained exactly as received,
including unresolved or tentative author credits; no author is invented or
reassigned by the port. As background on the engine's licensing lineage, the
recovered OpenBOR `List.c` at
commit [`473ee64634faa77b2ac4302f71987d600774c199`](https://github.com/DCurrent/openbor/blob/473ee64634faa77b2ac4302f71987d600774c199/engine/source/scriptlib/List.c) contains the OpenBOR Team 2004–2011 copyright and its BSD
license reference, preceding the later list revisions. Existing copyrights,
license conditions and named contributors are preserved.

Original AnyBOR code and retrodiv's original modifications are licensed under
BSD-3-Clause, as scoped in [LICENSES.md](LICENSES.md). A modification notice does not
replace the license of the surrounding upstream file. The original engine
licenses and third-party notices remain unchanged, and the former combined BSD
notice is retained separately for its existing grants and attributions.

Alex Pankratov's halloc headers explicitly grant a BSD license by reference
to `opensource.org/licenses/bsd-license.php`, the historical URL for the
[three-clause BSD license](https://opensource.org/license/bsd-3-clause).
The [author's repository](https://github.com/apankrat/halloc) confirms that
licensing, including the 1.2.1 history. The accompanying `LICENSE` supplies
the referenced terms locally with the original 2004–2010 copyright.

The WebM helpers are the files bundled by the pinned OpenBOR releases;
notices are collected from every included version. The miniz amalgamation's
internal copyright blocks, libco's backend notices, libvpx's `PATENTS` and
the x86inc assembly notice are included in the license dossier. Compiler
runtime license texts are pinned to their source URLs and hashes in
`LICENSES/runtime-sources.json`. These reference texts cover the runtime
families described in `LICENSES.md`; each build's tool versions are recorded
in its receipt.

The unused libvpx motion-estimation fixtures under
`build_debug/non_greedy_mv_test_files/` are omitted from the source distribution.
They include two photographic frames stored as numeric text and four auxiliary
data files. AnyBOR builds only the decoders and disables libvpx's unit tests;
its own runtime checks generate their test content. The local dependency
manifest records this omission; the upstream archive pin remains unchanged.

`SOURCES.json` inventories the exported source tree. `SBOM.spdx.json` maps
the included packages and license expressions. `make check` validates the
inventory and notices. `make release` verifies that its binary, notices and
sources match the build receipt, then checks the contents of the resulting
ZIP. Builds need only this directory, an installed compiler/toolchain and
the host build utilities listed in `README.md`; they do not download code.

The generic buffer transform compiler/interpreter is original AnyBOR work.
It provides only generic buffer execution and source compilation.
