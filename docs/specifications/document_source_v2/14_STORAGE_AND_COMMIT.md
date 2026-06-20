# 14 — Stockage, atomicité et commit

Le package est construit sous `.<run_id>.tmp`, puis validé intégralement avant renommage atomique.

Contenu minimal : request normalisée, artefacts, manifests, contrats, modèles natifs, ressources, rendus,
mappings, rapports, erreurs, audit JSONL, tentatives, checkpoints, `checksums.sha256`, validation et manifeste.

Tous les chemins contractuels sont relatifs et POSIX. Les chemins absolus hôte sont interdits. Le commit
n'est valide que si le manifeste, les hashes, schémas, références et invariants sont valides. Un marqueur
seul ne suffit pas.
