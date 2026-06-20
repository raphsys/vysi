# DS14 — Validation & Acceptance

## Mission

Contrôler le draft package assemblé après DS13, agréger les résultats documentaires et décider s’il peut
être transmis à DS15 sans jamais effectuer le commit.

## Entrées obligatoires

- checkpoint DS00–DS10, DS12–DS13 cohérent ;
- politique effective ;
- contrats et artefacts référencés ;
- rapports de couverture et de préservation pour chaque document publiable ;
- catalogue d’erreurs et manifeste d’exécution.

## Sortie propriétaire

`validation/validation_report.json` conforme à `ValidationReport` 2.8.0.

## Contrôles obligatoires

DS14 vérifie au minimum :

1. schémas et versions des contrats ;
2. hashes de fichiers et hashes canoniques ;
3. métadonnées de références ;
4. références orphelines et cycles interdits ;
5. conservation exacte des octets sources ;
6. exhaustivité de l’inventaire de checkpoint ;
7. cohérence du DAG et des étapes obligatoires ;
8. cohérence des identités documentaires ;
9. présence des représentations DS06–DS13 ;
10. décisions de sécurité et d’accès ;
11. statuts de couverture et de préservation ;
12. absence de recalcul implicite des formules ;
13. déterminisme et unicité des mappings ;
14. absence de `PackageManifest` et de `COMMITTED` prématurés ;
15. absence de mutation des entrées pendant la validation.

## Statuts

- `ok` : aucun avertissement d’acceptation et aucun blocage ;
- `review` : draft éligible mais nécessitant une revue explicite ;
- `rejected` : politique ou sécurité refusant le contenu ;
- `error` : intégrité, schéma, référence ou invariant empêchant un package fiable ;
- `cancelled` : arrêt demandé avant achèvement du rapport.

`commit_eligible=true` est limité à `ok` et `review`, avec zéro échec bloquant et tous les documents
éligibles.

## Préconditions

- budget restant suffisant ;
- cancellation non demandée ;
- DS13 achevée ;
- checkpoint lisible et rattaché au même `run_id` ;
- politique effective disponible.

## Garanties

- sortie immuable et sérialisable ;
- identité du snapshot validé conservée ;
- chaque anomalie est visible dans les contrôles et, si nécessaire, dans `ErrorCatalog` ;
- aucune anomalie n’est supprimée pour obtenir un statut favorable ;
- aucune entrée métier n’est modifiée ;
- un rejet métier n’est pas confondu avec un crash opérationnel ;
- DS15 peut décider sur une preuve explicite et non sur un marqueur seul.

## Erreurs principales

- `DS-VAL-001` : intégrité, schéma, référence ou invariant invalide ;
- `DS-VAL-002` : politique, sécurité ou format non acceptable ;
- `DS-VAL-003` : avertissement ou revue requise.

## Interdictions

- créer `PackageManifest` ;
- produire `checksums.sha256` final ;
- créer `COMMITTED` ;
- corriger une entrée pendant la validation ;
- appeler une unité métier aval ;
- transformer un échec bloquant en avertissement sans règle contractuelle ;
- considérer `VALIDATION_COMPLETE` comme une preuve d’acceptation.

## Reprise

Une reprise complète retourne le rapport existant sans le réécrire. Une reprise après cancellation ou
échec opérationnel revalide le snapshot courant. Les erreurs historiques restent auditées mais ne rendent
pas automatiquement un draft courant non éligible si les contrôles actifs passent.

## Tests minimaux

- cas nominal `ok` ou `review` éligible ;
- source binaire altérée ;
- contrat ou hash canonique altéré ;
- référence orpheline ;
- rejet par politique stricte ;
- limite atteinte ;
- cancellation puis reprise ;
- reprise idempotente ;
- absence de mutation des entrées ;
- absence de `PackageManifest` et `COMMITTED` ;
- validation du rapport et de son hash canonique.

DS14 vérifie également que chaque profil demandé possède exactement une vue publiée. Un profil absent,
non demandé ou dupliqué est une incohérence bloquante : une indisponibilité normale doit être publiée
comme vue `unsupported`, jamais masquée par une omission.

## Contrôles DS11 2.8

DS14 vérifie qu’une unité visible possède une géométrie observable, que les ensembles visible/clippé/omis sont cohérents, et qu’un passthrough binaire ne revendique pas une fidélité visuelle évaluée.
