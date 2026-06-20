# 00 — Périmètre et frontière

## Mission positive

`DOCUMENT_SOURCE` acquiert, identifie, sécurise, préserve et décrit techniquement une source. Il peut :

- recevoir fichier, flux, bytes, URL autorisée, répertoire, archive ou collection ordonnée ;
- préserver les octets originaux et leur provenance ;
- détecter format, conteneur, version, chiffrement et restrictions ;
- inventorier parties, streams, ressources, styles, relations et métadonnées ;
- produire un modèle natif typé selon la famille documentaire ;
- projeter une IR technique commune explicitement non canonique ;
- générer, sur demande, des vues rendues isolées et traçables ;
- cartographier les représentations ;
- mesurer couverture, fidélité, pertes et risques de round-trip ;
- produire un package vérifiable, reprenable et atomique.

## Périmètre négatif absolu

L'unité ne doit pas :

- effectuer d'OCR ;
- attribuer des rôles éditoriaux ou sémantiques ;
- classifier une page ou un bloc par sens ;
- traduire, résumer, corriger ou reformuler ;
- recalculer silencieusement des formules ;
- exécuter macros, JavaScript, DDE, ActiveX ou liens externes ;
- mettre à jour automatiquement champs, modèles distants ou connexions de données ;
- considérer un rendu comme structure native ;
- supprimer un contenu non compris pour faire réussir la validation.

## Frontière aval

`ANALYSE_DOCUMENTAIRE` reçoit le package validé et peut produire rôles, ordre de lecture sémantique,
unités de traduction, classification et compréhension. Ces résultats ne reviennent jamais modifier les
contrats source ; ils créent de nouveaux contrats aval.
