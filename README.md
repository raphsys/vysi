# Vysi

Vysi est une infrastructure documentaire multi-format fondée sur des contrats stricts, des représentations
séparées et une traçabilité vérifiable. Le projet ne confond pas les octets, le conteneur, le modèle natif,
l’IR technique, le rendu et les assets dérivés.

La version **0.6.1** implémente `DOCUMENT_SOURCE` jusqu’à la cartographie et au contrôle de préservation :
**DS00 à DS10, puis DS12 et DS13**. DS11 reste optionnelle ; DS14 et DS15 ne sont pas encore exécutées.

## État de DOCUMENT_SOURCE

- DS00–DS06 — coordination, requête, acquisition, détection, sécurité, identité et accès ;
- DS07 — inventaire des conteneurs ;
- DS08 — décodage natif ;
- DS09 — publication des profils et catalogues natifs ;
- DS10 — projection déterministe vers `TechnicalDocumentIR` ;
- DS12 — inventaire typé et cartographie entre représentations ;
- DS13 — couverture, fidélité, préservation, pertes et risque de round-trip.

DS12 et DS13 ne rendent pas le document, ne réalisent aucune interprétation sémantique métier et ne mutent
aucune entrée. Lorsqu’aucun rendu DS11 n’existe, les transitions visuelles sont `not_run` et les scores
visuels restent `null` ; cette absence n’est pas transformée artificiellement en perte.

Le checkpoint final porte `QUALITY_COMPLETE`, mais jamais `COMMITTED`, marqueur réservé à DS15.

## Installation

Utiliser l’installateur livré avec l’archive :

```bash
chmod +x install_vysi_0.6.1.sh
./install_vysi_0.6.1.sh
```

## Validation après installation

```bash
cd "$HOME/Mes_Projets/vysi"
source .vysi/bin/activate
./scripts/check_all.sh
./scripts/smoke_document_source_mapping.sh
./scripts/smoke_document_source_quality.sh
```

## Exécution

DS12 uniquement :

```bash
vysi mapping --source chemin/vers/document.docx \
  --output runtime/results/document_source
```

DS12–DS13 :

```bash
vysi quality --source chemin/vers/document.docx \
  --output runtime/results/document_source
```

Les spécifications normatives sont dans `docs/specifications/document_source_v2/`.
# vysi
