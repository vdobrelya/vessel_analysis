"""Validate segmentation across the three lumen-colour regimes.

Runs segment + measure on a cyan plate, a white plate, and a washed-out white
plate and prints the vessel count and median equivalent diameter, then checks:

  * min(G, B) recovers WHITE lumens (the plates that used to return ~0 vessels);
  * the overexposed slide-background blob is rejected by MAX_VESSEL_DIAMETER_UM;
  * the white scale-bar annotation never survives as a vessel;
  * the cyan-reference count is tunable purely via MIN_VESSEL_DIAMETER_UM, with no
    implicit size bias baked into segmentation.

Run from the repo root:  uv run python scripts/validate_segmentation.py
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

import vessel_morphometry as vm
from vessel_morphometry import config
from vessel_morphometry.find_bar import find_scale_bar
from vessel_morphometry.segment import _blank_scale_bar

REPO = Path(__file__).resolve().parent.parent
SCALE = 1.163   # µm/px - constant across plates (see the calibration verdict)

PLATES = [
    ("GUNDA_ACC_T4_1_10x", "cyan reference"),
    ("STURT_SHED_T5_3_10x", "cyan / texture-prone"),
    ("GUNDA_ACC_T5_3_10x", "white lumens"),
    ("NOCO_ACC_T9_3_10x",  "white / washed-out"),
]


def measure_plate(name, min_um=0.0):
    """Segment + measure one plate at a given MIN_VESSEL_DIAMETER_UM."""
    img = cv2.imread(str(REPO / "data" / "10x" / f"{name}.png"))
    labels = vm.segment(img)
    previous = config.MIN_VESSEL_DIAMETER_UM
    config.MIN_VESSEL_DIAMETER_UM = min_um
    try:
        df = vm.measure(labels, img.shape, vm.Params(um_per_px=SCALE), source=name)
    finally:
        config.MIN_VESSEL_DIAMETER_UM = previous
    return img, df


def blanked_mask(img):
    """Boolean image of the pixels segment() blanks for the scale bar + label."""
    canvas = np.full(img.shape[:2], 255, np.uint8)
    bar = find_scale_bar(img)
    if bar is not None:
        _blank_scale_bar(canvas, bar)
    return canvas == 0


print(f"scale = {SCALE} µm/px | MAX = {config.MAX_VESSEL_DIAMETER_UM} µm | "
      f"study MIN = 11 µm\n")
print(f"{'plate':22s} {'regime':20s} {'channel':10s} {'n@MIN0':>7s} {'n@MIN11':>8s} {'med_dia':>8s}")
print("-" * 82)
for name, regime in PLATES:
    img, df0 = measure_plate(name, 0.0)
    _, df11 = measure_plate(name, 11.0)
    channel = vm.choose_channel(img)   # per-plate: g_minus_r (cyan) or min_gb (white)
    print(f"{name:22s} {regime:20s} {channel:10s} {len(df0):7d} {len(df11):8d} "
          f"{df0['equiv_diam_um'].median():6.1f}um")

# --- guard 1: NOCO's overexposed background blob (~264 µm) must be rejected ---
img, noco = measure_plate("NOCO_ACC_T9_3_10x", 0.0)
assert noco["equiv_diam_um"].max() < config.MAX_VESSEL_DIAMETER_UM, "background blob survived!"
print(f"\n[guard] NOCO background blob rejected: max diam "
      f"{noco['equiv_diam_um'].max():.1f}um < {config.MAX_VESSEL_DIAMETER_UM}um")

# --- guard 2: the scale-bar annotation never becomes a vessel ---
for name, _ in PLATES:
    img, df = measure_plate(name, 0.0)
    blank = blanked_mask(img)
    if not blank.any():
        print(f"[guard] {name}: no bar detected - nothing to blank")
        continue
    in_annotation = [(blank[int(r.cy), int(r.cx)]) for r in df.itertuples()]
    assert not any(in_annotation), f"{name}: a vessel centroid fell in the blanked annotation!"
    print(f"[guard] {name}: 0 of {len(df)} vessels sit in the blanked bar/label region")

# --- MIN tunability on the cyan reference (no implicit size bias) ---
print("\nGUNDA_ACC_T4_1 count vs MIN_VESSEL_DIAMETER_UM:")
for m in [0.0, 5.0, 11.0, 20.0]:
    _, df = measure_plate("GUNDA_ACC_T4_1_10x", m)
    print(f"   MIN = {m:5.1f} um -> {len(df):4d} vessels")
