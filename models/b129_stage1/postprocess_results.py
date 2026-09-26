#!/usr/bin/env python3
"""Post-process the B129 FEBio normal-contact search run.

Outputs use the last converged XPLT state even when the solver subsequently
terminates at a negative-Jacobian stability limit.

Generated outputs:
- pressure history
- selected load-state metrics at 0.5...5 MPa plus final stable state
- final deformed von-Mises stress field with iso-stress contour lines
- final deformed normal-stress field with iso-stress contour lines
- true-scale rubber bottom-surface history every 0.5 um indentation
- CSV containing those surface-history curves

The FEBio contact-pressure and contact-gap surface variables are zero for the
current one-pass sliding-elastic setup. Therefore projected contact activity is
reconstructed from the deformed rubber/rigid-profile geometry, and local normal
pressure is represented by -sigma_zz in the first rubber element layer. The
spatial mean of this proxy is checked against the top-reaction nominal pressure.
"""
from __future__ import annotations

import argparse
import csv
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np

STATE = 0x02000000
STATE_HEADER = 0x02010000
STATE_TIME = 0x02010002
STATE_DATA = 0x02020000
NODE_DATA = 0x02020300
DOMAIN_DATA = 0x02020400
SURFACE_DATA = 0x02020500
VAR_ID = 0x02020002
VAR_DATA = 0x02020003


def chunks(data: bytes, start: int, end: int):
    pos = start
    while pos < end:
        tag, length = struct.unpack_from("<II", data, pos)
        nxt = pos + 8 + length
        if nxt > end:
            raise ValueError("Invalid XPLT chunk length")
        yield tag, pos + 8, nxt
        pos = nxt
    if pos != end:
        raise ValueError("Invalid XPLT chunk boundary")


def child(data: bytes, start: int, end: int, tag: int):
    for item in chunks(data, start, end):
        if item[0] == tag:
            return item[1:]
    raise ValueError(f"Missing XPLT chunk {tag:#x}")


def raw_var(data: bytes, var_chunk):
    _, begin, end = var_chunk
    i0, _ = child(data, begin, end, VAR_ID)
    var_id = struct.unpack_from("<I", data, i0)[0]
    d0, d1 = child(data, begin, end, VAR_DATA)
    region_id, nbytes = struct.unpack_from("<II", data, d0)
    if d0 + 8 + nbytes > d1:
        raise ValueError("Invalid variable payload length")
    arr = np.frombuffer(data, dtype="<f4", count=nbytes // 4, offset=d0 + 8)
    return var_id, region_id, arr


def parse_feb_mesh(feb_path: Path):
    root = ET.parse(feb_path).getroot()
    mesh = root.find("Mesh")
    if mesh is None:
        raise ValueError("FEBio Mesh section not found")

    nodes = {}
    for block in mesh.findall("Nodes"):
        for n in block:
            nodes[int(n.attrib["id"])] = np.array(
                [float(v) for v in n.text.split(",")], dtype=float
            )
    max_id = max(nodes)
    xyz = np.zeros((max_id, 3), dtype=float)
    for nid, c in nodes.items():
        xyz[nid - 1] = c

    domains = {e.attrib.get("name"): e for e in mesh.findall("Elements")}
    rubber_block = domains.get("rubber")
    if rubber_block is None:
        raise ValueError("Rubber element domain not found")
    rubber_conn = np.array(
        [[int(v) - 1 for v in e.text.split(",")] for e in rubber_block], dtype=int
    )

    surfaces = {s.attrib.get("name"): s for s in mesh.findall("Surface")}
    bottom = surfaces.get("rubber_bottom")
    al_top = surfaces.get("al_top")
    if bottom is None or al_top is None:
        raise ValueError("Required contact surfaces not found")

    bottom_conn = np.array(
        [[int(v) - 1 for v in q.text.split(",")] for q in bottom], dtype=int
    )
    bottom_node_ids = np.array(
        [bottom_conn[0, 0]] + [q[3] for q in bottom_conn], dtype=int
    )

    al_ids = []
    for q in al_top:
        vals = [int(v) - 1 for v in q.text.split(",")]
        al_ids.extend([vals[0], vals[1]])
    al_ids = np.unique(al_ids)
    order = np.argsort(xyz[al_ids, 0])
    al_ids = al_ids[order]

    return (
        xyz,
        rubber_conn,
        bottom_conn,
        bottom_node_ids,
        xyz[al_ids, 0],
        xyz[al_ids, 2],
    )


def parse_states(xplt_path: Path, ramp_um: float):
    data = xplt_path.read_bytes()
    if data[:4] != b"BEF\0":
        raise ValueError("Not a FEBio XPLT file")

    states = []
    for state_chunk in chunks(data, 4, len(data)):
        if state_chunk[0] != STATE:
            continue
        _, begin, end = state_chunk

        h0, h1 = child(data, begin, end, STATE_HEADER)
        t0, _ = child(data, h0, h1, STATE_TIME)
        time = struct.unpack_from("<f", data, t0)[0]

        d0, d1 = child(data, begin, end, STATE_DATA)

        n0, n1 = child(data, d0, d1, NODE_DATA)
        node_vars = list(chunks(data, n0, n1))
        if len(node_vars) < 2:
            raise ValueError("Expected displacement and reaction-force variables")
        _, _, disp_flat = raw_var(data, node_vars[0])
        _, _, force_flat = raw_var(data, node_vars[1])

        dom0, dom1 = child(data, d0, d1, DOMAIN_DATA)
        domain_vars = list(chunks(data, dom0, dom1))
        if len(domain_vars) < 2:
            raise ValueError("Expected stress and Lagrange-strain variables")
        _, _, stress_flat = raw_var(data, domain_vars[0])
        _, _, strain_flat = raw_var(data, domain_vars[1])

        # Read/validate surface variables even though the present FEBio
        # formulation exports zero contact pressure/gap values.
        surf0, surf1 = child(data, d0, d1, SURFACE_DATA)
        surface_vars = list(chunks(data, surf0, surf1))
        if len(surface_vars) < 3:
            raise ValueError("Expected contact pressure, gap and status variables")
        _, _, cp = raw_var(data, surface_vars[0])
        _, _, gap = raw_var(data, surface_vars[1])
        _, _, status = raw_var(data, surface_vars[2])

        states.append(
            {
                "time": float(time),
                "indentation_um": float(time * ramp_um),
                "displacement": disp_flat.reshape(-1, 3),
                "reaction": force_flat.reshape(-1, 3),
                "stress": stress_flat.reshape(-1, 6),
                "strain": strain_flat.reshape(-1, 6),
                "contact_pressure_raw": cp.astype(float),
                "contact_gap_raw": gap.astype(float),
                "contact_status_raw": status.astype(float),
            }
        )

    if not states:
        raise ValueError("No converged XPLT states found")
    return states


def von_mises(s):
    sxx, syy, szz, sxy, syz, sxz = s.T
    return np.sqrt(
        0.5
        * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy**2 + syz**2 + sxz**2)
    )


def max_principal_sym6(v):
    out = np.empty(len(v), dtype=float)
    for i, (xx, yy, zz, xy, yz, xz) in enumerate(v):
        M = np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]], dtype=float)
        out[i] = np.linalg.eigvalsh(M)[-1]
    return out


def reaction_pressure(state, top_node_ids, nominal_area_um2):
    return float(
        state["reaction"][top_node_ids, 2].sum(dtype=float) / nominal_area_um2
    )


def interpolate_crossing(xs, ys, target):
    for i in range(len(ys) - 1):
        y0, y1 = ys[i], ys[i + 1]
        if (y0 <= target <= y1) or (y1 <= target <= y0):
            if y1 == y0:
                return float(xs[i])
            f = (target - y0) / (y1 - y0)
            return float(xs[i] + f * (xs[i + 1] - xs[i]))
    return math.nan


def nearest_state_by_pressure(states, pressures, target):
    idx = int(np.argmin(np.abs(np.asarray(pressures) - target)))
    return idx, states[idx]


def write_pressure_history(path, states, pressures):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["indentation_um", "nominal_pressure_MPa"])
        for st, p in zip(states, pressures):
            w.writerow([f"{st['indentation_um']:.9g}", f"{p:.9g}"])


def element_centers_deformed(xyz, rubber_conn, displacement):
    xdef = xyz + displacement
    return xdef[rubber_conn].mean(axis=1)


def geometric_contact_metrics(
    xyz,
    bottom_conn,
    displacement,
    al_x,
    al_z,
    stress,
    gap_tol_um=0.01,
):
    """Projected 2D contact fraction and first-layer normal-pressure proxy."""
    xdef = xyz[:, 0] + displacement[:, 0]
    zdef = xyz[:, 2] + displacement[:, 2]

    facet_gaps = []
    for q in bottom_conn:
        qx = xdef[q]
        qz = zdef[q]
        az = np.interp(qx, al_x, al_z)
        facet_gaps.append(float(np.mean(qz - az)))
    facet_gaps = np.asarray(facet_gaps)

    active = facet_gaps <= gap_tol_um
    nfacets = len(bottom_conn)
    normal_pressure_proxy = np.maximum(0.0, -stress[:nfacets, 2])

    return {
        "projected_contact_fraction": float(np.count_nonzero(active) / nfacets),
        "min_geometric_gap_um": float(np.min(facet_gaps)),
        "max_geometric_gap_um": float(np.max(facet_gaps)),
        "max_normal_pressure_proxy_MPa": float(np.max(normal_pressure_proxy)),
        "mean_normal_pressure_proxy_MPa": float(np.mean(normal_pressure_proxy)),
    }


def plot_stress_field(
    path,
    xyz,
    rubber_conn,
    state,
    field,
    label,
    title,
    depth_um=24.0,
):
    centers = element_centers_deformed(
        xyz, rubber_conn, state["displacement"]
    )
    z_surface = float(np.min(centers[:, 2]))
    keep = centers[:, 2] <= z_surface + depth_um
    X = centers[keep, 0]
    Z = centers[keep, 2]
    V = np.asarray(field)[keep]

    tri = mtri.Triangulation(X, Z)
    vmax = float(np.nanmax(V))
    vmin = float(np.nanmin(V))
    if not np.isfinite(vmax) or not np.isfinite(vmin):
        raise ValueError("Non-finite stress field")
    if abs(vmax - vmin) < 1e-12:
        levels = np.linspace(vmin - 1e-6, vmax + 1e-6, 8)
    else:
        levels = np.linspace(vmin, vmax, 14)

    fig, ax = plt.subplots(figsize=(14, 4.5))
    cf = ax.tricontourf(tri, V, levels=levels)
    cs = ax.tricontour(
        tri, V, levels=levels[1:-1], linewidths=0.55
    )
    ax.clabel(cs, inline=True, fontsize=6, fmt="%.2g")
    cbar = fig.colorbar(cf, ax=ax, pad=0.015)
    cbar.set_label(label)
    ax.set_xlabel("x [µm]")
    ax.set_ylabel("z [µm]")
    ax.set_title(title)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(float(np.min(X)), float(np.max(X)))
    ax.set_ylim(float(np.min(Z)), float(np.max(Z)))
    fig.tight_layout()
    fig.savefig(path, dpi=240)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xplt", type=Path)
    ap.add_argument("feb", type=Path)
    ap.add_argument("--ramp-um", type=float, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--nominal-width-um", type=float, default=200.0)
    ap.add_argument("--depth-um", type=float, default=1.0)
    args = ap.parse_args()

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    nominal_area = args.nominal_width_um * args.depth_um

    (
        xyz,
        rubber_conn,
        bottom_conn,
        bottom_node_ids,
        al_x,
        al_z,
    ) = parse_feb_mesh(args.feb)
    states = parse_states(args.xplt, args.ramp_um)

    rubber_node_ids = np.unique(rubber_conn.reshape(-1))
    zmax = xyz[rubber_node_ids, 2].max()
    top_node_ids = rubber_node_ids[
        np.isclose(xyz[rubber_node_ids, 2], zmax)
    ]

    pressures = [
        reaction_pressure(st, top_node_ids, nominal_area) for st in states
    ]
    indentations = [st["indentation_um"] for st in states]

    write_pressure_history(
        out / "B129_pressure_history.csv", states, pressures
    )

    final = states[-1]
    final_pressure = pressures[-1]
    final_vm = von_mises(final["stress"])
    final_principal_strain = max_principal_sym6(final["strain"])
    final_contact = geometric_contact_metrics(
        xyz,
        bottom_conn,
        final["displacement"],
        al_x,
        al_z,
        final["stress"],
    )

    targets = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
    with (out / "B129_selected_states.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "target_pressure_MPa",
                "stored_indentation_um",
                "stored_nominal_pressure_MPa",
                "interpolated_indentation_um",
                "projected_contact_fraction",
                "max_normal_pressure_proxy_MPa",
                "mean_normal_pressure_proxy_MPa",
                "min_geometric_gap_um",
                "max_geometric_gap_um",
                "max_von_Mises_MPa",
                "max_principal_Lagrange_strain",
            ]
        )
        for target in targets:
            idx, st = nearest_state_by_pressure(
                states, pressures, target
            )
            cm = geometric_contact_metrics(
                xyz,
                bottom_conn,
                st["displacement"],
                al_x,
                al_z,
                st["stress"],
            )
            vm_i = von_mises(st["stress"])
            e1_i = max_principal_sym6(st["strain"])
            w.writerow(
                [
                    target,
                    f"{st['indentation_um']:.9g}",
                    f"{pressures[idx]:.9g}",
                    f"{interpolate_crossing(indentations, pressures, target):.9g}",
                    f"{cm['projected_contact_fraction']:.9g}",
                    f"{cm['max_normal_pressure_proxy_MPa']:.9g}",
                    f"{cm['mean_normal_pressure_proxy_MPa']:.9g}",
                    f"{cm['min_geometric_gap_um']:.9g}",
                    f"{cm['max_geometric_gap_um']:.9g}",
                    f"{np.max(vm_i):.9g}",
                    f"{np.max(e1_i):.9g}",
                ]
            )

        w.writerow(
            [
                "FINAL_STABLE",
                f"{final['indentation_um']:.9g}",
                f"{final_pressure:.9g}",
                "",
                f"{final_contact['projected_contact_fraction']:.9g}",
                f"{final_contact['max_normal_pressure_proxy_MPa']:.9g}",
                f"{final_contact['mean_normal_pressure_proxy_MPa']:.9g}",
                f"{final_contact['min_geometric_gap_um']:.9g}",
                f"{final_contact['max_geometric_gap_um']:.9g}",
                f"{np.max(final_vm):.9g}",
                f"{np.max(final_principal_strain):.9g}",
            ]
        )

    plot_stress_field(
        out / "B129_final_von_Mises_stress.png",
        xyz,
        rubber_conn,
        final,
        final_vm,
        "von Mises stress [MPa]",
        (
            "B129 final stable state – von Mises stress, "
            f"u={final['indentation_um']:.3f} µm, "
            f"pnom={final_pressure:.3f} MPa"
        ),
    )

    normal_compression = -final["stress"][:, 2]
    plot_stress_field(
        out / "B129_final_normal_stress.png",
        xyz,
        rubber_conn,
        final,
        normal_compression,
        "compressive normal stress −σzz [MPa]",
        (
            "B129 final stable state – normal stress, "
            f"u={final['indentation_um']:.3f} µm, "
            f"pnom={final_pressure:.3f} MPa"
        ),
    )

    max_half = math.floor(final["indentation_um"] / 0.5) * 0.5
    surface_targets = np.arange(0.0, max_half + 0.25, 0.5)
    chosen = []
    for target in surface_targets:
        idx = int(
            np.argmin(np.abs(np.asarray(indentations) - target))
        )
        if not chosen or idx != chosen[-1][0]:
            chosen.append((idx, target))

    curves = []
    for idx, target in chosen:
        st = states[idx]
        zdef = (
            xyz[bottom_node_ids, 2]
            + st["displacement"][bottom_node_ids, 2]
        )
        xdef = (
            xyz[bottom_node_ids, 0]
            + st["displacement"][bottom_node_ids, 0]
        )
        curves.append(
            (idx, target, st["indentation_um"], xdef, zdef)
        )

    with (
        out / "B129_rubber_surface_history_0p5um.csv"
    ).open("w", newline="") as f:
        w = csv.writer(f)
        hdr = ["point", "al_x_um", "al_z_um"]
        for _, target, actual, _, _ in curves:
            hdr.extend(
                [
                    f"rubber_x_target_{target:.1f}um",
                    (
                        f"rubber_z_target_{target:.1f}um_"
                        f"actual_{actual:.6f}um"
                    ),
                ]
            )
        w.writerow(hdr)
        n = max(len(al_x), len(bottom_node_ids))
        for i in range(n):
            row = [
                i,
                al_x[i] if i < len(al_x) else "",
                al_z[i] if i < len(al_z) else "",
            ]
            for _, _, _, xd, zd in curves:
                row.extend(
                    [
                        xd[i] if i < len(xd) else "",
                        zd[i] if i < len(zd) else "",
                    ]
                )
            w.writerow(row)

    fig, ax = plt.subplots(figsize=(15, 4.2))
    ax.plot(al_x, al_z, linewidth=1.2, label="Rigid Al profile")
    for _, target, _, xd, zd in curves:
        ax.plot(
            xd,
            zd,
            linewidth=0.65,
            label=f"{target:.1f} µm",
        )

    if abs(final["indentation_um"] - max_half) > 0.05:
        xd = (
            xyz[bottom_node_ids, 0]
            + final["displacement"][bottom_node_ids, 0]
        )
        zd = (
            xyz[bottom_node_ids, 2]
            + final["displacement"][bottom_node_ids, 2]
        )
        ax.plot(
            xd,
            zd,
            linewidth=1.0,
            linestyle="--",
            label=f"final {final['indentation_um']:.3f} µm",
        )

    ax.set_xlabel("x [µm]")
    ax.set_ylabel("z [µm]")
    ax.set_title(
        "B129 rubber surface contours every 0.5 µm indentation"
    )
    ax.set_aspect("equal", adjustable="box")
    ax.legend(
        ncol=4,
        fontsize=7,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.24),
    )
    fig.tight_layout()
    fig.savefig(
        out / "B129_rubber_surface_history_0p5um.png",
        dpi=240,
    )
    plt.close(fig)

    with (out / "B129_final_summary.txt").open("w") as f:
        f.write(
            f"last_converged_indentation_um="
            f"{final['indentation_um']:.9g}\n"
        )
        f.write(
            f"last_converged_nominal_pressure_MPa="
            f"{final_pressure:.9g}\n"
        )
        for k, v in final_contact.items():
            f.write(f"{k}={v:.9g}\n")
        f.write(
            f"max_von_Mises_MPa={np.max(final_vm):.9g}\n"
        )
        f.write(
            "max_principal_Lagrange_strain="
            f"{np.max(final_principal_strain):.9g}\n"
        )

    print(f"states={len(states)}")
    print(
        "last_converged_indentation_um="
        f"{final['indentation_um']:.9g}"
    )
    print(
        "last_converged_nominal_pressure_MPa="
        f"{final_pressure:.9g}"
    )
    print(
        "projected_contact_fraction="
        f"{final_contact['projected_contact_fraction']:.9g}"
    )
    print(
        "max_normal_pressure_proxy_MPa="
        f"{final_contact['max_normal_pressure_proxy_MPa']:.9g}"
    )
    print(f"max_von_Mises_MPa={np.max(final_vm):.9g}")


if __name__ == "__main__":
    main()
