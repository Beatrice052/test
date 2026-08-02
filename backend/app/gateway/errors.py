"""Stable Gateway failure taxonomy and retry boundary."""


class GatewayError(RuntimeError):
    code = "GW_ERROR"
    retryable = False


class GatewayUnavailableError(GatewayError):
    code = "GW_UNAVAILABLE"
    retryable = True


class GatewayTimeoutError(GatewayError):
    code = "GW_TIMEOUT"
    retryable = True


class GatewayRateLimitedError(GatewayError):
    code = "GW_RATE_LIMITED"
    retryable = True


class GatewayAuthenticationError(GatewayError):
    code = "GW_AUTHENTICATION"


class GatewayProtocolError(GatewayError):
    code = "GW_PROTOCOL"


class GatewayCapabilityError(GatewayError):
    code = "GW_CAPABILITY"
