"""Check drawing masks using the shared sprite pixel and route oracles.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import copy
import hashlib
import json

from contract_fixtures import load_contract_fixture
import test_sprite_raster as raster


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-sprite-mask-contracts.json'


class ModernSpriteMaskTests(raster.SpriteRasterTests):
    @classmethod
    def fixture_data(cls):
        data = load_contract_fixture(FIXTURE)
        shared = load_contract_fixture(raster.FIXTURE)
        data['palettes'] = shared['palettes']
        data['contracts'] = {}
        for name, entry in data['shared_contracts'].items():
            original = shared['contracts'][entry['source']]
            digest = hashlib.sha256(json.dumps(original, sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest()
            if digest != entry['source_sha256']:
                raise ValueError('Shared raster case inventory changed')
            cases = copy.deepcopy(original)
            for index, pixels in entry['pixel_overrides'].items():
                index = int(index)
                if not 0 <= index < len(cases) or len(pixels) != 120:
                    raise ValueError('Bounded complete raster pixel override required')
                cases[index]['expected'] = pixels
            data['contracts'][name] = cases
        return data


if __name__ == '__main__':
    import unittest
    unittest.main()
