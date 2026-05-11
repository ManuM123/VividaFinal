import os
import numpy as np
import matplotlib.pyplot as plt

# Relative path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "processed_spectrograms")

def plot_spectrogram():
    # Get the first available file
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.npy')]
    if not files:
        print("No spectrograms found!")
        return

    file_to_open = files[0]
    data = np.load(os.path.join(DATA_DIR, file_to_open))

    plt.figure(figsize=(10, 4))
    # We use 'viridis' or 'magma' to see the intensity clearly
    plt.imshow(data, aspect='auto', origin='lower', cmap='magma')
    plt.colorbar(label='Intensity (dB)')
    plt.title(f"Spectrogram Visualization: {file_to_open}")
    plt.xlabel("Time (Pixels/Frames)")
    plt.ylabel("Frequency (Mel Bins)")
    
    print(f"Displaying image for: {file_to_open}")
    plt.show()

if __name__ == "__main__":
    plot_spectrogram()