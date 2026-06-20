# 17 — Versionnement et compatibilité

SemVer contractuel : MAJOR rupture, MINOR ajout rétrocompatible, PATCH correction sans changement de sens.

Un lecteur de contrats doit ignorer uniquement les extensions déclarées dans un espace de noms autorisé.
Un champ normatif inconnu dans un contrat majeur identique est une erreur. Les migrations sont pures,
versionnées, auditées et ne suppriment pas l'original.

La ligne 2.x est gelée pour l'implémentation. Les contrats 0.1.0 sont expérimentaux et non stables.
