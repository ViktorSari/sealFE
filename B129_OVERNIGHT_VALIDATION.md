# B129 overnight validation — 2026-09-27

## Scope and prior state

The user authorized continuation of numerical finalization, all three lateral-support regimes, and additional justified overnight checks. Source branch: `codex/b129-contact-closure`, commit `add6037` (see B129_CONTACT_CLOSURE_2026-09-27.md). Do not repeat the K sweep: use K=2000 MPa with volumetric augmentation as the established modelling assumption.

The completed vertical mesh study at penalty 0.40 MPa/um and 0.05 um increments supports a 0.75 um first-layer mesh. Comparing 0.75 and 0.375 um: 5 MPa indentation differs 0.014%; nearby-state peak contact pressure 0.011%, maximum von Mises 0.43%, maximum principal Lagrange strain 0.59%. Geometric overlap persists around 0.103 um. This is NOT zero penetration and no physical acceptance threshold has been agreed.

## New cases

| Case | Support in x | Rubber depth (um) | Profile subdivisions | Endpoint (um) |
| --- | --- | ---: | ---: | ---: |
| reference_clean | both-side rollers | 100 | 1 | 3.42 |
| free_sides | one top-centre anchor, otherwise free | 100 | 1 | 50 |
| elastic_E_over_H | side springs, k_s=0.07404 MPa/um | 100 | 1 | 50 |
| elastic_10E_over_H | side springs, k_s=0.7404 MPa/um | 100 | 1 | 20 |
| profile_refined_x2 | both-side rollers | 100 | 2 | 3.5 |
| depth_200um | both-side rollers | 200 | 1 | 5.0 |

All cases retain uy=0 (plane strain), C10=0.348 MPa, C01=0.886 MPa, K=2000 MPa, volumetric atol=0.01, contact penalty 0.40 MPa/um, contact tolerance 0.01/maxaug 25, external increment <=0.05 um, solver dtol/etol=0.01. The 3.42 um reference endpoint is chosen just beyond the prior 5 MPa crossing (3.41548 um) but below its last converged indentation. Changed endpoint changes normalized time stepping, so reproduction must be checked rather than assumed.

The two elastic stiffnesses are exploratory, NOT measured assembly stiffness. Scale: infinitesimal incompressible E=6(C10+C01)=7.404 MPa; E/H=0.07404 MPa/um for H=100 um. Each side node has spring constant k_s*A_tributary, with half-thickness y weights and trapezoidal z weights. Springs stay horizontal: auxiliary anchors have fixed x,y and z constrained to follow the corresponding rubber node. Thus these supports contribute no intentional vertical reaction. Their total tributary area is verified as 100 um^2 per side. No centre x anchor is retained for elastic cases because the springs restrain translation.

Longer free/elastic endpoints search for a 5 MPa crossing, not equal-displacement comparisons. These cases may terminate early; that is not proof of physical impossibility. Each solver has a 95-minute cap, each job a 120-minute cap, with two cases in parallel.

## Required review

1. Distinguish workflow success, solve_outcome, valid postprocessing, and reached_5MPa. Only reference_clean has a strict successful-solve gate; sensitivity artifacts preserve useful earlier converged states.
2. Verify springs pass FEBio parsing and produce nonzero lateral restraint without vertical support force. If their XPLT adds extra stress domains, select the rubber domain explicitly; never silently mix spring or rigid data.
3. Compare indentation at equal nominal pressures by interpolation only within monotonic converged history. Existing local extrema correspond to nearest stored pressure; do not label them exact pressure-matched values.
4. For x refinement and depth, examine force balance, overlap, contact fraction, pressure peaks, stress/strain and J, using actual state pressures. Do not infer mesh convergence merely from reaction/indentation.
5. For boundary cases that fail early, diagnose logs before changing physics. At most a targeted step/contact remedy based on that diagnosis; no blind parameter sweep or renewed K study.
6. No final physical acceptance until support applicability and overlap tolerance are resolved. User requested all support regimes, not selection of an actual one.
7. Keep reports/code on this GitHub branch. Main and the earlier working branch are untouched. Save standalone deliverables to Library if produced.

## Reproducibility

`studies/b129_boundary_study.py` builds cases using the existing measured geometry. FEBio XML conventions checked against official v4.13 source: FEBioXML/FEBioBoundarySection3.cpp (linear constraint), FEBioXML/FEBioDiscreteSection.cpp (discrete material), FEBioXML/FEBioMeshSection4.cpp (DiscreteSet), FEBioMech/FESpringMaterial.cpp (spring force/stiffness). Local checks passed for roller/free/elastic boundary XML, spring count, tributary stiffness, Python compilation, workflow structure, and aggregation against four existing diagnostics artifacts. Runtime spring behavior still requires the actual solver run.

`studies/b129_overnight_summary.py` collects compact CSV/text evidence into `B129-overnight-comparison`; full XPLT and model/log files are retained in each case artifact for 30 days.
