# vessel-morphometry

Detect, measure, and vectorise stained xylem **vessels** in cross-sections of
**Mulga** (*Acacia aneura*), and compare vessel anatomy across a rainfall
gradient.

## Scientific aim

Xylem vessels are the pipes a tree uses to move water from root to leaf. Their
size and shape are a trade-off: wide vessels move a lot of water cheaply but are
more prone to drought-induced embolism, while narrow, round vessels are safer
but slower. We expect this trade-off to leave a fingerprint along a **rainfall
gradient**, so this project quantifies vessel area, shape, and packing density
from light-microscope images and asks how they change from wetter to drier
sites.

Each image is a 10× cross-section stained so that vessel lumens appear **cyan**
against **magenta** cell-wall tissue. Filenames encode the experiment:

```
SITE_GROUP_TREE_REP_10x.png      e.g. GUNDA_ACC_T4_1_10x.png
```

| Site    | Rainfall class |
|---------|----------------|
| `GUNDA` | **high**       |
| `NOCO`  | **moderate**   |
| `STURT` | **low**        |

(The code also maps the legacy spelling `NOCCO` to *moderate*.) `GROUP` is one of
three sampling groups — `ACC`, `SHED`, `OFF`; `TREE` and `REP` identify the
individual tree and the replicate section.

## Repository layout

```
vessel_morphometry/     the importable package (segment -> measure -> export)
  config.py             calibration constant + tunable Params
  segment.py            (green - red) Otsu segmentation -> label image
  measure.py            regionprops-based shape metrics + filename parsing
  export.py             CSV / labelled PNG / QC overlay / editable SVG
  find_bar.py           locate the white scale bar (verified; do not edit)
  calibrate.py          read the µm label + turn bar length into µm/px
scripts/
  calibrate_dataset.py  scan every plate -> outputs/calibration.csv + verdict
data/10x/               121 source PNGs  (READ-ONLY -- never modify)
notebooks/
  1_tutorial.ipynb      one image, explained end to end + two "under the hood" sections
  2_batch.ipynb         run every image -> outputs/all_vessels.csv + area_fraction.csv
  3_analysis.ipynb      cross-site / cross-rainfall statistics and figures
outputs/                everything the notebooks generate (git-ignored)
legacy/                 the original three notebooks + their CSV/PNG outputs (kept for reference)
```

## Install

The project uses [uv](https://docs.astral.sh/uv/). From the repo root:

```bash
uv venv                     # create .venv  (Python >= 3.10)
uv pip install -e .         # install vessel_morphometry + dependencies, editable
```

Quick check:

```bash
uv run python -c "import vessel_morphometry; print('ok')"
```

## Running the notebooks

Launch Jupyter (`uv run jupyter lab`) and open them in order — each one assumes
the previous has run:

1. **`notebooks/1_tutorial.ipynb`** — read this first. It walks one image
   (`GUNDA_ACC_T4_1_10x.png`) through every stage of the package and then opens
   up two ideas the package hides: how connected-component labelling works, and
   why the perimeter you choose changes circularity by ~38%.
2. **`notebooks/2_batch.ipynb`** — runs the pipeline over all 121 images and
   writes `outputs/all_vessels.csv` (one row per vessel) and
   `outputs/area_fraction.csv` (one row per image).
3. **`notebooks/3_analysis.ipynb`** — loads those CSVs and produces the
   cross-site / cross-rainfall distributions, summaries, and figures.

To run a notebook head-to-tail from the command line:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/1_tutorial.ipynb
```

## Calibration: pixels → microns

Each plate carries a thin near-white **scale bar** (usually vertical at the right
margin) with a "*N* µm" label. The reliable signal is the **bar's pixel length**,
not the often-blurry number: `µm/px = label_µm / bar_px`. Generate a calibration
table once:

```bash
uv run python scripts/calibrate_dataset.py        # writes outputs/calibration.csv
```

It measures every bar, best-effort-reads each label, and prints the headline
question — **is the scale constant or does it vary?** On this dataset it is
**constant at ~1.167 µm/px** (inter-quartile spread < 1%), so the many unreadable
labels do not matter: one value calibrates every plate. Each row is tagged `ok`,
`bar_only` (bar found, label unreadable), `no_bar`, or `outlier` (label disagrees
with the cohort — needs a look). Nothing is ever dropped, and no value is snapped
to a list of "expected" lengths.

**Reading the label uses OCR** (`rapidocr-onnxruntime`), which is **optional**:

- Enable it with `uv pip install -e ".[ocr]"` — pure pip, **no system binary**;
  the recognition models ship in the wheel (the first run may download and cache
  them). Then labels are read automatically and rows become `ok`.
- Without it, every bar is `bar_only`: the run still works and falls back to the
  constant ~1.167 µm/px. You can also type a value into the blank
  **`label_um_manual`** column of `outputs/calibration.csv` for any plate **that
  has a bar**; the batch prefers it (`label_um_manual / bar_px`) over everything
  else. (A `no_bar` plate has no pixel length, so a manual label there can't be
  used and the row keeps the cohort value.)

`2_batch.ipynb` reads `outputs/calibration.csv` and applies the per-image µm/px,
filling `area_um2` and the `*_um` columns. If the CSV is missing, it falls back to
the constant `CALIBRATION_UM_PER_PX["10x"]` in
[`config.py`](vessel_morphometry/config.py) (which ships as `None`, leaving
`area_um2` as `NaN`) and warns.

## Metric definitions

One row per vessel. Lengths are in **pixels** (suffix `_px`) unless calibrated.

| Column                        | Meaning |
|-------------------------------|---------|
| `area_px`                     | Lumen area = number of pixels in the vessel. |
| `area_um2`                    | Area in µm² (`NaN` unless calibrated). |
| `circularity`                 | `4·π·A / P²`, using the **Crofton** perimeter `P`. 1.0 = perfect circle; lower = more irregular. Tiny blobs can sit slightly above 1.0 from discretisation. |
| `diam_major_px`               | Major axis of the ellipse with the same second moments as the vessel. |
| `diam_minor_px`               | Minor axis of that fitted ellipse. |
| `feret_max_px`                | Maximum Feret diameter — the longest caliper distance across the lumen. |
| `equiv_diam_px`               | Diameter of a circle with the same area (`√(4A/π)`). |
| `aspect_ratio`                | `diam_minor / diam_major`. 1.0 = round, → 0 = elongated. |
| `eccentricity`                | Ellipse eccentricity. 0 = circle, → 1 = a line. |
| `solidity`                    | Area / convex-hull area. < 1 means dents/concavities in the outline. |
| `touches_border`              | `True` if the vessel touches an image edge (clipped → unreliable shape). |
| `cx`, `cy`                    | Centroid column/row (pixels). |
| `vessel_id`                   | Label id within its source image. |
| `source_image`, `site`, `group`, `rainfall` | Experiment metadata parsed from the filename. |

Per-image vessel packing comes from `vessel_area_fraction()`:
`vessel_fraction = vessel pixels / whole-image pixels` (note: the denominator is
the **whole image**, not just tissue — see the docstring before interpreting it
as a true within-tissue density).

## Changes from the original pipeline

This package replaces three ad-hoc notebooks (now in `legacy/`). Three fixes
matter scientifically:

- **Circularity corrected by ~38%.** The old code measured the perimeter by
  counting exposed pixel edges — a staircase that over-estimates a smooth curve
  by a factor of ~`4/π`. Because circularity divides by `P²`, that pulled every
  value down by roughly `(π/4)² ≈ 0.62`. We use scikit-image's **Crofton**
  perimeter, which is close to unbiased. On the tutorial image the median
  circularity moves from ~**0.55** (staircase) to ~**0.91** (Crofton) — a ~38%
  upward correction. The tutorial reproduces this side by side.
- **A `(green − red)` vessel detector.** The cyan stain is high in *both* green
  and blue, and the magenta tissue is high in *both* red and blue, so
  thresholding the **blue** channel (the old approach) can't cleanly separate
  them and under-captures vessel edges. On the `green − red` axis the two stains
  sit at opposite ends, so a single subtraction separates them and Otsu can pick
  the threshold automatically.
- **A correct DataFrame export.** The original stored pixel coordinates as
  stringified lists that had to be parsed back out, and metrics were appended
  inconsistently. Measurement now goes straight to a tidy one-row-per-vessel
  table with stable column names, ready for `pandas`.
