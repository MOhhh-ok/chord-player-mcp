#!/usr/bin/env python3
"""
chord_player.py - コード進行をMIDI生成→WAV変換→再生するスクリプト

使い方:
    python3 chord_player.py --chords "C Am F G" --bpm 120
    python3 chord_player.py --chords "Cmaj7 Dm7 G7 C" --bpm 90 --instrument 0 --beats 4
    python3 chord_player.py --chords "Em/B Am7 Dsus4 G" --bpm 100 --voicing open
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

from midiutil import MIDIFile

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

# コードタイプ → ルートからの半音間隔リスト
CHORD_INTERVALS = {
    "":      [0, 4, 7],           # major
    "m":     [0, 3, 7],           # minor
    "7":     [0, 4, 7, 10],       # dominant 7th
    "maj7":  [0, 4, 7, 11],       # major 7th
    "m7":    [0, 3, 7, 10],       # minor 7th
    "m7b5":  [0, 3, 6, 10],       # half-diminished
    "dim":   [0, 3, 6],           # diminished
    "dim7":  [0, 3, 6, 9],        # diminished 7th
    "aug":   [0, 4, 8],           # augmented
    "sus2":  [0, 2, 7],           # suspended 2nd
    "sus4":  [0, 5, 7],           # suspended 4th
    "7sus4": [0, 5, 7, 10],       # dominant 7th sus4
    "add9":  [0, 4, 7, 14],       # add 9th
    "madd9": [0, 3, 7, 14],       # minor add 9th
    "6":     [0, 4, 7, 9],        # major 6th
    "m6":    [0, 3, 7, 9],        # minor 6th
    "9":     [0, 4, 7, 10, 14],   # dominant 9th
    "maj9":  [0, 4, 7, 11, 14],   # major 9th
    "m9":    [0, 3, 7, 10, 14],   # minor 9th
    "5":     [0, 7],              # power chord
}

# GM音色名 → プログラム番号
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

def _find_soundfont() -> str:
    """Auto-detect a SoundFont file for FluidSynth."""
    import glob
    if sf := os.environ.get("SOUNDFONT_PATH"):
        return sf
    for pattern in [
        "/opt/homebrew/Cellar/fluid-synth/*/share/fluid-synth/sf2/*.sf2",
        "/usr/local/Cellar/fluid-synth/*/share/fluid-synth/sf2/*.sf2",
        "/usr/share/sounds/sf2/*.sf2",
        "/usr/share/soundfonts/*.sf2",
    ]:
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    raise FileNotFoundError(
        "No SoundFont found. Set the SOUNDFONT_PATH environment variable."
    )


SOUNDFONT_PATH = _find_soundfont()


def parse_chord(chord_str: str) -> tuple[int, list[int]]:
    """コード文字列をパースして (ベース音の半音値, 構成音の半音間隔リスト) を返す"""
    # スラッシュコード処理
    bass_override = None
    if "/" in chord_str:
        chord_part, bass_part = chord_str.split("/", 1)
        bass_override = NOTE_MAP.get(bass_part)
        chord_str = chord_part

    # ルート音を抽出
    if len(chord_str) >= 2 and chord_str[1] in ("#", "b"):
        root_name = chord_str[:2]
        quality = chord_str[2:]
    else:
        root_name = chord_str[:1]
        quality = chord_str[1:]

    root = NOTE_MAP.get(root_name)
    if root is None:
        print(f"Warning: unknown root note '{root_name}', skipping", file=sys.stderr)
        return 0, [0, 4, 7]

    intervals = CHORD_INTERVALS.get(quality)
    if intervals is None:
        print(f"Warning: unknown chord type '{quality}' in '{root_name}{quality}', using major", file=sys.stderr)
        intervals = CHORD_INTERVALS[""]

    return root, intervals, bass_override


def chord_to_midi_notes(root: int, intervals: list[int], bass_override: int | None,
                        base_octave: int = 4, voicing: str = "close") -> list[int]:
    """コード情報からMIDIノート番号のリストを生成"""
    base_midi = 12 * (base_octave + 1) + root  # C4 = 60

    notes = [base_midi + iv for iv in intervals]

    if voicing == "open":
        # オープンボイシング: 2番目の音を1オクターブ上げる
        if len(notes) >= 3:
            notes[1] += 12
    elif voicing == "drop2":
        # ドロップ2: 上から2番目の音を1オクターブ下げる
        if len(notes) >= 3:
            notes[-2] -= 12
            notes.sort()

    # ベース音追加（スラッシュコード or デフォルトルート）
    if bass_override is not None:
        bass_midi = 12 * base_octave + bass_override  # 1オクターブ下
        # ベース音がコード音より高い場合はさらに下げる
        while bass_midi >= min(notes):
            bass_midi -= 12
        notes.insert(0, bass_midi)
    elif voicing != "close":
        # open/drop2ではルートを1オクターブ下にも追加
        notes.insert(0, base_midi - 12)

    return notes


def generate_midi(chords: list[str], bpm: int, beats_per_chord: int,
                  instrument: int, voicing: str, velocity: int,
                  output_path: str):
    """コード進行からMIDIファイルを生成"""
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


def midi_to_wav(midi_path: str, wav_path: str, soundfont: str):
    """MIDIファイルをWAVに変換"""
    result = subprocess.run(
        ["fluidsynth", "-F", wav_path, "-ni", soundfont, midi_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"fluidsynth error: {result.stderr}", file=sys.stderr)
        sys.exit(1)


def play_wav(wav_path: str):
    """WAVファイルを再生"""
    system = platform.system()
    candidates = {
        "Darwin": "afplay",
        "Linux": "aplay",
        "Windows": "powershell",
    }
    cmd = candidates.get(system)
    if cmd is None:
        print(f"Unsupported platform: {system}", file=sys.stderr)
        sys.exit(1)
    if shutil.which(cmd) is None:
        print(f"'{cmd}' not found. Install it or use --no-play / --output.", file=sys.stderr)
        sys.exit(1)
    if system == "Windows":
        subprocess.run([cmd, "-c", f'(New-Object Media.SoundPlayer "{wav_path}").PlaySync()'])
    else:
        subprocess.run([cmd, wav_path])


def resolve_instrument(value: str) -> int:
    """音色名またはプログラム番号を解決"""
    if value.isdigit():
        return int(value)
    name = value.lower().replace(" ", "_").replace("-", "_")
    if name in INSTRUMENT_NAMES:
        return INSTRUMENT_NAMES[name]
    print(f"Unknown instrument '{value}', using piano (0)", file=sys.stderr)
    print(f"Available: {', '.join(sorted(INSTRUMENT_NAMES.keys()))}", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(description="コード進行を再生する")
    parser.add_argument("--chords", required=True, help='コード進行 (例: "C Am F G")')
    parser.add_argument("--bpm", type=int, default=120, help="テンポ (default: 120)")
    parser.add_argument("--beats", type=int, default=4, help="1コードあたりの拍数 (default: 4)")
    parser.add_argument("--instrument", default="piano", help="音色名 or GM番号 (default: piano)")
    parser.add_argument("--voicing", choices=["close", "open", "drop2"], default="close",
                        help="ボイシング (default: close)")
    parser.add_argument("--velocity", type=int, default=90, help="ベロシティ (default: 90)")
    parser.add_argument("--octave", type=int, default=4, help="ベースオクターブ (default: 4)")
    parser.add_argument("--soundfont", default=SOUNDFONT_PATH, help="サウンドフォントのパス")
    parser.add_argument("--output", default=None, help="出力WAVファイルパス (指定しない場合は一時ファイルで再生)")
    parser.add_argument("--midi-only", action="store_true", help="MIDIファイルのみ出力")
    parser.add_argument("--no-play", action="store_true", help="再生しない")
    parser.add_argument("--list-instruments", action="store_true", help="使用可能な音色一覧")

    args = parser.parse_args()

    if args.list_instruments:
        for name, num in sorted(INSTRUMENT_NAMES.items(), key=lambda x: x[1]):
            print(f"  {num:3d}: {name}")
        return

    chords = args.chords.split()
    instrument = resolve_instrument(args.instrument)

    # 出力先の決定
    if args.output:
        midi_path = args.output.replace(".wav", ".mid")
        wav_path = args.output if args.output.endswith(".wav") else args.output + ".wav"
    else:
        tmp_dir = tempfile.mkdtemp()
        midi_path = os.path.join(tmp_dir, "output.mid")
        wav_path = os.path.join(tmp_dir, "output.wav")

    # MIDI生成
    generate_midi(chords, args.bpm, args.beats, instrument, args.voicing, args.velocity, midi_path)
    print(f"MIDI generated: {midi_path}")

    if args.midi_only:
        return

    # WAV変換
    midi_to_wav(midi_path, wav_path, args.soundfont)
    print(f"WAV rendered: {wav_path}")

    # 再生
    if not args.no_play:
        print(f"Playing: {' → '.join(chords)} (BPM={args.bpm}, instrument={instrument})")
        play_wav(wav_path)


if __name__ == "__main__":
    main()
