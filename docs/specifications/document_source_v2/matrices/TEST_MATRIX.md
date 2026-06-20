# Matrice de tests normative

| Axe | Exigence minimale |
|---|---|
| Contrats | chaque schéma modifié a exemple valide et invalide pertinent |
| Références | aucune référence orpheline, hash erroné ou schema incompatible |
| Déterminisme | exécutions identiques donnent les mêmes identités de contenu et hashes d’assets déterministes |
| Sécurité | corpus actif, chiffré, malformé, zip/xml bombs, traversal, SVG échappé |
| Formats | TXT/DOCX/XLSX/PPTX/PDF/images/OLE + variantes réelles |
| Résilience | timeout, crash, cancellation, resume, publication atomique, disque/budget insuffisant |
| Volumétrie | passthrough en flux, limites temp, aucun chargement binaire intégral non borné |
| Récursivité | embedded documents, profondeur et cycles |
| Rendu none | DS11 évaluée, aucun catalogue, score visuel null |
| Rendu preview | environnement, substitutions, limitations et approximate explicites |
| Rendu passthrough | octets, taille, hash, surfaces et géométries vérifiés |
| Rendu required | unsupported/missing surface devient bloquant |
| Intégration | mappings DS12, mesures DS13 et décisions DS14 avec/sans rendu |
| Acceptation | ok/review/rejected/error/cancelled selon politiques |
| Compatibilité | lecture 2.x, migration 0.1 expérimentale, extension inconnue |
| Fuzzing | probes, conteneurs, parseurs natifs et entrées textuelles de preview |
