# Statut des implémentations DOCUMENT_SOURCE

- `execution/`, `subunits/`, `security_v2/`, `container_v2/`, `native_v2/`, `technical_ir_v2/`,
  `rendering_v2/`, `representation_v2/`, `quality_v2/` et `validation_v2/` : implémentation normative
  DS00–DS14 de Vysi 0.8.1 ;
- `services/ingest.py`, les anciens contrats hors `contracts_v2/` et certains adapters 0.1 : prototype
  conservé uniquement pour migration et comparaison.

Toute nouvelle fonctionnalité doit cibler les contrats v2. La prochaine sous-unité non implémentée est
DS15 — Persistence, Audit and Commit.
