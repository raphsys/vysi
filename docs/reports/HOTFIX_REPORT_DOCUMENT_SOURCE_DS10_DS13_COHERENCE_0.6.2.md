# Rapport de correctif — cohérence DS10–DS13 — Vysi 0.6.2

## 1. Défauts observés sur un DOCX réel

La version 0.6.1 exécutait correctement DS08, DS12 et DS13, mais les rapports réels révélaient trois
incohérences :

1. les approximations de parties du conteneur étaient attribuées à `native_to_technical_ir` au lieu de
   `container_to_native` ;
2. l’axe style pouvait produire `0.0` avec `omitted = 0`, faute de périmètre requis explicite ;
3. DS13 exigeait la projection des métadonnées alors que DS10 ne chargeait pas ce catalogue.

## 2. Décision d’architecture

`TechnicalDocumentIR` reste une projection technique non autoritaire, mais il doit refléter les catalogues
techniques nécessaires aux consommateurs aval. DS10 consomme donc désormais tous les catalogues DS09 :
styles, relations, métadonnées, annotations et ressources.

Les définitions de style deviennent des unités `style_definition`. Elles conservent type, nom natif, parent,
propriétés directes, propriétés résolues et adresse source. Cette projection ne signifie pas que le style est
appliqué à un bloc : seules les références explicites de profil restent dans `style_refs`.

Les métadonnées deviennent des unités `metadata` protégées. Elles conservent espace de noms, nom natif,
valeur typée, sensibilité et adresse source. Elles ne deviennent jamais du texte traduisible.

## 3. Correction DS13

Chaque `FeatureMeasurement` publie désormais :

- `encountered` : éléments observés ;
- `required` : sous-ensemble soumis à une obligation de projection ou de rendu ;
- `preservation_stage` : transition propriétaire de la mesure.

Les scores utilisent uniquement `required`. Un périmètre nul produit `null`. Les pertes héritent directement
de `preservation_stage` ; l’axe général ne sert plus à deviner leur propriétaire.

Le contournement qui rattachait les pertes `container_to_native` à la transition `native_to_technical_ir` a
été supprimé.

## 4. Résultat sur le document réel de contrôle

- styles : 6 rencontrés, 6 requis, 6 projetés, score 1.0 ;
- métadonnées : 18 rencontrées, 18 requises, 18 projetées ;
- sémantique technique : score 1.0 ;
- approximation de 8 parties : perte unique rattachée à `container_to_native` ;
- transition `container→native` : partielle, exactitude inférée, confiance 0.5 ;
- transition `native→technical_ir` : sans perte sur les catalogues techniques ;
- absence de DS11 : transitions visuelles `not_run`, scores visuels `null` ;
- aucun marqueur `COMMITTED`.

## 5. Contrats et validation

L’erratum 2.5 ajoute `required` et `preservation_stage` au schéma de couverture et explicite la projection
DS10 des styles et métadonnées. Deux exemples invalides vérifient le caractère obligatoire et fermé de ces
champs.

La validation de livraison couvre Ruff, mypy strict, 102 tests unitaires et d’intégration, contrats, smoke DS12,
smoke DS13, exécution sur DOCX réaliste, installation isolée et rollback transactionnel.
