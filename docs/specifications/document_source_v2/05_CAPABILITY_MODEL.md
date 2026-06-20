# 05 — Modèle de capacités

Le pipeline est piloté par capacités, non par chaînes `if format == ...` dispersées.

Capacités minimales :

- conteneur, texte, styles, relations, ressources ;
- pages natives, layout fluide, grille, slides, frames ;
- formules, révisions, annotations, timing, contenu actif ;
- chiffrement, signatures, objets incorporés ;
- rendu natif ou externe ;
- traitement partiel et adressage aléatoire.

Chaque lecteur annonce `supported`, `partial`, `unsupported` et ses limites. La sélection de lecteur est
une décision auditable fondée sur format, sécurité, capacités demandées et budget.
