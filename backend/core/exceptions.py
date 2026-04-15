class ServiceError(Exception):
    """Base exception for service-layer errors."""


class AuthenticationError(ServiceError):
    """Raised for invalid authentication requests."""


class SessionNotFoundError(ServiceError):
    """Raised when a chat session cannot be found for a user."""


class GenerationError(ServiceError):
    """Raised when answer generation fails."""

