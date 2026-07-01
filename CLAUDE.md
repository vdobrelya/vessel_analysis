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
