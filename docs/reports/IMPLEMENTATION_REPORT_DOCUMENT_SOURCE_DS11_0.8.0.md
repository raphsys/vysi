# Rapport d’implémentation — DOCUMENT_SOURCE DS11 — Vysi 0.8.0

## Portée

Cette version implémente `DS11 — Optional Source Rendering` et réintègre ses sorties dans DS12, DS13 et
DS14. Elle valide les parcours avec et sans rendu sans empiéter sur DS15.

## Architecture retenue

DS11 est un nœud explicite du DAG après DS10. Son caractère optionnel est une décision de politique :

- `none` : étape évaluée, aucune sortie rendue ;
- `on_demand` : sortie partielle ou unsupported admise avec revue ;
- `required` : absence de capacité ou de surface bloquante.

Les sorties propriétaires sont `RenderedViewCatalog`, `GeometryCatalog`, `DerivedAssetCatalog` et les
assets matérialisés. Elles sont calculées en staging, validées ensemble et publiées atomiquement.

## Backend intégré

Le backend intégré n’exécute aucun logiciel Office externe. Il produit :

- previews SVG techniques pour TXT, DOCX, XLSX et PPTX ;
- passthrough byte-identique pour PDF et images ;
- état unsupported pour les conteneurs OLE historiques.

Les previews Office sont volontairement approximatives. La pagination, les polices et les effets natifs ne
sont jamais prétendus exacts.

## Sécurité

- réseau refusé ;
- macros désactivées ;
- champs non mis à jour ;
- formules non recalculées ;
- aucun OCR ;
- textes SVG échappés et nettoyés pour XML 1.0 ;
- chemins portables ;
- hashes et tailles vérifiés ;
- passthrough copié en flux ;
- budget `max_temp_bytes` appliqué ;
- entrées revérifiées après exécution.

## Intégration

DS12 ajoute les arêtes vers les vues, géométries et assets. DS13 distingue `not_run`, `unsupported`,
`approximate` et `exact`, sans gonfler le score visuel par la seule présence d’objets techniques. DS14
valide la politique demandée, les trois catalogues, les fichiers et l’absence de `COMMITTED`.

## Tests

La tranche couvre notamment : mode none, preview des quatre familles applicatives, passthrough raster,
plusieurs profils, backend unsupported, rendu required, reprise DS10, déterminisme, asset altéré, budget,
sécurité XML, mappings, qualité, validation et non-régression DS00–DS14.

## Limites assumées

Le rendu Office intégré est un aperçu technique, pas un renderer bureautique exact. L’ajout futur d’un
backend LibreOffice, Microsoft Office ou spécialisé devra respecter les mêmes ports, contrats, règles de
sandbox et preuves.

## Frontière

Vysi 0.8.0 ne crée ni `PackageManifest` final, ni checksums de livraison, ni `COMMITTED`. DS15 reste la
prochaine tranche.

## Durcissements finaux

- port `SourceRenderer` et sélection déterministe par capacité/priorité/identifiant ;
- budget contrôlé pendant la matérialisation et sur les assets uniques après déduplication ;
- contrôles de cancellation à l’intérieur des boucles de surfaces ;
- rollback de publication jusqu’à la création réussie des références de checkpoint ;
- rejet explicite d’un `technical_preview` incompatible avec une source raster ou fixe.

DS14 vérifie également que chaque profil demandé possède exactement une vue publiée. Un profil absent,
non demandé ou dupliqué est une incohérence bloquante : une indisponibilité normale doit être publiée
comme vue `unsupported`, jamais masquée par une omission.
