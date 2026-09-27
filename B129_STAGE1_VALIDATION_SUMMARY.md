# B129 Stage-1 normal-contact validation summary

Date: 2026-09-27

## Scope and traceability

This summary closes the original frictionless normal-contact validation scope.
It does not include sliding, viscoelasticity, hysteresis, adhesion, or a revised
material model. The measured aluminium profile is unchanged.

- Remote `main` verified at `7c98a3183a771c7210b5c70d9593d84cfd243db7`.
- Latest verified reference workflow: [run 86](https://github.com/ViktorSari/sealFE/actions/runs/36261831686), input commit `2b29a37eb58461630736361a14bba3d1ddee605c`.
- The local validation branch and all commits after remote `main` are local only.
- Reference physics: MR2 C10=0.348 MPa, C01=0.886 MPa; placeholder K=850 MPa;
  100 um rubber; measured rigid Al profile; penalty 0.30 MPa/um; AUGLAG
  one-pass; uy=0; friction=0; maximum external increment 0.1 um.
- Final local solver recommendation: tolerance=0.01, gaptol=0, maxaug=50.
  Run 86 used maxaug=25 and forced acceptance only at the first loaded step.

## Reference result

Run 86 contains 319 converged stored states. Its last converged state is
5.152655765 um / 14.157748301 MPa; the following attempts terminate with a
negative rubber-element Jacobian. This is a numerical stability boundary, not
a physical failure prediction.

At interpolated 5 MPa:

| Quantity | Value |
| --- | ---: |
| Indentation | 4.014656899 um |
| Projected contact fraction | 1.000000 |
| Facet-average contact pressure maximum | 9.424362308 MPa |
| Maximum sampled vertical geometric penetration | 0.141203799 um |
| Maximum FEBio facet-average contact gap | 0.090393135 um |
| Maximum von Mises stress | 2.855902148 MPa |
| P95 von Mises stress | 1.181007912 MPa |
| Maximum principal Lagrange strain | 0.423546547 |
| P95 principal Lagrange strain | 0.151514836 |
| Contact-pressure/reaction mismatch | -0.00004295% |

Geometric penetration and FEBio facet-average gap are independent measures and
must not be equated. Run 86 exactly reproduces run 81 at every reported
0.5/1/2/3/4/5 MPa metric.

## Controlled vertical mesh sensitivity

Only the rubber vertical node sequence changed. All three cases reach 5 MPa
before negative-Jacobian termination.

| Case | Near-contact spacing | Elements | Last stable indentation | Last stable pressure |
| --- | ---: | ---: | ---: | ---: |
| coarse | 3.0 um | 4000 | 4.545358 um | 9.193136 MPa |
| reference | 1.5 um | 4800 | 5.152656 um | 14.157748 MPa |
| fine | 0.75 um | 6800 | 5.047650 um | 13.161693 MPa |

Fine/reference maximum absolute differences across the six target pressures:

| Quantity | Maximum absolute difference |
| --- | ---: |
| Indentation | 0.0772% |
| Projected contact fraction | 1.0955% |
| Facet-average pressure maximum | 2.3172% |
| Maximum von Mises stress | 2.8121% |
| Maximum principal Lagrange strain | 4.0459% |
| P95 von Mises stress | 12.6048% |
| P95 principal Lagrange strain | 14.4700% |

Global indentation and contact-pressure results are adequately stable for the
Stage-1 scope. P95 stress/strain are not vertically mesh-converged and must be
reported as a discretization limitation. Stability endpoints are non-monotonic
with mesh size and were not used to select a mesh.

## Contact convergence sensitivity

The first accepted loaded step of run 86 reached augmentation 26 with configured
maxaug=25 while the D-multiplier change was 0.0150706 > tolerance 0.01. No later
accepted step reached that limit.

| tolerance | maxaug | Last stable pressure | Maximum augmentation | Forced acceptance |
| ---: | ---: | ---: | ---: | ---: |
| 0.0100 | 25 | 14.157748 MPa | 26 | 1 |
| 0.0100 | 50 | 13.567010 MPa | 36 | 0 |
| 0.0075 | 50 | 8.372837 MPa | 42 | 0 |
| 0.0050 | 50 | 2.432740 MPa | 50 | 0 |

At 5 MPa, changing only maxaug from 25 to 50 changes indentation by -0.0114%,
pressure maximum by +0.0071%, penetration by -0.2396%, FEBio gap by -0.4995%,
and each reported stress/strain metric by at most 0.0057%. Therefore maxaug=50
is adopted locally to enforce natural augmentation convergence.

Changing tolerance from 0.0100 to 0.0075 at maxaug=50 changes global and
stress/strain results only slightly, but reduces the 5 MPa penetration by 22.74%
and FEBio gap by 23.56%. The 0.0050 run cannot reach 3 MPa and shows a further
38-52% reduction in penetration/gap through 0.5-2 MPa. Local penetration and
gap are therefore not contact-tolerance-converged. Tolerance 0.0075 is not
selected merely because it is the tightest tested value that survives 5 MPa.

## Output package and limitations

The postprocessor exports active `rubber_bottom` region-2 facet-average contact
pressure, reaction balance, separate geometric/FEBio gap measures, identical-
pressure metrics and percentage differences, undeformed/deformed mesh figures,
true x:z-scale deformed stress isolines, rubber surfaces every 0.5 um, and the
exact final surface CSV. All new local report figures were visually inspected;
the comparison-axis layout was corrected.

Remaining limitations for publication use:

1. K=850 MPa is a placeholder, not a measured bulk modulus.
2. Local penetration/gap are contact-tolerance-sensitive.
3. P95 stress/strain are not vertically mesh-converged.
4. Positive facet-average pressure over the full projected length does not prove
   full Gauss-point contact on every facet.
5. Negative-Jacobian termination is a numerical stability limit only.

The next independent discretization task, if required, is a rubber-x sweep that
does not resample or smooth the measured rigid profile. Material-form and
boundary-condition research remains after this original Stage-1 package.
