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

    def debug_audio(
        self,
        audio_path: Path,
        output_dir: Path | None = None,
        analysis_id: str | None = None,
    ) -> dict:
        raw_audio, raw_sr = self.preprocessor.load_audio(str(audio_path))
        filtered_audio = self.preprocessor.apply_band_pass_filter(raw_audio)
        standardised_audio = self.preprocessor.standardise_audio_length(filtered_audio)
        normalised_audio = self.preprocessor.peak_normalisation(standardised_audio)
        features = self.preprocessor.extract_hybrid_features(normalised_audio).astype(np.float32)
        normalised_features = self._normalise_feature_blocks(features[np.newaxis, ...].copy())
        if "mlp" not in str(self.model_path).lower():
            model_input = normalised_features[..., np.newaxis]
        else:
            model_input = normalised_features

        debug_outputs = {}
        if output_dir and analysis_id:
            debug_outputs = self._write_debug_feature_files(
                output_dir=output_dir,
                analysis_id=analysis_id,
                features=features,
                model_input=model_input,
            )

        return {
            "input_file": str(audio_path),
            "raw_audio": self._audio_stats(raw_audio, raw_sr),
            "filtered_audio": self._audio_stats(filtered_audio, self.preprocessor.sample_rate),
            "standardised_audio": self._audio_stats(standardised_audio, self.preprocessor.sample_rate),
            "normalised_audio": self._audio_stats(normalised_audio, self.preprocessor.sample_rate),
            "features": self._array_stats(features),
            "log_mel_spectrogram": self._array_stats(features[:128, :]),
            "mfccs": self._array_stats(features[128:168, :]),
            "chroma": self._array_stats(features[168:, :]),
            "normalised_features": self._array_stats(normalised_features),
            "model_input": self._array_stats(model_input),
            "acoustic_profile": self._build_acoustic_profile(audio_path),
            "debug_outputs": debug_outputs,
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

    def _build_acoustic_profile(self, audio_path: Path) -> dict:
        audio, sample_rate = self.preprocessor.load_audio(str(audio_path))
        filtered_audio = self.preprocessor.apply_band_pass_filter(audio)
        frame_rms = self._frame_rms(audio, sample_rate)
        speech_threshold = max(0.015, float(np.mean(frame_rms)) * 0.55)
        active_ratio = float(np.mean(frame_rms > speech_threshold)) if frame_rms.size else 0.0

        return {
            "sample_rate": int(sample_rate),
            "duration_seconds": round(float(audio.shape[0] / sample_rate), 4),
            "raw_rms": round(self._rms(audio), 6),
            "filtered_rms": round(self._rms(filtered_audio), 6),
            "peak_abs": round(float(np.max(np.abs(audio))), 6),
            "active_ratio": round(active_ratio, 6),
        }

    def _frame_rms(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        frame_length = max(1, int(sample_rate * 0.05))
        hop_length = max(1, int(sample_rate * 0.025))
        if audio.shape[0] < frame_length:
            return np.array([self._rms(audio)], dtype=np.float32)

        values = []
        for start in range(0, audio.shape[0] - frame_length + 1, hop_length):
            frame = audio[start : start + frame_length]
            values.append(self._rms(frame))
        return np.array(values, dtype=np.float32)

    def _audio_stats(self, audio: np.ndarray, sample_rate: int) -> dict:
        return {
            "sample_rate": int(sample_rate),
            "samples": int(audio.shape[0]),
            "duration_seconds": round(float(audio.shape[0] / sample_rate), 4),
            "min": round(float(np.min(audio)), 6),
            "max": round(float(np.max(audio)), 6),
            "mean": round(float(np.mean(audio)), 6),
            "rms": round(float(np.sqrt(np.mean(np.square(audio)))), 6),
            "peak_abs": round(float(np.max(np.abs(audio))), 6),
        }

    def _array_stats(self, values: np.ndarray) -> dict:
        return {
            "shape": [int(dim) for dim in values.shape],
            "min": round(float(np.min(values)), 6),
            "max": round(float(np.max(values)), 6),
            "mean": round(float(np.mean(values)), 6),
            "std": round(float(np.std(values)), 6),
        }

    def _rms(self, audio: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0

    def _write_debug_feature_files(
        self,
        output_dir: Path,
        analysis_id: str,
        features: np.ndarray,
        model_input: np.ndarray,
    ) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)

        log_mel = features[:128, :]
        log_mel_png = output_dir / f"{analysis_id}_log_mel_spectrogram.png"
        hybrid_features_path = output_dir / f"{analysis_id}_hybrid_features.npy"
        model_input_path = output_dir / f"{analysis_id}_model_input.npy"

        np.save(hybrid_features_path, features)
        np.save(model_input_path, model_input)
        self._write_spectrogram_image(log_mel, log_mel_png)

        return {
            "log_mel_spectrogram_png": str(log_mel_png),
            "hybrid_features_npy": str(hybrid_features_path),
            "model_input_npy": str(model_input_path),
        }

    def _write_spectrogram_image(self, spectrogram: np.ndarray, output_path: Path) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
        image = ax.imshow(
            spectrogram,
            aspect="auto",
            origin="lower",
            interpolation="nearest",
            cmap="magma",
        )
        ax.set_title("Log-mel spectrogram")
        ax.set_xlabel("Time frames")
        ax.set_ylabel("Mel bands")
        fig.colorbar(image, ax=ax, label="dB")
        fig.tight_layout()
        fig.savefig(output_path)
        plt.close(fig)
