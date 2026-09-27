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

## Contact augmentation, step size, and intermediate penalty — follow-up

The earlier decision above describes the first sweep, not the current best-tested setting. [Augmentation/step run 36330795746](https://github.com/ViktorSari/sealFE/actions/runs/36330795746) halved the external displacement increment from 0.10 to 0.05 µm and tightened the contact multiplier tolerance from 0.01 to 0.003 (maxaug 25 to 40). All three fine-mesh cases stopped with negative Jacobians below 5 MPa: penalty 0.30 at 0.839 MPa, 0.40 at 0.486 MPa, and 0.45 at 0.433 MPa. The stricter multiplier setting is rejected.

[Step-isolation run 36332294094](https://github.com/ViktorSari/sealFE/actions/runs/36332294094) restored contact tolerance 0.01 and maxaug 25, retaining the 0.05 µm increment. On the 0.75 µm near-contact mesh, penalty 0.30 reached 8.387 MPa and penalty 0.40 reached 6.041 MPa before later termination. Both crossed the target 5 MPa. The model was ramped to a maximum 3.5 µm; the reported pressure is the last *converged*, not prescribed, endpoint.

| Penalty (MPa/µm), 0.75 µm mesh | Interpolated indentation at 5 MPa (µm) | Stored pressure near 5 MPa (MPa) | Minimum geometric gap (µm) | FEBio maximum contact gap (µm) | Facet peak pressure (MPa) | Max von Mises (MPa) | Max principal Lagrange strain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.30 | 3.437643 | 4.986713 | −0.136047 | 0.090563 | 9.359208 | 2.745159 | 0.413171 |
| 0.40 | 3.415479 | 4.992322 | −0.103630 | 0.069255 | 9.364594 | 2.743134 | 0.412827 |

The 0.40 setting reduces the magnitude of reconstructed geometric penetration by about 23.8% at the nearby stored states; interpolated indentation changes by −0.022164 µm (−0.645%). FEBio contact gap and geometric overlap use different definitions and signs. The facet contact pressure integral agrees with the reaction within 0.0001% at these states.

[Penalty/mesh run 36333363218](https://github.com/ViktorSari/sealFE/actions/runs/36333363218) tested 0.50 and 0.60 MPa/µm on the fine mesh and 0.40 on a 1.50 µm near-contact mesh, all with the original augmentation tolerance and 0.05 µm increments. The fine-mesh 0.50 and 0.60 cases stopped at 4.001 and 1.683 MPa, respectively. Coarse-mesh 0.40 reached 5.785 MPa. At its nearest stored state, 5.041572 MPa, the coarse-mesh 0.40 case has interpolated 5 MPa indentation 3.415220 µm, minimum geometric gap −0.104368 µm, facet peak pressure 9.458441 MPa, max von Mises 2.812834 MPa and max principal Lagrange strain 0.426490. Compared with the 0.75 µm mesh at 4.992322 MPa, the interpolated indentation differs by 0.008%, the gap magnitude by 0.7%, the facet peak pressure by 1.0%, von Mises maximum by 2.5% and strain maximum by 3.3%. The local maxima are **close-pressure**, not exact equal-pressure, comparisons; the stored pressures differ by 0.049 MPa.

**Interim numerical choice after two meshes:** K=2000 MPa, volume augmentation on, sliding-elastic contact with penalty 0.40 MPa/µm, contact multiplier tolerance 0.01/maxaug 25, 0.05 µm external increment, 0.75 µm near-contact layer. It is the strongest tested penalty that reaches 5 MPa on both meshes in this sweep. This choice still has approximately 0.104 µm reconstructed geometric overlap at 5 MPa. It is a bounded approximation, not zero penetration. Before presenting the local fields as physically validated, document the acceptable geometric-overlap criterion and justify the both-sides x roller boundary condition against the actual assembly. The third-mesh result and final numerical decision follow below.

## Third-mesh check and numerical decision

[Third-mesh run 36334416082](https://github.com/ViktorSari/sealFE/actions/runs/36334416082) repeated penalty 0.40, contact tolerance 0.01 and 0.05 µm increments with a 0.375 µm near-contact layer. It reached 5.502 MPa. The 5 MPa selected state was stored at 5.000319 MPa, allowing a close comparison to the 0.75 µm state stored at 4.992322 MPa. Full XPLT files remain in the run artifacts; [compact diagnostics run 36335429188](https://github.com/ViktorSari/sealFE/actions/runs/36335429188) records the selected values.

| Near-contact layer (µm) | Stored pressure (MPa) | Interpolated 5 MPa indentation (µm) | Minimum geometric gap (µm) | Facet peak pressure (MPa) | Max von Mises (MPa) | Max principal Lagrange strain |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.500 | 5.041572 | 3.415220 | −0.104368 | 9.458441 | 2.812834 | 0.426490 |
| 0.750 | 4.992322 | 3.415479 | −0.103630 | 9.364594 | 2.743134 | 0.412827 |
| 0.375 | 5.000319 | 3.415002 | −0.102978 | 9.363525 | 2.731443 | 0.410400 |

Between the 0.75 and 0.375 µm meshes, the interpolated indentation differs by 0.014%, geometric overlap magnitude by 0.63%, facet peak pressure by 0.011%, von Mises maximum by 0.43%, and principal-strain maximum by 0.59%. The extrema come from nearby, not exactly identical, stored pressures; the latter two differ by only 0.0080 MPa. The overlap approaches about 0.103 µm with refinement rather than zero. The Gauss-point maximum absolute relative-volume departure from one is 0.0581 on the third mesh, consistent with element-average rather than pointwise volume augmentation.

**Numerical closure for the stated 0–5 MPa load interval:** select the 0.40 MPa/µm penalty and the 0.75 µm near-contact mesh with 0.05 µm increments, contact multiplier tolerance 0.01 and maxaug 25. The finer third mesh supports the 0.75 µm outputs at the accuracy above. Report the approximately 0.103–0.104 µm geometric overlap as a model limitation, not as zero penetration. The numerical settings are specified and tested; **physical validation remains open** until the two-sided x-roller boundary condition is justified from the actual assembly and an acceptable overlap criterion is stated. The K=2000 MPa choice remains a modelling assumption and is not reopened here.
