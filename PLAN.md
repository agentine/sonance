# sonance — Implementation Plan

## Overview

**sonance** is a modern, zero-dependency replacement for
[pydub](https://github.com/jiaaro/pydub) (18.4M monthly PyPI downloads,
9.7K stars, unmaintained since March 2021, **broken on Python 3.13+**).

sonance provides a 100% pydub-compatible API so existing code can migrate
with a single import path change.

**PyPI package:** `sonance`
**License:** MIT

---

## Why pydub Needs Replacing

| Signal | Detail |
|---|---|
| Downloads | 18.4M/month (PyPI) |
| Stars | 9,700 |
| Dependents | 108,000+ |
| Maintainer | James Robert (jiaaro) — SOLE MAINTAINER |
| Last release | v0.25.1 — March 10, 2021 (5 years ago) |
| Open issues | 339 |
| Open PRs | 75 |
| Snyk status | **Inactive** |
| Python 3.13 | **BROKEN** — `audioop` module removed from stdlib |
| Python 3.12 | DeprecationWarning for `audioop` usage |
| Funding | None |

### The audioop Crisis

Python 3.13 (October 2024) removed the `audioop` C extension module from
the standard library. pydub uses `audioop` extensively for:

- Volume adjustment (`audioop.mul`)
- Audio mixing (`audioop.add`)
- Sample width conversion (`audioop.lin2lin`)
- Channel conversion (`audioop.tomono`, `audioop.tostereo`)
- RMS/peak analysis (`audioop.rms`, `audioop.max`, `audioop.maxpp`)
- Sample rate conversion (`audioop.ratecv`)
- Phase inversion, DC offset removal

**pydub is completely broken on Python 3.13+** with
`ModuleNotFoundError: No module named 'audioop'`. A PR (#816) to add
`audioop-lts` as a dependency has sat unmerged since January 2025. The
maintainer has not responded.

### No API-Compatible Replacement Exists

- **librosa** — scientific audio analysis, completely different paradigm
- **pedalboard** — Spotify's audio plugin framework, different API
- **soundfile** — file I/O only, no manipulation/effects
- **ffmpeg-python** — wraps ffmpeg CLI directly, different API
- **miniaudio** — low-level bindings, different API

None of these provide pydub's signature simple API: slice with `[]`,
concatenate with `+`, adjust volume with `+`/`-` (dB), fade, filter, export.

---

## Design Principles

1. **Drop-in compatible** — same `AudioSegment` class, same operators,
   same effects, same I/O methods
2. **No audioop dependency** — pure Python PCM operations using `struct`
   and `array` (works on Python 3.9–3.14+)
3. **Zero dependencies** — only stdlib + ffmpeg as external tool
4. **Type-safe** — full type hints, `py.typed`, strict mypy
5. **Python 3.9+** — drop Python 2 cruft, use modern idioms
6. **Performance** — optional numpy acceleration when available
7. **src/ layout** — modern Python packaging (`pyproject.toml` only)

---

## Public API Surface (pydub-compatible)

### AudioSegment Class

```python
from sonance import AudioSegment

# Construction
seg = AudioSegment(data=b'...', metadata={...})
seg = AudioSegment.empty()
seg = AudioSegment.silent(duration=1000, frame_rate=11025)
seg = AudioSegment.from_file("audio.mp3", format="mp3")
seg = AudioSegment.from_mp3("song.mp3")
seg = AudioSegment.from_wav("sound.wav")
seg = AudioSegment.from_ogg("audio.ogg")
seg = AudioSegment.from_flv("video.flv")
seg = AudioSegment.from_raw(data, sample_width=2, frame_rate=44100, channels=2)
seg = AudioSegment.from_mono_audiosegments(left, right)

# Operators
combined = seg1 + seg2          # concatenation
louder = seg + 6                # +6 dB
quieter = seg - 3               # -3 dB
repeated = seg * 3              # repeat 3x
first_10s = seg[:10000]         # slice (ms)
duration = len(seg)             # duration in ms

# Properties
seg.raw_data                    # bytes
seg.frame_rate                  # Hz
seg.channels                    # 1=mono, 2=stereo
seg.sample_width                # bytes per sample
seg.frame_width                 # bytes per frame
seg.frame_count()               # total frames
seg.duration_seconds            # float seconds
seg.rms                         # RMS amplitude
seg.dBFS                        # dBFS level
seg.max                         # peak amplitude
seg.max_possible_amplitude      # max value for bit depth
seg.max_dBFS                    # max dBFS
seg.array_type                  # array.array type code

# Methods
seg.get_array_of_samples()
seg.get_sample_slice(start, end)
seg.get_frame(index)
seg.set_sample_width(sample_width)
seg.set_frame_rate(frame_rate)
seg.set_channels(channels)
seg.split_to_mono()
seg.get_dc_offset(channel=1)
seg.remove_dc_offset(channel=None, offset=None)
seg.apply_gain(volume_change)
seg.overlay(other, position=0, loop=False, times=None, gain_during_overlay=None)
seg.append(other, crossfade=100)
seg.fade(to_gain=0, from_gain=0, start=None, end=None, duration=None)
seg.fade_in(duration)
seg.fade_out(duration)
seg.reverse()
seg.export(out_f, format="mp3", codec=None, bitrate=None, parameters=None,
           tags=None, id3v2_version="4", cover=None)
```

### Effects (registered on AudioSegment via decorator)

```python
seg.normalize(headroom=0.1)
seg.speedup(playback_speed=1.5, chunk_size=150, crossfade=25)
seg.strip_silence(silence_len=1000, silence_thresh=-16, padding=100)
seg.compress_dynamic_range(threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
seg.invert_phase(channels=(1, 1))
seg.low_pass_filter(cutoff)
seg.high_pass_filter(cutoff)
seg.pan(pan_amount)
seg.apply_gain_stereo(left_gain=0.0, right_gain=0.0)
seg.apply_mono_filter_to_each_channel(filter_fn)
```

### Silence Detection

```python
from sonance.silence import (
    detect_silence,
    detect_nonsilent,
    split_on_silence,
    detect_leading_silence,
)
```

### Signal Generators

```python
from sonance.generators import Sine, Pulse, Square, Sawtooth, Triangle, WhiteNoise

tone = Sine(440).to_audio_segment(duration=1000, volume=-3.0)
```

### Utilities

```python
from sonance.utils import (
    db_to_float, ratio_to_db, make_chunks,
    mediainfo, mediainfo_json,
    register_pydub_effect,
)
```

### Playback

```python
from sonance.playback import play
play(seg)
```

### Exceptions

```python
from sonance.exceptions import (
    SonanceException,    # base (alias: PydubException for compat)
    TooManyMissingFrames,
    InvalidDuration,
    InvalidTag,
    InvalidID3TagVersion,
    CouldntDecodeError,
    CouldntEncodeError,
    MissingAudioParameter,
)
```

### Compatibility Import

```python
# For zero-change migration:
import sonance as pydub
from sonance import AudioSegment  # same class
```

---

## Key Technical Decisions

### Replacing audioop

All `audioop` operations will be reimplemented in pure Python:

| audioop function | Implementation |
|---|---|
| `mul(frag, width, factor)` | `struct` unpack → multiply → clamp → repack |
| `add(frag1, frag2, width)` | Unpack both → add → clamp → repack |
| `bias(frag, width, bias)` | Unpack → add bias → clamp → repack |
| `lin2lin(frag, width, newwidth)` | Unpack at old width → scale → repack at new width |
| `tomono(frag, width, lfactor, rfactor)` | Deinterleave → weighted sum → repack |
| `tostereo(frag, width, lfactor, rfactor)` | Apply factors → interleave → repack |
| `rms(frag, width)` | Unpack → sum of squares → sqrt(mean) |
| `max(frag, width)` | Unpack → max(abs(sample)) |
| `maxpp(frag, width)` | Unpack → find max peak-to-peak |
| `ratecv(...)` | Linear interpolation resampler |
| `reverse(frag, width)` | Reverse frame order |

Optional acceleration: when `numpy` is available, use vectorized
operations for 10-100x speedup on large audio segments.

### File Structure

```
src/
  sonance/
    __init__.py           # from .audio_segment import AudioSegment
    audio_segment.py      # AudioSegment class
    pcm.py                # Pure Python audioop replacements
    effects.py            # Registered effects (normalize, filters, etc.)
    silence.py            # Silence detection/splitting
    generators.py         # Signal generators (Sine, Square, etc.)
    playback.py           # play() function
    utils.py              # Utilities (db_to_float, mediainfo, etc.)
    exceptions.py         # Exception hierarchy
    scipy_effects.py      # Optional scipy-based effects
    _compat.py            # PydubException alias, import sonance as pydub
    py.typed              # PEP 561 marker
```

---

## Implementation Phases

### Phase 1: Pure Python Audio Engine

Core PCM operations and AudioSegment foundation.

**Deliverables:**
- `pcm.py` — pure Python replacements for all `audioop` functions:
  `mul`, `add`, `bias`, `lin2lin`, `tomono`, `tostereo`, `rms`, `max`,
  `maxpp`, `ratecv`, `reverse`; using `struct.unpack`/`struct.pack` and
  `array.array` for efficient sample manipulation; clamping to prevent
  overflow; support for 8-bit, 16-bit, 24-bit, and 32-bit sample widths
- `AudioSegment.__init__()` with raw PCM data storage
- Core properties: `raw_data`, `frame_rate`, `channels`, `sample_width`,
  `frame_width`, `frame_count()`, `duration_seconds`, `rms`, `dBFS`,
  `max`, `max_possible_amplitude`, `max_dBFS`, `array_type`
- Operator overloads: `__add__` (concat), `__radd__`, `__sub__` (volume),
  `__mul__` (repeat), `__getitem__` (slice), `__len__`, `__eq__`, `__ne__`,
  `__iter__`, `__hash__`
- Core methods: `get_array_of_samples()`, `get_sample_slice()`,
  `get_frame()`, `apply_gain()`, `set_sample_width()`, `set_frame_rate()`,
  `set_channels()`, `split_to_mono()`, `from_mono_audiosegments()`,
  `empty()`, `silent()`
- Internal methods: `_spawn()`, `_sync()`, `_parse_position()`, `bounded()`
- Exception hierarchy
- Optional numpy acceleration path (auto-detected)

### Phase 2: I/O & Format Support

File loading and export via ffmpeg.

**Deliverables:**
- `AudioSegment.from_file()` — universal loader via ffmpeg subprocess
- Format-specific constructors: `from_mp3()`, `from_wav()`, `from_ogg()`,
  `from_flv()`, `from_raw()`
- `AudioSegment.from_file_using_temporary_files()` — fallback loader
- Native WAV reading/writing using `wave` module (no ffmpeg needed)
- `AudioSegment.export()` — full export with format, codec, bitrate,
  parameters, tags, ID3v2 version, cover art support
- ffmpeg/ffprobe/avconv subprocess management
- `mediainfo()` and `mediainfo_json()` — probe file metadata
- `get_encoder_name()`, `get_player_name()`, `get_prober_name()`
- `get_supported_codecs()`, `get_supported_decoders()`,
  `get_supported_encoders()`
- `which()`, `fsdecode()` utilities
- WAV header parsing (`extract_wav_headers`, `fix_wav_headers`)

### Phase 3: Effects, Silence & Generators

Audio processing effects and signal generation.

**Deliverables:**
- `register_pydub_effect` decorator (registers methods on AudioSegment)
- Volume effects: `normalize()`, `apply_gain_stereo()`, `pan()`
- Time effects: `speedup()`, `reverse()` (already in Phase 1 via operator)
- Dynamics: `compress_dynamic_range()`
- Filters: `low_pass_filter()`, `high_pass_filter()` (1st-order RC)
- Phase: `invert_phase()`
- Spatial: `apply_mono_filter_to_each_channel()`
- Mix: `overlay()` with position, loop, times, gain_during_overlay
- Join: `append()` with crossfade
- Fade: `fade()`, `fade_in()`, `fade_out()`
- DC offset: `get_dc_offset()`, `remove_dc_offset()`
- Mid-Side: `stereo_to_ms()`, `ms_to_stereo()`
- Silence: `detect_silence()`, `detect_nonsilent()`, `split_on_silence()`,
  `detect_leading_silence()`, `strip_silence()`
- Generators: `SignalGenerator` base, `Sine`, `Pulse`, `Square`,
  `Sawtooth`, `Triangle`, `WhiteNoise` — with `to_audio_segment()`
- `make_chunks()` utility
- Optional `scipy_effects.py`: `band_pass_filter()`, `eq()`,
  scipy-backed `low_pass_filter()` and `high_pass_filter()`
- `playback.play()` via ffplay/avplay

### Phase 4: Polish & Ship

Testing, documentation, and release.

**Deliverables:**
- **Compatibility tests** — golden tests comparing sonance output against
  pydub output for every method and option combination
- **audioop parity tests** — verify pure Python `pcm.py` matches
  `audioop` output exactly (on Python <3.13 where audioop exists)
- **Python 3.13+ tests** — verify sonance works WITHOUT audioop
- **Edge case tests** — empty segments, zero-length, mono/stereo
  conversion, extreme sample widths, Unicode paths, large files
- **Performance benchmarks** — compare pcm.py vs audioop (C), measure
  numpy acceleration factor
- **Full type hints** — strict mypy, `py.typed` marker
- **README** — installation, quickstart, migration from pydub
- **Migration guide** — `import sonance as pydub` one-liner, behavioral
  differences (if any)
- **CI** — GitHub Actions: lint, test, build on Python 3.9/3.10/3.11/
  3.12/3.13/3.14
- **PyPI publish** — `sonance`

---

## Compatibility Guarantees

For any audio file and any pydub operation:

```python
from pydub import AudioSegment as PydubSegment
from sonance import AudioSegment as SonanceSegment

pydub_seg = PydubSegment.from_file("test.mp3")
sonance_seg = SonanceSegment.from_file("test.mp3")

# These must be equal:
assert pydub_seg.rms == sonance_seg.rms
assert pydub_seg.dBFS == sonance_seg.dBFS
assert pydub_seg.duration_seconds == sonance_seg.duration_seconds
assert pydub_seg.raw_data == sonance_seg.raw_data
```

The only intentional divergence: sonance works on Python 3.13+ where
pydub does not.
