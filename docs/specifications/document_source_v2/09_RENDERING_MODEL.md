# 09 — Modèle de rendu source

## Statut

Le rendu source est optionnel, isolé, non canonique et piloté par politique. Il ne remplace ni les octets,
ni le conteneur, ni le modèle natif, ni l’IR technique.

DS11 est toujours évaluée dans le DAG : `mode=none` signifie explicitement `not_run`, et non absence
silencieuse de l’étape.

## Profils demandés

- `source_reference` : meilleure référence sûre disponible ;
- `technical_preview` : aperçu technique dérivé ;
- `native_passthrough` : conservation byte-identique d’un format intrinsèquement visuel.

La vue conserve séparément le profil demandé et la nature réellement produite.

## Sorties

DS11 publie ensemble :

- `RenderedViewCatalog` ;
- `GeometryCatalog` ;
- `DerivedAssetCatalog` ;
- les assets binaires référencés.

Une publication partielle des trois catalogues est interdite.

## Environnement de rendu

Chaque vue trace : moteur, version, OS, architecture, locale, timezone, profil, DPI lorsque pertinent,
polices et substitutions, paramètres d’impression connus, mise à jour des champs, politique de calcul,
accès externe, macros, warnings, déterminisme et hash de l’environnement.

## Surfaces

Types autorisés : page fixe, page fluide calculée, page d’impression de feuille, slide, canvas raster,
aperçu texte et thumbnail. Une unité native et sa surface rendue restent deux objets distincts.

Chaque surface possède : dimensions, unité, rotation, DPI éventuel, média, statut, fidélité, espace de
coordonnées, unités natives sources et assets matérialisés.

## Fidélité

- un aperçu technique est toujours `approximate` ;
- un passthrough byte-identique peut être `exact` comme référence source ;
- l’absence de méthode de mesure est `not_assessed` ;
- une géométrie complète ne prouve pas à elle seule une fidélité visuelle.

## Sécurité

Le backend intégré Vysi interdit réseau, macros, champs dynamiques, recalcul, OCR et réparation. Un backend
externe futur doit respecter les mêmes contrats, être sandboxé et publier ses limites.
