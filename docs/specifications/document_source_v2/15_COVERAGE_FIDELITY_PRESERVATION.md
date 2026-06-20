# 15 — Couverture, fidélité et préservation

Axes séparés : binaire, structurel, sémantique technique, style, relationnel, visuel, interactif,
computationnel et round-trip.

Chaque fonction rencontrée déclare compte observé, périmètre requis, extrait, préservé, projeté, rendu,
opaque, approximé, non pris en charge et omis. Toute omission possède une sévérité, une transition
propriétaire et une preuve.

`PreservationReport` décrit les transitions :

```text
binary → container
container → native
native → technical_ir
native → rendered
rendered → asset
roundtrip
```

Une conversion, réparation ou fallback possède son propre constat. Aucune perte n’est silencieuse.

## Périmètre des scores

Les scores utilisent exclusivement `required`. Un périmètre vide produit `null`, jamais `0.0`.

## Rendu

- `mode=none` : mesures de rendu `not_run`, score visuel `null` ;
- vue unsupported : couverture explicite, aucun score favorable inventé ;
- aperçu technique approximatif : score visuel borné à `0.5` ;
- passthrough source byte-identique : préservation binaire `1.0`, score visuel `null` tant qu’aucun décodage/raster de contrôle n’a été évalué ;
- la présence d’un asset ou d’une bbox n’augmente pas automatiquement le score visuel.

Chaque perte ou approximation de rendu appartient à `native_to_rendered` ou `rendered_to_asset`, jamais à
une transition choisie seulement d’après l’axe général.

## Vérité de visibilité 2.8

DS13 distingue `serialized`, `fully_visible`, `partially_clipped`, `not_visible` et `not_assessed`. Une référence attachée à une surface sans géométrie visible ne compte jamais comme rendue.
