# Rapport d'implémentation — DOCUMENT_SOURCE DS00–DS06 — Vysi 0.3.0

## Périmètre

Cette version implémente le tronc commun DS00 à DS06. Elle ne décode pas encore les structures natives
complètes et ne produit pas de package final DS15.

## Sorties

- `request/source_ingestion_request.json`
- `request/normalized_source_request.json`
- `request/policy_set.json`
- `manifests/acquired_source_bundle.json`
- `manifests/format_probe_report.json`
- `manifests/security_clearance.json`
- `manifests/source_identity_manifest.json`
- `manifests/access/*.json`
- `execution/run_manifest.json`
- `execution/error_catalog.json`
- `execution/checkpoint_manifest.json`
- `PREFLIGHT_COMPLETE`

## Erratum contractuel

L'implémentation a démontré que deux liens de provenance étaient indispensables :

1. `NormalizedSourceRequest.normalized_sources` ;
2. `AcquiredSourceBundle.artifacts[].source_locator_id`.

Ces deux contrats passent en 2.1.0. Les autres contrats restent en 2.0.0.

## Garanties

- préservation des octets acquis ;
- hash SHA-256 streaming ;
- absence d'exécution active ;
- absence de réseau ;
- détection non fondée sur l'extension seule ;
- reprise après checkpoint partiel ;
- conversion des exceptions aux frontières de sous-unités ;
- absence de `COMMITTED` avant DS15.

## Limites conscientes

- pas de téléchargement URL ;
- pas de déchiffrement ;
- pas de sandbox système séparée, car aucune opération de décodage risquée n'est encore exécutée ;
- inventaire profond des conteneurs reporté à DS07 ;
- décodage natif contractuel reporté à DS08–DS09.
