PIPELINE.md
File
doc_parser_v2 : C'est un dossier dans lequel on reprends tout le projet à zero.

VOICI CE QUE ON A FAIT A PRESENT: 

On va créer un nouveau dossier et reprendre de zero le projet en partant du
  contrat canonique. vraiment de zero. Certes pour les fichiers, on va voir si
  il y en a pour s'en inspirer. L'actuel projet est trop confus.


• Je crée un projet isolé dans docs_parser_v2/, sans dépendance vers l’ancien
  code. Je n’y porte d’abord que le modèle canonique, ses invariants et des
  tests ; les anciens fichiers resteront uniquement des références ponctuelles,
  jamais des imports.

────────────────────────────────────────────────────────────────────────────────

• Le socle est créé sans copier le pipeline existant : domaine pur, interfaces,
  architecture, TODO et tests d’isolation. Je valide maintenant que le paquet
  s’installe conceptuellement seul et que ses invariants échouent correctement
  sur les états contradictoires.

────────────────────────────────────────────────────────────────────────────────

• Nouveau projet créé dans docs_parser_v2.

  Il contient uniquement :

  - PageModel canonique et ses invariants
  - Interfaces extraction/rendu/audit
  - Architecture indépendante
  - Nouveau TODO
  - Aucun import de l’ancien projet
  - 7 tests passants

  Prochaine étape définie : créer un format d’entrée minimal et trois pages de
  référence avant tout moteur.


› Que dit PageModel ?



› Non non.


• Tu veux voir le contenu exact du fichier PageModel, ou savoir quelle vision
  fonctionnelle du produit il impose ?


› On reprends de 0
  Efface tout et suis mes instructions


• J’efface uniquement le nouveau projet docs_parser_v2. Je ne touche pas au
  projet historique ni à ses fichiers. Ensuite, j’attends tes instructions sans
  recréer de structure ni faire d’hypothèse.

────────────────────────────────────────────────────────────────────────────────

• docs_parser_v2 est désormais vide. J’attends tes instructions.


› On décrit le pipeline d'abord ! Go !


• Je commence uniquement par la spécification du pipeline : entrées, étapes,
  sorties, responsabilités et conditions d’arrêt. Aucun modèle de données ni
  code métier avant validation de ce document.

────────────────────────────────────────────────────────────────────────────────

• Le pipeline initial est décrit dans docs_parser_v2/PIPELINE.md.

  Aucun code ni modèle n’a été créé. Cette description doit être validée ou
  corrigée avant la suite.
Thought for 6s

J’ai compris l’état exact du projet.

docs_parser_v2/ a été vidé, puis repris sans code, sans PageModel et sans reprise implicite de l’ancien pipeline. À ce stade, la seule fondation est PIPELINE.md, qui décrit la chaîne fonctionnelle avant toute conception de schéma ou d’implémentation.

Mon verdict sur PIPELINE.md

Le document pose une bonne architecture générale. Les séparations essentielles sont présentes :

observation factuelle ;
compréhension ;
décision ;
traduction ;
préparation du fond ;
résolution géométrique ;
compilation des opérations ;
exécution du rendu ;
validation du rendu réel ;
livraison reproductible.

La règle la plus importante est également correcte :

une étape observe, décide ou exécute ; elle ne mélange pas ces responsabilités.

C’est précisément ce qui manquait au projet historique.

Cependant, le pipeline n’est pas encore suffisamment défini pour servir de contrat fondateur. Il décrit bien ce qui doit se passer, mais pas encore assez précisément :

quels objets circulent ;
qui possède chaque objet ;
quels états sont autorisés ;
comment une étape prouve qu’elle a terminé ;
comment les ambiguïtés sont représentées ;
comment une erreur locale est corrigée ou escaladée ;
quelles données sont immuables et lesquelles sont dérivées ;
comment les décisions documentaires et les décisions page par page s’articulent.

Il ne faut donc pas encore créer PageModel.

1. Ce qui doit absolument être conservé
Séparation entre observations et interprétation

L’étape 2 doit rester strictement factuelle.

Elle ne doit jamais décider :

qu’un texte est un titre ;
qu’un objet doit être traduit ;
qu’une image doit rester dans le fond ;
qu’un bloc appartient à une légende ;
qu’un élément est décoratif.

Elle doit seulement produire des observations avec :

moteur ;
version ;
bbox ;
espace de coordonnées ;
valeur observée ;
confiance ;
preuve ou ressource source ;
éventuels résultats concurrents.
Décision canonique avant reconstruction

La reconstruction ne doit jamais décider ce qui doit être préservé ou traduit.

Elle reçoit une décision déjà prise, puis résout uniquement :

la place ;
la taille ;
les ruptures ;
les collisions ;
les contraintes géométriques ;
les paramètres de rendu.
Render plan unique

L’étape 8 est fondamentale.

Le PDF, le PNG de contrôle et les autres backends doivent consommer le même plan de rendu. Ils peuvent différer dans leur implémentation technique, mais pas dans :

le contenu ;
les positions ;
l’ordre des opérations ;
les objets à afficher ;
les styles résolus.
Validation après rendu

Il faut conserver la règle :

aucune validation finale ne peut se limiter au modèle interne ou au plan de rendu.

Une opération correcte sur le papier peut être mal exécutée par un backend. La validation doit donc examiner le fichier réellement généré.

2. Première correction conceptuelle : distinguer les types de décisions

La phrase suivante est juste dans son intention, mais trop large :

Attribuer à chaque unité source une seule destination finale.

Une unité peut participer à plusieurs relations sans être dupliquée dans le rendu.

Par exemple, un texte peut être simultanément :

contenu d’un bloc ;
titre d’une figure ;
membre d’un ordre de lecture ;
ancre d’un objet graphique ;
élément d’une structure sémantique.

Ce qui doit être unique n’est pas toute son appartenance au modèle, mais sa disposition de rendu principale.

Il faut donc distinguer :

Relations sémantiques

Elles peuvent être multiples :

contains
belongs_to
caption_of
label_of
reads_before
anchored_to
continuation_of
overlaps
derived_from
Destination canonique de rendu

Elle doit être unique pour une exécution donnée :

translate_and_redraw
preserve_text_exactly
preserve_pixels
retain_in_background
reconstruct_as_graphic
exclude_as_artifact

Ainsi, une unité peut posséder plusieurs relations, mais une seule destination de rendu.

3. Il manque une analyse au niveau du document

Le pipeline passe directement de l’extraction des pages à la compréhension de page.

Or de nombreuses décisions ne peuvent pas être prises page par page isolément :

détection des en-têtes et pieds de page répétés ;
identification des numéros de page ;
styles typographiques globaux ;
table des matières ;
chapitres et sections ;
continuité des paragraphes entre pages ;
légendes récurrentes ;
tableaux répartis sur plusieurs pages ;
terminologie ;
pages maîtresses ;
familles de pages ;
marges et grilles éditoriales ;
objets récurrents ;
distinction entre couverture, corps, annexe et index.

Il faut donc introduire une étape explicite de compréhension documentaire.

La séquence devrait devenir :

Extraction factuelle
        ↓
Compréhension locale de chaque page
        ↓
Compréhension globale du document
        ↓
Réconciliation page ↔ document
        ↓
Décision canonique

La compréhension globale ne remplace pas la compréhension de page. Elle la corrige et la complète.

4. Il manque une phase explicite de réconciliation des observations

Plusieurs moteurs peuvent fournir des résultats contradictoires :

PDF natif : "rn"
OCR : "m"
détecteur typographique : Helvetica 10 pt
analyse raster : police visuellement différente
moteur de layout : deux blocs
extracteur PDF : un seul bloc

L’étape 2 produit des observations. Mais l’étape 3 ne doit pas consommer directement un ensemble incohérent sans procédure formelle.

Il faut une sous-étape :

Réconciliation factuelle

Elle doit :

regrouper les observations portant sur le même objet probable ;
conserver les hypothèses concurrentes ;
calculer les accords et désaccords ;
sélectionner une observation principale sans supprimer les autres ;
signaler les conflits non résolus ;
établir une géométrie de référence ;
produire une confiance agrégée explicable.

La valeur retenue ne doit jamais remplacer silencieusement les preuves initiales.

5. Le concept d’unité doit rester indéfini pour l’instant

Il serait prématuré de créer un PageModel, parce que le pipeline ne dit pas encore clairement ce qu’est une unité.

Il faudra distinguer au minimum :

observation ;
entité source ;
entité sémantique ;
unité de traduction ;
unité de mise en page ;
objet visuel ;
opération de rendu ;
résultat de rendu ;
constat d’audit.

Un même bloc OCR ne doit pas automatiquement devenir :

unité source
= unité de traduction
= unité de reconstruction
= opération de rendu

C’est précisément ce type de fusion qui a rendu l’ancien projet confus.

Exemple :

Un paragraphe source
    ├── plusieurs observations OCR/PDF
    ├── une entité sémantique
    ├── une ou plusieurs unités de traduction
    ├── plusieurs lignes de mise en page
    └── plusieurs opérations graphiques de rendu

Ces objets doivent être reliés, mais non confondus.

6. La traduction doit être divisée en plusieurs responsabilités

L’étape 5 est actuellement trop compacte.

Elle rassemble :

construction des unités ;
protection des fragments ;
traduction ;
restauration ;
validation.

Il faut au moins distinguer :

Préparation de traduction
sélection des unités autorisées ;
constitution du contexte ;
fusion ou fragmentation linguistique ;
identification des éléments protégés ;
définition du registre, domaine et ton ;
contraintes de longueur ;
dépendances entre unités.
Exécution de traduction
appel du moteur ;
conservation de toutes les variantes éventuelles ;
journal des paramètres ;
correspondance source-cible.
Contrôle linguistique
couverture ;
langue cible ;
omission ;
répétition ;
préservation des tokens ;
cohérence terminologique ;
qualité grammaticale ;
cohérence inter-unités.
Acceptation canonique

Une seule version traduite est ensuite attachée à l’unité source pour l’exécution courante.

Le moteur de traduction ne doit pas modifier directement le modèle source.

7. La préparation du fond ne doit pas dépendre uniquement d’un effacement raster

Le terme « retirer du fond » peut induire une architecture trop orientée image.

Il existe plusieurs cas :

texte natif PDF à supprimer d’une couche vectorielle ;
texte raster à inpeindre ;
texte faisant partie d’une photographie et devant être conservé ;
texte intégré à un schéma à reconstruire ;
élément mixte texte + forme ;
masque transparent ;
texture à restaurer ;
couche de fond déjà propre ;
objet réutilisable tel quel.

L’étape devrait plutôt s’appeler :

Préparation des substrats visuels

Elle produirait :

fonds réutilisables ;
fonds nettoyés ;
objets vectoriels préservés ;
objets raster préservés ;
masques ;
zones à restaurer ;
preuves de suppression ;
zones interdites à l’inpainting ;
ressources dérivées.

Ainsi, le nettoyage raster n’est qu’une stratégie parmi d’autres.

8. La reconstruction géométrique doit produire un état résolu, mais aussi ses compromis

Le document dit correctement qu’aucun backend ne doit recalculer la mise en page.

Mais la géométrie finale doit également conserver :

les contraintes initiales ;
les contraintes relâchées ;
les alternatives examinées ;
la solution retenue ;
les déplacements appliqués ;
les réductions de police ;
les changements d’interligne ;
les changements de largeur ;
les ruptures supplémentaires ;
les déplacements d’objets adjacents ;
le niveau de dégradation ;
la raison de chaque compromis.

Sinon, le résultat sera difficile à auditer.

Une solution géométrique ne doit pas uniquement dire :

bbox finale = [...]
font_size = 9.4

Elle doit aussi expliquer :

font_size source = 11
minimum autorisé = 9
taille retenue = 9.4
raison = expansion française de 28 %
autres options rejetées = débordement / collision avec figure
9. Les arrêts doivent être transformés en une vraie politique d’échec

Le document mentionne plusieurs conditions d’arrêt, mais il faut définir trois niveaux.

Erreur fatale

L’exécution complète ne peut pas continuer :

fichier illisible ;
identité source non calculable ;
page impossible à décoder ;
corruption du modèle canonique ;
absence de propriétaire pour une unité ;
divergence non maîtrisée des espaces de coordonnées.
Échec local de page ou d’unité

Le reste du document peut être analysé :

OCR insuffisant sur une zone ;
traduction refusée ;
objet graphique impossible à reconstruire ;
collision non résolue sur une page.
Demande de revue

Le pipeline a une solution possible mais ne peut pas la garantir :

ambiguïté sémantique ;
faible confiance ;
modification typographique importante ;
conservation probable d’un texte dans une image ;
réduction de police proche du seuil.

Il faut éviter qu’une page en échec empêche forcément l’analyse de 479 autres pages. En revanche, la publication globale peut rester bloquée.

10. Il manque le cycle de correction

Le pipeline est présenté comme une ligne droite :

ingestion → extraction → compréhension → ... → validation

En pratique, la validation peut révéler :

un texte manquant ;
un mauvais masque ;
une collision ;
une classification erronée ;
une traduction incorrecte ;
un problème de backend.

Il faut interdire les boucles implicites, mais prévoir des boucles contrôlées.

Exemple :

Validation
   ↓
Diagnostic attribué à une étape propriétaire
   ↓
Nouvelle révision de cette étape
   ↓
Recompilation des étapes dépendantes
   ↓
Nouveau rendu
   ↓
Nouvelle validation

La correction doit produire une nouvelle révision, et non muter silencieusement les résultats précédents.

11. Les états doivent être versionnés et immuables

Pour une exécution donnée, les sorties de chaque étape doivent être enregistrées comme des snapshots :

source_snapshot
observation_snapshot
understanding_snapshot
decision_snapshot
translation_snapshot
visual_substrate_snapshot
layout_snapshot
render_plan_snapshot
render_result_snapshot
audit_snapshot
delivery_manifest

Chaque snapshot doit avoir :

identifiant ;
version de schéma ;
hash ;
parent ;
horodatage ;
moteurs et versions ;
paramètres ;
statut ;
liste des erreurs ;
liste des avertissements.

Une correction génère un nouveau snapshot.

12. Pipeline révisé recommandé

Je recommande de figer d’abord cette séquence conceptuelle :

0. Définition de l’exécution
1. Ingestion et normalisation de la source
2. Extraction factuelle multicanale
3. Réconciliation des observations
4. Compréhension locale des pages
5. Compréhension globale du document
6. Réconciliation page-document
7. Inventaire canonique et attribution des propriétaires
8. Décision canonique de traitement
9. Préparation et exécution de la traduction
10. Validation linguistique
11. Préparation des substrats visuels
12. Résolution géométrique
13. Compilation du plan de rendu
14. Exécution des backends
15. Validation des fichiers réellement rendus
16. Diagnostic et éventuelle révision contrôlée
17. Publication et livraison reproductible

Cela ne signifie pas qu’il faudra dix-huit programmes indépendants. Ce sont des responsabilités conceptuelles. Certaines pourront appartenir au même paquet, à condition que leurs contrats restent distincts.

Conclusion

PIPELINE.md est un bon premier cadrage, nettement plus sain que l’architecture historique. Mais il reste encore trop général pour créer les classes centrales.

La prochaine étape correcte n’est pas PageModel.

La prochaine étape correcte est de compléter la spécification avec quatre documents conceptuels :

PIPELINE.md
VOCABULARY.md
STATES_AND_OWNERSHIP.md
INVARIANTS.md
ERROR_AND_REVIEW_POLICY.md

Ensuite seulement, il sera possible de définir le contrat canonique sans reproduire les confusions de l’ancien projet.

Pasted text.txt
Document
Voici l'architecture de validation_corpus/document_source/source 

Donc on fait la validation sur ce corpus

diagnostic.json
File
README.txt
Document
sources-derived-images-tiff_multiframe-multipage.json
File
Pasted text.txt
Document
erreur du correctif
acceptance_report.html
File
acceptance_report.json
File
run.log
File
(.docs_parser_v2) raphael@debian:~/Mes_Projets/docs_parser_v2$ ./scripts/run_current_corpus_validation.sh "$PWD" public
Préparation des attentes...
Fichiers inventoriés : 522
Attentes créées      : 522
Attentes conservées  : 0
Acceptés attendus    : 518
Rejetés attendus     : 4
Pages séparées       : 480
Cohérence original/pages : True
Inventaire           : /home/raphael/Mes_Projets/docs_parser_v2/validation_corpus/document_source/notes/CORPUS_INVENTORY_20260619T155440Z.json
=== PHASE public : 27 fichier(s) ===
{
  "total": 27,
  "passed": 22,
  "failed": 4,
  "errored": 1,
  "duration_seconds": 452.7699718340009
}

Rapport JSON : /home/raphael/Mes_Projets/docs_parser_v2/validation_corpus/document_source/validation_views/20260619T155439Z/public/reports/20260619T155441Z/acceptance_report.json
Rapport HTML : /home/raphael/Mes_Projets/docs_parser_v2/validation_corpus/document_source/validation_views/20260619T155439Z/public/reports/20260619T155441Z/acceptance_report.html
public: total=27 passed=22 failed=4 errored=1 duration=452.77s
FAIL public rc=1

Je démarre l’implémentation de DS10 — Technical IR Projection à partir de Vysi 0.4.0. Je vais auditer les contrats existants, vérifier la forme exacte des profils natifs et du schéma IR, puis produire une version 0.5.0 installable et validée sans modifier les responsabilités de DS11–DS15.

Le contrat DS10 est suffisant sans nouvel erratum : il permet une projection déterministe, typée et traçable. J’implémente maintenant une projection pure par profil natif, puis une sous-unité d’exécution qui vérifie les hashes, les références, les hiérarchies et l’absence de mutation avant de publier TechnicalDocumentIR.

Le premier contrôle a détecté uniquement trois écarts de style d’import. Aucun défaut fonctionnel n’est encore apparu. Je les corrige puis je relance Ruff, mypy et toute la suite de tests.

Thought for 18m 32s
Vysi 0.5.0 — Implémentation DS10

DS10 — Technical IR Projection est maintenant implémenté et validé.

Télécharger Vysi 0.5.0 — DOCUMENT_SOURCE DS10

SHA-256 :

9fbe399e81ab28c017df914d9de9f6d3974c20e79d0f0b4af550ffb729bcb621
Installation
cd "$HOME/Téléchargements"

unzip -q vysi_0.5.0_DOCUMENT_SOURCE_DS10_IMPLEMENTATION.zip

cd vysi_0.5.0_DOCUMENT_SOURCE_DS10_IMPLEMENTATION

chmod +x install_vysi_0.5.0.sh

./install_vysi_0.5.0.sh

L’installateur :

sauvegarde la version 0.4.0 ;
installe Vysi 0.5.0 ;
recrée .vysi ;
valide le manifest ;
exécute Ruff, mypy et pytest ;
valide les contrats ;
exécute le smoke test DS00–DS10 ;
restaure automatiquement l’ancienne version en cas d’échec.
Ce que DS10 produit

Chaque document natif publié par DS09 est projeté vers :

ir/<document_id>/
└── technical_document_ir.json

Lorsqu’une référence non résolue est rencontrée :

ir/<document_id>/
└── projection_warnings.json

Le checkpoint final porte :

PREFLIGHT_COMPLETE
NATIVE_COMPLETE
IR_COMPLETE

Il ne porte jamais :

COMMITTED

COMMITTED reste réservé à DS15.

Profils natifs pris en charge
Texte brut

Projection de :

lignes ;
texte exact ;
offsets octets ;
encodage ;
style de fin de ligne.
DOCX/DOCM

Projection de :

sections ;
paragraphes ;
runs ;
tableaux ;
lignes ;
cellules ;
en-têtes et pieds de page ;
notes ;
champs ;
contrôles de contenu ;
signets ;
révisions ;
annotations.

Aucune classification en titre, chapitre, corps de texte ou légende n’est effectuée.

XLSX/XLSM

Projection de :

feuilles ;
visibilité des feuilles ;
cellules ;
adresses ;
valeurs brutes ;
valeurs mises en cache ;
styles ;
formules ;
dépendances ;
fonctions volatiles.

Invariant :

formula.recalculated = false

Les formules sont conservées et protégées, jamais exécutées.

PPTX/PPTM

Projection de :

slides ;
formes ;
groupes ;
objets visuels ;
textes de formes ;
transitions ;
animations ;
notes et références de layouts/masters.

Le texte « Titre » d’une forme reste un texte natif. DS10 ne le transforme pas en unité sémantique title.

PDF

Projection de :

pages fixes ;
dimensions ;
rotation ;
références de boîtes ;
annotations techniques.

DS10 ne réalise ni OCR ni analyse graphique avancée.

Images

Projection de :

frames ;
dimensions ;
durée ;
orientation ;
profils ICC ;
politique de surfaces.

La distinction reste explicite :

GIF/WebP animé → plusieurs frames, une surface documentaire
TIFF multipage → une surface documentaire par frame
DOC/XLS/PPT historiques

Projection technique de :

storages OLE ;
streams ;
tailles ;
hashes ;
état de lecture.

Ces unités restent protégées et le statut demeure review, car la couverture native est encore inventory_only.

Traçabilité

Chaque unité IR possède :

unit_id
kind
parent_id
ordinal
origin
source_native_ids
text
protected
style_refs
resource_refs
technical_properties

Deux origines seulement sont autorisées :

native_projection
synthetic

Une unité native_projection doit obligatoirement référencer au moins une unité native.

Une unité synthetic ne peut pas prétendre provenir directement d’une unité native.

Invariants vérifiés

DS10 rejette :

les contrats natifs dont le hash canonique est invalide ;
les fichiers référencés dont le SHA-256 est incorrect ;
les contract_id incohérents ;
les profils rattachés à un autre document ;
les catalogues rattachés à un autre document ;
les identifiants IR dupliqués ;
les parents orphelins ;
les auto-parentages ;
les cycles hiérarchiques ;
les occurrences pointant vers une ressource absente ;
les profils non projetables.

Il garantit également :

OCR exécutée                  = false
interprétation sémantique     = false
recalcul des formules         = false
mutation des entrées          = false
Erratum contractuel 2.3

L’implémentation a détecté une erreur dans le schéma commun typedValue.

Le schéma utilisait :

"oneOf": [
  {"type": "number"},
  {"type": "integer"}
]

En JSON Schema, une valeur entière satisfait également le type number. Elle était donc rejetée parce qu’elle validait deux branches de oneOf.

La correction est :

"anyOf": [
  {"type": "number"},
  {"type": "integer"}
]

La liste des types autorisés ne change pas. Cet erratum ne rend pas les propriétés libres.

Commandes après installation
cd "$HOME/Mes_Projets/vysi"
source .vysi/bin/activate

./scripts/check_all.sh
./scripts/smoke_document_source_ir.sh

Exécution sur un document :

vysi ir \
  --source "/chemin/vers/document.docx" \
  --output runtime/results/document_source

Reprise d’un checkpoint DS09 existant :

vysi ir \
  --request request.json \
  --resume-from runtime/results/document_source/preflight-run_<id> \
  --output runtime/results/document_source
Validation obtenue
Version Vysi                : 0.5.0
Fichiers manifestés         : 313
Documents normatifs         : 28
Sous-unités spécifiées      : 16
Profils natifs              : 7
Schémas JSON                : 41
Codes d’erreur              : 54
Fichiers mypy strict        : 70
Tests                       : 64/64
Exemples valides            : 40
Exemples invalides rejetés  : 9
Ruff                        : PASS
mypy strict                 : PASS
Validation contractuelle    : PASS
Smoke DS00–DS10             : PASS
Installation isolée         : PASS
Archive ZIP                 : PASS
Rollback transactionnel     : PASS

Le rollback a été vérifié en corrompant volontairement un fichier manifesté. L’installation a détecté l’écart de taille et de SHA-256 puis restauré le projet précédent.

La prochaine tranche est DS12–DS13 : cartographie des représentations, couverture, fidélité et préservation. Conformément à l’ordre gelé, DS11 — rendu optionnel — sera implémenté après stabilisation de ces contrats de contrôle.

(.vysi) raphael@debian:~/Mes_Projets/vysi$ cd "$HOME/Mes_Projets/vysi"
source .vysi/bin/activate

./scripts/check_all.sh
./scripts/smoke_document_source_native.sh
Python : 3.10.20
Vysi   : 0.4.0
No broken requirements found.
Structure valide : 16 groupes, 16 sous-unités, 7 profils, 41 schémas.
Spécification gelée valide : 27 documents normatifs, 16 sous-unités, 41 schémas, 54 codes d’erreur.
Manifest projet valide : 305 fichiers, version 0.4.0.
All checks passed!
Success: no issues found in 67 source files
....................................................                     [100%]
52 passed in 27.42s
DOCUMENT_SOURCE contracts valid: 41 schemas, 40 valid examples, 9 rejected invalid examples.
VYSI 0.4.0 — DOCUMENT_SOURCE DS00–DS09 : VALIDATION COMPLETE
Checkpoint DS00–DS09 valide
Smoke DS00-DS09 réussi : /home/raphael/Mes_Projets/vysi/runtime/results/document_source/preflight-run_b4ertthxfahcn5pdguono5x4vt
(.vysi) raphael@debian:~/Mes_Projets/vysi$ cd "$HOME/Téléchargements"

unzip -q vysi_0.5.0_DOCUMENT_SOURCE_DS10_IMPLEMENTATION.zip

cd vysi_0.5.0_DOCUMENT_SOURCE_DS10_IMPLEMENTATION

chmod +x install_vysi_0.5.0.sh

./install_vysi_0.5.0.sh
Interpréteur sélectionné : /home/raphael/.pyenv/versions/3.10.20/bin/python (3.10.20)
[1/8] Sauvegarde du projet Vysi existant
[2/8] Installation de Vysi 0.5.0
[3/8] Création de l'environnement .vysi
[4/8] Installation du projet et des outils
Requirement already satisfied: pip in ./.vysi/lib/python3.10/site-packages (23.0.1)
Collecting pip
  Using cached pip-26.1.2-py3-none-any.whl (1.8 MB)
Requirement already satisfied: setuptools in ./.vysi/lib/python3.10/site-packages (79.0.1)
Collecting setuptools
  Using cached setuptools-82.0.1-py3-none-any.whl (1.0 MB)
Collecting wheel
  Using cached wheel-0.47.0-py3-none-any.whl (32 kB)
Collecting packaging>=24.0
  Using cached packaging-26.2-py3-none-any.whl (100 kB)
Installing collected packages: setuptools, pip, packaging, wheel
  Attempting uninstall: setuptools
    Found existing installation: setuptools 79.0.1
    Uninstalling setuptools-79.0.1:
      Successfully uninstalled setuptools-79.0.1
  Attempting uninstall: pip
    Found existing installation: pip 23.0.1
    Uninstalling pip-23.0.1:
      Successfully uninstalled pip-23.0.1
Successfully installed packaging-26.2 pip-26.1.2 setuptools-82.0.1 wheel-0.47.0
Obtaining file:///home/raphael/Mes_Projets/vysi
  Installing build dependencies ... done
  Checking if build backend supports build_editable ... done
  Getting requirements to build editable ... done
  Preparing editable metadata (pyproject.toml) ... done
Collecting pytest<10,>=8 (from vysi==0.5.0)
  Using cached pytest-9.1.1-py3-none-any.whl.metadata (7.6 kB)
Collecting jsonschema<5,>=4.20 (from vysi==0.5.0)
  Using cached jsonschema-4.26.0-py3-none-any.whl.metadata (7.6 kB)
Collecting ruff<1,>=0.8 (from vysi==0.5.0)
  Using cached ruff-0.15.18-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (26 kB)
Collecting mypy<2,>=1.10 (from vysi==0.5.0)
  Using cached mypy-1.20.2-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.4 kB)
Collecting types-jsonschema<5,>=4.23 (from vysi==0.5.0)
  Using cached types_jsonschema-4.26.0.20260518-py3-none-any.whl.metadata (1.8 kB)
Collecting attrs>=22.2.0 (from jsonschema<5,>=4.20->vysi==0.5.0)
  Using cached attrs-26.1.0-py3-none-any.whl.metadata (8.8 kB)
Collecting jsonschema-specifications>=2023.03.6 (from jsonschema<5,>=4.20->vysi==0.5.0)
  Using cached jsonschema_specifications-2025.9.1-py3-none-any.whl.metadata (2.9 kB)
Collecting referencing>=0.28.4 (from jsonschema<5,>=4.20->vysi==0.5.0)
  Using cached referencing-0.37.0-py3-none-any.whl.metadata (2.8 kB)
Collecting rpds-py>=0.25.0 (from jsonschema<5,>=4.20->vysi==0.5.0)
  Using cached rpds_py-0.30.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.1 kB)
Collecting typing_extensions>=4.6.0 (from mypy<2,>=1.10->vysi==0.5.0)
  Using cached typing_extensions-4.15.0-py3-none-any.whl.metadata (3.3 kB)
Collecting mypy_extensions>=1.0.0 (from mypy<2,>=1.10->vysi==0.5.0)
  Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
Collecting pathspec>=1.0.0 (from mypy<2,>=1.10->vysi==0.5.0)
  Using cached pathspec-1.1.1-py3-none-any.whl.metadata (14 kB)
Collecting tomli>=1.1.0 (from mypy<2,>=1.10->vysi==0.5.0)
  Using cached tomli-2.4.1-py3-none-any.whl.metadata (10 kB)
Collecting librt>=0.8.0 (from mypy<2,>=1.10->vysi==0.5.0)
  Using cached librt-0.11.0-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (1.3 kB)
Collecting exceptiongroup>=1 (from pytest<10,>=8->vysi==0.5.0)
  Using cached exceptiongroup-1.3.1-py3-none-any.whl.metadata (6.7 kB)
Collecting iniconfig>=1.0.1 (from pytest<10,>=8->vysi==0.5.0)
  Using cached iniconfig-2.3.0-py3-none-any.whl.metadata (2.5 kB)
Requirement already satisfied: packaging>=22 in ./.vysi/lib/python3.10/site-packages (from pytest<10,>=8->vysi==0.5.0) (26.2)
Collecting pluggy<2,>=1.5 (from pytest<10,>=8->vysi==0.5.0)
  Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
Collecting pygments>=2.7.2 (from pytest<10,>=8->vysi==0.5.0)
  Using cached pygments-2.20.0-py3-none-any.whl.metadata (2.5 kB)
Using cached jsonschema-4.26.0-py3-none-any.whl (90 kB)
Using cached mypy-1.20.2-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (14.7 MB)
Using cached pytest-9.1.1-py3-none-any.whl (386 kB)
Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
Using cached ruff-0.15.18-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (11.6 MB)
Using cached types_jsonschema-4.26.0.20260518-py3-none-any.whl (16 kB)
Using cached attrs-26.1.0-py3-none-any.whl (67 kB)
Using cached exceptiongroup-1.3.1-py3-none-any.whl (16 kB)
Using cached iniconfig-2.3.0-py3-none-any.whl (7.5 kB)
Using cached jsonschema_specifications-2025.9.1-py3-none-any.whl (18 kB)
Using cached librt-0.11.0-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (496 kB)
Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
Using cached pathspec-1.1.1-py3-none-any.whl (57 kB)
Using cached pygments-2.20.0-py3-none-any.whl (1.2 MB)
Using cached referencing-0.37.0-py3-none-any.whl (26 kB)
Using cached rpds_py-0.30.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (390 kB)
Using cached tomli-2.4.1-py3-none-any.whl (14 kB)
Using cached typing_extensions-4.15.0-py3-none-any.whl (44 kB)
Building wheels for collected packages: vysi
  Building editable for vysi (pyproject.toml) ... done
  Created wheel for vysi: filename=vysi-0.5.0-0.editable-py3-none-any.whl size=1548 sha256=113116ef0a71977a7b34dbbebdf1936afa70f354b4063e137652c25d6211146c
  Stored in directory: /tmp/pip-ephem-wheel-cache-a5vpjjq_/wheels/d8/4a/40/c26b22afc9c82adf1fc724e5a4bca6954e8f0476dba60c9138
Successfully built vysi
Installing collected packages: vysi, typing_extensions, tomli, ruff, rpds-py, pygments, pluggy, pathspec, mypy_extensions, librt, iniconfig, attrs, referencing, mypy, exceptiongroup, types-jsonschema, pytest, jsonschema-specifications, jsonschema
Successfully installed attrs-26.1.0 exceptiongroup-1.3.1 iniconfig-2.3.0 jsonschema-4.26.0 jsonschema-specifications-2025.9.1 librt-0.11.0 mypy-1.20.2 mypy_extensions-1.1.0 pathspec-1.1.1 pluggy-1.6.0 pygments-2.20.0 pytest-9.1.1 referencing-0.37.0 rpds-py-0.30.0 ruff-0.15.18 tomli-2.4.1 types-jsonschema-4.26.0.20260518 typing_extensions-4.15.0 vysi-0.5.0
[5/8] Validation complète
Python : 3.10.20
Vysi   : 0.5.0
No broken requirements found.
Structure valide : 17 groupes, 16 sous-unités, 7 profils, 41 schémas.
Spécification gelée valide : 28 documents normatifs, 16 sous-unités, 41 schémas, 54 codes d’erreur.
Manifest projet valide : 313 fichiers, version 0.5.0.
All checks passed!
Success: no issues found in 70 source files
................................................................         [100%]
64 passed in 36.48s
DOCUMENT_SOURCE contracts valid: 41 schemas, 40 valid examples, 9 rejected invalid examples.
VYSI 0.5.0 — DOCUMENT_SOURCE DS00–DS10 : VALIDATION COMPLETE
[6/8] Smoke test DS00–DS10
Checkpoint DS00–DS10 valide
Smoke DS00-DS10 réussi : /home/raphael/Mes_Projets/vysi/runtime/results/document_source/preflight-run_lzuvhjnmay44x2mnzgf6usp62j
[7/8] Vérification des artefacts
[8/8] Commit de l'installation

VYSI 0.5.0 — DOCUMENT_SOURCE DS00–DS10 INSTALLÉ
Projet         : /home/raphael/Mes_Projets/vysi
Environnement : /home/raphael/Mes_Projets/vysi/.vysi
CLI            : /home/raphael/Mes_Projets/vysi/.vysi/bin/vysi
Contrats       : v2.0.0 + errata ciblés 2.1, 2.2 et 2.3
Sauvegarde     : /home/raphael/Mes_Projets/vysi_backups/vysi_before_0.5.0_20260620T081244Z.tar.gz

Activation :
  cd "/home/raphael/Mes_Projets/vysi"
  source .vysi/bin/activate
Thought for 4s

Installation confirmée. Vysi 0.5.0 est correctement déployé et DS00–DS10 forment maintenant la nouvelle baseline stable.

Version                    : 0.5.0
Manifest                   : 313 fichiers — PASS
Spécifications             : 28 documents — PASS
Schémas                    : 41 — PASS
Ruff                       : PASS
mypy strict                : 70 fichiers — PASS
Tests                      : 64/64 — PASS
Validation contractuelle   : PASS
Smoke DS00–DS10            : PASS

Checkpoint produit :

runtime/results/document_source/
└── preflight-run_lzuvhjnmay44x2mnzgf6usp62j

Sauvegarde de la version précédente :

~/Mes_Projets/vysi_backups/
└── vysi_before_0.5.0_20260620T081244Z.tar.gz

Le pipeline est désormais opérationnel jusqu’à :

DS00–DS06  préflight
DS07       inventaire des conteneurs
DS08       décodage natif
DS09       catalogues natifs
DS10       projection vers TechnicalDocumentIR

Les marqueurs attendus sont présents jusqu’à IR_COMPLETE, sans COMMITTED prématuré.

La prochaine tranche est DS12–DS13 :

cartographie complète entre binaire, conteneur, natif et IR ;
mesure de couverture ;
fidélité par axe ;
préservation ;
pertes, approximations et éléments opaques ;
décision technique ok, review ou ko.

DS11, consacré au rendu optionnel, viendra ensuite s’intégrer dans cette infrastructure de contrôle.
