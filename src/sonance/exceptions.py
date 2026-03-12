"""Exception hierarchy for sonance (pydub-compatible)."""


class SonanceException(Exception):
    """Base exception for all sonance errors."""


# pydub compatibility alias
PydubException = SonanceException


class TooManyMissingFrames(SonanceException):
    """Raised when too many audio frames are missing or corrupt."""


class InvalidDuration(SonanceException):
    """Raised when an invalid duration value is provided."""


class InvalidTag(SonanceException):
    """Raised when an audio metadata tag is invalid."""


class InvalidID3TagVersion(SonanceException):
    """Raised when an unsupported ID3 tag version is specified."""


class CouldntDecodeError(SonanceException):
    """Raised when audio data cannot be decoded."""


class CouldntEncodeError(SonanceException):
    """Raised when audio data cannot be encoded."""


class MissingAudioParameter(SonanceException):
    """Raised when a required audio parameter is missing."""
