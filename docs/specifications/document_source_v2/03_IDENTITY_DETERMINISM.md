# 03 — Identité, hashing et déterminisme

## Identifiants

- `run_id` : aléatoire, identifie une tentative d'exécution ;
- `request_id` : fourni ou généré, stable pour la demande ;
- `artifact_id` : déterministe depuis le SHA-256 et le rôle dans le bundle ;
- `document_id` : déterministe depuis les artefacts ordonnés, la sélection et le profil logique ;
- `native_unit_id` : déterministe depuis `document_id`, profil et adresse native ;
- `representation_id` : déterministe depuis producteur, entrées et paramètres normalisés ;
- `contract_id` : déterministe depuis le payload canonique hors champs éphémères.

## Hash canonique

Le hash d'un contrat exclut `content_hash` lui-même et les champs déclarés éphémères. Les nombres,
Unicode, clés et chemins sont canonisés. Les timestamps d'exécution ne participent pas à l'identité du
contenu sauf lorsque le format source les porte explicitement.

## Déterminisme

Une opération non déterministe doit déclarer `determinism = nondeterministic`, ses causes et sa tolérance.
Les rendus dépendant des polices, locale ou version du moteur incorporent l'environnement dans leur identité.
