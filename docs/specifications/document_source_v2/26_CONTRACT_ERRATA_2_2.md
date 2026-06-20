# 26 — Erratum contractuel 2.2.0

## Motif

`NativeDocument.profile_ref` est une référence de contrat vérifiable. Les sept schémas de profils natifs 2.0.0 ne possédaient pourtant aucun `header`, ce qui empêchait la validation transitive de la référence.

## Correction normative

Les contrats suivants reçoivent un `header` obligatoire et une version de contrat `2.2.0` :

- `profile_plain_text` ;
- `profile_wordprocessing` ;
- `profile_spreadsheet` ;
- `profile_presentation` ;
- `profile_fixed_layout` ;
- `profile_raster` ;
- `profile_legacy_ole`.

Le champ interne `profile_version` reste `2.0.0` : il versionne le modèle natif, tandis que `header.schema_version` versionne son enveloppe contractuelle.

## Compatibilité

L'erratum ne modifie aucune sémantique de profil. Il rend les profils adressables, hashables et validables comme contrats de premier rang.
