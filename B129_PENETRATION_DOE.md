# B129: geometric overlap reduction DoE

## Objective and fixed baseline

Minimize reconstructed geometric overlap at **5 MPa nominal pressure**, conditional on a converged 0–5 MPa branch. Preserve K=2000 MPa (adopted), the augmented MR2 material, 0.75 µm near-contact mesh, 0.01 contact tolerance / 25 augmentations, 100 µm rubber thickness, and the same measured profile. A smaller overlap is useful only if the model still reaches 5 MPa and the pressure/reaction balance and mesh checks hold. Report both reconstructed geometric overlap and FEBio's contact-gap quantity; they are not interchangeable.

## Stage A: numerical contact DoE at the currently fixed side boundary

Two factors: contact penalty P (0.40, 0.45, 0.50 MPa/µm) and external displacement increment Δu (0.05, 0.025 µm). This is a 2×2 corner design with two center-penalty cases; it can show whether reducing the step rescues a higher penalty and whether the effects interact. The P=0.40/Δu=0.05 and P=0.50/Δu=0.05 runs already exist, so only four new cases are needed.

| P (MPa/µm) | Δu (µm) | Status before this DoE | Reason |
| ---: | ---: | --- | --- |
| 0.40 | 0.05 | completed, crosses 5 MPa | reference: ~0.104 µm overlap |
| 0.40 | 0.025 | new | smaller-step control |
| 0.45 | 0.05 | new | intermediate penalty |
| 0.45 | 0.025 | new | interaction/center penalty |
| 0.50 | 0.05 | completed, stops at 4.001 MPa | failed corner |
| 0.50 | 0.025 | new | test whether smaller steps rescue branch |

For every run record the last converged pressure, success at 5 MPa, overlap and FEBio contact gap at the nearest state, interpolated 5 MPa indentation, facet pressure peak/integral, von Mises and strain maxima, and negative-Jacobian location. Select the *lowest-overlap converged* candidate. For two candidates with close overlap, prefer the one with lower solver cost and stable local fields. Recheck the winner on the 0.375 µm mesh before replacing the established setting. A workflow marked successful because postprocessing ran does not imply the FEBio solve reached 5 MPa.

## Stage B: elastic continuation at the lateral edges

The rubber continues outside the 200 µm profile window, so two x-fixed edges are a limiting, overly rigid representation. A one-sided x roller previously changed the solution and stopped near 0.217 MPa; that is not a useful elastic-continuation model. Compare the Stage A winner and P=0.40 under the same compliant boundary implementation. A suitable implementation is to extend the rubber **and measured aluminium profile** by increasing the sampled window on both sides, keep the 200 µm B129 segment as the central observation window, and check convergence as the added width grows. The original 1000 µm `CA129_02.TXT` profile is available; its 400–600 µm slice matches the repository CSV exactly after the same constant z shift. Do not repeat or invent the edge trace. A periodic side constraint is a distinct representative-volume approximation and should be checked for compatibility with the nonperiodic measured endpoints; it is not automatically equivalent to a semi-infinite continuation.

For Stage B, compare added material widths (e.g. 100 and 200 µm each side) against the two x-fixed baseline with matched central mesh and pressure. Evaluate the central 200 µm contact fields, side displacements, reactions, and overlap. Extending the measured aluminium profile also changes the loaded surface; compare whole-window and central-window metrics separately. Only after the boundary response stabilizes should a physical contact result be selected. Do not call a lower overlap caused by a different side support a numerical contact improvement without separately assessing the changed deformation field.

The 0.103 µm overlap corresponds to about 3.0% of the 5 MPa indentation and 1.67% of this 200 µm trace's height range. These ratios describe scale; they are not an acceptance criterion. No zero-penetration or physically validated claim is made from them.
