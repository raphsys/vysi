# Matrice de support cible

| Famille | Profil | Structure native | Rendu | État initial d'implémentation |
|---|---|---:|---:|---|
| TXT | plain_text.v2 | complet visé | aperçu optionnel | prototype |
| DOCX | wordprocessing.v2 | complet progressif | externe optionnel | prototype partiel |
| XLSX | spreadsheet.v2 | complet progressif | impression optionnelle | prototype partiel |
| PPTX | presentation.v2 | complet progressif | slide optionnelle | prototype partiel |
| PDF | fixed_layout.v2 | migration contrôlée | natif | à migrer |
| Images | raster.v2 | migration contrôlée | natif | à migrer |
| DOC/XLS/PPT | legacy_ole.v2 | partiel explicite | externe optionnel | inventaire seulement |
| ODT/ODS/ODP | extension future | non | non | extension point |
| EPUB/HTML/RTF | extension future | non | non | extension point |

La réussite d'un rendu ne transforme jamais un support natif partiel en support complet.
