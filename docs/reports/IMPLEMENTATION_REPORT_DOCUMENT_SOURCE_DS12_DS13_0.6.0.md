# Rapport d’implémentation — DOCUMENT_SOURCE DS12–DS13 — Vysi 0.6.0

## 1. Décision d’architecture

DS12 et DS13 ont été reconstruits comme une tranche unique au-dessus de la baseline DS00–DS10. Ils ne
réinterprètent pas les formats, ne rendent pas les documents et ne corrigent pas silencieusement les entrées.
Ils vérifient, relient et mesurent les représentations déjà publiées.

DS11 reste optionnelle. Si ses catalogues sont absents, l’axe visuel n’est pas inventé : son score reste
`null` et les transitions `native→rendered` et `rendered→asset` sont `not_run`.

## 2. DS12 — Representation Mapping

### Entrées vérifiées

Pour chaque document, DS12 vérifie notamment :

- le bundle d’acquisition et les octets des artefacts ;
- le rapport de détection ;
- le catalogue de conteneur et le résultat de décodage lorsqu’ils existent ;
- le contrat natif et son profil référencé ;
- styles, relations, métadonnées, annotations et ressources ;
- `TechnicalDocumentIR` ;
- les catalogues de rendu, géométrie et assets lorsqu’ils existent.

Chaque contrat est contrôlé par schéma, version majeure compatible, `contract_id`, hash canonique, chemin et
SHA-256 de référence. Les entrées sont fingerprintées puis revérifiées avant publication.

### Inventaire typé

L’inventaire distingue :

- objets binaires ;
- parties et relations de conteneur ;
- unités, styles, relations, métadonnées, annotations et ressources natives ;
- unités IR ;
- surfaces rendues ;
- géométries ;
- assets dérivés.

Une clé étrangère n’est jamais transformée automatiquement en entité. Une même identité ne peut pas recevoir
deux natures incompatibles.

### Arêtes

Les arêtes couvrent :

- binaire→conteneur ;
- conteneur→natif ;
- natif→IR ;
- natif→rendu, propriétaire→géométrie et rendu/entrée→asset si DS11 existe.

Chaque arête déclare sources, cibles, relation, cardinalité, méthode, exactitude, confiance, producteur,
version, déterminisme et preuves. Son identifiant est recalculable à partir de son identité déterministe.

Les relations OOXML utilisent les parties et relations physiques réelles. Les formats PDF/raster à partie
physique unique ne sont pas dégradés artificiellement en mappings inférés.

### Invariants

DS12 rejette notamment :

- un identifiant de couche absent, dupliqué ou de type incohérent ;
- une source ou cible inconnue ;
- une arête non canonique ou à identité falsifiée ;
- un mapping exact de confiance différente de 1 ;
- une preuve absente, dupliquée ou non portable ;
- une unité native sans origine binaire/conteneur ;
- une unité IR sans mapping entrant ;
- une surface rendue sans rattachement minimal à la source ;
- une géométrie ou un asset non mappé.

## 3. DS13 — Coverage, Fidelity & Preservation

### Fonctions mesurées

DS13 mesure explicitement les artefacts, parties et relations de conteneur, unités natives, styles,
relations, métadonnées, annotations, ressources, occurrences de ressources, formules, révisions, contenus
interactifs, contenus opaques, surfaces, géométries, assets et capacités de rendu exigées.

Chaque fonction possède : axe, base de calcul, compteurs observés/extraits/préservés/projetés/rendus,
opaque/approximé/non pris en charge/omis, statut et preuves.

### Axes

Les axes restent séparés :

- binaire ;
- structurel ;
- sémantique technique ;
- style ;
- relationnel ;
- visuel ;
- interactif ;
- computationnel ;
- round-trip.

Un axe non mesurable reste `null` au lieu de recevoir un score arbitraire.

### Préservation et pertes

Le rapport décrit exactement cinq transitions :

1. binaire→conteneur ;
2. conteneur→natif ;
3. natif→IR ;
4. natif→rendu ;
5. rendu→asset.

Chaque transition déclare méthode, version, déterminisme, exactitude, confiance, preuves, entrées, sorties et
références aux pertes. Une transition partielle, avec perte ou en échec ne peut pas être publiée sans perte
associée. Une transition `not_run` impose `not_applicable`, une confiance `null` et aucune sortie.

Les pertes possèdent un identifiant stable, une catégorie, une sévérité, un axe, des sources canoniques, une
description et des preuves. Les formules sont préservées sans exécution. Les anciens conteneurs OLE restent
en `review` avec risque élevé tant que leur décodage métier est `inventory_only`.

## 4. Politique d’échec

- erreurs globales de contrats, bundle ou probe : fatales ;
- erreur locale d’un document : isolable si `allow_partial=true` ;
- cancellation et dépassement de budget : toujours propagés ;
- politique stricte : pertes majeures pouvant produire `rejected` ;
- aucune anomalie n’est supprimée pour obtenir un statut favorable.

## 5. Erratum contractuel 2.4

Les schémas initiaux ne portaient pas toutes les preuves exigées par les textes normatifs. L’erratum 2.4 rend
obligatoires :

- cardinalité, producteur, version, déterminisme et preuves des mappings ;
- axe, base et preuves des fonctions de couverture ;
- méthode, version, déterminisme, confiance, pertes et preuves des transitions.

## 6. Validation réalisée

- Ruff : PASS ;
- mypy strict : PASS ;
- pytest : 95/95 ;
- profils : texte, DOCX, XLSX, PPTX, PDF, raster et OLE ;
- hashes d’artefacts et références falsifiés ;
- IR et mapping altérés ;
- identité déterministe et tri canonique ;
- politique de rendu obligatoire ;
- politique stricte ;
- lot multi-document partiel ;
- cancellation, reprise et budgets ;
- absence de mutation des entrées ;
- validation des références du checkpoint ;
- smoke DS12 ;
- smoke DS13 ;
- absence de `COMMITTED`.
