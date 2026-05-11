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
