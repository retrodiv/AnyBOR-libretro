# Content descriptors and engine overrides

A manual engine choice in the core options takes priority over external engine
settings. With automatic selection enabled, the order is:

1. A matching `zip-imohash` engine rule in the system directory's `AnyBOR.ini`.
2. A matching `pak-imohash` engine rule in that INI.
3. The engine declared by the external `.anybor` descriptor.
4. The engine declared by the descriptor inside the ZIP.
5. Verified engine-executable identities, followed by filename/content detection.

The first applicable setting wins, independently of INI section order. A manual
core option takes priority over every entry above. An invalid winning profile
is an error, rather than a reason to fall through to a lower-priority setting.

An explicit engine setting must name an available profile. Both `engine = 6330`
and `engine = v3.0 6330` select the same profile. Variants retain their suffix:
`engine = 6391-mod` or `engine = v3.0 6391-mod`. An unavailable profile is an error;
it does not silently select a neighboring build. Omitting `engine` from a
descriptor preserves automatic detection. `Auto` is not an engine override value.

## AnyBOR.ini

Place `AnyBOR.ini` in the frontend's system directory. Each rule selects an
engine for an original PAK or complete ZIP identified by its standard imohash. The prefix specifies which file is identified:

```ini
[pak-imohash:0123456789abcdef0123456789abcdef.overrides]
engine = v3.0 6330

[zip-imohash:fedcba9876543210fedcba9876543210.overrides]
engine = v3.0 6391
```

Obtain the selector with the supplied utility (Python standard library only):

```sh
python3 tools/content_key.py /path/to/content.pak
python3 tools/content_key.py /path/to/content.zip
```

The utility emits `pak-imohash` for `.pak`/`.spk` and `zip-imohash` for `.zip`,
case insensitive by extension. Replace each example selector with its output. The bare `imohash` selector prefix is not accepted.

A `pak-imohash` rule identifies the original PAK before any content
preparation. A selected PAK inside a ZIP uses the same identity as its loose copy; the ZIP's name, compression and auxiliary files are not part of this
selector. These rules do not choose between multiple PAKs inside a ZIP: use a
descriptor to select the payload first. Unpacked games have no PAK identity.

A `zip-imohash` rule identifies the complete original ZIP, including its
compressed representation, descriptor and auxiliary files. Renaming the ZIP
preserves the identity; repacking or changing its contents can change it. The
rule applies to the game selected by ordinary ZIP loading, including an unpacked
game. It does not select between multiple games or bypass archive validation.
A nonmatching ZIP rule leaves PAK rules and descriptor settings eligible.

Each selector contains 32 hexadecimal digest digits, case insensitive. The
file size is already encoded at the beginning of standard imohash as unsigned
LEB128; no separate size field is accepted. Zero, overflowing and noncanonical
size encodings are rejected. Imohash reads the whole file below
131,072 bytes; otherwise it reads 16,384 bytes at the beginning, midpoint and
end. It is a sampled identity, not a complete-file integrity check. SHA-256
selectors are not supported. Only rules of the corresponding kind and file size
trigger sampled reads. PAK and ZIP selectors have separate namespaces, even for
equal digests. There is no bundled game-identity database.

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

The `[overrides]` section is optional. `payload` must name an existing `.pak`,
`.spk` or `.zip` file relative to the descriptor's directory. The selected file still
passes ordinary ZIP extraction where applicable, content preparation and PACK
validation. A descriptor inside a ZIP can select one PAK payload even when the
ZIP contains other games or auxiliary files. A descriptor inside a ZIP cannot target another
ZIP or descriptor.
Without a descriptor, ZIP loading requires one recognizable game and no
inconclusive candidates.

A ZIP may contain only one descriptor. Multiple descriptors, an invalid
descriptor, a missing target or an invalid selected PAK produce a clear load
error. The current ZIP supplies its descriptor even when extraction uses a
cache; cached descriptor text is not authoritative.

An external descriptor can load a ZIP with the same selection and validation
as opening that ZIP directly:

```ini
[anybor]
payload = Packages/content.zip

[overrides]
engine = v3.0 6330
```

Its engine setting applies to the selected game. Omitting it preserves the
ZIP's ordinary engine selection, including an internal descriptor setting.

For a loose PAK or ZIP, the core scans its directory for a unique valid sibling
`.anybor` targeting that file. Other targets do not apply; malformed sibling
descriptors are ignored with a warning. Several matching descriptors are
ambiguous. Opening a malformed descriptor directly is an error.

Descriptors are bounded to 64 KiB; sibling enumeration to 4,096 directory
entries. Absolute paths, parent/current-directory components, links and
descriptor targets are rejected.
ZIP targets are allowed only in external descriptors; nested ZIP loading is
rejected. Existing ZIP extraction quotas and path validation remain in effect for the entire archive, including files not
selected by a descriptor.

INI settings and descriptors are read at load/restart. Logs identify the
selected engine and the external rule or descriptor used. A loose descriptor
uses its payload's save namespace, whether the payload is a PAK or ZIP.
ZIPs retain the namespace of the original ZIP; descriptor names do not create separate save
namespaces.

## Descriptor controls and labels

`[controls]` maps the core's logical source actions to engine actions for this
content. Names are `up`, `down`, `left`, `right`, `attack`, `attack2`, `attack3`,
`attack4`, `jump`, `special`, `start` and `escape`. A destination of `none`
disables that source. Unspecified sources retain their mapping. Simultaneous
sources mapped to one action combine without releasing each other.

`[labels]` supplies optional functional labels for those same source actions.
Labels describe the action shown in the controls list, independently of the
historical engine input it receives. Duplicate source declarations are errors.

```ini
[controls]
attack = attack4
special = attack3
attack3 = special
attack4 = none

[labels]
attack = Attack
special = Dodge
attack3 = HUD
```

An external descriptor takes precedence over the ZIP descriptor for each
explicit control or label; unspecified entries can come from the ZIP descriptor.
Directions and Start retain their defaults unless explicitly mapped.

## Named input preparation

`transform = adjustment` in a descriptor's `[overrides]` section selects the
`adjustment` entry of `[transforms]` in the system directory's `AnyBOR.ini`.
The byte-buffer language, limits and cache validation are described in
[content transforms](CONTENT_TRANSFORMS.md). A descriptor without this field
retains the INI's `input` default. The selected named entry must exist and all
functions must validate; an unavailable entry rejects the load.

The external descriptor's transform wins over a ZIP descriptor's transform.
Functions remain external to the core and descriptors contain only their names.
Named transforms require an ordinary PACK input; structural header repair keeps
its existing route for descriptors without a named transform. Engine selection
retains its independent manual and INI priorities.
