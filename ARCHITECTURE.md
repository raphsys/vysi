# Architecture Vysi 0.6.1

## Principe

Vysi maintient séparément les octets originaux, le conteneur, les modèles natifs, l’IR technique,
les rendus et les mappings.

```text
SourceIngestionRequest
        ↓
DS00–DS06  tronc de confiance
        ↓
DS07       ContainerPartCatalog
        ↓
DS08       NativeDecodeResult + staging
        ↓
DS09       profils et catalogues natifs canoniques
        ↓
DS10       TechnicalDocumentIR
        ↓
DS12       RepresentationMappingCatalog
        ↓
DS13       FeatureCoverageReport + PreservationReport
        ↓
Checkpoint QUALITY_COMPLETE
```

DS11 est optionnelle. Lorsqu’un rendu existe, DS12 et DS13 l’intègrent ; lorsqu’il n’existe pas, l’axe
visuel est `null` et les transitions correspondantes sont `not_run`.

## Autorités

- octets originaux : intégrité binaire ;
- catalogue de conteneur : parties et relations de package ;
- profil natif : structure propre au format ;
- catalogues DS09 : styles, relations, ressources, métadonnées et annotations ;
- `TechnicalDocumentIR` : projection technique interopérable ;
- mappings DS12 : correspondances, pas transfert d’autorité ;
- rapports DS13 : mesure de couverture et déclaration des pertes.

## Propriétés

- identifiants stables ;
- références et hashes contrôlés ;
- mappings plusieurs-à-plusieurs ;
- fidélité mesurée par axes séparés ;
- aucune perte silencieuse ;
- absence de rendu distinguée d’un échec de rendu ;
- `COMMITTED` interdit avant DS15.
