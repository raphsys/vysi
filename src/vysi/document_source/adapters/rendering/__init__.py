"""Adaptateurs de rendu source DS11.

Tout backend externe doit implémenter :class:`SourceRenderer`, déclarer ses
capacités avant ouverture de la source et produire uniquement les objets
intermédiaires validés par DS11. Le backend intégré est enregistré dans
``rendering_v2.backend``.
"""
