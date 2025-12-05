# VortexAI Portable Assistant

Minimal assistant pipeline for local devices. Default harness uses the keyboard as a stand-in for wake word, recording, STT, and TTS so you can iterate without audio hardware; audio mode adds wake + mic + Whisper + Piper.

## Architecture
- **Wake** → **Record** → **STT** → **Chat** → **TTS**.
- Components are wired with dependency injection so you can swap in real wake word, VAD, Whisper STT, Piper TTS, etc., without touching the orchestrator.
- Chat requests are sent to the Vortex `/chat` endpoint; responses are validated before being spoken.

## Running (console mode)
```bash
# Ensure Python 3.10+
python -m vortex_portable
# or
python main.py
```
Type the wake word when prompted (default: `hey vortex`), enter your utterance, and the assistant will print the reply.

## Running (audio mode: wake word + mic + Whisper + Piper)
1) Install deps:
   ```bash
   pip install -r requirements.txt
   ```
2) Ensure `.env` points to your Piper model/binary and (optionally) wake model, and sets `VORTEX_MODE=audio`.
3) Run:
   ```bash
   python -m vortex_portable
   # or
   python main.py
   ```
   The agent listens for the wake word via microphone, records your speech, transcribes with Whisper, hits `/chat`, and speaks the reply with Piper.

### Configuration
Environment variables (all optional):
- `VORTEX_API_BASE_URL` (default: `http://localhost:8000`)
- `VORTEX_API_KEY` (optional bearer token)
- `VORTEX_REQUEST_TIMEOUT` (seconds, default: `10`)
- `VORTEX_SYSTEM_PROMPT` (seed system message)
- `VORTEX_WAKE_WORD` (default: `hey vortex`)
- `VORTEX_LANGUAGE` (language hint for STT)
- `VORTEX_CONVERSATION_ID` (conversation id to reuse; default is a random UUID each run)
- `VORTEX_DEBUG` (`true`/`1` to send `debug: true` with chat requests)
- `VORTEX_MODE` (`console` default, or `audio` to enable mic + TTS)
- `VORTEX_WHISPER_MODEL` (Whisper model size, default `tiny`)
- `VORTEX_WHISPER_DEVICE` (e.g., `cpu` or `cuda`)
- `VORTEX_RECORD_SECONDS` (seconds per utterance when recording audio, default `5`)
- `VORTEX_PIPER_MODEL` (path to Piper `.onnx` model, required for `audio` mode)
- `VORTEX_PIPER_BINARY` (Piper binary name/path, default `piper`)
- `VORTEX_PIPER_SPEAKER` (optional speaker id/name for Piper)
- `VORTEX_WAKE_MODEL` (optional openWakeWord model path; defaults to built-ins)

## Assumptions about `/chat` API shape
- Request body: `{"message": "<user text>", "conversation_id": "<id>", "debug": <bool>}`.
- Accepted response shapes (first match wins):
  1. `{"data": {"response": "<text>", "conversation_id": "<id>"}}`
  2. `{"reply": "<text>"}`
  3. `{"message": {"role": "assistant", "content": "<text>"}}`
  4. `{"choices": [{"message": {"role": "assistant", "content": "<text>"}}]}`
- The client raises an error if none of the shapes are present or if JSON/headers are invalid.

If your backend differs, adjust `vortex_portable/services/chat_client.py` accordingly.

## Audio mode (mic + wake word + Whisper + Piper)
1) Install deps:
   ```bash
   pip install -r requirements.txt
   ```
2) Provide a Piper model and binary (set `VORTEX_PIPER_MODEL` and optionally `VORTEX_PIPER_BINARY`/`VORTEX_PIPER_SPEAKER`).
3) Optional: set a custom openWakeWord model via `VORTEX_WAKE_MODEL`; otherwise defaults load.
4) Run:
   ```bash
   VORTEX_MODE=audio python -m vortex_portable
   # or override via CLI
   python -m vortex_portable --mode audio
   ```
5) Speak after the wake word is detected; Whisper transcribes; Piper plays the reply through your default audio device.

## Extending
- Swap implementations in `vortex_portable/cli.py:build_assistant` for custom wake/STT/TTS or hardware-specific recorders.
- For offline audio, implement a new `SpeechToText` that consumes `CapturedAudio.data` and sets `transcript_hint` to `None`.
- To add streaming or retries, extend `HttpChatClient` with backoff or SSE handling.

## Development notes
- Core console mode uses only the standard library; audio mode requires deps in `requirements.txt`.
- Code is organized into small, testable modules under `vortex_portable/`.
