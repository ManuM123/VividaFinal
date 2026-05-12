from fastapi.testclient import TestClient

from backend import main


class FakeEngine:
    model = object()
    model_path = "tests/fake_cnn_lstm_best.keras"

    def _classifier_name(self):
        return "cnn_lstm_keras"

    def predict(self, audio_path):
        assert audio_path.exists()
        return {
            "emotion": "fearful",
            "confidence": 0.73,
            "probabilities": {"fearful": 0.73},
            "classifier": "cnn_lstm_keras",
            "model_latency_ms": 12.4,
            "state": {
                "key": "threat",
                "name": "Threat system",
                "colour": "red",
                "summary": "Test state summary.",
            },
            "latency_ms": 42.0,
            "model_path": "tests/fake_cnn_lstm_best.keras",
            "model_available": True,
        }


def test_health_reports_loaded_model(monkeypatch):
    monkeypatch.setattr(main, "engine", FakeEngine())
    client = TestClient(main.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["model_available"] is True
    assert response.json()["classifier"] == "cnn_lstm_keras"


def test_analyse_deletes_audio_and_returns_guidance(monkeypatch):
    monkeypatch.setattr(main, "engine", FakeEngine())
    client = TestClient(main.app)

    response = client.post(
        "/api/analyse",
        data={
            "session_id": "test-user",
            "first_name": "Manu",
            "transcript": "I am nervous about my guitar performance.",
        },
        files={"audio": ("voice.wav", b"RIFFtest-audio", "audio/wav")},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["prediction"]["classifier"] == "cnn_lstm_keras"
    assert body["prediction"]["state"]["key"] == "threat"
    assert body["audio_deleted"] is True
    assert "guitar performance" in body["guidance"]["intro"]


def test_tts_returns_wav_without_storing_audio(monkeypatch):
    async def fake_tts(text):
        assert "steady breath" in text
        return b"RIFFfake-wav"

    monkeypatch.setattr(main, "synthesize_guidance_audio", fake_tts)
    monkeypatch.setattr(main, "_tts_rate_bucket", {})
    client = TestClient(main.app)

    response = client.post("/api/tts", json={"text": "steady breath"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == b"RIFFfake-wav"


def test_tts_rejects_overlong_text(monkeypatch):
    monkeypatch.setattr(main, "_tts_rate_bucket", {})
    client = TestClient(main.app)

    response = client.post("/api/tts", json={"text": "x" * (main.TTS_MAX_TEXT_CHARS + 1)})

    assert response.status_code == 413


def test_tts_rate_limits_per_client(monkeypatch):
    async def fake_tts(text):
        return b"RIFFfake-wav"

    monkeypatch.setattr(main, "synthesize_guidance_audio", fake_tts)
    monkeypatch.setattr(main, "TTS_RATE_LIMIT", 1)
    monkeypatch.setattr(main, "_tts_rate_bucket", {})
    client = TestClient(main.app)

    first = client.post("/api/tts", json={"text": "steady breath"})
    second = client.post("/api/tts", json={"text": "steady breath"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_notification_config_reports_vapid_key(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-public-key")
    client = TestClient(main.app)

    response = client.get("/api/notifications/config")

    assert response.status_code == 200
    assert response.json() == {"supported": True, "publicKey": "test-public-key"}


def test_notification_subscribe_stores_subscription(monkeypatch):
    captured = {}

    async def fake_user(request):
        return {"id": "user-123"}

    async def fake_supabase_request(
        method,
        path,
        *,
        body=None,
        prefer=None,
        access_token=None,
    ):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        captured["prefer"] = prefer
        captured["access_token"] = access_token
        return {}

    monkeypatch.setattr(main, "_require_supabase_user", fake_user)
    monkeypatch.setattr(main, "_supabase_request", fake_supabase_request)
    client = TestClient(main.app)

    response = client.post(
        "/api/notifications/subscribe",
        headers={"Authorization": "Bearer test-token"},
        json={
            "subscription": {
                "endpoint": "https://push.example/sub",
                "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
            },
            "reminder_hour_utc": 18,
            "user_agent": "pytest",
        },
    )

    assert response.status_code == 200
    assert captured["method"] == "POST"
    assert "push_subscriptions" in captured["path"]
    assert captured["body"]["user_id"] == "user-123"
    assert captured["body"]["enabled"] is True
    assert captured["body"]["motivation_enabled"] is True
    assert captured["access_token"] == "test-token"
    assert 9 <= captured["body"]["motivation_hour_utc"] <= 20


def test_motivational_message_uses_first_name():
    message = main._motivational_message("Manu!")

    assert message == (
        "In case you forgot Manu, you are absolutely capable of creating "
        "the version of you that you can't stop thinking about."
    )
