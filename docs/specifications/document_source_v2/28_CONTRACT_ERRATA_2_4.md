# Erratum contractuel 2.4 — preuves de mapping et explicabilité de la fidélité

## Constat

Les spécifications normatives exigeaient que chaque correspondance déclare sa cardinalité, son producteur,
sa version, son déterminisme et ses preuves. Le schéma 2.0 de `RepresentationMappingCatalog` ne portait pas
tous ces champs. De même, les transitions du `PreservationReport` ne permettaient pas de relier explicitement
une transition à sa méthode, sa confiance, ses pertes et ses preuves. Enfin, les éléments de couverture
n'indiquaient pas l'axe mesuré ni la base de calcul.

Cette divergence permettait un rapport syntaxiquement valide mais insuffisamment explicable.

## Correction normative

### `RepresentationMappingCatalog` 2.4.0

Chaque arête déclare désormais obligatoirement :

- `cardinality` : `one_to_one`, `one_to_many`, `many_to_one` ou `many_to_many` ;
- `producer` et `producer_version` ;
- `determinism` ;
- au moins une preuve portable dans `evidence_refs`.

Les listes de sources, cibles et preuves sont sans doublons. Un mapping `exact` doit être produit avec une
confiance de `1.0` par l'implémentation DS12.

### `FeatureCoverageReport` 2.4.0

Chaque fonction mesurée déclare :

- son `axis` de fidélité ;
- son `basis`, c'est-à-dire la règle de mesure en langage explicite ;
- au moins une preuve.

### `PreservationReport` 2.4.0

Chaque transition déclare désormais :

- version du producteur et méthode ;
- déterminisme ;
- exactitude et confiance ;
- preuves ;
- références aux pertes qui justifient un état partiel ou avec perte.

Une transition `not_run` porte obligatoirement `exactness = not_applicable` et `confidence = null`.

## Compatibilité

Les contrats 2.0 restent lisibles comme documents historiques, mais DS12–DS13 publient exclusivement les
formes 2.4.0. Cet erratum ne transfère aucune autorité entre les couches et n'autorise aucune propriété libre.
