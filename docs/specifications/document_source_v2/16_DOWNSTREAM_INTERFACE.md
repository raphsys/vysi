# 16 — Interface avec les unités aval

Les unités aval consomment uniquement un package validé `ok` ou `review` autorisé par leur politique.

Elles reçoivent : enveloppe, modèle natif, IR technique, styles, relations, ressources, vues, mappings,
confiance, erreurs, couverture et préservation. Elles ne dépendent pas des handles de bibliothèques ni des
fichiers temporaires.

Toute annotation sémantique aval référence les identifiants source ; elle ne modifie pas les contrats de
`DOCUMENT_SOURCE`.
