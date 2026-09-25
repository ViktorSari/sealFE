# B129 FEBio run history

All runs use displacement-controlled top loading and a maximum external displacement increment of 0.1 µm. Nominal pressure is the sum of top-node z reaction forces divided by the 200 µm × 1 µm nominal area, extracted from the last converged state in each .xplt artifact. The target is 0–5 MPa; a workflow failure means the nonlinear solve did not reach the −50 µm displacement endpoint.

| Run | Commit | Change | Last converged indentation (µm) | Nominal pressure (MPa) | Failure |
| --- | --- | --- | ---: | ---: | --- |
| [20](https://github.com/ViktorSari/sealFE/actions/runs/36123025374) | f491a8a | Smaller adaptive substeps | 3.239496 | 0.587390 | Nonconvergence; negative element Jacobians in rubber |
| [21](https://github.com/ViktorSari/sealFE/actions/runs/36124271422) | e8c537e | 8 µm first rubber layer | 3.464444 | 1.046170 | Negative Jacobians near contact peaks; 10 retries exhausted |
| [22](https://github.com/ViktorSari/sealFE/actions/runs/36125836137) | 1d51909 | 12 µm first rubber layer | 3.445507 | 1.007336 | Negative Jacobians; reverted larger layer |
| [23](https://github.com/ViktorSari/sealFE/actions/runs/36126572704) | a47989b | 8 µm layer, lower contact penalty 0.30 MPa/µm | 3.539280 | 1.403586 | Negative Jacobians; 10 retries exhausted |
| [24](https://github.com/ViktorSari/sealFE/actions/runs/36127949288) | 072b96a | Penalty-only contact | 4.100000 | 0.052944 | Negative Jacobians; reaction dropped from 0.233375 MPa at 4.0 µm to 0.052944 MPa at 4.1 µm |
| [25](https://github.com/ViktorSari/sealFE/actions/runs/36129034075) | fae69c5 | Penalty-only contact, 4 µm first layers | 4.174442 | 0.052719 | Negative Jacobians; reaction dropped after 0.249056 MPa peak |

| [26](https://github.com/ViktorSari/sealFE/actions/runs/36130271562) | 108f652 | Augmented contact, 4 µm first layers | 3.604658 | 1.892250 | Negative Jacobians near the contact; 10 retries exhausted |

Penalty-only runs 24–25 have a load drop near failure and do not establish useful progress toward 5 MPa. The next experiment refines the first 8 µm to 2 µm layers while retaining augmented Lagrange contact. The bulk modulus (850 MPa) is a placeholder and absolute pressure predictions require material validation.
