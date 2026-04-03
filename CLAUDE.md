# chord-player

コード進行を音声で再生するツール。

## 使い方

```bash
cd /Users/masaaki/Dev/playground/chord-player
source .venv/bin/activate
python3 chord_player.py --chords "C Am F G" --bpm 120
```

## パラメータ

| パラメータ | 説明 | デフォルト |
|-----------|------|-----------|
| `--chords` | コード進行（スペース区切り） | 必須 |
| `--bpm` | テンポ | 120 |
| `--beats` | 1コードあたりの拍数 | 4 |
| `--instrument` | 音色名 or GM番号 | piano |
| `--voicing` | close / open / drop2 | close |
| `--velocity` | 音量(0-127) | 90 |
| `--octave` | ベースオクターブ | 4 |
| `--output` | 出力WAVパス | 一時ファイル |
| `--midi-only` | MIDI出力のみ | false |
| `--no-play` | 再生しない | false |

## 対応コード

メジャー(C), マイナー(Cm), 7th(C7), maj7(Cmaj7), m7(Cm7), dim, aug, sus2, sus4, add9, 6, 9, m7b5, 5(パワーコード) 等。スラッシュコード(C/E)も対応。

## 音色の例

piano, electric_piano, guitar, acoustic_guitar, organ, strings, bass, violin, flute, sax, trumpet, synth_pad, vibraphone, choir など。`--list-instruments` で一覧表示。

## 使用例

```bash
# 基本のコード進行
python3 chord_player.py --chords "C Am F G" --bpm 120

# ジャズっぽく
python3 chord_player.py --chords "Cmaj7 Am7 Dm7 G7" --bpm 90 --instrument electric_piano --voicing drop2

# ギターでバラード
python3 chord_player.py --chords "G Em C D" --bpm 72 --instrument guitar --beats 8 --voicing open

# スラッシュコード
python3 chord_player.py --chords "C C/B Am Am/G F G C" --bpm 100
```

## 依存

- Python 3 + midiutil（.venvにインストール済み）
- fluidsynth（brew install fluid-synth）
- afplay（macOS標準）
