"""Turn a stained cross-section into a labelled image of vessel lumens.

The whole trick is one subtraction. The vessels are stained cyan (high GREEN and
high blue, low red); the surrounding tissue is magenta (high red and high blue,
low green). Blue is high in BOTH, so thresholding the blue channel - the old
approach - can't cleanly separate them and tends to under-capture the vessel
edge. But on the green-minus-red axis the two stains sit at opposite ends, so a
single (green - red) image separates them almost perfectly, and Otsu can pick
the threshold automatically.
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


def vesselness(image_bgr: np.ndarray) -> np.ndarray:
    """Single-channel image: cyan vessels bright, magenta tissue dark."""
    b, g, r = cv2.split(image_bgr.astype(np.int16))
    return np.clip(g - r, 0, 255).astype(np.uint8)


def segment(image_bgr: np.ndarray, p: Params = Params()) -> np.ndarray:
    """Return an int label image: 0 = background, 1..N = individual vessels."""
    v = vesselness(image_bgr)
    t = p.threshold if p.threshold is not None else threshold_otsu(v)

    mask = v > t
    mask = opening(mask, disk(1))           # remove single-pixel speckle
    mask = ndi.binary_fill_holes(mask)      # make lumens solid

    labels = _split_touching(mask, p) if p.use_watershed else label(mask)
    return _filter_by_area(labels, p)


def _split_touching(mask: np.ndarray, p: Params) -> np.ndarray:
    """Watershed split of vessels that touch (off by default; rarely needed)."""
    dist = ndi.distance_transform_edt(mask)
    coords = peak_local_max(dist, min_distance=p.ws_min_distance, labels=mask)
    peaks = np.zeros(dist.shape, dtype=bool)
    peaks[tuple(coords.T)] = True
    markers, _ = ndi.label(peaks)
    return watershed(-dist, markers, mask=mask)


def _filter_by_area(labels: np.ndarray, p: Params) -> np.ndarray:
    """Drop objects outside [min_area_px, max_area_px] and relabel 1..N."""
    counts = np.bincount(labels.ravel())
    keep = (counts > p.min_area_px) & (counts <= p.max_area_px)
    keep[0] = False                          # background is never a vessel
    return label(keep[labels])
