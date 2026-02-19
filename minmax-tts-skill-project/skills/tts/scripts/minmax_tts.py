#!/usr/bin/env python3
"""MiniMaxi Text-to-Speech helper.

Aligned with MiniMax Open Platform docs:
- Sync TTS HTTP: POST https://api.minimaxi.com/v1/t2a_v2
- Voice clone guide uses MINIMAX_API_KEY + voice_id/file_id flow.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


DEFAULT_ENDPOINT = "https://api.minimaxi.com/v1/t2a_v2"
DEFAULT_BACKUP_ENDPOINT = "https://api-bj.minimaxi.com/v1/t2a_v2"
DEFAULT_MODEL = "speech-2.8-hd"
SUPPORTED_MODELS = [
    "speech-2.8-hd",
    "speech-2.8-turbo",
    "speech-2.6-hd",
    "speech-2.6-turbo",
    "speech-02-hd",
    "speech-02-turbo",
    "speech-01-hd",
    "speech-01-turbo",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call MiniMaxi TTS HTTP API and save audio file.")
    parser.add_argument("--text", help="Text content to synthesize.")
    parser.add_argument("--text-file", help="Read text from file.")
    parser.add_argument("--voice-id", required=True, help="Voice ID (system voice or cloned voice_id).")
    parser.add_argument("--output", required=True, help="Output audio file path.")
    parser.add_argument("--format", default="mp3", choices=["mp3", "wav", "flac", "pcm"])
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=SUPPORTED_MODELS, help="MiniMaxi TTS model.")
    parser.add_argument("--sample-rate", type=int, default=32000)
    parser.add_argument("--bitrate", type=int, default=128000)
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--volume", type=float, default=1.0)
    parser.add_argument("--pitch", type=int, default=0)
    parser.add_argument("--emotion", default="", help="Optional emotion in voice_setting.")
    parser.add_argument(
        "--language-boost",
        default="",
        help="Optional language_boost. Example: auto / Chinese / English.",
    )
    parser.add_argument(
        "--pronunciation-tone",
        action="append",
        default=[],
        help='Optional pronunciation_dict.tone item. Repeatable. Example: "处理/(chu3)(li3)"',
    )
    parser.add_argument("--output-format", default="hex", choices=["hex", "url"])
    parser.add_argument("--subtitle-enable", action="store_true", help="Enable subtitle service (non-stream only).")
    parser.add_argument("--aigc-watermark", action="store_true", help="Append AIGC watermark to generated audio.")
    parser.add_argument("--voice-modify-pitch", type=float, default=None)
    parser.add_argument("--voice-modify-intensity", type=float, default=None)
    parser.add_argument("--voice-modify-timbre", type=float, default=None)
    parser.add_argument(
        "--endpoint",
        default=os.getenv("MINIMAX_TTS_ENDPOINT", os.getenv("MINMAX_TTS_ENDPOINT", DEFAULT_ENDPOINT)),
    )
    parser.add_argument(
        "--backup-endpoint",
        default=os.getenv("MINIMAX_TTS_BACKUP_ENDPOINT", DEFAULT_BACKUP_ENDPOINT),
        help="Fallback endpoint if primary endpoint fails.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MINIMAX_API_KEY", os.getenv("MINMAX_API_KEY", "")),
    )
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args()


def read_text(args: argparse.Namespace) -> str:
    if bool(args.text) == bool(args.text_file):
        raise ValueError("Provide exactly one of --text or --text-file.")

    if args.text:
        text = args.text.strip()
    else:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()

    if not text:
        raise ValueError("Input text is empty.")
    return text


def build_payload(text: str, args: argparse.Namespace) -> dict:
    payload = {
        "model": args.model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": args.voice_id,
            "speed": args.speed,
            "vol": args.volume,
            "pitch": args.pitch,
        },
        "audio_setting": {
            "sample_rate": args.sample_rate,
            "bitrate": args.bitrate,
            "format": args.format,
            "channel": args.channel,
        },
        "subtitle_enable": args.subtitle_enable,
        "output_format": args.output_format,
        "aigc_watermark": args.aigc_watermark,
    }
    if args.emotion:
        payload["voice_setting"]["emotion"] = args.emotion
    if args.language_boost:
        payload["language_boost"] = args.language_boost
    if args.pronunciation_tone:
        payload["pronunciation_dict"] = {"tone": args.pronunciation_tone}

    voice_modify: dict[str, float] = {}
    if args.voice_modify_pitch is not None:
        voice_modify["pitch"] = args.voice_modify_pitch
    if args.voice_modify_intensity is not None:
        voice_modify["intensity"] = args.voice_modify_intensity
    if args.voice_modify_timbre is not None:
        voice_modify["timbre"] = args.voice_modify_timbre
    if voice_modify:
        payload["voice_modify"] = voice_modify

    return payload


def call_minimaxi(payload: dict, args: argparse.Namespace) -> dict:
    if not args.api_key:
        raise ValueError("Missing API key. Set MINIMAX_API_KEY (or legacy MINMAX_API_KEY).")

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "Content-Type": "application/json",
    }
    endpoints = [args.endpoint]
    if args.backup_endpoint and args.backup_endpoint not in endpoints:
        endpoints.append(args.backup_endpoint)

    last_error: Exception | None = None
    for endpoint in endpoints:
        req = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=args.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            last_error = RuntimeError(f"HTTP {exc.code} @ {endpoint}: {details}")
        except Exception as exc:
            last_error = RuntimeError(f"Request failed @ {endpoint}: {exc}")

    raise RuntimeError(str(last_error) if last_error else "Unknown request error")


def decode_audio_field(audio_value: str) -> bytes:
    try:
        return bytes.fromhex(audio_value)
    except ValueError:
        return base64.b64decode(audio_value)


def save_audio(resp: dict, args: argparse.Namespace) -> Path:
    base_resp = resp.get("base_resp", {})
    status_code = base_resp.get("status_code", 0)
    if status_code != 0:
        status_msg = base_resp.get("status_msg", "unknown error")
        trace_id = resp.get("trace_id", "")
        raise RuntimeError(
            f"MiniMaxi error: status_code={status_code}, status_msg={status_msg}, trace_id={trace_id}"
        )

    data = resp.get("data") or {}
    audio = data.get("audio")
    if not audio:
        raise RuntimeError("Response missing data.audio.")

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.output_format == "url":
        with urllib.request.urlopen(audio, timeout=args.timeout) as downloaded:
            content = downloaded.read()
    else:
        content = decode_audio_field(audio)

    output_path.write_bytes(content)
    return output_path


def main() -> int:
    args = parse_args()
    try:
        text = read_text(args)
        payload = build_payload(text, args)
        resp = call_minimaxi(payload, args)
        output_path = save_audio(resp, args)
        extra_info = resp.get("extra_info") or {}
        result = {
            "ok": True,
            "output_path": str(output_path),
            "voice_id": args.voice_id,
            "model": args.model,
            "format": args.format,
            "bytes": output_path.stat().st_size,
            "trace_id": resp.get("trace_id"),
            "usage_characters": extra_info.get("usage_characters"),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
