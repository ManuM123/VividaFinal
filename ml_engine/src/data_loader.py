import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "processed_spectrograms")

def get_dataloaders(batch_size=32, seed=42):
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.npy')]
    
    # 1. THE BUCKET SYSTEM
    # Key: '03-01-02...' | Value: ['orig_03-01-02....npy', 'aug_03-01-02....npy']
    buckets = {}
    
    for f in all_files:
        # Strip prefixes and extension to find the "Core ID"
        core_id = f.replace('aug_', '').replace('orig_', '').replace('.npy', '')
        
        if core_id not in buckets:
            buckets[core_id] = []
        buckets[core_id].append(f)

    unique_ids = list(buckets.keys())
    print(f"✅ Grouped {len(all_files)} files into {len(unique_ids)} unique recording buckets.")

    # 2. SPLIT THE BUCKETS (Ensures twins stay together)
    train_ids, temp_ids = train_test_split(unique_ids, test_size=0.30, random_state=seed)
    val_ids, test_ids = train_test_split(temp_ids, test_size=0.50, random_state=seed)

    def process_split(id_list):
        x, y = [], []
        for core_id in id_list:
            for filename in buckets[core_id]:
                # The label is the first two digits of the core_id
                # '03-01-02...' -> '03' -> 3 -> 2 (for 0-indexing)
                label = int(core_id.split('-')[0]) - 1
                
                data = np.load(os.path.join(DATA_DIR, filename))
                x.append(data)
                y.append(label)
        return np.array(x), np.array(y)

    # 3. LOAD DATA
    x_train, y_train = process_split(train_ids)
    x_val, y_val = process_split(val_ids)
    x_test, y_test = process_split(test_ids)

    print(f"📊 Dataset Split: Train={len(x_train)}, Val={len(x_val)}, Test={len(x_test)}")

    # 4. CREATE TF DATASETS
    def make_ds(x, y, shuffle=True):
        ds = tf.data.Dataset.from_tensor_slices((x, y))
        if shuffle:
            ds = ds.shuffle(len(x))
        return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)

    return make_ds(x_train, y_train), make_ds(x_val, y_val, False), make_ds(x_test, y_test, False)

if __name__ == "__main__":
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.npy')]
    shapes = {}

    print("Checking shapes of all 2880 files...")
    for f in all_files:
        data = np.load(os.path.join(DATA_DIR, f))
        current_shape = data.shape
        shapes[current_shape] = shapes.get(current_shape, 0) + 1

    print("\n--- SHAPE REPORT ---")
    for shape, count in shapes.items():
        print(f"Shape {shape}: found in {count} files")
    print("--------------------")