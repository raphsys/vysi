# Rapport d'implémentation — DOCUMENT_SOURCE DS10 — Vysi 0.5.0

## Objet

Cette version implémente `DS10 — Technical IR Projection` au-dessus de la baseline DS00–DS09.
Elle ne produit ni rendu, ni mapping inter-représentations final, ni analyse sémantique.

## Entrées

Pour chaque document natif publié par DS09 :

- `native_document.json` ;
- profil natif référencé ;
- catalogue des styles ;
- catalogue des relations ;
- catalogue des annotations ;
- catalogue des ressources.

DS10 vérifie le schéma, le `content_hash`, le hash de fichier et la cohérence du `contract_id` du profil.

## Projection par profil

- texte : lignes et offsets octets ;
- traitement de texte : sections, paragraphes, runs, tableaux, cellules, révisions et annotations ;
- tableur : feuilles, cellules et formules non recalculées ;
- présentation : slides, formes, transitions et animations ;
- fixed-layout : pages et dimensions techniques ;
- raster : frames et politique de surfaces ;
- OLE historique : storages et streams avec état `review` hérité du natif.

Les relations et ressources natives sont représentées comme unités techniques traçables. Aucune unité
n'est classée comme titre, chapitre, légende, corps de texte ou unité de traduction.

## Invariants

- identifiants IR déterministes ;
- une racine synthétique par document ;
- toute unité `native_projection` possède au moins une source native ;
- aucun parent orphelin ;
- aucun cycle hiérarchique ;
- aucune mutation des contrats d'entrée ;
- aucune OCR ;
- aucune traduction ;
- aucun recalcul de formule ;
- aucun `COMMITTED` avant DS15.

## Erratum 2.3

Le schéma commun `typedValue` utilisait `oneOf` avec `number` et `integer`, ce qui rejetait les entiers
valides. Il utilise désormais `anyOf`, sans changement de la liste des valeurs autorisées.

## Validation

- Ruff : réussi ;
- mypy strict : réussi ;
- tests : 64 réussis ;
- contrats : 41 schémas, 40 exemples valides, 9 exemples invalides rejetés ;
- reprise DS09 vers DS10 : validée ;
- altération d'un contrat natif : rejetée ;
- déterminisme des identifiants et du hash IR : validé.
