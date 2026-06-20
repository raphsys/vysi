# Vysi

Vysi est une infrastructure documentaire multi-format fondée sur des contrats stricts, des représentations
séparées et une traçabilité vérifiable. Le projet ne confond pas les octets, le conteneur, le modèle natif,
l’IR technique, le rendu source et les assets dérivés.

La version **0.8.1** implémente `DOCUMENT_SOURCE` de **DS00 à DS14**, avec DS11 évaluée selon la politique.
DS15 demeure seule propriétaire de la persistance finale et du marqueur `COMMITTED`.

## État de DOCUMENT_SOURCE

- DS00–DS06 — coordination, requête, acquisition, détection, sécurité, identité et accès ;
- DS07 — inventaire des conteneurs ;
- DS08 — décodage natif ;
- DS09 — profils et catalogues natifs ;
- DS10 — projection déterministe vers `TechnicalDocumentIR` ;
- DS11 — rendu source optionnel, géométrie et assets ;
- DS12 — cartographie entre représentations ;
- DS13 — couverture, fidélité, préservation et pertes ;
- DS14 — validation du draft et éligibilité explicite à DS15.

## Deux parcours validés

```text
sans rendu : DS10 → DS11(not_run) → DS12 → DS13 → DS14
avec rendu : DS10 → DS11(rendered) → DS12 → DS13 → DS14
```

En mode `none`, aucun faux rendu n’est créé et le score visuel reste `null`. En mode rendu, les aperçus
techniques restent `approximate`; les PDF et images peuvent être conservés par passthrough byte-identique, sans transformer cette préservation binaire en score visuel artificiel.

## Installation

Utiliser l’installateur livré avec l’archive :

```bash
chmod +x install_vysi_0.8.1.sh
./install_vysi_0.8.1.sh
```

Pour inclure un document réel dans la recette post-installation :

```bash
VYSI_ACCEPTANCE_SOURCE=/chemin/document.docx ./install_vysi_0.8.1.sh
```

## Validation après installation

```bash
cd "$HOME/Mes_Projets/vysi"
source .vysi/bin/activate
./scripts/check_all.sh
./scripts/smoke_document_source_rendering.sh
./scripts/smoke_document_source_quality_rendered.sh
./scripts/smoke_document_source_validation_rendered.sh
./scripts/post_install_acceptance.sh /chemin/vers/document.docx
```

## Exécution

DS11 :

```bash
vysi render --source document.docx --render-mode on_demand \
  --render-profile source_reference --output runtime/results/document_source
```

DS14 sans rendu :

```bash
vysi validate --source document.docx --render-mode none \
  --output runtime/results/document_source
```

DS14 avec rendu :

```bash
vysi validate --source document.docx --render-mode on_demand \
  --render-profile source_reference --output runtime/results/document_source
```

Les spécifications normatives sont dans `docs/specifications/document_source_v2/`.
