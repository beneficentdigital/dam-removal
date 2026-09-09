# River Barrier Detection — Spain Pilot, EU Scale-Up

Reference brief for Dam Removal Europe: building a satellite-based pipeline to find undocumented river barriers (dams, weirs/azudes) in Spain, then extending across Europe.

## The problem, in numbers
No single reliable count exists. Depending on source:

| Source | Count | Covers |
|---|---|---|
| SEPREM (large dam registry) | 1,254 | Large regulated dams only (>15m) |
| SNCZI/MITECO national inventory | ~5,100 "presas" | Registered water-impounding dams |
| SNCZI/MITECO, all barriers | ~29,882 | Presas + registered azudes |
| AMBER Barrier Atlas (pan-European) | part of 629,955 across 36 countries | Compiled from existing databases + field-validated |
| Dam Removal Europe estimate for Spain | ~171,203 | Statistical extrapolation from field survey density, not geolocated |
| AMBER's estimate, all Europe | 1,000,000+ | Statistical extrapolation, not geolocated |

Important distinction: AMBER's 629,955 figure IS a real geo-referenced database (location, type, height per record). The larger estimates (171,203 for Spain; 1M+ for Europe) are NOT — they come from a random forest regression model trained on field-survey density data (2,715km of river walked across 147 rivers), predicting barrier density per sub-catchment. No GPS coordinates exist for the gap between recorded and estimated totals. That gap is what this project targets.

## Ground truth / baseline data (free, open)
- **SNCZI/MITECO** — national dam inventory, shapefile (ETRS89), CC-attribution license. sig.miteco.gob.es/snczi
- **Andalucía regional inventory** — Agencia Andaluza del Agua + CEDEX + REDIAM combined, includes azudes, updated 2022. Coverage primarily Guadalquivir basin — check whether it extends to Axarquía's Mediterranean-draining rivers.
- **AMBER Barrier Atlas** — 629,955 geo-referenced barriers, 36 countries incl. Spain and the Western Balkans (Albania, Bosnia, Montenegro, North Macedonia, Serbia). amber.international/european-barrier-atlas
- **AMBER Barrier Tracker app** — existing citizen-science verification tool, feeds into Dam Removal Europe's ongoing reporting. Useful as a verification loop for new detections.
- **GRanD / Global Dam Watch** — ~7,400 dams globally, but only >15m or >0.1km³ reservoir — misses small barriers entirely.
- **OpenStreetMap** — crowdsourced `waterway=weir`/`weir=yes` tags. Independent cross-check, not a primary source.

## Licensing (checked during planning, 2026-09-09)
- **AMBER Barrier Atlas** — confirmed **CC-BY-4.0** on Figshare (DOI
  10.6084/m9.figshare.12629051) — redistributable with attribution.
- **PNOA** — free for any legitimate purpose; sole obligation is
  acknowledging IGN as the source.
- **SNCZI/MITECO** — open under Spain's public-sector information reuse
  law (Ley 37/2007) via the MITECO Open Data Portal; attribution expected.
- **Andalucía regional inventory** (Agencia Andaluza del Agua + CEDEX +
  REDIAM) — **not yet confirmed**. Verify before the pilot's output CSV
  is shared publicly — see plan.md Risks.

## Reference / scaffold layers
- **EU-Hydro** (Copernicus/EEA) — pan-European river network, free, open, all EEA countries. Being upgraded to 2.0. Use as the scaffold to know where to run detection rather than scanning blindly. Note: no water body data existed for Albania, Bosnia, North Macedonia, Montenegro, Serbia when originally built — same gap as everywhere else.
- **PNOA** (Instituto Geográfico Nacional) — Spain's national aerial orthophotography, ~25cm resolution, free, periodically refreshed. Better resolution than RBOD's Google Earth training imagery — likely the best imagery source for the Spain pilot.
- **PNOA-LiDAR / PNOA-MDT** — free national elevation/DEM data for Spain. Needed for the terrain/hydrological detection layer (see below).

## Detection approach: four stackable, complementary layers
No single method is sufficient. Each catches what the others miss.

### 1. Direct structure detection (image-based object detection)
- **RBOD dataset** (Wu, Li, Du, Wan, Yang, Xiao — Chongqing Jiaotong University, *Scientific Data*, Feb 2025). 4,872 satellite images, 11,741 annotated barriers across 5 classes (dams, weirs, groynes, sluices, locks) — weirs is the largest class (5,129), the closest match to Spain's azud problem. Five benchmarked architectures; best is YOLOv8x-OBB at mAP@0.5 = 0.82. Data: Zenodo. Code: github.com/wu325/RBOD-. Imagery: Google Earth basemap, sub-meter resolution.
- **Sun et al. trained CNN model** (Yunnan University + Durham University, *Water Resources Research*, 2024). FCOS/ResNeXt-101 model, run at whole-basin scale on the Mekong, found 13,054 barriers (10,561 previously unrecorded — existing databases had captured under 3%). Trained model, R scripts, and resulting barrier database open on Zenodo.
- **RF-YOLOv11 hybrid framework** — newer follow-on built on RBOD, adds a Random Forest "candidate area delineation" pre-filter to narrow search area before running the full detector, more efficient over large regions. Notes RBOD's training data over-represents warm temperate zones — worth checking generalization to Mediterranean terrain specifically.

### 2. Terrain / hydrological analysis (DEM-based)
- **Yellow River check dam study** — combines deep learning image classification with DEM/hydrological analysis (predicts likely dam locations from valley shape and flow accumulation, then confirms visually). Reports 98.56% precision / 82.40% recall on dam-controlled-area extraction — notably higher than pure image-detection benchmarks, and specifically built to catch small dams that image-only methods (incl. Sun et al.'s) miss. No public code repo found — approach would need reproducing from the paper's method, using PNOA-MDT as the DEM source.

### 3. Water signature detection (spectral, proxy-based)
- **OmniWaterMask (OWM)** — open, combines deep learning + NDWI + OpenStreetMap water-body data, built specifically for farm dam monitoring (i.e., detecting the pooled water a small dam creates, rather than the structure itself). Water has a much stronger, more reliable spectral signature than a small physical structure.
- General small-reservoir/pond detection literature (NDWI + CNN) as backup/reference — e.g. the 2026 Brazil small-reservoir mapping study (1984–2025 time series).

### 4. Ecological signature (algae, secondary confirming signal)
- **CyFi (Cyanobacteria Finder)** — open-source Python package, Sentinel-2, lightweight tree-based ML, built specifically for small inland water bodies (lakes, reservoirs, rivers) rather than large slow-moving ocean blooms. Stagnant water behind an unregistered barrier is more likely to show algal buildup than a free-flowing stretch — useful as a confirming signal, not a primary detector.

### Additional candidates found during planning (not in the original brief)
- **DL-HFCS** (Deep Learning + Hydrological Feature Constraint Strategies) — *Deep Learning and Hydrological Feature Constraint Strategies for Dam Detection: Global Application to Sentinel-2 Remote Sensing Imagery*, Remote Sensing (MDPI), March 2025, DOI 10.3390/rs17071194. YOLOv5s preliminary detection + hydrological constraints to eliminate false positives, on Sentinel-2 (global coverage, no PNOA dependency). No confirmed public code found, but validated across multiple regions rather than a single basin — meaningfully lower transferability risk than the Yellow River check-dam method for the DEM/hydrological layer. Worth pursuing as a second candidate/contact alongside Dr. Wen Dai's method, not a replacement — found 2026-09-09, authors not yet identified.
- **segment-geospatial (samgeo)** — Python package (samgeo.gishub.org) applying Meta's Segment Anything Model to geospatial imagery. Not a detector on its own, but directly useful for Layer 1's manual annotation step: point at a known dam's GPS location and let SAM propose the structure's boundary, human verifies/adjusts rather than drawing every box from scratch. Speeds up the "manually annotate ~50-100 dams" decision without reducing accuracy, since a human still checks every one.

### Not currently useful for discovery (noted for completeness)
- **Methane detection** (GHGSat, Sentinel-2 vision transformer/deep learning methods) — real and demonstrated (GHGSat has published a direct measurement from Cameroon's Lom Pangar Dam), but tuned for point-source plumes ≥~200kg/h. Below the sensitivity needed to find small undocumented barriers from their emissions. Useful later as an *impact* argument for barriers already confirmed, not as a discovery tool.

## Technical stack (free, no paid infrastructure required)
Precedent: Balaniuk et al.'s Brazil tailings dam study did country-scale detection with this exact free stack — Sentinel-2 via Google Earth Engine, TensorFlow, Google Colaboratory — and found 263 unregistered mines/dams. Small team, no special infrastructure.

- **Google Earth Engine** — imagery access and large-scale raster processing (free account, Spain has access already set up)
- **Google Colab** — model fine-tuning and inference (free tier; may need modest paid compute credits for a national-scale run)
- **PNOA** — primary Spain imagery source; Sentinel-2 as backup/wider context
- **PNOA-MDT** — DEM for the terrain/hydrological layer

## Suggested build sequence
1. Pull PNOA (or Sentinel-2) imagery over Spain via Earth Engine, tiled sensibly.
2. Fine-tune RBOD's best architecture (YOLOv8x-OBB) and/or adapt Sun et al.'s trained checkpoint, using SNCZI + AMBER + Andalucía regional data as training/validation ground truth.
3. Add the DEM/hydrological layer (Yellow River method, reproduced against PNOA-MDT) to catch small barriers image detection misses.
4. Add OmniWaterMask/NDWI water-signature detection as a complementary pass.
5. Add CyFi as a confirming signal where available.
6. Treat agreement across methods as higher-confidence; run everything against EU-Hydro so detection is scoped to actual river lines, not scanned blindly.
7. Cross-check all outputs against SNCZI, AMBER, and OSM to flag genuinely new detections.
8. Route uncertain/new detections through AMBER's Barrier Tracker app for human/citizen verification.
9. Compute real precision/recall for the Spain pilot — this figure itself would be a first-of-its-kind, citable result for a Mediterranean basin, not just a means to a count.
10. If successful, repeat basin by basin across Europe, prioritizing the countries EU-Hydro and AMBER both show as data-blank (Albania, Bosnia, North Macedonia, Montenegro, Serbia).

## Context: published accuracy is not yet near 95%
RBOD's best benchmarked model = 0.82 mAP@0.5. No published figure exists yet for the stacked, multi-layer approach described above, or for any of this applied to Spain specifically — that would be a new result this project establishes, not one it borrows.

## Contacts (for advice/collaboration on adapting the method)
- **Prof. Martyn C. Lucas**, Durham University — m.c.lucas@durham.ac.uk. Co-author, Sun et al. Mekong model (underlies Layer 1, direct structure detection). Aquatic Animal Ecology group, focus on fish migration/barrier passage.
- **Dr. Wenjie Li**, Chongqing Jiaotong University — li_wj1984@163.com. Corresponding author, RBOD dataset (underlies Layer 1).
- Daming He / Chao Ding (Yunnan University, Institute of International Rivers and Eco-Security) — no confirmed direct email found; institute line +86-871-65034577, or via Lucas as an intro.
- **Dr. Wen Dai**, Nanjing University of Information Science and Technology — wen.dai@nuist.edu.cn. Corresponding author, "Combining Deep Learning and Hydrological Analysis for Identifying Check Dam Systems from Remote Sensing Images and DEMs in the Yellow River Basin" (underlies Layer 2, DEM/hydrological — no public code exists for this method, found via web search 2026-09-09, not in the original brief).

## Adjacent precedent / landscape references
- **Balaniuk et al.** — Brazil tailings dam detection, proof of the "small team, free cloud tools, country-scale" approach. github.com/remis/mining-discovery-with-deep-learning
- **NatCap / National Geographic / Microsoft "Detecting Dams with AI and Satellite Imagery"** — open but explicitly "work in progress," less mature than RBOD/Sun et al. github.com/charlottegiseleweil/dams
- **`satellite-image-deep-learning/techniques`** (GitHub) — maintained meta-index of remote sensing models across every category, useful for spot-checking whether something newer has appeared.
