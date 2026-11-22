# Source provenance

This distribution offers selectable OpenBOR profiles from pinned source
snapshots with a shared libretro platform layer. `src/pin.json` records the
upstream repository, full commit IDs and dependency archive SHA-256 hashes.
Each engine has an `ANYBOR-SOURCE.json` manifest identifying the original and
distributed hash of every retained upstream file. This makes the port's modifications
distinguishable from upstream code without importing upstream Git history.
The shared port, frontend glue and build tooling are included as source.

The v3.0 7369-dev, v3.0 7391-dev and v3.0 7420-dev profiles adapt
[`c0c8afe5dbdf5325e65e503ec0547f9b1e5c10eb`](https://github.com/DCurrent/openbor/tree/c0c8afe5dbdf5325e65e503ec0547f9b1e5c10eb/engine),
[`8d809a5d13f9c77bc2a3e1cacfa4c5bf8aca4266`](https://github.com/DCurrent/openbor/tree/8d809a5d13f9c77bc2a3e1cacfa4c5bf8aca4266/engine), and
[`8a180f22934d574d0159693951d0339eedc53f8a`](https://github.com/DCurrent/openbor/tree/8a180f22934d574d0159693951d0339eedc53f8a/engine)
on the 7533 source tree. The three original revisions share the
[upstream BSD grant](LICENSES/OpenBOR-7142.txt). Their source-defined behavior
is documented in [historical profiles](docs/HISTORICAL_PROFILES.md#7369-7391-and-7420).

The v3.0 6997-dev, v3.0 7039-dev and v3.0 7091-dev profiles adapt
[`203d148433ac86ac51c131564d14c2465f8af80b`](https://github.com/DCurrent/openbor/tree/203d148433ac86ac51c131564d14c2465f8af80b/engine),
[`be46a55822e19750728ef271b7bebd80ccd678f1`](https://github.com/DCurrent/openbor/tree/be46a55822e19750728ef271b7bebd80ccd678f1/engine), and
[`8ad68746200339af2a9006bd9f489f8df0d26347`](https://github.com/DCurrent/openbor/tree/8ad68746200339af2a9006bd9f489f8df0d26347/engine)
on the 7142 source tree. The three revisions carry the same
[upstream BSD grant](LICENSES/OpenBOR-7533.txt). The original source and
ported behavior are documented in [historical profiles](docs/HISTORICAL_PROFILES.md#6997-7039-and-7091).

The v3.0 6453-dev profile adapts upstream
[`2664325c0bd301332f27df3f4bd68cd64d20aa2b`](https://github.com/DCurrent/openbor/tree/2664325c0bd301332f27df3f4bd68cd64d20aa2b/engine)
on the 6391 source tree. Its 6412-dev control follows
[`d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8`](https://github.com/DCurrent/openbor/tree/d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8/engine).
Both upstream revisions retain the same BSD grant and author notice as
the 6391 source. The attack mapper adaptation and source coverage are
documented in [historical profiles](docs/HISTORICAL_PROFILES.md).

The official v4.0 7530, 7555, 7556 and 7735 profiles identify their own source
revisions in `src/pin.json`. The 7556 package's engine has an embedded 7555
label; its verified package identity and global-configuration implementation
correspond to source revision `fc92d78dbf8110c8af10702233ba4f022d6bdc50`.
Profile adaptations retain source copyright notices and the applicable BSD terms.
The imported flash and music interfaces retain their [7735 source license](LICENSES/OpenBOR-profile-7735-BSD-3-Clause.txt); source-import records preserve their own original hashes.

Profiles v3.0 4161-dev, v3.0 4183-dev and v3.0 4213 identify their original
source revisions in `src/pin.json`:

| Profile | Source revision |
|---|---|
| v3.0 4161-dev | [`baab46acb6545655d104f5a717364766890089f2`](https://github.com/DCurrent/openbor/tree/baab46acb6545655d104f5a717364766890089f2/engine) |
| v3.0 4183-dev | [`f1a221a00eda2ed45b779dc6df165a5e93db0773`](https://github.com/DCurrent/openbor/tree/f1a221a00eda2ed45b779dc6df165a5e93db0773/engine) |
| v3.0 4213 | [`7d343fe28e53b9eb3066693392cc0a1353afdde0`](https://github.com/DCurrent/openbor/tree/7d343fe28e53b9eb3066693392cc0a1353afdde0/engine) |

The 4183 and 4213 source aliases and profile limits are described in
[historical profiles](docs/HISTORICAL_PROFILES.md#forward-profiles-through-4213).
Imported mathematical helpers and allocation declarations carry
their own 4183 source hashes in `ANYBOR-SOURCE.json`. The retained
[early profile license](LICENSES/OpenBOR-profile-4153-BSD-3-Clause.txt) contains
the same copyright notice, BSD conditions and disclaimer as that revision's root grant.
Original per-file notices remain authoritative for adapted source and fixtures.

## Profiles from 4283 to 4431

Each of these profiles has two commit histories at the same build count
with identical complete source trees. The first column of commit links
matches the original source revision recorded in `src/pin.json`.

| Profile | Original source | Equivalent source |
|---|---|---|
| v3.0 4283-dev | [`d138a14a304f83c48fbe0aded4edf483b15ff64e`](https://github.com/DCurrent/openbor/tree/d138a14a304f83c48fbe0aded4edf483b15ff64e/engine) | [`247b809e697434c9f244570375fdc0550b4ed62e`](https://github.com/DCurrent/openbor/tree/247b809e697434c9f244570375fdc0550b4ed62e/engine) |
| v3.0 4287 | [`5d5c4d22a0ef7e4913fa5540263421aa8ecba5a8`](https://github.com/DCurrent/openbor/tree/5d5c4d22a0ef7e4913fa5540263421aa8ecba5a8/engine) | [`9fb86c1871870e741f810382e00929fc89b80da8`](https://github.com/DCurrent/openbor/tree/9fb86c1871870e741f810382e00929fc89b80da8/engine) |
| v3.0 4316 | [`ba7bbb797f2e016dc496ee2c1154740907301894`](https://github.com/DCurrent/openbor/tree/ba7bbb797f2e016dc496ee2c1154740907301894/engine) | [`d745e9e0e50f78baf76b5f100bb0d241d82fd691`](https://github.com/DCurrent/openbor/tree/d745e9e0e50f78baf76b5f100bb0d241d82fd691/engine) |
| v3.0 4317 | [`2a0c6096356e7f2231a298799bcc51d36ffde899`](https://github.com/DCurrent/openbor/tree/2a0c6096356e7f2231a298799bcc51d36ffde899/engine) | [`cac52c55f30043eb65493757b4971355f1e39da8`](https://github.com/DCurrent/openbor/tree/cac52c55f30043eb65493757b4971355f1e39da8/engine) |
| v3.0 4320 | [`f2d878dbedd740cbee36fa509a8a40d00f0834b7`](https://github.com/DCurrent/openbor/tree/f2d878dbedd740cbee36fa509a8a40d00f0834b7/engine) | [`92123f7bd5be50ef30fbfadeeed3cf92a11496fc`](https://github.com/DCurrent/openbor/tree/92123f7bd5be50ef30fbfadeeed3cf92a11496fc/engine) |
| v3.0 4321 | [`6e452af0c56d7639f75f39c776c6c36c9fcf97fc`](https://github.com/DCurrent/openbor/tree/6e452af0c56d7639f75f39c776c6c36c9fcf97fc/engine) | [`44746415630f5d185a45d4e6c1e82e9bb4f9956e`](https://github.com/DCurrent/openbor/tree/44746415630f5d185a45d4e6c1e82e9bb4f9956e/engine) |
| v3.0 4328 | [`7dc955cb343c1e543be01da7d7544117831aacb1`](https://github.com/DCurrent/openbor/tree/7dc955cb343c1e543be01da7d7544117831aacb1/engine) | [`f5089b72ef8465538bea397cc45bbaa69569ee0f`](https://github.com/DCurrent/openbor/tree/f5089b72ef8465538bea397cc45bbaa69569ee0f/engine) |
| v3.0 4330 | [`13b5f3941555a3b2175726912e0697d1bd1965c5`](https://github.com/DCurrent/openbor/tree/13b5f3941555a3b2175726912e0697d1bd1965c5/engine) | [`1a3d5d9806b0e1ba7fd3d5fdaa86b30012d9a583`](https://github.com/DCurrent/openbor/tree/1a3d5d9806b0e1ba7fd3d5fdaa86b30012d9a583/engine) |
| v3.0 4332 | [`b4b7b358836bfa6c8f654b4a6c8ec2391a8e1de3`](https://github.com/DCurrent/openbor/tree/b4b7b358836bfa6c8f654b4a6c8ec2391a8e1de3/engine) | [`352345377ade0322580001f489d807f202f1189d`](https://github.com/DCurrent/openbor/tree/352345377ade0322580001f489d807f202f1189d/engine) |
| v3.0 4334 | [`1791420e7f7b336e75ea2e101210c72040199260`](https://github.com/DCurrent/openbor/tree/1791420e7f7b336e75ea2e101210c72040199260/engine) | [`60845a0bd54229f5feb2b20aaba007c34e51783b`](https://github.com/DCurrent/openbor/tree/60845a0bd54229f5feb2b20aaba007c34e51783b/engine) |
| v3.0 4336 | [`09b33973a311c6b9d1bf51f0c1bb02ea7552a594`](https://github.com/DCurrent/openbor/tree/09b33973a311c6b9d1bf51f0c1bb02ea7552a594/engine) | [`64bd97aeda1f391d19a3f798455f912bb7a33d0b`](https://github.com/DCurrent/openbor/tree/64bd97aeda1f391d19a3f798455f912bb7a33d0b/engine) |
| v3.0 4342 | [`7d7859b2936a89800cc0643aa8604dffe973e5ad`](https://github.com/DCurrent/openbor/tree/7d7859b2936a89800cc0643aa8604dffe973e5ad/engine) | [`1d86260b92761e6b2362a648465d927323d0f1e7`](https://github.com/DCurrent/openbor/tree/1d86260b92761e6b2362a648465d927323d0f1e7/engine) |
| v3.0 4343 | [`1216fa3ddab599af2ae58dc5af5c8b8acac39099`](https://github.com/DCurrent/openbor/tree/1216fa3ddab599af2ae58dc5af5c8b8acac39099/engine) | [`c4b606f11c3f134a17353edb036671cff63824e8`](https://github.com/DCurrent/openbor/tree/c4b606f11c3f134a17353edb036671cff63824e8/engine) |
| v3.0 4344 | [`fa53ebb66d8f366303727414982b40187639a19e`](https://github.com/DCurrent/openbor/tree/fa53ebb66d8f366303727414982b40187639a19e/engine) | [`472efb790f9cf840496ed39bd8ee8d6465973724`](https://github.com/DCurrent/openbor/tree/472efb790f9cf840496ed39bd8ee8d6465973724/engine) |
| v3.0 4346 | [`5234311c7899617eb64844f61e6ed72c17c074fb`](https://github.com/DCurrent/openbor/tree/5234311c7899617eb64844f61e6ed72c17c074fb/engine) | [`c19a8507421afcf1b68d43480140b8928f5eace6`](https://github.com/DCurrent/openbor/tree/c19a8507421afcf1b68d43480140b8928f5eace6/engine) |
| v3.0 4349 | [`2df760d73101928088bf40987207472f0c4e86e6`](https://github.com/DCurrent/openbor/tree/2df760d73101928088bf40987207472f0c4e86e6/engine) | [`23508162152685ba27e2dd23710250b3a8c353e2`](https://github.com/DCurrent/openbor/tree/23508162152685ba27e2dd23710250b3a8c353e2/engine) |
| v3.0 4352 | [`dbc6f6aadea001a2c4518eca11fccb2f191d7117`](https://github.com/DCurrent/openbor/tree/dbc6f6aadea001a2c4518eca11fccb2f191d7117/engine) | [`a3e4ddce42aef088c3cb1404e15b4f4d632ae17e`](https://github.com/DCurrent/openbor/tree/a3e4ddce42aef088c3cb1404e15b4f4d632ae17e/engine) |
| v3.0 4366 | [`c9933b364a07ace66bf83b4c175b8e4fac402d83`](https://github.com/DCurrent/openbor/tree/c9933b364a07ace66bf83b4c175b8e4fac402d83/engine) | [`c356310c12dfa38bab657dd998ea392da5e6f873`](https://github.com/DCurrent/openbor/tree/c356310c12dfa38bab657dd998ea392da5e6f873/engine) |
| v3.0 4367-dev | [`34b50501f3a7809b89397c64b6a87ad951e30c44`](https://github.com/DCurrent/openbor/tree/34b50501f3a7809b89397c64b6a87ad951e30c44/engine) | [`7dc10ec5ee7a82b27b2170233190b2398a4047bd`](https://github.com/DCurrent/openbor/tree/7dc10ec5ee7a82b27b2170233190b2398a4047bd/engine) |
| v3.0 4377 | [`fcb58c55802df1403f0ae2071b0cbd7eb4b593d7`](https://github.com/DCurrent/openbor/tree/fcb58c55802df1403f0ae2071b0cbd7eb4b593d7/engine) | [`34bbe1b4793427330a1649d2270f0ef046c0da67`](https://github.com/DCurrent/openbor/tree/34bbe1b4793427330a1649d2270f0ef046c0da67/engine) |
| v3.0 4379 | [`8a1f6ebd6649e8cccb236df00dff568f840e32c2`](https://github.com/DCurrent/openbor/tree/8a1f6ebd6649e8cccb236df00dff568f840e32c2/engine) | [`315a9cc479fda2092bfbdd081d3d035ae006950d`](https://github.com/DCurrent/openbor/tree/315a9cc479fda2092bfbdd081d3d035ae006950d/engine) |
| v3.0 4383 | [`3e3c5215dd223fc02408f046bd46108594a47505`](https://github.com/DCurrent/openbor/tree/3e3c5215dd223fc02408f046bd46108594a47505/engine) | [`ea1f02d1dae4f91ea5edfdc5f0d37cd9274bc28a`](https://github.com/DCurrent/openbor/tree/ea1f02d1dae4f91ea5edfdc5f0d37cd9274bc28a/engine) |
| v3.0 4385 | [`ff2d6d2b272317e3a8bc5ab6f3aba11064093b12`](https://github.com/DCurrent/openbor/tree/ff2d6d2b272317e3a8bc5ab6f3aba11064093b12/engine) | [`a8a2d02e95cad594131bee691fdb96e560112bee`](https://github.com/DCurrent/openbor/tree/a8a2d02e95cad594131bee691fdb96e560112bee/engine) |
| v3.0 4387 | [`a3ba57902e7af0eec23c714ff5f2036c869c198b`](https://github.com/DCurrent/openbor/tree/a3ba57902e7af0eec23c714ff5f2036c869c198b/engine) | [`ef02914273cfe1bcc93d8b2fa337d1c17343fe1f`](https://github.com/DCurrent/openbor/tree/ef02914273cfe1bcc93d8b2fa337d1c17343fe1f/engine) |
| v3.0 4389 | [`e3d50a51ae0a4af78a080acc013c7e400db0938c`](https://github.com/DCurrent/openbor/tree/e3d50a51ae0a4af78a080acc013c7e400db0938c/engine) | [`341d0a8e7ccd106e0dcd4f6faabfc8feed2f0be3`](https://github.com/DCurrent/openbor/tree/341d0a8e7ccd106e0dcd4f6faabfc8feed2f0be3/engine) |
| v3.0 4390 | [`c3e6fafef9a7857a66b4205e5f51523f112191b6`](https://github.com/DCurrent/openbor/tree/c3e6fafef9a7857a66b4205e5f51523f112191b6/engine) | [`776cacd7a7f8d503eb6cc2221cbfc94ceb9282f5`](https://github.com/DCurrent/openbor/tree/776cacd7a7f8d503eb6cc2221cbfc94ceb9282f5/engine) |
| v3.0 4393 | [`1854f84851e3b9ba8c4f4c01b0124673b2dd3ee6`](https://github.com/DCurrent/openbor/tree/1854f84851e3b9ba8c4f4c01b0124673b2dd3ee6/engine) | [`e5b0a9171e8f219df8969af955430034a1682f05`](https://github.com/DCurrent/openbor/tree/e5b0a9171e8f219df8969af955430034a1682f05/engine) |
| v3.0 4394 | [`28cec6d4467f06293b2990f15beb5707c4cfb6eb`](https://github.com/DCurrent/openbor/tree/28cec6d4467f06293b2990f15beb5707c4cfb6eb/engine) | [`dae4d82464fe3c5290f843b3aaeba2ee7f944211`](https://github.com/DCurrent/openbor/tree/dae4d82464fe3c5290f843b3aaeba2ee7f944211/engine) |
| v3.0 4396 | [`3b5f7aaf8c42b5e15623c01222d70f4dc0e9d8fb`](https://github.com/DCurrent/openbor/tree/3b5f7aaf8c42b5e15623c01222d70f4dc0e9d8fb/engine) | [`f6e83311eae5b5e4b983c43bf1ce3c31f402b387`](https://github.com/DCurrent/openbor/tree/f6e83311eae5b5e4b983c43bf1ce3c31f402b387/engine) |
| v3.0 4400 | [`6d1a0e85ba6abba3010b1a8bb0847f8f66ed087c`](https://github.com/DCurrent/openbor/tree/6d1a0e85ba6abba3010b1a8bb0847f8f66ed087c/engine) | [`24111e9fae36903be1f8011c55682163d49141e0`](https://github.com/DCurrent/openbor/tree/24111e9fae36903be1f8011c55682163d49141e0/engine) |
| v3.0 4401 | [`b09f9f80522c05e988c385e2deeb7c58638c0c6a`](https://github.com/DCurrent/openbor/tree/b09f9f80522c05e988c385e2deeb7c58638c0c6a/engine) | [`0065caef9c6ff3f4c2ce4dee54a92964a4c36c20`](https://github.com/DCurrent/openbor/tree/0065caef9c6ff3f4c2ce4dee54a92964a4c36c20/engine) |
| v3.0 4403 | [`40cc7b440cadcaf80b4098ae9974e1299052d02a`](https://github.com/DCurrent/openbor/tree/40cc7b440cadcaf80b4098ae9974e1299052d02a/engine) | [`21ee31311f8128be4754757e40749d8d843fbe86`](https://github.com/DCurrent/openbor/tree/21ee31311f8128be4754757e40749d8d843fbe86/engine) |
| v3.0 4404-dev | [`1b34823401b491dee519d0e52649a17bc3c8bf8a`](https://github.com/DCurrent/openbor/tree/1b34823401b491dee519d0e52649a17bc3c8bf8a/engine) | [`ce9e5564caa3c6ba29bc73952ccff643f20a3caa`](https://github.com/DCurrent/openbor/tree/ce9e5564caa3c6ba29bc73952ccff643f20a3caa/engine) |
| v3.0 4406 | [`0fb4dcc40339339b940e28d2efef1a33aa726f64`](https://github.com/DCurrent/openbor/tree/0fb4dcc40339339b940e28d2efef1a33aa726f64/engine) | [`11f20095afc4c01aba080a6bca9aea4f885dd7e0`](https://github.com/DCurrent/openbor/tree/11f20095afc4c01aba080a6bca9aea4f885dd7e0/engine) |
| v3.0 4411 | [`6ee2a2c01b6b859724ea4766767a49338915a786`](https://github.com/DCurrent/openbor/tree/6ee2a2c01b6b859724ea4766767a49338915a786/engine) | [`c63e6a508aa5e31123899cdf0ebb7097c5db3331`](https://github.com/DCurrent/openbor/tree/c63e6a508aa5e31123899cdf0ebb7097c5db3331/engine) |
| v3.0 4412 | [`216efbaede246f11f449510fd47c344241814a2e`](https://github.com/DCurrent/openbor/tree/216efbaede246f11f449510fd47c344241814a2e/engine) | [`33cef9bd3f9bb43b7500d3e6761cb1b1f186fedc`](https://github.com/DCurrent/openbor/tree/33cef9bd3f9bb43b7500d3e6761cb1b1f186fedc/engine) |
| v3.0 4413 | [`c63e07e02ba065a9dbb4dee040a59e1fa8c87a74`](https://github.com/DCurrent/openbor/tree/c63e07e02ba065a9dbb4dee040a59e1fa8c87a74/engine) | [`1630a0dacdbb834680411478dc04c14ae3ec36e0`](https://github.com/DCurrent/openbor/tree/1630a0dacdbb834680411478dc04c14ae3ec36e0/engine) |
| v3.0 4414 | [`dffd708be7c8583116f72c5677a8b46d9aa62031`](https://github.com/DCurrent/openbor/tree/dffd708be7c8583116f72c5677a8b46d9aa62031/engine) | [`e111458fadcc6ae7ccd09860ad59fa11a70ac5f7`](https://github.com/DCurrent/openbor/tree/e111458fadcc6ae7ccd09860ad59fa11a70ac5f7/engine) |
| v3.0 4417 | [`4c7f7728f14d8f85cc0248432716633abeed72fc`](https://github.com/DCurrent/openbor/tree/4c7f7728f14d8f85cc0248432716633abeed72fc/engine) | [`5f535606d18c5bbf91450b6eaa8d16bb64f32b9b`](https://github.com/DCurrent/openbor/tree/5f535606d18c5bbf91450b6eaa8d16bb64f32b9b/engine) |
| v3.0 4419 | [`f1e88cb51e634a1658ba00478a6c934fa7263666`](https://github.com/DCurrent/openbor/tree/f1e88cb51e634a1658ba00478a6c934fa7263666/engine) | [`fb63cf08b1cc78baa263e89f4171a577e63d00c1`](https://github.com/DCurrent/openbor/tree/fb63cf08b1cc78baa263e89f4171a577e63d00c1/engine) |
| v3.0 4420 | [`2e5668a4811af62c0c79cbb6d624bc121ba2210c`](https://github.com/DCurrent/openbor/tree/2e5668a4811af62c0c79cbb6d624bc121ba2210c/engine) | [`1f27c2fbf60c6d34f538a53f37bb4c01f14eafd3`](https://github.com/DCurrent/openbor/tree/1f27c2fbf60c6d34f538a53f37bb4c01f14eafd3/engine) |
| v3.0 4421-dev | [`b34a35d7e0d740865f955da8effbf9872447ac86`](https://github.com/DCurrent/openbor/tree/b34a35d7e0d740865f955da8effbf9872447ac86/engine) | [`ca9b5c358792d34c5da056c8f2361f68bad3400f`](https://github.com/DCurrent/openbor/tree/ca9b5c358792d34c5da056c8f2361f68bad3400f/engine) |
| v3.0 4423 | [`dd4b6b8390ec8a8ec6bd17adee07b8d1ca163635`](https://github.com/DCurrent/openbor/tree/dd4b6b8390ec8a8ec6bd17adee07b8d1ca163635/engine) | [`d5451f6588ac896a444e8ce28928c583d1b967a7`](https://github.com/DCurrent/openbor/tree/d5451f6588ac896a444e8ce28928c583d1b967a7/engine) |
| v3.0 4424 | [`a474558c1e4b5872a87b89763808842990f788bb`](https://github.com/DCurrent/openbor/tree/a474558c1e4b5872a87b89763808842990f788bb/engine) | [`52a6fc65131f1e223b3ac8f051dd5005cf8855f6`](https://github.com/DCurrent/openbor/tree/52a6fc65131f1e223b3ac8f051dd5005cf8855f6/engine) |
| v3.0 4426 | [`deaa7dd15e3ef7c0e2b90925311aa68c9c501b1a`](https://github.com/DCurrent/openbor/tree/deaa7dd15e3ef7c0e2b90925311aa68c9c501b1a/engine) | [`08f21d06917078066f567c29c0de9358be15c952`](https://github.com/DCurrent/openbor/tree/08f21d06917078066f567c29c0de9358be15c952/engine) |
| v3.0 4429 | [`133af494330ba0bdea991311dfea4edc518f2641`](https://github.com/DCurrent/openbor/tree/133af494330ba0bdea991311dfea4edc518f2641/engine) | [`cd4cf7f762bc279daa651a9a3c5e53ba0ef21d51`](https://github.com/DCurrent/openbor/tree/cd4cf7f762bc279daa651a9a3c5e53ba0ef21d51/engine) |
| v3.0 4430 | [`40b29e34d584bdf4bacd4440dd6948c130c559f2`](https://github.com/DCurrent/openbor/tree/40b29e34d584bdf4bacd4440dd6948c130c559f2/engine) | [`dbbb9a7ee5bd8955c98460c19431bf7a8066f5a2`](https://github.com/DCurrent/openbor/tree/dbbb9a7ee5bd8955c98460c19431bf7a8066f5a2/engine) |
| v3.0 4431 | [`21ba2305dc68764f47c7297e7bb3e78cb2547d62`](https://github.com/DCurrent/openbor/tree/21ba2305dc68764f47c7297e7bb3e78cb2547d62/engine) | [`d9a0c590e2a300eeebba59ee042be91ad1d86218`](https://github.com/DCurrent/openbor/tree/d9a0c590e2a300eeebba59ee042be91ad1d86218/engine) |

The early Android random provider uses an independently written, engine-owned
state machine for the platform's additive random sequence. Its factual
algorithm and sequence controls are checked against Android's
[rand interface](https://github.com/aosp-mirror/platform_bionic/blob/main/libc/bionic/rand.cpp),
[random implementation](https://github.com/aosp-mirror/platform_bionic/blob/main/libc/upstream-netbsd/common/lib/libc/stdlib/random.c)
and [native library tests](https://github.com/aosp-mirror/platform_bionic/blob/main/tests/stdlib_test.cpp).
The port does not import those platform implementation files.

[ENGINE_EXECUTABLES.json](docs/ENGINE_EXECUTABLES.json) records verified engine
program and installable-package SHA-256 and imohash values, builds, variants, byte sizes and available
source package/member references. The lookup table contains these factual
identities, not executable code. Verification checks archive members' sizes and
CRCs, directly preserved packages' manifest hashes, executable/package formats
and local SHA-256. Package identity and embedded version labels are separate
facts; supported discrepancies are recorded in the catalog. The catalog digest
binds the published projection to its verified input. The built-in catalog contains
no game, PAK or game-content identities. User-authored external imohash engine
settings follow [content configuration](docs/CONTENT_CONFIGURATION.md); they are
separate from the engine catalog. No executable is run for identification. Imohash values use standard sampling parameters and are calculated
only after each complete executable payload matches its recorded SHA-256.
Different executables can share a sampled imohash value.

Verified modified engine entries retain exact acquisition details privately.
Their public records identify the provenance receipt by SHA-256 and omit
private package/member names. These receipt digests document verification;
only the engine executable identities participate in engine selection.

Files imported from an upstream revision into another physical baseline have a
`source_import` entry with their own upstream commit, repository and original
SHA-256. The baseline hash remains separate. Provenance-only revisions in
`src/pin.json` identify source inputs without adding selectable profiles.
Restored graphics code from revision `b38a0a6dd38dc5b638e895183f4ed4df469300ae`
retains the [original no-sale license](LICENSES/OpenBOR-3400.txt); the mathematical
controls in `tools/fixtures/early_inverse_math.c`, `early_water_geometry_math.c`
and `early_model_remaining_math.c` retain their own original source notices.
BSD-3-Clause covers only the original adapters and modifications.
The imported media sources retain
their original copyright blocks and the complete [profile license](LICENSES/OpenBOR-profile-4153-BSD-3-Clause.txt);
the SBOM identifies the selected source revision and its embedded component terms.

Engine imports in the public Git history include the portable circle and
fixed-width endian adaptations from their first appearance. Their inventories
retain the original upstream hashes separately from the distributed hashes;
these adapted imports are not unmodified upstream snapshots.

[MODIFICATIONS.md](MODIFICATIONS.md) explains the current differences from each
pinned OpenBOR build and the shared port's additions. Its generated per-engine
inventories link modified files to their original source and explain their
changes. The circle and endian adaptations are present from the first public
engine imports; the replaced implementations are not distributed.
The manifests also record omitted upstream engine files and their hashes;
unchanged files are identified without modification claims. These records are
documentation; the included sources build directly.

The source snapshots originate from the [OpenBOR repository](https://github.com/DCurrent/openbor).
The 3400 and 3741 source snapshots retain their original no-sale licenses.
Logical profile source revisions, dates and physical source trees are recorded
in `src/pin.json`. The 3020-dev profile identifies the first revision with
preserved engine code, commit `473ee64634faa77b2ac4302f71987d600774c199`
(2011-02-23). Official release profiles in the same range identify their own
source commits; the shared 3400 source tree retains its original license.
Each included snapshot keeps its own license; later license grants do not
replace the terms of earlier source.

The circle rasterizer in `src/port/libretro/anybor_circle.h` is a new integer
geometry implementation for this port. It enumerates symmetric integer
coordinates using the circle equation and clips them to the target surface.
The engine wrappers preserve the original pixel-writing interface.
`anybor_adpcm.c` implements IMA ADPCM's predictor, quantizer adaptation and
nibble packing for the OpenBOR audio API. Its algorithm is described by the
[IMA format reference linked from RFC 3551](https://www.rfc-editor.org/rfc/rfc3551#section-4.5.1).
`anybor_endian.h` supplies fixed-width integer conversions for the engine APIs,
replacing the historical SDL-derived header and its assumption that an x86-64
`long` is 64 bits (which is false on Windows).
These original replacement implementations carry retrodiv's BSD-3-Clause notice.

Upstream implementation comments and credits are retained exactly as received,
including unresolved or tentative author credits; no author is invented or
reassigned by the port. As background on the engine's licensing lineage, the
recovered OpenBOR `List.c` at
commit [`473ee64634faa77b2ac4302f71987d600774c199`](https://github.com/DCurrent/openbor/blob/473ee64634faa77b2ac4302f71987d600774c199/engine/source/scriptlib/List.c) contains the OpenBOR Team 2004–2011 copyright and its BSD
license reference, preceding the later list revisions. Existing copyrights,
license conditions and named contributors are preserved.

Original AnyBOR code and retrodiv's original modifications are licensed under
BSD-3-Clause, as scoped in [LICENSES.md](LICENSES.md). A modification notice does not
replace the license of the surrounding upstream file. The original engine
licenses and third-party notices remain unchanged, and the former combined BSD
notice is retained separately for its existing grants and attributions.

Alex Pankratov's halloc headers explicitly grant a BSD license by reference
to `opensource.org/licenses/bsd-license.php`, the historical URL for the
[three-clause BSD license](https://opensource.org/license/bsd-3-clause).
The [author's repository](https://github.com/apankrat/halloc) confirms that
licensing, including the 1.2.1 history. The accompanying `LICENSE` supplies
the referenced terms locally with the original 2004–2010 copyright.

The WebM helpers are the files bundled by the pinned OpenBOR releases;
notices are collected from every included version. The miniz amalgamation's
internal copyright blocks, libco's backend notices, libvpx's `PATENTS` and
the x86inc assembly notice are included in the license dossier. Compiler
runtime license texts are pinned to their source URLs and hashes in
`LICENSES/runtime-sources.json`. These reference texts cover the runtime
families described in `LICENSES.md`; each build's tool versions are recorded
in its receipt.

The unused libvpx motion-estimation fixtures under
`build_debug/non_greedy_mv_test_files/` are omitted from the source distribution.
They include two photographic frames stored as numeric text and four auxiliary
data files. AnyBOR builds only the decoders and disables libvpx's unit tests;
its own runtime checks generate their test content. The local dependency
manifest records this omission; the upstream archive pin remains unchanged.

`SOURCES.json` inventories the exported source tree. `SBOM.spdx.json` maps
the included packages and license expressions. `make check` validates the
inventory and notices. `make release` verifies that its binary, notices and
sources match the build receipt, then checks the contents of the resulting
ZIP. Builds need only this directory, an installed compiler/toolchain and
the host build utilities listed in `README.md`; they do not download code.

The generic buffer transform compiler/interpreter is original AnyBOR work.
It provides only generic buffer execution and source compilation.


The v3.0 6330-lns-010g profile reconstructs the modified 6330 LNS v0.10g engine
with LNS Enhancements by Hechelion and Gonzalo MVP, from the initial
[AveyondFly/openbor-fflns source](https://github.com/AveyondFly/openbor-fflns/commit/cfb4f3a676613714757d4539275482f7c323d6ad)
uploaded by yizhigai. The adapted portions cover model loading/unloading,
character selection, score/settings records, menus, combat, model/script
properties, HUD colours and cached I/O. The baseline excludes later uploader
changes. OpenBOR's BSD-3-Clause licence and original OpenBOR Team copyright
notices apply and are retained. Attribution identifies the contributors;
it does not imply endorsement or complete binary equivalence.
The original modified-source BSD grant is retained in
`LICENSES/OpenBOR-profile-6330-lns-010g-BSD-3-Clause.txt`; source regression excerpts
retain their associated notices in `tools/fixtures/lns-6330-NOTICE.txt`.
The independent PACK 1.1 container adapter uses the published format and
volume lookup rules documented in the later
[container source](https://github.com/AveyondFly/openbor-fflns/blob/5cac65237db9b1409a0b7ee4a1a64d6507834915/engine/source/gamelib/packfile.c);
it reads unchanged member bytes without importing that later engine baseline.

The v3.0 6391-mod profile reconstructs Kratus's experimental build described
in the [published discussion](https://www.chronocrash.com/forum/threads/npc-walking-backwards-how-to-solve-it.6933/).
Its implementation is based on published descriptions and official code;
the unpublished build's sources were unavailable and were not used. The
four-ID history and selection-menu escape adapt official commits
`0824ff3e`, `e4f0605d`, `46e2bbfb` and `e10dd3f1`, whose complete identifiers
are recorded in `src/pin.json`. Its contract excludes the `backtotitle` alias.
OpenBOR's existing copyrights and license terms apply. Attribution identifies
the experimental build's author; it does not imply endorsement or complete
binary equivalence. The source/profile mapping and platform limits are in
[HISTORICAL_PROFILES](docs/HISTORICAL_PROFILES.md).

The v3.0 6392-dev profile is an explicitly documented reconstruction. Its
behavioral specification is the author's
[published test-build discussion](https://www.chronocrash.com/forum/threads/openbor-test-build-6392.4936/).
The multihit history and menu behavior were adapted from upstream
[PR 229](https://github.com/DCurrent/openbor/pull/229), including commits
`0824ff3e`, `e4f0605d`, `4462a156`, `46e2bbfb` and `e10dd3f1`.
The source manifest records their complete identifiers. Existing OpenBOR
copyrights and license terms continue to apply; the original unpublished test
source tree is not asserted to have been recovered.

The divergent v3.0 7086-dev and v3.0 7123-dev contracts are adapted from
[revision 7a45a2215a0cc12c1085d92e7b210a827ea552c2](https://github.com/DCurrent/openbor/tree/7a45a2215a0cc12c1085d92e7b210a827ea552c2/engine)
and [revision f5261e7cb97786909276c0b87f8f9f63504d2844](https://github.com/DCurrent/openbor/tree/f5261e7cb97786909276c0b87f8f9f63504d2844/engine).
Their exact references are recorded with the selected profiles in `src/pin.json`.
Retained OpenBOR implementations and adaptations keep their upstream copyright
and BSD terms; added original helpers carry separate BSD-3-Clause notices.

## ZIP cache identity

`src/glue/anybor_imohash.h` implements standard imohash defaults: complete input
below 128 KiB, otherwise 16 KiB samples at the beginning, midpoint and end,
MurmurHash3 x64_128 with seed zero, and unsigned LEB128 file-size encoding.
Sampling and encoding follow Jim Kalafut's MIT implementation at commit
`611245ae8069800035b185d9d43f36829885ab82`. MurmurHash3 follows Peter Scott's
C port at commit `dae94be0c0f54a399d23ea6cbe54bca5a4e93ce4`, retaining Austin
Appleby's public-domain dedication. The C adaptation is copied from retrodiv's
AnyGM implementation at commit `31d5666d72559136327b3165bbaca3b81759965b`,
with local names and a miniz archive-reader adapter. Known-answer test vectors
retain Jim Kalafut's MIT notice. Full notices accompany source and binaries in
`LICENSES/imohash.txt` and `LICENSES/murmur3.txt`.
`tools/content_key.py` implements the same sampled selector in Python under MIT,
with the same algorithm credits; its vectors are checked against the core.


The pinned libarchive 3.8.11 source archive supplies the standalone RAR5 reader.
Only the RAR5 format and unfiltered input are registered; static linking selects
its reachable closure. External codec/crypto libraries and command-line tools
are disabled. Source pruning removes examples, test media and unused programs,
while retaining build templates and original notices. Per-file manifests bind
the archive and distributed sources. BLAKE2's offered CC0-1.0 option is selected;
other libarchive sources retain their own BSD terms. Build-support scripts keep
their individual terms and exceptions, independently of the runtime grant.
