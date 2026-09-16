# Configured content transforms

AnyBOR can adapt a packed input using a byte-buffer function supplied by the user.
Typical uses are extracting an archive after a custom header, selecting its byte
range inside a larger container, and converting stored word order. The function
receives bytes and returns the complete ordinary PACK that the engine will read.
Use these adapters with content you created or have permission to adapt.

## System configuration

Place `AnyBOR.ini` in the system directory configured by the frontend. Libretro
supplies it through `RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY`. On a case-sensitive
filesystem the spelling is exact. Neither the content directory nor the process
working directory supplies a fallback. The core does not install or generate this
file. An absent file selects no transforms; an unreadable or malformed existing
file rejects packed-content loading.

```ini
[transforms]
input = buffer identity() {
    return slice(0, input_size);
}
```

Only the entry whose INI key is `input` runs, once before the PACK reader. The
function name after `buffer` is descriptive and does not select it. Other declared
functions are validated but not dispatched. Each load follows this sequence:

1. Extract the selected member when the loaded content is an ordinary ZIP.
2. Apply the explicitly configured `input` function to the packed file, if present.
3. Validate the complete resulting PACK before starting the engine.

An adapter can leave a representation unchanged with `return slice(0, input_size)`.
A rejected operation or invalid result fails the load. An unchanged PACK retains
ordinary structural index recovery when applicable. Unpacked mods do not use this
interface. It has no pipelines, per-record hooks, native plugins, external commands,
filesystem operations or network operations. In particular, a function cannot
return a ZIP for another extraction pass or normalize individual script records.

This example removes a four-byte `DEMO` prefix from an archive you authored:

```ini
[transforms]
input = buffer unwrap_authored_container() {
    if (input_size >= 4 && read32(input, 0) == 0x4f4d4544) {
        return slice(4, input_size - 4);
    }
    return slice(0, input_size);
}
```

Prepend those four ASCII bytes to a PACK containing your own material. Loading
that wrapper with this declaration yields the original PACK. Other inputs pass
through unchanged.

## Ready-to-use examples

[`examples/input_transforms.ini`](../examples/input_transforms.ini) contains four
standalone functions. Copy it to the frontend system directory as `AnyBOR.ini`
and rename exactly one entry key to `input`. For example, change
`header_payload = buffer remove_sized_header()` to
`input = buffer remove_sized_header()`. Keep the function body and braces.
The file as supplied selects nothing; there is no `input` key.

| Entry to select | Input representation | Result |
|---|---|---|
| `copy_payload` | An ordinary PACK | The same bytes, without a cache copy |
| `header_payload` | A custom header whose first little-endian u32 is its total size, followed by a PACK | The bytes after the complete header |
| `range_payload` | Two little-endian u32 values giving an absolute byte offset and byte length, followed by caller-defined data | Exactly the indicated PACK, leaving surrounding data out |
| `little_endian_words` | An archive stored with each complete four-byte word reversed; any final one to three bytes stay in their original order | The original archive byte order |

Header sizes must be at least four bytes and fit inside the input. Range offsets
must follow the eight-byte directory and the complete nonempty range must fit.
Both adapters reject invalid bounds; the PACK validator checks the extracted data.
The word-order adapter reverses every complete word and leaves a partial final
word unchanged. It does not interpret individual archive fields.

These representations are examples for your own packaging tools. Selection applies to every packed
input loaded with that configuration. Choose the function for the representation
you are using; these three adapters do not automatically recognize other layouts.
Remove the `input` declaration to resume ordinary PACK loading.

To generate complete sample inputs from AnyBOR's original diagnostic content:

```sh
python3 tools/make_fixture.py --output .build/fixtures/diagnostic.pak
python3 - <<'PY'
from pathlib import Path
import struct

root = Path('.build/fixtures')
pak = (root / 'diagnostic.pak').read_bytes()
header = struct.pack('<I', 12) + b'EXAMPLE!'
(root / 'header.pak').write_bytes(header + pak)
prefix, trailer = b'example metadata', b'example trailer'
directory = struct.pack('<II', 8 + len(prefix), len(pak))
(root / 'range.pak').write_bytes(directory + prefix + pak + trailer)
words = bytearray(pak)
for offset in range(0, len(pak) - 3, 4):
    words[offset:offset + 4] = pak[offset:offset + 4][::-1]
(root / 'words.pak').write_bytes(words)
PY
```

Load `header.pak`, `range.pak` or `words.pak` with the corresponding example
selected. Each produces the same diagnostic game as `diagnostic.pak`. The `.pak`
suffix lets the frontend pass the example to the core; it does not determine the
container layout or make an invalid result acceptable.

## Buffer language

Each entry is a multiline `buffer name() { ... }` function. Statements include
initialized `uint64_t` variables, assignments, `if`/`else`, `while`, `for`, `break`,
`continue`, `reject()` and `return slice(offset, length)`. Arithmetic uses unsigned
64-bit wrapping integers with C operator precedence; logical operators short-circuit.
Decimal/hexadecimal integers and character literals are supported, without C type
suffixes. There are no pointers, native function calls or recursion.

`input` is read-only. `work` starts as a private copy of it. `scratch` provides
64 KiB initialized to zero. Optional first-statement `parameters("ABC");` supplies
read-only parameter bytes. `input_size`, `parameter_size` and `metadata_size` are
read-only builtin variables; this consumer supplies no metadata.

`read8`, `read32`, `read64` and matching `write` operations use a buffer and an
offset; writes take a third value argument. Multibyte values are little-endian.
Only work and scratch are writable. `slice` returns part of work;
`scratch_slice` returns part of scratch. Every access and returned slice is
bounds checked. Invalid shifts, division by zero, falling through a function or
exhausting the instruction budget reject without producing a result.

Configuration is limited to 512 KiB and 16 named functions. One source function
is at most 64 KiB, compiled instructions at most 12 KiB, parameters at most 4 KiB,
and input at most 1 GiB. Execution allows at most `1,000,000 + 128 * input_size`
instructions; that is a resource bound, not a promise of short loading time.
Work cannot grow beyond the input size. Peak memory includes input, work and
scratch. The compiler uses no external C compiler at content-load time.

Names are case-sensitive lowercase ASCII letters, digits, dots, underscores and
hyphens, up to 63 bytes. Duplicate names or transform sections reject. Outside a
function, whole-line `;` and `#` comments are allowed; inside, use `//` or `/* */`.
The closing brace ends its declaration line. UTF-8 BOM, LF, CRLF and CR are
accepted. Section-shaped text within a function comment remains part of it.

## Validation, caching and ownership

The original file remains unchanged. Preparation runs at each load and the normal
PACK validator checks its complete result before engine boot. The cache identity
includes the original SHA-256, compiled function and parameter identity, and result
SHA-256. Preparation runs again when loading: a previously cached result cannot
replace the currently selected operation or its validation. Without an `input`
function, the original file follows ordinary PACK loading and structural checks.
An invalid result fails before engine boot and returns control to the frontend.

If a function returns byte-identical input, loading keeps the original path and
does not create a cache copy. Structural index recovery still applies when
needed. This avoids unnecessary disk traffic for ordinary archives that the
configured function leaves unchanged.

A completed result is published atomically below
`<save>/AnyBOR-cache/input-<8-hex>/<original-name>.pak`. The directory uses the
first eight hexadecimal characters of the source/configuration/result identity
to keep paths short. A cached result is reused only when its complete SHA-256
matches the newly prepared bytes; a short-prefix collision replaces the cached
file with the correct result. Failed operations remove their temporary output
and publish no partial result. Programs are freed before engine boot; they are
not serialized with gameplay state.

## Implementation

The compiler and byte-buffer VM are original AnyBOR components. They provide
generic compilation and bounded byte-buffer execution only.
