import os
import numpy as np
import tensorflow as tf

# Relative pathing: Go up one level from 'src', then into 'data/processed_spectrograms'
# BASE_DIR is .../ml_engine/src/helper_functions
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Climb up 3 levels: helper_functions -> src -> ml_engine
# Then go down into data/processed_spectrograms
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "data", "processed_spectrograms"))

def check_data():
    if not os.path.exists(DATA_DIR):
        print(f"Error: Directory not found at {DATA_DIR}")
        return

    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.npy')]
    
    shapes = set() # A 'set' only keeps unique values
    for f in files:
        data = np.load(os.path.join(DATA_DIR, f))
        shapes.add(data.shape)

    print("--- GLOBAL DATA REPORT ---")
    print(f"Total files scanned: {len(files)}")
    print(f"Unique shapes found: {shapes}") 
    
    if len(shapes) == 1:
        print("SUCCESS! All files have identical dimensions.")
    else:
        print("WARNING! Multiple shapes detected! Training will fail.")
    print("--------------------------")

if __name__ == "__main__":
    check_data()