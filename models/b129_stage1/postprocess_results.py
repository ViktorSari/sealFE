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

All XPLT regions are read and the rubber_bottom surface is identified by name
and verified against FEB connectivity. Contact pressure is the FEBio facet
average (not a Gauss-point maximum). Zero secondary-surface output must never
be substituted for the active primary surface. -sigma_zz remains an explicitly
labelled first-layer proxy for comparison, not the contact traction.
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


def raw_regions(data, var_chunk):
    _, begin, end = var_chunk
    i0, _ = child(data, begin, end, VAR_ID)
    var_id = struct.unpack_from("<I", data, i0)[0]
    d0, d1 = child(data, begin, end, VAR_DATA)
    regions = {rid: np.frombuffer(data, dtype="<f4", count=(z-a)//4, offset=a)
               for rid, a, z in chunks(data, d0, d1)}
    return var_id, regions


def xplt_metadata(data):
    r0, r1 = child(data, 4, len(data), 0x01000000)
    d0, d1 = child(data, r0, r1, 0x01020000)
    names = {}
    for group, a, z in chunks(data, d0, d1):
        names[group] = {}
        for i, (_, j, k) in enumerate(chunks(data, a, z), 1):
            u, v = child(data, j, k, 0x01020004)
            names[group][data[u:v].split(b"\0")[0].decode()] = i
    m0, m1 = child(data, 4, len(data), 0x01040000)
    a, z = child(data, m0, m1, 0x01043000)
    surfaces = {}
    for _, j, k in chunks(data, a, z):
        h, e = child(data, j, k, 0x01043101)
        u, _ = child(data, h, e, 0x01043102)
        rid = struct.unpack_from("<I", data, u)[0]
        u, v = child(data, h, e, 0x01043104)
        n = struct.unpack_from("<I", data, u)[0]
        name = data[u+4:u+4+n].decode()
        u, v = child(data, j, k, 0x01043200)
        faces = [np.frombuffer(data, dtype="<i4", count=(f-e)//4, offset=e)[2:6]
                 for _, e, f in chunks(data, u, v)]
        surfaces[name] = (rid, np.asarray(faces))
    return names, surfaces


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


def parse_states(xplt_path: Path, ramp_um: float, bottom_conn=None):
    data = xplt_path.read_bytes()
    if data[:4] != b"BEF\0":
        raise ValueError("Not a FEBio XPLT file")
    names, surfaces = xplt_metadata(data)
    sid, faces = surfaces["rubber_bottom"]
    if bottom_conn is not None and not np.array_equal(faces, bottom_conn):
        raise ValueError("XPLT rubber_bottom connectivity differs from FEB")
    states = []
    for tag, begin, end in chunks(data, 4, len(data)):
        if tag != STATE:
            continue
        h0, h1 = child(data, begin, end, STATE_HEADER)
        t0, _ = child(data, h0, h1, STATE_TIME)
        time = struct.unpack_from("<f", data, t0)[0]
        f0, _ = child(data, h0, h1, 0x02010003)
        if struct.unpack_from("<I", data, f0)[0] != 0:
            continue  # Never use failed/debug iterates as converged results.
        d0, d1 = child(data, begin, end, STATE_DATA)
        def values(tag, group, name, region=None):
            a, z = child(data, d0, d1, tag)
            variables = dict(raw_regions(data, v) for v in chunks(data, a, z))
            regions = variables[names[group][name]]
            if region is None:
                if len(regions) != 1:
                    raise ValueError(f"Ambiguous domain for {name}: {list(regions)}")
                return next(iter(regions.values()))
            return regions[region]
        st = {"time": float(time), "indentation_um": float(time*ramp_um),
              "contact_surface_id": sid}
        for key, name in [("displacement", "displacement"), ("reaction", "reaction forces")]:
            st[key] = values(NODE_DATA, 0x01023000, name, 0).reshape(-1, 3)
        for key, name in [("stress", "stress"), ("strain", "Lagrange strain")]:
            st[key] = values(DOMAIN_DATA, 0x01024000, name).reshape(-1, 6)
        for key, name in [("contact_pressure_raw", "contact pressure"),
                          ("contact_gap_raw", "contact gap"), ("contact_status_raw", "contact status")]:
            st[key] = values(SURFACE_DATA, 0x01025000, name, sid)
        states.append(st)
    if len(states) < 2:
        raise ValueError("No loaded converged XPLT states found")
    if np.any(np.diff([s["time"] for s in states]) <= 0):
        raise ValueError("Non-monotonic XPLT times")
    return states


def von_mises(s):
    sxx, syy, szz, sxy, syz, sxz = s.T
    return np.sqrt(
        0.5
        * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy**2 + syz**2 + sxz**2)
    )


def max_principal_sym6(v):
    m = np.empty((len(v), 3, 3))
    m[:, 0, 0], m[:, 1, 1], m[:, 2, 2] = v[:, :3].T
    m[:, 0, 1] = m[:, 1, 0] = v[:, 3]
    m[:, 1, 2] = m[:, 2, 1] = v[:, 4]
    m[:, 0, 2] = m[:, 2, 0] = v[:, 5]
    return np.linalg.eigvalsh(m)[:, -1]


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


if __name__ == "__main__":
    from stage1_report import main
    main()
