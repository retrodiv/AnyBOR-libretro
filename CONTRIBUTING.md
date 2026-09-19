# Contributing

The core builds from this repository alone. See README.md for toolchains.
Changes to the public sources can be submitted as patches or pull requests;
keep each engine's upstream notices and describe affected engine builds.
The maintained source snapshot is assembled from pinned OpenBOR versions
with a shared port layer. PROVENANCE.md and the per-engine modification
manifests identify those origins. [MODIFICATIONS.md](MODIFICATIONS.md) explains
the changes and links the per-engine file inventories.
Update the relevant source notice and modification record when changing an
engine file; preserve each file's baseline and existing modification explanations.

```sh
make check
NUMPROC=4 make
make check-binary BINARY=anybor_libretro.so
make release
```

Run a local content test for changes affecting gameplay or save states.
Only include test content and assets that you have authority to distribute,
with their license and attribution. Do not attach commercial or third-party
game PAKs, extracted resources, private logs, keys or memory dumps to public
issues. Minimal reproductions with original assets are preferred.

By submitting a contribution, identify its author and source and provide it
under the license applicable to the affected component. Original contributions
to the AnyBOR port, tools, tests, examples and documentation use BSD-3-Clause.
Work in upstream components must preserve their existing terms; separately identified
original additions use BSD-3-Clause as described in [LICENSES.md](LICENSES.md).
Flag incorporated third-party material and retain its terms. Changes to external components
must identify the original source and the modifications. A contribution
does not relicense code or assets owned by other parties.

Source hashes in SOURCES.json describe the distributed snapshot. The build
receipt records the actual source hashes, toolchain and binary; packaging
rejects binaries whose source tree or notice dossier has changed since the
build. Licensing metadata is documentation, not a substitute for review of
new third-party material.

After reviewing source edits, run `python3 tools/update_manifest.py` and
`make check` to update and validate the local modification hashes. The updater
preserves the original upstream hashes and pins. Keep component copyright
and license notices with any changed or added third-party material.
The updater preserves existing explanations and source references; it does not
write explanations for new changes. Keep the file inventory, manifest summaries
and source/origin references in sync with the reviewed change record.
