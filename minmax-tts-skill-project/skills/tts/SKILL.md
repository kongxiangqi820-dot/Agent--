---
name: tts
description: Use this skill when the user asks for text-to-speech, dubbing, voice-over, or audio narration generation for videos using MiniMaxi TTS. This includes converting short or medium text into mp3/wav/flac, selecting a voice_id (system or cloned), adjusting speed/volume/pitch/emotion, and producing final audio files for downstream video workflows.
---

# TTS (MiniMaxi) Workflow

## Core Rule

Always generate dubbing audio by running the bundled Python script.  
Do not hand-write ad-hoc HTTP calls when this skill is available.

Script path:

`skills/tts/scripts/minmax_tts.py`

## Prepare

1. Set API key in environment variable:
   - PowerShell: `$env:MINIMAX_API_KEY="your_minimaxi_key"`
2. Ensure output directory exists (for example `outputs/audio/`).
3. Choose a valid `voice_id` from MiniMaxi system voices or your cloned voices.
   - See `skills/tts/references/minmax-voice-notes.md`

## Execute

### A) Convert direct text to audio

```powershell
python skills/tts/scripts/minmax_tts.py `
  --text "这是一段用于短视频配音的旁白文本" `
  --voice-id female-shaonv `
  --output outputs/audio/narration.mp3
```

### B) Convert long text file to audio

```powershell
python skills/tts/scripts/minmax_tts.py `
  --text-file scripts/input.txt `
  --voice-id male-qn-jingying `
  --model speech-2.8-hd `
  --format mp3 `
  --output outputs/audio/narration_from_file.mp3
```

### C) Fine tune tone and rhythm

```powershell
python skills/tts/scripts/minmax_tts.py `
  --text "请用更快节奏播报这段文案" `
  --voice-id female-yujie `
  --emotion happy `
  --speed 1.15 `
  --volume 1.2 `
  --pitch 0 `
  --output outputs/audio/fast_style.mp3
```

### D) Use cloned voice_id from voice-clone flow

```powershell
python skills/tts/scripts/minmax_tts.py `
  --text "这是使用克隆音色进行配音的测试文本" `
  --voice-id your_cloned_voice_id `
  --output outputs/audio/cloned_voice.mp3
```

## Parameters

- `--voice-id`: required. System voice_id or cloned voice_id.
- `--model`: default `speech-2.8-hd`.
- `--text` / `--text-file`: exactly one must be provided.
- `--output`: target audio file path.
- `--format`: `mp3` / `wav` / `flac` / `pcm` (default `mp3`).
- `--speed`, `--volume`, `--pitch`, `--emotion`: expressive controls.
- `--output-format`: `hex` / `url`, default `hex`.
- `--endpoint`: default `https://api.minimaxi.com/v1/t2a_v2`.

## Output Contract

After successful execution, the script prints a single JSON object containing:

- `ok`
- `output_path`
- `voice_id`
- `model`
- `format`
- `bytes`
- `trace_id`

Use `output_path` as the dubbing input for your downstream video pipeline.

## Troubleshooting

- If you get 401/403:
  - Check `MINIMAX_API_KEY`.
- If you get voice-related errors:
  - Confirm the `voice_id` exists in current MiniMaxi voice list.
- If synthesis fails for long text:
  - Split text into smaller chunks and synthesize per chunk, then concatenate later.
- If you use a cloned voice:
  - Ensure voice clone was completed first (upload file -> clone -> get `voice_id`).
