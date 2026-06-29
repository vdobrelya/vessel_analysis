"""Write outputs: CSV, a labelled PNG, a QC overlay, and a scalable SVG.

The SVG is the one worth explaining. It embeds the original image and draws one
editable polygon per vessel on top, plus the id number. Because it is vector, you
can open it in a browser, Inkscape or Illustrator, recolour outlines, nudge a
vertex, or pull the polygons out - it is the automated stand-in for hand-tracing
the vessels, which is what this whole pipeline replaced.
"""
from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np
from skimage.color import label2rgb
from skimage.segmentation import find_boundaries

from .config import Params

YELLOW_BGR = (0, 255, 255)


def save_csv(df, path) -> None:
    df.to_csv(path, index=False)


def labelled_png(image_bgr, labels, df, path, p: Params = Params()) -> None:
    """Original image + vessel outlines + id number at each centroid."""
    canvas = image_bgr.copy()
    canvas[find_boundaries(labels, mode="outer")] = YELLOW_BGR
    for _, row in df.iterrows():
        x, y, txt = int(row.cx), int(row.cy), str(int(row.vessel_id))
        # black halo then white fill so ids read on any background
        cv2.putText(canvas, txt, (x - 6, y + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    p.font_scale, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(canvas, txt, (x - 6, y + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    p.font_scale, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(path), canvas)


def qc_overlay(image_bgr, labels, path) -> None:
    """Each vessel in a distinct colour - a quick visual check of segmentation."""
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    over = (label2rgb(labels, image=rgb, alpha=0.4, bg_label=0) * 255).astype(np.uint8)
    over[find_boundaries(labels, mode="outer")] = (255, 255, 0)
    cv2.imwrite(str(path), cv2.cvtColor(over, cv2.COLOR_RGB2BGR))


def vessel_svg(image_bgr, labels, df, path, p: Params = Params()) -> None:
    """Scalable vector overlay: image + one editable polygon and id per vessel."""
    H, W = labels.shape
    png_bytes = cv2.imencode(".png", image_bgr)[1].tobytes()
    b64 = base64.b64encode(png_bytes).decode()

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        f'<image href="data:image/png;base64,{b64}" width="{W}" height="{H}"/>',
        '<g fill="none" stroke="yellow" stroke-width="1.5">',
    ]
    for vid in df["vessel_id"].astype(int):
        mask = (labels == vid).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            simplified = cv2.approxPolyDP(contour, p.svg_simplify_px, True).reshape(-1, 2)
            pts = " ".join(f"{x},{y}" for x, y in simplified)
            parts.append(f'<polygon points="{pts}"/>')
    parts.append('</g><g fill="white" font-size="11" font-family="sans-serif">')
    for _, row in df.iterrows():
        parts.append(f'<text x="{row.cx:.0f}" y="{row.cy:.0f}">{int(row.vessel_id)}</text>')
    parts.append("</g></svg>")

    Path(path).write_text("\n".join(parts))
