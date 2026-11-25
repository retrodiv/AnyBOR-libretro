# Content descriptors and engine overrides

A manual engine choice in the core options takes priority over external engine
settings. With automatic selection enabled, the order is:

1. A matching `imohash:zip:<digest>` engine rule in the system directory's `AnyBOR.ini`.
2. A matching `imohash:pak:<digest>` engine rule in that INI.
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
engine for an original PAK or complete ZIP identified by its standard imohash.
The selector includes the file kind.

```ini
[imohash:pak:0123456789abcdef0123456789abcdef.overrides]
engine = v3.0 6330

[imohash:zip:fedcba9876543210fedcba9876543210.overrides]
engine = v3.0 6391
```

Obtain the selector with the supplied utility (Python standard library only):

```sh
python3 tools/content_key.py /path/to/content.pak
python3 tools/content_key.py /path/to/content.zip
```

The utility emits `imohash:pak:<digest>` for `.pak` or `.spk` and
`imohash:zip:<digest>` for `.zip`, with case-insensitive extension matching.
Replace each example selector with its output.

A rule with `imohash:pak:<digest>` identifies the original PAK before any content
preparation. A selected PAK inside a ZIP uses the same identity as its loose copy; the ZIP's name, compression and auxiliary files are not part of this
selector. These rules do not choose between multiple PAKs inside a ZIP: use a
descriptor to select the payload first. Unpacked games have no PAK identity.

A rule with `imohash:zip:<digest>` identifies the complete original ZIP, including its
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

## Scoped presentation directives

`[overrides]` accepts presentation directives for the current game.
**Content Override Directives** controls these directives during play and is on
by default. `?gameres` selects AnyBOR's native game-raster path. `?crt` requires
**Adjust for 4:3 CRT TV**. The effective CRT orientation combines
**OS Screen Orientation** with **Image Rotation**. Use `?crt=horizontal`
or `?crt=vertical` to scope `windowraster` or `drawhold` to one orientation.

```ini
?crt=horizontal windowraster|320|240
?crt=vertical windowraster|240|320
?gameres ?global.enable_hud drawhold|hud_scale|1
?crt $crt_layout=1
```

`windowraster|width|height` fits the engine picture into the specified raster
before CRT fitting and rotation. Width accepts 1–3840 and height accepts
1–2160. The content's own framebuffer and geometry remain available when
the scope closes. A later matching window declaration takes priority.

`drawhold|name|value` temporarily substitutes a numeric script global while
drawing scripts run. `$name=value` holds an existing numeric global while
the scope is active and restores its previous value when the scope closes.
The optional `?global.name` condition requires a nonzero numeric global.
Values can combine finite decimal numbers and existing numeric script globals
using `$global.name`, arithmetic and parentheses. An unavailable global or a
non-finite result skips that evaluation. Each directive in a semicolon chain
carries its own scope. A loaded descriptor set supports up to 64 numeric directives.

`@window_w` and `@window_h` select individual raster extents in the absence
of a matching `windowraster` directive. `@present_crop_left`,
`@present_crop_top`, `@present_crop_right` and `@present_crop_bottom`
remove whole-pixel margins before CRT fitting. A negative margin or an
empty result disables the crop. `@present_shift_x` and `@present_shift_y`
move the composed frame before rotation and fill the exposed edges with
black. Crop and shift affect the delivered picture and preserve the saved
engine raster.

## Declared CRT mode

A descriptor can request a CRT canvas and refresh in its `[overrides]` section.

```ini
[anybor]
payload = Paks/content.pak

[overrides]
?crt crtmode|256|192|60
```

The directive applies while **Adjust for 4:3 CRT TV** is on. Numeric width is
16 to 640, height 16 to 480, and refresh 2 to 300 Hz. The numbers are integers.
The core centres the native image at its original pixel size in the declared
canvas before applying **Image Rotation**. If the image exceeds a fixed
dimension, normal CRT sizing applies at the declared refresh.

```ini
?crt crtmode|window_w|window_h|60
?crt crtmode|256|192|window_fps
```

Each example is a separate declaration. `window_w` and `window_h` follow the
current game raster before CRT fitting and rotation. Automatic CRT timing
and `window_fps` follow AnyBOR's normal 60 Hz output or the active level's
declared cadence. For a slower level, the core requests an integer
multiple of the cadence between 50 and 60 Hz when one is available.
A fixed refresh changes presentation cadence. The core keeps the same
game clock and audio sample rate. The frontend can
decline the requested refresh and controls physical display timings.

A later `crtmode` declaration takes priority. An external descriptor for a ZIP
can override the declaration in the ZIP's own descriptor.

```ini
?crt roomspeed|0,2-4|50
```

`roomspeed|levels|rate` sets the simulation ticks per second for the listed
playable levels in the current set. Indices follow the set's entry order
from zero, counting selection and scene entries. Use commas and inclusive
ranges. The rate is an integer from 1 through 300. The directive
applies to gameplay in those levels, and the native cadence applies again
when the scope closes. Later declarations replace the rate for each
overlapping level. `roomspeed` and `crtmode` use the plain `?crt` scope.

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
Functions are supplied by the user through a descriptor or system configuration.
Named transforms prepare an ordinary PACK input or the files of a loose game
resolved from a ZIP. Structural header repair keeps its existing route for
descriptors without a named transform. Engine selection
retains its independent manual and INI priorities.

## Descriptor-local functions

A descriptor can contain its complete byte-buffer adjustment in `[overrides]`:

```ini
[anybor]
payload = Paks/content.pak

[overrides]
transform = buffer unchanged() {
    return slice(0, input_size);
}
```

This function uses the grammar and execution limits in
[content transforms](CONTENT_TRANSFORMS.md), within the descriptor's 64 KiB
file limit. For packed content, local functions adjust an ordinary, structurally
valid PACK input; other packed representations are rejected before execution.
For a ZIP resolving to a loose game, the function runs separately on each file.
`input_size` describes that file, and the read-only `metadata` buffer contains
its normalized lowercase relative path, without a terminating NUL (at most
256 bytes). `metadata_size` gives its length. A function can select its own
files by inspecting this metadata and return other files unchanged.
It requires no `AnyBOR.ini`. The compiler parses the entire function;
section-shaped text in its strings or comments remains function text. Only one
`transform` field is accepted. A named INI entry and a local function cannot be
combined in one descriptor.

A local function takes precedence over the INI's default `input` transform.
The external descriptor's transform, either local or named, takes precedence
over a transform in the ZIP's descriptor. Engine-choice priorities remain
independent. Prepared output is keyed by the sampled input identity, compiled
function and parameters, and core version. For loose games, the key uses the
ZIP's size and imohash and the game's root within it. The separate prepared
tree is reused when its marker lists the exact output files and their sizes
and imohashes match the tree on disk. Missing or extra files trigger a rebuild.
The ZIP extraction retains its own validation. Both cache-clearing core options
default to **On**. Set both to **Off** to retain prepared output between loads.
See [content transforms](CONTENT_TRANSFORMS.md) for the sampling rules.
