# Architecture Vysi 0.8.1

## Chaîne DOCUMENT_SOURCE

```text
SourceIngestionRequest
        ↓
DS00–DS06  tronc de confiance
        ↓
DS07       ContainerPartCatalog
        ↓
DS08       NativeDecodeResult
        ↓
DS09       profils et catalogues natifs
        ↓
DS10       TechnicalDocumentIR
        ↓
DS11       RenderedViewCatalog + GeometryCatalog + DerivedAssetCatalog
        ↓
DS12       RepresentationMappingCatalog
        ↓
DS13       FeatureCoverageReport + PreservationReport
        ↓
DS14       ValidationReport + commit_eligible
        ↓
Checkpoint VALIDATION_COMPLETE
```

DS11 est optionnelle par politique mais toujours évaluée dans le DAG. `mode=none` ne produit aucun
catalogue ; `on_demand` autorise une vue partielle explicite ; `required` bloque l’absence de capacité.

## Autorités

- octets originaux : autorité binaire ;
- conteneur : parties et relations physiques ;
- modèle natif : autorité structurelle propre au format ;
- `TechnicalDocumentIR` : projection technique interopérable ;
- rendu DS11 : preuve ou aperçu visuel non canonique ;
- mappings DS12 : correspondances prouvées ;
- rapports DS13 : mesures et pertes ;
- rapport DS14 : validation et éligibilité à DS15.

## Rendu intégré

- TXT, DOCX, XLSX, PPTX : previews SVG sûres, déterministes quant aux octets mais dépendantes de
  l’environnement comme représentation, toujours approximatives ;
- PDF et images : passthrough source hashé, sans lecture intégrale en mémoire ;
- OLE historique : unsupported par le backend intégré.

Les backends externes sont des extensions. Aucun backend ne peut exécuter des macros, recalculer des
formules, appeler le réseau ou modifier la source.

## Propriétés

- snapshots immuables et hashés ;
- publication atomique ;
- budgets et cancellation ;
- géométries rattachées à des espaces explicites ;
- distinction profil demandé / résultat obtenu ;
- absence de rendu distincte d’un échec ;
- score visuel non fabriqué ;
- `VALIDATION_COMPLETE` distinct de `commit_eligible` ;
- `PackageManifest` et `COMMITTED` interdits avant DS15.
