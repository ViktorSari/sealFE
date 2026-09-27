# B129 volumetric augmentation trial — 2026-09-27

## Decision

The augmented three-field MR2 model shows numerical bulk-parameter convergence for the **global indentation** from 0.5 to 5 MPa. With K = 2000, 5000, and 10000 MPa, the maximum spread of interpolated indentation at a common nominal pressure is 0.032% (at 5 MPa). K is an augmentation/penalty parameter in this comparison, not a measured bulk modulus. Use K = 5000 MPa as the representative trial for example output plots, pending the local-contact and mesh checks below. This is not a claim of pointwise J = 1.

| Nominal pressure (MPa) | K=2000 + aug indentation (µm) | K=5000 + aug (µm) | K=10000 + aug (µm) | Span relative to K=5000 |
| ---: | ---: | ---: | ---: | ---: |
| 0.5 | 2.779288 | 2.779075 | 2.779003 | 0.0103% |
| 1 | 3.301877 | 3.301616 | 3.300986 | 0.0270% |
| 2 | 3.392222 | 3.391786 | 3.391483 | 0.0218% |
| 3 | 3.407211 | 3.406694 | 3.406362 | 0.0249% |
| 4 | 3.421700 | 3.421417 | 3.421234 | 0.0136% |
| 5 | 3.438139 | 3.437056 | 3.437329 | 0.0315% |

Interpolated indentation uses the two adjacent converged reaction-pressure states. Local field summaries in the current artifacts use the nearest stored state, which may differ appreciably from the nominal target; do not interpret small differences in local maxima as a pressure-matched sensitivity result.

## Run evidence

- [Volumetric augmentation run #3](https://github.com/ViktorSari/sealFE/actions/runs/36324031328), commit `98d81f6a`: no-augmentation K=850 completed at 4.2 µm / 6.435381 MPa; augmented K=850 stopped at 3.410196 µm / 3.130370 MPa with negative Jacobian; augmented K=5000 stopped at 3.553048 µm / 11.977052 MPa with negative Jacobian.
- [Bracketing convergence run #1](https://github.com/ViktorSari/sealFE/actions/runs/36325181890), commit `960823af`: augmented K=2000 stopped at 3.523848 µm / 10.053928 MPa; augmented K=10000 stopped at 3.554610 µm / 12.159004 MPa. Both reached 5 MPa before the expected negative-Jacobian stability limit.
- The preceding run #2 failed in model generation because `\\b` in a raw regex did not match the self-closing rubber SolidDomain XML. PR #3 fixes the matcher. No physical geometry, contact or MR2 parameter was changed.

The non-augmented K=850 reference gives 4.014657 µm at 5 MPa, versus 3.437056 µm for augmented K=5000. Thus the old placeholder-based result is materially different (~14.4% in indentation); do not mix these configurations.

## Local checks still required

- The K=5000 augmented 5 MPa nearest stored state has Gauss-point J minimum ~0.9354, median ~0.999995, maximum ~1.0646. FEBio's three-field augmentation acts on **element-averaged** volume ratio, so pointwise J is not exactly unity. Check mesh sensitivity and local strains with the augmented material.
- The current postprocessor's local normal-pressure value is a first-layer `-σzz` proxy. Reprocess the active `rubber_bottom` XPLT contact traction/pressure field and verify force balance at equal pressure before publication plots.
- The 5 MPa geometric overlap is roughly 0.135 µm in the K=5000 case. Contact penetration/tolerance sensitivity remains separate from K convergence.
- Repeat the mesh and contact accuracy checks with the chosen augmented configuration. Do not infer physical bulk modulus from this numerical convergence.
