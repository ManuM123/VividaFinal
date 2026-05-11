import os
import time
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")
os.environ.setdefault("NUMBA_CACHE_DIR", "/private/tmp/numba")

import keras
import numpy as np

from ml_engine.src.preprocessing import AudioPreprocessor


EMOTIONS = [
    "neutral",
    "calm",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprised",
]

EMOTION_TO_STATE = {
    "angry": "threat",
    "fearful": "threat",
    "surprised": "threat",
    "happy": "drive",
    "calm": "soothing",
    "neutral": "soothing",
    "sad": "soothing",
    "disgust": "threat",
}

STATE_COPY = {
    "threat": {
        "name": "Threat system",
        "colour": "red",
        "summary": "Your voice suggests a high-alert fight, flight, or freeze pattern.",
    },
    "drive": {
        "name": "Drive system",
        "colour": "blue",
        "summary": "Your voice suggests active goal pursuit and mobilised energy.",
    },
    "soothing": {
        "name": "Soothing system",
        "colour": "green",
        "summary": "Your voice suggests a lower-arousal regulated or reflective pattern.",
    },
}


class ModelUnavailableError(RuntimeError):
    pass


class VividaInferenceEngine:
    def __init__(self, model_path: str | None = None):
        self.preprocessor = AudioPreprocessor()
        self.model_path = self._resolve_model_path(model_path)
        self.model = self._load_model(self.model_path)

    def predict(self, audio_path: Path) -> dict:
        if self.model is None:
            raise ModelUnavailableError(
                "Vivida SER model is not available. Train and save "
                "ml_engine/results/cnn_lstm_best.keras, or set VIVIDA_MODEL_PATH."
            )

        start = time.perf_counter()
        features = self.preprocessor.process_file(str(audio_path)).astype(np.float32)
        model_result = self._predict_with_model(features)

        emotion = model_result["emotion"]
        state_key = EMOTION_TO_STATE.get(emotion, "soothing")
        latency_ms = (time.perf_counter() - start) * 1000

        return {
            **model_result,
            "state": {
                "key": state_key,
                **STATE_COPY[state_key],
            },
            "latency_ms": round(latency_ms, 2),
            "model_path": str(self.model_path) if self.model_path else None,
            "model_available": self.model is not None,
        }

    def _resolve_model_path(self, explicit_path: str | None) -> Path | None:
        requested_path = explicit_path or os.getenv("VIVIDA_MODEL_PATH")
        if requested_path:
            path = Path(requested_path)
            return path if path.exists() else None

        candidates = [
            Path("ml_engine/results/cnn_lstm_best.keras"),
            Path("ml_engine/results/mlp_best.keras"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _load_model(self, model_path: Path | None):
        if model_path is None:
            return None
        try:
            return keras.models.load_model(model_path, safe_mode=False)
        except Exception as exc:
            print(f"Vivida warning: could not load model {model_path}: {exc}")
            return None

    def _predict_with_model(self, features: np.ndarray) -> dict | None:
        if self.model is None:
            return None

        x = self._normalise_feature_blocks(features[np.newaxis, ...])
        if "mlp" not in str(self.model_path).lower():
            x = x[..., np.newaxis]

        started = time.perf_counter()
        probabilities = self.model.predict(x, verbose=0)[0]
        model_latency = (time.perf_counter() - started) * 1000
        index = int(np.argmax(probabilities))

        return {
            "emotion": EMOTIONS[index],
            "confidence": round(float(probabilities[index]), 4),
            "probabilities": {
                emotion: round(float(probabilities[i]), 4)
                for i, emotion in enumerate(EMOTIONS)
            },
            "classifier": self._classifier_name(),
            "model_latency_ms": round(model_latency, 2),
        }

    def _classifier_name(self) -> str:
        if not self.model_path:
            return "keras_ser_model"
        name = self.model_path.name.lower()
        if "cnn_lstm" in name:
            return "cnn_lstm_keras"
        if "mlp" in name:
            return "mlp_keras"
        return "keras_ser_model"

    def _normalise_feature_blocks(self, x_arr: np.ndarray) -> np.ndarray:
        mel = x_arr[:, :128, :]
        engineered = x_arr[:, 128:, :]
        mel = (mel - np.min(mel)) / (np.max(mel) - np.min(mel) + 1e-8)
        engineered = (engineered - np.min(engineered)) / (
            np.max(engineered) - np.min(engineered) + 1e-8
        )
        x_arr[:, :128, :] = mel
        x_arr[:, 128:, :] = engineered
        return x_arr
