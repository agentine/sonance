# sonance

A zero-dependency, modern Python replacement for [pydub](https://github.com/jiaaro/pydub).

Works on **Python 3.9–3.14+**, including Python 3.13 where pydub is broken due to the removal of `audioop`.

## Installation

```bash
pip install sonance
```

## Quick Start

```python
from sonance import AudioSegment

# Load, manipulate, export — same API as pydub
seg = AudioSegment.from_file("audio.mp3")
louder = seg + 6           # +6 dB
first_10s = seg[:10000]    # first 10 seconds
seg.export("out.wav", format="wav")
```

## Migration from pydub

```python
# Change this:
from pydub import AudioSegment

# To this:
from sonance import AudioSegment

# Or for zero-change migration:
import sonance as pydub
```

## License

MIT
