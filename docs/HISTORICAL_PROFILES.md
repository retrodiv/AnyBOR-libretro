# Choosing a profile

Selectable engine profiles: v3.0 3400, v3.0 3780, v3.0 3783, v3.0 3789, v3.0
3793, v3.0 3797, v3.0 3805, v3.0 3814, v3.0 3818, v3.0 3822, v3.0 3824, v3.0
3829, v3.0 3831, v3.0 3837, v3.0 3839, v3.0 3842, v3.0 4086, v3.0 4088-dev,
v3.0 4107, v3.0 4111, v3.0 4129, v3.0 4153, v3.0 4432, v3.0 4453, v3.0 6330,
v3.0 6391, v3.0 6392-dev, v3.0 6412-dev, v3.0 6510-dev, v3.0 7086-dev, v3.0
7123-dev, v4.0 7142-alpha, v4.0 7533 and v4.0 8023-dev.

Auto uses build tags and content clues to choose a profile. You can select one
manually when a game needs it. Historical profiles preserve selected earlier
content behavior while retaining safety and lifecycle corrections.

## Select a profile

Manual selection overrides Auto when the metadata is missing or incorrect:

1. Find the engine build specified by the content's author or original release.
2. Open **Quick Menu > Core Options > System > Engine build**. Frontends without
   categories display **Engine build** in the flat core-options list.
3. Select the full value, such as **v3.0 3780**, and use **Restart** or reload
   the content. The frontend log reports the selected profile.
4. Keep that profile for the session. States require the same logical profile,
   core build and content; switching profiles does not convert existing states.

If the required revision is unknown, start with Auto and consult the content
release documentation before choosing manually.

## Selected contracts and shared behavior

| Boundary | Selected earlier contract |
|---|---|
| 3797 | Player-property names/numeric selectors, integer/void setter result and rejected numeric values; AI-flag names/selectors, earlier read-only nested timers and deprecated walking result. |
| 3798 | Introduction of the player keys setter. |
| 3800 | Earlier player spawn Z limit of 0..232. |
| 3802 | Earlier user-defined preprocessor names, including names reserved by later builtins. |
| 3820 | Earlier level-property selectors and nonfatal rejected setter values. |
| 3821 | Earlier text setters retain their numeric result, tolerate negative indices and preserve rejected numeric fields. |
| 3826 | Unknown textual constants return an empty value before this revision; later profiles reject them. |
| 3805 | Ordered level spawn scripts with shared cached per-file locals before this revision; combined per-entry scripts afterwards. |
| 3821 | Player weapon-number spelling and introduction of its setter. |

Complete script variable names are supported in every engine. Names are never
truncated to imitate unsafe fixed-size storage. Native and compiled-script
regressions cover these selected contracts, including state restoration of
complete global and local names.

Every reviewed contract-bearing revision is recorded below. Conditional rows
select earlier observable behavior; shared rows retain additive syntax or safety
corrections. An earlier profile never requests unsafe memory behavior.

| Revision | Policy | Scope |
|---|---|---|
|3783|conditional|Earlier shared scroll axes, zero-as-unspecified bounds and numeric system-property ordering; later independent bounds. Camera safety corrections remain universal.|
|3784|shared|Direct video dimensions are additive syntax; clipping and camera bounds remain safe.|
|3786|shared|Individual x/z/a setters are additive aliases; the existing position setter remains available.|
|3787|conditional|The spawn-to-respawn animation fallback follows its introduction. Missing color maps remain safe rather than restoring an abort.|
|3789|not applicable|Standalone touch-screen docking is replaced by the frontend interface.|
|3793|conditional|Weapon-model update order and model-copy callback registration follow this revision; snapshots and ownership remain initialized.|
|3797|conditional|Player-property and AI-flag names, numeric selectors, result values and rejected-value handling follow the selected contract.|
|3798|conditional|The player keys setter follows its introduction. Guard-point and memory/lifecycle corrections remain shared.|
|3800|conditional|Player spawn Z uses the earlier 0..232 limit before this revision.|
|3801|conditional|Holdblock bit 2 and AI orbit sign/parity handling follow this boundary.|
|3802|conditional|Preprocessor builtin-like names remain ordinary user macros earlier; malformed lexical input is always rejected safely.|
|3803|shared|Retain corrected lexer token handoff and preprocessing bounds; defined is already reserved by the selected 3802 boundary.|
|3805|conditional|Earlier ordered spawn scripts retain shared per-file locals; later entries use combined scripts. Additive level-script syntax remains accepted.|
|3806|conditional|The explicit nested-script suppression flag applies from this revision; script ownership remains safe.|
|3810|shared|switch, case, default and break were already reserved in 3780. The added grammar does not newly reserve these identifiers.|
|3812|shared|String switch/case is additive grammar; diagnostics remain safe.|
|3813|conditional|Animation-command grouping, early return and nested-interpreter snapshots follow 3813, 3823 and 3836 boundaries.|
|3816|shared|Ternary operators are additive grammar and introduce no reserved identifiers.|
|3819|conditional|Raw versus format-aware shadowcolor conversion, idle entry order and sleep timing follow this boundary.|
|3820|conditional|Level selector numbering, successful results and nonfatal rejection preserve the earlier contract. The level getter uses the drawmethod runtime mapper earlier and the level mapper from this boundary; compiler literals use the level mapper in both. Completed-game bonuses are recalculated by successful character/difficulty menu loads earlier and by the saved-game loader from this boundary; other callers retain their native side effects.|
|3821|conditional|The level setter changes from the drawmethod runtime mapper to the level mapper. Unconverted property strings preserve their native cache-index dispatch. Text numeric/string conversion, result values, partial field updates and weapon-number spelling follow this boundary. Text ownership remains bounded.|
|3822|conditional|Native saves begin recording selectable/model state here; eager cached-model loading ends at 3835. Model-name lookup remains additive.|
|3823|conditional|Animation commands use the original default grouping and early-return policy, with nocmdcompatible controlling the later contract.|
|3824|conditional|The idle/sleep timer guard and finished-animation behavior follow this boundary.|
|3825|conditional|Sleep activation changes from an inclusive to a strict deadline.|
|3826|conditional|Unknown textual constants return empty earlier and are rejected later. Dynamic suffix lookups retain safe corrected prefix mapping.|
|3828|conditional|Earlier unsupported unary operands clear to empty; supported numeric values follow the earlier contract without unsafe signed overflow. Other selector sub-enum orders are unchanged.|
|3830|conditional|Attack-table size, environmental damage typing/health and Defense ALL are selected together, retaining bounded storage.|
|3831|conditional|Attack extension offsets, exported environmental constants, default animation slots and Offense ALL follow this revision.|
|3833|shared|Shift operators are additive grammar. Formatting safety is retained.|
|3834|conditional|exit function registration and completed holdblock animation behavior follow this boundary. Interpreter completion safety remains shared.|
|3835|conditional|Native saved model records stop eagerly loading cached models here.|
|3836|conditional|Nested interpreter snapshots and bReset behavior follow the original nocmdcompatible contract; ownership remains valid.|
|3837|conditional|Earlier arithmetic-mean camera framing, integer truncation and branch-specific offsets; later extreme-player framing and span limits.|
|3838|conditional|playsample result type, negative sample handling and system-property numbering follow this boundary. Dynamic sample ownership and channel safety remain shared.|
|3839|shared|Bitwise operators are additive grammar and introduce no reserved words.|
|3841|shared|Extracted animation statements are semantically unchanged; sync syntax is additive.|
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

## Reconstructed test profile

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
| v3.0 3400 | `3400` |
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
interpreter once. Later profiles retain the combined per-entry script path.

Patch `96-logical-4453-compat.patch` adapts the behavior of upstream
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
Patch `96-logical-6412-compat.patch` adapts the later upstream 6412 script
changes from commit
[`d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8`](https://github.com/DCurrent/openbor/commit/d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8)
for engine 6412. Engine 6391 retains its scalar binding properties
and numeric property IDs. Engine 6412 exposes axis-handle binding
properties, owner and opponent entity properties, binding animation flags,
the corrected Y-axis setter, frame-kill binding behavior, and `unload_model`.
Each profile has its own save directory.

Patches `97-logical-6330-compat.patch` and `98-logical-6510-compat.patch`
adapt the earlier [6330 source](https://github.com/DCurrent/openbor/commit/4b1705fa37457ab38bc5d0fcc561242019588e32)
and later [6510 source](https://github.com/DCurrent/openbor/commit/ecce29b95700468aa3401915625dac2d56e4ca60)
inside the same 6391 engine object. Runtime profile branches restore 6330's
boomerang model commands, projectile movement and catching, earlier juggle
condition and settings layout. The 6510 branches supply binding matching,
positioning, tags, overrides and script events, revised blocking and flashes,
and the distinct boss-death attack type. Native animation, attack, entity,
subtype and spawn IDs are translated at script boundaries so adding shared
selectors does not change the public numbering of older profiles. The earlier
collision scripting entry points remain unavailable in profile 6330.
