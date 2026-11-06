"""Check own-profile movement without a target, viewport edges and waits.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import unittest

import test_historical_wander as wander


class FreeWanderContracts(wander.WanderContracts):
    fixture = Path(__file__).with_name('fixtures') / 'profile-free-wander-contracts.json'
    routine = 'common_try_wandercompletely'


if __name__ == '__main__':
    unittest.main()
