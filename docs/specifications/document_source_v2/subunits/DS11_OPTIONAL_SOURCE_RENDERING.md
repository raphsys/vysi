# DS11 — Optional Source Rendering

## Mission

Produire, lorsque la politique le demande, une référence visuelle source isolée, traçable et non canonique,
ainsi que sa géométrie observable et ses assets dérivés. DS11 ne remplace ni le modèle natif ni
`TechnicalDocumentIR`.

## Position dans le DAG

```text
DS10 TechnicalDocumentIR
        ↓
DS11 Optional Source Rendering
        ↓
DS12 Representation Mapping
```

DS11 est toujours évaluée. Elle peut être `not_run` par politique, mais elle n’est jamais silencieusement
omise du checkpoint.

## Entrées obligatoires

- `PolicySet.rendering_policy` ;
- `AcquiredSourceBundle` et artefacts acquis vérifiés ;
- `FormatProbeReport` ;
- `NativeDocument` ;
- profil natif ;
- catalogues DS09 ;
- `TechnicalDocumentIR` ;
- budgets et état de cancellation.

Toutes les entrées sont vérifiées par hash, schéma, `contract_id`, `document_id` et immutabilité.

## Sorties propriétaires

Par document rendu :

```text
rendered/<document_id>/rendered_view_catalog.json
rendered/<document_id>/geometry_catalog.json
rendered/<document_id>/derived_asset_catalog.json
rendered/<document_id>/assets/*
```

Les trois catalogues sont publiés ensemble ou aucun ne l’est.

## Modes

### `none`

- aucun catalogue DS11 ;
- aucun asset ;
- DS11 est marquée terminée ;
- DS13 déclare le visuel `not_run` avec score `null`.

### `on_demand`

- les profils demandés sont tentés ;
- une capacité indisponible reste visible sous `unsupported` ;
- un aperçu partiel entraîne une revue, pas un succès exact.

### `required`

- chaque profil demandé doit produire une vue compatible et au moins une surface ;
- une absence de backend, de surface ou d’asset est bloquante ;
- une vue approximative reste possible si le profil demandé l’autorise, mais elle demeure `partial`.

## Profils de rendu 2.7

- `source_reference` ;
- `technical_preview` ;
- `native_passthrough`.

La politique demandée et la nature obtenue sont stockées séparément.

## Capacités intégrées Vysi 0.8.1

| Profil natif | Résultat intégré | Fidélité déclarée |
|---|---|---|
| `plain_text` | pages SVG techniques | approximative |
| `wordprocessing` | aperçu de flux SVG, pagination dérivée | approximative |
| `spreadsheet` | aperçu de grille/feuille SVG | approximative |
| `presentation` | aperçu textuel par slide SVG | approximative |
| `fixed_layout` | passthrough du PDF et boîtes de pages natives | exacte pour la référence source |
| `raster` | passthrough du conteneur image et dimensions de frames | exacte mono-frame, partielle multiframe |
| `legacy_ole` | non pris en charge par le backend intégré | unsupported |

Les aperçus Office ne prétendent jamais reproduire les polices, la pagination, l’impression ou les effets
d’un moteur Office natif. Les backends sont isolés derrière le port `SourceRenderer`. La sélection est déterministe par capacité,
priorité puis identifiant de backend. Vysi 0.8.1 enregistre uniquement le backend intégré ; un backend
Office/PDF externe pourra être ajouté sans modifier les contrats DS11–DS14.

`technical_preview` n’est pas artificiellement appliqué aux profils intrinsèquement rendus `fixed_layout`
et `raster` : ces profils utilisent `source_reference` ou `native_passthrough`. Une demande incompatible
reste explicitement `unsupported`.

## Environnement obligatoire

Chaque vue enregistre au minimum :

- moteur et version ;
- famille de renderer ;
- Python, OS et architecture ;
- locale et fuseau ;
- profil demandé ;
- état réseau ;
- état macros ;
- mise à jour des champs ;
- recalcul des formules ;
- substitutions de polices ;
- déterminisme ;
- avertissements ;
- hash de l’environnement.

## Géométrie

Chaque surface possède son espace de coordonnées et au moins une géométrie de surface. L’origine,
l’unité, les axes, la méthode, la confiance et la source sont explicites.

La géométrie DS11 décrit ce que le backend connaît. Elle n’invente pas les positions internes absentes.

## Sécurité

DS11 :

- ne contacte jamais le réseau ;
- n’exécute aucun contenu actif ;
- ne met pas à jour les champs ;
- ne recalcule aucune formule ;
- n’effectue aucun OCR ;
- n’interprète aucun rôle éditorial ;
- ne suit aucun lien externe ;
- n’écrit qu’en staging puis dans son espace propriétaire.

Les textes insérés dans un SVG sont échappés et normalisés en XML 1.0 sûr.

## Budgets

- `max_wall_seconds` et `max_cpu_seconds` sont vérifiés par le contexte ;
- `max_temp_bytes` borne la somme des assets publiables d’un document ;
- le passthrough est copié en flux, sans chargement intégral en mémoire ;
- tout dépassement produit `DS-LIM-001`.

## Publication atomique

1. calcul dans `runtime/tmp/ds11-<document_id>` ;
2. validation des trois schémas ;
3. validation des invariants croisés ;
4. écriture/copie des assets ;
5. vérification taille et SHA-256 ;
6. renommage atomique vers `rendered/<document_id>` ;
7. création et vérification des références de checkpoint tant que la sauvegarde précédente existe encore ;
8. restauration de la version précédente — ou suppression de la nouvelle publication — en cas d’échec.

## Garanties

- aucune mutation des entrées ;
- identifiants stables ;
- chemins portables ;
- assets hashés ;
- références non orphelines ;
- vue partielle explicite ;
- indisponibilité explicite ;
- aucune promotion d’un aperçu vers une fidélité exacte.

## Erreurs principales

- `DS-RND-001` : entrée, invariant, publication ou intégrité invalide ;
- `DS-RND-002` : rendu requis indisponible ou aucun rendu publiable ;
- `DS-RND-003` : rendu partiel ou unsupported admis en revue ;
- `DS-LIM-001` : budget dépassé ;
- `DS-RUN-003` : cancellation.

## Reprise

Une reprise depuis DS10 relit et vérifie toutes les entrées. Une reprise depuis DS11 valide les catalogues
et les assets déjà publiés avant de poursuivre vers DS12. Un asset altéré bloque la reprise.

## Interdictions

- appeler directement DS12, DS13 ou DS14 ;
- muter un contrat antérieur ;
- masquer un fallback ;
- déclarer une pagination native pour un aperçu dérivé ;
- attribuer un score de fidélité ;
- créer `PackageManifest`, checksums finaux ou `COMMITTED`.

## Tests obligatoires

- mode `none` ;
- aperçu TXT/DOCX/XLSX/PPTX ;
- passthrough PDF/raster ;
- multiframe partiel ;
- plusieurs profils ;
- backend unsupported ;
- required bloquant ;
- cancellation et budgets, y compris déduplication des assets identiques ;
- sélection déterministe du backend ;
- rollback si la création des références échoue après promotion ;
- reprise depuis DS10 ;
- déterminisme des identités et octets ;
- asset altéré ;
- référence orpheline ;
- sécurité XML ;
- immutabilité ;
- intégration DS12–DS14 avec et sans rendu.

## Visibilité contractuelle 2.8

Les aperçus techniques paginent et replient le contenu sans débordement silencieux. Les surfaces publient séparément les références sérialisées, visibles, clippées et omises. Les passthrough binaires utilisent `not_assessed` pour la fidélité visuelle.
