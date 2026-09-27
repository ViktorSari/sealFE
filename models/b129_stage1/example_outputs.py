#!/usr/bin/env python3
"""Publication-style B129 PNG/GIF/CSV outputs from an existing XPLT."""
from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.ticker import AutoMinorLocator, MultipleLocator
import matplotlib.tri as mtri
import numpy as np
from PIL import Image

import active_contact_reader as pp


PROFILE_WINDOW_UM = 100.0
GIF_STEP_UM = 0.025
PRESSURE_LEVELS_MPA = (1.0, 2.0, 3.0, 4.0, 5.0)
DATE_FMT = "%y-%m-%d"  # filename-safe representation of YY/MM/DD


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
    a = (target - u[j - 1]) / (u[j] - u[j - 1])
    return (1 - a) * states[j - 1]["displacement"] + a * states[j]["displacement"], float(target), True


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
    intervals = sorted(
        (max(al_x[0], a), min(al_x[-1], b))
        for a, b, active in zip(x0, x1, cp > threshold)
        if active and min(al_x[-1], b) > max(al_x[0], a)
    )
    ds = np.hypot(np.diff(al_x), np.diff(al_z))
    cumulative = np.r_[0.0, np.cumsum(ds)]

    def arc(x):
        return np.interp(x, al_x, cumulative)

    merged = []
    for a, b in intervals:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    active = float(sum(arc(b) - arc(a) for a, b in merged))
    return active, float(cumulative[-1])


def output_path(out: Path, number: int, txt_name: str, stamp: str, suffix: str) -> Path:
    """Exact user naming pattern: number_txt-name_date.ext."""
    stem = Path(txt_name).stem
    return out / f"{number:02d}_{stem}_{stamp}.{suffix}"


def _peak_prominence_proxy(x, z, i, radius_um=18.0):
    left = np.where(x >= x[i] - radius_um)[0][0]
    right = np.where(x <= x[i] + radius_um)[0][-1]
    left_min = float(np.min(z[left:i + 1]))
    right_min = float(np.min(z[i:right + 1]))
    return float(z[i] - max(left_min, right_min))


def choose_profile_window(al_x, al_z, width=PROFILE_WINDOW_UM):
    """Choose a deterministic 100 um window containing two strong asperities when possible."""
    total = float(al_x[-1] - al_x[0])
    if total <= width + 1e-9:
        return float(al_x[0]), float(al_x[-1]), []

    local = np.where((al_z[1:-1] > al_z[:-2]) & (al_z[1:-1] >= al_z[2:]))[0] + 1
    prominences = [(i, _peak_prominence_proxy(al_x, al_z, int(i))) for i in local]
    min_prom = max(0.35, 0.08 * float(np.ptp(al_z)))
    peaks = [(int(i), p) for i, p in prominences if p >= min_prom]
    peaks.sort(key=lambda t: t[1], reverse=True)

    best = None
    for a in range(len(peaks)):
        for b in range(a + 1, len(peaks)):
            ia, pa = peaks[a]
            ib, pb = peaks[b]
            sep = abs(float(al_x[ia] - al_x[ib]))
            if 12.0 <= sep <= width - 8.0:
                score = pa + pb
                if best is None or score > best[0]:
                    best = (score, ia, ib)

    if best is not None:
        _, ia, ib = best
        center = 0.5 * float(al_x[ia] + al_x[ib])
        start = center - width / 2.0
        picked = sorted([float(al_x[ia]), float(al_x[ib])])
    else:
        start = 0.5 * (float(al_x[0] + al_x[-1]) - width)
        picked = []

    start = round(start / 5.0) * 5.0
    start = max(float(al_x[0]), min(start, float(al_x[-1] - width)))
    if picked:
        if picked[0] < start:
            start = max(float(al_x[0]), np.floor(picked[0] / 5.0) * 5.0)
        if picked[1] > start + width:
            start = min(float(al_x[-1] - width), np.ceil((picked[1] - width) / 5.0) * 5.0)
    return float(start), float(start + width), picked


def local_x(x, x0):
    return np.asarray(x) - x0


def profile_limits(al_x, al_z, x0, x1):
    m = (al_x >= x0) & (al_x <= x1)
    zmin = float(np.min(al_z[m]))
    zmax = float(np.max(al_z[m]))
    ylo = 5.0 * np.floor(zmin / 5.0)
    yhi = 5.0 * np.ceil(zmax / 5.0)
    if yhi <= ylo:
        yhi = ylo + 5.0
    return ylo, yhi


def stress_limits(al_x, al_z, x0, x1):
    """From the profile bottom to 3x the highest profile peak, rounded upward to 5 um."""
    m = (al_x >= x0) & (al_x <= x1)
    zmin = float(np.min(al_z[m]))
    peak = max(float(np.max(al_z[m])), 1.0)
    ylo = 5.0 * np.floor(zmin / 5.0)
    yhi = 5.0 * np.ceil((3.0 * peak) / 5.0)
    if yhi <= ylo + 5.0:
        yhi = ylo + 10.0
    return ylo, yhi


def apply_line_template(ax, xlim, ylim, xlabel=None, ylabel=None, x_major=25.0, y_major=None):
    """Template based on the user's supplied profile/correlation figures."""
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_color("#d8d8d8")
        spine.set_linewidth(0.45)
    ax.grid(which="major", color="#dddddd", linewidth=0.45)
    ax.grid(which="minor", color="#eeeeee", linewidth=0.28)
    ax.set_axisbelow(True)
    if x_major:
        ax.xaxis.set_major_locator(MultipleLocator(x_major))
    ax.xaxis.set_minor_locator(AutoMinorLocator(5))
    if y_major:
        ax.yaxis.set_major_locator(MultipleLocator(y_major))
    ax.yaxis.set_minor_locator(AutoMinorLocator(5))
    ax.tick_params(axis="both", which="major", labelsize=9, width=0.5, length=3, color="#666666")
    ax.tick_params(axis="both", which="minor", width=0.35, length=2, color="#999999")
    if xlabel:
        ax.set_xlabel(xlabel, fontstyle="italic", fontsize=11, labelpad=8)
    if ylabel:
        ax.set_ylabel(ylabel, fontstyle="italic", fontsize=11, labelpad=8)

    xmin, xmax = xlim
    ymin, ymax = ylim
    y_axis = 0.0 if ymin <= 0.0 <= ymax else ymin
    ax.annotate("", xy=(xmax, y_axis), xytext=(xmin, y_axis),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=0.65, mutation_scale=9),
                annotation_clip=False, zorder=6)
    ax.annotate("", xy=(xmin, ymax), xytext=(xmin, ymin),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=0.65, mutation_scale=9),
                annotation_clip=False, zorder=6)


def selected_pressure_states(states, pressure):
    maxp = max(float(pressure[id(s)]) for s in states)
    if maxp >= PRESSURE_LEVELS_MPA[-1]:
        targets = np.asarray(PRESSURE_LEVELS_MPA, dtype=float)
    else:
        lo = max(maxp / 5.0, 0.05)
        targets = np.linspace(lo, maxp, 5)
    selected = [min(states, key=lambda s: abs(float(pressure[id(s)]) - target)) for target in targets]
    return targets, selected


def save_contact_curve(path, csv_path, states, xyz, bottom_conn, al_x, al_z, pressure):
    rows = []
    for st in states:
        xz, cp = contact_segments(xyz, bottom_conn, st)
        length, full = true_contact_length(xz, cp, al_x, al_z)
        xwidth = xz[:, 1, 0] - xz[:, 0, 0]
        recovered = float(np.dot(cp, xwidth) / (al_x[-1] - al_x[0]))
        p = float(pressure[id(st)])
        if p > 1e-5 and abs(recovered - p) / p > 0.02:
            raise ValueError("FEBio contact pressure fails reaction balance")
        ratio = min(1.0, max(0.0, length / full))
        rows.append((st["indentation_um"], p, length, full, ratio, np.max(cp), recovered))

    with csv_path.open("w", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["indentation_um", "nominal_pressure_MPa", "active_Al_profile_arc_um",
                    "measured_Al_profile_arc_um", "contact_length_ratio",
                    "max_facet_contact_pressure_MPa", "pressure_integral_MPa"])
        w.writerows(rows)

    pressures = np.asarray([r[1] for r in rows], dtype=float)
    ratios = np.asarray([r[4] for r in rows], dtype=float)
    full_idx = None
    for i in range(len(rows)):
        if ratios[i] >= 0.995 and np.all(ratios[i:] >= 0.990):
            full_idx = i
            break
    if full_idx is None:
        xmax = float(np.max(pressures))
    else:
        pfull = float(pressures[full_idx])
        hard_max = 1.10 * pfull
        quarter = 0.25
        xmax = np.floor(hard_max / quarter + 1e-12) * quarter
        if xmax <= pfull:
            tenth = 0.10
            xmax = np.floor(hard_max / tenth + 1e-12) * tenth
        xmax = max(xmax, pfull)
    xmax = max(xmax, 0.5)

    fig, ax = plt.subplots(figsize=(12, 2.65))
    ax.plot(pressures, ratios, color="#222222", lw=1.15)
    apply_line_template(
        ax, (0.0, xmax), (0.0, 1.02),
        xlabel=r"Nominal pressure, $p_{nom}$ [MPa]",
        ylabel="Contact length ratio [-]",
        x_major=0.5 if xmax <= 6.0 else 1.0,
        y_major=0.25,
    )
    fig.subplots_adjust(left=0.095, right=0.985, top=0.96, bottom=0.27)
    fig.savefig(path, dpi=260)
    plt.close(fig)


def save_contact_plot(path, csv_path, states, xyz, bottom_conn, al_x, al_z, pressure, x0, x1):
    targets, selected = selected_pressure_states(states, pressure)
    ylo, yhi = profile_limits(al_x, al_z, x0, x1)
    shades = plt.cm.Oranges(np.linspace(0.35, 0.95, 5))

    with csv_path.open("w", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["target_nominal_pressure_MPa", "stored_nominal_pressure_MPa",
                    "stored_indentation_um", "max_facet_contact_pressure_MPa",
                    "window_x_start_um", "window_x_end_um"])
        for target, st in zip(targets, selected):
            w.writerow([target, pressure[id(st)], st["indentation_um"],
                        np.max(st["contact_pressure_raw"]), x0, x1])

    fig, axes = plt.subplots(5, 1, figsize=(12, 8.4), sharex=True, sharey=True)
    for row, (target, st, color) in enumerate(zip(targets, selected, shades)):
        ax = axes[row]
        curve = surface_points(xyz, bottom_conn, st["displacement"])
        xz, cp = contact_segments(xyz, bottom_conn, st)
        m_al = (al_x >= x0) & (al_x <= x1)
        ax.plot(local_x(al_x[m_al], x0), al_z[m_al], color="#777777", lw=0.85)
        m_curve = (curve[:, 0] >= x0) & (curve[:, 0] <= x1)
        ax.plot(local_x(curve[m_curve, 0], x0), curve[m_curve, 1], color=color, lw=1.35)

        active = cp > 1e-8
        seg = xz[active].copy()
        keep = (np.max(seg[:, :, 0], axis=1) >= x0) & (np.min(seg[:, :, 0], axis=1) <= x1)
        seg = seg[keep]
        if len(seg):
            seg[:, :, 0] -= x0
            ax.add_collection(LineCollection(seg, colors="#8c2d04", linewidths=2.0, zorder=5))

        apply_line_template(ax, (0.0, x1 - x0), (ylo, yhi), x_major=25.0, y_major=5.0)
        ax.text(0.985, 0.82,
                r"$p_{nom}$ = %.2f MPa,  $u$ = %.3f µm" % (pressure[id(st)], st["indentation_um"]),
                transform=ax.transAxes, ha="right", va="center", fontsize=9.5)
        if row < 4:
            ax.tick_params(labelbottom=False)
    axes[-1].set_xlabel(r"Measurement coordinate, $x$ [$\mu$m]", fontstyle="italic", fontsize=12, labelpad=8)
    fig.supylabel(r"Profile height, $z$ [$\mu$m]", x=0.025, fontstyle="italic", fontsize=12)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.985, bottom=0.105, hspace=0.36)
    fig.savefig(path, dpi=260)
    plt.close(fig)


def save_surface_history(path, csv_path, states, xyz, bottom_conn, al_x, al_z, x0, x1):
    end = float(states[-1]["indentation_um"])
    targets = list(np.arange(0.0, end + 1e-8, 0.5))
    if not np.isclose(targets[-1], end):
        targets.append(end)
    curves = []
    with csv_path.open("w", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["target_indent_um", "x_local_um", "x_original_um", "rubber_z_um", "visual_interpolation"])
        for u in targets:
            d, actual, interp = at_indent(states, u)
            curve = surface_points(xyz, bottom_conn, d)
            m = (curve[:, 0] >= x0) & (curve[:, 0] <= x1)
            c = curve[m]
            curves.append((actual, c, interp))
            w.writerows((actual, x - x0, x, z, int(interp)) for x, z in c)

    ylo, yhi = profile_limits(al_x, al_z, x0, x1)
    fig, ax = plt.subplots(figsize=(12, 4.0))
    m_al = (al_x >= x0) & (al_x <= x1)
    ax.plot(local_x(al_x[m_al], x0), al_z[m_al], color="black", lw=1.15, zorder=5)
    cm = plt.get_cmap("Oranges")
    denom = max(end, 1e-9)
    for u, curve, _ in curves:
        ax.plot(local_x(curve[:, 0], x0), curve[:, 1], color=cm(0.25 + 0.70 * u / denom), lw=0.95)
    apply_line_template(
        ax, (0.0, x1 - x0), (ylo, yhi),
        xlabel=r"Measurement coordinate, $x$ [$\mu$m]",
        ylabel=r"Profile height, $z$ [$\mu$m]",
        x_major=25.0, y_major=5.0,
    )
    bar = fig.add_axes([0.23, 0.10, 0.55, 0.025])
    fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, end), cmap=cm),
                 cax=bar, orientation="horizontal", label=r"Indentation, $u$ [$\mu$m]")
    fig.subplots_adjust(left=0.095, right=0.985, top=0.97, bottom=0.30)
    fig.savefig(path, dpi=260)
    plt.close(fig)


def front_mesh_edges(coords, rubber_conn):
    faces = rubber_conn[:, [0, 1, 5, 4]]
    q = coords[faces][:, :, [0, 2]]
    return np.stack((q[:, [0, 1]], q[:, [1, 2]], q[:, [2, 3]], q[:, [3, 0]])).reshape(-1, 2, 2)


def draw_deformed_mesh(ax, coords, rubber_conn, x0, alpha=0.32, lw=0.23):
    edges = front_mesh_edges(coords, rubber_conn).copy()
    edges[:, :, 0] -= x0
    ax.add_collection(LineCollection(edges, colors="#303030", linewidths=lw, alpha=alpha, zorder=5))


def save_mesh(path, xyz, rubber_conn, bottom_conn, al_x, al_z, states, pressure, x0, x1):
    ylo, yhi = stress_limits(al_x, al_z, x0, x1)
    chosen = min(states, key=lambda s: abs(float(pressure[id(s)]) - 5.0))
    fig, axes = plt.subplots(2, 1, figsize=(12, 5.6), sharex=True, sharey=True)
    for ax, coords, label in [
        (axes[0], xyz, "Undeformed mesh"),
        (axes[1], xyz + chosen["displacement"],
         "Deformed mesh: %.2f MPa, u = %.3f µm" % (pressure[id(chosen)], chosen["indentation_um"])),
    ]:
        draw_deformed_mesh(ax, coords, rubber_conn, x0, alpha=0.55, lw=0.28)
        m_al = (al_x >= x0) & (al_x <= x1)
        ax.plot(local_x(al_x[m_al], x0), al_z[m_al], color="black", lw=0.8, zorder=6)
        apply_line_template(ax, (0.0, x1 - x0), (ylo, yhi), x_major=25.0, y_major=5.0)
        ax.text(0.985, 0.86, label, transform=ax.transAxes, ha="right", va="center", fontsize=9.5)
        ax.set_aspect("equal", adjustable="box")
    axes[-1].set_xlabel(r"Measurement coordinate, $x$ [$\mu$m]", fontstyle="italic", fontsize=11, labelpad=7)
    fig.supylabel(r"Height, $z$ [$\mu$m]", x=0.025, fontstyle="italic", fontsize=11)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.98, bottom=0.12, hspace=0.35)
    fig.savefig(path, dpi=260)
    plt.close(fig)

    pts = xyz[rubber_conn]
    dx = np.diff(al_x)
    dz = np.diff(al_z)
    return {
        "rubber_hex8_elements": len(rubber_conn),
        "contact_facets": len(bottom_conn),
        "nominal_x_pitch_um": float(np.median(dx)),
        "rubber_first_layer_um": float(np.median(np.abs(pts[:len(bottom_conn), 4, 2] - pts[:len(bottom_conn), 0, 2]))),
        "rubber_height_um": float(np.max(xyz[rubber_conn, 2]) - np.min(xyz[rubber_conn, 2])),
        "out_of_plane_um": 1.0,
        "measured_profile_arc_um": float(np.sum(np.hypot(dx, dz))),
        "display_window_x_start_um": x0,
        "display_window_x_end_um": x1,
        "display_window_width_um": x1 - x0,
        "stress_mesh_display_y_min_um": ylo,
        "stress_mesh_display_y_max_um": yhi,
    }


def field_points_and_values(xyz, rubber_conn, bottom_conn, st, values):
    centers = pp.element_centers_deformed(xyz, rubber_conn, st["displacement"])
    bottom = surface_points(xyz, bottom_conn, st["displacement"])
    edge_ids = np.minimum(np.arange(len(bottom)), len(bottom_conn) - 1)
    points = np.vstack((centers[:, [0, 2]], bottom))
    field = np.r_[values, values[edge_ids]]
    return points, field, centers


def save_single_field(path, label, unit, fn, cmap, xyz, rubber_conn, bottom_conn,
                      states, pressure, al_x, al_z, x0, x1):
    targets, selected = selected_pressure_states(states, pressure)
    ylo, yhi = stress_limits(al_x, al_z, x0, x1)
    prepared = []
    visible_values = []
    for st in selected:
        v = np.asarray(fn(st), dtype=float)
        points, field, centers = field_points_and_values(xyz, rubber_conn, bottom_conn, st, v)
        vis = ((centers[:, 0] >= x0) & (centers[:, 0] <= x1) &
               (centers[:, 2] >= ylo) & (centers[:, 2] <= yhi))
        if np.any(vis):
            visible_values.append(v[vis])
        prepared.append((st, v, points, field))
    all_vis = np.concatenate(visible_values) if visible_values else np.concatenate([p[1] for p in prepared])
    lo = float(np.nanmin(all_vis))
    hi = float(np.nanmax(all_vis))
    if label in ("von Mises stress", "Maximum principal Lagrange strain"):
        lo = max(0.0, lo)
    if np.isclose(lo, hi):
        hi = lo + 1e-6
    levels = np.linspace(lo, hi, 17)
    isolines = np.linspace(lo, hi, 9)[1:-1]

    fig, axes = plt.subplots(5, 1, figsize=(12, 12.8), sharex=True, sharey=True)
    cf = None
    for ax, (st, v, points, field), target in zip(axes, prepared, targets):
        xplot = points[:, 0] - x0
        tri = mtri.Triangulation(xplot, points[:, 1])
        cf = ax.tricontourf(tri, field, levels=levels, cmap=cmap, extend="both")
        ax.tricontour(tri, field, levels=isolines, colors="white", linewidths=0.35, alpha=0.75)
        current = xyz + st["displacement"]
        draw_deformed_mesh(ax, current, rubber_conn, x0, alpha=0.25, lw=0.20)
        m_al = (al_x >= x0) & (al_x <= x1)
        ax.plot(local_x(al_x[m_al], x0), al_z[m_al], color="black", lw=0.65, zorder=6)
        ax.set_xlim(0.0, x1 - x0)
        ax.set_ylim(ylo, yhi)
        ax.set_aspect("equal", adjustable="box")
        ax.tick_params(axis="both", labelsize=8.5)
        ax.xaxis.set_major_locator(MultipleLocator(25.0))
        ax.yaxis.set_major_locator(MultipleLocator(5.0))
        ax.text(0.985, 0.88,
                r"$p_{nom}$ = %.2f MPa,  $u$ = %.3f µm" % (pressure[id(st)], st["indentation_um"]),
                transform=ax.transAxes, ha="right", va="center", fontsize=9.2,
                bbox=dict(facecolor="white", alpha=0.72, edgecolor="none", pad=1.5))
    axes[-1].set_xlabel(r"Measurement coordinate, $x$ [$\mu$m]", fontstyle="italic", fontsize=11, labelpad=7)
    fig.supylabel(r"Height, $z$ [$\mu$m]", x=0.025, fontstyle="italic", fontsize=11)
    cbar = fig.colorbar(cf, ax=axes, fraction=0.025, pad=0.018)
    cbar.set_label(label + (f" [{unit}]" if unit else ""), fontsize=10)
    fig.subplots_adjust(left=0.075, right=0.87, top=0.985, bottom=0.075, hspace=0.34)
    fig.savefig(path, dpi=260)
    plt.close(fig)


def save_fields(paths, xyz, rubber_conn, bottom_conn, states, pressure, al_x, al_z, x0, x1):
    save_single_field(
        paths["max_principal"], "Maximum principal Lagrange strain", "-",
        lambda s: pp.max_principal_sym6(s["strain"]), "cividis",
        xyz, rubber_conn, bottom_conn, states, pressure, al_x, al_z, x0, x1,
    )
    save_single_field(
        paths["minus_sigma"], r"$-\sigma_{zz}$", "MPa",
        lambda s: -s["stress"][:, 2], "magma",
        xyz, rubber_conn, bottom_conn, states, pressure, al_x, al_z, x0, x1,
    )
    save_single_field(
        paths["von_mises"], "von Mises stress", "MPa",
        lambda s: pp.von_mises(s["stress"]), "viridis",
        xyz, rubber_conn, bottom_conn, states, pressure, al_x, al_z, x0, x1,
    )


def save_gif(path, states, xyz, bottom_conn, al_x, al_z, x0, x1):
    end = float(states[-1]["indentation_um"])
    targets = list(np.arange(0.0, end + 1e-8, GIF_STEP_UM))
    if not np.isclose(targets[-1], end):
        targets.append(end)
    ylo, yhi = profile_limits(al_x, al_z, x0, x1)
    frames = []
    m_al = (al_x >= x0) & (al_x <= x1)
    alx = local_x(al_x[m_al], x0)
    alz = al_z[m_al]

    for u in targets:
        d, actual, interp = at_indent(states, u)
        curve = surface_points(xyz, bottom_conn, d)
        m = (curve[:, 0] >= x0) & (curve[:, 0] <= x1)
        c = curve[m]
        fig, ax = plt.subplots(figsize=(12, 3.3))
        ax.plot(alx, alz, color="#555555", lw=1.05)
        ax.plot(local_x(c[:, 0], x0), c[:, 1], color="#d95f0e", lw=1.45)
        apply_line_template(
            ax, (0.0, x1 - x0), (ylo, yhi),
            xlabel=r"Measurement coordinate, $x$ [$\mu$m]",
            ylabel=r"Profile height, $z$ [$\mu$m]",
            x_major=25.0, y_major=5.0,
        )
        ax.text(0.985, 0.88, r"$u$ = %.3f µm%s" % (actual, "*" if interp else ""),
                transform=ax.transAxes, ha="right", va="center", fontsize=10)
        fig.subplots_adjust(left=0.09, right=0.985, top=0.96, bottom=0.24)
        fig.canvas.draw()
        arr = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
        frames.append(Image.fromarray(arr))
        plt.close(fig)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=60, loop=0, optimize=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("xplt", type=Path)
    p.add_argument("feb", type=Path)
    p.add_argument("--ramp-um", type=float, default=4.2)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--txt-name", default="CA129_02.TXT")
    p.add_argument("--date-stamp", default=None, help="filename date, YY-MM-DD; defaults to today")
    args = p.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    stamp = args.date_stamp or date.today().strftime(DATE_FMT)

    xyz, rubber_conn, bottom_conn, _, al_x, al_z = pp.parse_feb_mesh(args.feb)
    root = ET.parse(args.feb).getroot()
    rubber = next(m for m in root.findall("./Material/material") if m.get("name") == "rubber")
    k_mpa = float(rubber.findtext("k"))
    domain = next(d for d in root.findall("./MeshDomains/SolidDomain") if d.get("name") == "rubber")
    augmented = domain.findtext("laugon") == "1"
    states = pp.parse_states(args.xplt, args.ramp_um, bottom_conn)
    width = float(al_x[-1] - al_x[0])
    pressure = {id(st): nominal_pressure(st, xyz, rubber_conn, width) for st in states}

    x0, x1, peaks = choose_profile_window(al_x, al_z, PROFILE_WINDOW_UM)
    paths = {
        "contact_ratio_png": output_path(out, 1, args.txt_name, stamp, "png"),
        "contact_ratio_csv": output_path(out, 1, args.txt_name, stamp, "csv"),
        "contact_line_png": output_path(out, 2, args.txt_name, stamp, "png"),
        "contact_line_csv": output_path(out, 2, args.txt_name, stamp, "csv"),
        "gif": output_path(out, 3, args.txt_name, stamp, "gif"),
        "max_principal": output_path(out, 4, args.txt_name, stamp, "png"),
        "mesh": output_path(out, 5, args.txt_name, stamp, "png"),
        "minus_sigma": output_path(out, 6, args.txt_name, stamp, "png"),
        "surface_png": output_path(out, 7, args.txt_name, stamp, "png"),
        "surface_csv": output_path(out, 7, args.txt_name, stamp, "csv"),
        "von_mises": output_path(out, 8, args.txt_name, stamp, "png"),
        "summary": output_path(out, 9, args.txt_name, stamp, "csv"),
    }

    save_contact_curve(paths["contact_ratio_png"], paths["contact_ratio_csv"],
                       states, xyz, bottom_conn, al_x, al_z, pressure)
    save_contact_plot(paths["contact_line_png"], paths["contact_line_csv"],
                      states, xyz, bottom_conn, al_x, al_z, pressure, x0, x1)
    save_gif(paths["gif"], states, xyz, bottom_conn, al_x, al_z, x0, x1)
    save_fields(paths, xyz, rubber_conn, bottom_conn, states, pressure, al_x, al_z, x0, x1)
    stats = save_mesh(paths["mesh"], xyz, rubber_conn, bottom_conn, al_x, al_z, states, pressure, x0, x1)
    save_surface_history(paths["surface_png"], paths["surface_csv"],
                         states, xyz, bottom_conn, al_x, al_z, x0, x1)

    with paths["summary"].open("w", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["quantity", "value", "status"])
        for key, value in stats.items():
            w.writerow([key, value, "from FEB geometry / deterministic display rule"])
        w.writerow(["display_prominent_asperities_original_x_um", ";".join(f"{v:.3f}" for v in peaks),
                    "100 um window chosen to include two strong asperities when possible"])
        for key, value, status in [
            ("source_txt", args.txt_name, "input identity"),
            ("material", "MR2 C10=0.348 MPa, C01=0.886 MPa", "fitted input"),
            ("K_MPa", k_mpa, "numerical augmentation parameter, not measured"),
            ("volume_augmentation", int(augmented), "three-field element-averaged volume"),
            ("volume_augmentation_atol", domain.findtext("atol") or "off", "three-field domain"),
            ("rubber_side_x", "both roller boundaries", "boundary condition"),
            ("rubber_y", "uy=0", "boundary condition"),
            ("rubber_top_z", "prescribed displacement", "boundary condition"),
            ("rigid_Al", "fully fixed", "boundary condition"),
            ("contact_penalty_MPa_per_um", 0.30, "numerical contact parameter"),
            ("contact_method", "one-pass sliding elastic, augmented Lagrange", "friction coefficient 0"),
            ("max_external_increment_um", 0.1, "adaptive cutbacks allowed"),
            ("gif_display_increment_um", GIF_STEP_UM, "visual interpolation between converged states"),
        ]:
            w.writerow([key, value, status])

    mapping = [
        (1, "contact_length_ratio", "PNG + CSV"),
        (2, "contact_line_five_levels", "PNG + CSV"),
        (3, "indentation, 0.025 um display step", "GIF"),
        (4, "maximum principal Lagrange strain, five levels", "PNG"),
        (5, "mesh panels, undeformed + deformed near 5 MPa", "PNG"),
        (6, "minus sigma_zz, five levels", "PNG"),
        (7, "surface evolution, 0.5 um indentation increments", "PNG + CSV"),
        (8, "von Mises stress, five levels", "PNG"),
        (9, "model / mesh / display summary", "CSV"),
    ]
    with (out / "README.txt").open("w") as fread:
        fread.write(f"Source TXT: {args.txt_name}\n")
        fread.write(f"Filename date: {stamp} (YY-MM-DD, filename-safe form of YY/MM/DD)\n")
        fread.write(f"100 um display window: x={x0:.3f}..{x1:.3f} um original coordinate\n")
        if peaks:
            fread.write("Prominent asperities in selection: " + ", ".join(f"{v:.3f} um" for v in peaks) + "\n")
        fread.write("\nNumbered result map:\n")
        for number, name, formats in mapping:
            fread.write(f"{number:02d}: {name} [{formats}]\n")

    print("Wrote", len(list(out.iterdir())), "publication-style files")
    print("display_window_um=", x0, x1, "prominent_peaks=", peaks)
    print("last_converged=", states[-1]["indentation_um"], pressure[id(states[-1])])


if __name__ == "__main__":
    main()
