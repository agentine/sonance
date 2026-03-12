"""sonance — A zero-dependency, modern Python replacement for pydub."""

__version__ = "0.1.0"

from sonance.audio_segment import AudioSegment
from sonance.exceptions import (
    SonanceException,
    PydubException,
    TooManyMissingFrames,
    InvalidDuration,
    InvalidTag,
    InvalidID3TagVersion,
    CouldntDecodeError,
    CouldntEncodeError,
    MissingAudioParameter,
)

__all__ = [
    "AudioSegment",
    "SonanceException",
    "PydubException",
    "TooManyMissingFrames",
    "InvalidDuration",
    "InvalidTag",
    "InvalidID3TagVersion",
    "CouldntDecodeError",
    "CouldntEncodeError",
    "MissingAudioParameter",
]
