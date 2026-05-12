import asyncio

from backend.exercises import EXERCISES, build_guidance, personalise_guidance


def test_each_state_has_structured_exercise_metadata():
    for state_key in ("threat", "drive", "soothing"):
        exercise = EXERCISES[state_key]

        assert exercise["title"]
        assert exercise["subtitle"]
        assert exercise["duration_seconds"] >= 75
        assert exercise["breath_pattern"]
        assert exercise["animation"]
        assert len(exercise["phases"]) == 3
        assert exercise["reflection_prompt"]
        assert len(exercise["steps"]) >= 5


def test_exercises_use_compassionate_mind_tracks():
    assert EXERCISES["threat"]["title"] == "Two Chairs: Meet the Alarm"
    assert EXERCISES["drive"]["title"] == "Kindness Into Action"
    assert EXERCISES["soothing"]["title"] == "Find Your Soothing Rhythm"
    assert EXERCISES["threat"]["animation"] == "two_chairs_dialogue"
    assert EXERCISES["drive"]["animation"] == "kindness_to_action"
    assert EXERCISES["soothing"]["animation"] == "heart_safe_place"


def test_guidance_personalises_name_and_transcript():
    guidance = build_guidance(
        first_name="Manu!",
        transcript="I have a guitar performance in front of 200 people.",
        emotion="fearful",
        state={"key": "threat", "name": "Threat system"},
    )

    assert "Hey Manu" in guidance["intro"]
    assert "guitar performance" in guidance["intro"]
    assert "classified" not in guidance["intro"].lower()
    assert "threat system" not in guidance["intro"].lower()
    assert guidance["voice_script"].endswith(
        "Take the next small step from the steadier place you just practised."
    )
    assert "two chairs" in guidance["voice_script"].lower()
    assert "compassion chair" in guidance["voice_script"].lower()


def test_empty_transcript_still_generates_safe_guidance():
    guidance = build_guidance(
        first_name="",
        transcript="",
        emotion="calm",
        state={"key": "soothing", "name": "Soothing system"},
    )

    assert "Hey there" in guidance["intro"]
    assert "something is on your mind" in guidance["intro"]
    assert guidance["animation"] == "heart_safe_place"
    assert "wandering" in " ".join(guidance["steps"]).lower()


def test_drive_uses_compassionate_memory_to_support_action():
    guidance = build_guidance(
        first_name="Manu",
        transcript="I want to do well in my guitar performance.",
        emotion="happy",
        state={"key": "drive", "name": "Drive system"},
    )

    assert guidance["title"] == "Kindness Into Action"
    assert "guitar performance" in guidance["intro"]
    assert "encouraged" in " ".join(guidance["steps"]).lower()
    assert "next step" in guidance["voice_script"].lower()


def test_personalisation_is_static_without_provider(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    guidance = build_guidance(
        first_name="Manu",
        transcript="I am nervous about my guitar performance.",
        emotion="calm",
        state={"key": "soothing", "name": "Soothing system"},
    )

    personalised = asyncio.run(
        personalise_guidance(
            first_name="Manu",
            transcript="I am nervous about my guitar performance.",
            emotion="calm",
            state={"key": "soothing", "name": "Soothing system"},
            guidance=guidance,
        )
    )

    assert personalised["personalisation_source"] == "static"
    assert personalised["title"] == "Find Your Soothing Rhythm"
