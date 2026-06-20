# Erratum contractuel 2.3 — valeurs numériques typées

## Constat

Le schéma commun `typedValue` utilisait `oneOf` avec les variantes JSON Schema `number` et
`integer`. En JSON Schema, toute valeur entière satisfait également `number`. Une valeur entière valide
était donc rejetée parce qu'elle satisfaisait deux branches de `oneOf`.

## Correction normative

`typedValue` utilise désormais `anyOf`. La liste des types autorisés ne change pas : chaîne, nombre,
entier, booléen, valeur nulle ou tableau de valeurs scalaires. Cette correction ne rend pas les sacs de
propriétés libres et ne modifie pas la sémantique de `value_type`.

## Portée

L'erratum corrige la validation des propriétés techniques de DS10 et des propriétés natives déjà prévues.
Il n'introduit aucun nouveau champ et ne rompt aucun contrat valide antérieur.
