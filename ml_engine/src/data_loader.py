import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split, StratifiedKFold

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "processed_spectrograms")

def _normalise_feature_blocks(x_arr):
    """Normalise mel and engineered feature blocks separately within each split."""
    mel = x_arr[:, :128, :]
    features = x_arr[:, 128:, :]

    mel = (mel - np.min(mel)) / (np.max(mel) - np.min(mel) + 1e-8)
    features = (features - np.min(features)) / (np.max(features) - np.min(features) + 1e-8)

    x_arr[:, :128, :] = mel
    x_arr[:, 128:, :] = features
    return x_arr


def _prepare_model_input(x_arr, model_input="hybrid"):
    if model_input in {"hybrid", "mlp"}:
        return x_arr
    if model_input in {"cnn_lstm", "cnn"}:
        return x_arr[..., np.newaxis]
    if model_input in {"vector", "cnn_1d"}:
        return np.mean(x_arr, axis=2)[..., np.newaxis]
    raise ValueError("model_input must be one of: 'hybrid', 'mlp', 'cnn_lstm', 'cnn', 'vector', 'cnn_1d'")


def _augment_spectrogram(x, y):
    """Apply lightweight SpecAugment-style regularisation to training examples."""
    x = tf.cast(x, tf.float32)
    row_count = tf.shape(x)[0]
    col_count = tf.shape(x)[1]
    should_mask = tf.random.uniform([]) < 0.40

    freq_width = tf.random.uniform([], minval=0, maxval=8, dtype=tf.int32)
    freq_start = tf.random.uniform([], minval=0, maxval=128 - 8, dtype=tf.int32)
    time_width = tf.random.uniform([], minval=0, maxval=10, dtype=tf.int32)
    time_start = tf.random.uniform([], minval=0, maxval=126 - 10, dtype=tf.int32)

    rows = tf.range(row_count)[:, tf.newaxis, tf.newaxis]
    cols = tf.range(col_count)[tf.newaxis, :, tf.newaxis]

    mel_rows = rows < 128
    freq_mask = tf.logical_and(rows >= freq_start, rows < freq_start + freq_width)
    freq_mask = tf.logical_and(freq_mask, mel_rows)
    time_mask = tf.logical_and(cols >= time_start, cols < time_start + time_width)
    mask = tf.cast(tf.logical_not(tf.logical_or(freq_mask, time_mask)), tf.float32)
    mask = tf.cond(should_mask, lambda: mask, lambda: tf.ones_like(mask))

    noise = tf.random.normal(tf.shape(x), mean=0.0, stddev=0.004, dtype=tf.float32)
    x = tf.clip_by_value((x * mask) + noise, 0.0, 1.0)
    return x, y


def get_kfold_dataloaders(
    n_splits=5,
    batch_size=32,
    seed=42,
    model_input="hybrid",
    include_test=True,
):
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.npy')]
    
    # 1. BUCKET SYSTEM: Manually grouping twins to prevent data leakage
    buckets = {}
    for f in all_files:
        core_id = f.replace('aug_', '').replace('orig_', '').replace('.npy', '')
        if core_id not in buckets:
            buckets[core_id] = []
        buckets[core_id].append(f)

    unique_ids = list(buckets.keys())
    
    # Extract the emotion label for Stratification
    labels = [int(core_id.split('-')[2]) - 1 for core_id in unique_ids]

    # 2. Test set - reserved for final evaluation
    train_val_ids, test_ids, train_val_labels, test_labels = train_test_split(
        unique_ids, labels, test_size=0.20, random_state=seed, stratify=labels
    )

    def process_split(id_list):
        x, y = [], []
        for core_id in id_list:
            for filename in buckets[core_id]:
                label = int(core_id.split('-')[2]) - 1
                data = np.load(os.path.join(DATA_DIR, filename))
                x.append(data)
                y.append(label)
        
        x_arr = np.array(x, dtype=np.float32)
        y_arr = np.array(y)

        x_arr = _normalise_feature_blocks(x_arr)
        x_arr = _prepare_model_input(x_arr, model_input=model_input)
        return x_arr, y_arr

    def make_dataset(x, y, shuffle=True, augment=False):
        ds = tf.data.Dataset.from_tensor_slices((x, y))
        if shuffle:
            ds = ds.shuffle(len(x), seed=seed, reshuffle_each_iteration=True)
        if augment:
            ds = ds.map(_augment_spectrogram, num_parallel_calls=tf.data.AUTOTUNE)
        return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)

    test_ds, x_test, y_test = None, None, None
    if include_test:
        x_test, y_test = process_split(test_ids)
        test_ds = make_dataset(x_test, y_test, shuffle=False)
        print(f"Test Set: {len(x_test)} files.")
    else:
        print(f"Hold-out test set reserved: {sum(len(buckets[core_id]) for core_id in test_ids)} files.")

    # 3. STRATIFIED K-FOLD on the remaining 80%
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    
    folds = []
    train_val_ids = np.array(train_val_ids)
    train_val_labels = np.array(train_val_labels)

    for train_idx, val_idx in skf.split(train_val_ids, train_val_labels):
        fold_train_ids = train_val_ids[train_idx]
        fold_val_ids = train_val_ids[val_idx] # This becomes the rotating validation set

        x_train, y_train = process_split(fold_train_ids)
        x_val, y_val = process_split(fold_val_ids)

        train_ds = make_dataset(
            x_train,
            y_train,
            shuffle=True,
            augment=model_input in {"cnn_lstm", "cnn"},
        )
        val_ds = make_dataset(x_val, y_val, shuffle=False)
        
        folds.append((train_ds, val_ds))

    print(f"Generated {n_splits} Balanced Folds for Cross-Validation.")
    return folds, test_ds, x_test, y_test
