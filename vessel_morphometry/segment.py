"""Turn a stained cross-section into a labelled image of vessel lumens.

The separation channel is **min(green, blue)** - the "not-magenta" invariant. The
surrounding tissue is magenta (high red and blue, but LOW green), so it is the
only thing with weak green; min(G, B) therefore stays HIGH for any bright lumen -
whether it photographed **cyan** (high green + blue) or **white** (high in every
channel) - and LOW for tissue.

The old channel, clip(green - red), only lit up *cyan* lumens: on plates where the
lumens came out white, green ≈ red so green - red ≈ 0, Otsu collapsed, and the
plate returned almost no vessels. min(G, B) fixes that while still separating
cyan from magenta.

Only a small FIXED pixel noise floor is applied here; the biological size window
lives in measure.py, where microns-per-pixel is known.
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.filters import threshold_otsu
from skimage.measure import label
from skimage.morphology import disk, opening
from skimage.segmentation import watershed

from .config import Params
from .find_bar import find_scale_bar

# Blanking of the scale-bar annotation: pad this many pixels around the bar (its
# thin axis) and reach this far toward the image interior to cover the adjacent
# "<N> µm" label. White label text is pixel-identical to a white lumen, so only
# location can reject it.
_BAR_PAD_PX = 15
_LABEL_REACH_PX = 90


def vesselness(image_bgr: np.ndarray) -> np.ndarray:
    """Single-channel image: bright lumens (cyan OR white) high, magenta tissue low.

    min(G, B) is high only where BOTH green and blue are high - true of cyan and
    white lumens - and low for magenta tissue, which is weak in green.
    """
    b, g, r = cv2.split(image_bgr.astype(np.int16))
    return np.minimum(g, b).astype(np.uint8)


def _blank_scale_bar(v: np.ndarray, bar: dict) -> None:
    """Zero out the scale bar and its adjacent label in `v` (in place), so the
    white annotation can never be thresholded into vessels.

    Pads the bar's thin axis by _BAR_PAD_PX and reaches _LABEL_REACH_PX toward the
    image interior (the side the label sits on - away from the margin the bar hugs).
    """
    H, W = v.shape
    r0, c0, r1, c1 = bar["bbox"]
    rr0, rr1 = r0 - _BAR_PAD_PX, r1 + _BAR_PAD_PX
    cc0, cc1 = c0 - _BAR_PAD_PX, c1 + _BAR_PAD_PX
    if bar["orientation"] == "vertical":
        if c0 < W - c1:                 # bar hugs the LEFT edge -> label is to the right
            cc1 += _LABEL_REACH_PX
        else:                           # bar hugs the RIGHT edge -> label is to the left
            cc0 -= _LABEL_REACH_PX
    else:                               # horizontal bar
        if r0 < H - r1:                 # bar hugs the TOP -> label is below
            rr1 += _LABEL_REACH_PX
        else:                           # bar hugs the BOTTOM -> label is above
            rr0 -= _LABEL_REACH_PX
    v[max(0, rr0):min(H, rr1), max(0, cc0):min(W, cc1)] = 0


def segment(image_bgr: np.ndarray, p: Params = Params()) -> np.ndarray:
    """Return an int label image: 0 = background, 1..N = individual vessels."""
    v = vesselness(image_bgr)

    # Blank the scale bar + its label BEFORE thresholding, if one is present.
    bar = find_scale_bar(image_bgr)     # channel-order invariant; safe on BGR
    if bar is not None:
        _blank_scale_bar(v, bar)

    t = p.threshold if p.threshold is not None else threshold_otsu(v)
    mask = v > t
    mask = opening(mask, disk(1))       # remove single-pixel speckle
    mask = ndi.binary_fill_holes(mask)  # make lumens solid

    labels = _split_touching(mask, p) if p.use_watershed else label(mask)
    return _drop_small(labels, p.noise_floor_px)


def _split_touching(mask: np.ndarray, p: Params) -> np.ndarray:
    """Watershed split of vessels that touch (off by default; rarely needed)."""
    dist = ndi.distance_transform_edt(mask)
    coords = peak_local_max(dist, min_distance=p.ws_min_distance, labels=mask)
    peaks = np.zeros(dist.shape, dtype=bool)
    peaks[tuple(coords.T)] = True
    markers, _ = ndi.label(peaks)
    return watershed(-dist, markers, mask=mask)


def _drop_small(labels: np.ndarray, min_px: int) -> np.ndarray:
    """Drop connected components smaller than `min_px` and relabel 1..N.

    This is only a FIXED noise floor (stain speckle); biological size limits are
    applied later in measure.py, in microns.
    """
    counts = np.bincount(labels.ravel())
    keep = counts >= min_px
    keep[0] = False                          # background is never a vessel
    return label(keep[labels])
