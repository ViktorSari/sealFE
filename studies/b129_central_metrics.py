#!/usr/bin/env python3
"""Central 200 µm diagnostics at nominal pressure for extended B129 windows."""
import argparse
import csv
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'models/b129_stage1'))
import active_contact_reader as pp


def facet_gaps(xyz, conn, displacement, al_x, al_z):
    deformed = xyz + displacement
    xy = deformed[conn]
    return np.mean(xy[:, :, 2] - np.interp(xy[:, :, 0], al_x, al_z), axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xplt', type=Path)
    ap.add_argument('feb', type=Path)
    ap.add_argument('--ramp-um', type=float, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--target-mpa', type=float, default=5.0)
    args = ap.parse_args()
    xyz, rubber, bottom, _, al_x, al_z = pp.parse_feb_mesh(args.feb)
    states = pp.parse_states(args.xplt, args.ramp_um, bottom)
    top_z = np.max(xyz[rubber, 2])
    top = np.unique(rubber[np.any(np.isclose(xyz[rubber, 2], top_z), axis=1)])
    top = top[np.isclose(xyz[top, 2], top_z)]
    width = float(al_x[-1] - al_x[0])
    pressures = np.array([pp.reaction_pressure(s, top, width) for s in states])
    assert np.all(np.diff(pressures) >= -1e-5), 'Nonmonotonic nominal pressure'
    centers = xyz[bottom, 0].mean(axis=1)
    central = (centers >= 0) & (centers <= 200)
    if np.count_nonzero(central) != 400:
        raise ValueError('The central 200 µm must have 400 facets')
    reached = np.max(pressures) >= args.target_mpa
    j = int(np.argmin(np.abs(pressures - args.target_mpa))) if reached else len(states)-1
    nearest = states[j]
    g_near = facet_gaps(xyz, bottom, nearest['displacement'], al_x, al_z)[central]
    g_at_target = float('nan')
    if reached:
        hi = int(np.searchsorted(pressures, args.target_mpa))
        lo = max(0, hi-1)
        if hi == lo:
            d = states[hi]['displacement']
        else:
            a = (args.target_mpa - pressures[lo]) / (pressures[hi] - pressures[lo])
            d = states[lo]['displacement'] * (1-a) + states[hi]['displacement'] * a
        g_at_target = float(np.min(facet_gaps(xyz, bottom, d, al_x, al_z)[central]))
    cp = np.asarray(nearest['contact_pressure_raw'])
    side_left = xyz[:, 0] == al_x[0]
    side_right = xyz[:, 0] == al_x[-1]
    row = dict(window_width_um=width, target_pressure_MPa=args.target_mpa,
               reached_5_MPa=int(reached), last_converged_pressure_MPa=float(pressures[-1]),
               nearest_pressure_MPa=float(pressures[j]),
               min_central_gap_nearest_um=float(np.min(g_near)),
               min_central_gap_interpolated_um=g_at_target,
               central_facet_peak_pressure_nearest_MPa=float(np.max(cp[central])),
               max_abs_left_side_ux_um=float(np.max(np.abs(nearest['displacement'][side_left, 0]))),
               max_abs_right_side_ux_um=float(np.max(np.abs(nearest['displacement'][side_right, 0]))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=row.keys()); w.writeheader(); w.writerow(row)
    print(row)

if __name__ == '__main__':
    main()
