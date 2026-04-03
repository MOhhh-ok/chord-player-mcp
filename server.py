#!/usr/bin/env python3
"""chord-player MCP server"""

import os
import platform
import shutil
import subprocess
import tempfile

from mcp.server.fastmcp import FastMCP
from midiutil import MIDIFile

mcp = FastMCP("chord-player")

# ルート音名 → 半音数(C=0)
NOTE_MAP = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4, "E#": 5,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11, "B#": 0,
}

CHORD_INTERVALS = {
    "":      [0, 4, 7],
    "m":     [0, 3, 7],
    "7":     [0, 4, 7, 10],
    "maj7":  [0, 4, 7, 11],
    "m7":    [0, 3, 7, 10],
    "m7b5":  [0, 3, 6, 10],
    "dim":   [0, 3, 6],
    "dim7":  [0, 3, 6, 9],
    "aug":   [0, 4, 8],
    "sus2":  [0, 2, 7],
    "sus4":  [0, 5, 7],
    "7sus4": [0, 5, 7, 10],
    "add9":  [0, 4, 7, 14],
    "madd9": [0, 3, 7, 14],
    "6":     [0, 4, 7, 9],
    "m6":    [0, 3, 7, 9],
    "9":     [0, 4, 7, 10, 14],
    "maj9":  [0, 4, 7, 11, 14],
    "m9":    [0, 3, 7, 10, 14],
    "5":     [0, 7],
}

INSTRUMENT_NAMES = {
    "acoustic_piano": 0, "piano": 0,
    "bright_piano": 1,
    "electric_piano": 4, "epiano": 4,
    "harpsichord": 6,
    "clavinet": 7,
    "vibraphone": 11,
    "marimba": 12,
    "organ": 19, "church_organ": 19,
    "accordion": 21,
    "nylon_guitar": 24, "acoustic_guitar": 24, "guitar": 24,
    "steel_guitar": 25,
    "jazz_guitar": 26,
    "clean_guitar": 27, "electric_guitar": 27,
    "overdriven_guitar": 29,
    "distortion_guitar": 30,
    "acoustic_bass": 32, "bass": 32,
    "electric_bass": 33,
    "slap_bass": 36,
    "violin": 40,
    "viola": 41,
    "cello": 42,
    "strings": 48, "string_ensemble": 48,
    "choir": 52,
    "trumpet": 56,
    "trombone": 57,
    "tuba": 58,
    "french_horn": 60,
    "sax": 66, "tenor_sax": 66,
    "alto_sax": 65,
    "oboe": 68,
    "flute": 73,
    "pad": 88, "synth_pad": 88,
    "synth_lead": 80,
}

SOUNDFONT_PATH = "/opt/homebrew/Cellar/fluid-synth/2.5.3/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2"


def parse_chord(chord_str: str):
    bass_override = None
    if "/" in chord_str:
        chord_part, bass_part = chord_str.split("/", 1)
        bass_override = NOTE_MAP.get(bass_part)
        chord_str = chord_part

    if len(chord_str) >= 2 and chord_str[1] in ("#", "b"):
        root_name = chord_str[:2]
        quality = chord_str[2:]
    else:
        root_name = chord_str[:1]
        quality = chord_str[1:]

    root = NOTE_MAP.get(root_name, 0)
    intervals = CHORD_INTERVALS.get(quality, CHORD_INTERVALS[""])
    return root, intervals, bass_override


def chord_to_midi_notes(root, intervals, bass_override, base_octave=4, voicing="close"):
    base_midi = 12 * (base_octave + 1) + root
    notes = [base_midi + iv for iv in intervals]

    if voicing == "open" and len(notes) >= 3:
        notes[1] += 12
    elif voicing == "drop2" and len(notes) >= 3:
        notes[-2] -= 12
        notes.sort()

    if bass_override is not None:
        bass_midi = 12 * base_octave + bass_override
        while bass_midi >= min(notes):
            bass_midi -= 12
        notes.insert(0, bass_midi)
    elif voicing != "close":
        notes.insert(0, base_midi - 12)

    return notes


def generate_midi(chords, bpm, beats_per_chord, instrument, voicing, velocity, output_path):
    midi = MIDIFile(1)
    track = 0
    channel = 0
    time = 0
    midi.addTempo(track, 0, bpm)
    midi.addProgramChange(track, channel, 0, instrument)

    for chord_str in chords:
        root, intervals, bass_override = parse_chord(chord_str)
        notes = chord_to_midi_notes(root, intervals, bass_override, voicing=voicing)
        for note in notes:
            midi.addNote(track, channel, note, time, beats_per_chord, velocity)
        time += beats_per_chord

    with open(output_path, "wb") as f:
        midi.writeFile(f)


def resolve_instrument(value: str) -> int:
    if value.isdigit():
        return int(value)
    name = value.lower().replace(" ", "_").replace("-", "_")
    return INSTRUMENT_NAMES.get(name, 0)


@mcp.tool()
def play_chords(
    chords: str,
    bpm: int = 120,
    beats: int = 4,
    instrument: str = "piano",
    voicing: str = "close",
    velocity: int = 90,
    output: str | None = None,
) -> str:
    """コード進行を再生する。

    Args:
        chords: スペース区切りのコード進行 (例: "C Am F G", "Cmaj7 Dm7 G7 C")
        bpm: テンポ (default: 120)
        beats: 1コードあたりの拍数 (default: 4)
        instrument: 音色名 (piano, electric_piano, guitar, organ, strings, sax, flute 等)
        voicing: ボイシング close / open / drop2 (default: close)
        velocity: 音量 0-127 (default: 90)
        output: 出力WAVパス (省略時は一時ファイルで再生後削除)
    """
    chord_list = chords.split()
    inst_num = resolve_instrument(instrument)

    if output:
        midi_path = output.replace(".wav", ".mid")
        wav_path = output if output.endswith(".wav") else output + ".wav"
    else:
        tmp_dir = tempfile.mkdtemp()
        midi_path = os.path.join(tmp_dir, "output.mid")
        wav_path = os.path.join(tmp_dir, "output.wav")

    # MIDI生成
    generate_midi(chord_list, bpm, beats, inst_num, voicing, velocity, midi_path)

    # WAV変換
    result = subprocess.run(
        ["fluidsynth", "-F", wav_path, "-ni", SOUNDFONT_PATH, midi_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return f"fluidsynth error: {result.stderr}"

    # 再生
    if platform.system() == "Darwin" and shutil.which("afplay"):
        subprocess.run(["afplay", wav_path])

    progression = " → ".join(chord_list)
    return f"再生完了: {progression} (BPM={bpm}, instrument={instrument}, voicing={voicing})"


@mcp.tool()
def list_instruments() -> str:
    """使用可能な音色の一覧を返す"""
    lines = []
    for name, num in sorted(INSTRUMENT_NAMES.items(), key=lambda x: x[1]):
        lines.append(f"{num:3d}: {name}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
