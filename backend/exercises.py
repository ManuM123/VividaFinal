from __future__ import annotations

import base64
import io
import json
import os
import re
import time
import wave
from copy import deepcopy
from dataclasses import dataclass

import httpx


GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_TEXT_MODEL = "gemini-2.5-flash-lite"
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_TTS_VOICE = "Vindemiatrix"
GEMINI_PCM_RATE = 24000
GEMINI_PCM_CHANNELS = 1
GEMINI_PCM_SAMPLE_WIDTH = 2
GEMINI_TTS_MAX_CHARS = 1800
GEMINI_TTS_RETRIES = 2

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_TTS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_TTS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
ELEVENLABS_TTS_RETRIES = 2


@dataclass(frozen=True)
class SynthesizedAudio:
    content: bytes
    media_type: str
    provider: str


EXERCISES = {
    "threat": {
        "title": "Two Chairs: Meet the Alarm",
        "subtitle": "Let the worried part speak, then answer it from a steadier compassionate chair.",
        "duration_seconds": 120,
        "breath_pattern": "inhale 4, exhale 6 between chairs",
        "animation": "two_chairs_dialogue",
        "haptics": [45, 70, 45, 110],
        "phases": [
            {
                "label": "Alarm chair",
                "body": "Give the anxious or protective part one clear sentence, without judging it.",
            },
            {
                "label": "Compassion chair",
                "body": "Shift posture, soften the face, and answer with warmth, courage, and steadiness.",
            },
            {
                "label": "Bridge",
                "body": "Let both sides be heard, then choose one small action that protects and supports you.",
            },
        ],
        "reflection_prompt": "What did the compassionate chair understand that the alarm chair could not see yet?",
        "steps": [
            "Place two imaginary chairs in front of you: one for the alarm, one for compassion.",
            "In the alarm chair, let the worried or protective part say one short sentence.",
            "Take one slower breath and move attention into the compassion chair.",
            "From this chair, answer the alarm as someone warm, wise, and firmly on your side.",
            "Use we language if it helps: we can take this seriously without being ruled by it.",
            "Close by choosing one kind, practical step that helps you feel a little safer.",
        ],
        "llm_frame": (
            "Compassion Focused Therapy inspired two-chair dialogue: the anxious, "
            "angry, ashamed, or protective part is allowed to speak briefly; the "
            "compassionate self then responds with warmth, validation, courage, "
            "and one practical next step. The aim is not to silence alarm, but to "
            "balance it with the soothing system."
        ),
        "prompt_rules": [
            "Do not use the phrase threat system in user-facing guidance.",
            "Do not mention the classifier or detected emotion.",
            "Write one short sentence from the alarm chair.",
            "Write a warm response from the compassion chair.",
            "Validate the worry without agreeing with catastrophic predictions.",
            "End with one concrete next step that fits the user's situation.",
        ],
    },
    "drive": {
        "title": "Kindness Into Action",
        "subtitle": "Use a memory of encouragement to turn striving into one supported next step.",
        "duration_seconds": 120,
        "breath_pattern": "steady breath while recalling encouragement",
        "animation": "kindness_to_action",
        "haptics": [25, 35, 25, 35, 90],
        "phases": [
            {
                "label": "Memory",
                "body": "Recall a moment when someone was kind, warm, encouraging, or supportive toward you.",
            },
            {
                "label": "Feeling",
                "body": "Notice the details: face, voice, tone, posture, and how receiving kindness lands in the body.",
            },
            {
                "label": "Action",
                "body": "Carry that supported feeling into one goal-directed step that helps without harshness.",
            },
        ],
        "reflection_prompt": "What changes when the next step comes from encouragement rather than pressure?",
        "steps": [
            "Sit comfortably and let your breathing become steady enough to pay attention.",
            "Bring to mind a time someone encouraged you with warmth, patience, or belief in you.",
            "Notice one detail of that memory: their face, their voice, their posture, or the atmosphere.",
            "Let the feeling of receiving kindness become something you can sense in your body.",
            "Now bring your current goal to mind while keeping a little of that support with you.",
            "Choose one useful next step that serves the goal without needing to prove your worth.",
        ],
        "llm_frame": (
            "Compassion Focused Therapy inspired compassionate memory imagery: "
            "recall receiving kindness, warmth, encouragement, or support; attend "
            "to sensory details and the felt sense of receiving kindness; then "
            "carry that compassionate feeling into a current goal as one supported, "
            "sustainable next action."
        ),
        "prompt_rules": [
            "Do not tell the user to simply relax or stop caring.",
            "Acknowledge motivation, pressure, or wanting to do well in ordinary language.",
            "Invite a memory of encouragement without forcing a clear image.",
            "Include sensory detail: face, voice, posture, tone, atmosphere, or body feeling.",
            "Turn the remembered support into one concrete action for the user's goal.",
            "Avoid making achievement sound like proof of worth.",
        ],
    },
    "soothing": {
        "title": "Find Your Soothing Rhythm",
        "subtitle": "Use mindful breathing to settle attention, notice wandering thoughts, and return kindly.",
        "duration_seconds": 120,
        "breath_pattern": "natural inhale, slow unforced exhale",
        "animation": "heart_safe_place",
        "haptics": [20, 55, 20, 55, 20],
        "phases": [
            {
                "label": "Settle",
                "body": "Sit in a supported posture and let the breath be noticed rather than controlled.",
            },
            {
                "label": "Rhythm",
                "body": "Allow the breath to find a comfortable pace that suits your body right now.",
            },
            {
                "label": "Return",
                "body": "When the mind wanders, notice it without judgement and gently come back to breathing.",
            },
        ],
        "reflection_prompt": "What helped most when your mind wandered: noticing, softening, or returning to the breath?",
        "steps": [
            "Place both feet on the floor and let your hands rest somewhere comfortable.",
            "Notice the breath entering and leaving through your nose or mouth.",
            "Let the breath move down into the body as far as feels natural, without forcing it.",
            "Allow the out-breath to be a little slower if that feels comfortable.",
            "When thoughts pull you away, silently name that as wandering and return to the next breath.",
            "Close by choosing one small kind action that matches this steadier rhythm.",
        ],
        "llm_frame": (
            "Compassion Focused Therapy inspired mindful breathing: settle the "
            "body, notice the breath, find a natural soothing rhythm, notice "
            "mind wandering without judgement, then gently return."
        ),
    },
}


def build_guidance(first_name: str, transcript: str, emotion: str, state: dict) -> dict:
    name = _clean_name(first_name) or "there"
    challenge = _summarise_situation(transcript)
    state_key = state["key"]
    exercise = deepcopy(EXERCISES[state_key])

    if state_key == "threat":
        intro = (
            f"Hey {name}. It sounds like {challenge} is weighing on your mind. "
            "Let's give the worried part a little space, then answer it from a steadier chair."
        )
        personalised_line = (
            "The aim is not to argue with the alarm or push it away. We will let it speak, "
            "then bring in a compassionate response that is warm, honest, and practical."
        )
    elif state_key == "drive":
        intro = (
            f"Hey {name}. It sounds like {challenge} is bringing pressure and momentum. "
            "Let's slow that drive down enough to make it useful."
        )
        personalised_line = (
            "This energy can be useful, but it does not need a harsh critic to lead it. "
            "We will turn pressure into a compassionate next step."
        )
    else:
        intro = (
            f"Hey {name}. It sounds like {challenge} is present for you today. "
            "Let's settle into a rhythm your body does not have to force."
        )
        personalised_line = (
            "This is a good moment to train the gentle skill of noticing and returning. "
            "We will find a breathing rhythm that feels natural rather than forced."
        )

    closing = (
        f"{name}, you do not need to solve the whole situation in this minute. "
        "Take the next small step from the steadier place you just practised."
    )
    exercise_heading = f"We will use {exercise['title']}."
    voice_script = " ".join(
        [intro, exercise_heading, personalised_line, *exercise["steps"], closing]
    )
    return {
        **exercise,
        "intro": intro,
        "personalised_line": personalised_line,
        "voice_script": voice_script,
        "personalisation_source": "static",
    }


async def personalise_guidance(
    *,
    first_name: str,
    transcript: str,
    emotion: str,
    state: dict,
    guidance: dict,
) -> dict:
    """Optionally replace static text with LLM-personalised guidance.

    The transcript is sent only to the configured LLM provider for this request.
    It is not logged or written to disk by this module, and failed/disabled LLM
    calls fall back to the static exercise.
    """

    if os.getenv("VIVIDA_AI_GUIDANCE", "1").strip().lower() in ("0", "off", "false"):
        return guidance

    if not os.getenv("GEMINI_API_KEY"):
        return guidance

    try:
        generated = await _call_gemini_text(
            prompt=_build_personalisation_prompt(
                first_name=first_name,
                transcript=transcript,
                emotion=emotion,
                state=state,
                guidance=guidance,
            ),
        )
        return _merge_personalised_guidance(guidance, generated)
    except Exception as exc:
        fallback = dict(guidance)
        fallback["personalisation_source"] = "static_fallback"
        fallback["personalisation_error"] = exc.__class__.__name__
        return fallback


async def synthesize_guidance_audio(text: str) -> SynthesizedAudio:
    script = _clean_generated_text(text, max_length=GEMINI_TTS_MAX_CHARS)
    if not script:
        raise ValueError("No guidance text supplied")

    provider = tts_provider_name()
    if provider == "elevenlabs":
        return await _synthesize_elevenlabs_audio(script)
    if provider == "gemini":
        return await _synthesize_gemini_audio(script)
    raise ValueError("No TTS provider is configured")


def tts_provider_name() -> str:
    configured = os.getenv("VIVIDA_TTS_PROVIDER", "").strip().lower()
    if configured in {"elevenlabs", "gemini"}:
        return configured
    if os.getenv("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "browser_fallback"


async def _synthesize_elevenlabs_audio(script: str) -> SynthesizedAudio:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is not set")

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", ELEVENLABS_TTS_VOICE_ID)
    model = os.getenv("ELEVENLABS_TTS_MODEL", ELEVENLABS_TTS_MODEL)
    output_format = os.getenv("ELEVENLABS_OUTPUT_FORMAT", ELEVENLABS_OUTPUT_FORMAT)
    payload = {
        "text": script,
        "model_id": model,
        "voice_settings": {
            "stability": float(os.getenv("ELEVENLABS_STABILITY", "0.55")),
            "similarity_boost": float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75")),
            "style": float(os.getenv("ELEVENLABS_STYLE", "0.1")),
            "use_speaker_boost": os.getenv("ELEVENLABS_SPEAKER_BOOST", "1")
            .strip()
            .lower()
            not in {"0", "false", "off"},
        },
    }

    audio = await _post_elevenlabs_tts_with_retry(
        api_key=api_key,
        voice_id=voice_id,
        output_format=output_format,
        payload=payload,
    )
    return SynthesizedAudio(
        content=audio,
        media_type=_media_type_for_elevenlabs_format(output_format),
        provider="elevenlabs",
    )


async def _synthesize_gemini_audio(script: str) -> SynthesizedAudio:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    voice_name = os.getenv("VIVIDA_GEMINI_TTS_VOICE", GEMINI_TTS_VOICE)
    model = os.getenv("VIVIDA_GEMINI_TTS_MODEL", GEMINI_TTS_MODEL)
    tts_prompt = (
        "# AUDIO PROFILE: Vivida Guide\n"
        "A warm, gentle wellbeing guide. Calm, grounded, and mature. "
        "The voice should feel quietly supportive, never clinical or performative.\n\n"
        "## THE SCENE: A Quiet Check-In\n"
        "The listener is taking a private pause after sharing something personal. "
        "The room is quiet. The guide speaks close to the microphone with no rush.\n\n"
        "### DIRECTOR'S NOTES\n"
        "SYNTHESIZE SPEECH ONLY. Do not read these instructions aloud.\n"
        "Style: soft, compassionate, steady, and reassuring.\n"
        "Pacing: slow enough for breathing practice, with natural pauses after short sentences.\n"
        "Articulation: clear British English, low intensity, no dramatic emphasis.\n"
        "Voice match: use the selected voice naturally; do not force a mismatched character.\n\n"
        "#### TRANSCRIPT\n"
        "[softly, slowly]\n"
        "SPOKEN TRANSCRIPT BEGINS:\n"
        f"{script}\n"
        "SPOKEN TRANSCRIPT ENDS."
    )
    payload = {
        "contents": [{"parts": [{"text": tts_prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name,
                    }
                }
            },
        },
        "model": model,
    }

    response_data = await _post_gemini_tts_with_retry(
        api_key=api_key,
        model=model,
        payload=payload,
    )
    inline_data = _extract_inline_audio(response_data)
    audio_bytes = base64.b64decode(inline_data["data"])
    mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or ""
    if "wav" in mime_type:
        return SynthesizedAudio(
            content=audio_bytes,
            media_type="audio/wav",
            provider="gemini",
        )
    return SynthesizedAudio(
        content=_pcm_to_wav(audio_bytes),
        media_type="audio/wav",
        provider="gemini",
    )


def _clean_name(first_name: str) -> str:
    return re.sub(r"[^A-Za-z'-]", "", first_name or "").strip()[:40]


def _summarise_situation(transcript: str) -> str:
    cleaned = re.sub(r"\s+", " ", (transcript or "").strip())
    if not cleaned:
        return "something is on your mind"
    if len(cleaned) > 170:
        cleaned = cleaned[:167].rsplit(" ", 1)[0] + "..."
    return f"this situation is on your mind: {cleaned}"


def _build_personalisation_prompt(
    *,
    first_name: str,
    transcript: str,
    emotion: str,
    state: dict,
    guidance: dict,
) -> str:
    name = _clean_name(first_name) or "there"
    transcript_excerpt = re.sub(r"\s+", " ", (transcript or "").strip())[:700]
    exercise_context = {
        "title": guidance["title"],
        "subtitle": guidance.get("subtitle", ""),
        "therapeutic_frame": guidance.get("llm_frame", ""),
        "state_key": state.get("key", ""),
        "fixed_phases": guidance.get("phases", []),
        "fallback_steps": guidance.get("steps", []),
        "prompt_rules": guidance.get("prompt_rules", []),
    }

    return f"""
You write short spoken guidance for Vivida, a student wellbeing app.

Task:
- Personalise the existing exercise to the user's situation.
- Keep the therapeutic structure fixed; do not invent diagnosis, therapy, or medical claims.
- Do not say you are an AI.
- Use gentle British English.
- Keep the voice script calm, concrete, and suitable for text-to-speech.
- Do not mention machine learning, classifiers, detected emotions, or system labels.
- If the transcript is empty or unclear, stay general.
- Avoid copying any copyrighted source text.
- Mention the user's situation only at a high level; do not add extra sensitive details.
- Include one tiny compassionate next step that fits the user's situation.
- For a two-chair exercise, clearly move from the alarm chair to the compassion chair, then bridge them.

User:
Name: {name}
Internal routing emotion: {emotion}
Internal routing state: {state.get("name", state.get("key", ""))}
Transcript: {transcript_excerpt or "[empty]"}

Exercise scaffold:
{json.dumps(exercise_context, ensure_ascii=True)}

Return only valid JSON with this exact shape:
{{
  "intro": "1-2 sentences, starts with Hey {name}.",
  "personalised_line": "1-2 sentences explaining why this exercise fits.",
  "steps": ["5 or 6 short spoken steps"],
  "reflection_prompt": "one short reflective question",
  "voice_script": "a complete 80-130 second spoken script using the intro, personalised line, steps, and tiny next step"
}}
""".strip()


async def _call_gemini_text(prompt: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    model = os.getenv("VIVIDA_GEMINI_TEXT_MODEL", GEMINI_TEXT_MODEL)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": int(os.getenv("VIVIDA_GEMINI_MAX_TOKENS", "700")),
            "responseMimeType": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(
            f"{GEMINI_GENERATE_URL}/{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
    data = response.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return _parse_json_text("".join(part.get("text", "") for part in parts))


async def _post_gemini_tts_with_retry(
    *,
    api_key: str,
    model: str,
    payload: dict,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(GEMINI_TTS_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GEMINI_GENERATE_URL}/{model}:generateContent",
                    headers={
                        "x-goog-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
            _extract_inline_audio(data)
            return data
        except Exception as exc:
            last_error = exc
            if not _should_retry_tts(exc, attempt):
                break
            time.sleep(0.25 * (attempt + 1))

    raise last_error or ValueError("Gemini TTS request failed")


async def _post_elevenlabs_tts_with_retry(
    *,
    api_key: str,
    voice_id: str,
    output_format: str,
    payload: dict,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(ELEVENLABS_TTS_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    f"{ELEVENLABS_TTS_URL}/{voice_id}",
                    params={"output_format": output_format},
                    headers={
                        "xi-api-key": api_key,
                        "Content-Type": "application/json",
                        "Accept": _media_type_for_elevenlabs_format(output_format),
                    },
                    json=payload,
                )
            response.raise_for_status()
            if not response.content:
                raise ValueError("ElevenLabs TTS returned empty audio")
            return response.content
        except Exception as exc:
            last_error = exc
            if not _should_retry_elevenlabs_tts(exc, attempt):
                break
            time.sleep(0.25 * (attempt + 1))

    raise last_error or ValueError("ElevenLabs TTS request failed")


def _should_retry_tts(exc: Exception, attempt: int) -> bool:
    if attempt >= GEMINI_TTS_RETRIES:
        return False
    if isinstance(exc, ValueError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


def _should_retry_elevenlabs_tts(exc: Exception, attempt: int) -> bool:
    if attempt >= ELEVENLABS_TTS_RETRIES:
        return False
    if isinstance(exc, ValueError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


def _media_type_for_elevenlabs_format(output_format: str) -> str:
    if output_format.startswith("mp3"):
        return "audio/mpeg"
    if output_format.startswith("wav"):
        return "audio/wav"
    if output_format.startswith("pcm"):
        return "audio/L16"
    if output_format.startswith("ulaw"):
        return "audio/basic"
    return "application/octet-stream"


def _parse_json_text(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.S).strip()
    return json.loads(cleaned)


def _merge_personalised_guidance(base: dict, generated: dict) -> dict:
    merged = dict(base)

    for key, max_length in {
        "intro": 420,
        "personalised_line": 420,
        "reflection_prompt": 220,
        "voice_script": 2200,
    }.items():
        value = _clean_generated_text(generated.get(key), max_length=max_length)
        if value:
            merged[key] = value

    steps = generated.get("steps")
    if isinstance(steps, list):
        clean_steps = [
            _clean_generated_text(step, max_length=220)
            for step in steps
            if _clean_generated_text(step, max_length=220)
        ]
        if 5 <= len(clean_steps) <= 6:
            merged["steps"] = clean_steps

    merged["personalisation_source"] = "gemini"
    return merged


def _clean_generated_text(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:max_length].rsplit(" ", 1)[0] if len(cleaned) > max_length else cleaned


def _extract_inline_audio(data: dict) -> dict:
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline_data = part.get("inlineData") or part.get("inline_data")
            if inline_data and inline_data.get("data"):
                return inline_data
    raise ValueError("Gemini TTS response did not include audio data")


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(GEMINI_PCM_CHANNELS)
        wav_file.setsampwidth(GEMINI_PCM_SAMPLE_WIDTH)
        wav_file.setframerate(GEMINI_PCM_RATE)
        wav_file.writeframes(pcm_bytes)
    return output.getvalue()
