# Installation de Vysi 0.8.1

La livraison officielle contient le projet et `install_vysi_0.8.1.sh`.

L’installateur :

1. vérifie les hashes de la livraison et le manifest ;
2. sélectionne Python 3.10 à 3.13 ;
3. sauvegarde le projet existant ;
4. bascule vers Vysi 0.8.1 ;
5. recrée `.vysi` ;
6. installe les dépendances ;
7. exécute Ruff, mypy, tests, schémas et contrats ;
8. exécute les smoke tests sans rendu ;
9. exécute les smoke tests avec rendu DS11 ;
10. exécute la recette post-installation DS14 sur un cas synthétique et, si fourni, un document réel ;
11. affiche les valeurs réellement lues dans `validation_report.json` ;
12. commit l’installation seulement après toutes les validations ;
13. restaure l’ancienne installation en cas d’échec.

## Installation

```bash
cd "$HOME/Téléchargements/vysi_0.8.1_DOCUMENT_SOURCE_DS11_MULTIFORMAT_TRUTHFULNESS"
chmod +x install_vysi_0.8.1.sh
VYSI_ACCEPTANCE_SOURCE=/chemin/document.docx ./install_vysi_0.8.1.sh
```

## Contrôles manuels

```bash
cd "$HOME/Mes_Projets/vysi"
source .vysi/bin/activate
./scripts/check_all.sh
./scripts/smoke_document_source_rendering.sh
./scripts/smoke_document_source_quality_rendered.sh
./scripts/smoke_document_source_validation_rendered.sh
./scripts/post_install_acceptance.sh /chemin/document.docx
```

## Variables

```text
VYSI_TARGET                    chemin d’installation
VYSI_BACKUP_DIR                dossier des sauvegardes
VYSI_PYTHON                    interpréteur Python
VYSI_ACCEPTANCE_SOURCE         document réel optionnel
VYSI_TEST_FILE_TIMEOUT_SECONDS délai groupé pytest
VYSI_TEST_NODE_TIMEOUT_SECONDS délai par nœud pytest
VYSI_FORCE_INSTALL_FAILURE     injection de panne pour tester le rollback
```

## Campagne de corpus multiformat réel

Vysi 0.8.1 conserve les outils de campagne utilisés pour DS11 :

```bash
COUNT_PER_TYPE=10 MAX_TOTAL_GB=10 YES=1 \
  ./scripts/download_and_test_vysi_real_corpus.sh
```

Le téléchargement et l'exécution sont séparables :

```bash
./scripts/run_vysi_multiformat_acceptance.sh \
  "$HOME/Documents/vysi_real_corpus"
```

Ces scripts produisent des rapports de campagne hors des artefacts contractuels du pipeline. Ils ne modifient pas les contrats DS00–DS14 et ne doivent pas produire `COMMITTED`.
