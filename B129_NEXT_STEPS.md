# B129 Stage-1 continuation

Keep reference MR2 0.348/0.886 MPa, placeholder K=850 MPa, 1.5 um near-contact layers,
9 um transition, 0.30 MPa/um penalty, 0.1 um maximum step, uy=0, friction=0.
Do not smooth/alter the measured profile. Do not start sliding before user approval
and receipt/inspection of the complete material model.

1. Read current main and latest Actions runs. Run 86 is a reference reproduction
   with additional contact traction and nodal contact pressure outputs. Inspect
   its actual logs/artifacts on completion. Keep current work; do not reset main.
2. Validate new report on run 86 and check true traction orientation/integration.
   The run-81 report runs successfully and one final normal-stress map was visually
   inspected. Other plots and zero/fallback contact-output handling need review.
3. Inspect augmentation-limit acceptance and penetration. Perform separately
   labelled contact-tolerance convergence tests with one parameter changed at a
   time; compare same-pressure physical outputs, not survival endpoint.
   Completed locally for (tolerance,maxaug) = (0.01,25), (0.01,50),
   (0.0075,50), and (0.005,50). Raising maxaug to 50 removes forced acceptance
   with negligible 5 MPa changes. Tolerance tightening leaves global/stress
   outputs nearly unchanged but reduces penetration/gap by 20-50%; 0.005 stops
   at 2.43 MPa. Therefore local penetration/gap are not tolerance-converged.
   Use 0.01/50 for the next production reproduction and report the sensitivity;
   do not choose 0.0075 solely because it survives past 5 MPa.
   The local generator now defaults to 0.01/50. Run-86 reproduction remains
   available explicitly with `--contact-tolerance 0.01 --maxaug 25`.
4. Compare coarse/reference/fine under final MR2 at 0.5,1,2,3,4,5 MPa. Preserve
   reference mesh exactly. Vary near-surface vertical resolution first and then
   rubber x resolution independently; keep rigid measured profile unchanged.
   Report indentation, projected contact fraction, facet pressure maximum and
   representative stress/strain with percent differences. Do not infer convergence
   of local pressure from global indentation alone.
   Prepared vertical sequence: coarse 3.0 um, reference 1.5 um unchanged, fine
   0.75 um through the near-contact zone. The comparison script consumes each
   case's `B129_same_pressure_metrics.csv`; the independent rubber-x sweep remains
   a second phase and must not resample the measured rigid profile. The local
   dispatch-only matrix workflow generates all three vertical cases, preserves
   raw solves and compact reports separately, then builds the identical-pressure
   comparison. Reference generation is byte-identical to run 86 FEB input
   (`431ca93aa6be5c21bdf04d5af0c59828ef179b184951d06d7388e44292cd1210`)
   when generated explicitly with `--maxaug 25`; the production default is now
   the validated `maxaug=50` solver correction.
   The controlled vertical sweep has now been executed locally. All cases exceed
   5 MPa before negative-Jacobian termination. Global indentation/contact results
   are close, but P95 stress and strain are not vertically mesh-converged
   (maximum fine/reference deviations 12.60% and 14.47%). Keep this limitation;
   do not select the reference because its unrelated failure endpoint is highest.
   Next discretization phase is an independent rubber-x sweep without resampling
   or smoothing the measured rigid profile.
5. Separate model-form sensitivity (K, layer thickness, lateral constraints)
   from discretization errors. Baseline stays unchanged, variants are documented.
6. Improve efficiency with postprocess-only artifact replay and keyed FEBio cache;
   no full solve for plot-only edits. Workflow currently cancels an active main
   run on a new main push: wait for completion before integration.
7. Update run history with actual evidence, preserve numerical outputs and images,
   then stop at Stage 1 and report limitations. Never present inversion as physical
   failure or K=850 as measured. A green workflow is not scientific validation.
