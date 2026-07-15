class AIServiceError(Exception):
    """Base class for every failure in the AI layer."""

    user_message = "The AI service is unavailable right now. Please try again."


class ConfigurationError(AIServiceError):
    user_message = "The AI service is not configured. Check OPENROUTER_API_KEY."


class RateLimitError(AIServiceError):
    user_message = "Rate limit reached. Please wait a moment and try again."


class TimeoutError(AIServiceError):
    user_message = "The AI service took too long to respond. Please try again."


class UpstreamError(AIServiceError):
    """Non-retryable HTTP error from OpenRouter (bad key, bad model id, 4xx)."""

    user_message = "The AI service rejected the request. Please try again later."


class ParseError(AIServiceError):
    """The model replied, but not with JSON we could use."""

    user_message = "The AI returned an unreadable response. Please try again."

    def __init__(self, message, raw_response=""):
        super().__init__(message)
        # Kept so failures can be logged and inspected — this is the single most
        # useful thing to have when debugging a free-tier model.
        self.raw_response = raw_response
