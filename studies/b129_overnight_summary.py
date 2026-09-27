#!/usr/bin/env python3
"""Collect overnight cases, retaining solver status and actual stored pressures."""
import csv
import json
import shutil
import sys
from pathlib import Path

src, out = map(Path, sys.argv[1:3])
out.mkdir(parents=True, exist_ok=True)
rows = []
for folder in sorted(src.iterdir()):
    if not folder.is_dir():
        continue
    def kv(name):
        p = folder / name
        return dict(line.split('=', 1) for line in p.read_text().splitlines() if '=' in line) if p.exists() else {}
    settings = kv('case_settings.txt')
    metrics = kv('B129_final_summary.txt')
    row = {'case': folder.name.removeprefix('B129-overnight-'),
           'solve_outcome': settings.get('solve_outcome', 'unknown'),
           'postprocessing_available': bool(metrics),
           'reached_5MPa': metrics.get('reached_5MPa', 'unknown'),
           'max_pressure_MPa': metrics.get('max_converged_nominal_pressure_MPa', ''),
           'indentation_at_5MPa_um': '',
           'monotonic_pressure': 'unknown'}
    p = folder / 'B129_pressure_history.csv'
    if p.exists():
        with p.open() as f:
            data = list(csv.DictReader(f))
        ps = [float(x['nominal_pressure_MPa']) for x in data]
        us = [float(x['indentation_um']) for x in data]
        row['monotonic_pressure'] = all(b >= a - 1e-7 for a,b in zip(ps,ps[1:]))
        crossings = [(a,b,ua,ub) for a,b,ua,ub in zip(ps,ps[1:],us,us[1:]) if a <= 5 <= b and b > a]
        if crossings and row['monotonic_pressure']:
            a,b,ua,ub = crossings[0]
            row['indentation_at_5MPa_um'] = ua + (5-a)/(b-a)*(ub-ua)
    rows.append(row)
    target = out / folder.name
    target.mkdir(exist_ok=True)
    for name in ['case_settings.txt','B129_final_summary.txt','B129_pressure_history.csv',
                 'B129_selected_states.csv','B129_true_contact_metrics.csv','B129_J_diagnostics.csv']:
        if (folder/name).exists():
            shutil.copy2(folder/name, target/name)
    log = folder/'febio_stdout.txt'
    if log.exists():
        (target/'solver_log_tail.txt').write_text('\n'.join(log.read_text(errors='replace').splitlines()[-100:]))
if not rows:
    raise RuntimeError('No case artifacts downloaded')
with (out/'comparison.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
(out/'comparison.json').write_text(json.dumps(rows,indent=2))
lines=['# B129 overnight study', '',
       'Workflow success is not evidence of solver completion. See solve_outcome and reached_5MPa separately.',
       'Local field metrics use the recorded actual stored pressure; only indentation is interpolated. No extrapolation.',
       'Elastic supports are sensitivity assumptions, not measured fixture stiffness.', '',
       '| Case | Solver | Reached 5 MPa | Max p (MPa) | u at 5 MPa (um) | Monotonic p |',
       '| --- | --- | --- | ---: | ---: | --- |']
for r in rows:
    lines.append('| '+' | '.join(str(r[k]) for k in ['case','solve_outcome','reached_5MPa','max_pressure_MPa','indentation_at_5MPa_um','monotonic_pressure'])+' |')
(out/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
