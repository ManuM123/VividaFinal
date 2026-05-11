from __future__ import annotations

import re


EXERCISES = {
    "threat": {
        "title": "Validate the Alarm",
        "subtitle": "Meet threat feelings with validation, warmth, and one kinder view.",
        "duration_seconds": 120,
        "breath_pattern": "inhale 4, exhale 6",
        "animation": "softening_sentence",
        "haptics": [45, 70, 45],
        "phases": [
            {
                "label": "Validate",
                "body": "Name the feeling as an understandable threat response, not a failure.",
            },
            {
                "label": "Soften",
                "body": "Use the longer exhale to lower the body alarm by one small degree.",
            },
            {
                "label": "Reframe",
                "body": "Let one alternative thought land with warmth instead of forcing positivity.",
            },
        ],
        "reflection_prompt": "Does the kinder view feel even one percent more helpful?",
        "steps": [
            "Settle your feet and let the phone rest steadily in your hand.",
            "Say inwardly: it makes sense that this feels difficult right now.",
            "Inhale gently for four counts, then exhale for six counts.",
            "On each exhale, loosen the jaw, shoulders, and hands by one small degree.",
            "Offer one warmer alternative: this feeling is a signal, not a prediction.",
            "Let that alternative arrive in the tone of someone kind, steady, and on your side.",
        ],
    },
    "drive": {
        "title": "Compassionate Coach",
        "subtitle": "Turn pressure and self-criticism into a steady next step.",
        "duration_seconds": 100,
        "breath_pattern": "inhale 4, hold 2, exhale 5",
        "animation": "two_voice_shift",
        "haptics": [25, 35, 25, 70, 25],
        "phases": [
            {
                "label": "Concern",
                "body": "Notice the part of you that is pushing, criticising, or trying to prevent failure.",
            },
            {
                "label": "Coach",
                "body": "Answer from wisdom, courage, and warmth using we language.",
            },
            {
                "label": "Next step",
                "body": "Choose one action that helps rather than proves your worth.",
            },
        ],
        "reflection_prompt": "What would a reliable coach say that genuinely has your best interests at heart?",
        "steps": [
            "Notice the energy in your body without needing to spend all of it at once.",
            "Let the concerned or self-critical voice speak one short sentence.",
            "Ask whether that voice is helping you improve or only frightening you.",
            "Shift into a compassionate coach posture: steady spine, soft face, slower breath.",
            "Reply with we language: we can meet this one step at a time.",
            "Choose one concrete next step that makes the situation one percent easier.",
        ],
    },
    "soothing": {
        "title": "Safe Place Heart Focus",
        "subtitle": "Strengthen the soothing system through safe-place imagery and heart focus.",
        "duration_seconds": 120,
        "breath_pattern": "inhale 5, exhale 5",
        "animation": "heart_safe_place",
        "haptics": [20, 55, 20, 55, 20],
        "phases": [
            {
                "label": "Place",
                "body": "Bring to mind a place, memory, or scene where your body can soften.",
            },
            {
                "label": "Image",
                "body": "Invite a compassionate presence with warmth, wisdom, strength, and no judgement.",
            },
            {
                "label": "Heart",
                "body": "Rest attention around the heart area and let the safe feeling become physical.",
            },
        ],
        "reflection_prompt": "Which detail made the safe image feel most real: colour, sound, warmth, or posture?",
        "steps": [
            "Let the breath settle into an even rhythm: five counts in, five counts out.",
            "Bring to mind a safe place, real or imagined, where nothing is demanded of you.",
            "Notice one detail from that place: colour, temperature, sound, or light.",
            "Add a compassionate image or presence that looks at you with warmth and steadiness.",
            "Rest attention around the heart area and breathe as if warmth could gather there.",
            "Close by naming one kind action you can take for yourself next.",
        ],
    },
}


def build_guidance(first_name: str, transcript: str, emotion: str, state: dict) -> dict:
    name = _clean_name(first_name) or "there"
    challenge = _summarise_challenge(transcript)
    state_key = state["key"]
    exercise = EXERCISES[state_key]

    intro = (
        f"Hey {name}. I heard {challenge}. Your voice was classified as {emotion}, "
        f"which Vivida maps to the {state['name'].lower()}."
    )

    if state_key == "threat":
        personalised_line = (
            "The aim is not to argue with the feeling. We will validate the alarm, "
            "settle the body, and let one compassionate alternative feel possible."
        )
    elif state_key == "drive":
        personalised_line = (
            "This energy can be useful, but it does not need a harsh critic to lead it. "
            "We will turn pressure into a compassionate next step."
        )
    else:
        personalised_line = (
            "This is a good moment to strengthen the sense of being supported, so your "
            "soothing system has a safe image and body feeling to rest on."
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
    }


def _clean_name(first_name: str) -> str:
    return re.sub(r"[^A-Za-z'-]", "", first_name or "").strip()[:40]


def _summarise_challenge(transcript: str) -> str:
    cleaned = re.sub(r"\s+", " ", (transcript or "").strip())
    if not cleaned:
        return "that something is on your mind"
    if len(cleaned) > 170:
        cleaned = cleaned[:167].rsplit(" ", 1)[0] + "..."
    return f"that you are facing this: {cleaned}"
