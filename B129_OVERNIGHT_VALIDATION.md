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

## Review — 2026-09-28 (initial six-case run completed)

Run [36347015295](https://github.com/ViktorSari/sealFE/actions/runs/36347015295), source dace0f6. All six artifacts and compact comparison 10941527425 reviewed against solver stdout. Only the reference terminated normally. Five sensitivity solves ended with negative Jacobians in failed Newton iterates and exhausted retries; these are numerical failures, not physical pressure limits. Accepted last states have positive Gauss-point J.

| Case | Solver termination | Monotonic covered p (MPa) | u at 5 MPa (um) | u at 0.1 MPa (um) |
| --- | --- | ---: | ---: | ---: |
| reference_clean | normal | 0–5.371275 | 3.415275 | 1.413246 |
| free_sides | negative Jacobian / retries | 0–0.142501 | unavailable | 2.410305 |
| elastic_E_over_H | negative Jacobian / retries | 0–0.206325 | unavailable | 1.981088 |
| elastic_10E_over_H | negative Jacobian / retries | 0–0.575896 | unavailable | 1.536349 |
| profile_refined_x2 | negative Jacobian / retries | 0–3.361506 | unavailable | 1.413910 |
| depth_200um | negative Jacobian / retries | 0–1.296806 | unavailable | 1.419123 |

Indentations interpolated only inside monotonic stored histories. At 3 MPa reference and x2 indentation are 3.391683 and 3.391895 um (0.00624% difference); this alone does not establish field convergence or 5 MPa mesh independence.

### Local fields at each case's LAST accepted pressure (not equal-load comparisons)

Contact ratio below is the projected positive FEBio contact-pressure length divided by the nominal 200 um width. Overlap is the magnitude of the most negative **facet-averaged vertical gap** on facets wholly within the measured profile; it is not a pointwise penetration maximum.

| Case | Actual p (MPa) | Contact ratio | In-profile overlap (um) | Peak facet p (MPa) | Max von Mises (MPa) | Max principal Lagrange strain | Gauss J range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| reference_clean | 5.371275 | 1.0000 | 0.110089 | 9.753605 | 2.744051 | 0.412985 | 0.942250–1.057724 |
| free_sides | 0.142501 | 0.1801 | 0.040755 | 2.079779 | 1.199778 | 0.159624 | 0.964368–1.035624 |
| elastic_E_over_H | 0.206325 | 0.2152 | 0.051513 | 2.487941 | 1.382968 | 0.187178 | 0.934508–1.065486 |
| elastic_10E_over_H | 0.575896 | 0.4400 | 0.096594 | 4.032954 | 2.192022 | 0.317444 | 0.931817–1.068085 |
| profile_refined_x2 | 3.361506 | 1.0000 | 0.077663 | 7.865975 | 2.752198 | 0.415309 | 0.946152–1.053832 |
| depth_200um | 1.296806 | 0.8347 | 0.086819 | 5.511878 | 2.703809 | 0.405910 | 0.952701–1.047292 |

The absolute contact-integral/top-reaction mismatch at these final states is below 0.000054%. This checks the vertical contact force integral, not every local equilibrium residual. The reference's nearest stored state to 5 MPa is 4.932195 MPa, with peak facet pressure 9.304257 MPa; do not describe these as exact 5 MPa local values.

### Postprocessing correction and spring audit

Found endpoint clamping in numpy.interp when lateral expansion moves rubber nodes beyond the finite measured aluminium profile. Original whole-profile geometric gaps/contact fractions for free and elastic cases are invalid. Reader corrected in commit 1f43c4a: outside-profile samples become NaN, whole-profile geometric metrics are unavailable, and separate in-profile extrema plus coverage are emitted. Synthetic in-range/out-of-range checks passed, and corrected final-state geometry recomputed from all six original XPLTs. Original downloadable artifacts remain historical, uncorrected outputs; the in-profile overlap table above supersedes their free/elastic geometric overlap values.

| Case | Fully covered facets | Excluded edge facets |
| --- | ---: | ---: |
| free_sides | 98.25% | 7/400 |
| elastic_E_over_H | 98.75% | 5/400 |
| elastic_10E_over_H | 99.25% | 3/400 |

Spring runtime audit from final XPLT + FEB: anchor/rubber z-displacement mismatch exactly zero at stored precision; reconstructed total absolute horizontal spring forces 17.263136 and 98.635866 MPa*um^2 for weak/strong support; reconstructed vertical spring forces zero. Stress array has 6400 entries for 6400 rubber elements in both cases: no extra spring stress domain mixed in. Finite profile edge escape is also a model limitation for interpreting free-side results.

### One targeted follow-up, not a parameter sweep

Run [36369381426](https://github.com/ViktorSari/sealFE/actions/runs/36369381426), commit 962e5118, retries **only profile_refined_x2**, reducing external increment 0.05 to 0.01 um (and the linked minimum step); original 3.5 um endpoint and all physical/contact/material settings unchanged. Logs show iterative divergence/negative Jacobians after a positive-J accepted state and exhausted cutbacks. This bounded step-path test may improve continuation; success is not assumed. No reference duplication; no new K study.

Next check: inspect B129-targeted-profile_refined_x2_step001 and comparison artifacts, normal/error termination, 5 MPa coverage and same-pressure fields. If this one retry still fails, record it as unresolved mesh/solver robustness and do not repeat blindly. Free/elastic/depth failures remain unresolved; no evidence yet justifies their physical finalization. No full physical validation: support stiffness is unmeasured and overlap acceptance is unapproved.
