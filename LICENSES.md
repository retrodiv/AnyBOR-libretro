# Licensing and redistribution

The [BSD-3-Clause license](LICENSE) at the repository root covers original AnyBOR work
by retrodiv: the original port and glue, compatibility helpers, build tools,
tests, examples, project documentation and retrodiv's original modifications.
The same grant is retained in [the notice dossier](LICENSES/AnyBOR-original-BSD-3-Clause.txt).
It does not relicense third-party code or other authors' contributions.
Files containing upstream code retain that code's notices and conditions;
their AnyBOR modification notices apply BSD-3-Clause only to retrodiv's contributions.

AnyBOR contains OpenBOR / Open Beats of Rage, originally by Senile Team
and subsequently developed by the OpenBOR Team. The full core combines
several licenses. Its inclusion of OpenBOR build 3400 restricts sale: **do
not sell this combined source distribution or its binaries without the
specific prior written permission required by that engine's license.**
Free redistribution with the supplied notices is permitted by those terms.
This restriction also applies when distributing a modified combined core.
The upstream name and attribution are retained as that license requires.
No endorsement by Senile Team, OpenBOR Team or libretro is claimed.

| Component / source path | Terms and attribution |
|---|---|
| `src/engines/3400/` | Custom OpenBOR license, including its no-sale clauses; exact text in that directory's `LICENSE` and `LICENSES/OpenBOR-3400.txt`. Retrodiv's original AnyBOR modifications are BSD-3-Clause; the engine's conditions remain in force |
| Other `src/engines/<build>/` directories | Each pinned engine's BSD-3-Clause license; retrodiv's original AnyBOR modifications are BSD-3-Clause, and embedded components below retain their own terms |
| Original port and glue, compatibility helpers, build tools, tests, examples and project documentation | BSD-3-Clause, `LICENSE`; existing upstream authorship notices remain authoritative for adapted code |
| `src/port/libretro/libco/` | ISC; `valgrind.h` has its separate permissive header license, reproduced in the notice dossier |
| `src/port/libretro/dlmalloc.inc` | Doug Lea's public-domain dedication, with the CC0 waiver referenced in its header |
| `src/third_party/libretro.h` | MIT, libretro API contributors |
| `src/third_party/miniz.c`, `miniz.h` | MIT; all amalgamated notices, including Rich Geldreich, RAD Game Tools and Martin Raiber, are retained |
| `src/engines/*/source/webmlib/nestegg/` | ISC, Mozilla Foundation and Matthew Gregan |
| `src/engines/*/source/webmlib/halloc/` | BSD-3-Clause, Alex Pankratov; full text accompanies the original explicit BSD-license reference |
| Other WebM helpers, including YUV conversion | Original per-file Xiph.Org, Google, Sam Lantinga, University of California, Erik Corry and Brown University notices, as applicable to each snapshot |
| `src/deps/zlib/` | Zlib license |
| `src/deps/libpng/` | PNG Reference Library License version 2; preserved notices cover the earlier incorporated versions too |
| `src/deps/libogg/`, `src/deps/libvorbis/` | BSD-3-Clause, Xiph.Org Foundation and named contributors |
| `src/deps/libvpx/` | BSD-3-Clause and Google's additional patent grant in `PATENTS`; assembler helpers retain their own permissive notices, including `third_party/x86inc/x86inc.asm` |

The former combined BSD notice is preserved verbatim in
[`LICENSES/AnyBOR-BSD-3-Clause.txt`](LICENSES/AnyBOR-BSD-3-Clause.txt), including
its upstream attributions. Earlier BSD grants are not withdrawn. That retained
notice does not extend BSD-3-Clause to components with different licenses or
replace the BSD-3-Clause grant for the current original AnyBOR work.

The combined DLL/SO must be redistributed under all applicable component terms;
it is not an exclusively BSD-3-Clause-licensed binary. Keep all applicable notices,
the other component notices and the OpenBOR 3400 conditions with the distribution.
Licensing the original port under BSD-3-Clause does not grant permission to sell the
combined core containing that engine.

Every supported binary statically includes the five libraries in `src/deps/`.
Decoder-only libvpx builds are used. The source distribution also retains
build-support files with their original licenses, including GPL Autoconf
auxiliary scripts and their applicable exceptions. These scripts are build
tools; their license does not change the license of the libraries they build.
The removed OpenBOR graphics-filter implementations are not included.
The replaced historical circle and SDL-derived endian implementations are
also excluded from the published change records. Their descriptive summaries
identify the replaced implementations without reproducing or relicensing that code.

The `LICENSES/` directory and its checksummed `index.json` preserve the exact
component notices. `NOTICE.txt` assembles that documentation, including
individual source-header notices. It is embedded verbatim in every release
DLL/SO, including stripped cores delivered as a single file by an updater.
On loading content the core attempts to write `anybor-license-notices.txt` in the
frontend's save directory; the write is best-effort.
Release ZIPs include the dossier as ordinary files.
Retain the dossier when redistributing either form; do not remove the embedded
documentation when producing a bare core.

Compiler runtime notices are included separately. GNU runtime components use
GPL-3.0 with the GCC Runtime Library Exception where their headers provide
that exception; this permits the eligible compilation used here. Windows
builds also retain MinGW-w64 and winpthreads notices. Android NDK builds
retain LLVM compiler-rt, libc++, libc++abi and libunwind notices, including their LLVM
exceptions and legacy notices. These texts apply to the corresponding
runtime components, not to all of AnyBOR. `build.json` records the actual
compiler, linker, dynamic imports, static dependencies and source hashes for
each packaged binary. Operating-system libraries are dynamically imported
and are not copied into the packages.

Games are separately licensed works. This distribution supplies no third-party games,
game artwork, soundtracks, commercial game executables or BIOS files, and
grants no rights to third-party game content. Load content you are entitled
to use. Project names identify compatibility and authorship; their presence
does not grant trademark rights.

