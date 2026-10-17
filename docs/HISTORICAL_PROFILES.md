# Historical engine profiles

Historical profiles share engine 3842 while selecting specific earlier content
contracts. They are compatibility variants, not complete copies of every
intermediate upstream engine or its former defects. Safety and lifecycle
corrections remain enabled.

## Select a profile

1. Find the engine build specified by the content's author or original release.
   A renamed archive is not reliable evidence of that build.
2. Open **Quick Menu > Core Options > System > Engine build**. Frontends without
   categories display **Engine build** in the flat core-options list.
3. Select the full value, such as **v3.0 3780**, and use **Restart** or reload
   the content. The frontend log reports the selected profile and physical engine.
4. Keep that profile for the session. States require the same logical profile,
   core build and content; switching profiles does not convert existing states.

The available historical revisions are 3780, 3783, 3789, 3793, 3797, 3805,
3814, 3818, 3822, 3824, 3829, 3831, 3837 and 3839. Profile 3842 retains the
corresponding later contracts. If the required revision is unknown, start with
Auto and consult the content's release documentation before choosing manually.
Auto retains its established engine-era routing; it does not infer these minor
historical profiles from missing syntax, a renamed file or a content hash.

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

The following table records every reviewed contract-bearing revision. Shared
rows deliberately retain engine 3842 behavior. They are explicit compatibility
limits, not claims that the corresponding historical behavior is reproduced.
Additive syntax and safety corrections are retained rather than manufacturing
historical parser errors, crashes or invalid memory accesses.

| Revision | Policy | Scope and reason |
|---|---|---|
|3783|shared|Independent X/Z scroll bounds and explicit presence flags remain. Recreating conflated axes would restore a boundary defect; earlier axis conflation is not emulated. No original-runner framing dependency is established.|
|3784|shared|Direct video dimensions are an additive input form. Rejecting them in older profiles would remove useful compatible syntax; camera-boundary corrections remain universal.|
|3786|shared|Individual x/z/a setters are additive; the existing position setter remains available. Disabling the added names supplies no demonstrated compatibility benefit.|
|3787|shared|Retain the respawn fallback when spawn is absent and tolerant missing-remap handling. No original-runner dependency on suppressing that fallback is demonstrated; restoring a fatal missing-remap path would reduce robustness.|
|3789|not-applicable|touch.txt screen docking belongs to the removed standalone Android presentation implementation. Libretro frontend input and presentation do not execute it.|
|3793|shared|The new model-copy callback is absent in content that does not request it. Keep the consistent weapon-before-callback ordering and initialized self/old locals; no original-runner dependency on stale player weapon state is established.|
|3797|conditional|Player names/numeric selectors, spawn-property expansion, integer versus void setter results, nonfatal rejected numeric values, and AI-flag names/selectors/timer/walking getter contracts are profile-gated. Internal idle/walk dispatch corrections remain shared rather than restoring unproved animation defects.|
|3798|conditional|The player keys setter follows its introduction boundary. holdblock is explicitly requested behavior; keep guard-point, blockpain and animation repairs in all profiles rather than recreating the immediately repaired intermediate fault.|
|3800|conditional|Player spawn Z retains the earlier 0..232 clamp before 3800. Modern coordinates remain unchanged; invalid height handling remains safe.|
|3801|shared|Keep holdblock bit 2 support and normalized/parity-correct AI orbit selection. No original-runner combat dependency on the former orbit sign or blockpain defect is demonstrated; reproducing it would require broader combat oracles.|
|3802|conditional|Before 3802, builtin-like names remain ordinary user macros and are not implicitly expanded or reserved. Later profiles keep builtin expansion and reserved-name errors. Conditional grammar, lexical bounds, nesting and lifetime safety remain shared; malformed lexical input is rejected in every profile.|
|3803|shared|Keep the identifier handoff for defined and the corrected preprocessing/lexer boundary. Reintroducing the token mismatch is not needed by any demonstrated old-content contract.|
|3805|conditional|Before 3805, multiple spawnscript declarations retain source order and per-file cached locals. Keep additive level @script syntax and safe ownership/cleanup; later profiles retain per-entry combined scripts.|
|3806|shared|nonestedscript is an explicit opt-in flag with default 0. Its addition does not change the default contract; keep correct busy-state and script-owner restoration.|
|3810|shared|switch/case/break is additive grammar. No old-content use of a newly reserved word as an identifier is demonstrated; per-profile parsers are disproportionate without such evidence. Keep safe branch/compiler repairs.|
|3812|shared|String switch/case extends the new grammar; accepting it does not change previously valid programs. Keep corrected error diagnostics.|
|3813|shared|The later 3823 default already retains separate legacy @cmd frame checks. Preserve that explicit compatibility mechanism and nested-state safety fixes; recreating intermediate automatic grouping has no demonstrated compatibility benefit.|
|3816|shared|Ternary expressions are additive grammar; no need to reject otherwise valid expressions solely to imitate an older parser.|
|3819|shared|Retain format-aware shadowcolor conversion and idle/sleep timer repairs. No original-runner image mismatch requiring the former raw color interpretation is demonstrated; a gate without such an oracle risks inconsistent indexed/RGB rendering.|
|3820|conditional|Earlier level-property numeric selectors omit type; known setters preserve the caller return representation and tolerate rejected values. Unknown or read-only selectors remain errors. Retain the corrected property-name mapper and bounds/type checks rather than restoring the old incorrect mapper.|
|3821|conditional|Earlier text setters retain integer results, nonfatal negative indices and rejected numeric fields, including independent field updates and an unchanged omitted timeout. Later profiles retain strict conversion errors and void results. Player weapon-number spelling and setter availability also follow this boundary. Text name lookup is bounded and preserves each engine native IDs.|
|3822|shared|Model-name property lookup is additive. Keep saved selectable/preload-list consistency and model-index bounds; reverting native-save/model lifetime behavior without an original persistence oracle would risk missing resources and unsafe cached models.|
|3823|shared|Retain nocmdcompatible default 0 and its explicit grouping/early-return option; it already restores legacy separate frame checks. No extra logical-profile gate is needed for that default.|
|3826|conditional|Before 3826, unknown textual constants yield an empty value without aborting the script. Later profiles retain strict rejection. Known constants, numeric passthrough, missing arguments and invalid argument types retain their existing contracts; no guessed constant aliases are introduced.|
|3828|shared|All 23 reviewed getter/setter sub-enum orders are unchanged after normalization. Retain early model constants, safe unified mappings and reference/lifetime fixes. Unsupported-type unary quirks are not emulated without an affected valid program.|
|3830|shared|Keep the 3842 attack-type layout, typed environmental damage and Defense ALL behavior. These are a coupled combat/constant/layout contract; reverting isolated pieces risks wrong indices and unsafe tables. No original-runner gameplay dependency is established in the reviewed content, so broad combat emulation is outside this narrow profile release.|
|3831|shared|Retain attack-array extension/bounds fixes and 3842 dynamic attack suffix IDs. Legacy numerical attack-ID emulation is coupled to 3830 and lacks a demonstrated original-runner dependency; retain compiler/instruction correctness fixes universally.|
|3833|shared|Shift operators are additive grammar. Preserve output format-string correction for all profiles; recreating a formatting vulnerability offers no compatibility benefit.|
|3834|shared|exit() is additive. Keep interpreter completion/early-stop and holdblock animation fixes rather than emulating unfinished or stale execution.|
|3835|shared|Keep saved-model lifetime and on-demand resource loading consistent with 3842 native saves. Reintroducing eager model loading can add unnecessary allocation/preloading and needs an original persistence case before changing the shared resource lifecycle.|
|3836|shared|Keep the final nocmdcompatible-controlled nested-interpreter behavior and safe script-owner handling. Restoring unconditional interpreter snapshots changes nested execution and resource lifetime; no original-runner dependency is demonstrated, so that broader VM contract is explicitly not emulated.|
|3837|shared|Retain extreme-player camera midpoint/span handling as a multiplayer camera correction. No original-runner need for former arithmetic-mean framing is established; preserving the fix avoids restoring edge-of-screen defects.|
|3838|shared|Keep dynamic sample cache/lifecycle and channel APIs, including integer playsample results and tolerant invalid IDs. No reviewed script is established to depend on the former void result/error. Recreating fixed cache limits or broken querychannel/stopchannel fallthrough is not justified.|
|3839|shared|Bitwise operators are additive grammar. Keep accepted syntax instead of manufacturing historical parse failures.|
|3841|shared|Normalized extracted animation statements are identical apart from locals and explicit parameters/return. sync is additive; no old default synchronization difference is established.|
|3842|shared|Retain compact font atlas with its glyph-width contract, clipping bounds and soundtoplay NULL guard. No original image difference requiring old per-glyph allocations is demonstrated; restoring unsafe clipping is excluded.|

A failure that disappears in the original declared engine remains a compatibility
issue to investigate, even when it also occurs in the shared engine. Selecting
an earlier profile does not promise exact emulation of an original executable.
