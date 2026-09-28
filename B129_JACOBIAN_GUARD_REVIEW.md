# B129 Jacobian-guarded continuation — 2026-09-28

User authorized continuation of remaining validation. Previous results: B129_OVERNIGHT_VALIDATION.md. New run: https://github.com/ViktorSari/sealFE/actions/runs/36376712962 (workflow commit eccdcf54956aa0202710209f25be3694bcd5f8c8).

## Evidence-based numerical change

The failed solves have positive-J last accepted states and negative Jacobians during Newton trials. FEBio v4.13 FECore/FENewtonSolver.cpp exposes ls_check_jacobians; FECore/FELineSearch.cpp defaults it to false. When enabled, UpdateModel catches NegativeJacobianDetected and halves the Newton line-search scale (bounded by lsiter). It also avoids the unguarded below-lsmin fallback to scale 0.5. This is a targeted nonlinear continuation remedy, not another external-step sweep or a material failure claim.

Only ls_check_jacobians changes from 0 to 1. Existing lsiter=10, lsmin=0.001 and all material/contact/mesh settings remain. Six cases reproduce the prior endpoints and external increments; x2 uses its latest 0.01 um retry, other cases 0.05 um. The reference is rerun to check that the guarded path reproduces the accepted response. K stays 2000 MPa. No solver-source modification beyond existing diagnostic print limits.

Local checks: YAML parsed; six case settings checked; XML edit on an actual saved FEB model changed only the guard flag, with exact round-trip comparison after reverting it. Local solver execution was unavailable. CI must verify parsing and actual behavior.

## Review gates

- Inspect solver termination and timeout separately from workflow status; sensitivity jobs retain failed partial results.
- Compare each guarded case to its corresponding prior unguarded history only within common pressure coverage. Check reference reproduction and whether each case reaches 5 MPa.
- Audit contact integral/top reaction balance, positive Gauss J, contact fraction, local pressure/stress/strain and in-profile geometric overlap. Check augmentation warnings and forced acceptance too.
- Local extrema at nearest stored pressure must retain actual pressure labels. No extrapolation. Free-side edge escape and unmeasured spring stiffness remain model limitations.
- If guarding still fails, diagnose before any further change. No automatic parameter sweep or duplicate running jobs.
- If guarding succeeds, mesh/depth/support comparisons still require analysis; it does not establish physical validation or eliminate the approximately 0.11 um overlap.

Status: submitted, awaiting results. The existing hourly review is resumed for this run and must stop after reporting its results.
