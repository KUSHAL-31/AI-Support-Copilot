class CopilotError(Exception):
    """Base application exception."""


class ProviderError(CopilotError):
    """Raised when an external AI provider fails."""


class IngestionError(CopilotError):
    """Raised when document ingestion fails."""


class RetrievalError(CopilotError):
    """Raised when retrieval cannot complete."""


class LowConfidenceAnswer(CopilotError):
    """Raised when the system cannot produce a grounded answer."""
