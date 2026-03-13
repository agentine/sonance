# sonance

**Pure Python audio manipulation — a drop-in pydub replacement that works on Python 3.13+.**

pydub is broken on Python 3.13+ because the `audioop` C extension was removed from the standard library. sonance reimplements every `audioop` operation in pure Python using `struct` and `array`, restoring the familiar `AudioSegment` API with zero dependencies beyond Python itself (and ffmpeg for non-WAV formats).

---

## Why sonance

| | pydub | sonance |
|---|---|---|
| Python 3.13+ | Broken (`ModuleNotFoundError: No module named 'audioop'`) | Works |
| Python 3.12 | DeprecationWarning | Works |
| Python 3.9–3.11 | Works | Works |
| audioop dependency | Required (removed from stdlib) | None — pure Python |
| Dependencies | None (but audioop was stdlib) | None |
| Last release | March 2021 | Active |
| API compatibility | — | 100% pydub-compatible |

pydub has 18.4 million monthly downloads and 108,000+ dependents. Its sole maintainer has not responded to issues or PRs since 2021, and a fix for the Python 3.13 breakage has sat unmerged for over a year. sonance is the drop-in fix.

---

## Installation

```bash
pip install sonance
```

Optional numpy acceleration (10–100x speedup on large buffers):

```bash
pip install sonance[numpy]
```

ffmpeg must be installed separately for non-WAV formats (MP3, OGG, FLAC, etc.):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
apt install ffmpeg

# Windows
winget install ffmpeg
```

---

## Quick Start

```python
from sonance import AudioSegment

# Load any audio file
song = AudioSegment.from_file("song.mp3")

# Slice, adjust volume, concatenate — same as pydub
intro = song[:10000]          # first 10 seconds (ms-based slicing)
louder = song + 6             # +6 dB
quieter = song - 3            # -3 dB
loop = song * 3               # repeat 3 times
combined = intro + song[10000:20000]

# Inspect
print(f"{song.duration_seconds:.1f}s, {song.dBFS:.1f} dBFS")

# Export
song.export("out.wav", format="wav")
song.export("out.mp3", format="mp3", bitrate="192k")
```

---

## AudioSegment API

### Constructors

```python
from sonance import AudioSegment

# From a file (any format supported by ffmpeg)
seg = AudioSegment.from_file("audio.mp3")
seg = AudioSegment.from_file("audio.mp3", format="mp3")

# Format-specific shortcuts
seg = AudioSegment.from_mp3("song.mp3")
seg = AudioSegment.from_wav("sound.wav")
seg = AudioSegment.from_ogg("audio.ogg")

# From raw PCM bytes
seg = AudioSegment.from_raw(
    data,
    sample_width=2,   # bytes per sample: 1, 2, 3, or 4
    frame_rate=44100, # Hz
    channels=2,       # 1=mono, 2=stereo
)

# Utility constructors
empty = AudioSegment.empty()                          # zero-length segment
silence = AudioSegment.silent(duration=1000)          # 1 second of silence
silence = AudioSegment.silent(duration=500, frame_rate=44100)

# Merge mono segments into multi-channel
stereo = AudioSegment.from_mono_audiosegments(left_mono, right_mono)
```

### Properties

| Property | Type | Description |
|---|---|---|
| `raw_data` | `bytes` | Raw PCM audio bytes |
| `frame_rate` | `int` | Sample rate in Hz |
| `channels` | `int` | Number of channels (1=mono, 2=stereo) |
| `sample_width` | `int` | Bytes per sample (1, 2, 3, or 4) |
| `frame_width` | `int` | Bytes per frame (`sample_width * channels`) |
| `duration_seconds` | `float` | Duration in seconds |
| `rms` | `int` | RMS amplitude |
| `dBFS` | `float` | Loudness in dBFS (−∞ for silence) |
| `max` | `int` | Peak absolute amplitude |
| `max_possible_amplitude` | `float` | Maximum value for the current bit depth |
| `max_dBFS` | `float` | Peak dBFS level |
| `array_type` | `str` | `array.array` type code for the sample width |

```python
seg = AudioSegment.from_file("audio.wav")

print(seg.duration_seconds)        # e.g. 3.14
print(seg.frame_rate)              # e.g. 44100
print(seg.channels)                # 1 or 2
print(seg.sample_width)            # 2 (16-bit)
print(seg.dBFS)                    # e.g. -14.3
print(seg.rms)                     # e.g. 4821
print(seg.max)                     # e.g. 28412
print(seg.max_possible_amplitude)  # 32768.0 for 16-bit
```

### Operators

```python
# Concatenation
combined = seg1 + seg2

# Volume adjustment (dB)
louder  = seg + 6     # +6 dB
quieter = seg - 3     # −3 dB

# Repeat
loop = seg * 3

# Slice by milliseconds
first_10s  = seg[:10000]
middle     = seg[5000:15000]
last_5s    = seg[-5000:]

# Length in milliseconds
duration_ms = len(seg)

# sum() works with AudioSegment.empty() as start value
total = sum(segments, AudioSegment.empty())
```

Segments with mismatched formats are automatically synchronized before concatenation or mixing — the higher sample width, frame rate, and channel count win.

### Transform Methods

```python
# Volume
louder = seg.apply_gain(6.0)      # +6 dB
quieter = seg.apply_gain(-3.0)    # -3 dB

# Sample format conversion
seg_16bit = seg.set_sample_width(2)   # 1, 2, 3, or 4 bytes
seg_48k   = seg.set_frame_rate(48000) # resample to 48 kHz
seg_stereo = seg.set_channels(2)      # mono → stereo
seg_mono   = seg.set_channels(1)      # stereo → mono

# Split stereo into a list of mono segments
[left, right] = stereo_seg.split_to_mono()

# DC offset
offset = seg.get_dc_offset(channel=1)         # measure (1-based channel)
clean  = seg.remove_dc_offset()                # auto-detect and remove
clean  = seg.remove_dc_offset(channel=1)       # one channel only
clean  = seg.remove_dc_offset(offset=128.0)    # explicit value
```

All transform methods return new `AudioSegment` instances — the original is never modified.

### Effects

```python
# Fade
faded_in  = seg.fade_in(duration=2000)    # 2-second fade in
faded_out = seg.fade_out(duration=2000)   # 2-second fade out

# Custom fade: specify start/end positions and gain targets
custom = seg.fade(to_gain=-6, from_gain=0, start=0, duration=3000)

# Overlay (mix two segments)
mixed = background.overlay(foreground)
mixed = background.overlay(foreground, position=3000)     # start at 3s
mixed = background.overlay(foreground, loop=True)         # loop foreground
mixed = background.overlay(foreground, times=3)           # repeat 3 times
mixed = background.overlay(foreground, gain_during_overlay=-6)

# Append with crossfade
joined = seg1.append(seg2, crossfade=100)   # 100 ms crossfade

# Strip silence from beginning and end
stripped = seg.strip_silence(silence_len=1000, silence_thresh=-16, padding=100)
```

### I/O

```python
# Load
seg = AudioSegment.from_file("audio.mp3")
seg = AudioSegment.from_file("audio.mp3", format="mp3")
seg = AudioSegment.from_wav("sound.wav")   # uses stdlib wave module, no ffmpeg

# Export
seg.export("out.mp3")
seg.export("out.wav", format="wav")
seg.export("out.ogg", format="ogg", codec="libvorbis")
seg.export("out.mp3", format="mp3", bitrate="192k")

# Export with metadata tags
seg.export(
    "out.mp3",
    format="mp3",
    bitrate="320k",
    tags={"artist": "Artist Name", "title": "Track Title", "album": "Album"},
    id3v2_version="4",
)

# Export to a file-like object
import io
buf = io.BytesIO()
seg.export(buf, format="wav")

# Export with cover art
seg.export("out.mp3", format="mp3", cover="cover.jpg")

# Pass arbitrary ffmpeg parameters
seg.export("out.mp3", format="mp3", parameters=["-q:a", "0"])
```

WAV files are read with Python's built-in `wave` module — no ffmpeg needed. All other formats require ffmpeg in `$PATH`.

---

## pcm.py — Pure Python audioop Equivalents

`sonance.pcm` provides direct replacements for every removed `audioop` function. You can use these directly if you need low-level PCM manipulation.

Supported sample widths: 1 (8-bit), 2 (16-bit), 3 (24-bit), 4 (32-bit). All functions operate on `bytes` fragments of raw PCM data.

```python
from sonance import pcm

# Multiply all samples by a factor (volume scaling)
pcm.mul(frag, width, factor)

# Add two fragments sample-by-sample (mixing)
pcm.add(frag1, frag2, width)

# Add a constant bias to all samples (DC offset correction)
pcm.bias(frag, width, bias_val)

# Convert between sample widths (e.g. 16-bit → 32-bit)
pcm.lin2lin(frag, width, newwidth)

# Stereo → mono with channel weights
pcm.tomono(frag, width, lfactor, rfactor)

# Mono → stereo with per-channel scaling
pcm.tostereo(frag, width, lfactor, rfactor)

# RMS amplitude
pcm.rms(frag, width)

# Peak absolute amplitude
pcm.max(frag, width)

# Maximum peak-to-peak amplitude
pcm.maxpp(frag, width)

# Resample (linear interpolation); returns (output_bytes, state)
pcm.ratecv(frag, width, nchannels, inrate, outrate, state)

# Reverse frame order
pcm.reverse(frag, width)
```

### audioop → pcm mapping

| `audioop` | `sonance.pcm` | Notes |
|---|---|---|
| `audioop.mul(frag, width, factor)` | `pcm.mul(frag, width, factor)` | Identical signature |
| `audioop.add(frag1, frag2, width)` | `pcm.add(frag1, frag2, width)` | Identical signature |
| `audioop.bias(frag, width, bias)` | `pcm.bias(frag, width, bias)` | Identical signature |
| `audioop.lin2lin(frag, width, newwidth)` | `pcm.lin2lin(frag, width, newwidth)` | Identical signature |
| `audioop.tomono(frag, width, lf, rf)` | `pcm.tomono(frag, width, lf, rf)` | Identical signature |
| `audioop.tostereo(frag, width, lf, rf)` | `pcm.tostereo(frag, width, lf, rf)` | Identical signature |
| `audioop.rms(frag, width)` | `pcm.rms(frag, width)` | Identical signature |
| `audioop.max(frag, width)` | `pcm.max(frag, width)` | Identical signature |
| `audioop.maxpp(frag, width)` | `pcm.maxpp(frag, width)` | Identical signature |
| `audioop.ratecv(frag, width, nc, ir, or, state)` | `pcm.ratecv(frag, width, nc, ir, or, state)` | Identical signature |
| `audioop.reverse(frag, width)` | `pcm.reverse(frag, width)` | Identical signature |

When numpy is installed, the compute-heavy functions (`mul`, `add`, `bias`, `rms`) use vectorized array operations automatically with no API change.

---

## Optional numpy Acceleration

sonance works without numpy. Install it for 10–100x speedup on large audio buffers:

```bash
pip install sonance[numpy]
# or separately:
pip install numpy
```

The acceleration is automatic — no code changes needed. When numpy is present, `pcm.mul`, `pcm.add`, `pcm.bias`, and `pcm.rms` dispatch to vectorized NumPy implementations. 24-bit (3-byte) audio always uses the pure Python path since numpy does not have a native 24-bit integer type.

---

## Migration Guide: pydub → sonance

### Option 1: Change one import line

```python
# Before
from pydub import AudioSegment

# After
from sonance import AudioSegment
```

That's it. The `AudioSegment` class is API-compatible — all operators, properties, methods, and constructors work the same way.

### Option 2: Zero-change migration via compatibility shim

If you want to migrate without touching any other imports, use:

```python
import sonance as pydub
```

Then `pydub.AudioSegment` resolves to `sonance.AudioSegment`. Any code that does `from pydub import AudioSegment` still needs a one-line change, but the module-level attribute access pattern `pydub.AudioSegment` works immediately.

### Option 3: Replace audioop directly

If your code imports `audioop` directly (not through pydub), replace it:

```python
# Before
import audioop
result = audioop.mul(frag, 2, 1.5)

# After
from sonance import pcm
result = pcm.mul(frag, 2, 1.5)
```

Every `audioop` function has an identical counterpart in `sonance.pcm`.

### Exception compatibility

pydub's `PydubException` is available as an alias:

```python
from sonance.exceptions import PydubException  # alias for SonanceException
```

### What changed

sonance is intentionally 100% compatible with pydub. The only intentional difference is that sonance works on Python 3.13+ and pydub does not. If you find a behavioral difference, please open an issue.

---

## Project Structure

```
src/sonance/
    __init__.py        # AudioSegment + exceptions re-exported
    audio_segment.py   # AudioSegment class
    pcm.py             # Pure Python audioop replacements
    exceptions.py      # SonanceException hierarchy
    _compat.py         # PydubException alias
    py.typed           # PEP 561 marker (full type hints)
```

---

## Requirements

- **Python 3.9+** (including 3.13, 3.14)
- **ffmpeg** in `$PATH` for non-WAV formats
- **numpy** (optional) for accelerated PCM operations

---

## License

MIT
