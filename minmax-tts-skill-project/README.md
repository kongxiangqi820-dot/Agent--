# MiniMax TTS Skill (Standalone)

This is a standalone project that contains one reusable `tts` skill for dubbing.

## What it includes

- `skills/tts/SKILL.md`: skill instructions (focuses on calling Python script)
- `skills/tts/scripts/minmax_tts.py`: MiniMax TTS API caller
- `skills/tts/references/minmax-voice-notes.md`: voice/endpoint notes
- `skills/tts/agents/openai.yaml`: UI metadata

## Quick start

1. Set key:

```powershell
$env:MINMAX_API_KEY="your_minmax_api_key"
```

2. Generate audio:

```powershell
python skills/tts/scripts/minmax_tts.py `
  --text "这是一段配音文本" `
  --voice-id female-shaonv `
  --output outputs/audio/demo.mp3
```

## Notes

- Keep keys only in environment variables.
- `voice_id` should be selected from your available MiniMax voice list.
