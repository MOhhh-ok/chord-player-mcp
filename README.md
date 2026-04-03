# chord-player-mcp

An MCP server that plays chord progressions via MIDI/WAV synthesis.

## Prerequisites

- [FluidSynth](https://www.fluidsynth.org/) with a SoundFont installed
- [uv](https://docs.astral.sh/uv/) (for `uvx`)

```bash
# macOS
brew install fluid-synth
```

## Setup (Claude Code)

Add the following to your MCP settings:

```json
{
  "mcpServers": {
    "chord-player": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/MOhhh-ok/chord-player-mcp", "chord-player-mcp"]
    }
  }
}
```

## MCP Tools

### `play_chords`

Play a chord progression.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `chords` | Space-separated chord progression (e.g. `"C Am F G"`) | required |
| `bpm` | Tempo | 120 |
| `beats` | Beats per chord | 4 |
| `instrument` | Instrument name or GM program number | piano |
| `voicing` | `close` / `open` / `drop2` | close |
| `velocity` | Volume (0-127) | 90 |
| `output` | Output WAV path (temp file if omitted) | - |

### `list_instruments`

Returns a list of available instrument names.

## Supported Chords

Major (C), minor (Cm), 7th (C7), maj7 (Cmaj7), m7 (Cm7), dim, dim7, aug, sus2, sus4, 7sus4, add9, madd9, 6, m6, 9, maj9, m9, 5 (power chord). Slash chords (C/E) are also supported.

## Instruments

piano, electric_piano, guitar, acoustic_guitar, organ, strings, bass, violin, flute, sax, trumpet, synth_pad, vibraphone, choir, and more.

## Examples

```
# Basic progression
play_chords("C Am F G")

# Jazz voicing
play_chords("Cmaj7 Am7 Dm7 G7", bpm=90, instrument="electric_piano", voicing="drop2")

# Guitar ballad
play_chords("G Em C D", bpm=72, instrument="guitar", beats=8, voicing="open")

# Slash chords
play_chords("C C/B Am Am/G F G C", bpm=100)
```
