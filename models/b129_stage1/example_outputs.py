#!/usr/bin/env python3
"""Example B129 PNG/GIF/CSV outputs from an existing, converged-state XPLT."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import matplotlib.tri as mtri
import numpy as np
from PIL import Image

import active_contact_reader as pp


def nominal_pressure(st, xyz, rubber_conn, width):
    top_z = np.max(xyz[rubber_conn, 2])
    top = np.unique(rubber_conn[np.any(np.isclose(xyz[rubber_conn, 2], top_z), axis=1)])
    top = top[np.isclose(xyz[top, 2], top_z)]
    return pp.reaction_pressure(st, top, width)


def surface_points(xyz, bottom_conn, displacement):
    ids = np.r_[bottom_conn[0, 0], bottom_conn[:, 3]]
    return (xyz + displacement)[ids][:, [0, 2]]


def at_indent(states, target):
    u = np.asarray([s["indentation_um"] for s in states])
    if target <= u[0]:
        return states[0]["displacement"], float(u[0]), False
    if target >= u[-1]:
        return states[-1]["displacement"], float(u[-1]), False
    j = int(np.searchsorted(u, target))
    if np.isclose(u[j], target, atol=1e-7):
        return states[j]["displacement"], float(u[j]), False
    a = (target-u[j-1])/(u[j]-u[j-1])
    return (1-a)*states[j-1]["displacement"]+a*states[j]["displacement"], float(target), True


def contact_segments(xyz, bottom_conn, state):
    deformed = xyz + state["displacement"]
    xz = deformed[bottom_conn[:, [0, 3]], :][:, :, [0, 2]]
    cp = np.asarray(state["contact_pressure_raw"], dtype=float)
    if cp.shape != (len(bottom_conn),):
        raise ValueError("Contact pressure does not match rubber_bottom facets")
    return xz, cp


def true_contact_length(xz, cp, al_x, al_z, threshold=1e-8):
    """Union of active projected facet intervals, measured along rigid profile."""
    x0, x1 = xz[:, 0, 0], xz[:, 1, 0]
    if np.any(x1 <= x0):
        raise ValueError("Folded contact surface")
    intervals = sorted((max(al_x[0], a), min(al_x[-1], b))
                       for a, b, active in zip(x0, x1, cp > threshold)
                       if active and min(al_x[-1], b) > max(al_x[0], a))
    ds = np.hypot(np.diff(al_x), np.diff(al_z))
    cumulative = np.r_[0., np.cumsum(ds)]
    def arc(x):
        return np.interp(x, al_x, cumulative)
    merged = []
    for a, b in intervals:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return float(sum(arc(b)-arc(a) for a, b in merged)), float(cumulative[-1])


def save_contact_plot(path, csv_path, states, xyz, bottom_conn, al_x, al_z, pressure):
    max_pressure = pressure[id(states[-1])]
    # More resolution during the first stages of contact; include exact final.
    targets = max_pressure*np.array([.01, .04, .12, .35, 1.])
    selected = [min(states, key=lambda s: abs(pressure[id(s)]-p)) for p in targets]
    maximum = max(float(np.max(s["contact_pressure_raw"])) for s in selected)
    fig, axes = plt.subplots(10, 1, figsize=(16, 15), sharey=True)
    bounds = [(al_x[0], (al_x[0]+al_x[-1])/2),
              ((al_x[0]+al_x[-1])/2, al_x[-1])]
    zmin = min(np.min(al_z), min(np.min(surface_points(xyz,bottom_conn,s["displacement"])[:,1]) for s in selected))
    zmax = max(np.max(al_z), max(np.max(surface_points(xyz,bottom_conn,s["displacement"])[:,1]) for s in selected))
    with csv_path.open("w", newline="") as f:
        w=csv.writer(f)
        w.writerow(["target_nominal_pressure_MPa","stored_nominal_pressure_MPa",
                    "stored_indentation_um","max_facet_contact_pressure_MPa"])
        for target,st in zip(targets,selected):
            w.writerow([target,pressure[id(st)],st["indentation_um"],
                        np.max(st["contact_pressure_raw"])])
    for row, (target, st) in enumerate(zip(targets, selected)):
        xz, cp = contact_segments(xyz, bottom_conn, st)
        for j,(left,right) in enumerate(bounds):
            ax=axes[2*row+j]
            ax.plot(al_x, al_z, color="0.35", lw=.8, label="Measured Al")
            active = cp > 1e-8
            lines = LineCollection(xz[active], cmap="inferno", norm=plt.Normalize(0, maximum),
                                   linewidths=2.5)
            lines.set_array(cp[active])
            ax.add_collection(lines)
            ax.plot(xz[:, 0, 0], xz[:, 0, 1], lw=.45, color="#3579a8", alpha=.7)
            ax.set_aspect("equal", adjustable="box")
            ax.set_ylabel("z [µm]")
            ax.set_xlim(left,right)
            ax.set_ylim(zmin-.3,zmax+.3)
            ax.set_title("Target %.3f MPa | state %.3f MPa, u=%.3f µm | x=%.0f–%.0f µm" %
                         (target,pressure[id(st)],st["indentation_um"],left,right),fontsize=9)
    axes[-1].set_xlabel("x [µm]")
    fig.subplots_adjust(left=.08,right=.85,top=.97,bottom=.05,hspace=.55)
    cax=fig.add_axes([.89,.20,.022,.60])
    fig.colorbar(lines, cax=cax, label="FEBio facet-average normal contact pressure [MPa]")
    fig.savefig(path, dpi=170)
    plt.close(fig)


def save_contact_curve(path, csv_path, states, xyz, bottom_conn, al_x, al_z, pressure):
    rows = []
    for st in states:
        xz, cp = contact_segments(xyz, bottom_conn, st)
        length, full = true_contact_length(xz, cp, al_x, al_z)
        xwidth = xz[:, 1, 0]-xz[:, 0, 0]
        recovered = float(np.dot(cp, xwidth)/(al_x[-1]-al_x[0]))
        p = pressure[id(st)]
        if p > 1e-5 and abs(recovered-p)/p > .02:
            raise ValueError("FEBio contact pressure fails reaction balance")
        rows.append((st["indentation_um"], p, length, full, length/full,
                     np.max(cp), recovered))
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["indentation_um","nominal_pressure_MPa","active_Al_profile_arc_um",
                    "measured_Al_profile_arc_um","contact_length_ratio",
                    "max_facet_contact_pressure_MPa","pressure_integral_MPa"])
        w.writerows(rows)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot([r[1] for r in rows], [r[4] for r in rows], color="#17698c", lw=1.7)
    ax.set(xlabel="Nominal pressure [MPa]", ylabel="Contact arc / measured Al profile arc [-]",
           xlim=(0,None), ylim=(0,1.02), title="B129 contact evolution")
    ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(path,dpi=200);plt.close(fig)


def save_surface_history(path, csv_path, states, xyz, bottom_conn, al_x, al_z):
    end = states[-1]["indentation_um"]
    targets = list(np.arange(0, end+1e-8, .5))
    if not np.isclose(targets[-1], end):
        targets.append(end)
    curves = []
    with csv_path.open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["target_indent_um","x_um","rubber_z_um","visual_interpolation"])
        for u in targets:
            d, actual, interp = at_indent(states,u)
            curve=surface_points(xyz,bottom_conn,d)
            curves.append((actual,curve,interp))
            w.writerows((actual,x,z,int(interp)) for x,z in curve)
    fig,axes=plt.subplots(4,1,figsize=(15,11),sharey=True)
    cm=plt.get_cmap("viridis")
    bounds=np.linspace(al_x[0],al_x[-1],5)
    for ax,left,right in zip(axes,bounds[:-1],bounds[1:]):
        ax.plot(al_x,al_z,color="black",lw=1.2,label="Measured rigid Al")
        for u,curve,interp in curves:
            ax.plot(curve[:,0],curve[:,1],color=cm(u/end),lw=.95)
        ax.set(xlim=(left,right),xlabel="x [µm]",ylabel="z [µm]",
               title="Measured profile: x=%.0f–%.0f µm"%(left,right))
        ax.set_aspect("equal",adjustable="box")
    axes[0].legend(fontsize=8,loc="upper right")
    fig.suptitle("Rubber contact surface at 0.5 µm indentation increments",fontsize=13)
    fig.subplots_adjust(top=.94,bottom=.17,hspace=.7)
    bar=fig.add_axes([.20,.095,.60,.016])
    fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0,end),cmap=cm),
                 cax=bar,orientation="horizontal",label="Indentation [µm]; final exact state included")
    fig.text(.5,.018,"Intermediate curves are interpolated between converged states for display only.",
             ha="center",fontsize=8)
    fig.savefig(path,dpi=200);plt.close(fig)


def save_mesh(path, xyz, rubber_conn, bottom_conn, al_x, al_z, states, pressure):
    # Thin extrusion: use the front y-plane's lower x-z quadrilateral edges.
    faces=rubber_conn[:,[0,1,5,4]]
    def panel(ax, coords, zoom, caption):
        q=coords[faces][:,:,[0,2]]
        edges=np.stack((q[:,[0,1]],q[:,[1,2]],q[:,[2,3]],q[:,[3,0]])).reshape(-1,2,2)
        ax.add_collection(LineCollection(edges,color="#4d7c99",linewidths=.25))
        ax.plot(al_x,al_z,color="#333",lw=.6)
        ax.set_xlim(al_x[0],al_x[-1])
        if zoom:
            ax.set_ylim(np.min(al_z)-1,np.max(al_z)+12)
        else:
            ax.set_ylim(min(np.min(al_z),np.min(coords[:,2]))-1,
                        max(np.max(al_z),np.max(coords[:,2]))+1)
        ax.set_aspect("equal",adjustable="box")
        ax.set(xlabel="x [µm]",ylabel="z [µm]",title=caption)
    chosen=min(states,key=lambda s:abs(pressure[id(s)]-5.0))
    fig,axes=plt.subplots(5,1,figsize=(15,18))
    panel(axes[0],xyz,False,"Undeformed full mesh")
    for i,(left,right) in enumerate([(al_x[0],(al_x[0]+al_x[-1])/2),
                                     ((al_x[0]+al_x[-1])/2,al_x[-1])]):
        panel(axes[1+i],xyz,True,"Undeformed contact mesh, x=%.0f–%.0f µm"%(left,right))
        axes[1+i].set_xlim(left,right)
        panel(axes[3+i],xyz+chosen["displacement"],True,
              "Deformed mesh at %.3f MPa, x=%.0f–%.0f µm"%(pressure[id(chosen)],left,right))
        axes[3+i].set_xlim(left,right)
    fig.tight_layout();fig.savefig(path,dpi=200);plt.close(fig)
    pts=xyz[rubber_conn]
    dx=np.diff(al_x)
    dz=np.diff(al_z)
    stats={"rubber_hex8_elements":len(rubber_conn),"contact_facets":len(bottom_conn),
           "nominal_x_pitch_um":float(np.median(dx)),
           "rubber_first_layer_um":float(np.median(np.abs(pts[:len(bottom_conn),4,2]-pts[:len(bottom_conn),0,2]))),
           "rubber_height_um":float(np.max(xyz[rubber_conn,2])-np.min(xyz[rubber_conn,2])),
           "out_of_plane_um":1.0,"measured_profile_arc_um":float(np.sum(np.hypot(dx,dz)))}
    return stats


def save_fields(out,xyz,rubber_conn,bottom_conn,states,pressure,al_x,al_z):
    selected=[min(states,key=lambda s:abs(s["indentation_um"]-u))
              for u in np.linspace(.2,1,5)*states[-1]["indentation_um"]]
    for label,fn,cmap in [
        ("von_Mises",lambda s:pp.von_mises(s["stress"]),"viridis"),
        ("minus_sigma_zz",lambda s:-s["stress"][:,2],"magma"),
        ("max_principal_Lagrange_strain",lambda s:pp.max_principal_sym6(s["strain"]),"cividis")]:
        fig,axes=plt.subplots(5,1,figsize=(15,22),sharex=True,sharey=True)
        values=[fn(s) for s in selected]
        lo,hi=min(float(np.min(v)) for v in values),max(float(np.max(v)) for v in values)
        for ax,st,v in zip(axes,selected,values):
            centers=pp.element_centers_deformed(xyz,rubber_conn,st["displacement"])
            current=xyz+st["displacement"]
            bottom=surface_points(xyz,bottom_conn,st["displacement"])
            top_z=np.max(xyz[rubber_conn,2])
            top=np.unique(rubber_conn[np.isclose(xyz[rubber_conn,2],top_z)
                                      & np.isclose(xyz[rubber_conn,1],0)])
            top=top[np.argsort(current[top,0])]
            top_curve=current[top][:,[0,2]]
            if len(bottom)!=len(top_curve) or len(bottom)!=len(bottom_conn)+1:
                raise ValueError("Unexpected rubber boundary discretization")
            # Constant extension of the adjacent element-center field to its
            # boundary, only to close the plotted contour at the mesh edge.
            edge_ids=np.minimum(np.arange(len(bottom)),len(bottom_conn)-1)
            points=np.vstack((centers[:,[0,2]],bottom,top_curve))
            field=np.r_[v,v[edge_ids],v[-len(bottom_conn):][edge_ids]]
            tri=mtri.Triangulation(points[:,0],points[:,1])
            cf=ax.tricontourf(tri,field,levels=np.linspace(lo,hi,16),cmap=cmap)
            ax.tricontour(tri,field,levels=np.linspace(lo,hi,9)[1:-1],
                          colors="white",linewidths=.35,alpha=.7)
            ax.plot(*bottom.T,color="black",lw=.6)
            ax.plot(*top_curve.T,color="black",lw=.6)
            ax.plot(al_x,al_z,color="black",lw=.45)
            ax.set_aspect("equal",adjustable="box")
            ax.set_ylabel("z [µm]")
            ax.set_title("u = %.3f µm  |  p_nom = %.3f MPa"%(st["indentation_um"],pressure[id(st)]),fontsize=10)
        axes[-1].set_xlabel("x [µm]")
        axes[-1].set_xlim(al_x[0],al_x[-1])
        axes[-1].set_ylim(np.min(al_z)-2,np.max(xyz[rubber_conn,2])+2)
        fig.colorbar(cf,ax=axes,label=label+(" [MPa]" if label!="max_principal_Lagrange_strain" else " [-]"),
                     shrink=.65,pad=.01)
        fig.savefig(out/("B129_"+label+"_five_levels.png"),dpi=180,bbox_inches="tight")
        plt.close(fig)


def save_gif(path,states,xyz,bottom_conn,al_x,al_z):
    end=float(states[-1]["indentation_um"])
    targets=list(np.arange(0,end+1e-8,.1))
    if not np.isclose(targets[-1],end):
        targets.append(end)
    frames=[]
    ylo=min(np.min(al_z),np.min(surface_points(xyz,bottom_conn,states[-1]["displacement"])[:,1]))-.5
    yhi=max(np.max(al_z),np.max(surface_points(xyz,bottom_conn,states[0]["displacement"])[:,1]))+.5
    for u in targets:
        d,actual,interp=at_indent(states,u)
        curve=surface_points(xyz,bottom_conn,d)
        fig,axes=plt.subplots(2,1,figsize=(12,5.5))
        for ax,(left,right) in zip(axes,[(al_x[0],(al_x[0]+al_x[-1])/2),
                                         ((al_x[0]+al_x[-1])/2,al_x[-1])]):
            ax.plot(al_x,al_z,color="#444",lw=1.1,label="Measured Al")
            ax.plot(curve[:,0],curve[:,1],color="#167fa2",lw=1.5,label="Rubber contact surface")
            ax.set(xlim=(left,right),ylim=(ylo,yhi),xlabel="x [µm]",ylabel="z [µm]")
            ax.set_aspect("equal",adjustable="box")
        axes[0].legend(loc="upper right",fontsize=7)
        fig.suptitle("B129 indentation: %.3f µm%s"%(actual," (visual interpolation)" if interp else ""))
        fig.canvas.draw()
        arr=np.asarray(fig.canvas.buffer_rgba())[...,:3].copy()
        frames.append(Image.fromarray(arr))
        plt.close(fig)
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=140,loop=0,
                   optimize=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("xplt",type=Path);p.add_argument("feb",type=Path)
    p.add_argument("--ramp-um",type=float,default=4.2);p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    xyz,rubber_conn,bottom_conn,_,al_x,al_z=pp.parse_feb_mesh(args.feb)
    root=ET.parse(args.feb).getroot()
    rubber=next(m for m in root.findall("./Material/material") if m.get("name")=="rubber")
    k_mpa=float(rubber.findtext("k"))
    domain=next(d for d in root.findall("./MeshDomains/SolidDomain") if d.get("name")=="rubber")
    augmented=domain.findtext("laugon")=="1"
    states=pp.parse_states(args.xplt,args.ramp_um,bottom_conn)
    width=float(al_x[-1]-al_x[0])
    pressure={id(st):nominal_pressure(st,xyz,rubber_conn,width) for st in states}
    save_contact_plot(out/"B129_contact_line_five_levels.png",out/"B129_contact_line_levels.csv",
                      states,xyz,bottom_conn,al_x,al_z,pressure)
    save_contact_curve(out/"B129_contact_length_ratio.png",out/"B129_contact_length_ratio.csv",states,xyz,bottom_conn,al_x,al_z,pressure)
    save_surface_history(out/"B129_surface_evolution.png",out/"B129_surface_evolution.csv",states,xyz,bottom_conn,al_x,al_z)
    stats=save_mesh(out/"B129_mesh_panels.png",xyz,rubber_conn,bottom_conn,al_x,al_z,states,pressure)
    with (out/"B129_model_mesh_summary.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["quantity","value","status"])
        for k,v in stats.items():w.writerow([k,v,"from FEB geometry"])
        for k,v,status in [
            ("material","MR2 C10=0.348 MPa, C01=0.886 MPa","fitted input"),
            ("K_MPa",k_mpa,"numerical augmentation parameter, not measured"),
            ("volume_augmentation",int(augmented),"three-field element-averaged volume"),
            ("volume_augmentation_atol",domain.findtext("atol") or "off","three-field domain"),
            ("rubber_side_x","both roller boundaries","boundary condition"),
            ("rubber_y","uy=0","boundary condition"),
            ("rubber_top_z","prescribed displacement","boundary condition"),
            ("rigid_Al","fully fixed","boundary condition"),
            ("contact_penalty_MPa_per_um",0.30,"numerical contact parameter"),
            ("contact_method","one-pass sliding elastic, augmented Lagrange","friction coefficient 0"),
            ("max_external_increment_um",0.1,"adaptive cutbacks allowed"),
        ]:w.writerow([k,v,status])
    save_fields(out,xyz,rubber_conn,bottom_conn,states,pressure,al_x,al_z)
    save_gif(out/"B129_indentation_0p1um.gif",states,xyz,bottom_conn,al_x,al_z)
    print("Wrote",len(list(out.iterdir())),"example files; last converged",states[-1]["indentation_um"],pressure[id(states[-1])])


if __name__=="__main__":
    main()
