# DS13 — Coverage, Fidelity & Preservation

## Mission

Mesurer fonctions, pertes, approximations et risques de round-trip.

## Entrées obligatoires

`all catalogs and mappings`

## Sortie propriétaire

`FeatureCoverageReport + PreservationReport`

## Préconditions

- versions compatibles et hashes vérifiés ;
- références non orphelines ;
- budget restant suffisant ;
- cancellation non demandée ;
- politique de sécurité autorisant l'étape.

## Garanties

- sortie immuable et sérialisable sans handle actif ;
- identifiants selon `03_IDENTITY_DETERMINISM.md` ;
- aucune modification en place des entrées ;
- périmètre requis explicite pour chaque mesure ;
- propriétaire de transition explicite pour chaque perte ;
- score `null` lorsqu’aucune projection n’est requise ;
- toute dégradation, récupération ou fallback enregistré ;
- état partiel explicite si la politique le permet.

## Erreurs principales

- `DS-COV-001` ;
- `DS-PRS-001` ;

## Interdictions

- appeler une unité métier aval ;
- supprimer une anomalie pour obtenir un statut favorable ;
- écrire hors de sa zone temporaire ;
- publier une sortie non validée.

## Tests minimaux

- cas nominal ;
- entrée invalide ;
- hash ou référence invalide ;
- limite atteinte ;
- cancellation ;
- reprise déterministe ;
- absence de mutation des entrées.
