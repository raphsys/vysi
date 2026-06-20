# Statut des implémentations DOCUMENT_SOURCE

- `execution/`, `subunits/`, `security_v2/`, `container_v2/` et `native_v2/` : implémentation
  normative DS00–DS10 et DS12–DS13 de Vysi 0.6.1.
- `services/ingest.py`, `adapters/native/` et les anciens contrats hors `contracts_v2/` : prototype 0.1
  conservé uniquement pour comparaison et migration progressive.

Toute nouvelle fonctionnalité doit cibler les contrats v2 et poursuivre DS11, DS14 et DS15.
