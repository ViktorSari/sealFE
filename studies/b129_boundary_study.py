#!/usr/bin/env python3
"""B129 side-support variants: roller, free-x, or distributed x-only springs.

Spring traction is t_x=-k_s*u_x on each reference side area. k_s has units
MPa/um; each nodal stiffness is k_s times its tributary area (um^2).
Auxiliary anchors follow z via linear constraints and are fixed in x/y,
so the springs exert no artificial vertical force. Free-x uses one top
centre x anchor solely to remove rigid translation; uy=0 remains everywhere.
"""
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODE = os.environ.get('B129_SUPPORT_MODE', 'rollers')
if MODE not in {'rollers', 'free', 'elastic'}:
    raise ValueError('B129_SUPPORT_MODE must be rollers, free or elastic')
os.environ['B129_SIDE_BC_MODE'] = 'both_sides' if MODE == 'rollers' else 'center_top_anchor'
from studies.b129_mesh_sensitivity import main as generate
from models.b129_stage1 import generate_model as gm


def add_elastic_support(path, stiffness):
    if not np.isfinite(stiffness) or stiffness <= 0:
        raise ValueError('Side stiffness must be positive and finite')
    tree = ET.parse(path)
    root = tree.getroot()
    mesh, boundary = root.find('Mesh'), root.find('Boundary')
    coords = {int(n.get('id')): np.fromstring(n.text, sep=',')
              for b in mesh.findall('Nodes') for n in b}
    rubber = mesh.find("Elements[@name='rubber']")
    ids = sorted({int(v) for e in rubber for v in e.text.split(',')})
    xmin, xmax = min(coords[i][0] for i in ids), max(coords[i][0] for i in ids)
    zlevels = np.unique([coords[i][2] for i in ids])
    zweights = np.zeros(len(zlevels))
    zweights[:-1] += np.diff(zlevels)/2
    zweights[1:] += np.diff(zlevels)/2
    width_y = np.ptp([coords[i][1] for i in ids])
    # The two y-plane nodes share the side strip area equally.
    side_ids = [i for i in ids if coords[i][0] in (xmin, xmax)]
    for bc in list(boundary):
        if bc.get('node_set') == 'rubber_x_center_top_anchor':
            boundary.remove(bc)
    anchors = ET.SubElement(mesh, 'Nodes', name='side_spring_anchors')
    anchor_ids = []
    discrete = ET.Element('Discrete')
    root.insert(list(root).index(root.find('LoadData')), discrete)
    next_id = max(coords) + 1
    areas = {xmin: 0.0, xmax: 0.0}
    # Long enough to stay horizontal without reversal for all proposed cases.
    anchor_distance = 1000.0
    for index, node_id in enumerate(side_ids, 1):
        xyz = coords[node_id].copy()
        side = xyz[0]
        xyz[0] += -anchor_distance if side == xmin else anchor_distance
        aid = next_id
        next_id += 1
        anchor_ids.append(aid)
        ET.SubElement(anchors, 'node', id=str(aid)).text = ','.join(f'{v:.12g}' for v in xyz)
        zi = int(np.argmin(abs(zlevels - xyz[2])))
        area = float(zweights[zi] * width_y / 2)
        areas[side] += area
        name = f'side_spring_{index}'
        ds = ET.SubElement(mesh, 'DiscreteSet', name=name)
        ET.SubElement(ds, 'delem').text = f'{node_id},{aid}'
        material = ET.SubElement(discrete, 'discrete_material', id=str(index), name=name, type='linear spring')
        ET.SubElement(material, 'E').text = f'{stiffness * area:.12g}'
        ET.SubElement(discrete, 'discrete', dmat=str(index), discrete_set=name)
        lc = ET.SubElement(boundary, 'bc', name=f'follow_z_{index}', type='linear constraint')
        ET.SubElement(lc, 'node').text = str(aid)
        ET.SubElement(lc, 'dof').text = 'z'
        child = ET.SubElement(lc, 'child_dof')
        ET.SubElement(child, 'node').text = str(node_id)
        ET.SubElement(child, 'dof').text = 'z'
        ET.SubElement(child, 'value').text = '1'
    ET.SubElement(mesh, 'NodeSet', name='side_spring_anchor_xy').text = ','.join(map(str, anchor_ids))
    bc = ET.SubElement(boundary, 'bc', type='zero displacement', node_set='side_spring_anchor_xy')
    for dof, value in [('x_dof', 1), ('y_dof', 1), ('z_dof', 0)]:
        ET.SubElement(bc, dof).text = str(value)
    expected = float((zlevels[-1]-zlevels[0]) * width_y)
    assert all(np.isclose(a, expected) for a in areas.values()), (areas, expected)
    assert len(set(anchor_ids)) == len(side_ids)
    ET.indent(root)
    tree.write(path, encoding='utf-8', xml_declaration=True)
    print(f'Elastic support: k_s={stiffness} MPa/um; area per side={expected} um^2; springs={len(side_ids)}')


if __name__ == '__main__':
    generate()
    if MODE == 'elastic':
        add_elastic_support(gm.OUTPUT_FEB, float(os.environ['B129_SIDE_STIFFNESS_MPA_PER_UM']))
    print(f'Boundary study support mode: {MODE}')
