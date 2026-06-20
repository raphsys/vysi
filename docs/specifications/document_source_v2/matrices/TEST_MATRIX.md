# Matrice de tests normative

| Axe | Exigence minimale |
|---|---|
| Contrats | chaque schéma a exemple valide et au moins un invalide pertinent |
| Références | aucune référence orpheline, hash erroné ou schema incompatible |
| Déterminisme | 10 exécutions identiques donnent les mêmes identités de contenu |
| Sécurité | corpus actif, chiffré, malformé, zip/xml bombs, traversal |
| Formats | TXT/DOCX/XLSX/PPTX/PDF/images/OLE + variantes réelles |
| Résilience | timeout, crash worker, cancellation, resume, disque plein |
| Volumétrie | documents volumineux sans chargement intégral non borné |
| Récursivité | embedded documents, profondeur et cycles |
| Rendu | environnement, polices, locale et fallbacks tracés |
| Acceptation | ok/review/rejected/error/cancelled selon politiques |
| Compatibilité | lecture 2.x, migration 0.1 expérimentale, extension inconnue |
| Fuzzing | probes, conteneurs et parseurs natifs |
