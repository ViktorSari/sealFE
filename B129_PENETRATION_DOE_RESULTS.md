# B129 penetration DoE — provisional results, 2026-09-28

## Decision first

The only new Stage A case to reach 5 MPa is P=0.45 MPa/µm at Δu=0.05 µm. Its nearest stored state at 5.0724 MPa has a reconstructed geometric gap of −0.09367 µm versus −0.10363 µm for the P=0.40 reference stored at 4.9923 MPa. This is approximately 9.6% less overlap **at nearby but not identical pressure**. The 5 MPa interpolated indentation changes from 3.415479 to 3.407734 µm (−0.227%). The pressure integral agrees with the reaction within 0.0001% for P=0.45. A 0.375 µm mesh check is running before this becomes a selected setting.

The smaller Δu=0.025 µm did not help: all three cases terminated with negative Jacobians before 5 MPa. An Actions job's successful completion means diagnostics were produced; it is not a converged 5 MPa branch.

| P (MPa/µm) | Δu (µm) | Last converged pressure (MPa) | 5 MPa? | Geometric gap near 5 MPa (µm) |
| ---: | ---: | ---: | :---: | ---: |
| 0.40 | 0.05 | 6.041 | Yes | −0.103630 at 4.9923 MPa |
| 0.40 | 0.025 | 4.645 | No | — |
| 0.45 | 0.05 | 5.406 | Yes | −0.093668 at 5.0724 MPa |
| 0.45 | 0.025 | 1.670 | No | — |
| 0.50 | 0.05 | 4.001 | No | — |
| 0.50 | 0.025 | 1.552 | No | — |

The P=0.45 nearest-state facet contact-pressure peak is 9.4586 MPa; maximum von Mises stress is 2.7426 MPa, and maximum principal Lagrange strain is 0.41273. The reconstructed geometric gap and FEBio contact gap are distinct quantities; the latter maximum is +0.06260 µm in this state.

## Lateral continuation pilot

With P=0.40/Δu=0.05 and an extended *measured* Al profile plus rubber, the 50 µm side padding reached only 2.452 MPa and the 100 µm padding reached only 0.906 MPa. Both then failed with negative Jacobians. Thus neither gives a 5 MPa central-window result or evidence that lateral continuation reduces overlap. The extended measured roughness changes the contact problem together with boundary distance; do not interpret the failed pilot as a measured elastic side stiffness. A follow-up needs an isolated compliant-side implementation or a convergent larger-domain setup.

Full results: [Stage A run 36397081948](https://github.com/ViktorSari/sealFE/actions/runs/36397081948), [lateral pilot run 36397671911](https://github.com/ViktorSari/sealFE/actions/runs/36397671911), [compact diagnostics 36401369180](https://github.com/ViktorSari/sealFE/actions/runs/36401369180). The P=0.45 third-mesh run is [36401573739](https://github.com/ViktorSari/sealFE/actions/runs/36401573739).
