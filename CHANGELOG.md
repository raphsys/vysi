# Changelog

## 0.6.1 — Canonicalisation des propriétés natives OOXML

- correction de DS08 pour les propriétés OOXML camelCase (`keepNext`, `rFonts`, `pgSz`, etc.) ;
- maintien du schéma fermé en minuscules au lieu de l’assouplir ;
- conservation de l’adresse XML native détaillée dans `source_address` ;
- couverture des attributs XLSX namespacés et camelCase ;
- ajout d’un test DOCX réaliste exécuté jusqu’à DS12 et DS13 ;
- 97 tests passants, Ruff et mypy strict.

## 0.6.0 — Reconstruction DOCUMENT_SOURCE DS12–DS13

- reconstruction complète de DS12 et DS13 à partir de la baseline DS00–DS10 ;
- inventaire typé des couches binaire, conteneur, native, IR, rendu, géométrie et assets ;
- distinction stricte entre identités d’objets, clés étrangères, adresses natives et preuves ;
- cartographie déterministe avec cardinalité, exactitude, confiance, producteur, version et preuves ;
- relations OOXML exactes fondées sur les parties et relations réelles du conteneur ;
- traitement exact des formats à partie physique unique, sans mapping inféré artificiel ;
- invariants d’existence, de hiérarchie, d’unicité, de tri canonique et d’identité stable ;
- vérification des schémas, versions, hashes contractuels, références et octets d’artefacts ;
- détection de toute mutation d’une entrée entre lecture et publication ;
- couverture par fonctionnalité avec axe, base de mesure, compteurs et preuves ;
- transitions de préservation binaire→conteneur, conteneur→natif, natif→IR, natif→rendu et rendu→asset ;
- pertes, approximations, omissions, contenus opaques et capacités non prises en charge explicitement déclarés ;
- absence de DS11 représentée par `not_run`/`null`, jamais comme une perte implicite ;
- formules conservées et protégées sans exécution ni recalcul ;
- formats OLE historiques explicitement placés en `review` tant que leur décodage métier reste différé ;
- politique `allow_partial` isolant les échecs documentaires locaux sans masquer les erreurs globales ;
- reprise et cancellation DS12/DS13, contrôle des budgets et déterminisme des résultats ;
- correction de la reprise DS00–DS10 : une erreur historique résolue ne contamine plus le statut courant ;
- commandes CLI `vysi mapping` et `vysi quality` ;
- `jsonschema` déclaré comme dépendance runtime réelle, et non plus seulement comme outil de développement ;
- marqueurs `MAPPING_COMPLETE` et `QUALITY_COMPLETE`, sans `COMMITTED` ;
- erratum contractuel 2.4 pour l’explicabilité des mappings, couvertures et transitions ;
- tests positifs, négatifs, altérations, multi-document, politiques strictes et invariants ;
- 95 tests passants, Ruff et mypy strict.
## 0.5.0 — DOCUMENT_SOURCE DS10 Technical IR Projection

- projection multi-format vers `TechnicalDocumentIR` ;
- racines synthétiques et unités natives traçables ;
- projection texte, Wordprocessing, Spreadsheet, Presentation, Fixed-layout, Raster et OLE ;
- formules protégées sans recalcul ;
- relations, annotations et ressources représentées techniquement ;
- validation des hashes et références d'entrée ;
- reprise DS09 vers DS10 ;
- marqueur `IR_COMPLETE` sans `COMMITTED` ;
- erratum 2.3 sur `typedValue` entier/number ;
- 64 tests, Ruff et mypy strict.

## 0.4.0 — DOCUMENT_SOURCE DS07–DS09 Implementation

- inventaire profond ZIP/OOXML, OLE/CFB et artefacts simples ;
- hashes de parties, relations, chemins portables, quotas et signaux de sécurité ;
- décodage natif TXT, DOCX, XLSX, PPTX, PDF et images ;
- profil OLE historique explicitement limité à `inventory_only` ;
- styles DOCX directs/hérités/résolus ;
- formules XLSX préservées sans recalcul ;
- slides, formes, transitions et animations PPTX inventoriées ;
- pages PDF, géométrie, rotation, métadonnées et annotations techniques ;
- sémantique distincte GIF/WebP animé versus TIFF multipage ;
- publication canonique DS09 des modèles, styles, relations, métadonnées, annotations et ressources ;
- reprise d'un checkpoint DS06 jusqu'à DS09 ;
- erratum contractuel 2.2.0 : les profils natifs deviennent des contrats référencés ;
- 52 tests, Ruff et mypy strict.

## 0.3.0 — DOCUMENT_SOURCE DS00–DS06 Implementation

- implémentation réelle de DS00 à DS06 ;
- checkpoint après chaque sous-unité et reprise compatible ;
- cancellation par jeton fichier et budgets CPU/temps ;
- acquisition locale, répertoire et bytes/stream injectés par streaming ;
- détection PDF, OOXML, OLE, images, texte UTF et binaire inconnu ;
- sécurité ZIP sans extraction, détection de traversée, doublons, macros et bombes ;
- identité déterministe des documents ;
- détection de chiffrement, signatures et restrictions ;
- validation complète d'un checkpoint de préflight ;
- erratum contractuel 2.1.0 pour normalized_sources et source_locator_id ;
- 37 tests, Ruff et mypy strict.

## 0.2.0 — DOCUMENT_SOURCE Contract Freeze

- remplacement des spécifications courtes de 0.1.0 par un dossier normatif complet ;
- frontière de l'unité et modèles d'autorité figés ;
- 16 sous-unités DS00 à DS15 spécifiées ;
- contrats publics et internes versionnés ;
- schémas JSON Draft 2020-12 stricts ;
- profils natifs typés pour texte, traitement de texte, tableur, présentation, fixed-layout, raster et OLE historique ;
- modèle de sécurité, budgets, erreurs, reprise, cancellation, déterminisme et commit atomique ;
- exemples valides et invalides ;
- validateur contractuel et tests de références, hashes et invariants ;
- prototype 0.1.0 explicitement reclassé comme expérimental.

## 0.1.0 — Prototype architectural

- première preuve exécutable multi-représentations ;
- lecteurs initiaux TXT, DOCX, XLSX et PPTX.
