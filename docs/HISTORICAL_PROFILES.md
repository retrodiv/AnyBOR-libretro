# Choosing a profile

Selectable engine profiles: v3.0 3020-dev, v3.0 3057, v3.0 3062, v3.0 3073,
v3.0 3081, v3.0 3109, v3.0 3117, v3.0 3143, v3.0 3160, v3.0 3173, v3.0 3192,
v3.0 3208, v3.0 3273, v3.0 3288, v3.0 3303, v3.0 3307, v3.0 3310, v3.0 3311,
v3.0 3316, v3.0 3317, v3.0 3318, v3.0 3327, v3.0 3328, v3.0 3330, v3.0 3332,
v3.0 3335, v3.0 3337, v3.0 3340, v3.0 3341, v3.0 3342, v3.0 3350, v3.0 3351,
v3.0 3352, v3.0 3353, v3.0 3354, v3.0 3355, v3.0 3356, v3.0 3357, v3.0 3360,
v3.0 3361, v3.0 3362, v3.0 3365, v3.0 3366, v3.0 3367, v3.0 3371, v3.0 3372,
v3.0 3373, v3.0 3375, v3.0 3379, v3.0 3380, v3.0 3381, v3.0 3383, v3.0 3385,
v3.0 3388, v3.0 3391, v3.0 3394, v3.0 3397, v3.0 3400, v3.0 3666, v3.0 3667,
v3.0 3669, v3.0 3670, v3.0 3671, v3.0 3672, v3.0 3673, v3.0 3674, v3.0 3675,
v3.0 3677, v3.0 3678, v3.0 3679, v3.0 3680, v3.0 3682, v3.0 3685, v3.0 3686,
v3.0 3689, v3.0 3690, v3.0 3691, v3.0 3692, v3.0 3693, v3.0 3694, v3.0 3697,
v3.0 3699, v3.0 3701, v3.0 3703, v3.0 3704, v3.0 3707, v3.0 3708, v3.0 3709,
v3.0 3710, v3.0 3711, v3.0 3713, v3.0 3714, v3.0 3715, v3.0 3716, v3.0 3722,
v3.0 3725, v3.0 3726, v3.0 3727, v3.0 3728, v3.0 3729, v3.0 3730, v3.0 3732,
v3.0 3738, v3.0 3740, v3.0 3741, v3.0 3742-dev, v3.0 3761-dev, v3.0 3769, v3.0
3773, v3.0 3780, v3.0 3783, v3.0 3789, v3.0 3793, v3.0 3797, v3.0 3805, v3.0
3814, v3.0 3818, v3.0 3822, v3.0 3824, v3.0 3829, v3.0 3831, v3.0 3837, v3.0
3839, v3.0 3842, v3.0 4086, v3.0 4088-dev, v3.0 4107, v3.0 4111, v3.0 4129,
v3.0 4153, v3.0 4432, v3.0 4453, v3.0 6330, v3.0 6391, v3.0 6391-mod, v3.0
6392-dev, v3.0 6412-dev, v3.0 6510-dev, v3.0 7086-dev, v3.0 7123-dev, v4.0
7142-alpha, v4.0 7533 and v4.0 8023-dev.

Auto uses build tags and content clues to choose a profile. You can select one
manually when a game needs it. Historical profiles preserve selected earlier
content behavior while retaining safety and lifecycle corrections.

The 3741 source tree reads GIF headers and image descriptors as 13 and 9 bytes.
Persisted configuration, progress and score records have their own explicit
packing scope. GIF header packing does not change those record declarations;
native ABI checks do not establish cross-platform save-file compatibility.

The 3400 source tree uses explicit 32-bit script-save records: a four-byte
counter, a 24-byte variable name and fixed variant fields. Linux x86-64 and
macOS use 12-byte variants and 40-byte named records; Windows, Linux ARM64,
Linux RISC-V and Android use 16-byte variants and 48-byte named records.
String values retain their cache-index semantics. Non-null object references
resolve within live allocations in the current engine arena; unavailable
references are rejected. These records do not establish portable object or
string identities between sessions. Partial reads retain unaffected fields,
and indexed writes retain the original offset within each profile's capacity.

Profiles before 3667 initialize each level set with two players and apply
`single`/`maxplayers` only within a set. From 3667, those commands also define
the defaults before the first set. Regular input refresh covers the selected
set before 3668 and all player ports from that boundary, within the player
table limits.

Buffered reads from 3777 prefer an external file before the cached archive
reader. Earlier profiles use the selected archive reader directly; its uncached
mode retains external-file overrides. Active-content aliases retain their
existing handling.

Model-copy script loading and callbacks are available from 3793. Earlier
profiles retain unknown-command diagnostics for that declaration. Callback
self/old locals clear after execution. Creation-entry caches retain the native
lookup and failed-compilation reset rules; no creation callback runs before
3762.

Video settings preserve the selected profile's numeric-prefix conversion.
Custom dimensions and numeric mode 255 are available from 3784; custom-mode
debug text retains its prior offset in 3784 and derives it from the height
from 3785. Player spawn Z clamps to 232 outside 0–232 before 3800.

Menu key names accept escape from 3777; the twelve other names retain their
indices. Unknown menu commands warn before 3766, except for the ignored font
options; profiles from 3766 ignore unknown commands.

Selection icons with colourmap zero use their sprite palette before 3673
and the model palette from that boundary. Valid nonzero indices select the
corresponding model map.

Duplicate-player checks use a case-sensitive name prefix before 3831 and
full case-insensitive equality from that boundary. The final-player countdown
applies the original joining-state predicate from 3820; its earlier rule
depends on available credits.

Profiles before 3791 retain unsigned spawn scores and model AI flags, while
negative signed score multipliers clamp to zero. From 3791, the `-1` sentinel
controls score/multiplier clamping and model AI inheritance.

Profiles before 3828 read animation limits from the selected model list after
global scripts are compiled, then construct animation vectors before loading
the models. Profiles from 3828 read those limits from the standard model list
before global scripts. Vector reconstruction during model reload follows the
same source boundary; script and model availability checks remain bounded.

Animation callbacks before 3813 clear their four context locals after the
model scripts run. Profiles from 3813 preserve an initialized local context
when its interpreter is resetting and restore the current model's script
binding when available. Real uninitialized script owners reject writes before
3814; internal context labels retain safe handling. From 3815, a successful
insertion that fills the variable table collects retired entries. A refused
insertion does not collect them.

The `nonestedscript` setting is available from 3806 and `nocmdcompatible` from
3823. Earlier profiles leave those flags unchanged when reading the settings.

Sprite cleanup follows the owning list independently of the original counter
width or the number of shared map entries. Each owner releases its sprite and
filename once; map entries borrow those resources. Native release order, count
reset and retained map capacity are preserved in every profile.

Sprite-map growth preserves each source's capacity policy and existing entries.
Failed growth retains the previous storage and capacity; allocation extents are
checked before an allocation is requested.

Sprite loading preserves native filename lookup and center-dependent sharing.
The direct-map source creates an additional alias at the first filename match
when its center differs; node-cache sources can reuse a later matching entry.
The image format is not part of the native filename cache key. A reload must
be available before its metadata is read, and an incomplete new node releases
only its own partial resources. Cache requests for absent nodes are inert.

Rendering in profiles before 3741 reads a selected positive colourmap entry
directly, including an empty entry, independently of the loaded-map count.
The fixed-table profiles before 3739 retain their fixed extent. Profiles from
3741 use their native loaded-count palette fallback. Missing models, missing
tables and unavailable extents have bounded, defined results.

Script streams in profiles before 3739 use 50 slots and release their buffers
with the level. Closing a slot retains its native position and size fields.
Profiles from 3739 grow the slot table and retain streams across level changes;
script shutdown releases them. Owned buffer extents are tracked independently
of those native fields so argument and position checks preserve initialized
data after embedded zero bytes.
Stream loading uses aligned local output parameters before updating the native
record, preserving its field offsets, loaded bytes and callback result.

Native global-script cleanup omits the loading script's `clear` callback before
3727 and invokes it from 3727. Earlier profiles retain that script until the
engine's arena is released.

Projected shadows retain the default drawing palette before 3716. From 3716,
the shadow and its reflection use the entity's drawing palette.

Remap errors stop model loading before 3787. Profiles from 3787 report a warning
and continue; successful loads update palette flags.

## Select a profile

Manual selection overrides Auto when the metadata is missing or incorrect:

1. Find the engine build specified by the content's author or original release.
2. Open **Engine build** in the core-options list, under **System** when
   categories are available.
3. Select the full value, such as **v3.0 3780**, and use **Restart** or reload
   the content. The frontend log reports the selected profile.
4. Keep that profile for the session. States require the same logical profile,
   core build and content; switching profiles does not convert existing states.

If the required revision is unknown, start with Auto and consult the content
release documentation before choosing manually.

## Selected contracts and shared behavior

Historical scaling filters are omitted. Display-mode requests containing a
filter selection use the unfiltered image; the selection does not change the
output dimensions or pixel conversion. This is a limit of visual fidelity.

| Boundary | Selected earlier contract |
|---|---|
| 3670 | Line parsing accepts 18 arguments earlier and 64 from this revision. |
| 3685 | Default attack-depth tolerance adds one to a third of grab distance from this revision. |
| 3729 | Authored collision bounds gain an upper depth coordinate. Frame conversion, hit centers and flash positions follow the native range calculation. |
| 3762 | Copy and compile leave creation functions uncalled before this revision; later profiles dispatch them with native local arguments. |
| 3767 | Callback entries use `clear` and `init` earlier, and `ondestroy` and `oncreate` from this revision. Creation dispatch requires 3762 or later. |
| 3792 | WAV reads use the earlier sample-count extent and zero 16-bit padding before this revision; later profiles use byte extents and native 0x80 padding. |
| 3797 | Player-property names/numeric selectors, integer/void setter result and rejected numeric values; AI-flag names/selectors, earlier read-only nested timers and deprecated walking result. |
| 3798 | Introduction of the player keys setter. |
| 3800 | Earlier player spawn Z limit of 0..232. |
| 3802 | Earlier user-defined preprocessor names, conditional handling and function-macro parsing. |
| 3808 | Compilation preserves the interpreter's reset flag earlier and clears it from this revision. |
| 3820 | Earlier level-property selectors and nonfatal rejected setter values. |
| 3821 | Earlier text setters retain their numeric result, tolerate negative indices and preserve rejected numeric fields. |
| 3822 | Line capacity and the script constant `MAX_ARG_LEN` are 512 earlier and 511 from this revision. |
| 3826 | Unknown textual constants return an empty value before this revision; later profiles reject them. |
| 3805 | Ordered level spawn scripts with shared cached per-file locals before this revision; combined per-entry scripts afterwards. |
| 3821 | Player weapon-number spelling and introduction of its setter. |

Under the integer result contract, `changetextobjproperty` leaves a rejected
numeric field and any existing integer result intact. `cleartextobj` retains
that integer when clearing a valid object and returns zero for an out-of-range
index. `settextobj` updates accepted scalar fields before validating its string
and keeps the current expiry when time is omitted. Under the void result
contract, supplied numeric fields are validated before record updates and an
omitted timeout has the defined value zero.

The 3741 source tree provides 50 zeroed text-object slots for profiles below
3739 and dynamic slots from 3739. Fixed tables return their profile's
out-of-range result for indices outside 0..49 without growing. If dynamic
growth cannot reserve storage, the table and its existing objects remain intact.

Complete script variable names are supported in every engine. Names are never
truncated to imitate unsafe fixed-size storage. Native and compiled-script
regressions cover these selected contracts, including state restoration of
complete global and local names.

Every reviewed contract-bearing revision is recorded below. Conditional rows
select earlier observable behavior; shared rows retain additive syntax or safety
corrections. An earlier profile never requests unsafe memory behavior.

| Revision | Policy | Scope |
|---|---|---|
|3681|conditional|Earlier model attacks, smartbombs and environment damage retain fixed drop velocities; later profiles use configured defaults. Explosive attacks retain the native fixed value or scaled default, while smartbombs preserve the template's third component.|
|3722|conditional|Earlier difficulty menus show at most the first two five-entry pages; later profiles page through the selected entry.|
|3762|conditional|Automatic creation callbacks run after copying or compiling, with source-defined local arguments and restoration of the current script. Earlier profiles do not dispatch a creation callback.|
|3767|conditional|Destruction/creation callback names are `clear`/`init` earlier and `ondestroy`/`oncreate` from this revision; these spellings are not aliases.|
|3773|conditional|The Back entry retains the final difficulty page from this boundary. A difficulty locked behind one completion uses the native earlier or later row position.|
|3776|conditional|Earlier profiles pass each HUD icon owner's color map and ignore the extra icon-command flag. Profiles from this boundary honor that flag for player, weapon, MP, opponent and joining-model icons.|
|3779|conditional|Earlier imports retain exact paths and release modules with their last importing script; calls resolve local or native functions. Later profiles normalize ASCII case and separators, retain modules until script-system cleanup, and search exported functions in reverse import order after local functions.|
|3783|conditional|Earlier shared scroll axes, zero-as-unspecified bounds and numeric system-property ordering; later independent bounds. Exact endpoint and reverse speed-limit progress follow the native earlier or later rules. Camera bounds remain checked.|
|3784|conditional|Direct video dimensions and mode 255 follow their native availability. Earlier profiles retain numeric-mode parsing and errors. Camera blockades apply after speed limiting earlier and before it from this revision; clipping and camera bounds remain checked.|
|3785|conditional|The debug text offset for direct video dimensions follows the native height calculation at this revision and later.|
|3786|conditional|Individual x/z/a entity setters follow their native availability and result values. The position setter retains independent coordinate updates.|
|3787|conditional|The spawn-to-respawn animation fallback follows its introduction. Missing color maps remain safe rather than restoring an abort.|
|3789|not applicable|Standalone touch-screen docking is replaced by the frontend interface.|
|3792|conditional|WAV read extents, sample lengths and 16-bit padding follow the native byte/sample contract. Allocation and read counts remain checked; resident-byte registration covers the bytes actually loaded.|
|3793|conditional|Weapon-model update order and model-copy callback registration follow this revision; snapshots and ownership remain initialized.|
|3797|conditional|Player-property and AI-flag names, numeric selectors, result values and rejected-value handling follow the selected contract.|
|3798|conditional|The player keys setter follows its introduction. Guard-point and memory/lifecycle corrections remain shared.|
|3800|conditional|Player spawn Z uses the earlier 0..232 limit before this revision.|
|3801|conditional|Holdblock bit 2 and AI orbit sign/parity handling follow this boundary.|
|3802|conditional|Earlier profiles treat builtin-like names as user macros, reject `#if`/`#elif`, and retain their top-of-stack conditional decisions, token lookahead and macro argument splitting. Lexical errors and excess conditional depth have bounded, defined rejection.|
|3803|shared|Retain corrected lexer token handoff and preprocessing bounds; defined is already reserved by the selected 3802 boundary.|
|3805|conditional|Earlier ordered spawn scripts retain shared per-file locals and the spawnscript scope. Inline level scripts and combined per-entry scripts are available from this revision.|
|3806|conditional|The explicit nested-script suppression flag applies from this revision; script ownership remains safe.|
|3808|conditional|Successful compilation clears the interpreter reset flag from this revision and preserves the earlier flag beforehand.|
|3810|conditional|Integer switch/case syntax is available from this revision. Its keywords remain reserved in earlier profiles. Earlier diagnostics retain numeric production identifiers; invalid control targets receive a defined refusal.|
|3812|conditional|String case labels are accepted from this revision; earlier switch syntax accepts integer labels.|
|3813|conditional|Animation-command grouping, early return and nested-interpreter snapshots follow 3813, 3823 and 3836 boundaries.|
|3816|conditional|Conditional expressions are available from this revision. First/Follow sets match the selected grammar.|
|3818|conditional|Assignment expressions yield the earlier loaded value before this revision and reload the assigned value from this revision.|
|3819|conditional|Raw versus format-aware shadowcolor conversion, idle entry order and sleep timing follow this boundary.|
|3820|conditional|Level selector numbering, successful results and nonfatal rejection preserve the earlier contract. The level getter uses the drawmethod runtime mapper earlier and the level mapper from this boundary; compiler literals use the level mapper in both. Completed-game bonuses are recalculated by successful character/difficulty menu loads earlier and by the saved-game loader from this boundary; other callers retain their native side effects.|
|3821|conditional|The level setter changes from the drawmethod runtime mapper to the level mapper. Unconverted property strings preserve their native cache-index dispatch. Text numeric/string conversion, result values, partial field updates and weapon-number spelling follow this boundary. Text ownership remains bounded.|
|3822|conditional|Native saves begin recording selectable/model state here; eager cached-model loading ends at 3835. Saved-game restores reset player-model selection before this boundary and retain saved model selection from it. Model-cache getters and setters resolve names from this boundary. Earlier profiles retain numeric-member selection and their native diagnostic, with bounded cache indices.|
|3823|conditional|Animation commands use the original default grouping and early-return policy, with nocmdcompatible controlling the later contract.|
|3824|conditional|The idle/sleep timer guard and finished-animation behavior follow this boundary.|
|3825|conditional|Sleep activation changes from an inclusive to a strict deadline.|
|3826|conditional|Earlier profiles retain fixed numbered animation constants and resolve other animation suffixes at runtime, using their original offsets and clamps within table bounds. From this boundary, configured suffixes resolve in the constant mapper. Unknown textual constants return empty earlier and are rejected later.|
|3828|conditional|Entity getters and setters use their separate subproperty mappings and diagnostics before this boundary, for compiler literals and runtime calls. Earlier unsupported unary operands clear to empty; supported numeric values follow the earlier contract without unsafe signed overflow. The compiler mapping pass limits native calls to 32 arguments from this revision; earlier profiles retain their dynamic argument lists. Other selector sub-enum orders are unchanged.|
|3830|conditional|Attack-table size, environmental damage typing/health and Defense ALL are selected together, retaining bounded storage.|
|3831|conditional|Attack extension offsets, exported environmental constants, default animation slots and Offense ALL follow this revision. Earlier profiles refresh literal values before runtime unary operations and print their own opcode numbers on execution failure. Unary constant folding and expression-statement instruction removal follow the selected parser contract.|
|3833|conditional|Shift expressions are available from this revision, with their native precedence.|
|3834|conditional|exit function registration and completed holdblock animation behavior follow this boundary. Earlier calls clear their completion flag; calls from this revision derive it from the reset state.|
|3835|conditional|Native saved model records stop eagerly loading cached models here.|
|3836|conditional|Nested interpreter snapshots and bReset behavior follow the original nocmdcompatible contract; ownership remains valid.|
|3837|conditional|Earlier arithmetic-mean camera framing, integer truncation and branch-specific offsets; later extreme-player framing and span limits.|
|3838|conditional|Sample caching uses 1,024 reusable slots before this boundary, releasing names with their audio. Later profiles retain named identifiers and reload audio on demand or during model-cache operations. Playback identifiers, playsample result type, negative sample handling and system-property numbering follow this boundary; channel bounds remain checked.|
|3839|conditional|Bitwise AND, XOR and OR expressions are available from this revision, with their native precedence.|
|3841|conditional|Animation-name lookup preserves native aliases, ranges, implicit synchronization, bounce, attack-one and energy defaults. Explicit sync is recognized from this revision; earlier profiles use their unknown-command route.|
|3842|conditional|Model clips use absolute screen coordinates earlier; later profiles subtract frame offsets and add the projected entity position. Coordinate arithmetic and sprite bounds remain safe. Font atlas storage preserves earlier glyph widths, palettes and raster output, checked against each profile's own source. Font palettes must fit their owning allocation before use. Sprite sizing uses defined byte counts; empty viewport intersections return without raster access.|

A failure that disappears in the original declared engine remains a compatibility
issue to investigate, even when it also occurs with another profile. Selecting
an earlier profile does not promise exact emulation of an original executable.


## Early profile contracts

The early family uses the 4086 physical source with contracts taken from each
profile's own upstream revision. The unofficial development snapshot is
exact-tag/manual only. Official automatic profiles cover declared revisions
through 4153. Source commits and dates are recorded in [src/pin.json](../src/pin.json).

| Boundary | Native behavior |
|---|---|
| 4094 | True-color static PNG backgrounds can use the 32-bit background path. Earlier profiles retain their indexed-background requirement. |
| 4095 | The engine-credit-screen system variable is present. String names and numeric system-variable IDs follow each profile's native namespace. |
| 4096 | Level alpha masks apply to one sprite layer. Missing mask images retain the original accepted result; unsafe missing base images fail cleanly. |
| 4100 | The optional shutdown message uses the second argument; earlier profiles preserve their defined first-argument cache selection. Invalid cache indices and formats requiring absent variadic arguments fail safely. |
| 4101 | Attack staydown reads return an integer; earlier profiles retain the native pointer result type for defined values. |
| 4134 | Positive playback frequencies are unrestricted by the earlier three-rate whitelist. |
| 4137 | The scene `video` command uses the native WebM decoder. Earlier profiles ignore that scene command. |
| 4141 | Sound-menu completion clears its own active flag; configuration-menu completion retains its native flag behavior. |
| 4146 | Controller assignment consumes the pending key through the platform input adapter. |

The six-integer hitbox layout retains the native field order, frame conversion,
storage and collision results. Temporary parser expressions, resolved import
nodes, Ogg buffers and layer masks have bounded ownership. PNG member reads and
row sizes are checked independently of palette-only routing. Sprite validation
remains strict for every profile. Native tests compare each profile with
independent observations from its own original source; they do not establish
complete executable equivalence.

## Reconstructed variants

**v3.0 6391-mod** reconstructs the experimental build by Kratus described in
the [published discussion](https://www.chronocrash.com/forum/threads/npc-walking-backwards-how-to-solve-it.6933/).
It is based on published descriptions and official code; the unpublished build's
sources were unavailable and were not used. Its contract retains four incoming
attack IDs, enables the multihit correction by default and provides its native
cheat-menu toggle. `gotomainmenu(9)` exits character selection. Its script API
has no `backtotitle` alias. Airborne collisions reject attacks whose juggle cost
exceeds the target's current juggle points, as in the official 6391 source.
Standalone platform controls and menus use frontend facilities; container
validation remains strict. This is a reconstruction, with no claim of complete
binary equivalence or endorsement by the experimental build's author.

A manual choice or an explicit filename variant selects this profile:
**Build 6391 Mod**, **Build 6391-mod** and **Build 6391_MOD** are equivalent.
**Build 63XX Mod** selects it within that interval. A bare **Build 6391** tag,
ordinary content evidence and accompanying executables retain numeric routing.
Settings, logs and state identity use the separate `6391-mod` profile key.
See [provenance](../PROVENANCE.md) for the official source commits.

**v3.0 6392-dev** reconstructs behavior published by the test-build author,
using the subsequent upstream source changes. Exact sources of that test build
were not recovered; complete binary equivalence is not claimed. The selected
contract keeps four incoming attack IDs, enables the multihit correction by
default and offers its original cheat-menu toggle. Selection-screen title
requests accept `gotomainmenu(9)` and the earlier `backtotitle(flag)` alias.
Standalone controller and mod-menu changes are replaced by frontend facilities.
See [provenance](../PROVENANCE.md) for the published behavioral and source basis.

An exact filename **Build 6392** tag or a manual choice selects this test
revision directly. Imprecise tags are checked against content evidence, with
stable or automatic profiles preferred. Ordinary unlabelled inference and
accompanying executables do not select nonautomatic profiles.
See [content selection rules](AUTO_SELECTION_RULES.md) for boundaries and limits.

## Divergent test profiles

**v3.0 7086-dev** follows revision
`7a45a2215a0cc12c1085d92e7b210a827ea552c2`; **v3.0 7123-dev** follows
`f5261e7cb97786909276c0b87f8f9f63504d2844`. These development branches retain
earlier animation-property selectors, optional model records, follow/counter
decisions, energy rules and attack/binding IDs. The latter profile also selects
its incoming-attack history and cheat toggle, selection priority, return-to-title
flag and drawing order. Memory and lifecycle corrections remain enabled.

Later additive APIs and command names remain accepted without renumbering
selectors or changing the meaning of content valid for the selected revision.
Standalone device drivers and mod pickers are replaced by frontend facilities;
in-game menus and script-visible timing remain covered by native regressions.

Exact **Build 7086** and **Build 7123** filename tags select these profiles.
Manual selection is available. Ordinary accompanying executable declarations
and unlabelled inference use automatic profiles; imprecise tags retain the
content-evidence and stable-profile priority described in
[content selection rules](AUTO_SELECTION_RULES.md). Existing states require
the same core build and selected profile and are not converted.


## Profile implementation details

Profiles are compatibility selections. Several profiles use one physical source tree, with revision-specific behavior selected in code. Safety corrections and accepted additive extensions stay shared. This implementation reference is separate from the user-facing profile inventory.

| Selectable profile | Source tree |
|---|---|
| v3.0 3020-dev | `3400` |
| v3.0 3057 | `3400` |
| v3.0 3062 | `3400` |
| v3.0 3073 | `3400` |
| v3.0 3081 | `3400` |
| v3.0 3109 | `3400` |
| v3.0 3117 | `3400` |
| v3.0 3143 | `3400` |
| v3.0 3160 | `3400` |
| v3.0 3173 | `3400` |
| v3.0 3192 | `3400` |
| v3.0 3208 | `3400` |
| v3.0 3273 | `3400` |
| v3.0 3288 | `3400` |
| v3.0 3303 | `3400` |
| v3.0 3307 | `3400` |
| v3.0 3310 | `3400` |
| v3.0 3311 | `3400` |
| v3.0 3316 | `3400` |
| v3.0 3317 | `3400` |
| v3.0 3318 | `3400` |
| v3.0 3327 | `3400` |
| v3.0 3328 | `3400` |
| v3.0 3330 | `3400` |
| v3.0 3332 | `3400` |
| v3.0 3335 | `3400` |
| v3.0 3337 | `3400` |
| v3.0 3340 | `3400` |
| v3.0 3341 | `3400` |
| v3.0 3342 | `3400` |
| v3.0 3350 | `3400` |
| v3.0 3351 | `3400` |
| v3.0 3352 | `3400` |
| v3.0 3353 | `3400` |
| v3.0 3354 | `3400` |
| v3.0 3355 | `3400` |
| v3.0 3356 | `3400` |
| v3.0 3357 | `3400` |
| v3.0 3360 | `3400` |
| v3.0 3361 | `3400` |
| v3.0 3362 | `3400` |
| v3.0 3365 | `3400` |
| v3.0 3366 | `3400` |
| v3.0 3367 | `3400` |
| v3.0 3371 | `3400` |
| v3.0 3372 | `3400` |
| v3.0 3373 | `3400` |
| v3.0 3375 | `3400` |
| v3.0 3379 | `3400` |
| v3.0 3380 | `3400` |
| v3.0 3381 | `3400` |
| v3.0 3383 | `3400` |
| v3.0 3385 | `3400` |
| v3.0 3388 | `3400` |
| v3.0 3391 | `3400` |
| v3.0 3394 | `3400` |
| v3.0 3397 | `3400` |
| v3.0 3400 | `3400` |
| v3.0 3666 | `3741` |
| v3.0 3667 | `3741` |
| v3.0 3669 | `3741` |
| v3.0 3670 | `3741` |
| v3.0 3671 | `3741` |
| v3.0 3672 | `3741` |
| v3.0 3673 | `3741` |
| v3.0 3674 | `3741` |
| v3.0 3675 | `3741` |
| v3.0 3677 | `3741` |
| v3.0 3678 | `3741` |
| v3.0 3679 | `3741` |
| v3.0 3680 | `3741` |
| v3.0 3682 | `3741` |
| v3.0 3685 | `3741` |
| v3.0 3686 | `3741` |
| v3.0 3689 | `3741` |
| v3.0 3690 | `3741` |
| v3.0 3691 | `3741` |
| v3.0 3692 | `3741` |
| v3.0 3693 | `3741` |
| v3.0 3694 | `3741` |
| v3.0 3697 | `3741` |
| v3.0 3699 | `3741` |
| v3.0 3701 | `3741` |
| v3.0 3703 | `3741` |
| v3.0 3704 | `3741` |
| v3.0 3707 | `3741` |
| v3.0 3708 | `3741` |
| v3.0 3709 | `3741` |
| v3.0 3710 | `3741` |
| v3.0 3711 | `3741` |
| v3.0 3713 | `3741` |
| v3.0 3714 | `3741` |
| v3.0 3715 | `3741` |
| v3.0 3716 | `3741` |
| v3.0 3722 | `3741` |
| v3.0 3725 | `3741` |
| v3.0 3726 | `3741` |
| v3.0 3727 | `3741` |
| v3.0 3728 | `3741` |
| v3.0 3729 | `3741` |
| v3.0 3730 | `3741` |
| v3.0 3732 | `3741` |
| v3.0 3738 | `3741` |
| v3.0 3740 | `3741` |
| v3.0 3741 | `3741` |
| v3.0 3742-dev | `3741` |
| v3.0 3761-dev | `3842` |
| v3.0 3769 | `3842` |
| v3.0 3773 | `3842` |
| v3.0 3780 | `3842` |
| v3.0 3783 | `3842` |
| v3.0 3789 | `3842` |
| v3.0 3793 | `3842` |
| v3.0 3797 | `3842` |
| v3.0 3805 | `3842` |
| v3.0 3814 | `3842` |
| v3.0 3818 | `3842` |
| v3.0 3822 | `3842` |
| v3.0 3824 | `3842` |
| v3.0 3829 | `3842` |
| v3.0 3831 | `3842` |
| v3.0 3837 | `3842` |
| v3.0 3839 | `3842` |
| v3.0 3842 | `3842` |
| v3.0 4086 | `4086` |
| v3.0 4088-dev | `4086` |
| v3.0 4107 | `4086` |
| v3.0 4111 | `4086` |
| v3.0 4129 | `4086` |
| v3.0 4153 | `4086` |
| v3.0 4432 | `4432` |
| v3.0 4453 | `4432` |
| v3.0 6330 | `6391` |
| v3.0 6391 | `6391` |
| v3.0 6391-mod | `6391` |
| v3.0 6392-dev | `6391` |
| v3.0 6412-dev | `6391` |
| v3.0 6510-dev | `6391` |
| v3.0 7086-dev | `7142` |
| v3.0 7123-dev | `7142` |
| v4.0 7142-alpha | `7142` |
| v4.0 7533 | `7533` |
| v4.0 8023-dev | `8023` |

## Baselines and complete file inventories

| OpenBOR build | Pinned commit | File inventory |
|---|---|---|
| v3.0 3400 | `66fa1529897131ca51528967fbb21ee124e45775` | [v3.0 3400](modifications/3400.md) |
| v3.0 3741 | `00bcc4947748e8af10d030a82b60520bbd402e30` | [v3.0 3741](modifications/3741.md) |
| v3.0 3842 | `1f702a991ace7fa31884262e458a85e351f62713` | [v3.0 3842](modifications/3842.md) |
| v3.0 4086 | `af23dc9c2316bb7853bb266ccf40986aa9765aeb` | [v3.0 4086](modifications/4086.md) |
| v3.0 4432 | `2566cbee6185025e6a69d2aa1823b15c7a154ff9` | [v3.0 4432](modifications/4432.md) |
| v3.0 6391 | `494708eb34e71d1afda237873907701c4ec3a569` | [v3.0 6391](modifications/6391.md) |
| v3.0 7086-dev | `7a45a2215a0cc12c1085d92e7b210a827ea552c2` | [Selected contracts](HISTORICAL_PROFILES.md#divergent-test-profiles) |
| v3.0 7123-dev | `f5261e7cb97786909276c0b87f8f9f63504d2844` | [Selected contracts](HISTORICAL_PROFILES.md#divergent-test-profiles) |
| v4.0 7142-alpha | `9dcd966d1dc8e93ff03c39edbd6bd262f4a2d7ab` | [v4.0 7142-alpha](modifications/7142.md) |
| v4.0 7533 | `5c8261444de6b61f8e2ce6e79e3d86a2949e55bd` | [v4.0 7533](modifications/7533.md) |
| v4.0 8023-dev | `16aae1a30b81063778f21977ae20b849bd1c76f9` | [v4.0 8023-dev](modifications/8023.md) |

Each inventory links every modified or added engine file to its explanation,
original source at the pinned commit (where it existed). The accompanying `ANYBOR-SOURCE.json` also lists unchanged
files, omitted files from the upstream `engine/` subtree, original/distributed
SHA-256 hashes, and modification topics. Files elsewhere in the upstream repository,
including its standalone tools and repository documentation, are outside this
engine export. Pins and dependency archive hashes are in [src/pin.json](../src/pin.json).

The public engine imports include the portable circle and fixed-width endian
adaptations. Their replaced historical implementations are absent from the
distributed sources and documentation. The upstream baselines and original
hashes remain recorded for comparison.


### Revision contracts

Historical profiles select the player-property API by the chosen build. The pre-3797 contract preserves the integer result and nonfatal rejection
of an unconvertible score or other numeric value without changing the stored
value. The 3797 contract keeps its void success and script-error rejection.
Property names and numeric IDs remain in the logical build's domain, including
the 3797 spawn-property expansion, the 3798 keys setter and the 3821
weapon-number spelling and setter. Invalid names remain safe errors, and no
mutator receives an uninitialized optional argument. Safety and lifecycle
corrections are retained for every profile.

The same 3797 boundary selects native AI-flag names and numeric IDs. Older
profiles retain the read-only nested `freezetime` and `pain_time` getters and
the empty result of the deprecated `walking` getter. Newer profiles expose
`idlemode` and `walkmode`; the shared entity layout remains unchanged.

Player spawn Z coordinates retain the earlier 0..232 limit before 3800.
Before 3805, level spawn scripts retain ordered calls and one cached interpreter
per file, including shared script locals across spawn entries. The level owns
both cached resources and call nodes, including nodes belonging to discarded
parser entries. Cleanup preserves resource creation order and frees each
interpreter once. Their scope name is `spawnscript`. Inline level scripts are
available from 3805; earlier profiles handle their lines as ordinary level
commands. Later profiles retain the combined per-entry script path.

Patch `70-profile-4453.patch` adapts the behavior of upstream
[4453](https://github.com/DCurrent/openbor/commit/7906e2573fcd70e9eafcd30fbdcc680832c4ae42)
(2017-04-08). Profile 4453 forces 32-bit screens, keeps model-local indexed
palettes, ignores `colourdepth` and skips the legacy `remap`-to-palette
conversion removed in that revision. The earlier profile retains its video
configuration and palette conversion. Native settings I/O packs and unpacks
the original 4432 12-entry
layout and uses the 4453 13-entry layout directly. Profile identity keeps
their directories and save states separate. The later control menu disables
Exit reassignment. Both profiles bound the DOT loop to its allocated slots
and keep control-menu indexing within its arrays.


Engine 6391 uses upstream commit
[`494708eb34e71d1afda237873907701c4ec3a569`](https://github.com/DCurrent/openbor/commit/494708eb34e71d1afda237873907701c4ec3a569).
Patch `71-profile-6412.patch` adapts the later upstream 6412 script
changes from commit
[`d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8`](https://github.com/DCurrent/openbor/commit/d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8)
for engine 6412. Engine 6391 retains its scalar binding properties
and numeric property IDs. Engine 6412 exposes axis-handle binding
properties, owner and opponent entity properties, binding animation flags,
the corrected Y-axis setter, frame-kill binding behavior, and `unload_model`.
Each profile has its own save directory.

Patches `72-profile-6330.patch` and `73-profile-6510.patch`
adapt the earlier [6330 source](https://github.com/DCurrent/openbor/commit/4b1705fa37457ab38bc5d0fcc561242019588e32)
and later [6510 source](https://github.com/DCurrent/openbor/commit/ecce29b95700468aa3401915625dac2d56e4ca60)
inside the same 6391 engine object. Runtime profile branches restore 6330's
boomerang model commands, projectile movement and catching, earlier juggle
condition and settings layout. The 6510 branches supply binding matching,
positioning, tags, overrides and script events, revised blocking and flashes,
and the distinct boss-death attack type. Script-container copy and cleanup
follow the native callback declaration order, retaining the shared field layout. Native animation, attack, entity,
subtype and spawn IDs are translated at script boundaries so adding shared
selectors does not change the public numbering of older profiles. The earlier
collision scripting entry points remain unavailable in profile 6330.

Profiles before build 3680 track impact pause by animation frame; later profiles
track its deadline. The earlier frame state retains its native signed 16-bit
representation within the shared pause storage. Animation changes and frame
updates use the corresponding profile rules for resetting that state.

Idle animation selection retains the incoming target-query context in profiles
before build 3680. Other profiles use their source-defined context selection
and restoration, including the alternate-animation path. Missing contexts
leave a defined fallback. Refused animation changes emit their source-defined
diagnostics in profiles before build 3694.

Level physics starts with maximum toss speed 100, maximum fall speed -6 and
gravity -0.1 in profiles below build 3681. Profiles from build 3681 use the
configured level defaults.

Animation-triggered removal uses fixed drop velocity before build 3681 and
configured default drop velocity from build 3681. Spawn and summon events
precede removal before build 3689; removal precedes those events from build
3689. Script changes to the active animation or frame interrupt the remaining
frame events. Alternate idle queries retain the subject context through build
3796; the animation-series path restores the incoming context from build 3797.

Fresh native script records retain a zero validity marker before build 3693
and the script marker from build 3693. Explicit first initialization sets the
script marker in both cases. Variable arrays retain their native empty state.

Failed assertions identify the expression, function, source file and line.
Profiles before 3811 use a C-style diagnostic on standard error; profiles from
3811 use the engine log. Failed invariants stop the active engine through the
core's controlled exit while the frontend process remains running. Assertion
evaluation follows each profile's source rules when NDEBUG is defined.

The source-defined profiles from 3666 through 3773 retain their own script,
data, rendering and audio contracts. The 3742-dev and 3761-dev profiles are
available through an exact build tag or manual selection; weak-tag and
unlabelled content inference do not select them. Their source commits are
recorded in `src/pin.json`.
