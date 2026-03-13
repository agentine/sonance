# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-13

Initial release of **sonance** — a zero-dependency, modern Python replacement for [pydub](https://github.com/jiaaro/pydub) that works on Python 3.13+ where pydub is broken due to the removal of the `audioop` standard library module.

### Added

- **`pcm.py`** — pure-Python implementations of all `audioop` functions used by pydub: `add`, `mul`, `bias`, `ratecv` (sample rate conversion via linear interpolation), `lin2lin` (bit depth conversion), `tostereo`, `tomono`, `max`, `minmax`, `rms`, `cross` (zero-crossings), `reverse`, `byteswap`, `adpcm2lin`, `lin2adpcm`, `ulaw2lin`, `lin2ulaw`, `alaw2lin`, `lin2alaw`. Optional NumPy fast path for bulk operations with identical output.
- **`AudioSegment`** — pydub-compatible core class:
  - Constructors: `AudioSegment(data, sample_width, frame_rate, channels)`, `from_file(path, format)`, `from_wav`, `from_mp3`, `from_ogg`, `from_raw`, `from_mono_audiosegments`, `silent`, `empty`
  - Properties: `duration_seconds`, `frame_count`, `frame_rate`, `sample_width`, `channels`, `max`, `max_dBFS`, `dBFS`, `rms`
  - Transforms: `set_frame_rate`, `set_channels`, `set_sample_width`, `apply_gain`, `normalize`, `fade_in`, `fade_out`, `fade`, `reverse`, `overlay`, `append`
  - Operators: `+` (concatenate), `*` (loop), `[]` (slice by milliseconds), `+=`
  - Export: `export(path, format, bitrate, parameters, tags, id3v2_version, cover)`
- **Optional NumPy acceleration** — install with `pip install sonance[numpy]`; pure-Python fallback always available.
- **Python 3.9–3.13 support** — works on 3.13 where `audioop` was removed; pure-Python path requires no C extensions.
- **pydub drop-in** — `from sonance import AudioSegment` replaces `from pydub import AudioSegment` for all common operations.
- **87 tests** (9 skipped on Python 3.13 due to `audioop` parity checks not applicable without the C module).

### Fixed

- NumPy/pure-Python parity: `_np_mul` now uses `np.trunc()` (not `np.round()`) to match C `audioop` truncation semantics.
- 8-bit `bias()` uses unsigned modular wrapping (values clamp to `[0, 255]`), matching `audioop` behavior.
- `__radd__` implemented so `sum([seg1, seg2], AudioSegment.empty())` works correctly.
