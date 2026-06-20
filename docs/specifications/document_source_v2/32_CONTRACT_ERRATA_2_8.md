# 32 — Contract Errata 2.8

```yaml
contract_version: 2.8.0
project_release: Vysi 0.8.1
status: normative
```

## Décisions

1. `native_unit_refs` d’une surface désigne uniquement les unités effectivement visibles.
2. `serialized_native_unit_refs`, `clipped_native_unit_refs`, `omitted_native_unit_refs` et `visibility_basis` sont obligatoires.
3. Chaque unité visible d’un aperçu technique possède une géométrie avec `visibility`, `clipped`, `serialized`, `role` et `native_unit_refs`.
4. Le passthrough PDF/image prouve la préservation binaire, pas la fidélité visuelle ; sa fidélité est `not_assessed` et le score visuel est `null`.
5. Le score visuel DS13 combine fidélité de surface, visibilité réelle et couverture géométrique.
6. DS14 contrôle les résumés de visibilité et rejette toute unité déclarée visible sans géométrie observable.
