# DOCUMENT_SOURCE v2 — Spécification normative gelée

## Statut

```text
contract_line: 2.x
freeze_version: 2.0.0
project_release: Vysi 0.8.1
status: FROZEN_FOR_IMPLEMENTATION
```

Le gel signifie que l'implémentation peut commencer. Toute rupture sémantique exige une version
majeure des contrats. Un ajout rétrocompatible exige une version mineure.

## Mission

Recevoir des sources documentaires non fiables et produire un paquet technique multi-représentations,
immuable, auditable, portable, validé et reproductible, sans compréhension éditoriale ou linguistique.

## Hiérarchie normative

1. `00_SCOPE_AND_BOUNDARY.md` ;
2. `01_AUTHORITY_AND_REPRESENTATIONS.md` ;
3. `02_PUBLIC_CONTRACT.md` ;
4. `18_ACCEPTANCE_INVARIANTS.md` ;
5. contrats des sous-unités ;
6. schémas JSON ;
7. catalogues et matrices ;
8. documents d'implémentation.

Une contradiction bloque l'implémentation jusqu'à résolution documentée dans le registre de décisions.

## Documents

- 00–24 : architecture, contrats, sécurité, exécution, stockage et acceptation ;
- 25–32 : errata contractuels 2.1.0 à 2.8.0 issus de l’implémentation ;
- `subunits/` : DS00 à DS15 ;
- `profiles/` : modèles natifs typés ;
- `catalogs/` : codes d'erreur, capacités et états ;
- `matrices/` : formats, fonctions, tests et interfaces aval ;
- `examples/` : objets valides et invalides.

## Interdiction structurante

Ni un rendu PDF, ni `TechnicalDocumentIR`, ni un JSON générique ne peuvent remplacer le modèle natif.
