# 07 — Profils natifs typés

Le contrat `NativeDocument` est une enveloppe discriminée. Son `profile_kind` sélectionne un schéma strict :

- `plain_text.v2` ;
- `wordprocessing.v2` ;
- `spreadsheet.v2` ;
- `presentation.v2` ;
- `fixed_layout.v2` ;
- `raster.v2` ;
- `legacy_ole.v2`.

Les extensions de format utilisent un registre versionné. Les propriétés libres sont limitées aux espaces
`extensions` nommés et ne peuvent remplacer des champs normatifs.

Tout élément inconnu est préservé comme `OpaqueNativePart` avec adresse, hash, type et motif d'opacité.
