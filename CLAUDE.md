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
- Keep notebook code student-readable: short cells, comments, no dense
  one-liners.
