#!/usr/bin/env python3
"""Measured-profile continuation around the original B129 x=0..200 µm window."""
import os
from pathlib import Path
import numpy as np

from b129_mesh_sensitivity import z_levels
from models.b129_stage1 import generate_model as gm

PAD_UM = float(os.environ.get('B129_LATERAL_PAD_UM', '100'))
if PAD_UM not in (50.0, 100.0, 200.0):
    raise ValueError('B129_LATERAL_PAD_UM must be 50, 100, or 200')
PROFILE = Path(__file__).resolve().parents[1] / 'models/b129_stage1/B129_200_800um_profile.csv'

def profile():
    data = np.loadtxt(PROFILE, delimiter=',', skiprows=1)
    select = (data[:, 0] >= -PAD_UM) & (data[:, 0] <= 200 + PAD_UM)
    x, z = data[select].T
    if len(x) != round((200 + 2 * PAD_UM) / 0.5) + 1:
        raise ValueError('Measured continuation profile is incomplete')
    return x, z

if __name__ == '__main__':
    gm.NEAR_CONTACT_LAYER_UM = float(os.environ.get('B129_SURFACE_DZ_UM', '0.75'))
    gm.RUBBER_Z_LEVELS_UM = z_levels(gm.NEAR_CONTACT_LAYER_UM, gm.RUBBER_HEIGHT_UM)
    gm.load_profile = profile
    print('Measured B129 extension: pad each side', PAD_UM, 'µm')
    gm.main()
