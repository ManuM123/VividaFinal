import librosa
from scipy.signal import butter, filtfilt
import numpy as np

class AudioPreprocessor:
    def __init__(self, sample_rate=16000, window_length=4):
        # window_length is the size of the 'audio slice' (in seconds) the model expects. Longer recordings will be segmented into multiple windows of this length.
        
        self.sample_rate = sample_rate
        self.window_length = window_length
        self.total_samples = sample_rate * window_length 

    
    #Removes non-human frequencies (300Hz-4000Hz) to reduce evironmental noise and electronic hiss.
    def apply_band_pass_filter(self, audio):
        nyquist = 0.5 * self.sample_rate
        low_cutoff = 300 / nyquist
        high_cutoff = 4000 / nyquist

        b, a = butter(N=4, Wn=[low_cutoff, high_cutoff], btype='bandpass')

        return filtfilt(b, a, audio)
    
    # ensures all audio is of the same length
    def standardise_audio_length(self, audio):
        audio, _ = librosa.effects.trim(audio, top_db=30)

        # if audio is too long
        if len(audio) > self.total_samples:
            return audio[:self.total_samples]
        else:
            missing_padding = self.total_samples - len(audio)
            return np.pad(audio, (0, missing_padding), 'constant')
        
    def peak_normalisation(self, audio):
        return librosa.util.normalize(audio)
    
    def create_log_mel_spectrogram(self, audio):
        mel_spec = librosa.feature.melspectrogram(
            y=audio,
            sr=self.sample_rate,
            n_mels = 128,
            hop_length=512
        )

        log_mel_spec = librosa.power_to_db(mel_spec, ref=np.max)

        return log_mel_spec
    
    def process_file(self, file_path):
        # end to end function that preprocesses .wav file and converts it into spectogram
       
        # 1. Load the audio file
        audio, _ = librosa.load(file_path, sr=self.sample_rate)

        # 2. Clean the noise
        audio = self.apply_band_pass_filter(audio)

        # 3. Fix the length to 4 seconds
        audio = self.standardise_audio_length(audio)

        # 4. Boost the volume (Normalization)
        audio = self.peak_normalisation(audio)

        # 5. Convert to the final "Image"
        spectrogram = self.create_log_mel_spectrogram(audio)

        return spectrogram