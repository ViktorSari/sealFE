"""Reproducible Stage-1 reports. No solver or material changes.

XPLT scalar contact pressure is a four-Gauss-point facet average. Its projected
integral is an equilibrium diagnostic, not exact quadrature of contact forces.
Contact fraction is resolution-limited: pressure-active projected facets, with
an independent piecewise-linear geometric estimate and gap-tolerance study.
"""
import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
import matplotlib.tri as mtri
import numpy as np
from postprocess_results import (parse_feb_mesh, parse_states, reaction_pressure,
                                von_mises, max_principal_sym6, write_pressure_history)

TARGETS = [0.5, 1., 2., 3., 4., 5.]
FLOAT_RE = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'


def save_csv(path, rows):
    with Path(path).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def feb_contact_maxaug(feb_path):
    node = ET.parse(feb_path).getroot().find('.//Contact/contact/maxaug')
    if node is None or node.text is None:
        raise ValueError('Contact maxaug not found in FEB input')
    return int(node.text)


def parse_augmentation_log(log_path, maxaug):
    """Return accepted-step augmentation evidence from a FEBio text log."""
    begin = re.compile(r'beginning time step\s+(\d+)\s*:\s*(' + FLOAT_RE + r')')
    augment = re.compile(r'augmentation\s*#\s*(\d+)')
    multiplier = re.compile(r'D multiplier\s*:\s*(' + FLOAT_RE + r')')
    gap = re.compile(r'maximum gap\s*:\s*(' + FLOAT_RE + r')')
    converged = re.compile(r'converged at time\s*:\s*(' + FLOAT_RE + r')')
    current = None
    accepted = []
    for line in Path(log_path).read_text(errors='replace').splitlines():
        m = begin.search(line)
        if m:
            current = dict(
                step=int(m.group(1)), requested_time=float(m.group(2)),
                max_augmentation=0, last_D_multiplier=float('nan'),
                last_maximum_gap_um=float('nan'))
            continue
        if current is None:
            continue
        m = augment.search(line)
        if m:
            current['max_augmentation'] = max(current['max_augmentation'], int(m.group(1)))
            continue
        m = multiplier.search(line)
        if m:
            current['last_D_multiplier'] = float(m.group(1))
            continue
        m = gap.search(line)
        if m:
            current['last_maximum_gap_um'] = float(m.group(1))
            continue
        m = converged.search(line)
        if m:
            current['converged_time'] = float(m.group(1))
            current['maxaug_limit'] = maxaug
            # FENewtonSolver logs m_naug + 1, while the contact interface tests
            # m_naug >= maxaug. Thus forced acceptance first appears as
            # "augmentation # maxaug+1" in the text log.
            current['maxaug_forced_acceptance'] = current['max_augmentation'] > maxaug
            accepted.append(current)
            current = None
    if not accepted:
        raise ValueError('No accepted FEBio steps found in solver log')
    forced = [r for r in accepted if r['maxaug_forced_acceptance']]
    summary = dict(
        accepted_solver_steps=len(accepted),
        configured_maxaug=maxaug,
        maximum_logged_augmentation=max(r['max_augmentation'] for r in accepted),
        maxaug_forced_acceptance_steps=len(forced),
        first_maxaug_forced_step=forced[0]['step'] if forced else None,
        first_maxaug_forced_time=forced[0]['converged_time'] if forced else None,
        first_maxaug_forced_D_multiplier=forced[0]['last_D_multiplier'] if forced else None,
        first_maxaug_forced_maximum_gap_um=forced[0]['last_maximum_gap_um'] if forced else None,
    )
    return accepted, summary


def bracket(values, target):
    v = np.asarray(values)
    if target < v[0] or target > v[-1]:
        raise ValueError(f'Target {target} outside stored range [{v[0]}, {v[-1]}]')
    j = int(np.searchsorted(v, target, side='left'))
    if j == 0 or v[j] == target:
        return j, j, 0.
    return j-1, j, float((target-v[j-1])/(v[j]-v[j-1]))


def mix_state(states, i, j, f):
    keys = ['time', 'indentation_um', 'displacement', 'stress', 'strain',
            'reaction', 'contact_pressure_raw', 'contact_gap_raw']
    return {k: (1-f)*states[i][k]+f*states[j][k] for k in keys}


def geometry(xyz, conn, st, al_x, al_z):
    q = (xyz + st['displacement'])[conn][:, [0, 3], :]
    dx = q[:, 1, 0]-q[:, 0, 0]
    if np.any(dx <= 0):
        raise ValueError('Folded projected contact facets: single-valued geometry invalid')
    # Sample each facet densely against the unchanged piecewise-linear Al.
    t = np.linspace(0, 1, 17)
    xx = q[:, 0, 0, None]*(1-t)+q[:, 1, 0, None]*t
    zz = q[:, 0, 2, None]*(1-t)+q[:, 1, 2, None]*t
    gaps = zz-np.interp(xx, al_x, al_z)
    def fraction(tol):
        a, b = gaps[:, :-1]-tol, gaps[:, 1:]-tol
        frac = ((a <= 0) & (b <= 0)).astype(float)
        cross = (a <= 0) != (b <= 0)
        ratio = np.divide(-a, b-a, out=np.zeros_like(a), where=(b != a))
        frac[cross] = np.where(a <= 0, ratio, 1-ratio)[cross]
        return float(np.sum(frac.mean(axis=1)*dx)/200.)
    return q.mean(axis=1), dx, gaps, fraction


def metrics(xyz, conn, st, al_x, al_z, pressure):
    centers, dx, gaps, fraction = geometry(xyz, conn, st, al_x, al_z)
    cp = st['contact_pressure_raw'].astype(float)
    proxy = -st['stress'][:len(conn), 2].astype(float)
    true_available = bool(np.any(cp > 1e-8)) or pressure < 1e-8
    # Never silently interpret a zero-only field at nonzero load physically.
    local = cp if true_available else np.maximum(proxy, 0)
    mean = float(np.sum(local*dx)/200.)
    pproxy = float(np.sum(proxy*dx)/200.)
    vm = von_mises(st['stress'])
    ep = max_principal_sym6(st['strain'])
    m = dict(indentation_um=float(st['indentation_um']), nominal_pressure_MPa=float(pressure),
        projected_contact_fraction=float(np.sum(dx[cp > 1e-8])/200.) if true_available else fraction(.01),
        geometric_contact_fraction_0um=fraction(0),
        geometric_contact_fraction_0p01um=fraction(.01),
        geometric_contact_fraction_0p02um=fraction(.02),
        max_local_normal_pressure_MPa=float(local.max()),
        projected_mean_local_pressure_MPa=mean,
        contact_reaction_difference_pct=100*(mean-pressure)/pressure if pressure else 0.,
        max_normal_pressure_proxy_MPa=float(proxy.max()),
        projected_mean_normal_pressure_proxy_MPa=pproxy,
        proxy_reaction_difference_pct=100*(pproxy-pressure)/pressure if pressure else 0.,
        min_geometric_gap_um=float(gaps.min()), max_geometric_gap_um=float(gaps.max()),
        max_FEBio_contact_gap_um=float(st['contact_gap_raw'].max()),
        max_von_Mises_MPa=float(vm.max()), p95_von_Mises_MPa=float(np.percentile(vm,95)),
        max_principal_Lagrange_strain=float(ep.max()),
        p95_principal_Lagrange_strain=float(np.percentile(ep,95)),
        local_pressure_source='FEBio rubber_bottom facet average' if true_available else 'first-layer -sigma_zz PROXY')
    rows = [dict(facet=i+1, x_um=float(c[0]), z_um=float(c[2]), projected_length_um=float(d),
                 contact_pressure_MPa=float(p), first_layer_minus_sigma_zz_MPa=float(s),
                 FEBio_gap_um=float(g), geometric_gap_min_um=float(gmin), geometric_gap_max_um=float(gmax))
            for i,(c,d,p,s,g,gmin,gmax) in enumerate(zip(centers,dx,local,proxy,st['contact_gap_raw'],gaps.min(axis=1),gaps.max(axis=1)))]
    return m, rows


def finish(fig, ax, path, title, equal=True):
    ax.set(xlabel='x [µm]', ylabel='z [µm]', title=title)
    if equal:
        ax.set_aspect('equal', adjustable='box')
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches='tight')
    plt.close(fig)


def mesh_plot(path, xyz, elems, st, al_x, al_z, title, zoom=False):
    xd = xyz if st is None else xyz+st['displacement']
    polygons = xd[elems][:, [0,1,5,4]][:,:,[0,2]]
    fig, ax = plt.subplots(figsize=(12,6))
    ax.add_collection(PolyCollection(polygons,facecolors='none',edgecolors='#536d85',linewidths=.25))
    ax.plot(al_x,al_z,'k-',lw=.8)
    ax.autoscale()
    if zoom:
        ax.set_xlim(20,40); ax.set_ylim(al_z.min()-1, al_z.max()+12)
    finish(fig,ax,path,title)


def stress_plot(path, xyz, elems, st, field, al_x, al_z, label, title):
    # Draw actual deformed elements; recover nodal values only for isolines.
    # Fixed FE connectivity prevents Delaunay triangles bridging exterior voids.
    xd = xyz+st['displacement']
    quads = elems[:,[0,1,5,4]]
    nodes, inv = np.unique(quads, return_inverse=True)
    q = inv.reshape(-1,4)
    flat_inv = inv.ravel()
    nodal = np.bincount(flat_inv, weights=np.repeat(field,4))/np.bincount(flat_inv)
    tri = np.vstack([q[:,[0,1,2]],q[:,[0,2,3]]])
    coords = xd[nodes][:,[0,2]]
    triang = mtri.Triangulation(coords[:,0],coords[:,1],tri)
    fig, ax = plt.subplots(figsize=(13,5))
    pc = PolyCollection(xd[quads][:,:,[0,2]],array=field,cmap='YlOrRd',edgecolors='none',rasterized=True)
    ax.add_collection(pc);ax.autoscale()
    lo,hi=float(field.min()),float(field.max())
    if hi > lo+1e-8:
        cs=ax.tricontour(triang,nodal,levels=np.linspace(lo,hi,10)[1:-1],colors='#503520',linewidths=.45)
        ax.clabel(cs,fontsize=5,fmt='%.2g')
    ax.plot(al_x,al_z,'k-',lw=.8,label='Rigid measured Al')
    bottom=xd[elems[:len(al_x)-1]][:,[0,1]][:,:,[0,2]]
    ax.add_collection(LineCollection(bottom,colors='#176c9c',linewidths=.6))
    ax.set_xlim(al_x[0],al_x[-1]);ax.set_ylim(al_z.min()-1,al_z.max()+25)
    fig.colorbar(pc,ax=ax,pad=.015,label=label)
    finish(fig,ax,path,title+'\nElement-average field; recovered nodal isolines; true x:z scale')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('xplt',type=Path);ap.add_argument('feb',type=Path)
    ap.add_argument('--ramp-um',type=float,required=True);ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--log',type=Path,help='FEBio solver log for augmentation-limit diagnostics')
    args=ap.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    xyz,elems,bottom,bnodes,al_x,al_z=parse_feb_mesh(args.feb)
    states=parse_states(args.xplt,args.ramp_um,bottom)
    rubber=np.unique(elems); top=rubber[np.isclose(xyz[rubber,2],xyz[rubber,2].max())]
    pressures=np.array([reaction_pressure(st,top,200.) for st in states])
    indent=np.array([st['indentation_um'] for st in states])
    if np.any(np.diff(pressures)<-1e-5):
        raise ValueError('Nonmonotonic pressure: automatic interpolation is not justified')
    for st in states:
        if len(st['stress'])!=len(elems) or len(st['contact_pressure_raw'])!=len(bottom):
            raise ValueError('Field length does not match FEM topology')
    write_pressure_history(out/'B129_pressure_history.csv',states,pressures)
    fig,ax=plt.subplots(figsize=(7,4));ax.plot(indent,pressures);ax.set(xlabel='Indentation [µm]',ylabel='Nominal pressure [MPa]',title='B129 converged pressure–indentation history');ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'B129_pressure_indentation.png',dpi=200);plt.close(fig)
    allmetrics=[metrics(xyz,bottom,st,al_x,al_z,p)[0] for st,p in zip(states,pressures)]
    save_csv(out/'B129_state_metrics.csv',allmetrics)
    selected=[];interpolated=[];localrows=[]
    for target in TARGETS+[float(pressures[-1])]:
        final=target==pressures[-1]
        if target>pressures[-1]:continue
        idx=len(states)-1 if final else int(np.argmin(abs(pressures-target)))
        st=states[idx];label='FINAL_STABLE' if final else f'{target:g}MPa'
        selected.append(dict(target_pressure_MPa=label,**allmetrics[idx]))
        _,rows=metrics(xyz,bottom,st,al_x,al_z,pressures[idx])
        localrows.extend([dict(state=label,stored_pressure_MPa=float(pressures[idx]),**r) for r in rows])
        i,j,f=bracket(pressures,target)
        # Interpolate each scalar metric, not a fabricated equilibrium solve.
        row=dict(target_pressure_MPa=target,lower_pressure_MPa=float(pressures[i]),upper_pressure_MPa=float(pressures[j]),interpolation_weight=f)
        for k,v in allmetrics[i].items():
            if isinstance(v,(float,int)):
                row[k]=(1-f)*v+f*allmetrics[j][k]
        interpolated.append(row)
        if final or target==5:
            title=f'B129 {label}: u={st["indentation_um"]:.6f} µm, pnom={pressures[idx]:.6f} MPa'
            for name,field,unit in [('von_Mises',von_mises(st['stress']),'von Mises [MPa]'),('normal',-st['stress'][:,2],'−σzz [MPa]')]:
                stress_plot(out/f'B129_{label}_{name}_stress.png',xyz,elems,st,field,al_x,al_z,unit,title)
            mesh_plot(out/f'B129_{label}_deformed_mesh.png',xyz,elems,st,al_x,al_z,title)
    save_csv(out/'B129_selected_states.csv',selected)
    save_csv(out/'B129_same_pressure_metrics.csv',interpolated)
    save_csv(out/'B129_local_contact_pressure.csv',localrows)
    fig,ax=plt.subplots(figsize=(12,4))
    for label in dict.fromkeys(r['state'] for r in localrows):
        rr=[r for r in localrows if r['state']==label]
        ax.plot([r['x_um'] for r in rr],[r['contact_pressure_MPa'] for r in rr],lw=.8,label=f'{label} (p={rr[0]["stored_pressure_MPa"]:.3f})')
    ax.set(xlabel='Deformed x [µm]',ylabel='Facet-average normal contact pressure [MPa]',title='B129 local contact pressure on rubber_bottom');ax.legend(ncol=3,fontsize=7)
    fig.tight_layout();fig.savefig(out/'B129_local_contact_pressure.png',dpi=200);plt.close(fig)
    mesh_plot(out/'B129_undeformed_full_mesh.png',xyz,elems,None,al_x,al_z,'B129 undeformed rubber mesh and measured rigid Al')
    mesh_plot(out/'B129_undeformed_contact_mesh.png',xyz,elems,None,al_x,al_z,'B129 undeformed contact-region mesh',True)
    # Exact indentation levels via linear interpolation, explicitly not extra solves.
    surface_targets=list(np.arange(0,np.floor(indent[-1]/.5)*.5+.01,.5))
    if abs(surface_targets[-1]-indent[-1])>1e-8:surface_targets.append(float(indent[-1]))
    curve_rows=[];fig,ax=plt.subplots(figsize=(14,4))
    ax.plot(al_x,al_z,'k-',lw=1.1,label='Measured rigid Al')
    for target in surface_targets:
        i,j,f=bracket(indent,target);st=mix_state(states,i,j,f)
        xd=xyz[bnodes]+st['displacement'][bnodes]
        final=abs(target-indent[-1])<1e-8
        ax.plot(xd[:,0],xd[:,2],lw=1 if final else .65,ls='--' if final else '-',label=f'{target:.3f} µm' if final else f'{target:g} µm')
        for n,(x,_,z) in enumerate(xd):
            curve_rows.append(dict(indentation_um=target,point=n,x_um=x,z_um=z,lower_stored_indentation_um=indent[i],upper_stored_indentation_um=indent[j],interpolation_weight=f,is_final_stable=final))
    ax.legend(ncol=5,fontsize=7,loc='upper center',bbox_to_anchor=(.5,-.3))
    finish(fig,ax,out/'B129_rubber_surface_history_0p5um.png',f'Rubber surfaces every 0.5 µm; final u={indent[-1]:.6f} µm, pnom={pressures[-1]:.6f} MPa\nIntermediate curves linearly interpolated between converged states')
    save_csv(out/'B129_rubber_surface_history_0p5um.csv',curve_rows)
    save_csv(out/'B129_rigid_profile.csv',[dict(x_um=x,z_um=z) for x,z in zip(al_x,al_z)])
    summary=dict(last_converged_indentation_um=float(indent[-1]),last_converged_nominal_pressure_MPa=float(pressures[-1]),stored_states=len(states),rubber_elements=len(elems),contact_surface_id=states[-1]['contact_surface_id'],**{k:v for k,v in allmetrics[-1].items() if k not in ['indentation_um','nominal_pressure_MPa']})
    augmentation_note = '- Solver-log augmentation diagnostics were not supplied.'
    if args.log:
        augmentation_rows, augmentation_summary = parse_augmentation_log(
            args.log, feb_contact_maxaug(args.feb))
        save_csv(out/'B129_augmentation_diagnostics.csv', augmentation_rows)
        (out/'B129_augmentation_summary.json').write_text(
            json.dumps(augmentation_summary, indent=2)+'\n')
        summary.update(augmentation_summary)
        if augmentation_summary['maxaug_forced_acceptance_steps']:
            augmentation_note = (
                '- FEBio forced contact acceptance at the configured maxaug limit in '
                f"{augmentation_summary['maxaug_forced_acceptance_steps']} accepted step(s); "
                f"first at solver step {augmentation_summary['first_maxaug_forced_step']} "
                f"(time={augmentation_summary['first_maxaug_forced_time']:.9g}).")
        else:
            augmentation_note = '- No accepted solver step reached the configured maxaug limit.'
    summary['feb_sha256']=hashlib.sha256(args.feb.read_bytes()).hexdigest()
    summary['xplt_sha256']=hashlib.sha256(args.xplt.read_bytes()).hexdigest()
    (out/'B129_final_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'B129_final_summary.txt').write_text('\n'.join(f'{k}={v}' for k,v in summary.items())+'\n')
    (out/'B129_output_limitations.md').write_text('''# Output definitions and limitations
- Model: MR2 C10=0.348 MPa, C01=0.886 MPa. K=850 MPa is an unmeasured placeholder.
- No friction, adhesion, viscosity or profile smoothing. Lateral rollers and uy=0 constrain the layer.
- Contact pressure is the true FEBio rubber_bottom scalar output averaged over four Gauss points per facet. Reported maximum is a **facet-average maximum**, not a resolved pointwise peak.
- XPLT surface names and facet connectivity identify the active surface. The al_top one-pass output is zero and is not used as physical pressure.
- Projected contact fraction uses facets with positive pressure, so partially active facets can be overcounted. Geometry-based fractions at 0/0.01/0.02 µm tolerance are included independently. Neither is an exact integration-point contact-area measurement.
- FEBio contact status counts projected integration points, not necessarily load-bearing points; it is not used as an area fraction.
- First-layer -sigma_zz is retained as a proxy. Its mean and the projected contact-pressure integral are compared against top reaction/200 µm². The facet-average integral is approximate, not exact Gauss quadrature.
- Geometric penetration and FEBio positive contact gap are exported explicitly. Convergence does not prove small penetration or physical validity.
{augmentation_note}
- Same-pressure metrics are linearly interpolated scalar outputs between bracketing converged states; selected-state maps remain actual stored states.
- Surface curves at exact 0.5 µm increments are linearly interpolated. The exact final stable curve is included in the figure and CSV.
- Stress colours are element averages in actual deformed cells. Isolines use nodal averaging on FE connectivity, without extending into the exterior.
- Negative Jacobian identifies a numerical stability limit, not physical rubber failure. Mesh sensitivity and material/compressibility validation remain separate requirements.
'''.format(augmentation_note=augmentation_note))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
