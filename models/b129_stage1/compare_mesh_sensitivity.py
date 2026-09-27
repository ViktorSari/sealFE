#!/usr/bin/env python3
"""Compare B129 mesh cases at identical nominal pressures.

Each case must be a completed Stage-1 report directory, or its
B129_same_pressure_metrics.csv file. The reference case is the denominator for
signed percentage differences. This script does not mix mesh and model-form
changes and does not use each case's unrelated stability endpoint.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


TARGETS = (0.5, 1.0, 2.0, 3.0, 4.0, 5.0)
METRICS = (
    'indentation_um',
    'projected_contact_fraction',
    'max_local_normal_pressure_MPa',
    'max_geometric_penetration_um',
    'max_FEBio_contact_gap_um',
    'max_von_Mises_MPa',
    'p95_von_Mises_MPa',
    'max_principal_Lagrange_strain',
    'p95_principal_Lagrange_strain',
)


def case_path(value):
    label, sep, raw = value.partition('=')
    if not sep or not label or not raw:
        raise argparse.ArgumentTypeError('case must be LABEL=PATH')
    path = Path(raw)
    if path.is_dir():
        path = path / 'B129_same_pressure_metrics.csv'
    return label, path


def read_case(path):
    rows = {}
    with path.open(newline='') as f:
        for row in csv.DictReader(f):
            target = float(row['target_pressure_MPa'])
            if target not in TARGETS:
                continue
            values = {k: float(row[k]) for k in METRICS if k != 'max_geometric_penetration_um'}
            values['max_geometric_penetration_um'] = max(0.0, -float(row['min_geometric_gap_um']))
            rows[target] = values
    missing = sorted(set(TARGETS)-set(rows))
    if missing:
        raise ValueError(f'{path}: missing pressure targets {missing}')
    return rows


def write_csv(path, rows, fields):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', action='append', type=case_path, required=True,
                    help='mesh label and report directory/CSV: LABEL=PATH')
    ap.add_argument('--reference', default='reference')
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args()
    cases = dict(args.case)
    if len(cases) != len(args.case):
        raise ValueError('Duplicate mesh-case label')
    if args.reference not in cases:
        raise ValueError(f'Reference case {args.reference!r} was not supplied')
    data = {label: read_case(path) for label, path in cases.items()}
    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)

    long_rows = []
    wide_rows = []
    for target in TARGETS:
        for metric in METRICS:
            ref = data[args.reference][target][metric]
            wide = {'target_pressure_MPa': target, 'metric': metric,
                    'reference_case': args.reference, 'reference_value': ref}
            for label in cases:
                value = data[label][target][metric]
                diff = 100.0*(value-ref)/ref if ref != 0 else math.nan
                long_rows.append(dict(target_pressure_MPa=target, case=label,
                                      reference_case=args.reference, metric=metric,
                                      value=value, reference_value=ref,
                                      difference_pct=diff))
                wide[f'{label}_value'] = value
                wide[f'{label}_difference_pct'] = diff
            wide_rows.append(wide)
    write_csv(out/'B129_mesh_sensitivity_long.csv', long_rows,
              list(long_rows[0]))
    write_csv(out/'B129_mesh_sensitivity_wide.csv', wide_rows,
              list(wide_rows[0]))

    groups = [
        ('B129_mesh_sensitivity_contact.png', (
            ('indentation_um', 'Indentation [µm]'),
            ('projected_contact_fraction', 'Projected contact fraction [-]'),
            ('max_local_normal_pressure_MPa', 'Facet-average pressure max [MPa]'),
            ('max_geometric_penetration_um', 'Max geometric penetration [µm]'))),
        ('B129_mesh_sensitivity_stress_strain.png', (
            ('max_von_Mises_MPa', 'Max von Mises [MPa]'),
            ('p95_von_Mises_MPa', 'P95 von Mises [MPa]'),
            ('max_principal_Lagrange_strain', 'Max principal strain [-]'),
            ('p95_principal_Lagrange_strain', 'P95 principal strain [-]'))),
    ]
    for filename, panels in groups:
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex='col',
                                 constrained_layout=True)
        for ax, (metric, ylabel) in zip(axes.flat, panels):
            for label in cases:
                ax.plot(TARGETS, [data[label][p][metric] for p in TARGETS],
                        marker='o', ms=3, label=label)
            ax.set(ylabel=ylabel)
            ax.set_xticks(TARGETS)
            ax.grid(alpha=.25)
        for ax in axes[-1]:
            ax.set_xlabel('Nominal pressure [MPa]', labelpad=8)
        axes[0,0].legend()
        fig.suptitle(f'B129 mesh sensitivity; reference={args.reference}; identical pressures')
        fig.savefig(out/filename, dpi=200); plt.close(fig)


if __name__ == '__main__':
    main()
