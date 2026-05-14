import os

import librosa
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split, StratifiedKFold
from torch.utils.data import DataLoader, Dataset
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_RAVDESS_DIR = os.path.join(
    BASE_DIR,
    "..",
    "..",
    "data",
    "raw_ravdess_audio_files",
)
AUGMENTED_RAVDESS_DIR = os.path.join(
    BASE_DIR,
    "..",
    "..",
    "data",
    "augmented_audio_files",
)
MODEL_NAME = "facebook/wav2vec2-base"
TARGET_SAMPLING_RATE = 16000
RESULTS_DIR = os.path.join(BASE_DIR, "..", "..", "results")

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

id2label = {index: label for index, label in enumerate(EMOTIONS)}
label2id = {label: index for index, label in enumerate(EMOTIONS)}

RAVDESS_EMOTION_CODES = {
    "01": "neutral",
    "02": "calm",
    "03": "happy",
    "04": "sad",
    "05": "angry",
    "06": "fearful",
    "07": "disgust",
    "08": "surprised",
}


def load_wav2vec2_model(model_name=MODEL_NAME):
    feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
    model = AutoModelForAudioClassification.from_pretrained(
        model_name,
        num_labels=len(EMOTIONS),
        id2label=id2label,
        label2id=label2id,
    )
    if hasattr(model, "gradient_checkpointing_disable"):
        model.gradient_checkpointing_disable()
    return feature_extractor, model


def get_ravdess_audio_files(audio_dir=RAW_RAVDESS_DIR):
    audio_files_by_name = {}
    for root, _, files in os.walk(audio_dir):
        for filename in files:
            if filename.endswith(".wav"):
                audio_files_by_name.setdefault(filename, os.path.join(root, filename))

    return sorted(audio_files_by_name.values())


def ravdess_core_id(file_path):
    filename = os.path.basename(file_path)
    return filename.replace("aug_", "").replace(".wav", "")


def label_from_ravdess_filename(file_path):
    parts = ravdess_core_id(file_path).split("-")
    emotion_code = parts[2]
    emotion = RAVDESS_EMOTION_CODES[emotion_code]
    return label2id[emotion]


def get_augmented_files_by_core_id(augmented_dir=AUGMENTED_RAVDESS_DIR):
    augmented_files = get_ravdess_audio_files(augmented_dir)
    return {
        ravdess_core_id(file_path): file_path
        for file_path in augmented_files
    }


def load_waveform(file_path, target_sampling_rate=TARGET_SAMPLING_RATE):
    waveform, _ = librosa.load(
        file_path,
        sr=target_sampling_rate,
        mono=True,
    )
    return waveform


def prepare_ravdess_file(file_path, feature_extractor):
    waveform = load_waveform(file_path)
    encoded_audio = feature_extractor(
        waveform,
        sampling_rate=TARGET_SAMPLING_RATE,
        return_tensors="pt",
    )
    encoded_audio["labels"] = label_from_ravdess_filename(file_path)
    encoded_audio["path"] = file_path
    return encoded_audio


def prepare_ravdess_dataset(feature_extractor, audio_dir=RAW_RAVDESS_DIR):
    audio_files = get_ravdess_audio_files(audio_dir)
    return [
        prepare_ravdess_file(file_path, feature_extractor)
        for file_path in audio_files
    ]


class RavdessWaveformDataset(Dataset):
    def __init__(self, file_paths, feature_extractor):
        self.file_paths = list(file_paths)
        self.feature_extractor = feature_extractor

    def __len__(self):
        return len(self.file_paths)

    def __getitem__(self, index):
        file_path = self.file_paths[index]
        waveform = load_waveform(file_path)
        encoded_audio = self.feature_extractor(
            waveform,
            sampling_rate=TARGET_SAMPLING_RATE,
            return_tensors="pt",
        )

        return {
            "input_values": encoded_audio["input_values"].squeeze(0),
            "labels": label_from_ravdess_filename(file_path),
        }


def collate_wav2vec2_batch(batch, feature_extractor):
    input_values = [
        item["input_values"].numpy()
        for item in batch
    ]
    labels = torch.tensor(
        [item["labels"] for item in batch],
        dtype=torch.long,
    )

    padded_inputs = feature_extractor.pad(
        {"input_values": input_values},
        padding=True,
        return_attention_mask=True,
        return_tensors="pt",
    )
    padded_inputs["labels"] = labels
    return padded_inputs


def create_ravdess_splits(
    audio_dir=RAW_RAVDESS_DIR,
    augmented_dir=AUGMENTED_RAVDESS_DIR,
    n_splits=5,
    test_size=0.20,
    seed=42,
    include_augmented_train=True,
):
    audio_files = get_ravdess_audio_files(audio_dir)
    labels = [label_from_ravdess_filename(file_path) for file_path in audio_files]
    augmented_by_core_id = (
        get_augmented_files_by_core_id(augmented_dir)
        if include_augmented_train
        else {}
    )

    train_val_files, test_files, train_val_labels, test_labels = train_test_split(
        audio_files,
        labels,
        test_size=test_size,
        random_state=seed,
        stratify=labels,
    )

    train_val_files = np.array(train_val_files)
    train_val_labels = np.array(train_val_labels)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = []

    for train_index, val_index in skf.split(train_val_files, train_val_labels):
        original_train_files = train_val_files[train_index].tolist()
        augmented_train_files = [
            augmented_by_core_id[ravdess_core_id(file_path)]
            for file_path in original_train_files
            if ravdess_core_id(file_path) in augmented_by_core_id
        ]

        folds.append(
            {
                "train_files": original_train_files + augmented_train_files,
                "val_files": train_val_files[val_index].tolist(),
            }
        )

    return {
        "folds": folds,
        "test_files": test_files,
        "test_labels": test_labels,
    }


def create_wav2vec2_dataloaders(
    feature_extractor,
    fold,
    test_files=None,
    batch_size=8,
):
    train_dataset = RavdessWaveformDataset(
        fold["train_files"],
        feature_extractor,
    )
    val_dataset = RavdessWaveformDataset(
        fold["val_files"],
        feature_extractor,
    )

    collate_fn = lambda batch: collate_wav2vec2_batch(batch, feature_extractor)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collate_fn,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_fn,
    )

    test_loader = None
    if test_files is not None:
        test_dataset = RavdessWaveformDataset(
            test_files,
            feature_extractor,
        )
        test_loader = DataLoader(
            test_dataset,
            batch_size=batch_size,
            shuffle=False,
            collate_fn=collate_fn,
        )

    return train_loader, val_loader, test_loader


def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def freeze_wav2vec2_encoder(model):
    for parameter in model.wav2vec2.parameters():
        parameter.requires_grad = False
    return model


def unfreeze_last_wav2vec2_layers(model, n_layers=2):
    if n_layers <= 0:
        return model

    encoder_layers = model.wav2vec2.encoder.layers
    for layer in encoder_layers[-n_layers:]:
        for parameter in layer.parameters():
            parameter.requires_grad = True

    return model


def train_one_epoch(model, train_loader, optimizer, device):
    model.train()
    total_loss = 0.0
    true_labels = []
    predicted_labels = []

    for batch in train_loader:
        batch = {
            key: value.to(device)
            for key, value in batch.items()
        }

        optimizer.zero_grad()
        outputs = model(**batch)
        loss = outputs.loss
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        predictions = torch.argmax(outputs.logits, dim=1)
        true_labels.extend(batch["labels"].detach().cpu().tolist())
        predicted_labels.extend(predictions.detach().cpu().tolist())

    return {
        "loss": total_loss / len(train_loader),
        "accuracy": accuracy_score(true_labels, predicted_labels),
    }


def evaluate_wav2vec2(model, data_loader, device):
    model.eval()
    total_loss = 0.0
    true_labels = []
    predicted_labels = []

    with torch.no_grad():
        for batch in data_loader:
            batch = {
                key: value.to(device)
                for key, value in batch.items()
            }

            outputs = model(**batch)
            total_loss += outputs.loss.item()

            predictions = torch.argmax(outputs.logits, dim=1)
            true_labels.extend(batch["labels"].cpu().tolist())
            predicted_labels.extend(predictions.cpu().tolist())

    precision, recall, f1, _ = precision_recall_fscore_support(
        true_labels,
        predicted_labels,
        average="weighted",
        zero_division=0,
    )
    return {
        "loss": total_loss / len(data_loader),
        "accuracy": accuracy_score(true_labels, predicted_labels),
        "weighted_precision": precision,
        "weighted_recall": recall,
        "weighted_f1": f1,
        "classification_report": classification_report(
            true_labels,
            predicted_labels,
            target_names=EMOTIONS,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(true_labels, predicted_labels).tolist(),
    }


def save_wav2vec2_confusion_matrix(
    confusion_matrix_values,
    output_dir=RESULTS_DIR,
    filename="wav2vec2_validation_confusion_matrix.png",
):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)

    plt.figure(figsize=(10, 8))
    sns.heatmap(
        confusion_matrix_values,
        annot=True,
        fmt="d",
        cmap="Purples",
        xticklabels=EMOTIONS,
        yticklabels=EMOTIONS,
    )
    plt.title("Wav2Vec2 Validation Confusion Matrix", fontsize=16)
    plt.ylabel("True Emotion", fontsize=12)
    plt.xlabel("Predicted Emotion", fontsize=12)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return path


def save_wav2vec2_model(
    model,
    feature_extractor,
    output_dir=RESULTS_DIR,
    model_dir_name="wav2vec2_best",
):
    model_path = os.path.join(output_dir, model_dir_name)
    os.makedirs(model_path, exist_ok=True)

    model.cpu()
    model.save_pretrained(model_path)
    feature_extractor.save_pretrained(model_path)
    return model_path


def train_wav2vec2_fold(
    fold,
    test_files=None,
    epochs=5,
    batch_size=8,
    learning_rate=1e-4,
    freeze_encoder=True,
    unfreeze_last_n_layers=0,
    early_stopping_patience=None,
):
    device = get_device()
    feature_extractor, model = load_wav2vec2_model()
    model.to(device)

    if freeze_encoder:
        freeze_wav2vec2_encoder(model)
        unfreeze_last_wav2vec2_layers(model, n_layers=unfreeze_last_n_layers)

    train_loader, val_loader, test_loader = create_wav2vec2_dataloaders(
        feature_extractor,
        fold,
        test_files=test_files,
        batch_size=batch_size,
    )

    trainable_parameters = [
        parameter
        for parameter in model.parameters()
        if parameter.requires_grad
    ]
    optimizer = torch.optim.AdamW(
        trainable_parameters,
        lr=learning_rate,
    )

    history = []
    best_val_accuracy = -1.0
    best_epoch = None
    best_val_metrics = None
    best_model_state = None
    epochs_without_improvement = 0

    for epoch in range(1, epochs + 1):
        train_metrics = train_one_epoch(model, train_loader, optimizer, device)
        val_metrics = evaluate_wav2vec2(model, val_loader, device)

        epoch_result = {
            "epoch": epoch,
            "train_loss": train_metrics["loss"],
            "train_accuracy": train_metrics["accuracy"],
            "val_loss": val_metrics["loss"],
            "val_accuracy": val_metrics["accuracy"],
            "val_weighted_precision": val_metrics["weighted_precision"],
            "val_weighted_recall": val_metrics["weighted_recall"],
            "val_weighted_f1": val_metrics["weighted_f1"],
        }
        history.append(epoch_result)

        if val_metrics["accuracy"] > best_val_accuracy:
            best_val_accuracy = val_metrics["accuracy"]
            best_epoch = epoch
            best_val_metrics = val_metrics
            best_model_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        print(
            f"Epoch {epoch:02d}/{epochs}: "
            f"Train Acc: {train_metrics['accuracy']:.4f} | "
            f"Val Acc: {val_metrics['accuracy']:.4f} | "
            f"Loss: {train_metrics['loss']:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f} | "
            f"Val F1: {val_metrics['weighted_f1']:.4f}"
        )

        if (
            early_stopping_patience is not None
            and epochs_without_improvement >= early_stopping_patience
        ):
            print(
                f"Early stopping after {epoch} epochs. "
                f"Best Val Acc: {best_val_accuracy:.4f} at epoch {best_epoch}."
            )
            break

    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        model.to(device)

    print(
        f"Best Val Acc: {best_val_accuracy:.4f} "
        f"at epoch {best_epoch}."
    )

    return {
        "model": model,
        "feature_extractor": feature_extractor,
        "history": history,
        "best_epoch": best_epoch,
        "best_val_accuracy": best_val_accuracy,
        "best_val_metrics": best_val_metrics,
        "final_val_metrics": val_metrics,
        "test_loader": test_loader,
        "device": device,
    }


def run_wav2vec2_experiment(
    n_splits=5,
    epochs=5,
    batch_size=8,
    learning_rate=1e-4,
    seed=42,
    freeze_encoder=True,
    unfreeze_last_n_layers=0,
    max_folds=None,
    evaluate_test=False,
    early_stopping_patience=None,
    save_best_model=True,
    output_dir=RESULTS_DIR,
    model_dir_name="wav2vec2_best",
):
    splits = create_ravdess_splits(n_splits=n_splits, seed=seed)
    fold_results = []
    best_fold_result = None
    best_fold_number = None
    best_val_accuracy = -1.0

    folds_to_run = splits["folds"]
    if max_folds is not None:
        folds_to_run = folds_to_run[:max_folds]

    for fold_number, fold in enumerate(folds_to_run, start=1):
        print("\n" + "=" * 30)
        print(f"STARTING WAV2VEC2 FOLD {fold_number}/{n_splits}")
        print("=" * 30)

        fold_result = train_wav2vec2_fold(
            fold,
            test_files=splits["test_files"],
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            freeze_encoder=freeze_encoder,
            unfreeze_last_n_layers=unfreeze_last_n_layers,
            early_stopping_patience=early_stopping_patience,
        )

        best_val_metrics = fold_result["best_val_metrics"]
        fold_summary = {
            "fold": fold_number,
            "best_epoch": fold_result["best_epoch"],
            "best_val_accuracy": fold_result["best_val_accuracy"],
            "best_val_weighted_precision": best_val_metrics["weighted_precision"],
            "best_val_weighted_recall": best_val_metrics["weighted_recall"],
            "best_val_weighted_f1": best_val_metrics["weighted_f1"],
            "final_val_accuracy": fold_result["final_val_metrics"]["accuracy"],
        }

        print("\nBEST VALIDATION CLASSIFICATION REPORT:")
        print(best_val_metrics["classification_report"])

        confusion_matrix_path = save_wav2vec2_confusion_matrix(
            np.array(best_val_metrics["confusion_matrix"]),
            filename=f"wav2vec2_fold_{fold_number}_validation_confusion_matrix.png",
        )
        fold_summary["confusion_matrix_path"] = confusion_matrix_path
        fold_results.append(fold_summary)
        print(f"Saved validation confusion matrix to {confusion_matrix_path}")

        if fold_result["best_val_accuracy"] > best_val_accuracy:
            best_val_accuracy = fold_result["best_val_accuracy"]
            best_fold_number = fold_number
            best_fold_result = fold_result

    test_metrics = None
    if evaluate_test and best_fold_result is not None:
        test_metrics = evaluate_wav2vec2(
            best_fold_result["model"],
            best_fold_result["test_loader"],
            best_fold_result["device"],
        )
        print("\nHELD-OUT TEST CLASSIFICATION REPORT:")
        print(test_metrics["classification_report"])
        test_confusion_matrix_path = save_wav2vec2_confusion_matrix(
            np.array(test_metrics["confusion_matrix"]),
            output_dir=output_dir,
            filename="wav2vec2_test_confusion_matrix.png",
        )
        print(f"Saved test confusion matrix to {test_confusion_matrix_path}")

    best_model_path = None
    if save_best_model and best_fold_result is not None:
        best_model_path = save_wav2vec2_model(
            best_fold_result["model"],
            best_fold_result["feature_extractor"],
            output_dir=output_dir,
            model_dir_name=model_dir_name,
        )

    validation_accuracies = [
        result["best_val_accuracy"]
        for result in fold_results
    ]

    print("\n" + "=" * 30)
    print("WAV2VEC2 VALIDATION SUMMARY")
    print("=" * 30)
    print(f"Folds ran: {len(fold_results)}")
    print(f"Best fold: {best_fold_number}")
    print(f"Mean Best Val Acc: {np.mean(validation_accuracies):.4f}")
    print(f"Std Best Val Acc: {np.std(validation_accuracies):.4f}")
    if test_metrics is not None:
        print(f"Held-out Test Acc: {test_metrics['accuracy']:.4f}")
        print(f"Held-out Test F1: {test_metrics['weighted_f1']:.4f}")
    if best_model_path is not None:
        print(f"Saved best Wav2Vec2 model to {best_model_path}")

    results = pd.DataFrame(fold_results)
    results.attrs["best_model_path"] = best_model_path
    results.attrs["held_out_test"] = test_metrics
    return results


def smoke_test_wav2vec2_pipeline(batch_size=2):
    feature_extractor, model = load_wav2vec2_model()
    splits = create_ravdess_splits()
    first_fold = splits["folds"][0]

    train_loader, _, _ = create_wav2vec2_dataloaders(
        feature_extractor,
        first_fold,
        batch_size=batch_size,
    )

    batch = next(iter(train_loader))
    outputs = model(**batch)

    return {
        "loss": float(outputs.loss.detach().cpu()),
        "logits_shape": tuple(outputs.logits.shape),
        "batch_input_shape": tuple(batch["input_values"].shape),
        "batch_label_shape": tuple(batch["labels"].shape),
    }
