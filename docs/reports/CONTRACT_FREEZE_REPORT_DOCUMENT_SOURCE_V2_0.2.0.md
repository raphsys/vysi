# Rapport de gel contractuel — DOCUMENT_SOURCE v2

## Résultat

```text
statut: FROZEN_FOR_IMPLEMENTATION
project_version: 0.2.0
contract_major: 2
subunits: DS00–DS15
```

## Décisions majeures

- séparation stricte binaire/conteneur/natif/IR/rendu/assets ;
- `TechnicalDocumentIR` remplace l'appellation ambiguë `CommonDocumentIR` ;
- états explicites des représentations ;
- identités de contenu déterministes distinctes des run IDs ;
- profils natifs discriminés ;
- sécurité hostile-par-défaut et budgets obligatoires ;
- récursivité documentaire contrôlée ;
- validation complète avant commit ;
- package portable avec hashes, audit, erreurs et validation ;
- frontières aval figées.

## Réserves d'implémentation

Le gel ne prétend pas que tous les lecteurs sont complets. Les moteurs, bibliothèques et performances
seront validés par corpus. Une limitation d'implémentation ne peut pas modifier silencieusement le contrat.
