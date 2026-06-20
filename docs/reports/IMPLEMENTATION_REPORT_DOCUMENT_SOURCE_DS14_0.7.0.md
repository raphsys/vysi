# Rapport d’implémentation — DOCUMENT_SOURCE DS14 — Vysi 0.7.0

## Décision d’architecture

DS14 est implémentée comme une unité d’audit et de décision. Elle ne persiste pas le package final et ne
réalise aucune opération appartenant à DS15. Elle valide le draft sur disque et publie un rapport relié au
checkpoint pré-validation et à l’ensemble d’artefacts contrôlé.

## Contrôles réalisés

- validation des 41 schémas et des hashes canoniques ;
- vérification des SHA-256 du checkpoint et des octets sources ;
- cohérence `schema_id`, version et `contract_id` des références ;
- détection de références orphelines, non portables et cycles interdits ;
- détection des contrats publiés mais non inventoriés ;
- contrôle des étapes et du DAG ;
- contrôle de sécurité, réseau et contenu actif ;
- contrôle documentaire DS06–DS13 ;
- agrégation des statuts de couverture, préservation et accès ;
- interdiction du recalcul implicite des formules ;
- contrôle du déterminisme des mappings ;
- contrôle d’immutabilité des entrées ;
- interdiction de `PackageManifest` et `COMMITTED` avant DS15.

## Sémantique d’acceptation

Un rejet par politique produit un `ValidationReport` valide avec `package_status=rejected`; ce n’est pas un
crash de DS14. Une corruption empêchant une décision fiable produit `error`. Les états `ok` et `review`
peuvent être éligibles au commit uniquement si aucun contrôle bloquant n’échoue.

## Coordination

Le checkpoint est rafraîchi après la mise à jour du `RunManifest` et avant chaque sous-unité. DS14 reçoit
donc un snapshot cohérent. Après DS14, DS00 réécrit les contrats de coordination et ajoute le rapport au
checkpoint final.

## CLI et recette

- `vysi validate` exécute DS00–DS10 et DS12–DS14 ;
- `smoke_document_source_validation.sh` vérifie le parcours synthétique ;
- `post_install_acceptance.sh` fournit une recette post-installation réexécutable ;
- un document réel peut être fourni par argument ou `VYSI_ACCEPTANCE_SOURCE`.

## Validation

La tranche couvre nominal, altération binaire, contrat falsifié, référence orpheline, rejet strict,
cancellation/reprise, budget, idempotence, reprise d’un rejet, altération du rapport achevé, absence d’identité, rattachement des erreurs documentaires, immutabilité et hash canonique. Aucun marqueur `COMMITTED` n’est
créé.

## Résultat de validation

- 116 tests couvrant DS00–DS14 ;
- 41 schémas JSON ;
- 40 exemples valides ;
- 14 exemples invalides rejetés ;
- Ruff et mypy strict ;
- smoke DS14 synthétique ;
- recette réelle DOCX avec statut `review`, `commit_eligible=true` et zéro blocage.
