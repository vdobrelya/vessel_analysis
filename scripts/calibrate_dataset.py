"""Measure the scale bar on every 10x plate and write outputs/calibration.csv.

The headline question this answers: is the image scale (µm per pixel) CONSTANT
across plates, or does it VARY? If constant, the often-unreadable printed labels
do not matter - one value calibrates everything. If it varies, we need a label
(or a manual entry) per image.

    µm/px = label_µm / bar_px

The bar length is reliable; the printed label is read best-effort with rapidocr
(optional). Images with no bar, or a bar but no readable label, are flagged and
kept - never dropped. Edit the blank `label_um_manual` column to correct or
supply a label by hand; the measure step prefers it.

Run from the repo root:  uv run python scripts/calibrate_dataset.py
"""
from __future__ import annotations

import csv
import warnings
from pathlib import Path

import cv2
import numpy as np

from vessel_morphometry.calibrate import apply_anchor, calibrate_image, cohort_anchor

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "10x"
OUT = REPO / "outputs" / "calibration.csv"
MAG = "10x"
FALLBACK_UM_PER_PX = 1.167          # measured: 150 µm / ~128.5 px
CONSTANT_IQR_PCT = 5.0              # IQR <= this % of the median -> call it constant

COLUMNS = ["image", "mag", "bar_found", "bar_px", "orientation", "bbox",
           "label_ocr", "label_um", "um_per_px", "status", "label_um_manual"]


def scan(paths, progress=True):
    """Pass 1: find the bar and best-effort-read the label for each image.

    An unreadable image file is recorded as a no-bar row rather than crashing the
    whole run (the spec requires images are never dropped).
    """
    rows = []
    for n, path in enumerate(paths, 1):
        img = cv2.imread(str(path))
        if img is None:
            warnings.warn(f"could not read {path}; recording as no_bar")
            row = dict(bar_found=False, bar_px=None, orientation=None, bbox=None,
                       label_ocr=None, label_um=None)
        else:
            row = calibrate_image(img, anchor=None)   # anchor unknown yet
        row["image"] = path.stem
        rows.append(row)
        if progress and (n % 20 == 0 or n == len(paths)):
            print(f"  scanned {n}/{len(paths)}")
    return rows


def finalize(rows, fallback=FALLBACK_UM_PER_PX):
    """Pass 2: compute the cohort anchor, then fill um_per_px + status per row."""
    anchor, n_readable = cohort_anchor(rows, fallback=fallback)
    rows = [apply_anchor(r, anchor) for r in rows]
    return rows, anchor, n_readable


def summarize(rows, anchor, n_readable):
    """Print the per-status counts and the constant-vs-variable verdict."""
    n = len(rows)
    counts = {s: sum(r["status"] == s for r in rows)
              for s in ("ok", "outlier", "bar_only", "no_bar")}
    n_flagged = counts["no_bar"] + counts["bar_only"] + counts["outlier"]

    print("\n" + "=" * 64)
    print("CALIBRATION SUMMARY")
    print("=" * 64)
    print(f"images            : {n}")
    print(f"bar_found         : {sum(r['bar_found'] for r in rows)}")
    print(f"label_read        : {n_readable}")
    print(f"flagged (review)  : {n_flagged}  "
          f"(no_bar={counts['no_bar']}, bar_only={counts['bar_only']}, "
          f"outlier={counts['outlier']})")

    # Judge constancy from the CONSISTENT labels only (status 'ok'), so a few
    # garbled-but-confident reads (flagged 'outlier') cannot skew the verdict.
    ok = [r for r in rows if r["status"] == "ok"]
    print("\n--- is the scale constant across plates? ---")
    if len(ok) >= 2:
        ratios = np.array([r["label_um"] / r["bar_px"] for r in ok])
        med = float(np.median(ratios))
        q1, q3 = np.percentile(ratios, [25, 75])
        iqr = q3 - q1
        pct = 100 * iqr / med if med else float("nan")
        print(f"median µm/px           : {med:.4f}  "
              f"(from {len(ok)} consistent labels; {counts['outlier']} outliers excluded)")
        print(f"label/bar_px IQR       : {q1:.4f} - {q3:.4f}")
        print(f"spread (IQR / median)  : {iqr:.4f} = {pct:.1f}%")
        if pct <= CONSTANT_IQR_PCT:
            print(f"\n=> scale appears CONSTANT (use one value, ~{med:.3f} µm/px, for all plates)")
            print("   The unreadable labels do NOT matter - the bar length alone calibrates.")
        else:
            print("\n=> scale VARIES (per-image labels needed)")
            print("   Unreadable labels DO matter - fill label_um_manual for flagged plates.")
    elif n_readable >= 1:
        print(f"only {n_readable} readable label(s) ({counts['outlier']} flagged outlier) "
              f"- too few consistent labels to judge the spread.")
        print(f"cohort µm/px (median of readable): {anchor:.4f}")
    else:
        print(f"median µm/px           : using fallback {anchor:.4f} (no labels read)")
        print("\n=> cannot judge constant-vs-variable without readable labels.")
        print('   Install the OCR extra (uv pip install -e ".[ocr]"), or fill')
        print("   label_um_manual in the CSV, then re-run.")
    return counts


def write_csv(rows, path=OUT):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            bbox = r["bbox"]
            w.writerow({
                "image": r["image"],
                "mag": MAG,
                "bar_found": r["bar_found"],
                "bar_px": "" if r["bar_px"] is None else r["bar_px"],
                "orientation": r["orientation"] or "",
                "bbox": "" if bbox is None else " ".join(map(str, bbox)),
                "label_ocr": r["label_ocr"] or "",
                "label_um": "" if r["label_um"] is None else r["label_um"],
                "um_per_px": "" if r["um_per_px"] is None else round(r["um_per_px"], 4),
                "status": r["status"],
                "label_um_manual": "",      # user-editable; blank by default
            })


def main():
    paths = sorted(DATA.glob("*.png"))
    print(f"scanning {len(paths)} images in {DATA} ...")
    rows = scan(paths)
    rows, anchor, n_readable = finalize(rows)
    if n_readable == 0:
        print(f'WARNING: no labels could be read (is the [ocr] extra installed? '
              f'uv pip install -e ".[ocr]"). '
              f"Using the fallback {FALLBACK_UM_PER_PX} µm/px for every image.")
    write_csv(rows)
    summarize(rows, anchor, n_readable)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
