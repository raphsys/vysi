# Rapport de correctif — propriétés natives OOXML — Vysi 0.6.1

## Défaut observé

Un DOCX réel a atteint DS08 avec des propriétés WordprocessingML telles que `keepNext`, `rFonts`, `bCs`,
`szCs`, `headerReference`, `pgSz`, `pgMar` et `docGrid`. Le lecteur injectait directement ces noms XML
camelCase dans `typedProperty.name`, alors que le contrat impose l’espace portable
`^[a-z][a-z0-9_.:-]{1,200}$`.

Les fixtures minimales antérieures ne contenaient pas de propriétés `pPr`, `rPr` ou `sectPr` réalistes ; elles
ne pouvaient donc pas exposer cette incompatibilité.

## Décision

Le schéma n’est pas assoupli. DS08 transforme désormais tout identifiant natif en nom canonique déterministe :

- `paragraph.keepNext` → `paragraph.keep_next` ;
- `run.rFonts` → `run.r_fonts` ;
- `run.bCs` → `run.b_cs` ;
- `run.szCs` → `run.sz_cs` ;
- `section.headerReference` → `section.header_reference` ;
- `section.pgSz` → `section.pg_sz`.

Les namespaces XML et les caractères non portables sont également normalisés. Les identifiants anormalement
longs sont tronqués avec un suffixe SHA-256 stable.

La graphie native n’est pas perdue : `source_address` pointe désormais vers l’élément ou l’attribut XML exact,
y compris le nom camelCase original.

## Portée

Le correctif appartient à DS08. DS10, DS12 et DS13 ne contournent pas l’erreur : ils consomment les contrats
natifs corrigés. Aucun erratum contractuel n’est requis.

## Non-régression

Une fixture DOCX réaliste contient des propriétés de paragraphe, de run, de section, de style et une relation
d’en-tête. Elle doit atteindre `MAPPING_COMPLETE` puis `QUALITY_COMPLETE` avec uniquement des noms conformes
au contrat et des adresses natives vérifiables.
