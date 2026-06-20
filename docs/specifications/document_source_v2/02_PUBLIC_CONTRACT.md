# 02 — Contrat public

## Entrée

`SourceIngestionRequest` est l'unique entrée publique. Elle contient :

- `request_id` ;
- une ou plusieurs `SourceLocator` ordonnées ;
- `SelectionScope` ;
- `IngestionPolicy` ;
- `SecurityPolicy` ;
- `ResourceBudget` ;
- `RenderingPolicy` ;
- `PreservationPolicy` ;
- `StrictnessPolicy` ;
- métadonnées de corrélation non secrètes.

Les secrets sont fournis exclusivement par `secret_ref`; ils ne sont jamais sérialisés dans le package.

## Sortie

L'unique sortie publique est `DocumentSourcePackage`, représentée par `package_manifest.json` et un ou
plusieurs `DocumentEnvelope`. Un package d'échec reste auditable mais n'est pas accepté comme entrée aval.

## Compatibilité

Une unité aval dépend du contrat public, jamais des classes internes, chemins temporaires ou bibliothèques
de lecture.
