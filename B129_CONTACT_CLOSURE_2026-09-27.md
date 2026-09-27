# B129 normal-contact numerical closure (in progress)

## Decision and scope

The volume-augmented MR2 model is treated as a nearly incompressible **modelling assumption**. Use K=2000 MPa for the final numerical setup; do not present K as a measured property. The completed K=2000/5000/10000 study found at most 0.032% difference in the 5 MPa indentation relative to K=5000. The current output examples used K=5000 and must be regenerated from the final setup.

The remaining question is numerical and geometric contact accuracy over 0.5–5 MPa. This note records the six K=5000 checks from [Actions run 36326762566](https://github.com/ViktorSari/sealFE/actions/runs/36326762566). Each comparison uses the same B129 profile and a 200 µm segment. The tabulated local fields come from the **nearest stored state** to 5 MPa; their actual nominal pressures differ, so their extrema are indicative and should not be described as exact pressure-matched convergence results.

| Case | Reached 5 MPa? | Interpolated indentation at 5 MPa (µm) | Nearest stored pressure (MPa) | Maximum true contact pressure at stored state (MPa) | Minimum geometric gap (µm) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1.5 µm vertical mesh, penalty 0.30 | Yes | 3.437056 | 4.8996 | 9.289 | −0.1353 |
| 0.75 µm vertical mesh, penalty 0.30 | Yes | 3.436981 | 5.1394 | 9.512 | −0.1407 |
| 0.75 µm vertical mesh, penalty 0.60 | Yes | 3.392474 | 4.9310 | 9.316 | −0.0727 |
| Left-side x roller only | No: stopped at 0.217 MPa | — | — | — | — |
| Search radius 10 µm | Yes | 3.437056 | 4.8996 | 9.289 | −0.1353 |
| Solver displacement/energy tolerances 0.005 | Yes | 3.437460 | 4.8135 | 9.203 | −0.1338 |

The refined mesh changes interpolated indentation by 0.000075 µm (0.0022%). Doubling the search radius reproduces the reference. Tightening the solver tolerance changes interpolated indentation by 0.000403 µm (0.0117%). On the refined mesh, doubling the penalty reduces the magnitude of the geometric penetration by about 48% at a nearby stored pressure, but changes the 5 MPa indentation by 0.04451 µm (1.30%). Thus the original penalty is not yet accepted for publication-quality local contact fields. The geometric gap and FEBio-reported contact gap have different definitions/sign conventions; report both, with method stated.

The one-sided roller case develops a very different deformation/contact configuration and fails to reach the target. The both-sides x rollers are therefore a consequential *physical boundary assumption*, not a harmless solver setting. The actual specimen support or a defensible representative-volume argument is needed before treating absolute contact fields as validated for the physical assembly.

## Follow-up already launched

[K=2000 contact closure run 36328698707](https://github.com/ViktorSari/sealFE/actions/runs/36328698707) uses identical geometry/contact settings with the 0.75 µm mesh and penalties 0.30, 0.60 and 1.20 MPa/µm, plus the 1.5 µm mesh at penalty 0.60. Evaluate all cases at matching nominal pressure, check convergence/failures and pressure equilibrium, then choose the lowest penalty that makes penetration sufficiently small without materially changing indentation/contact pressure. If those cases do not stabilize, the normal-contact model remains open. No sliding run has been started.
