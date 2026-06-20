# 22 — Ordre d’implémentation

1. modèles communs, canonisation, identités et références ;
2. schémas stricts, validateur et exemples ;
3. DS00–DS06 : demande, acquisition, sécurité, identité et accès ;
4. DS07 : conteneurs ;
5. DS08–DS09 : profils natifs, styles, relations et ressources ;
6. DS10 : IR technique ;
7. DS12–DS13 : mappings, couverture et préservation sans rendu ;
8. DS14 : validation et acceptation du draft sans rendu ;
9. DS11 : rendu optionnel après stabilité du natif ;
10. réintégration DS12–DS14 avec et sans rendu ;
11. corpus d’acceptation complet et durcissement ;
12. DS15 : stockage, audit et commit.

L’ordre d’implémentation peut différer de l’ordre d’exécution, mais le DAG d’exécution reste :

```text
DS10 → DS11 → DS12 → DS13 → DS14 → DS15
```

Une phase ne ferme que lorsque ses invariants, erreurs, reprises et deux parcours de politique ont des tests.
