# 06 — Modèle de conteneur

Le catalogue couvre ZIP/OOXML, OLE/CFB, PDF, frames image, archives et conteneurs futurs.

Chaque partie ou stream possède : identité déterministe, chemin portable normalisé, taille compressée et
non compressée, hash si lu, type média, compression, relation parent, état de lecture, drapeaux de sécurité
et référence opaque de préservation.

Les noms dupliqués, traversées de chemin, chevauchements, cycles, entrées chiffrées, ratios anormaux et
incohérences de tables sont enregistrés. Inventorier n'autorise pas à exécuter ni à extraire hors sandbox.
