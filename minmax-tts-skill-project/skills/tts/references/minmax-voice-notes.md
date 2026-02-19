# MiniMaxi Voice Notes (Aligned)

Official docs:

- Voice clone guide:
  - https://platform.minimaxi.com/docs/guides/speech-voice-clone
- Sync TTS HTTP reference:
  - https://platform.minimaxi.com/docs/api-reference/speech-t2a-http
- System voice IDs FAQ:
  - https://platform.minimaxi.com/docs/faq/system-voice-id

Auth and endpoint:

- Header: `Authorization: Bearer <MINIMAX_API_KEY>`
- Primary endpoint: `POST https://api.minimaxi.com/v1/t2a_v2`
- Backup endpoint: `POST https://api-bj.minimaxi.com/v1/t2a_v2`

Voice clone IDs:

- `voice_id`: custom ID for your cloned voice.
- `file_id`: returned after uploading source audio, used in clone request.
- Clone workflow: upload audio -> create clone -> use cloned `voice_id` in TTS.

Practical note:

- Keep `voice_id` configurable in runtime arguments.
- Do not hardcode one voice for all dubbing tasks.
