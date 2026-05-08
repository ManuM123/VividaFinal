import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split, StratifiedKFold

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "processed_spectrograms")

def get_kfold_dataloaders(n_splits=5, batch_size=32, seed=42):
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

    # 2. GLOBAL HOLD-OUT TEST SET (20%) - Locked in the vault for final evaluation
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

        x_min = np.min(x_arr)
        x_max = np.max(x_arr)

        # Min-Max scaling
        x_arr = (x_arr - x_min) / (x_max - x_min + 1e-8)

        return x_arr, y_arr

    def make_dataset(x, y, shuffle=True):
        ds = tf.data.Dataset.from_tensor_slices((x, y))
        if shuffle:
            ds = ds.shuffle(len(x))
        return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)

    # Build test set
    x_test, y_test = process_split(test_ids)
    test_ds = make_dataset(x_test, y_test, shuffle=False)
    print(f"Test Set: {len(x_test)} files.")

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

        train_ds = make_dataset(x_train, y_train, shuffle=True)
        val_ds = make_dataset(x_val, y_val, shuffle=False)
        
        folds.append((train_ds, val_ds))

    print(f"Generated {n_splits} Balanced Folds for Cross-Validation.")
    return folds, test_ds, x_test, y_test