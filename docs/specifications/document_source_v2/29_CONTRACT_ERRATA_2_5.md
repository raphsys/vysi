# Erratum contractuel 2.5 — périmètre requis, propriétaire de perte et projection des catalogues techniques

## Constat

L’implémentation DS13 0.6.1 calculait certains scores sur le nombre total d’éléments rencontrés alors que
l’obligation de projection pouvait ne concerner qu’un sous-ensemble. Elle déduisait aussi le propriétaire
d’une perte à partir de l’axe de fidélité général. Cette déduction attribuait par exemple une approximation
de partie de conteneur à `native_to_technical_ir`, alors que la transition concernée était
`container_to_native`.

Deux catalogues natifs exposaient en outre une ambiguïté entre DS10 et DS13 :

- les styles étaient conservés dans `NativeStyleCatalog`, mais seuls leurs identifiants éventuellement
  référencés par des unités de contenu apparaissaient dans l’IR ;
- les métadonnées étaient conservées dans `NativeMetadataCatalog`, tandis que DS13 les exigeait dans la
  projection technique sans que DS10 les consomme.

Cette situation permettait les combinaisons incohérentes suivantes :

- `encountered > 0`, `omitted = 0`, mais score égal à `0.0` ;
- transition déclarée `lossless` alors qu’une approximation lui appartenait ;
- perte déclarée dans DS13 pour une donnée que DS10 n’avait contractuellement aucun moyen de projeter.

## Correction normative

### `FeatureCoverageReport` 2.5.0

Chaque mesure déclare désormais obligatoirement :

- `required` : nombre d’occurrences appartenant au périmètre obligatoire de la mesure ;
- `preservation_stage` : transition propriétaire de la mesure et de ses pertes éventuelles.

Les valeurs de `preservation_stage` sont fermées :

- `binary_to_container` ;
- `container_to_native` ;
- `native_to_technical_ir` ;
- `native_to_rendered` ;
- `rendered_to_asset` ;
- `roundtrip`.

Les scores de projection et de rendu sont calculés sur le périmètre `required`, jamais automatiquement sur
la totalité de `encountered`. Lorsque `required = 0`, le score correspondant est `null` et non `0.0`.
`omitted` ne peut pas dépasser `required`.

### Attribution des pertes

Une perte, omission, approximation ou capacité non prise en charge hérite exclusivement du
`preservation_stage` de la mesure qui l’a produite. L’axe (`structural`, `style`, etc.) ne détermine plus
la transition propriétaire.

Une perte `container_to_native` ne peut donc plus être rattachée artificiellement à
`native_to_technical_ir` pour satisfaire la chaîne de validation.

### `TechnicalDocumentIR` 2.5.0

DS10 consomme désormais l’ensemble des catalogues natifs obligatoires, y compris :

- `NativeStyleCatalog` ;
- `NativeMetadataCatalog`.

Chaque définition de style est projetée comme unité technique protégée `style_definition`, avec :

- type de style ;
- nom natif ;
- style parent éventuel ;
- propriétés directes ;
- propriétés résolues ;
- adresse native et provenance.

Cette projection ne signifie pas qu’un style est appliqué à une unité de contenu. DS10 ne fabrique aucune
application implicite : les références explicites restent dans `style_refs`, tandis que le catalogue de
définitions est conservé séparément dans l’IR.

Chaque métadonnée est projetée comme unité technique protégée `metadata`, avec :

- espace de noms ;
- nom natif ;
- valeur typée ;
- niveau de sensibilité ;
- adresse native et provenance.

Les métadonnées personnelles ou sensibles ne deviennent pas du contenu traduisible.

## Compatibilité

Les contrats 2.4 restent des artefacts historiques valides pour Vysi 0.6.0–0.6.1. Vysi 0.6.2 publie
exclusivement les formes 2.5.0 de `FeatureCoverageReport` et de `TechnicalDocumentIR`.

Cet erratum ne transfère pas l’autorité du modèle natif vers l’IR. Le modèle natif et ses catalogues restent
la source d’autorité ; l’IR demeure une projection technique interopérable et traçable.
