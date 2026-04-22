import librosa.display
import matplotlib.pyplot as plt
from preprocessing import AudioPreprocessor

preprocessor = AudioPreprocessor()

test_audio_file_path =  "03-01-04-02-02-01-05.wav"

spectogram = preprocessor.process_file(test_audio_file_path)

plt.figure(figsize=(10, 4))

# 2. Use librosa's special display function for spectrograms
librosa.display.specshow(
    spectogram, 
    sr=preprocessor.sample_rate, 
    hop_length=512, 
    x_axis='time', 
    y_axis='mel'
)

# 3. Add a color bar so we know what the colors mean (dB levels)
plt.colorbar(format='%+2.0f dB')

# 4. Give it a title and show it
plt.title('Log-Mel Spectrogram: ' + test_audio_file_path)
plt.tight_layout()
plt.show()