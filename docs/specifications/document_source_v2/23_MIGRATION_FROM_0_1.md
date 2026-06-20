# 23 — Migration depuis Vysi 0.1.0

La version 0.1.0 est conservée comme prototype. Ses contrats `SourceArtifact`, `NativeDocument`,
`CommonDocumentIR` et `DocumentEnvelope` ne sont pas considérés stables.

Migration :

- `CommonDocumentIR` devient `TechnicalDocumentIR` ;
- les références obligatoires deviennent `RepresentationSlot` ;
- les profils natifs libres deviennent discriminés ;
- les styles, relations, erreurs et exécution deviennent des catalogues séparés ;
- le package ajoute request, audit, checksums, validation et manifestes ;
- `COMMITTED` n'est plus suffisant sans validation_report et package_manifest.

Aucune unité aval ne doit être développée contre les contrats 0.1.0.
