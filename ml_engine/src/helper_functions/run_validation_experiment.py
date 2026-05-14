import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.helper_functions.run_experiement import run_experiment


def run_validation_experiment(
    model_type: str,
    n_splits: int = 5,
    epochs: int = 50,
    batch_size: int = 32,
    **kwargs,
):
    """Backward-compatible wrapper for older notebook calls."""
    results = run_experiment(
        model_type=model_type,
        n_splits=n_splits,
        epochs=epochs,
        batch_size=batch_size,
        save_best_model=False,
        validation_only=True,
        **kwargs,
    )

    if model_type.lower() == "wav2vec2":
        return results["best_val_accuracy"].tolist()

    return [fold["best_val_accuracy"] for fold in results["cross_validation"]["folds"]]
