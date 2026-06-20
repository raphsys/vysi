# Matrice de support Vysi 0.8.1

| Famille | Profil natif | Structure native | Rendu intégré DS11 | État DS11 |
|---|---|---:|---|---|
| TXT | plain_text.v2 | implémentée | aperçu SVG paginé techniquement | partial/approximate |
| DOCX/DOCM | wordprocessing.v2 | implémentée progressive | aperçu de flux SVG | partial/approximate |
| XLSX/XLSM | spreadsheet.v2 | implémentée progressive | aperçu de grille par feuille | partial/approximate |
| PPTX/PPTM | presentation.v2 | implémentée progressive | aperçu textuel par slide | partial/approximate |
| PDF | fixed_layout.v2 | implémentée technique | passthrough PDF + boîtes natives | available/exact source reference |
| Images | raster.v2 | implémentée technique | passthrough image + dimensions frames | exact mono-frame, partial multiframe |
| DOC/XLS/PPT | legacy_ole.v2 | inventaire seulement | aucun backend intégré sûr | unsupported |
| ODT/ODS/ODP | extension future | non | non | extension point |
| EPUB/HTML/RTF | extension future | non | non | extension point |

Un aperçu intégré ne prétend pas remplacer LibreOffice, Microsoft Office ou un renderer natif. La réussite
d’un rendu ne transforme jamais un support natif partiel en support complet.
