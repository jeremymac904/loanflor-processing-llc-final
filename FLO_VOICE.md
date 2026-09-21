# Flo voice

The polish pass reuses Hermes’ existing local-first voice architecture rather than introducing a second voice agent or cloud service.

## Current path

- Microphone input uses the desktop composer voice recorder and local transcription provider path; the installer already provisions the `.[wake,voice]` extras, including faster-whisper when available.
- The transcript enters the normal Flo composer/session path.
- Spoken output uses Hermes’ existing TTS provider registry and playback controls.
- Clicking Stop, using the existing interruption behavior, or beginning a new voice turn stops playback when supported.
- Voice activity is already represented as recording, processing, and speaking UI states; Petdex activity follows the same busy/reasoning/completion signals.

## Ashley controls

Voice is opt-in and never always-listening by default. The existing Settings → Voice surface remains the place for provider, permission, and playback controls. Text remains a complete equivalent for every voice action.

## Verification boundary

No reliable live microphone/TTS latency measurement was claimed on this Mac pass because the release-candidate gateway was offline and no Ashley Windows device was available. Measure recording-to-transcript, Flo response start, and TTS start on the target Windows machine after local voice dependencies are installed.
