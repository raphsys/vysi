# 20 — Registre de décisions

## DECIDED

- architecture multi-représentations ;
- modèle natif comme autorité structurelle ;
- IR technique, non sémantique ;
- rendu optionnel et non canonique ;
- contrats immuables, stricts et hashés ;
- pipeline DS00–DS15 piloté par capacités ;
- sécurité hostile par défaut ;
- package transactionnel et portable ;
- profils natifs versionnés ;
- contenus inconnus préservés de façon opaque ;
- catalogues complets de styles et métadonnées projetés dans l’IR technique ;
- scores calculés sur un périmètre requis explicite ;
- pertes attribuées à une transition propriétaire explicite ;
- DS11 toujours évaluée, même lorsque le rendu est `not_run` ;
- aperçu technique distinct d’un rendu natif ;
- passthrough volumineux copié en flux et vérifié ;
- fidélité visuelle non majorée par la seule présence de catalogues.

## DEFERRED

- moteur natif ou externe exact de rendu Office ;
- prise en charge sémantique complète DOC/XLS/PPT historiques ;
- signature cryptographique des packages ;
- stockage distribué et remote cache.

## FORBIDDEN

- tout convertir en PDF comme représentation principale ;
- exécuter du contenu actif ;
- fallback silencieux ;
- `dict[str, Any]` comme substitut durable à un contrat normatif ;
- utiliser `null` pour masquer l'état d'une représentation ;
- considérer l'IR ou le rendu comme source native.

## EXTENSION_POINT

- nouveaux profils de formats ;
- nouveaux adaptateurs d'acquisition ;
- nouveaux moteurs de rendu ;
- nouveaux backends de stockage ;
- nouveaux validateurs de format.
