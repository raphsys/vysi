# 09 — Modèle de rendu source

Le rendu est optionnel, isolé et non canonique. Il produit des `RenderedView` et `RenderedSurface`.

Le profil de rendu trace : moteur, version, OS/container, locale, timezone, DPI, polices et substitutions,
paramètres d'impression, mise à jour des champs, politique de calcul, accès externe, macros, warnings et
hash de l'environnement.

Types de surfaces : page fixe, page fluide calculée, page d'impression de feuille, slide, canvas raster,
aperçu texte et thumbnail. Une slide native et sa surface rendue restent deux objets distincts.
