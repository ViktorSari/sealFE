#!/usr/bin/env python3
"""B129 thickness sensitivity with controlled deep rubber grading.

Keeps the validated near-contact mesh unchanged through z=64 um, then
continues the deep mesh with a maximum vertical increment of 16 um up to
the requested rubber height. This isolates physical thickness/BC effects
from the very coarse 100->150 and 150->200 um layers used in the first sweep.
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.b129_stage1 import generate_model as gm


def controlled_z_levels(height_um: float) -> np.ndarray:
    base = [0.0, 1.5, 3.0, 4.5, 6.0, 9.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0]
    levels = [z for z in base if z < height_um]
    z = 64.0
    while z + 16.0 < height_um - 1e-12:
        z += 16.0
        levels.append(z)
    levels.append(float(height_um))
    levels = sorted(set(levels))
    return np.asarray(levels, dtype=float)


def main():
    gm.RUBBER_Z_LEVELS_UM = controlled_z_levels(gm.RUBBER_HEIGHT_UM)
    print(
        "Controlled thickness mesh: "
        f"height={gm.RUBBER_HEIGHT_UM} um, "
        f"z-levels={gm.RUBBER_Z_LEVELS_UM.tolist()}"
    )
    gm.main()


if __name__ == "__main__":
    main()
