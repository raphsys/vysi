# Index documentaire Vysi 0.8.1

## Gouvernance

- `README.md` — vue générale ;
- `ARCHITECTURE.md` — architecture multi-représentations ;
- `PIPELINE.md` — ordre d’exécution ;
- `INSTALLATION.md` — installation transactionnelle ;
- `CHANGELOG.md` — historique ;
- `docs/specifications/document_source_v2/00_*` à `31_*` — constitution et errata ;
- `docs/specifications/document_source_v2/subunits/` — DS00 à DS15.

## DS11

- `src/vysi/document_source/rendering_v2/models.py` — sorties internes immuables ;
- `rendering_v2/svg.py` — preview SVG sûr ;
- `rendering_v2/engine.py` — capacités intégrées ;
- `rendering_v2/validate.py` — invariants croisés ;
- `subunits/ds11_rendering.py` — orchestration, budgets et publication atomique ;
- `schemas/v2/rendered_view_catalog.schema.json` ;
- `schemas/v2/geometry_catalog.schema.json` ;
- `schemas/v2/derived_asset_catalog.schema.json` ;
- `tests/ds11/` — tests DS11 ;
- `scripts/smoke_document_source_rendering.sh`.

## Réintégration DS12–DS14

- `representation_v2/mapping.py` — mappings natif/IR/rendu/géométrie/assets ;
- `quality_v2/evaluate.py` — mesures visuelles et transitions ;
- `validation_v2/evaluate.py` — validation des politiques et assets ;
- `scripts/smoke_document_source_quality_rendered.sh` ;
- `scripts/smoke_document_source_validation_rendered.sh` ;
- `scripts/post_install_acceptance.sh`.

## Rapports

- `docs/reports/IMPLEMENTATION_REPORT_DOCUMENT_SOURCE_DS11_HARDENING_0.8.1.md` ;
- rapports antérieurs DS00–DS14 conservés dans `docs/reports/`.

## Outils de validation multiformat 0.8.1

- `scripts/download_and_test_vysi_real_corpus.sh` — constitution reproductible d'un corpus public local et lancement de la campagne.
- `scripts/run_vysi_multiformat_acceptance.sh` — exécution DS11–DS14 par format et agrégation CSV/Markdown.
