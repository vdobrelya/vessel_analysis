"""vessel_morphometry - detect, measure, and vectorise stained xylem vessels.

Quick start:
    import vessel_morphometry as vm
    df, fraction = vm.run("10x/GUNDA_ACC_T4_1_10x.png", out_dir="outputs")

For a step-by-step, explained walkthrough see notebooks/1_tutorial.ipynb.
"""
from __future__ import annotations

from pathlib import Path

import cv2

from .config import CALIBRATION_UM_PER_PX, Params
from .measure import measure, parse_name, vessel_area_fraction
from .segment import segment, vesselness, choose_channel
from .calibrate import calibrate_image, read_label, um_per_px_lookup
from . import calibrate, export

__all__ = [
    "Params", "CALIBRATION_UM_PER_PX",
    "segment", "vesselness", "choose_channel", "measure", "vessel_area_fraction",
    "parse_name", "calibrate", "calibrate_image", "read_label", "um_per_px_lookup",
    "export", "run",
]


def run(image_path, out_dir, p: Params = Params()):
    """Full pipeline on one image -> (DataFrame, area-fraction dict).

    Writes <stem>_vessels.csv, _labelled.png, _vessels.svg and _overlay.png.
    """
    image_path, out_dir = Path(image_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)

    labels = segment(img, p)
    df = measure(labels, img.shape, p, source=image_path.stem)

    stem = image_path.stem
    export.save_csv(df, out_dir / f"{stem}_vessels.csv")
    export.labelled_png(img, labels, df, out_dir / f"{stem}_labelled.png", p)
    export.vessel_svg(img, labels, df, out_dir / f"{stem}_vessels.svg", p)
    export.qc_overlay(img, labels, out_dir / f"{stem}_overlay.png")

    return df, vessel_area_fraction(labels)
