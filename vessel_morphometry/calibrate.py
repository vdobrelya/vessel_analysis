"""Scale-bar calibration: turn a plate's scale bar into microns-per-pixel.

Each 10x plate carries a thin near-white scale bar (usually vertical at the right
margin, sometimes horizontal) with a "<N> µm" label beside it. The RELIABLE
signal is the bar's pixel length (measured by find_bar.find_scale_bar). The
printed number is a bonus: it is often blurry or garbled, so OCR here is strictly
best-effort.

  µm/px = label_µm / bar_px        (when we can read the label)

OCR is OPTIONAL and uses rapidocr-onnxruntime (pure pip - no system binary). If it
or its models are unavailable, read_label simply returns no number and the caller
falls back to the cohort median (the `anchor`). Nothing here raises because OCR is
unavailable.

Colour order does not matter: the white-text detection compares the min/max across
channels, so BGR (OpenCV) and RGB give identical results.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from skimage.measure import label as cc_label

from .find_bar import find_scale_bar

# |per-image µm/px - cohort median| / median above this flags a row for review.
DEFAULT_OUTLIER_TOL = 0.20

# A single shared RapidOCR engine, created lazily on first use and cached (loading
# the ONNX models is slow, so we never build one per call - and importing the
# package stays cheap for the OCR-free notebooks). Stays None if rapidocr or its
# models are unavailable, so the pipeline degrades to bar-only.
_ENGINE = None
_ENGINE_TRIED = False


def _engine():
    """Return the shared RapidOCR instance, or None if it cannot be created."""
    global _ENGINE, _ENGINE_TRIED
    if _ENGINE_TRIED:
        return _ENGINE
    _ENGINE_TRIED = True
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    except Exception:
        _ENGINE = None        # not installed, or models could not be loaded
    return _ENGINE


def _drop_specks(mask, min_px=4):
    """Remove connected components of `min_px` pixels or fewer (stray sparkle)."""
    lab = cc_label(mask)
    sizes = np.bincount(lab.ravel())
    keep = sizes > min_px
    keep[0] = False                               # component 0 is the background
    return keep[lab]


def _label_crop(img, bbox, perp=230, along=30, upscale=5, edge_lo=150):
    """OCR-ready image of the label beside the bar (dark text on white), or None.

    The label text is white but anti-aliased, so the strict white_mask (tuned for
    the SOLID bar) keeps only broken glyph cores. Instead we render from the
    "whiteness" = min(R, G, B): white text scores high, coloured tissue scores low
    (one of its channels is always low). Mapping whiteness in [edge_lo, 255] to a
    grey ramp gives smooth dark-text-on-white that keeps the anti-aliased edges -
    what OCR engines expect. The strict mask is used only to LOCATE and tightly
    crop the label. Returns None if no text-like pixels are found.
    """
    H, W = img.shape[:2]
    r0, c0, r1, c1 = bbox
    vertical = (r1 - r0) >= (c1 - c0)
    if vertical:
        rr0, rr1, cc0, cc1 = r0 - along, r1 + along, c0 - perp, c1 + perp
    else:
        rr0, rr1, cc0, cc1 = r0 - perp, r1 + perp, c0 - along, c1 + along
    rr0, cc0 = max(0, rr0), max(0, cc0)
    rr1, cc1 = min(H, rr1), min(W, cc1)
    crop = img[rr0:rr1, cc0:cc1]
    if crop.size == 0:
        return None
    br0, bc0, br1, bc1 = max(0, r0 - rr0), max(0, c0 - cc0), r1 - rr0, c1 - cc0

    whiteness = crop.min(axis=2).astype(np.int16)   # white text high, coloured tissue low

    # Locate the label with the strict core mask (same idea as white_mask), then
    # drop the bar's own footprint and stray specks.
    core = whiteness > 170
    core[br0:br1, bc0:bc1] = False
    core = _drop_specks(core)
    if not core.any():
        return None

    # Smooth dark-on-white rendering that preserves anti-aliased edges.
    ramp = np.clip((whiteness - edge_lo) / (255 - edge_lo), 0, 1)   # 0..1, 1 = white text
    gray = (255 - ramp * 255).astype(np.uint8)      # dark text on a white field
    gray[br0:br1, bc0:bc1] = 255                    # blank the bar

    ys, xs = np.where(core)
    pad = 6
    y0, y1 = max(0, ys.min() - pad), min(gray.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(gray.shape[1], xs.max() + 1 + pad)
    gray = gray[y0:y1, x0:x1]                        # tight frame around the label

    gray = cv2.resize(gray, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(gray, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def read_label(img, bbox):
    """Best-effort OCR of the '<N> µm' label beside the bar.

    Returns (raw_str, um): `um` is an int ONLY when the recognised text contains
    exactly one clean 2-3 digit number (a clean scale label reads as a single
    number); any other count -> (raw_str, None). Never raises when rapidocr or its
    models are unavailable - it just returns (None, None) and the caller falls back
    to the cohort median.
    """
    ocr_img = _label_crop(img, bbox)
    if ocr_img is None:
        return None, None

    engine = _engine()
    if engine is None:                  # rapidocr not installed / models missing
        return None, None
    try:
        result, _ = engine(cv2.cvtColor(ocr_img, cv2.COLOR_GRAY2BGR))
    except Exception:
        return None, None
    if not result:
        return None, None

    raw = " ".join(text for _box, text, _score in result)
    matches = re.findall(r"\d{2,3}", raw)
    um = int(matches[0]) if len(matches) == 1 else None
    return raw, um


def apply_anchor(row, anchor, outlier_tol=DEFAULT_OUTLIER_TOL):
    """Fill in `um_per_px` and `status` given a base row and the cohort `anchor`.

    Pure arithmetic (no image work) so the dataset script can compute the cohort
    median first and then finalise every row without re-running OCR.

      ok        bar found + readable label, consistent with the cohort
      outlier   bar found + readable label, but far from the cohort median
      bar_only  bar found, no readable label   -> uses the anchor
      no_bar    no bar found                   -> uses the anchor
    """
    row = dict(row)
    if not row["bar_found"]:
        row["um_per_px"] = anchor
        row["status"] = "no_bar"
    elif row["label_um"] is not None:
        per = row["label_um"] / row["bar_px"]
        row["um_per_px"] = per
        if anchor is not None and abs(per - anchor) / anchor > outlier_tol:
            row["status"] = "outlier"
        else:
            row["status"] = "ok"
    else:
        row["um_per_px"] = anchor
        row["status"] = "bar_only"
    return row


def calibrate_image(img, anchor=None, *, outlier_tol=DEFAULT_OUTLIER_TOL):
    """Calibrate one image.

    Returns a dict with keys: bar_found, bar_px, orientation, bbox, label_ocr,
    label_um, um_per_px, status.

    `anchor` is the cohort median µm/px used when this image has no readable
    label (and to judge outliers); pass None to calibrate a single image on its
    own. No value is ever snapped to a list of "expected" bar lengths.
    """
    bar = find_scale_bar(img)
    if bar is None:
        base = dict(bar_found=False, bar_px=None, orientation=None, bbox=None,
                    label_ocr=None, label_um=None)
    else:
        raw, um = read_label(img, bar["bbox"])
        base = dict(bar_found=True, bar_px=bar["length_px"],
                    orientation=bar["orientation"], bbox=bar["bbox"],
                    label_ocr=raw, label_um=um)
    return apply_anchor(base, anchor, outlier_tol)


def cohort_anchor(rows, fallback=1.167):
    """Cohort µm/px = median(label_um / bar_px) over rows with a readable label.

    Returns (anchor, n_readable). Falls back to `fallback` (the measured 150 µm /
    128.5 px ≈ 1.167) when no labels could be read.
    """
    ratios = [r["label_um"] / r["bar_px"] for r in rows
              if r.get("label_um") is not None and r.get("bar_px")]
    if ratios:
        return float(np.median(ratios)), len(ratios)
    return float(fallback), 0


def um_per_px_lookup(calibration_csv, fallback_constant=None):
    """Build an image-stem -> µm/px map from a calibration.csv (TASK 3 wiring).

    Per image the value is resolved in this order:
        1. label_um_manual / bar_px   (a hand-entered label always wins)
        2. the um_per_px column        (only for trusted rows - NOT 'outlier')
        3. the cohort median           (outliers, unreadable, or missing rows)

    A row flagged `outlier` has a readable label that disagrees with the cohort, so
    its per-image µm/px is exactly the value not to trust; we use the robust cohort
    median for it instead (the user can still override any row via label_um_manual).

    Returns (lookup, default). The `default` (cohort median µm/px, computed over the
    non-outlier rows) is what callers use for images not present in the CSV. If the
    CSV is missing, returns ({}, fallback_constant) and warns, so the batch falls
    back to the single CALIBRATION_UM_PER_PX constant for every image.
    """
    path = Path(calibration_csv)
    if not path.exists():
        warnings.warn(
            f"{path} not found - falling back to the CALIBRATION_UM_PER_PX "
            f"constant ({fallback_constant}) for every image. "
            f"Run scripts/calibrate_dataset.py to generate it.")
        return {}, fallback_constant

    df = pd.read_csv(path, encoding="utf-8")    # label_ocr may contain 'µm'
    has_upp = "um_per_px" in df.columns
    has_status = "status" in df.columns

    # Cohort default = median µm/px over trusted rows (exclude flagged outliers).
    if has_upp:
        trusted = df.loc[df["status"] != "outlier", "um_per_px"] if has_status else df["um_per_px"]
        default = float(trusted.median()) if trusted.notna().any() else fallback_constant
    else:
        default = fallback_constant

    lookup = {}
    for _, r in df.iterrows():
        manual, bar_px = r.get("label_um_manual"), r.get("bar_px")
        is_outlier = has_status and r.get("status") == "outlier"
        if pd.notna(manual) and pd.notna(bar_px) and bar_px:
            value = float(manual) / float(bar_px)              # a hand-entered label wins
        elif has_upp and pd.notna(r.get("um_per_px")) and not is_outlier:
            value = float(r["um_per_px"])                      # trusted per-image value
        else:
            value = default                                    # outlier / unreadable / missing
        lookup[r["image"]] = value
    return lookup, default
