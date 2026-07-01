# Guidance for AI assistants working in this repo

- **`data/` is read-only source.** The PNGs in `data/10x/` are the original
  microscope images. Never modify them, and never write generated files into
  `data/`.
- **All generated files go to `outputs/`.** CSVs, labelled PNGs, overlays, and
  SVGs belong there (the folder is git-ignored apart from `.gitkeep`).
- **The `vessel_morphometry/` formulas have been reviewed.** Don't change the
  segmentation, measurement, or export logic — especially the metric
  definitions — without flagging it explicitly. If something looks wrong,
  surface it rather than editing silently.
- **`find_bar.py` (`find_scale_bar`, `white_mask`) is verified — use it as-is.**
  Calibration OCR (`calibrate.py`, rapidocr-onnxruntime) is **optional**: it must
  degrade to bar-only and never crash when rapidocr or its models are absent.
- Keep notebook code student-readable: short cells, comments, no dense
  one-liners.

## Potential improvements (not urgent — flag before doing)

- **Single source of truth for the linear metrics in `measure.py`.** The names
  `diam_major_px`, `diam_minor_px`, `feret_max_px`, `equiv_diam_px` are written
  twice — once in the unit-conversion loop and once in the `order` list — so the
  two can drift apart. Defining them once (e.g. a module-level list) and reusing
  it in both places would give a single source of truth.

## Pending notebook/doc cleanup (stale claims — verify when notebooks are re-run)

The three notebooks are committed **clean/unrun**. The package changed under them
(min(G,B)/adaptive channel, µm size window, 10x calibration now 1.163), so these
markdown/prose claims are stale. Cell indices are current; **do not edit numeric
claims blindly — re-run and re-read**.

Numeric claims to re-verify (count / circularity / per-image):
- `nb1` cell 0 & cell 32 — circularity medians "**0.55** (staircase) → **~0.91**
  (Crofton)" and the "**~38%**" correction.
- `nb2` cell 5 — scale "**~1.167**" (cohort median is ~1.163).
- `nb2` cell 13 — "**~12,000** total, a median of **~112** per image" (now far more
  at MIN=0); this bullet **also still names the removed `min_area_px` /
  `max_area_px`** (rename to `noise_floor_px` + `MIN`/`MAX_VESSEL_DIAMETER_UM`).
- `nb3` cell 17 — circularity "**0.8–0.9** … not down near **0.55**".
- (`nb2` "121 images" mentions are the fixed dataset size — fine.)

Stale method/config prose (not numeric):
- `nb1` cell 7 "Step 1 · The (green − red) channel" — the channel is now chosen
  **per plate** (G−R for cyan, min(G,B) for white); the tutorial's cyan image uses
  G−R, but the section should explain the adaptive choice.
- `nb1` cell 17 / `nb2` cell 5 / `README` — "area_um2 is NaN / ships as None": 10x
  calibration now ships as **1.163**, so `area_um2` is populated by default.
- `nb3` cell 21 — "set CALIBRATION_UM_PER_PX['10x'] …": already set.
- `nb3` cell 6 — the `50–3000 px` analysis window vs the new 11–120 µm cutoff.
