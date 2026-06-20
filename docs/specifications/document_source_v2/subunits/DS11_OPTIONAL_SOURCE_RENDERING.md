# DS11 — Optional Source Rendering

## Mission

Rendre en sandbox avec environnement et substitutions entièrement tracés.

## Entrées obligatoires

`RenderingPolicy + NativeDocument`

## Sortie propriétaire

`RenderedViewCatalog`

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

- `DS-RND-001` ;
- `DS-RND-002` ;

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
