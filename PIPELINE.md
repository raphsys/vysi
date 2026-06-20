# Pipeline DOCUMENT_SOURCE v2

## Implémenté en 0.6.1

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
DS12  Representation Mapping
DS13  Coverage, Fidelity & Preservation
```

## Étapes restantes

```text
DS11  Optional Source Rendering
DS14  Validation & Acceptance
DS15  Persistence, Audit & Commit
```

DS11 pourra être exécutée avant DS12 lors de son ajout. Les implémentations DS12–DS13 acceptent déjà les
catalogues de rendu, géométrie et assets lorsqu’ils sont disponibles.

## Sorties

```text
mapping/<document_id>/representation_mapping_catalog.json
quality/<document_id>/feature_coverage_report.json
quality/<document_id>/preservation_report.json
```

Le checkpoint porte `PREFLIGHT_COMPLETE`, `NATIVE_COMPLETE`, `IR_COMPLETE`, `MAPPING_COMPLETE` et
`QUALITY_COMPLETE`, mais jamais `COMMITTED`.
