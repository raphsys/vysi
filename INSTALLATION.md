# Installation de Vysi 0.6.1

La livraison officielle contient le projet et `install_vysi_0.6.1.sh`.

L’installateur :

1. vérifie le manifest et les hashes de la livraison ;
2. sélectionne un Python compatible 3.10 à 3.13 ;
3. sauvegarde le projet existant ;
4. installe le nouveau projet de manière transactionnelle ;
5. recrée l’environnement `.vysi` ;
6. installe Vysi et les outils de développement ;
7. exécute la validation complète ;
8. exécute les smoke tests DS12 et DS13 ;
9. restaure automatiquement l’ancienne installation en cas d’échec.

Installation :

```bash
cd "$HOME/Téléchargements/vysi_0.6.1_DOCUMENT_SOURCE_NATIVE_PROPERTY_HOTFIX"
chmod +x install_vysi_0.6.1.sh
./install_vysi_0.6.1.sh
```

Après installation :

```bash
cd "$HOME/Mes_Projets/vysi"
source .vysi/bin/activate
./scripts/check_all.sh
./scripts/smoke_document_source_mapping.sh
./scripts/smoke_document_source_quality.sh
```

Variables facultatives :

```text
VYSI_TARGET       chemin d’installation du projet
VYSI_BACKUP_DIR   dossier des sauvegardes
VYSI_PYTHON       interpréteur Python à utiliser
```
