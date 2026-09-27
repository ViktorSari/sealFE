# B129 normal-contact numerical closure (open)

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

## K=2000 MPa contact and mesh sweep — 2026-09-27

[Actions run 36328698707](https://github.com/ViktorSari/sealFE/actions/runs/36328698707) completed all four jobs and uploaded full-resolution XPLT and diagnostic CSV artifacts. The workflow jobs succeeded because postprocessing completed; **all four FEBio solves terminated after their last converged state with negative element Jacobians**. The stored nominal-pressure histories are monotonic. The integrated FEBio facet contact pressure agrees with top reaction within 0.015% at the 0.5 and 1 MPa selected states. The 5 MPa branch is available only at penalty 0.30.

| Mesh near contact | Penalty (MPa/µm) | Highest converged pressure (MPa) | Reached 5 MPa? | Interpolated indentation at 1 MPa (µm) | Geometric minimum gap near 1 MPa (µm) | FEBio facet peak pressure near 1 MPa (MPa) | Max von Mises near 1 MPa (MPa) | Max principal Lagrange strain near 1 MPa |
| --- | ---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| 0.75 µm | 0.30 | 8.85695 | Yes | 3.30041 | −0.12378 | 5.1894 | 2.6416 | 0.3942 |
| 0.75 µm | 0.60 | 4.41073 | No | 3.28016 | −0.06722 | 5.1501 | 2.6222 | 0.3914 |
| 0.75 µm | 1.20 | 1.87533 | No | 3.26788 | −0.03449 | 5.1103 | 2.5972 | 0.3871 |
| 1.50 µm | 0.60 | 3.44074 | No | 3.27891 | −0.06907 | 5.2848 | 2.7217 | 0.4106 |

The local metrics in this table come from the nearest **converged stored state** to 1 MPa, at actual nominal pressures 1.00637, 0.99656, 0.97899 and 1.01813 MPa in row order. Indentation alone is interpolated to exactly 1 MPa. They are close-pressure comparisons, not exact equal-pressure field convergence. The same order at the 0.5 MPa selected states has actual pressures 0.49251, 0.48159, 0.47701 and 0.49389 MPa. Their interpolated indentations are 2.77741, 2.75600, 2.75266 and 2.75568 µm; geometric minimum gaps are −0.10507, −0.05485, −0.03959 and −0.05348 µm. The contact pressure peaks are 3.7429, 3.7083, 3.7165 and 3.8720 MPa, respectively. Contact pressure, stress and strain are outputs of the converged XPLT states, not analytical proxies.

At 1 MPa, changing the fine-mesh penalty from 0.30 to 0.60 roughly halves geometric penetration while changing interpolated indentation by 0.02025 µm (0.61%). Changing 0.60 to 1.20 roughly halves penetration again, but the high-penalty run loses the branch below 2 MPa. With penalty 0.60, mesh refinement changes the 1 MPa indentation by 0.00125 µm (0.038%); the facet peak pressure changes by 2.55%, von Mises maximum by 3.8%, and maximum principal Lagrange strain by 4.9% at the nearby stored pressures. These local figures cannot establish 0.5–5 MPa convergence because neither penalty-0.60 run reaches 5 MPa.

The sole 5 MPa crossing is the fine-mesh penalty-0.30 case: interpolated indentation 3.43780 µm. Its nearest stored state is 5.12814 MPa with minimum geometric gap −0.13995 µm, FEBio facet peak contact pressure 9.5060 MPa, maximum von Mises stress 2.7461 MPa and maximum principal Lagrange strain 0.4133. These are **5.128 MPa state values**, not exact 5 MPa field values. Positive FEBio contact gap and negative reconstructed geometric gap use different definitions; the latter measures overlap of the deformed faceted surfaces.

**Decision:** No contact-penalty/mesh combination in this sweep has both small penetration and a converged 0.5–5 MPa branch. Retain penalty 0.30 on the fine mesh only as a provisional branch for global indentation; do not treat its local pressure/stress/strain fields as publication-ready. No final numerical contact setting is proposed. The both-sides x rollers remain a separate unresolved physical boundary assumption: the one-sided run stopped at 0.217 MPa and cannot validate the both-sides condition. No sliding run has been started, and no further K sweep is planned.
