# 18 — Invariants d'acceptation

## Invariants absolus

1. Les octets originaux sont préservés et hashés.
2. Toute référence porte chemin portable, hash, schema et contract_id.
3. Aucun contrat validé n'est modifié en place.
4. Toute partie détectée reste inventoriée, même illisible.
5. Toute unité native possède une adresse stable.
6. Toute unité IR possède une origine native ou synthétique déclarée.
7. Toute vue rendue possède un environnement de rendu.
8. Toute géométrie appartient à un espace de coordonnées.
9. Toute fonction non prise en charge est déclarée.
10. Aucun contenu actif n'est exécuté.
11. Aucun accès externe n'est implicite.
12. Aucune formule n'est recalculée implicitement.
13. Toute conversion, réparation et fallback est audité.
14. Toute représentation a un état explicite.
15. Les hashes de fichiers correspondent au manifeste.
16. Les références ne sont ni orphelines ni cycliques lorsque le cycle est interdit.
17. Les identifiants déterministes sont reproductibles.
18. Le package final est relisible sans état mémoire initial.
19. Un dépassement de limite est visible dans le package.
20. Aucun package n'est commis avant validation complète.

## Statut global

- `ok` : aucune perte majeure, aucun blocage, invariants satisfaits ;
- `review` : pertes/approximations acceptables mais explicites ;
- `rejected` : politique ou format interdit avant traitement accepté ;
- `error` : échec opérationnel empêchant un résultat fiable ;
- `cancelled` : arrêt demandé avec package d'audit éventuel.
