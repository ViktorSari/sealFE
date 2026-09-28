#!/usr/bin/env python3
"""Controlled mesh variants for B129 publication convergence checks.

By default this wrapper preserves the measured piecewise-linear geometry and
all reference physics. It changes FE discretization:
- vertical rubber spacing in the first 6 um, and/or
- subdivision of each measured 0.5 um profile segment.

Subdividing x does not invent roughness; linear interpolation exactly preserves
the reference piecewise-linear profile geometry.

Optional Gaussian regularization changes the geometry and must be reported as
a separate sensitivity case, never as the unmodified measured profile.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.b129_stage1 import generate_model as gm

_ORIGINAL_LOAD_PROFILE = gm.load_profile


def refined_profile(subdiv: int):
    x, z = _ORIGINAL_LOAD_PROFILE()
    sigma = float(os.environ.get("B129_PROFILE_GAUSSIAN_SIGMA_SAMPLES", "0"))
    if sigma < 0:
        raise ValueError("Profile smoothing sigma must be nonnegative")
    if sigma > 0:
        radius = max(1, int(np.ceil(4 * sigma)))
        offsets = np.arange(-radius, radius + 1)
        weights = np.exp(-0.5 * (offsets / sigma) ** 2)
        weights /= weights.sum()
        smoothed = np.convolve(np.pad(z, radius, mode="edge"), weights, mode="valid")
        print(f"Measured-profile regularization: sigma={sigma} samples; "
              f"max |delta z|={np.max(np.abs(smoothed - z)):.6g} um; "
              f"RMS delta z={np.sqrt(np.mean((smoothed - z)**2)):.6g} um")
        z = smoothed
    if subdiv == 1:
        return x, z
    if subdiv < 1:
        raise ValueError("B129_X_SUBDIV must be >= 1")
    xr = []
    zr = []
    for i in range(len(x) - 1):
        for j in range(subdiv):
            f = j / subdiv
            xr.append(x[i] + f * (x[i + 1] - x[i]))
            zr.append(z[i] + f * (z[i + 1] - z[i]))
    xr.append(x[-1])
    zr.append(z[-1])
    return np.asarray(xr, dtype=float), np.asarray(zr, dtype=float)


def z_levels(surface_dz: float, height: float):
    if surface_dz <= 0:
        raise ValueError("B129_SURFACE_DZ_UM must be > 0")
    # Controlled refinement region: 0..6 um. Keep the current 9 um transition
    # and the same deeper grading so only the near-contact discretization changes.
    near = list(np.arange(0.0, 6.0 + 0.25 * surface_dz, surface_dz))
    near = [float(v) for v in near if v <= 6.0 + 1e-10]
    deep = [9.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0, 100.0, 150.0, 200.0]
    levels = sorted(set([v for v in near + deep if v < height] + [height]))
    return np.asarray(levels, dtype=float)


def main():
    surface_dz = float(os.environ.get("B129_SURFACE_DZ_UM", "1.5"))
    x_subdiv = int(os.environ.get("B129_X_SUBDIV", "1"))

    gm.NEAR_CONTACT_LAYER_UM = surface_dz
    gm.RUBBER_Z_LEVELS_UM = z_levels(surface_dz, gm.RUBBER_HEIGHT_UM)
    x_used, z_used = refined_profile(x_subdiv)
    np.savetxt(gm.HERE / "used_profile.csv", np.column_stack([x_used, z_used]),
               delimiter=",", header="x_um,z_um", comments="", fmt="%.9g")
    gm.load_profile = lambda: (x_used, z_used)

    print(f"Mesh sensitivity wrapper: dz={surface_dz} um, x_subdiv={x_subdiv}")
    print(f"Rubber z levels: {gm.RUBBER_Z_LEVELS_UM.tolist()}")
    gm.main()


if __name__ == "__main__":
    main()
