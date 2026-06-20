# 10 — Cartographie des représentations

Le catalogue peut relier : octets, partie de conteneur, adresse native, unité native, unité IR, surface,
géométrie et asset.

Chaque edge déclare cardinalité, relation, méthode, exactitude (`exact`, `approximate`, `inferred`), confiance,
producteur, version et preuves. Les mappings plusieurs-à-plusieurs sont autorisés.

Une surface rendue sans mapping minimal vers le document source est invalide. Un mapping ne transfère pas
l'autorité d'une couche à une autre.
