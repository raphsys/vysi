# Rapport d'implémentation — DOCUMENT_SOURCE v2 — 0.1.0

## Périmètre livré

- projet autonome Vysi ;
- contrats multi-représentations ;
- préservation de l'original ;
- détection par contenu ;
- inventaire OOXML ;
- inventaire OLE partiel ;
- lecteurs natifs TXT, DOCX, XLSX et PPTX ;
- projection Common Document IR ;
- mappings natif vers IR ;
- sécurité passive des macros et relations externes ;
- couverture et préservation ;
- persistance transactionnelle avec `COMMITTED`.

## Règles figées

1. Le modèle natif est canonique.
2. Le rendu reste dérivé et optionnel.
3. Les formules ne sont pas recalculées.
4. Les macros et contenus actifs ne sont pas exécutés.
5. Les parties inconnues restent inventoriées et hashées.
6. Toute unité IR référence une unité native.

## Limites assumées de la fondation

- PDF et images sont détectés mais attendent leur migration contrôlée depuis
  `docs_parser_v2` ;
- DOC/XLS/PPT historiques sont inventoriés comme conteneurs OLE, sans décodage
  sémantique complet ;
- la branche de rendu n'est pas encore implémentée ;
- les profils DOCX/XLSX/PPTX seront enrichis par sous-domaines lors des prochaines
  révisions de la même unité.

## Validation de construction

- compilation Python : réussie ;
- Ruff : réussi ;
- mypy strict : réussi sur 36 fichiers source ;
- tests : 8 réussis ;
- smoke test transactionnel : réussi.
