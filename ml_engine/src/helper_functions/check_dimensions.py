import os
import numpy as np
import tensorflow as tf

# Relative pathing: Go up one level from 'src', then into 'data/processed_spectrograms'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "processed_spectrograms")

def check_data():
    # Verify the folder exists first
    if not os.path.exists(DATA_DIR):
        print(f"Error: Directory not found at {DATA_DIR}")
        print("Check your folder structure matches: ml_engine/data/processed_spectrograms")
        return

    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.npy')]
    
    if not files:
        print(f"Error: No .npy files found in {DATA_DIR}")
        return

    # Load one sample to verify dimensions
    sample_path = os.path.join(DATA_DIR, files[0])
    sample_data = np.load(sample_path)
    
    # Test Tensor conversion (GPU/Supervisor requirement)
    sample_tensor = tf.convert_to_tensor(sample_data, dtype=tf.float32)
    
    print("--- DATA REPORT ---")
    print(f"Path used: {DATA_DIR}")
    print(f"Total .npy files: {len(files)}")
    print(f"Spectrogram Shape: {sample_data.shape}")
    print(f"Tensor Conversion: SUCCESS")
    print(f"Tensor DType: {sample_tensor.dtype}")
    print("-------------------")

if __name__ == "__main__":
    check_data()