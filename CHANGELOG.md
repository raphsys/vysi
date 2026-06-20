# Changelog

## 0.8.1 — DS11 Multiformat Rendering Truthfulness & Acceptance Hardening

- distinction explicite entre sérialisation, visibilité, clipping, omission et non-évaluation ;
- géométrie par unité visible dans les aperçus techniques ;
- retour à la ligne et pagination déterministes TXT/DOCX ;
- pavage complet des grandes feuilles XLSX sans faux rattachement de cellules hors surface ;
- placeholders visibles pour formes et ressources PPTX non textuelles ;
- passthrough PDF/image exact au niveau binaire mais score visuel `null` sans décodage de contrôle ;
- recalcul DS13 du score visuel à partir de fidélité, visibilité et couverture géométrique ;
- validation DS14 des résumés de visibilité et des références visibles ;
- contrats DS11–DS14 2.8.0 et erratum 2.8.

## 0.8.0 — DOCUMENT_SOURCE DS11 Optional Source Rendering

- implémentation de DS11 et du marqueur `RENDERING_COMPLETE` ;
- modes `none`, `on_demand` et `required` ;
- previews techniques TXT/DOCX/XLSX/PPTX ;
- passthrough PDF/image hashé et copié en flux ;
- catalogues rendus, géométries et assets v2.7.0 ;
- budgets, cancellation, staging atomique et reprise ;
- intégration DS12–DS14 avec et sans rendu ;
- score visuel honnête et absence de faux rendu ;
- recette post-installation affichant les valeurs réellement lues.

## 0.7.0 — DOCUMENT_SOURCE DS14 Validation & Acceptance

- implémentation de DS14 sur le draft package DS00–DS13 ;
- `ValidationReport` 2.6.0 relié au checkpoint et au snapshot validé ;
- séparation explicite entre validation complète, statut global et `commit_eligible` ;
- validation des schémas, hashes, références, cycles, identités, DAG, sécurité et politiques ;
- contrôle de conservation des octets originaux et d’immutabilité des entrées ;
- agrégation documentaire `ok`, `review`, `rejected`, `error` et `cancelled` ;
- rejet métier produit comme résultat auditable, distinct d’un crash opérationnel ;
- ajout de la commande `vysi validate` et du marqueur `VALIDATION_COMPLETE` ;
- absence garantie de `PackageManifest`, checksums finaux et `COMMITTED` avant DS15 ;
- recette post-installation synthétique et optionnelle sur document réel ;
- erratum contractuel 2.6 et exemples invalides dédiés ;
- tests DS14 de falsification, référence orpheline, absence d’identité, politique stricte, cancellation, reprise, rapport achevé altéré et budget ;
- recette post-installation explicite, synthétique puis optionnelle sur document réel ;
- 116 tests passants, Ruff et mypy strict.

## 0.6.2 — Cohérence DS10–DS13 et fidélité explicable

- projection DS10 du catalogue complet des styles comme unités techniques protégées ;
- projection DS10 du catalogue complet des métadonnées avec espace de noms, valeur, sensibilité et provenance ;
- distinction stricte entre définition de style et application explicite, sans inférence éditoriale ;
- ajout du périmètre `required` à chaque mesure DS13 ;
- ajout de `preservation_stage` comme propriétaire explicite de chaque mesure et perte ;
- calcul des scores uniquement sur le périmètre requis ;
- score `null` lorsqu’aucune projection n’est requise, jamais `0.0` artificiel ;
- attribution des approximations de conteneur à `container_to_native` ;
- suppression du rattachement artificiel des pertes conteneur à `native_to_technical_ir` ;
- erratum contractuel 2.5 et deux nouveaux exemples invalides ;
- tests de non-régression sur DOCX réaliste avec styles, métadonnées et propriétés OOXML ;
- 102 tests passants, Ruff et mypy strict.

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
