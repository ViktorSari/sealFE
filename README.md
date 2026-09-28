# sealFE

Finite-element models for sealing tribology.

## B129 Stage 1: normal rough contact

The model presses a 100 µm thick Mooney–Rivlin rubber layer against a rigid measured B129 aluminium profile. The 200 µm profile window is sampled at 0.5 µm and extruded by 1 µm with plane-strain displacement constraints. The selected fit is `C10=0.348 MPa`, `C01=0.886 MPa`. Volume augmentation is active; `K=2000 MPa` is an adopted modelling assumption, not a measured material property. Nominal pressure is recovered from the top reaction. See [numerical closure](B129_CONTACT_CLOSURE_2026-09-27.md) for the sensitivity results and run artifacts.

| Final numerical setting | Value |
| --- | ---: |
| Near-contact layer | 0.75 µm |
| Sliding-elastic normal-contact penalty | 0.40 MPa/µm |
| Contact augmentation tolerance / max augmentations | 0.01 / 25 |
| External indentation increment | 0.05 µm |
| Target nominal-pressure range | 0–5 MPa |
| Lateral rubber boundary | `ux=0` on both x edges |
| Interface friction coefficient | 0 (normal-contact stage) |

The 0.40 penalty crosses 5 MPa on 1.5, 0.75 and 0.375 µm near-contact meshes. At nearby stored states around 5 MPa, the 0.75 and 0.375 µm meshes differ by at most 0.63% in the reported geometric overlap, facet contact-pressure peak, von Mises maximum and principal-strain maximum. The reconstructed geometric overlap approaches **0.103 µm**, rather than zero. Local fields are converged numerically for this boundary assumption; report that overlap explicitly.

The two fixed x edges are a consequential physical assumption for the isolated 200 µm window. The alternative one-sided roller case changed the deformation pattern and stopped below 0.22 MPa. That failure does **not** validate the two-sided constraint. Before interpreting absolute local contact fields as physical predictions for the assembly, establish from the actual rubber carrier and neighbouring material whether the two edges are laterally restrained. State an application-specific acceptable geometric-overlap criterion; current mesh convergence alone does not establish it.

The output workflow renders the selected `K=2000 MPa`, penalty-0.40 run only through 5 MPa, using the nearest stored converged states for field plots. The earlier `K=5000 MPa` example reaching about 12 MPa is superseded for this evaluation. The planned tangential sliding, time-dependent response and any adhesive interaction are separate stages.
