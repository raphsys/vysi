# DS09 — Native Models, Styles, Relations & Resources

## Mission

Matérialiser les modèles typés et catalogues autonomes.

## Entrées obligatoires

`NativeDecodeResult`

## Sortie propriétaire

`NativeDocument + catalogs`

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

- `DS-NAT-001` ;
- `DS-NAT-002` ;

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
