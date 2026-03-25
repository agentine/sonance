"""Comprehensive tests for Phase 1: pcm.py and AudioSegment core/operators."""

import array
import math
import struct
import sys

import pytest

from sonance import AudioSegment
from sonance.exceptions import MissingAudioParameter
from sonance.pcm import (
    add,
    bias,
    lin2lin,
    max as pcm_max,
    maxpp,
    mul,
    ratecv,
    reverse,
    rms,
    tomono,
    tostereo,
)

# =====================================================================
# pcm.py tests
# =====================================================================


class TestPcmMul:
    def test_mul_16bit(self) -> None:
        data = struct.pack("<hh", 1000, -2000)
        result = mul(data, 2, 2.0)
        assert struct.unpack("<hh", result) == (2000, -4000)

    def test_mul_clamp(self) -> None:
        data = struct.pack("<h", 30000)
        result = mul(data, 2, 2.0)
        assert struct.unpack("<h", result) == (32767,)

    def test_mul_8bit(self) -> None:
        # 8-bit: unsigned, 128=zero
        data = bytes([128 + 50])  # sample = +50
        result = mul(data, 1, 2.0)
        val = result[0] - 128
        assert val == 100

    def test_mul_32bit(self) -> None:
        data = struct.pack("<i", 100000)
        result = mul(data, 4, 3.0)
        assert struct.unpack("<i", result) == (300000,)

    def test_mul_24bit(self) -> None:
        # 24-bit: 1000 = 0xE8 0x03 0x00
        data = bytes([0xE8, 0x03, 0x00])
        result = mul(data, 3, 2.0)
        val = result[0] | (result[1] << 8) | (result[2] << 16)
        assert val == 2000

    def test_mul_zero_factor(self) -> None:
        data = struct.pack("<hh", 1000, -2000)
        result = mul(data, 2, 0.0)
        assert struct.unpack("<hh", result) == (0, 0)


class TestPcmAdd:
    def test_add_16bit(self) -> None:
        a = struct.pack("<hh", 100, 200)
        b = struct.pack("<hh", 300, 400)
        result = add(a, b, 2)
        assert struct.unpack("<hh", result) == (400, 600)

    def test_add_clamp(self) -> None:
        a = struct.pack("<h", 32000)
        b = struct.pack("<h", 32000)
        result = add(a, b, 2)
        assert struct.unpack("<h", result) == (32767,)

    def test_add_different_lengths(self) -> None:
        a = struct.pack("<h", 100)
        b = struct.pack("<hh", 100, 200)
        with pytest.raises(ValueError, match="same length"):
            add(a, b, 2)


class TestPcmBias:
    def test_bias_16bit(self) -> None:
        data = struct.pack("<h", 100)
        result = bias(data, 2, 50)
        assert struct.unpack("<h", result) == (150,)

    def test_bias_clamp(self) -> None:
        data = struct.pack("<h", 32000)
        result = bias(data, 2, 1000)
        assert struct.unpack("<h", result) == (32767,)


class TestPcmLin2Lin:
    def test_16_to_8(self) -> None:
        # 16-bit 0 → 8-bit: high byte of LE 0x0000 = 0x00
        data = struct.pack("<h", 0)
        result = lin2lin(data, 2, 1)
        assert result == bytes([0])
        # 16-bit 1000 (0x03E8) → high byte = 0x03
        data = struct.pack("<h", 1000)
        assert lin2lin(data, 2, 1) == bytes([0x03])

    def test_8_to_16(self) -> None:
        # 8-bit byte 0x8A (138) → LE 16-bit [0x00, 0x8A] = 0x8A00
        data = bytes([0x8A])
        result = lin2lin(data, 1, 2)
        assert result == b"\x00\x8a"

    def test_same_width(self) -> None:
        data = struct.pack("<hh", 100, 200)
        assert lin2lin(data, 2, 2) == data


class TestPcmToMono:
    def test_tomono_equal_mix(self) -> None:
        # Stereo: L=1000, R=3000
        data = struct.pack("<hh", 1000, 3000)
        result = tomono(data, 2, 0.5, 0.5)
        assert struct.unpack("<h", result) == (2000,)

    def test_tomono_left_only(self) -> None:
        data = struct.pack("<hh", 1000, 3000)
        result = tomono(data, 2, 1.0, 0.0)
        assert struct.unpack("<h", result) == (1000,)


class TestPcmToStereo:
    def test_tostereo(self) -> None:
        data = struct.pack("<h", 1000)
        result = tostereo(data, 2, 1.0, 0.5)
        L, R = struct.unpack("<hh", result)
        assert L == 1000 and R == 500

    def test_tostereo_silent_right(self) -> None:
        data = struct.pack("<h", 1000)
        result = tostereo(data, 2, 1.0, 0.0)
        L, R = struct.unpack("<hh", result)
        assert L == 1000 and R == 0


class TestPcmRms:
    def test_rms_constant(self) -> None:
        data = struct.pack("<hh", 100, -100)
        assert rms(data, 2) == 100

    def test_rms_empty(self) -> None:
        assert rms(b"", 2) == 0

    def test_rms_single_sample(self) -> None:
        data = struct.pack("<h", 500)
        assert rms(data, 2) == 500


class TestPcmMax:
    def test_max_positive_and_negative(self) -> None:
        data = struct.pack("<hh", 500, -1000)
        assert pcm_max(data, 2) == 1000

    def test_max_empty(self) -> None:
        assert pcm_max(b"", 2) == 0


class TestPcmMaxpp:
    def test_maxpp_triangle(self) -> None:
        # Triangle: 0 → 1000 → 0 → -1000
        data = struct.pack("<hhhh", 0, 1000, 0, -1000)
        pp = maxpp(data, 2)
        assert pp >= 1000

    def test_maxpp_constant(self) -> None:
        data = struct.pack("<hhh", 500, 500, 500)
        assert maxpp(data, 2) == 0

    def test_maxpp_short(self) -> None:
        data = struct.pack("<h", 500)
        assert maxpp(data, 2) == 0


class TestPcmRatecv:
    def test_ratecv_downsample(self) -> None:
        # 4 frames → ~2 frames (2:1 downsample)
        data = struct.pack("<hhhh", 0, 100, 200, 300)
        result, state = ratecv(data, 2, 1, 2, 1, None)
        n_frames = len(result) // 2
        assert n_frames == 2

    def test_ratecv_upsample(self) -> None:
        # 2 frames → ~4 frames (1:2 upsample)
        data = struct.pack("<hh", 0, 1000)
        result, state = ratecv(data, 2, 1, 1, 2, None)
        n_frames = len(result) // 2
        assert n_frames >= 2

    def test_ratecv_invalid_rate(self) -> None:
        with pytest.raises(ValueError):
            ratecv(b"\x00\x00", 2, 1, 0, 44100, None)


class TestPcmReverse:
    def test_reverse_16bit(self) -> None:
        data = struct.pack("<hhh", 1, 2, 3)
        result = reverse(data, 2)
        assert struct.unpack("<hhh", result) == (3, 2, 1)

    def test_reverse_8bit(self) -> None:
        data = bytes([1, 2, 3])
        result = reverse(data, 1)
        assert result == bytes([3, 2, 1])


class TestPcmValidation:
    def test_invalid_width(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            mul(b"\x00", 5, 1.0)

    def test_bad_fragment_length(self) -> None:
        with pytest.raises(ValueError, match="multiple"):
            mul(b"\x00\x01\x02", 2, 1.0)


# =====================================================================
# AudioSegment construction tests
# =====================================================================


class TestAudioSegmentConstruction:
    def test_basic_construction(self) -> None:
        data = b"\x00\x00" * 100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert seg.raw_data == data
        assert seg.sample_width == 2
        assert seg.frame_rate == 44100
        assert seg.channels == 1

    def test_metadata_construction(self) -> None:
        data = b"\x00\x00" * 100
        seg = AudioSegment(
            data=data,
            metadata={"sample_width": 2, "frame_rate": 44100, "channels": 1},
        )
        assert seg.sample_width == 2

    def test_missing_parameter(self) -> None:
        with pytest.raises(MissingAudioParameter):
            AudioSegment(data=b"\x00\x00")


class TestAudioSegmentProperties:
    def test_frame_width(self) -> None:
        seg = AudioSegment(data=b"\x00" * 40, sample_width=2, frame_rate=44100, channels=2)
        assert seg.frame_width == 4

    def test_duration_seconds(self) -> None:
        # 44100 16-bit mono samples = 1 second
        data = b"\x00\x00" * 44100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert abs(seg.duration_seconds - 1.0) < 0.001

    def test_rms_silent(self) -> None:
        seg = AudioSegment.silent(duration=100)
        assert seg.rms == 0

    def test_dbfs_silent(self) -> None:
        seg = AudioSegment.silent(duration=100)
        assert seg.dBFS == -float("inf")

    def test_rms_nonzero(self) -> None:
        data = struct.pack("<h", 1000) * 100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert seg.rms == 1000

    def test_max(self) -> None:
        data = struct.pack("<hh", 500, -1000)
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert seg.max == 1000

    def test_max_possible_amplitude(self) -> None:
        seg = AudioSegment(data=b"\x00\x00", sample_width=2, frame_rate=44100, channels=1)
        assert seg.max_possible_amplitude == 32768.0

    def test_max_dbfs(self) -> None:
        # Full-scale signal
        data = struct.pack("<h", 32767) * 100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert seg.max_dBFS > -0.01  # approximately 0 dBFS

    def test_array_type(self) -> None:
        seg1 = AudioSegment(data=b"\x00", sample_width=1, frame_rate=44100, channels=1)
        assert seg1.array_type == "b"
        seg2 = AudioSegment(data=b"\x00\x00", sample_width=2, frame_rate=44100, channels=1)
        assert seg2.array_type == "h"

    def test_frame_count(self) -> None:
        data = b"\x00\x00" * 100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert seg.frame_count() == 100.0

    def test_frame_count_ms(self) -> None:
        seg = AudioSegment(data=b"\x00\x00" * 44100, sample_width=2, frame_rate=44100, channels=1)
        assert seg.frame_count(ms=500) == 22050.0


class TestAudioSegmentSampleAccess:
    def test_get_array_of_samples(self) -> None:
        data = struct.pack("<hhh", 100, 200, 300)
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        arr = seg.get_array_of_samples()
        assert list(arr) == [100, 200, 300]

    def test_get_array_24bit(self) -> None:
        # 24-bit sample: 1000
        data = bytes([0xE8, 0x03, 0x00])
        seg = AudioSegment(data=data, sample_width=3, frame_rate=44100, channels=1)
        arr = seg.get_array_of_samples()
        assert arr[0] == 1000

    def test_get_sample_slice(self) -> None:
        data = struct.pack("<hhhh", 10, 20, 30, 40)
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        sliced = seg.get_sample_slice(1, 3)
        arr = sliced.get_array_of_samples()
        assert list(arr) == [20, 30]

    def test_get_frame(self) -> None:
        data = struct.pack("<hh", 100, 200)
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=2)
        frame = seg.get_frame(0)
        assert len(frame) == 4  # 2 channels * 2 bytes


# =====================================================================
# AudioSegment operator tests
# =====================================================================


class TestAudioSegmentOperators:
    def _make_seg(self, n_samples: int = 100, value: int = 1000) -> AudioSegment:
        data = struct.pack("<h", value) * n_samples
        return AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)

    def test_add_concat(self) -> None:
        a = self._make_seg(50)
        b = self._make_seg(50)
        c = a + b
        assert len(c.raw_data) == len(a.raw_data) + len(b.raw_data)

    def test_add_volume(self) -> None:
        seg = self._make_seg()
        louder = seg + 6
        assert louder.rms > seg.rms

    def test_sub_volume(self) -> None:
        seg = self._make_seg()
        quieter = seg - 6
        assert quieter.rms < seg.rms

    def test_mul_repeat(self) -> None:
        seg = self._make_seg(50)
        triple = seg * 3
        assert len(triple.raw_data) == len(seg.raw_data) * 3

    def test_mul_zero(self) -> None:
        seg = self._make_seg(50)
        empty = seg * 0
        assert len(empty.raw_data) == 0

    def test_getitem_slice(self) -> None:
        # 1 second of audio
        data = b"\x00\x00" * 44100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        first_half = seg[:500]
        assert len(first_half) <= 500

    def test_getitem_negative(self) -> None:
        data = b"\x00\x00" * 44100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        last_100ms = seg[-100:]
        assert len(last_100ms) > 0

    def test_len_ms(self) -> None:
        data = b"\x00\x00" * 44100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert len(seg) == 1000

    def test_eq(self) -> None:
        seg1 = self._make_seg()
        seg2 = self._make_seg()
        assert seg1 == seg2

    def test_ne(self) -> None:
        seg1 = self._make_seg(value=1000)
        seg2 = self._make_seg(value=2000)
        assert seg1 != seg2

    def test_hash(self) -> None:
        seg = self._make_seg()
        assert isinstance(hash(seg), int)

    def test_iter(self) -> None:
        seg = self._make_seg()
        chunks = list(seg)
        assert len(chunks) > 0

    def test_radd_sum(self) -> None:
        segs = [self._make_seg(50) for _ in range(3)]
        total = sum(segs, AudioSegment.empty())
        assert len(total.raw_data) == 50 * 2 * 3


# =====================================================================
# AudioSegment constructor tests
# =====================================================================


class TestAudioSegmentConstructors:
    def test_empty(self) -> None:
        seg = AudioSegment.empty()
        assert len(seg.raw_data) == 0
        assert seg.sample_width == 2
        assert seg.channels == 1

    def test_silent(self) -> None:
        seg = AudioSegment.silent(duration=1000, frame_rate=44100)
        assert abs(seg.duration_seconds - 1.0) < 0.001
        assert seg.rms == 0

    def test_silent_default_rate(self) -> None:
        seg = AudioSegment.silent(duration=1000)
        assert seg.frame_rate == 11025

    def test_from_mono_audiosegments(self) -> None:
        left = AudioSegment(
            data=struct.pack("<hh", 100, 200),
            sample_width=2,
            frame_rate=44100,
            channels=1,
        )
        right = AudioSegment(
            data=struct.pack("<hh", 300, 400),
            sample_width=2,
            frame_rate=44100,
            channels=1,
        )
        stereo = AudioSegment.from_mono_audiosegments(left, right)
        assert stereo.channels == 2
        # Interleaved: L0, R0, L1, R1
        samples = struct.unpack("<hhhh", stereo.raw_data)
        assert samples == (100, 300, 200, 400)


# =====================================================================
# AudioSegment transform tests
# =====================================================================


class TestAudioSegmentTransforms:
    def _make_seg(self, n_samples: int = 100, value: int = 1000) -> AudioSegment:
        data = struct.pack("<h", value) * n_samples
        return AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)

    def test_apply_gain(self) -> None:
        seg = self._make_seg()
        louder = seg.apply_gain(6.0)
        assert louder.rms > seg.rms
        quieter = seg.apply_gain(-6.0)
        assert quieter.rms < seg.rms

    def test_set_sample_width(self) -> None:
        seg = self._make_seg()
        seg8 = seg.set_sample_width(1)
        assert seg8.sample_width == 1
        # Round-trip should approximately preserve
        seg16 = seg8.set_sample_width(2)
        assert seg16.sample_width == 2

    def test_set_sample_width_noop(self) -> None:
        seg = self._make_seg()
        same = seg.set_sample_width(2)
        assert same is seg

    def test_set_frame_rate(self) -> None:
        # 1 second at 44100
        data = b"\x00\x00" * 44100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        resampled = seg.set_frame_rate(22050)
        assert resampled.frame_rate == 22050
        # Should be approximately half the frames
        ratio = resampled.frame_count() / seg.frame_count()
        assert 0.4 < ratio < 0.6

    def test_set_frame_rate_noop(self) -> None:
        seg = self._make_seg()
        same = seg.set_frame_rate(44100)
        assert same is seg

    def test_set_channels_mono_to_stereo(self) -> None:
        seg = self._make_seg()
        stereo = seg.set_channels(2)
        assert stereo.channels == 2
        assert len(stereo.raw_data) == len(seg.raw_data) * 2

    def test_set_channels_stereo_to_mono(self) -> None:
        seg = self._make_seg()
        stereo = seg.set_channels(2)
        mono = stereo.set_channels(1)
        assert mono.channels == 1

    def test_set_channels_noop(self) -> None:
        seg = self._make_seg()
        same = seg.set_channels(1)
        assert same is seg

    def test_split_to_mono(self) -> None:
        left = AudioSegment(
            data=struct.pack("<hh", 100, 200),
            sample_width=2,
            frame_rate=44100,
            channels=1,
        )
        right = AudioSegment(
            data=struct.pack("<hh", 300, 400),
            sample_width=2,
            frame_rate=44100,
            channels=1,
        )
        stereo = AudioSegment.from_mono_audiosegments(left, right)
        monos = stereo.split_to_mono()
        assert len(monos) == 2
        assert list(monos[0].get_array_of_samples()) == [100, 200]
        assert list(monos[1].get_array_of_samples()) == [300, 400]

    def test_split_mono_noop(self) -> None:
        seg = self._make_seg()
        monos = seg.split_to_mono()
        assert len(monos) == 1
        assert monos[0] is seg

    def test_dc_offset(self) -> None:
        data = struct.pack("<h", 1000) * 100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert seg.get_dc_offset() == 1000.0

    def test_remove_dc_offset(self) -> None:
        data = struct.pack("<h", 1000) * 100
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        corrected = seg.remove_dc_offset()
        assert abs(corrected.get_dc_offset()) < 1


# =====================================================================
# Edge case tests
# =====================================================================


class TestEdgeCases:
    def test_empty_segment_properties(self) -> None:
        seg = AudioSegment.empty()
        assert seg.rms == 0
        assert seg.max == 0
        assert seg.dBFS == -float("inf")
        assert seg.duration_seconds == 0.0
        assert seg.frame_count() == 0.0
        assert len(seg) == 0

    def test_single_frame(self) -> None:
        data = struct.pack("<h", 500)
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=1)
        assert seg.rms == 500
        assert seg.max == 500

    def test_8bit_roundtrip(self) -> None:
        # 8-bit unsigned: 128=silence, 0=min, 255=max
        data = bytes([128] * 100)
        seg = AudioSegment(data=data, sample_width=1, frame_rate=44100, channels=1)
        assert seg.rms == 0

    def test_32bit_segment(self) -> None:
        data = struct.pack("<i", 100000) * 10
        seg = AudioSegment(data=data, sample_width=4, frame_rate=44100, channels=1)
        assert seg.rms == 100000

    def test_stereo_rms(self) -> None:
        # Stereo with known values
        data = struct.pack("<hh", 1000, -1000) * 50
        seg = AudioSegment(data=data, sample_width=2, frame_rate=44100, channels=2)
        assert seg.rms == 1000

    def test_concat_different_rates(self) -> None:
        a = AudioSegment(data=b"\x00\x00" * 100, sample_width=2, frame_rate=44100, channels=1)
        b = AudioSegment(data=b"\x00\x00" * 100, sample_width=2, frame_rate=22050, channels=1)
        # Should sync to higher rate
        c = a + b
        assert c.frame_rate == 44100

    def test_concat_different_channels(self) -> None:
        mono = AudioSegment(data=b"\x00\x00" * 100, sample_width=2, frame_rate=44100, channels=1)
        stereo = AudioSegment(
            data=b"\x00\x00" * 200, sample_width=2, frame_rate=44100, channels=2
        )
        # Should sync to stereo
        c = mono + stereo
        assert c.channels == 2


# =====================================================================
# audioop parity tests (Python < 3.13 only)
# =====================================================================

_has_audioop = False
try:
    import audioop  # type: ignore[import-not-found]

    _has_audioop = True
except ImportError:
    pass


@pytest.mark.skipif(not _has_audioop, reason="audioop not available (Python 3.13+)")
class TestAudioopParity:
    """Verify pcm.py output matches audioop exactly."""

    def test_mul_parity(self) -> None:
        data = struct.pack("<hhhh", 1000, -2000, 32000, -32000)
        for factor in [0.5, 1.0, 2.0, 0.0]:
            expected = audioop.mul(data, 2, factor)
            got = mul(data, 2, factor)
            assert got == expected, f"mul factor={factor}"

    def test_add_parity(self) -> None:
        a = struct.pack("<hh", 100, -100)
        b = struct.pack("<hh", 200, -200)
        expected = audioop.add(a, b, 2)
        got = add(a, b, 2)
        assert got == expected

    def test_bias_parity(self) -> None:
        data = struct.pack("<hh", 100, -100)
        for b in [0, 50, -50, 100]:
            expected = audioop.bias(data, 2, b)
            got = bias(data, 2, b)
            assert got == expected, f"bias={b}"

    def test_rms_parity(self) -> None:
        data = struct.pack("<hhhh", 100, -200, 300, -400)
        expected = audioop.rms(data, 2)
        got = rms(data, 2)
        assert got == expected

    def test_max_parity(self) -> None:
        data = struct.pack("<hhhh", 100, -200, 300, -400)
        expected = audioop.max(data, 2)
        got = pcm_max(data, 2)
        assert got == expected

    def test_reverse_parity(self) -> None:
        data = struct.pack("<hhhh", 1, 2, 3, 4)
        expected = audioop.reverse(data, 2)
        got = reverse(data, 2)
        assert got == expected

    def test_tomono_parity(self) -> None:
        data = struct.pack("<hhhh", 100, 200, 300, 400)
        for lf, rf in [(1.0, 0.0), (0.0, 1.0), (0.5, 0.5)]:
            expected = audioop.tomono(data, 2, lf, rf)
            got = tomono(data, 2, lf, rf)
            assert got == expected, f"tomono lf={lf} rf={rf}"

    def test_tostereo_parity(self) -> None:
        data = struct.pack("<hh", 100, 200)
        for lf, rf in [(1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (0.5, 0.5)]:
            expected = audioop.tostereo(data, 2, lf, rf)
            got = tostereo(data, 2, lf, rf)
            assert got == expected, f"tostereo lf={lf} rf={rf}"

    def test_lin2lin_parity(self) -> None:
        data = struct.pack("<hh", 1000, -1000)
        for nw in [1, 4]:
            expected = audioop.lin2lin(data, 2, nw)
            got = lin2lin(data, 2, nw)
            assert got == expected, f"lin2lin 2→{nw}"
