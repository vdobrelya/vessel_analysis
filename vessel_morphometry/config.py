"""Configuration for the vessel morphometry pipeline.

Three things live here so students only have to look in one place:
  * CALIBRATION_UM_PER_PX      - the microns-per-pixel for each objective.
  * MIN/MAX_VESSEL_DIAMETER_UM - the biological size window.
  * Params                     - the tunable knobs for segmentation/measurement/export.
"""
from __future__ import annotations
from dataclasses import dataclass

# Microns per pixel, by objective. This is a fixed property of the microscope +
# camera, not of any single image, so set it ONCE here. Leave a value as None to
# report pixels only (area_um2 will be NaN and the *_um columns are not produced).
#   um_per_px = (a known length in microns) / (that length measured in pixels)
CALIBRATION_UM_PER_PX = {
    "10x": 1.163,   # cohort median from scripts/calibrate_dataset.py (~1.163 µm/px)
}

# Biological size window on the equivalent diameter (microns). Applied in
# measure.py after converting to pixels via the image's µm/px, so it works on the
# calibrated and the constant-fallback paths alike.
#   MIN = 0.0  keeps EVERY vessel (segmentation no longer has an implicit size
#              bias); raise it to reproduce the old "large-vessels-only" output
#              e.g. MIN = 11.0 drops the smallest lumens.
#   MAX = 120.0 rejects implausibly large blobs - no real Acacia vessel exceeds
#              this, so it also removes the overexposed slide-background blob.
MIN_VESSEL_DIAMETER_UM = 0.0
MAX_VESSEL_DIAMETER_UM = 120.0


@dataclass
class Params:
    # --- segmentation ---
    threshold: int | None = None    # None -> Otsu on the min(green, blue) channel
    noise_floor_px: int = 20        # drop specks this size or smaller (FIXED; not biological)
    use_watershed: bool = False     # split touching vessels (rarely needed for these slides)
    ws_min_distance: int = 10       # watershed: min pixels between vessel centres

    # --- measurement ---
    um_per_px: float | None = None  # usually set from CALIBRATION_UM_PER_PX[mag]

    # --- export ---
    svg_simplify_px: float = 1.0    # polygon simplification tolerance (Douglas-Peucker)
    font_scale: float = 0.45        # id-number size on the labelled PNG
