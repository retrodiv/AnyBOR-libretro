# Choosing a profile

Selectable engine profiles: v3.0 3400, v3.0 3780, v3.0 3783, v3.0 3789, v3.0 3793, v3.0 3797,
v3.0 3805, v3.0 3814, v3.0 3818, v3.0 3822, v3.0 3824, v3.0 3829, v3.0 3831,
v3.0 3837, v3.0 3839, v3.0 3842, v3.0 4086, v3.0 4432, v3.0 4453, v3.0 6330,
v3.0 6391, v3.0 6392-dev, v3.0 6412-dev, v3.0 6510-dev, v3.0 7123-dev, v4.0 7142-alpha,
v4.0 7533 and v4.0 8023-dev.

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
|3820|conditional|Level selector numbering, successful results and nonfatal rejection preserve the earlier contract.|
|3821|conditional|Text numeric/string conversion, result values, partial field updates and weapon-number spelling follow this boundary. Text ownership remains bounded.|
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
|3842|shared|Font storage retains glyph-width behavior; clipping and NULL checks remain safe.|

A failure that disappears in the original declared engine remains a compatibility
issue to investigate, even when it also occurs with another profile. Selecting
an earlier profile does not promise exact emulation of an original executable.


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
