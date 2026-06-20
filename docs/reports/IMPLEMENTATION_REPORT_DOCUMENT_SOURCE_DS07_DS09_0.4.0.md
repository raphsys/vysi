# Rapport d'implémentation — DOCUMENT_SOURCE DS07–DS09 — Vysi 0.4.0

## Objet

Implémenter l'inventaire des conteneurs, le décodage natif et la publication canonique des modèles
natifs conformément au gel contractuel de `DOCUMENT_SOURCE v2`.

## DS07 — Container Inventory

- ZIP/OOXML : parties, content types, relations internes/externes, compression, tailles, SHA-256,
  opacité, signaux macros/ActiveX/objets incorporés/signatures ;
- OLE/CFB : en-tête, FAT, DIFAT, mini-FAT, répertoire, storages, streams et hashes ;
- formats simples : artefact unique préservé ;
- quotas de parties et de volume décompressé ;
- interdiction des chemins non portables et des DTD/entités XML.

## DS08 — Native Decode

- TXT : encodage, BOM, fins de ligne, lignes, offsets octets et caractères de contrôle ;
- DOCX : sections, paragraphes, runs, tableaux, cellules, styles, révisions, annotations et ressources ;
- XLSX : feuilles, cellules, valeurs, formules, dépendances simples, styles et métadonnées ;
- PPTX : slides, formes, texte, transitions, animations et ressources ;
- PDF : pages fixed-layout, MediaBox, rotation, état de réparation, métadonnées et annotations ;
- raster : dimensions, frames et politique de surfaces ;
- OLE historique : inventaire natif partiel explicitement déclaré.

Les formules, macros, champs, animations et liens externes ne sont jamais exécutés.

## DS09 — Native Publication

Les contrats de staging DS08 sont validés puis publiés dans `native/<document_id>/`. Les profils,
styles, relations, métadonnées, annotations et ressources restent séparés et hashés.

## Erratum 2.2.0

Les sept profils natifs sont désormais des contrats complets munis d'un `header`. Cette correction est
nécessaire parce que `NativeDocument.profile_ref` référence un contrat identifiable, versionné et hashé.
Le contenu interne des profils reste en `profile_version = 2.0.0`.

## Limites assumées

- le décodage OLE historique reste `inventory_only` ;
- le lecteur PDF de DS08 produit un inventaire technique minimal, pas une analyse complète des objets ;
- la géométrie fine, l'IR technique, le rendu, les mappings et la fidélité appartiennent à DS10–DS13 ;
- les sous-documents incorporés sont inventoriés mais pas encore ingérés récursivement ;
- aucun package final n'est produit avant DS15.

## Validation

- 41 schémas stricts ;
- 40 exemples valides et 9 invalides rejetés ;
- 52 tests ;
- Ruff réussi ;
- mypy strict réussi ;
- smoke DS00–DS09 réussi ;
- validation des références, hashes, checkpoints et absence de `COMMITTED`.
