"""Projection déterministe des modèles natifs vers TechnicalDocumentIR."""

from .project import ProjectionError, project_document, validate_ir_invariants

__all__ = ["ProjectionError", "project_document", "validate_ir_invariants"]
