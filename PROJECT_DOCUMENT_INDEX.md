# Index documentaire Vysi 0.6.1

- `README.md` — vue générale et commandes ;
- `ARCHITECTURE.md` — architecture multi-représentations ;
- `PIPELINE.md` — DS00–DS15 et état d’implémentation ;
- `INSTALLATION.md` — installation transactionnelle ;
- `CHANGELOG.md` — historique des versions ;
- `docs/specifications/document_source_v2/README.md` — entrée normative ;
- `docs/specifications/document_source_v2/00_*` à `28_*` — constitution et errata ;
- `docs/specifications/document_source_v2/subunits/` — contrats DS00 à DS15 ;
- `docs/specifications/document_source_v2/profiles/` — profils natifs ;
- `src/vysi/document_source/schemas/v2/` — schémas JSON stricts ;
- `docs/reports/IMPLEMENTATION_REPORT_DOCUMENT_SOURCE_DS12_DS13_0.6.0.md` — rapport DS12–DS13.
- `docs/reports/HOTFIX_REPORT_DOCUMENT_SOURCE_NATIVE_PROPERTY_NAMES_0.6.1.md` — correctif DS08 sur les noms OOXML.

## Implémentation DS00–DS10

- `src/vysi/document_source/execution/` ;
- `src/vysi/document_source/container_v2/` ;
- `src/vysi/document_source/native_v2/` ;
- `src/vysi/document_source/technical_ir_v2/` ;
- `src/vysi/document_source/subunits/ds01_request.py` à `ds10_ir.py`.

## Implémentation DS12

- `src/vysi/document_source/execution/verified_inputs.py` — lecture vérifiée et immutabilité ;
- `src/vysi/document_source/representation_v2/models.py` — modèle typé des couches et arêtes ;
- `src/vysi/document_source/representation_v2/inventory.py` — inventaire multi-format ;
- `src/vysi/document_source/representation_v2/mapping.py` — construction et invariants ;
- `src/vysi/document_source/subunits/representation_inputs.py` — chargement autoritatif ;
- `src/vysi/document_source/subunits/ds12_mapping.py` — publication DS12.

## Implémentation DS13

- `src/vysi/document_source/quality_v2/models.py` — fonctions, pertes et transitions ;
- `src/vysi/document_source/quality_v2/evaluate.py` — couverture, fidélité et préservation ;
- `src/vysi/document_source/subunits/ds13_quality.py` — publication DS13.

## Validation et livraison

- `tests/ds12_ds13/` ;
- `scripts/smoke_document_source_mapping.sh` ;
- `scripts/smoke_document_source_quality.sh` ;
- `tools/generate_project_manifest.py` ;
- `scripts/generate_project_manifest.sh`.
