# Installing AnyBOR

Install the `anybor_libretro` library for your platform in the frontend's core
directory and `anybor_libretro.info` in its core-info directory. The library
reports `AnyBOR` as its name to the frontend. Use that name and the installed
library path in playlists, shortcuts and launch commands.

## Configuration and data

The system and save roots are supplied by the frontend; they are not
necessarily literal folders called `system` and `saves`.

| Item | Location |
|---|---|
| Optional external configuration | `AnyBOR.ini` in the frontend system directory |
| In-game saves, settings and logs | `AnyBOR/<game>/<engine>/` below the frontend save directory |
| ZIP extraction cache | `AnyBOR-cache/zipcache/` below the frontend save directory |
| Prepared content cache | `AnyBOR-cache/input-<8-hex>/` below the frontend save directory |
| License dossier | `anybor-license-notices.txt`, attempted in the frontend save directory when content is loaded |

If the frontend sorts saves by core name, it can add its own outer core
folder, producing a path such as `saves/AnyBOR/AnyBOR/<game>/<engine>/`. Frontend
overrides, core options, controller remaps and shader presets can also have
per-core folders or filenames. Use `AnyBOR` wherever the frontend asks for
the core name.

Optional buffer adapters are configured in `AnyBOR.ini` in the frontend system
directory. See [content transforms](CONTENT_TRANSFORMS.md) for selecting an adapter
and examples of extracting an embedded archive or converting its word order.

The internal `obor_*` API, core-option keys and `OBOR_*` diagnostic/build
variables refer to OpenBOR. Their spelling is part of the interface; do not
replace those prefixes with `abor_*`.

## Backups and updates

Close the frontend and back up configuration and saves before moving data or
updating a core. The builder does not modify external frontend installations.
If a destination already exists, compare and merge deliberately; do not
overwrite newer saves or settings. Cache directories can be recreated.

Ordinary in-game saves and settings can be carried over with their directories.
Cross-build save-state compatibility is not guaranteed: snapshots contain
addresses and coroutine state. Retain a matching binary for states you still
need, and create new states after updating the binary.
