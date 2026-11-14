# Content descriptors and engine overrides

A manual engine choice in the core options takes priority over external engine
settings. With automatic selection enabled, the order is:

1. A matching engine override in the system directory's `AnyBOR.ini`.
2. The engine declared by the selected `.anybor` descriptor.
3. Verified engine-executable identities, followed by filename/content detection.

An explicit engine setting must name an available profile. Both `engine = 6330`
and `engine = v3.0 6330` select the same profile. Variants retain their suffix:
`engine = 6391-mod` or `engine = v3.0 6391-mod`. An unavailable profile is an error;
it does not silently select a neighboring build. Omitting `engine` from a
descriptor preserves automatic detection. `Auto` is not an engine override value.

## AnyBOR.ini

Place `AnyBOR.ini` in the frontend's system directory. Each rule selects an
engine for a PAK identified by its byte size and standard imohash:

```ini
[imohash:123456:0123456789abcdef0123456789abcdef.overrides]
engine = v3.0 6330
```

Obtain the selector with the supplied utility (Python standard library only):

```sh
python3 tools/content_key.py /path/to/content.pak
```

Replace the example size and digest with those of the original PAK, before any
content preparation. A selected PAK inside a ZIP uses the same identity as its
loose copy; the ZIP's name, compression and auxiliary files are not part of this
selector. These rules do not choose between multiple PAKs inside a ZIP: use a
descriptor to select the payload first. Unpacked games have no PAK identity;
their existing detection rules apply.

The size is a positive decimal integer without leading zeros. The digest is
32 hexadecimal digits, case insensitive. Imohash reads the whole file below
131,072 bytes; otherwise it reads 16,384 bytes at the beginning, midpoint and
end. It is a sampled identity, not a complete-file integrity check. SHA-256
selectors are not supported. Only rules with the selected PAK's size trigger
sampled reads. There is no bundled game-identity database.

Rules can coexist with the `[transforms]` section documented in
[content transforms](CONTENT_TRANSFORMS.md). The complete INI is bounded to
512 KiB and 256 override sections. Each override section contains exactly one
`engine` field. Duplicate selectors, malformed fields and unsupported selector
prefixes are errors. Unmatched valid rules do not alter engine detection.

## .anybor descriptors

Load a descriptor directly, or place it inside a ZIP:

```text
Content.zip
  Content.anybor
  Paks/content.pak
```

```ini
[anybor]
payload = Paks/content.pak

[overrides]
engine = 6330
```

The `[overrides]` section is optional. `payload` must name an existing `.pak` or
`.spk` file relative to the descriptor's directory. The selected file still
passes the ordinary content preparation and PACK validation. A descriptor can
select one payload even when the ZIP contains other games or auxiliary files.
Without a descriptor, ZIP loading requires one recognizable game and no
inconclusive candidates.

A ZIP may contain only one descriptor. Multiple descriptors, an invalid
descriptor, a missing target or an invalid selected PAK produce a clear load
error. The current ZIP supplies its descriptor even when extraction uses a
cache; cached descriptor text is not authoritative.

For a loose PAK, the core scans its directory for a unique valid sibling
`.anybor` targeting that PAK. Other targets do not apply; malformed sibling
descriptors are ignored with a warning. Several matching descriptors are
ambiguous. Opening a malformed descriptor directly is an error.

Descriptors are bounded to 64 KiB; sibling enumeration to 4,096 directory
entries. Absolute paths, parent/current-directory components, links, nested
descriptors and ZIP targets are rejected. Existing ZIP extraction quotas and
path validation remain in effect for the entire archive, including files not
selected by a descriptor.

INI settings and descriptors are read at load/restart. Logs identify the
selected engine and the external rule or descriptor used. A loose descriptor
uses its payload's save namespace. ZIPs retain the namespace of the original
ZIP; descriptor names do not create separate save namespaces.
