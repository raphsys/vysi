# 01 — Autorité et représentations

## Couches

1. `BinaryArtifact` — octets et provenance ;
2. `ContainerModel` — parties, streams et relations physiques ;
3. `NativeModel` — structure propre au format ;
4. `TechnicalDocumentIR` — projection interopérable ;
5. `RenderedView` — apparence produite par un environnement précis ;
6. `DerivedAsset` — fichier dérivé d'une vue ou ressource ;
7. `RepresentationMapping` — preuve de correspondance.

## Autorité unique

Chaque fait a une autorité principale. Une valeur dupliquée dans une couche dérivée doit référencer
son origine et ne peut pas contredire silencieusement l'autorité.

## Projections

Toute projection déclare : producteur, version, méthode, entrées, pertes, approximations, confiance,
déterminisme et preuves. Une projection partielle est valide uniquement si son état est `partial` et si
les omissions sont enregistrées.

## Géométrie

Une adresse logique (`Sheet1!B7`, paragraphe 12, slide 4/shape 7) est distincte d'une géométrie rendue.
La géométrie rendue appartient à une surface et à un système de coordonnées versionné.
