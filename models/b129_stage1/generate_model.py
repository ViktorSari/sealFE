#!/usr/bin/env python3
"""
Stage-1 B129 rough aluminium / rubber normal-contact FEM model.

Geometry:
- measured B129 profile, 200 um window, 0.5 um pitch
- rigid rough aluminium
- 100 um rubber layer, thin 3D extrusion with uy=0 (plane-strain-like)

Material:
- uncoupled Mooney-Rivlin
- C10 = 0.20 MPa
- C01 = 0.65 MPa
- K = 850 MPa placeholder until measured compressibility/D is supplied

Loading:
- pressure ramp 0 -> 5 MPa

Contact:
- sliding-elastic normal contact
- augmented Lagrange, one-pass (rigid primary / deformable secondary)
- fric_coeff = 0 means no prescribed Coulomb shear at this Stage 1

The generated XML is patched to use FEBio's built-in skyline linear solver,
so the CI build does not require Intel MKL.
"""

from pathlib import Path
import numpy as np
import pyfebio as feb

MP = feb.material.MaterialParameter

HERE = Path(__file__).resolve().parent
PROFILE_CSV = HERE / "B129_400_600um_profile.csv"
OUTPUT_FEB = HERE / "B129_stage1_normal_contact.feb"

OUT_OF_PLANE_UM = 1.0
RUBBER_HEIGHT_UM = 100.0
AL_BASE_MARGIN_UM = 5.0
INITIAL_GAP_UM = 0.0

C10_MPA = 0.20
C01_MPA = 0.65
BULK_MODULUS_MPA = 850.0  # placeholder, approx. nu=0.499
MAX_PRESSURE_MPA = 5.0

TIME_STEPS = 100
STEP_SIZE = 0.01

RUBBER_Z_LEVELS_UM = np.array(
    [0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, RUBBER_HEIGHT_UM],
    dtype=float,
)


class MeshBuilder:
    def __init__(self):
        self.nodes = []
        self.next_node = 1
        self.next_elem = 1

    def add_node(self, x, y, z):
        nid = self.next_node
        self.next_node += 1
        self.nodes.append(
            feb.mesh.Node(id=nid, text=f"{x:.9g},{y:.9g},{z:.9g}")
        )
        return nid

    def add_hex8(self, conn):
        eid = self.next_elem
        self.next_elem += 1
        return feb.mesh.Hex8Element(id=eid, text=",".join(map(str, conn)))


def load_profile():
    a = np.loadtxt(PROFILE_CSV, delimiter=",", skiprows=1)
    x = a[:, 0].astype(float)
    z = a[:, 1].astype(float)
    if not np.all(np.diff(x) > 0):
        raise ValueError("Profile x coordinates must be strictly increasing.")
    return x, z


def main():
    x, rough = load_profile()
    nx = len(x)
    yvals = [0.0, OUT_OF_PLANE_UM]
    mb = MeshBuilder()

    # Rigid aluminium slab.
    al_base_z = float(np.min(rough) - AL_BASE_MARGIN_UM)
    al_bottom = np.zeros((nx, 2), dtype=int)
    al_top = np.zeros((nx, 2), dtype=int)

    for i in range(nx):
        for j, y in enumerate(yvals):
            al_bottom[i, j] = mb.add_node(x[i], y, al_base_z)
            al_top[i, j] = mb.add_node(x[i], y, rough[i])

    al_elements = []
    for i in range(nx - 1):
        al_elements.append(
            mb.add_hex8([
                al_bottom[i, 0], al_bottom[i + 1, 0],
                al_bottom[i + 1, 1], al_bottom[i, 1],
                al_top[i, 0], al_top[i + 1, 0],
                al_top[i + 1, 1], al_top[i, 1],
            ])
        )

    # Rubber block.
    z0 = float(np.max(rough) + INITIAL_GAP_UM)
    nz = len(RUBBER_Z_LEVELS_UM)
    rub_nodes = np.zeros((nx, 2, nz), dtype=int)

    for i in range(nx):
        for j, y in enumerate(yvals):
            for k, zr in enumerate(RUBBER_Z_LEVELS_UM):
                rub_nodes[i, j, k] = mb.add_node(x[i], y, z0 + zr)

    rub_elements = []
    for k in range(nz - 1):
        for i in range(nx - 1):
            rub_elements.append(
                mb.add_hex8([
                    rub_nodes[i, 0, k], rub_nodes[i + 1, 0, k],
                    rub_nodes[i + 1, 1, k], rub_nodes[i, 1, k],
                    rub_nodes[i, 0, k + 1], rub_nodes[i + 1, 0, k + 1],
                    rub_nodes[i + 1, 1, k + 1], rub_nodes[i, 1, k + 1],
                ])
            )

    model = feb.model.Model(
        control_=feb.control.Control(
            time_steps=TIME_STEPS,
            step_size=STEP_SIZE,
            plot_stride=5,
            output_stride=5,
            solver=feb.control.SolidSolver(
                symmetric_stiffness="symmetric",
            ),
        )
    )

    model.mesh_.add_node_domain(
        feb.mesh.Nodes(name="all_nodes", all_nodes=mb.nodes)
    )
    model.mesh_.add_element_domain(
        feb.mesh.Elements(name="al_rigid", type="hex8", all_elements=al_elements)
    )
    model.mesh_.add_element_domain(
        feb.mesh.Elements(name="rubber", type="hex8", all_elements=rub_elements)
    )

    model.material_.add_material(
        feb.material.RigidBody(
            name="al_rigid",
            id=1,
            center_of_mass=f"{0.5 * (x[0] + x[-1]):.9g},{0.5 * OUT_OF_PLANE_UM:.9g},{al_base_z:.9g}",
        )
    )
    model.material_.add_material(
        feb.material.MooneyRivlinUC(
            name="rubber",
            id=2,
            c1=MP(text=C10_MPA),
            c2=MP(text=C01_MPA),
            k=MP(text=BULK_MODULUS_MPA),
        )
    )

    model.meshdomains_.add_solid_domain(
        feb.meshdomains.SolidDomain(name="al_rigid", mat="al_rigid")
    )
    model.meshdomains_.add_solid_domain(
        feb.meshdomains.SolidDomain(name="rubber", mat="rubber")
    )

    # Contact surfaces.
    al_surf = feb.mesh.Surface(name="al_top")
    for i in range(nx - 1):
        al_surf.add_quad4(
            feb.mesh.Quad4Element(
                id=i + 1,
                text=",".join(map(str, [
                    al_top[i, 0], al_top[i + 1, 0],
                    al_top[i + 1, 1], al_top[i, 1],
                ])),
            )
        )
    model.mesh_.add_surface(al_surf)

    rub_bottom = feb.mesh.Surface(name="rubber_bottom")
    for i in range(nx - 1):
        rub_bottom.add_quad4(
            feb.mesh.Quad4Element(
                id=i + 1,
                text=",".join(map(str, [
                    rub_nodes[i, 0, 0], rub_nodes[i, 1, 0],
                    rub_nodes[i + 1, 1, 0], rub_nodes[i + 1, 0, 0],
                ])),
            )
        )
    model.mesh_.add_surface(rub_bottom)

    rub_top = feb.mesh.Surface(name="rubber_top")
    for i in range(nx - 1):
        rub_top.add_quad4(
            feb.mesh.Quad4Element(
                id=i + 1,
                text=",".join(map(str, [
                    rub_nodes[i, 0, -1], rub_nodes[i + 1, 0, -1],
                    rub_nodes[i + 1, 1, -1], rub_nodes[i, 1, -1],
                ])),
            )
        )
    model.mesh_.add_surface(rub_top)

    model.mesh_.add_surface_pair(
        feb.mesh.SurfacePair(
            name="rough_contact",
            primary="al_top",
            secondary="rubber_bottom",
        )
    )

    # Rigid Al fixed.
    model.rigid_.add_rigid_bc(
        feb.rigid.RigidFixed(
            rb="al_rigid",
            Rx_dof=1, Ry_dof=1, Rz_dof=1,
            Ru_dof=1, Rv_dof=1, Rw_dof=1,
        )
    )

    # Plane-strain-like condition: uy=0 for every rubber node.
    plane_nodes = rub_nodes.reshape(-1).tolist()
    model.mesh_.add_node_set(
        feb.mesh.NodeSet(
            name="rubber_plane_strain",
            text=",".join(map(str, plane_nodes)),
        )
    )
    model.boundary_.add_bc(
        feb.boundary.BCZeroDisplacement(
            node_set="rubber_plane_strain",
            x_dof=0, y_dof=1, z_dof=0,
        )
    )

    # Remove the remaining x rigid-body mode with one upper-centre anchor.
    anchor = int(rub_nodes[nx // 2, 0, -1])
    model.mesh_.add_node_set(
        feb.mesh.NodeSet(name="x_anchor", text=str(anchor))
    )
    model.boundary_.add_bc(
        feb.boundary.BCZeroDisplacement(
            node_set="x_anchor",
            x_dof=1, y_dof=0, z_dof=0,
        )
    )

    model.contact_.add_contact(
        feb.contact.SlidingElastic(
            name="rough_normal_contact",
            surface_pair="rough_contact",
            auto_penalty=1,
            laugon="AUGLAG",
            two_pass=0,
            symmetric_stiffness=1,
            fric_coeff=0,
            maxaug=25,
        )
    )

    model.loaddata_.add_load_curve(
        feb.loaddata.LoadCurve(
            id=1,
            points=feb.loaddata.CurvePoints(points=["0,0", "1,1"]),
        )
    )
    model.loads_.add_surface_load(
        feb.loads.PressureLoad(
            surface="rubber_top",
            pressure=feb.loads.Scale(lc=1, text=MAX_PRESSURE_MPA),
            linear=0,
            shell_bottom=0,
            symmetric_stiffness=0,
        )
    )

    model.output_.add_plotfile(
        feb.output.OutputPlotfile(
            all_vars=[
                feb.output.Var(type="displacement"),
                feb.output.Var(type="stress"),
                feb.output.Var(type="Lagrange strain"),
                feb.output.Var(type="contact pressure"),
                feb.output.Var(type="contact gap"),
                feb.output.Var(type="contact status"),
            ]
        )
    )

    model.save(str(OUTPUT_FEB))

    # pyFEBio currently restricts the LinearSolver enum to MKL solvers.
    # CI intentionally builds FEBio without MKL, so select built-in skyline.
    xml = OUTPUT_FEB.read_text(encoding="utf-8")
    xml = xml.replace('linear_solver type="pardiso"', 'linear_solver type="skyline"')
    OUTPUT_FEB.write_text(xml, encoding="utf-8")

    print(f"Generated: {OUTPUT_FEB}")
    print(f"Profile points: {nx}")
    print(f"Rigid Al hex8 elements: {len(al_elements)}")
    print(f"Rubber hex8 elements: {len(rub_elements)}")
    print(f"Pressure ramp: 0 -> {MAX_PRESSURE_MPA} MPa")
    print("Linear solver: skyline")


if __name__ == "__main__":
    main()
