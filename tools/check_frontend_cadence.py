#!/usr/bin/env python3
"""Reject rewind cadence regressions in paired real-frontend profile captures.

The caller supplies visually verified gameplay runs, first without rewind and
then with it, using the same frontend, content, input and measurement window.
This gate measures elapsed frontend time, not just the core's fast-forward
throughput. It also requires successful captures at the requested cadence;
disabling or silently failing rewind cannot pass.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import csv
import json
from pathlib import Path


def measure(path, start, end, granularity=None):
    if start < 1 or end - start < 600:
        raise ValueError('measure at least 600 gameplay frames after startup')
    with Path(path).open(newline='') as stream:
        rows = [row for row in csv.DictReader(stream)
                if start <= int(row['frame']) <= end]
    runs = [row for row in rows if row['event'] == 'run']
    if [int(row['frame']) for row in runs] != list(range(start, end + 1)):
        raise ValueError('measurement must contain every frame exactly once')
    if any(row['ok'] != '1' for row in runs):
        raise ValueError('failed frame in measurement')
    times = [int(row['begin_ns']) for row in runs]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('frame timestamps must increase')
    captures = [row for row in rows if row['event'] == 'serialize'
                and int(row['frame']) < end]
    if granularity is None:
        if captures:
            raise ValueError('control must have rewind disabled')
    else:
        if granularity < 1:
            raise ValueError('capture granularity must be positive')
        expected = (end - start) // granularity
        if abs(len(captures) - expected) > 1:
            raise ValueError('missing or extra rewind captures')
        if any(row['ok'] != '1' or int(row['written']) <= 0 or
               int(row['written']) > int(row['capacity']) for row in captures):
            raise ValueError('failed or incomplete rewind capture')
        frames = [int(row['frame']) for row in captures]
        if any(b - a != granularity for a, b in zip(frames, frames[1:])):
            raise ValueError('rewind captures do not have the requested cadence')
    if any(row['event'] == 'unserialize' for row in rows):
        raise ValueError('measure outside save/load and reverse-playback actions')
    return dict(fps=(end-start)*1e9/(times[-1]-times[0]),
                frames=end-start, captures=len(captures))


def compare(control, candidate, minimum_fps=59.7, maximum_loss=0.3):
    if not minimum_fps > 0 or not maximum_loss >= 0:
        raise ValueError('invalid cadence limits')
    # A fast-forward control cannot stand in for a refresh-limited run.
    if not minimum_fps <= control['fps'] <= 60.3:
        raise ValueError('control is not running at the expected 60 Hz cadence')
    loss = control['fps'] - candidate['fps']
    if candidate['fps'] < minimum_fps or candidate['fps'] > 60.3 or loss > maximum_loss:
        raise ValueError('rewind cadence regression: %.3f fps, loss %.3f fps' %
                         (candidate['fps'], loss))
    return dict(control=control, rewind=candidate, fps_loss=loss, passed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--start', required=True, type=int)
    parser.add_argument('--end', required=True, type=int)
    parser.add_argument('--granularity', type=int, default=10)
    args = parser.parse_args()
    result = compare(measure(args.control, args.start, args.end),
                     measure(args.candidate, args.start, args.end, args.granularity))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
