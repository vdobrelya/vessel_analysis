"""Configuration for the vessel morphometry pipeline.

Two things live here so students only have to look in one place:
  * CALIBRATION_UM_PER_PX - the microns-per-pixel for each objective.
  * Params               - the tunable knobs for segmentation/measurement/export.
"""
from __future__ import annotations
from dataclasses import dataclass

# Microns per pixel, by objective. This is a fixed property of the microscope +
# camera, not of any single image, so set it ONCE here. Leave a value as None to
# report pixels only (the *_um columns will be NaN and the code will warn).
#   um_per_px = (a known length in microns) / (that length measured in pixels)
CALIBRATION_UM_PER_PX = {
    "10x": None,   # <-- fill in once known, e.g. 0.745
}


@dataclass
class Params:
    # --- segmentation ---
    threshold: int | None = None    # None -> Otsu on the (green - red) channel
    min_area_px: int = 30           # drop objects this size or smaller (stain texture)
    max_area_px: int = 4000         # drop implausibly large blobs (merged/torn vessels)
    use_watershed: bool = False     # split touching vessels (rarely needed for these slides)
    ws_min_distance: int = 10       # watershed: min pixels between vessel centres

    # --- measurement ---
    um_per_px: float | None = None  # usually set from CALIBRATION_UM_PER_PX[mag]

    # --- export ---
    svg_simplify_px: float = 1.0    # polygon simplification tolerance (Douglas-Peucker)
    font_scale: float = 0.45        # id-number size on the labelled PNG
