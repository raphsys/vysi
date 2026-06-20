# Erratum contractuel 2.6 — ValidationReport, snapshot validé et éligibilité au commit

## Constat

Le contrat initial `ValidationReport` ne permettait pas de distinguer quatre faits différents :

- l’exécution technique complète de DS14 ;
- le statut documentaire global ;
- l’existence d’avertissements ou d’échecs bloquants ;
- l’autorisation explicite de transmettre le draft à DS15.

Il ne portait pas non plus l’identité du snapshot réellement contrôlé. Un rapport pouvait donc déclarer
`review` sans préciser s’il était éligible au commit, ou être détaché du checkpoint et de l’ensemble
d’artefacts qu’il prétendait valider.

## Correction normative

`ValidationReport` passe en version **2.6.0** et porte obligatoirement :

- `policy_ref` : politique effective appliquée ;
- `validated_snapshot.checkpoint_sha256` : hash du checkpoint pré-DS14 ;
- `validated_snapshot.artifact_set_sha256` : identité canonique de l’ensemble contrôlé ;
- compte des artefacts, contrats et références ;
- `package_status` ;
- `commit_eligible` ;
- résumé chiffré des contrôles et résultats documentaires ;
- contrôles typés, ordonnés, déterministes et reliés à leurs preuves ;
- résultat propre à chaque document ;
- références d’erreurs conservées dans le catalogue d’audit.

Un contrôle déclare : code, nature, portée, statut, sévérité, caractère bloquant, message et preuves.
Un contrôle bloquant est obligatoirement en échec. Un rapport `rejected`, `error` ou `cancelled` ne peut
jamais être `commit_eligible=true`. Un rapport éligible doit avoir un statut `ok` ou `review`, zéro échec bloquant et au moins un document
validé. Un rapport `error` peut contenir zéro résultat documentaire lorsque l’identité source elle-même est
absente ou invalide ; DS14 doit alors publier la preuve du blocage au lieu de transformer ce défaut en crash
opérationnel.

## Frontière DS14 / DS15

DS14 ne produit ni `PackageManifest`, ni `checksums.sha256`, ni marqueur `COMMITTED`. Il publie uniquement
`validation/validation_report.json` et le checkpoint peut porter `VALIDATION_COMPLETE`.

DS15 reste seul propriétaire :

- du manifeste final ;
- de l’inventaire de fichiers publiés ;
- des checksums finaux ;
- de l’audit de commit ;
- du renommage atomique ;
- du marqueur `COMMITTED`.

`VALIDATION_COMPLETE` signifie que DS14 a produit un rapport valide, pas que le package est accepté.
L’autorisation de DS15 se lit exclusivement dans `commit_eligible` après revalidation du rapport et du
snapshot.

## Snapshot et mutabilité

Le checkpoint utilisé par DS14 représente l’état pré-validation. Les fichiers de coordination
`run_manifest`, `error_catalog` et `checkpoint_manifest` peuvent ensuite être réécrits par DS00 pour
consigner le résultat de DS14. Leur évolution après le rapport ne constitue pas une mutation silencieuse
des entrées métier ; DS15 doit néanmoins revalider leurs versions finales.

Tous les autres artefacts contrôlés restent immuables pendant DS14.

## Compatibilité

Les anciens exemples `ValidationReport` 2.0.0 restent historiques. Vysi 0.7.0 publie exclusivement la
forme 2.6.0. Cet erratum ne modifie aucun schéma des représentations DS00–DS13.
