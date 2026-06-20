# 12 — Modèle d'erreur

Toute anomalie utilise un code stable du catalogue. `ErrorRecord` contient : code, étape, portée, sévérité,
message utilisateur, détails techniques sûrs, cause, retryable, recoverable, action, références de preuve et
traceback expurgé facultatif.

Les tentatives de lecteurs et fallbacks sont des objets distincts. Une exception Python non convertie en
`ErrorRecord` avant la frontière de sous-unité est un défaut d'implémentation.

Une erreur n'est jamais supprimée ; elle peut être résolue par une révision liée, reclassée avec justification
ou acceptée par une politique explicite.
