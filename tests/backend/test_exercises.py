from vivida_app.backend.exercises import EXERCISES, build_guidance


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
    assert EXERCISES["threat"]["title"] == "Validate the Alarm"
    assert EXERCISES["drive"]["title"] == "Compassionate Coach"
    assert EXERCISES["soothing"]["title"] == "Safe Place Heart Focus"
    assert EXERCISES["threat"]["animation"] == "softening_sentence"
    assert EXERCISES["drive"]["animation"] == "two_voice_shift"
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
    assert "Threat system".lower() in guidance["intro"].lower()
    assert guidance["voice_script"].endswith(
        "Take the next small step from the steadier place you just practised."
    )
    assert "validate the alarm" in guidance["voice_script"].lower()


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
