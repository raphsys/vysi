# 13 — Sémantique d'exécution

DS00 exécute un DAG de nœuds idempotents. Chaque nœud possède entrées hashées, paramètres normalisés,
préconditions, budget, timeout, stratégie de retry, sortie attendue et politique de cache.

États : pending, ready, running, succeeded, partial, failed, blocked, cancelled, invalidated, superseded.

Reprise autorisée si entrées, paramètres, versions et politique sont compatibles. La cancellation est
coopérative avec arrêt forcé du worker après délai. Les workers risqués sont isolés sans réseau et avec
limites système. Aucun nœud ne modifie un contrat validé en place.
