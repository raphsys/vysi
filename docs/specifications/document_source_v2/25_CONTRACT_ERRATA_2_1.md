# 25 — Errata contractuels 2.1.0 issus de l'implémentation DS00–DS06

Le gel 2.0.0 contenait deux omissions incompatibles avec une reprise et une provenance exactes.

1. `NormalizedSourceRequest` expose désormais `normalized_sources`. La requête originale reste immuable ;
   les localisations résolues sont persistées explicitement et peuvent être rejouées.
2. Chaque artefact de `AcquiredSourceBundle` expose `source_locator_id`. Cette relation est nécessaire pour
   la provenance, les secrets référencés, les diagnostics et les acquisitions multi-sources.

Ces ajouts portent les deux contrats concernés en `2.1.0`. Les autres contrats restent en `2.0.0`.
Aucun champ existant n'a changé de sens. L'implémentation refuse tout contournement implicite de ces liens.
