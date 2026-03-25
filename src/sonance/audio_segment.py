"""AudioSegment — core class for audio manipulation (pydub-compatible)."""

from __future__ import annotations

import array
import math
from typing import Any, Dict, List, Optional, Union

from sonance import pcm as _pcm
from sonance.exceptions import MissingAudioParameter


class AudioSegment:
    """Immutable container for raw PCM audio data.

    All manipulation methods return *new* AudioSegment instances.
    """

    def __init__(
        self,
        data: bytes = b"",
        *,
        metadata: Optional[Dict[str, Any]] = None,
        sample_width: Optional[int] = None,
        frame_rate: Optional[int] = None,
        channels: Optional[int] = None,
    ) -> None:
        if metadata is not None:
            self._sample_width: int = metadata.get(
                "sample_width", sample_width or 2
            )
            self._frame_rate: int = metadata.get(
                "frame_rate", frame_rate or 44100
            )
            self._channels: int = metadata.get("channels", channels or 1)
        else:
            if sample_width is None:
                raise MissingAudioParameter(
                    "sample_width is required (or pass metadata dict)"
                )
            if frame_rate is None:
                raise MissingAudioParameter(
                    "frame_rate is required (or pass metadata dict)"
                )
            if channels is None:
                raise MissingAudioParameter(
                    "channels is required (or pass metadata dict)"
                )
            self._sample_width = sample_width
            self._frame_rate = frame_rate
            self._channels = channels

        self._data: bytes = bytes(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _spawn(
        self,
        data: bytes,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> "AudioSegment":
        """Create a new AudioSegment with the same metadata (or overrides)."""
        meta: Dict[str, Any] = {
            "sample_width": self._sample_width,
            "frame_rate": self._frame_rate,
            "channels": self._channels,
        }
        if overrides:
            meta.update(overrides)
        return AudioSegment(data=data, metadata=meta)

    @staticmethod
    def _sync(
        *segments: "AudioSegment",
    ) -> list["AudioSegment"]:
        """Synchronize segments to the same sample_width, frame_rate, channels."""
        if not segments:
            return []

        # Pick the maximum of each parameter.
        max_sw = max(s._sample_width for s in segments)
        max_fr = max(s._frame_rate for s in segments)
        max_ch = max(s._channels for s in segments)

        result: list[AudioSegment] = []
        for s in segments:
            if s._sample_width != max_sw:
                s = s.set_sample_width(max_sw)
            if s._frame_rate != max_fr:
                s = s.set_frame_rate(max_fr)
            if s._channels != max_ch:
                s = s.set_channels(max_ch)
            result.append(s)
        return result

    @staticmethod
    def _parse_position(val: Any, duration_ms: int = 0) -> int:
        """Convert a position value to milliseconds (int)."""
        if isinstance(val, float):
            return int(val)
        if isinstance(val, int):
            return val
        raise TypeError(f"Cannot parse position: {val!r}")

    @staticmethod
    def bounded(val: int, mn: int, mx: int) -> int:
        """Clamp *val* to [mn, mx]."""
        return builtins_max(mn, builtins_min(val, mx))

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def raw_data(self) -> bytes:
        """Raw PCM audio data."""
        return self._data

    @property
    def sample_width(self) -> int:
        """Bytes per sample (1, 2, 3, or 4)."""
        return self._sample_width

    @property
    def frame_rate(self) -> int:
        """Sample rate in Hz."""
        return self._frame_rate

    @property
    def channels(self) -> int:
        """Number of audio channels (1=mono, 2=stereo)."""
        return self._channels

    @property
    def frame_width(self) -> int:
        """Bytes per frame (``sample_width * channels``)."""
        return self._sample_width * self._channels

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        fw = self.frame_width
        if fw == 0 or self._frame_rate == 0:
            return 0.0
        return len(self._data) / fw / self._frame_rate

    @property
    def array_type(self) -> str:
        """``array.array`` type code matching sample_width."""
        return {1: "b", 2: "h", 4: "i"}.get(self._sample_width, "h")

    @property
    def rms(self) -> int:
        """RMS amplitude of the audio."""
        return _pcm.rms(self._data, self._sample_width)

    @property
    def dBFS(self) -> float:
        """Loudness in dBFS (decibels relative to full scale)."""
        r = self.rms
        if r == 0:
            return -float("inf")
        return 20.0 * math.log10(r / self.max_possible_amplitude)

    @property
    def max(self) -> int:
        """Peak absolute amplitude."""
        return _pcm.max(self._data, self._sample_width)

    @property
    def max_possible_amplitude(self) -> float:
        """Maximum possible amplitude for the current sample width."""
        bits = self._sample_width * 8
        return float(2 ** (bits - 1))

    @property
    def max_dBFS(self) -> float:
        """Maximum dBFS level (peak relative to full scale)."""
        m = self.max
        if m == 0:
            return -float("inf")
        return 20.0 * math.log10(m / self.max_possible_amplitude)

    # ------------------------------------------------------------------
    # Sample access
    # ------------------------------------------------------------------

    def frame_count(self, ms: Optional[float] = None) -> float:
        """Number of frames. If *ms* is given, return frames in that duration."""
        if ms is not None:
            return ms * self._frame_rate / 1000.0
        fw = self.frame_width
        if fw == 0:
            return 0.0
        return float(len(self._data) // fw)

    def get_array_of_samples(self) -> array.array:  # type: ignore[type-arg]
        """Return an ``array.array`` of all samples.

        For 24-bit audio, samples are returned as 32-bit integers.
        """
        if self._sample_width == 3:
            # 24-bit: unpack manually to 32-bit array.
            result = array.array("i")
            for i in range(0, len(self._data), 3):
                b0 = self._data[i]
                b1 = self._data[i + 1]
                b2 = self._data[i + 2]
                val = b0 | (b1 << 8) | (b2 << 16)
                if val >= 0x800000:
                    val -= 0x1000000
                result.append(val)
            return result

        arr = array.array(self.array_type)
        arr.frombytes(self._data)
        return arr

    def get_sample_slice(
        self, start_sample: int = 0, end_sample: Optional[int] = None
    ) -> "AudioSegment":
        """Return a slice of the audio by sample index."""
        sw = self._sample_width
        total = len(self._data) // sw
        if end_sample is None:
            end_sample = total
        start_sample = builtins_max(0, start_sample)
        end_sample = builtins_min(end_sample, total)
        return self._spawn(self._data[start_sample * sw : end_sample * sw])

    def get_frame(self, index: int) -> bytes:
        """Return the raw bytes for frame at *index*."""
        fw = self.frame_width
        start = index * fw
        return self._data[start : start + fw]

    # ------------------------------------------------------------------
    # Transform methods
    # ------------------------------------------------------------------

    def apply_gain(self, volume_change: float) -> "AudioSegment":
        """Apply gain in dBFS. Positive = louder, negative = quieter."""
        factor = 10.0 ** (volume_change / 20.0)
        new_data = _pcm.mul(self._data, self._sample_width, factor)
        return self._spawn(new_data)

    def set_sample_width(self, sample_width: int) -> "AudioSegment":
        """Convert to a different sample width."""
        if sample_width == self._sample_width:
            return self
        new_data = _pcm.lin2lin(self._data, self._sample_width, sample_width)
        return self._spawn(new_data, {"sample_width": sample_width})

    def set_frame_rate(self, frame_rate: int) -> "AudioSegment":
        """Resample to a new frame rate."""
        if frame_rate == self._frame_rate:
            return self
        new_data, _ = _pcm.ratecv(
            self._data,
            self._sample_width,
            self._channels,
            self._frame_rate,
            frame_rate,
            None,
        )
        return self._spawn(new_data, {"frame_rate": frame_rate})

    def set_channels(self, channels: int) -> "AudioSegment":
        """Convert between mono and stereo."""
        if channels == self._channels:
            return self

        if self._channels == 1 and channels == 2:
            new_data = _pcm.tostereo(
                self._data, self._sample_width, 1.0, 1.0
            )
        elif self._channels == 2 and channels == 1:
            new_data = _pcm.tomono(
                self._data, self._sample_width, 0.5, 0.5
            )
        else:
            raise ValueError(
                f"Cannot convert from {self._channels} to {channels} channels"
            )

        return self._spawn(new_data, {"channels": channels})

    def split_to_mono(self) -> List["AudioSegment"]:
        """Split a multi-channel segment into a list of mono segments."""
        if self._channels == 1:
            return [self]

        sw = self._sample_width
        ch = self._channels
        fw = sw * ch
        n_frames = len(self._data) // fw

        channel_data: list[bytearray] = [bytearray() for _ in range(ch)]
        for i in range(n_frames):
            offset = i * fw
            for c in range(ch):
                sample_offset = offset + c * sw
                channel_data[c].extend(
                    self._data[sample_offset : sample_offset + sw]
                )

        return [
            self._spawn(bytes(cd), {"channels": 1}) for cd in channel_data
        ]

    def get_dc_offset(self, channel: int = 1) -> float:
        """Measure DC offset for the given channel (1-based)."""
        if self._channels == 1:
            seg = self
        else:
            mono_segs = self.split_to_mono()
            seg = mono_segs[channel - 1]

        samples = seg.get_array_of_samples()
        if len(samples) == 0:
            return 0.0
        return float(sum(samples)) / len(samples)

    def remove_dc_offset(
        self,
        channel: Optional[int] = None,
        offset: Optional[float] = None,
    ) -> "AudioSegment":
        """Remove DC offset. If *offset* is None, auto-detect."""
        if self._channels == 1:
            if offset is None:
                offset = self.get_dc_offset()
            return self._spawn(
                _pcm.bias(self._data, self._sample_width, -int(offset))
            )
        else:
            mono_segs = self.split_to_mono()
            corrected = []
            for i, seg in enumerate(mono_segs):
                ch_num = i + 1
                if channel is not None and ch_num != channel:
                    corrected.append(seg)
                else:
                    ch_offset = offset if offset is not None else seg.get_dc_offset()
                    corrected.append(
                        seg._spawn(
                            _pcm.bias(
                                seg._data, seg._sample_width, -int(ch_offset)
                            )
                        )
                    )
            return AudioSegment.from_mono_audiosegments(*corrected)

    # ------------------------------------------------------------------
    # Operators
    # ------------------------------------------------------------------

    def __add__(self, other: Any) -> "AudioSegment":
        """Concatenation (``seg1 + seg2``) or volume up (``seg + 6``)."""
        if isinstance(other, AudioSegment):
            # Concatenate.
            a, b = self._sync(self, other)
            return a._spawn(a._data + b._data)
        if isinstance(other, (int, float)):
            # Volume adjustment in dB.
            return self.apply_gain(float(other))
        return NotImplemented

    def __radd__(self, other: Any) -> "AudioSegment":
        """Support ``sum([seg1, seg2], AudioSegment.empty())``."""
        if isinstance(other, AudioSegment):
            return other.__add__(self)
        if other == 0:
            # sum() starts with 0.
            return self
        return NotImplemented

    def __sub__(self, other: Any) -> "AudioSegment":
        """Volume down (``seg - 3`` = -3 dB)."""
        if isinstance(other, (int, float)):
            return self.apply_gain(-float(other))
        return NotImplemented

    def __mul__(self, times: int) -> "AudioSegment":
        """Repeat segment (``seg * 3``)."""
        if isinstance(times, int):
            if times <= 0:
                return self._spawn(b"")
            return self._spawn(self._data * times)
        return NotImplemented

    def __getitem__(self, key: Any) -> "AudioSegment":
        """Slice by milliseconds (``seg[1000:5000]``)."""
        if isinstance(key, slice):
            fw = self.frame_width
            fr = self._frame_rate
            total_ms = len(self._data) / fw / fr * 1000.0

            start_ms = key.start if key.start is not None else 0
            stop_ms = key.stop if key.stop is not None else total_ms

            # Handle negative indices.
            if start_ms < 0:
                start_ms = total_ms + start_ms
            if stop_ms < 0:
                stop_ms = total_ms + stop_ms

            start_ms = builtins_max(0.0, start_ms)
            stop_ms = builtins_min(total_ms, stop_ms)

            start_byte = int(start_ms / 1000.0 * fr) * fw
            stop_byte = int(stop_ms / 1000.0 * fr) * fw

            return self._spawn(self._data[start_byte:stop_byte])
        raise TypeError(f"AudioSegment indices must be slices, not {type(key).__name__}")

    def __len__(self) -> int:
        """Duration in milliseconds."""
        fw = self.frame_width
        if fw == 0 or self._frame_rate == 0:
            return 0
        return int(len(self._data) / fw / self._frame_rate * 1000.0)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AudioSegment):
            return NotImplemented
        return (
            self._data == other._data
            and self._sample_width == other._sample_width
            and self._frame_rate == other._frame_rate
            and self._channels == other._channels
        )

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __iter__(self):  # type: ignore[no-untyped-def]
        """Iterate over 1-ms chunks."""
        fw = self.frame_width
        fr = self._frame_rate
        chunk_bytes = int(fr / 1000.0) * fw
        if chunk_bytes <= 0:
            chunk_bytes = fw
        for i in range(0, len(self._data), chunk_bytes):
            yield self._spawn(self._data[i : i + chunk_bytes])

    def __hash__(self) -> int:
        return hash((self._data, self._sample_width, self._frame_rate, self._channels))

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def empty(cls) -> "AudioSegment":
        """Create an empty (zero-length) AudioSegment."""
        return cls(
            data=b"",
            sample_width=2,
            frame_rate=44100,
            channels=1,
        )

    @classmethod
    def silent(
        cls, duration: int = 1000, frame_rate: int = 11025
    ) -> "AudioSegment":
        """Create a silent AudioSegment of *duration* milliseconds."""
        sample_width = 2
        channels = 1
        n_frames = int(frame_rate * duration / 1000.0)
        data = b"\x00" * (n_frames * sample_width * channels)
        return cls(
            data=data,
            sample_width=sample_width,
            frame_rate=frame_rate,
            channels=channels,
        )

    @classmethod
    def from_mono_audiosegments(
        cls, *mono_segments: "AudioSegment"
    ) -> "AudioSegment":
        """Merge mono AudioSegments into a multi-channel segment."""
        if not mono_segments:
            return cls.empty()

        # Sync all segments to the same format.
        segs = cls._sync(*mono_segments)
        for s in segs:
            if s._channels != 1:
                raise ValueError("All segments must be mono")

        n_channels = len(segs)
        sw = segs[0]._sample_width
        fr = segs[0]._frame_rate

        # Find shortest length.
        min_len = min(len(s._data) for s in segs)
        n_frames = min_len // sw

        out = bytearray()
        for i in range(n_frames):
            for s in segs:
                offset = i * sw
                out.extend(s._data[offset : offset + sw])

        return cls(
            data=bytes(out),
            sample_width=sw,
            frame_rate=fr,
            channels=n_channels,
        )


# Use builtins to avoid shadowing by pcm.max
import builtins as _builtins

builtins_max = _builtins.max
builtins_min = _builtins.min
