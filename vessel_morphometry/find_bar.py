import numpy as np
from PIL import Image
from skimage.measure import label, regionprops


def white_mask(img, min_channel=170, max_sat=45):
    R, G, B = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    mn = np.minimum(np.minimum(R, G), B)
    mx = np.maximum(np.maximum(R, G), B)
    return (mn > min_channel) & ((mx - mn) < max_sat)


def find_scale_bar(img, min_len=40, max_thick=6, min_aspect=8, min_extent=0.7):
    """Return dict for the most bar-like white component, or None.

    The bar is long, thin, solid, and shorter than a full image border.
    Works for vertical or horizontal bars; orientation falls out of the bbox.
    """
    H, W = img.shape[:2]
    lab = label(white_mask(img))
    best = None
    for p in regionprops(lab):
        r0, c0, r1, c1 = p.bbox
        h, w = r1 - r0, c1 - c0
        long_, short_ = max(h, w), min(h, w)
        if short_ == 0:
            short_ = 1
        if (long_ >= min_len and short_ <= max_thick
                and long_ / short_ >= min_aspect
                and p.extent >= min_extent
                and long_ < 0.9 * max(H, W)):          # exclude full borders
            if best is None or long_ > best["length_px"]:
                best = {"length_px": int(long_),
                        "orientation": "vertical" if h > w else "horizontal",
                        "bbox": (r0, c0, r1, c1),
                        "thickness_px": int(short_),
                        "extent": round(float(p.extent), 3)}
    return best


if __name__ == "__main__":
    for path in ["/mnt/user-data/uploads/STURT_SHED_T11_3_10x.png",
                 "/mnt/user-data/uploads/GUNDA_ACC_T4_1_10x.png"]:
        img = np.array(Image.open(path).convert("RGB"))
        res = find_scale_bar(img)
        name = path.split("/")[-1]
        if res:
            print(f"{name}: bar FOUND  len={res['length_px']}px  "
                  f"{res['orientation']}  thick={res['thickness_px']}  "
                  f"extent={res['extent']}  bbox={res['bbox']}")
        else:
            print(f"{name}: no bar found")
