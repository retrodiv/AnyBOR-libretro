# Libretro integration

The shared-library basename is `anybor_libretro`. `make platform=unix`
honors compiler variables supplied by Linux x86-64 and ARM64 runners;
`make platform=win64` builds the Windows x86-64 DLL. Android's entry point is
`ndk-build -C jni APP_ABI=arm64-v8a`, which installs `libs/arm64-v8a/libretro.so`
and leaves `anybor_libretro_android.so` available in the repository root.
Dependency sources are included; these build commands perform no downloads.

`.gitlab-ci.yml` extends the corresponding libretro infrastructure templates.
The metadata file `anybor_libretro.info` identifies the combined core as
`Non-commercial`, reflecting the no-sale clauses of the included OpenBOR
3400 snapshot. Its exact terms and the other component licenses accompany
the core in `LICENSES.md`, `LICENSES/` and the embedded `NOTICE.txt` dossier.

The libretro project maintains Core Updater availability and accepts the
repository into its infrastructure separately. The included metadata is
ready for [libretro-super/dist/info](https://github.com/libretro/libretro-super/tree/master/dist/info).
Build entry points follow the [core development documentation](https://docs.libretro.com/development/cores/developing-cores/)
and the [CI templates](https://git.libretro.com/libretro-infrastructure/ci-templates).
The supplied GitHub workflow builds release ZIPs on all four generic target
families. Recalbox has an additional ARM64 profile with a GLIBC 2.38 ceiling.
See [PUBLISHING.md](PUBLISHING.md) for the complete infrastructure handoff,
source packaging commands and the distinction between local verification and
acceptance by the hosted buildbot. [ANYBOR.md](ANYBOR.md) provides the core's
user documentation for the libretro documentation submission.

The content downloader supplies game content; cores are delivered through
the Core Updater. AnyBOR supplies the engine core and its diagnostic
fixture generator. Third-party game rights remain separate.
