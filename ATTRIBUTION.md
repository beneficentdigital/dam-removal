# Attribution

Sources used in the Guadalquivir basin pilot (`pilot_output.csv`,
`review_uncertain.csv`) and their license terms, per constitution.md
principle 5 and spec.md FR-014.

## Imagery

- **Sentinel-2 (COPERNICUS/S2_SR_HARMONIZED)** — European Space Agency /
  Copernicus Programme. Free and open under the [Copernicus data
  policy](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice).
  Required notice: "Contains modified Copernicus Sentinel data
  [2023-2025], processed by Google Earth Engine."
- **PNOA-MDT (25m digital terrain model)** — Instituto Geográfico
  Nacional (IGN), via public WCS. CC BY 4.0 per IGN's standard terms for
  IDEE web services. Pulled for the (currently stopped, see
  constitution.md) Layer 2 DEM work; not used in the current 3-layer
  pilot output.
- **PNOA10** — confirmed to have zero Earth Engine coverage of the
  Guadalquivir basin (see spec.md/research-brief.md); not used.

## Ground truth (barrier registry)

- **SNCZI/MITECO** (`presas`/`embalses` shapefiles) — Spain's Ministerio
  para la Transición Ecológica, downloaded manually from
  gis.miteco.gob.es. Public-sector Spanish government dataset; **exact
  reuse license terms not separately confirmed** at the point of
  download (T002 in tasks.md) — treat as provisional pending that
  confirmation before this ships as a public dataset.
- **AMBER Barrier Atlas** — pulled via Figshare. **CC BY 4.0, confirmed.**
  Cite: Belletti et al., "More than one million barriers fragment
  Europe's rivers," *Nature* 588, 436–441 (2020), and the AMBER Barrier
  Atlas dataset itself.
- **Andalucía regional inventory** (IECA/DERA, layer `T03_12_Presa`) —
  Junta de Andalucía. REDIAM's own metadata record for the related
  presas/embalses WMS states CC BY 4.0, which is a strong positive
  signal, but the specific IECA/DERA page actually used for this
  download did not show explicit terms in a quick check. **Still needs
  final confirmation before this ships publicly** (T002, open).
- **OpenStreetMap** (`waterway=weir`, via Overpass) — © OpenStreetMap
  contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/).
  Requires attribution and share-alike for any produced database that
  incorporates OSM data.

## Hydrography scaffold

- **EU-Hydro River Network Database** — European Environment Agency
  (EEA), via public ArcGIS REST. Free reuse with attribution per the
  [EEA standard reuse policy](https://www.eea.europa.eu/en/legal-notice).
- **IGN Red Hidrográfica** (`hy-n:WatercourseLink`, via public WFS) —
  Instituto Geográfico Nacional. **CC BY 4.0, confirmed** in the WFS's
  own capabilities/metadata response.
- **EEA WISE WFD2022 River Basin District** (basin boundary,
  `GUADALQUIVIR`/`ES050`) — European Environment Agency, same reuse
  policy as EU-Hydro above.

## Models

- **OmniWaterMask** — used for Layer 3 confirmation (`layer3_confirm_owm.py`).
  See the package's own license for reuse terms.
- **CyFi** — used for Layer 4 (algae/ecological confirming signal).
  See the package's own license for reuse terms.

## Open items before public release

1. Confirm the Andalucía DERA license (above).
2. Confirm SNCZI/MITECO's exact reuse terms (above) — the site itself
   didn't present them in-band during manual download.

Neither gap blocks internal pilot use; both should be closed before
`pilot_output.csv` or `review_uncertain.csv` are shared outside the
project.
