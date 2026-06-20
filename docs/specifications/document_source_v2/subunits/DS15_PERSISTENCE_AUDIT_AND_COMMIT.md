# DS15 — Persistence, Audit & Commit

## Mission

Écrire atomiquement, produire checksums/audit et publier le package.

## Entrées obligatoires

`accepted validation report`

## Sortie propriétaire

`PackageManifest`

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
- toute dégradation, récupération ou fallback enregistré ;
- état partiel explicite si la politique le permet.

## Erreurs principales

- `DS-PST-001` ;
- `DS-PST-002` ;

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
