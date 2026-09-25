# B129 FEBio run history

All runs use displacement-controlled top loading and a maximum external displacement increment of 0.1 µm. Nominal pressure is the sum of top-node z reaction forces divided by the 200 µm × 1 µm nominal area, extracted from the last converged state in each .xplt artifact. The target is 0–5 MPa; a workflow failure means the nonlinear solve did not reach that run's displacement endpoint.

| Run | Commit | Change | Last converged indentation (µm) | Nominal pressure (MPa) | Failure |
| --- | --- | --- | ---: | ---: | --- |
| [20](https://github.com/ViktorSari/sealFE/actions/runs/36123025374) | f491a8a | Smaller adaptive substeps | 3.239496 | 0.587390 | Nonconvergence; negative element Jacobians in rubber |
| [21](https://github.com/ViktorSari/sealFE/actions/runs/36124271422) | e8c537e | 8 µm first rubber layer | 3.464444 | 1.046170 | Negative Jacobians near contact peaks; 10 retries exhausted |
| [22](https://github.com/ViktorSari/sealFE/actions/runs/36125836137) | 1d51909 | 12 µm first rubber layer | 3.445507 | 1.007336 | Negative Jacobians; reverted larger layer |
| [23](https://github.com/ViktorSari/sealFE/actions/runs/36126572704) | a47989b | 8 µm layer, lower contact penalty 0.30 MPa/µm | 3.539280 | 1.403586 | Negative Jacobians; 10 retries exhausted |
| [24](https://github.com/ViktorSari/sealFE/actions/runs/36127949288) | 072b96a | Penalty-only contact | 4.100000 | 0.052944 | Negative Jacobians; reaction dropped from 0.233375 MPa at 4.0 µm to 0.052944 MPa at 4.1 µm |
| [25](https://github.com/ViktorSari/sealFE/actions/runs/36129034075) | fae69c5 | Penalty-only contact, 4 µm first layers | 4.174442 | 0.052719 | Negative Jacobians; reaction dropped after 0.249056 MPa peak |

| [26](https://github.com/ViktorSari/sealFE/actions/runs/36130271562) | 108f652 | Augmented contact, 4 µm first layers | 3.604658 | 1.892250 | Negative Jacobians near the contact; 10 retries exhausted |

| [27](https://github.com/ViktorSari/sealFE/actions/runs/36131673698) | 836566e | Augmented contact, 2 µm first 8 µm layers | 4.084314 | 5.533784 | Negative Jacobians; 10 retries exhausted after 195 completed steps |

| [28](https://github.com/ViktorSari/sealFE/actions/runs/36133553574) | d9593dd | Augmented contact, 1 µm first 8 µm layers | 4.347901 | 7.651088 | Negative Jacobians; 10 retries exhausted after 238 completed steps |

| [29](https://github.com/ViktorSari/sealFE/actions/runs/36136572474) | 6d95f2d | 4.30 µm analysis endpoint | unavailable | unavailable | FEBio solve failed; large artifact could not be opened during workspace outage |
| [30](https://github.com/ViktorSari/sealFE/actions/runs/36139545062) | 14bdc5a | Same model; first diagnostic workflow | unavailable | unavailable | FEBio solve failed; diagnostic command also failed due to escaping error |
| [31](https://github.com/ViktorSari/sealFE/actions/runs/36139598947) | 4a0c5bc | Same model; corrected diagnostic | 4.299551 | 7.242593 | Negative Jacobians near time 1; 10 retries exhausted |
| [32](https://github.com/ViktorSari/sealFE/actions/runs/36142613762) | d984213 | 4.20 µm analysis endpoint; diagnostic still used stale 4.30 µm scale | 4.198549 | 6.495353 | Negative Jacobians near time 1; 10 retries exhausted |
| [33](https://github.com/ViktorSari/sealFE/actions/runs/36142657424) | 5ba663f | Same model; corrected diagnostic scale | 4.198549 | 6.495353 | Negative Jacobians near time 1; 10 retries exhausted |

| [34](https://github.com/ViktorSari/sealFE/actions/runs/36145346210) | 17623a8 | Extended linear displacement curve to time 2; 4.20 µm at analysis time 1 | 4.198549 | 6.495353 | Identical negative-Jacobian failure to run 33; curve extension reverted |

Penalty-only runs 24–25 have a load drop near failure and do not establish useful progress toward 5 MPa. Run 27 crosses 5 MPa between converged states (4.014428 µm, 4.999290 MPa) and (4.017837 µm, 5.025094 MPa). Linear interpolation gives 4.014521 µm at 5 MPa. Its converged nominal pressure increases monotonically over the stored states; the solve later fails by element inversion. Run 28 extends the monotonic branch to 4.347901 µm and 7.651088 MPa; the next attempted step (4.348470 µm) inverts rubber elements. A verification run will stop at 4.30 µm, inside the established converged interval. The bulk modulus (850 MPa) is a placeholder and absolute pressure predictions require material validation.

Runs 31–33 failed within 0.0015 µm of their respective endpoints. Run 34 tests whether extending the same linear load curve beyond analysis time 1 removes an endpoint discontinuity; the displacement at t=1 remains 4.20 µm.

After run 34, the model was restored to the best run-28 settings (50 µm search ramp, 1 µm contact-side layers). A replay with diagnostic pressure output is pending.
