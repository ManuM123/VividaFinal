import json
import os
import sys
import time

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import keras
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.utils.class_weight import compute_class_weight

from src.data_loader import get_kfold_dataloaders

from src.models.cnn_lstm import Hybrid_CNN_LSTM, train_hybrid_cnn_lstm
from src.models.mlp import MLP, train_mlp


EMOTIONS = ["Neutral", "Calm", "Happy", "Sad", "Angry", "Fearful", "Disgust", "Surprised"]


class ValidationExperimentResult(dict):
    """Dict result that still supports legacy tuple unpacking in notebooks."""

    def __iter__(self):
        fold_accuracies = [
            fold["best_val_accuracy"]
            for fold in self["cross_validation"]["folds"]
        ]
        yield self["cross_validation"]["mean_best_val_accuracy"]
        yield fold_accuracies


def _resolve_output_dir(output_dir):
    if os.path.isabs(output_dir):
        return output_dir

    normalised = os.path.normpath(output_dir)
    if normalised == "ml_engine/results":
        return os.path.join(PROJECT_ROOT, "results")
    if normalised.startswith(f"ml_engine{os.sep}"):
        return os.path.join(PROJECT_ROOT, normalised.split(os.sep, 1)[1])
    return os.path.join(PROJECT_ROOT, normalised)


def _dataset_labels(dataset):
    labels = []
    for _, y_batch in dataset:
        labels.extend(y_batch.numpy().tolist())
    return np.array(labels)


def _class_weights_from_dataset(dataset):
    y = _dataset_labels(dataset)
    classes = np.unique(y)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y)
    return {int(cls): float(weight) for cls, weight in zip(classes, weights)}


def _predict_dataset(model, dataset):
    y_true = _dataset_labels(dataset)
    y_prob = model.predict(dataset, verbose=0)
    y_pred = np.argmax(y_prob, axis=1)
    return y_true, y_pred


def _latency_ms(model, sample, warmup_runs=3, timed_runs=20):
    for _ in range(warmup_runs):
        model.predict(sample, verbose=0)

    start = time.perf_counter()
    for _ in range(timed_runs):
        model.predict(sample, verbose=0)
    return ((time.perf_counter() - start) / timed_runs) * 1000


def _save_confusion_matrix(
    cm,
    model_type,
    output_dir,
    cmap_colour,
    suffix="",
    title_context="Held-Out Test",
):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{model_type}{suffix}_confusion_matrix.png")

    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap=cmap_colour,
        xticklabels=EMOTIONS,
        yticklabels=EMOTIONS,
    )
    plt.title(f"{model_type.upper()} {title_context} Confusion Matrix", fontsize=16)
    plt.ylabel("True Emotion", fontsize=12)
    plt.xlabel("Predicted Emotion", fontsize=12)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return path


def _save_model(model, model_path):
    keras_model = getattr(model, "model", None) or getattr(model, "network", None) or model
    keras_model.save(model_path)
    return model_path


def _model_config(model_type):
    model_type = model_type.lower()

    if model_type == "mlp":
        return {
            "input_shape": (180, 126),
            "model_input": "mlp",
            "model_class": MLP,
            "train_func": train_mlp,
            "cmap": "Blues",
            "use_class_weight": False,
        }

    if model_type in {"cnn_lstm"}:
        return {
            "input_shape": (180, 126, 1),
            "model_input": "cnn_lstm",
            "model_class": Hybrid_CNN_LSTM,
            "train_func": train_hybrid_cnn_lstm,
            "cmap": "Greens",
            "use_class_weight": True,
        }


    if model_type == "ast":
        raise NotImplementedError(
            "AST fine-tuning still needs a separate PyTorch/Hugging Face pipeline."
        )

    raise ValueError("Invalid model type. Choose one of: mlp, cnn_lstm, ast")


def run_experiment(
    model_type: str,
    n_splits: int = 5,
    epochs: int = 100,
    batch_size: int = 32,
    seed: int = 42,
    output_dir: str = "ml_engine/results",
    save_best_model: bool = True,
    validation_only: bool = False,
):
    output_dir = _resolve_output_dir(output_dir)

    if model_type.lower() == "ast":
        from src.helper_functions.run_ast_experiment import run_ast_experiment

        return run_ast_experiment(
            n_splits=n_splits,
            epochs=epochs,
            batch_size=batch_size,
            seed=seed,
            output_dir=output_dir,
            save_best_model=save_best_model,
            validation_only=validation_only,
        )

    config = _model_config(model_type)
 

    folds, test_ds, _, _ = get_kfold_dataloaders(
        n_splits=n_splits,
        batch_size=batch_size,
        seed=seed,
        model_input=config["model_input"],
        include_test=not validation_only,
    )

    fold_results = []
    validation_y_true = []
    validation_y_pred = []
    best_model = None
    best_val_acc = -1.0
    best_fold = None

    for i, (train_ds, val_ds) in enumerate(folds, start=1):
        print("\n" + "=" * 30)
        print(f"STARTING {model_type.upper()} FOLD {i}/{n_splits}")
        print("=" * 30)

        keras.backend.clear_session()
        model = config["model_class"](input_shape=config["input_shape"])

        class_weight = (
            _class_weights_from_dataset(train_ds) if config["use_class_weight"] else None
        )
        history = config["train_func"](
            model,
            train_ds,
            val_ds,
            epochs=epochs,
            class_weight=class_weight,
        ) if config["use_class_weight"] else config["train_func"](
            model,
            train_ds,
            val_ds,
            epochs=epochs,
        )

        fold_best_val_acc = float(max(history.history["val_accuracy"]))
        fold_best_val_loss = float(min(history.history["val_loss"]))
        fold_y_true, fold_y_pred = _predict_dataset(model, val_ds)
        fold_precision, fold_recall, fold_f1, _ = precision_recall_fscore_support(
            fold_y_true,
            fold_y_pred,
            average="weighted",
            zero_division=0,
        )
        validation_y_true.extend(fold_y_true.tolist())
        validation_y_pred.extend(fold_y_pred.tolist())

        fold_results.append(
            {
                "fold": i,
                "best_val_accuracy": fold_best_val_acc,
                "best_val_loss": fold_best_val_loss,
                "epochs_ran": len(history.history["loss"]),
                "restored_val_accuracy": float(accuracy_score(fold_y_true, fold_y_pred)),
                "weighted_precision": float(fold_precision),
                "weighted_recall": float(fold_recall),
                "weighted_f1": float(fold_f1),
            }
        )

        if fold_best_val_acc > best_val_acc:
            best_model = model
            best_val_acc = fold_best_val_acc
            best_fold = i

        print(f"Fold {i} Best Val Acc: {fold_best_val_acc:.4f}")

    cv_summary = {
        "model_type": model_type,
        "n_splits": n_splits,
        "epochs": epochs,
        "batch_size": batch_size,
        "seed": seed,
        "best_validation_fold": best_fold,
        "cross_validation": {
            "folds": fold_results,
            "mean_best_val_accuracy": float(
                np.mean([r["best_val_accuracy"] for r in fold_results])
            ),
            "std_best_val_accuracy": float(
                np.std([r["best_val_accuracy"] for r in fold_results])
            ),
        },
    }

    if validation_only:
        os.makedirs(output_dir, exist_ok=True)
        validation_y_true = np.array(validation_y_true)
        validation_y_pred = np.array(validation_y_pred)
        validation_precision, validation_recall, validation_f1, _ = (
            precision_recall_fscore_support(
                validation_y_true,
                validation_y_pred,
                average="weighted",
                zero_division=0,
            )
        )
        validation_cm = confusion_matrix(validation_y_true, validation_y_pred)
        validation_cm_path = _save_confusion_matrix(
            validation_cm,
            model_type,
            output_dir,
            config["cmap"],
            suffix="_validation",
            title_context="Cross-Validation",
        )
        validation_report_text = classification_report(
            validation_y_true,
            validation_y_pred,
            target_names=EMOTIONS,
            zero_division=0,
        )
        cv_summary["cross_validation"].update(
            {
                "restored_weight_accuracy": float(
                    accuracy_score(validation_y_true, validation_y_pred)
                ),
                "weighted_precision": float(validation_precision),
                "weighted_recall": float(validation_recall),
                "weighted_f1": float(validation_f1),
                "classification_report": classification_report(
                    validation_y_true,
                    validation_y_pred,
                    target_names=EMOTIONS,
                    output_dict=True,
                    zero_division=0,
                ),
                "confusion_matrix": validation_cm.tolist(),
                "confusion_matrix_path": validation_cm_path,
            }
        )
        results_path = os.path.join(output_dir, f"{model_type}_validation_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(cv_summary, f, indent=2)

        print("\n" + "=" * 30)
        print(f"{model_type.upper()} CROSS-VALIDATION COMPLETE")
        print(
            "Mean Best Val Acc: "
            f"{cv_summary['cross_validation']['mean_best_val_accuracy']:.4f} "
            f"+/- {cv_summary['cross_validation']['std_best_val_accuracy']:.4f}"
        )
        print("VALIDATION CLASSIFICATION REPORT:")
        print(validation_report_text)
        print(
            "Restored-Weight Val Acc: "
            f"{cv_summary['cross_validation']['restored_weight_accuracy']:.4f}"
        )
        print(f"Weighted Precision: {validation_precision:.4f}")
        print(f"Weighted Recall: {validation_recall:.4f}")
        print(f"Weighted F1: {validation_f1:.4f}")
        print("Held-out test set was not evaluated.")
        print(f"Saved validation metrics to {results_path}")
        print(f"Saved validation confusion matrix to {validation_cm_path}")
        print("=" * 30)
        return ValidationExperimentResult(cv_summary)

    print("\n" + "=" * 30)
    print(f"{model_type.upper()} HELD-OUT TEST EVALUATION")
    print(f"Best validation fold: {best_fold}")
    print("=" * 30)

    y_true, y_pred = _predict_dataset(best_model, test_ds)
    accuracy = float(accuracy_score(y_true, y_pred))
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred)

    sample_batch, _ = next(iter(test_ds))
    latency = float(_latency_ms(best_model, sample_batch[0:1]))

    os.makedirs(output_dir, exist_ok=True)
    cm_path = _save_confusion_matrix(cm, model_type, output_dir, config["cmap"])

    model_path = None
    if save_best_model:
        model_path = os.path.join(output_dir, f"{model_type}_best.keras")
        _save_model(best_model, model_path)

    report_text = classification_report(
        y_true,
        y_pred,
        target_names=EMOTIONS,
        zero_division=0,
    )
    print("CLASSIFICATION REPORT:")
    print(report_text)
    print(f"Test Accuracy: {accuracy:.4f}")
    print(f"Weighted Precision: {precision:.4f}")
    print(f"Weighted Recall: {recall:.4f}")
    print(f"Weighted F1: {f1:.4f}")
    print(f"Inference Latency: {latency:.2f} ms/sample")

    results = {
        **cv_summary,
        "held_out_test": {
            "accuracy": accuracy,
            "weighted_precision": float(precision),
            "weighted_recall": float(recall),
            "weighted_f1": float(f1),
            "latency_ms_per_sample": latency,
            "classification_report": classification_report(
                y_true,
                y_pred,
                target_names=EMOTIONS,
                output_dict=True,
                zero_division=0,
            ),
            "confusion_matrix": cm.tolist(),
        },
        "artifacts": {
            "confusion_matrix_path": cm_path,
            "model_path": model_path,
        },
    }

    results_path = os.path.join(output_dir, f"{model_type}_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Saved metrics to {results_path}")
    print(f"Saved confusion matrix to {cm_path}")
    if model_path:
        print(f"Saved best model to {model_path}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train and evaluate a Vivida SER model.")
    parser.add_argument("model_type", choices=["mlp", "cnn_lstm", "ast"])
    parser.add_argument("--splits", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="ml_engine/results")
    parser.add_argument("--no-save-model", action="store_true")
    parser.add_argument(
        "--validation-only",
        action="store_true",
        help="Run cross-validation only and do not load/evaluate the held-out test set.",
    )
    args = parser.parse_args()

    run_experiment(
        model_type=args.model_type,
        n_splits=args.splits,
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
        output_dir=args.output_dir,
        save_best_model=not args.no_save_model,
        validation_only=args.validation_only,
    )
