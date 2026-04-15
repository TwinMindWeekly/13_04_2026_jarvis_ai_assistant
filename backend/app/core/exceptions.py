from fastapi import HTTPException, status


class ProviderNotFoundError(HTTPException):
    def __init__(self, provider: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM provider '{provider}' is not supported. Use GET /api/providers for available options.",
        )


class ProviderAuthError(HTTPException):
    def __init__(self, provider: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"API key for provider '{provider}' is missing or invalid. Check your .env file.",
        )


class ProviderConnectionError(HTTPException):
    def __init__(self, provider: str, reason: str = ""):
        detail = f"Failed to connect to provider '{provider}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )


class ChatError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {message}",
        )
