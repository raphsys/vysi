# 19 — Cas Red Team architecturaux

La conception doit résister au minimum à :

- OOXML zip bomb, noms dupliqués, traversal, XML billion laughs ;
- DOCX avec révisions imbriquées, champs, contrôles de contenu et objets OLE ;
- XLSX de millions de cellules, shared formulas, liens externes et connexions ;
- PPTX avec masters, groupes, animations, médias et objets incorporés ;
- PDF actif, chiffré, réparé, pièces jointes et structure partiellement corrompue ;
- TIFF multipage, GIF animé, WebP animé, image énorme ou tronquée ;
- TXT sans encodage certain, NUL, bidi controls et lignes gigantesques ;
- document parent/enfant récursif et cycle d'incorporation ;
- crash worker, timeout, annulation, disque plein et commit interrompu ;
- rendu non déterministe dû aux polices ou à la locale ;
- format futur inconnu dont les octets doivent rester préservés.

Chaque cas est lié à au moins un test avant clôture de l'implémentation.
