# Content evidence for build tags

Manual selection is authoritative. An exact filename Build tag with its own
selectable profile retains its existing routing and priority. An exact Build
tag without its own profile first uses the ordinary automatic candidate. If
proved content requirements exclude that candidate, Auto chooses the profile
nearest to the declared build that satisfies all those requirements. Equal
distances prefer a stable or automatic profile, then the higher build. If no
profile satisfies every requirement, the log records the contradiction and
the existing routing is retained; this does not establish compatibility.
This check applies to prepared PACK content with a complete numeric Build tag,
not to the separate legacy v2 filename form.

An imprecise tag, such as Build 44XX or Build 3792-3911, is
intersected with the supported content evidence. The highest stable or automatic
profile inside the resulting compatible interval wins. Development profiles are
considered when no stable or automatic profile remains compatible there.
If content contradicts the declared interval, the declaration wins: choose the
nearest available profile inside it and record the conflict. Existing behavior
for an interval with no available profile is retained.

Syntax is inspected without executing scripts. Comments and quoted prose never
supply a requirement. Constant and property names count only as complete literal
arguments of recognized native calls. Dynamic expressions are inconclusive.
Preprocessing or a local declaration of a sampled builtin invalidates script
evidence. A truncated scan retains complete model-command facts already
observed, including removals and palette incompatibilities. It cannot prove
script binding: an unread declaration or macro may change a sampled call's
meaning, so uncertain script facts are discarded. A separately completed
dependency probe can still supply its established minimum. File, byte and time
budgets remain bounded. This is not whole-program reachability analysis.

Palette conversion and 8/16-bit output were temporarily removed and then
restored. They exclude the incompatible profile rather than imposing a false
global upper bound. Divergent source branches likewise need their verified
namespace support, rather than an assumption that build numbers form one line.

| Syntax context | Required token or literal | Necessary bounds / exception | Upstream changes |
|---|---|---|---|
|palette|`16bit`|all retained compatible eras except v3.0 4453|[`562f36d7`](https://github.com/DCurrent/openbor/commit/562f36d736aadc5ac0644a4ab2dbd50d20f880a3), [`c89f970c`](https://github.com/DCurrent/openbor/commit/c89f970c12754b617d3670124fb59b1ea7f0eb9a), [`7906e257`](https://github.com/DCurrent/openbor/commit/7906e2573fcd70e9eafcd30fbdcc680832c4ae42), [`4b1705fa`](https://github.com/DCurrent/openbor/commit/4b1705fa37457ab38bc5d0fcc561242019588e32)|
|palette|`8bit`|all retained compatible eras except v3.0 4453|[`562f36d7`](https://github.com/DCurrent/openbor/commit/562f36d736aadc5ac0644a4ab2dbd50d20f880a3), [`c89f970c`](https://github.com/DCurrent/openbor/commit/c89f970c12754b617d3670124fb59b1ea7f0eb9a), [`7906e257`](https://github.com/DCurrent/openbor/commit/7906e2573fcd70e9eafcd30fbdcc680832c4ae42), [`4b1705fa`](https://github.com/DCurrent/openbor/commit/4b1705fa37457ab38bc5d0fcc561242019588e32)|
|function|`allocate_palette`|from 7582|[`34342f6f`](https://github.com/DCurrent/openbor/commit/34342f6f606cf8421945dd69b7453dc754462907)|
|constant|`ani_prop_animhits`|4232–7083; corresponding divergent test-branch exception|[`869df0ce`](https://github.com/DCurrent/openbor/commit/869df0ce4aeeca5ab3c41ca48928e902a327fe4b), [`d7a21970`](https://github.com/DCurrent/openbor/commit/d7a21970717d7af9c291d1d9d0481a240c4c16a7), [`7a45a221`](https://github.com/DCurrent/openbor/commit/7a45a2215a0cc12c1085d92e7b210a827ea552c2), [`f5261e7c`](https://github.com/DCurrent/openbor/commit/f5261e7cb97786909276c0b87f8f9f63504d2844)|
|constant|`ani_prop_numframes`|4232–7083; corresponding divergent test-branch exception|[`869df0ce`](https://github.com/DCurrent/openbor/commit/869df0ce4aeeca5ab3c41ca48928e902a327fe4b), [`d7a21970`](https://github.com/DCurrent/openbor/commit/d7a21970717d7af9c291d1d9d0481a240c4c16a7), [`7a45a221`](https://github.com/DCurrent/openbor/commit/7a45a2215a0cc12c1085d92e7b210a827ea552c2), [`f5261e7c`](https://github.com/DCurrent/openbor/commit/f5261e7cb97786909276c0b87f8f9f63504d2844)|
|entity getter|`animation` as the complete second argument of `getentityproperty`|through 4201; unavailable from 4202|[`f48b54be`](https://github.com/DCurrent/openbor/commit/f48b54be09eed68c39612d6d358573eba65d6b89)|
|constant|`atk_land`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|constant|`atk_lifespan`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|constant|`atk_pit`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|constant|`atk_timeover`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|constant|`binding_ani_animation_kill`|6397–6434|[`72fd91ce`](https://github.com/DCurrent/openbor/commit/72fd91cef744ba514f04edeef326bdd6b40761a0), [`b0e5fd7f`](https://github.com/DCurrent/openbor/commit/b0e5fd7f378515b5167ce496f2e87e91bbffe21f)|
|constant|`binding_ani_animation_match`|6397–6434|[`72fd91ce`](https://github.com/DCurrent/openbor/commit/72fd91cef744ba514f04edeef326bdd6b40761a0), [`b0e5fd7f`](https://github.com/DCurrent/openbor/commit/b0e5fd7f378515b5167ce496f2e87e91bbffe21f)|
|constant|`binding_ani_frame_kill`|6397–6434|[`72fd91ce`](https://github.com/DCurrent/openbor/commit/72fd91cef744ba514f04edeef326bdd6b40761a0), [`b0e5fd7f`](https://github.com/DCurrent/openbor/commit/b0e5fd7f378515b5167ce496f2e87e91bbffe21f)|
|constant|`binding_ani_frame_match`|6397–6434|[`72fd91ce`](https://github.com/DCurrent/openbor/commit/72fd91cef744ba514f04edeef326bdd6b40761a0), [`b0e5fd7f`](https://github.com/DCurrent/openbor/commit/b0e5fd7f378515b5167ce496f2e87e91bbffe21f)|
|constant|`binding_ani_none`|6397–6434|[`72fd91ce`](https://github.com/DCurrent/openbor/commit/72fd91cef744ba514f04edeef326bdd6b40761a0), [`b0e5fd7f`](https://github.com/DCurrent/openbor/commit/b0e5fd7f378515b5167ce496f2e87e91bbffe21f)|
|constant|`binding_matching_none`|6436–6964|[`802bfc08`](https://github.com/DCurrent/openbor/commit/802bfc084c3d4ac926e096132064ae590c890db9), [`5d14cdf1`](https://github.com/DCurrent/openbor/commit/5d14cdf12c529e6eb5fd67f95d5be563ed086b29)|
|command|`boomerang`|any earlier revision through 6376|[`2e6a9404`](https://github.com/DCurrent/openbor/commit/2e6a94045150963da118775b1e34b014b3d33b1d)|
|command|`boomerangvalues`|any earlier revision through 6376|[`2e6a9404`](https://github.com/DCurrent/openbor/commit/2e6a94045150963da118775b1e34b014b3d33b1d)|
|command|`custboomerang`|any earlier revision through 6376|[`2e6a9404`](https://github.com/DCurrent/openbor/commit/2e6a94045150963da118775b1e34b014b3d33b1d)|
|command|`ebox`|from 6332|[`ed30ca95`](https://github.com/DCurrent/openbor/commit/ed30ca95e4d7d46181e215720d23e4452336a77e)|
|function|`exit`|from 3834|[`b3ad0f9d`](https://github.com/DCurrent/openbor/commit/b3ad0f9d585abf5388041d953dad08f57d2561bf)|
|aiflag_read|`freezetime`|any earlier revision through 3796|[`4490ee5d`](https://github.com/DCurrent/openbor/commit/4490ee5d18ffcc7604e95cd4910dadf6191e694a)|
|function|`get_colorset_property`|from 7470|[`fba169f8`](https://github.com/DCurrent/openbor/commit/fba169f8befe19315ecf0ebbc5f6207828caff58)|
|function|`get_command_input_event_property`|from 7843|[`d0a92dd3`](https://github.com/DCurrent/openbor/commit/d0a92dd39390df66235a9eaf937e6daa8fc6a3a5)|
|function|`get_entity_collision_collection`|6340–7823|[`a70cdf74`](https://github.com/DCurrent/openbor/commit/a70cdf74047b51bd133152370078ca2f3a6bf204), [`ace96922`](https://github.com/DCurrent/openbor/commit/ace969220b7f1d1aab0cd654cd8e978fa6f98ffb)|
|function|`get_entity_collision_instance`|6340–7823|[`a70cdf74`](https://github.com/DCurrent/openbor/commit/a70cdf74047b51bd133152370078ca2f3a6bf204), [`ace96922`](https://github.com/DCurrent/openbor/commit/ace969220b7f1d1aab0cd654cd8e978fa6f98ffb)|
|function|`get_entity_collision_property`|6340–7823|[`a70cdf74`](https://github.com/DCurrent/openbor/commit/a70cdf74047b51bd133152370078ca2f3a6bf204), [`ace96922`](https://github.com/DCurrent/openbor/commit/ace969220b7f1d1aab0cd654cd8e978fa6f98ffb)|
|function|`get_faction_property`|from 7445|[`3d430bf0`](https://github.com/DCurrent/openbor/commit/3d430bf0fc2aa24db1a2cb0cab2e4029431b9934)|
|function|`get_sound_property`|from 7871|[`7846cefe`](https://github.com/DCurrent/openbor/commit/7846cefe313fe2434bd04d1a42596785dbb083a7)|
|player_write|`keys`|from 3798|[`64554a92`](https://github.com/DCurrent/openbor/commit/64554a92b6596b1fec71cb4219305d6004fb8ee7)|
|attack_name|`land`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|attack_name|`lifespan`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|function|`movie_load`|from 7964|[`b892b63c`](https://github.com/DCurrent/openbor/commit/b892b63c63053ad209b2aab8179faeb83034c973)|
|function|`movie_play`|from 7964|[`b892b63c`](https://github.com/DCurrent/openbor/commit/b892b63c63053ad209b2aab8179faeb83034c973)|
|function|`movie_stop`|from 7964|[`b892b63c`](https://github.com/DCurrent/openbor/commit/b892b63c63053ad209b2aab8179faeb83034c973)|
|command|`on_bind_update_other_to_self_script`|from 6421|[`ab98603e`](https://github.com/DCurrent/openbor/commit/ab98603e7244ab6b41eac3e1cb94be5941cdbf80)|
|command|`on_bind_update_self_to_other_script`|from 6421|[`ab98603e`](https://github.com/DCurrent/openbor/commit/ab98603e7244ab6b41eac3e1cb94be5941cdbf80)|
|command|`onmodelcopyscript`|from 3793|[`edf23465`](https://github.com/DCurrent/openbor/commit/edf234656cae88b078718661a2bd0c42090f0687)|
|aiflag_read|`pain_time`|any earlier revision through 3796|[`4490ee5d`](https://github.com/DCurrent/openbor/commit/4490ee5d18ffcc7604e95cd4910dadf6191e694a)|
|attack_name|`pit`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|command|`remap`|all retained compatible eras except v3.0 4453|[`562f36d7`](https://github.com/DCurrent/openbor/commit/562f36d736aadc5ac0644a4ab2dbd50d20f880a3), [`c89f970c`](https://github.com/DCurrent/openbor/commit/c89f970c12754b617d3670124fb59b1ea7f0eb9a), [`7906e257`](https://github.com/DCurrent/openbor/commit/7906e2573fcd70e9eafcd30fbdcc680832c4ae42), [`4b1705fa`](https://github.com/DCurrent/openbor/commit/4b1705fa37457ab38bc5d0fcc561242019588e32)|
|system|`sample_play_id`|from 3838|[`cb129b1f`](https://github.com/DCurrent/openbor/commit/cb129b1f2d01e3653ade9f0663609a54527d8ca3)|
|system|`scrollmaxx`|from 3783|[`5da3e255`](https://github.com/DCurrent/openbor/commit/5da3e255b2783079872a57247b020090e307df0d)|
|system|`scrollminx`|from 3783|[`5da3e255`](https://github.com/DCurrent/openbor/commit/5da3e255b2783079872a57247b020090e307df0d)|
|function|`set_entity_collision_property`|6340–7823|[`a70cdf74`](https://github.com/DCurrent/openbor/commit/a70cdf74047b51bd133152370078ca2f3a6bf204), [`ace96922`](https://github.com/DCurrent/openbor/commit/ace969220b7f1d1aab0cd654cd8e978fa6f98ffb)|
|function|`set_sound_property`|from 7871|[`7846cefe`](https://github.com/DCurrent/openbor/commit/7846cefe313fe2434bd04d1a42596785dbb083a7)|
|player|`spawnhealth`|from 3797|[`4490ee5d`](https://github.com/DCurrent/openbor/commit/4490ee5d18ffcc7604e95cd4910dadf6191e694a)|
|player|`spawnmp`|from 3797|[`4490ee5d`](https://github.com/DCurrent/openbor/commit/4490ee5d18ffcc7604e95cd4910dadf6191e694a)|
|attack_name|`timeover`|from 3831|[`c61f02b3`](https://github.com/DCurrent/openbor/commit/c61f02b3fbb155dd416a7750eb9cb645d7785266)|
|level|`type`|from 3820|[`ee9b34fd`](https://github.com/DCurrent/openbor/commit/ee9b34fd1f52d7edb3c4604b39dc4efe2bb1b6ab)|
|function|`unload_model`|from 6411|[`3618084b`](https://github.com/DCurrent/openbor/commit/3618084b81e63cfd7586f4d8bd8ee734f7697e99)|
|player|`weapnum`|from 3821|[`651c34ff`](https://github.com/DCurrent/openbor/commit/651c34ffec57b78a8df7ae24898d8e369978d398)|
|player|`weaponum`|any earlier revision through 3820|[`651c34ff`](https://github.com/DCurrent/openbor/commit/651c34ffec57b78a8df7ae24898d8e369978d398)|

The existing literal `getentityproperty(..., "attack", ...)` probe supplies
the upper bound 4166 for this removed API; upstream change
[`4b3adb06`](https://github.com/DCurrent/openbor/commit/4b3adb06168068fd6388f907f2f79c51bf506e13)
removed it at 4167. Other existing command, animation, native-call and constant
rules continue to contribute their bounds. The log identifies the effective
rules and whether the selected profile supports them.

No absence of newer syntax establishes an old revision. Numeric values whose
meaning changed, without a distinguishing API spelling, do not establish a
version by themselves. A matching hash or game identity never selects a rule.
The reconstructed test profile has no invented content signature.

Unlabelled content retains the existing inference/fallback policy. The two
official releases v3.0 4453 and v3.0 6330 participate in ordinary automatic
routing. Accompanying executables and unlabelled inference do not select
nonautomatic test profiles. Loose mod directories retain metadata routing;
the packed-content analysis applies to prepared PACK content.
