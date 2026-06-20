# Erratum contractuel 2.7 — DS11 Optional Source Rendering

## Statut

```text
contract_version: 2.7.0
project_release: Vysi 0.8.0
scope: DS11 + intégration DS12–DS14
compatibility: additive and tightening
```

## Motif

Les contrats 2.0 décrivaient le rendu comme optionnel, mais ne suffisaient pas à distinguer sans ambiguïté :

- la politique demandée et le résultat réellement produit ;
- un aperçu technique d’une pagination native ;
- un passthrough d’une source visuelle d’un raster recalculé ;
- un asset binaire d’une référence de contrat JSON ;
- un rendu non demandé d’un rendu demandé mais indisponible ;
- la fidélité visuelle d’une simple complétude de catalogue.

Le présent erratum ferme ces ambiguïtés sans transformer le rendu en représentation canonique.

## Décisions normatives

### 1. DS11 est toujours évaluée

DS11 est un nœud explicite du DAG entre DS10 et DS12.

- `rendering_policy.mode = none` : DS11 termine sans publier de catalogues ; le marqueur
  `RENDERING_COMPLETE` signifie « politique évaluée », pas « image produite ».
- `on_demand` : un backend indisponible produit un état explicite `unsupported` ou `partial` et une revue.
- `required` : chaque profil demandé doit produire au moins une surface compatible ; sinon l’étape échoue.

### 2. Profils demandés

Les profils fermés de la ligne 2.7 sont :

- `source_reference` : meilleure référence visuelle sûre disponible ;
- `technical_preview` : aperçu technique dérivé, non canonique ;
- `native_passthrough` : conservation byte-identique réservée aux formats intrinsèquement visuels.

### 3. Nature réelle de la vue

`RenderedView.view_kind` est fermé à :

- `technical_preview` ;
- `native_passthrough` ;
- `unsupported`.

`requested_profile` conserve l’intention de la politique ; `view_kind` décrit le résultat réel. Ils ne
sont pas interchangeables.

### 4. Surfaces et assets

Une surface `available` ou `partial` :

- appartient à une vue existante ;
- référence un espace de coordonnées existant ;
- référence au moins un asset matérialisé ;
- déclare `status`, `fidelity`, dimensions, unité, rotation, média et unités natives sources.

`surface.asset_refs` contient des identifiants d’assets, jamais des références de contrats.

`DerivedAsset.stored_ref` est une référence binaire portable contenant :

```text
path
sha256
media_type
size_bytes
```

### 5. Géométrie

Toute géométrie déclare :

```text
owner_id
coordinate_space_id
geometry_kind
values
source
confidence
method
```

Une géométrie dérivée ne peut pas être présentée comme native. Une géométrie indisponible n’est pas
inventée.

### 6. Fidélité

- `exact` signifie conservation byte-identique ou géométrie native exacte selon le type de surface ;
- `approximate` signifie aperçu déclaré, pagination ou style dérivé ;
- `not_assessed` signifie qu’aucune mesure ne permet une conclusion.

La complétude des géométries ou des assets ne majore pas automatiquement le score visuel. En 2.7 :

- rendu non demandé : score visuel `null` ;
- aperçu technique déclaré : score visuel borné à `0.5` ;
- passthrough natif byte-identique : score visuel `1.0` pour la référence source préservée.

Ce score ne prétend pas comparer deux moteurs de rasterisation.

### 7. Sécurité et reproductibilité

DS11 interdit :

- réseau ;
- macros ;
- mise à jour des champs ;
- recalcul des formules ;
- OCR ;
- interprétation sémantique ;
- réparation silencieuse ;
- mutation des entrées.

L’environnement, le moteur, sa version, la locale, le fuseau, les substitutions et les avertissements
sont enregistrés. Les assets sont écrits dans une zone de staging, validés, puis publiés atomiquement.

### 8. Budgets

Les budgets de temps sont vérifiés pendant DS11. La somme des assets matérialisés pour un document ne
peut dépasser `resource_budget.max_temp_bytes`. Les passthroughs volumineux sont copiés en flux et hashés
sans lecture intégrale en mémoire.

### 9. Intégration aval

DS12 ajoute, selon disponibilité :

```text
native → rendered
technical_ir → rendered
rendered → geometry
rendered → derived_asset
native_resource → derived_asset
```

DS13 mesure séparément complétude, exactitude, déterminisme et fidélité. DS14 vérifie les trois catalogues,
les assets, les hashes, la politique demandée et l’absence de `COMMITTED`.

### 10. Responsabilités inchangées

DS11 ne produit jamais :

- compréhension éditoriale ;
- traduction ;
- reconstruction cible ;
- décision d’acceptation ;
- `PackageManifest` ;
- `COMMITTED`.

DS15 reste seule propriétaire du commit.

## Clarification d’implémentation du backend

La nature demandée par la politique et la nature effectivement produite restent distinctes. La sélection
du moteur est réalisée derrière le port `SourceRenderer`, selon une capacité déclarée et un ordre
déterministe. Cette clarification n’ajoute aucune propriété libre aux contrats.

Une vue `technical_preview` n’est pas une substitution implicite pour un document déjà intrinsèquement
rendu. Une demande incompatible doit rester `unsupported`.

DS14 vérifie également que chaque profil demandé possède exactement une vue publiée. Un profil absent,
non demandé ou dupliqué est une incohérence bloquante : une indisponibilité normale doit être publiée
comme vue `unsupported`, jamais masquée par une omission.
