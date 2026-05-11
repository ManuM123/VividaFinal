
import librosa
import numpy as np
import matplotlib.pyplot as plt
from data_augmentation import DataAugmentation
from preprocessing import AudioPreprocessor 

# 1. Setup
data_augmenter = DataAugmentation()
preprocessor = AudioPreprocessor()

test_audio_path = "03-01-04-02-02-01-05.wav"

# 2. Load and Augment Audio
audio, sr = librosa.load(test_audio_path, sr=16000)
augmented_audio = data_augmenter.augment(audio)

# 3. Convert to Spectrogram
spectrogram = preprocessor.create_log_mel_spectrogram(augmented_audio)

# 4. Apply SpecAugment (The "Visual" augmentation)
augmented_spectrogram = data_augmenter.apply_spec_augment(spectrogram)

# 5. "Print" it (Visualize)
plt.figure(figsize=(10, 4))
librosa.display.specshow(augmented_spectrogram, sr=16000, x_axis='time', y_axis='mel')
plt.colorbar(format='%+2.0f dB')
plt.title('Log-Mel Spectrogram with SpecAugment')
plt.tight_layout()
plt.show() # This will pop up a window with the image