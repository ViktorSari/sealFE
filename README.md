# sealFE

Finite-element models for sealing tribology.

## B129 Stage 1 — normal rough-contact baseline

The first model uses the measured B129 aluminium profile and a finite-strain rubber body in FEBio.

### Current setup

- profile: B129 / `CA129_02.TXT`, selected 200 µm window (400–600 µm in the original trace)
- profile pitch: 0.5 µm
- aluminium: rigid rough surface
- rubber: uncoupled Mooney–Rivlin
  - `C10 = 0.20 MPa`
  - `C01 = 0.65 MPa`
  - `K = 850 MPa` **temporary placeholder** until the measured compressibility / D parameter is supplied
- rubber depth: 100 µm
- nominal pressure ramp: 0 → 5 MPa
- contact: FEBio `sliding-elastic`, augmented Lagrange, two-pass
- prescribed Coulomb friction coefficient: 0

The zero interfacial Coulomb coefficient is deliberate: the final friction model is intended to obtain tangential resistance from physical contributions (viscoelastic hysteresis + adhesion, and any additional justified mechanism), not from an imposed global µ.

### Repository layout

```
models/b129_stage1/
  B129_400_600um_profile.csv
  generate_model.py

.github/workflows/
  run_b129_fem.yml
```

### GitHub Actions

The workflow:

1. installs Python and pinned pyFEBio,
2. generates `B129_stage1_normal_contact.feb`,
3. builds FEBio 4.13 from the official source with optional third-party solvers disabled,
4. uses FEBio's built-in `skyline` linear solver,
5. runs the nonlinear contact model,
6. uploads the FEBio input, log and `.xplt` output as an Actions artifact.

The source build is intentionally minimal so the repository does not depend on Intel MKL.

### Planned sequence

1. make the normal-contact model converge and mesh-check it,
2. compare 100 µm and 200 µm rubber depth,
3. refine the contact mesh if required,
4. add measured Prony terms and tangential sliding for hysteresis,
5. add an adhesive interface/contact-potential model,
6. extract the resulting tangential force rather than prescribe a macroscopic friction coefficient.
