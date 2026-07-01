"""Measure each vessel and parse experimental metadata from filenames.

A note on circularity, because it bit the original code. Circularity is
    circularity = 4 * pi * Area / Perimeter**2
which is 1.0 for a perfect circle and lower for irregular shapes. The catch is
the perimeter: if you count exposed pixel edges (a staircase around the blob),
you OVER-estimate the true boundary length by a factor of about 4/pi, and since
circularity divides by perimeter squared, that drags every value down by ~38%.
We use skimage's Crofton perimeter estimate, which integrates boundary crossings
over several directions and is close to unbiased. Discretisation can still nudge
very small blobs slightly above 1.0 - that is expected, not an error.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

from . import config
from .config import Params

# Site code -> rainfall class, used by the cross-site analysis.
RAINFALL = {"GUNDA": "high", "NOCO": "moderate", "NOCCO": "moderate", "STURT": "low"}


def parse_name(stem: str) -> tuple[str, str, str]:
    """'GUNDA_ACC_T4_1_10x' -> ('GUNDA', 'ACC', 'high')."""
    parts = stem.split("_")
    site = parts[0] if parts else ""
    group = parts[1] if len(parts) > 1 else ""
    return site, group, RAINFALL.get(site, "")


def measure(labels, image_shape, p: Params = Params(), source: str | None = None) -> pd.DataFrame:
    """One row per vessel with shape metrics; empty frame if nothing detected."""
    if labels.max() == 0:
        return pd.DataFrame()

    props = regionprops_table(
        labels,
        properties=(
            "label", "area", "perimeter_crofton", "centroid",
            "axis_major_length", "axis_minor_length", "feret_diameter_max",
            "equivalent_diameter_area", "eccentricity", "solidity", "bbox",
        ),
    )
    df = pd.DataFrame(props)

    # circularity from the (less-biased) Crofton perimeter; guard against P == 0
    per = df["perimeter_crofton"].replace(0, np.nan)
    df["circularity"] = 4 * np.pi * df["area"] / per ** 2

    # aspect ratio: 1.0 = round, -> 0 = elongated (minor / major ellipse axis)
    df["aspect_ratio"] = df["axis_minor_length"] / df["axis_major_length"]

    # whole vs cut-off: a vessel clipped by the image edge has unreliable shape
    H, W = image_shape[:2]
    df["touches_border"] = (
        (df["bbox-0"] == 0) | (df["bbox-1"] == 0)
        | (df["bbox-2"] == H) | (df["bbox-3"] == W)
    )

    df = df.rename(columns={
        "label": "vessel_id", "area": "area_px",
        "centroid-0": "cy", "centroid-1": "cx",
        "axis_major_length": "diam_major_px", "axis_minor_length": "diam_minor_px",
        "feret_diameter_max": "feret_max_px", "equivalent_diameter_area": "equiv_diam_px",
    })

    # real-world units, if calibrated
    if p.um_per_px:
        s = p.um_per_px
        df["area_um2"] = df["area_px"] * s * s
        for c in ["diam_major_px", "diam_minor_px", "feret_max_px", "equiv_diam_px"]:
            df[c.replace("_px", "_um")] = df[c] * s
    else:
        df["area_um2"] = np.nan

    # --- biological size filter (equivalent diameter, microns) ---
    # Convert the µm bounds to a pixel bound with this image's µm/px: per-image if
    # calibrated, else the config constant. MIN = 0 keeps everything (segmentation
    # has no implicit size bias now); MAX rejects over-large blobs such as the
    # overexposed slide background. Size alone decides here - border-touching
    # vessels are kept (only flagged). Skipped when no scale is available at all.
    scale = p.um_per_px or config.CALIBRATION_UM_PER_PX.get("10x")
    if scale:
        lo_px = config.MIN_VESSEL_DIAMETER_UM / scale
        hi_px = config.MAX_VESSEL_DIAMETER_UM / scale
        df = df[(df["equiv_diam_px"] >= lo_px) & (df["equiv_diam_px"] <= hi_px)].copy()

    # experimental metadata
    if source is not None:
        site, group, rainfall = parse_name(source)
        df["source_image"], df["site"], df["group"], df["rainfall"] = source, site, group, rainfall

    order = ["source_image", "vessel_id", "circularity", "area_px", "area_um2",
             "diam_major_px", "diam_major_um", "diam_minor_px", "diam_minor_um",
             "feret_max_px", "feret_max_um", "equiv_diam_px", "equiv_diam_um",
             "aspect_ratio", "eccentricity", "solidity", "touches_border",
             "site", "group", "rainfall", "cx", "cy"]
    cols = [c for c in order if c in df.columns]
    return df[cols].sort_values("vessel_id").reset_index(drop=True)


def vessel_area_fraction(labels) -> dict:
    """Fraction of the image occupied by vessel lumens.

    NOTE: this is vessels / WHOLE IMAGE, not vessels / cell-wall tissue - the
    denominator includes background and mounting medium. For a true within-tissue
    vessel density you must mask the section outline first.
    """
    vessel_px = int((labels > 0).sum())
    return {"vessel_px": vessel_px, "image_px": labels.size,
            "vessel_fraction": vessel_px / labels.size}
