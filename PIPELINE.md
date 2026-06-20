# Pipeline DOCUMENT_SOURCE v2

## Implémenté en Vysi 0.8.1

```text
DS00  Run Coordination
DS01  Request & Policy Normalization
DS02  Acquisition & Source Bundle
DS03  Format, Container & Reader Probe
DS04  Security Preflight & Budgets
DS05  Identity, Integrity & Provenance
DS06  Access, Encryption & Restrictions
DS07  Container Inventory
DS08  Native Decode
DS09  Native Models, Styles, Relations & Resources
DS10  Technical IR Projection
DS11  Optional Source Rendering
DS12  Representation Mapping
DS13  Coverage, Fidelity & Preservation
DS14  Validation & Acceptance
```

## Étape restante

```text
DS15  Persistence, Audit & Commit
```

## Politique DS11

```text
none       → DS11 évaluée, aucun rendu, visual=null
on_demand  → vues disponibles/partielles/unsupported explicites
required   → absence de vue compatible bloquante
```

## Sorties DS11–DS14

```text
rendered/<document_id>/rendered_view_catalog.json
rendered/<document_id>/geometry_catalog.json
rendered/<document_id>/derived_asset_catalog.json
rendered/<document_id>/assets/*
mapping/<document_id>/representation_mapping_catalog.json
quality/<document_id>/feature_coverage_report.json
quality/<document_id>/preservation_report.json
validation/validation_report.json
```

## Marqueurs

```text
PREFLIGHT_COMPLETE
NATIVE_COMPLETE
IR_COMPLETE
RENDERING_COMPLETE
MAPPING_COMPLETE
QUALITY_COMPLETE
VALIDATION_COMPLETE
```

`RENDERING_COMPLETE` signifie que la politique DS11 a été évaluée. Il ne prouve pas qu’un asset a été
produit. `COMMITTED` reste strictement réservé à DS15.
