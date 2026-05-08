import colorednoise as cn
import os
import librosa
import numpy as np
import random

class DataAugmentation:
    def __init__(self, sample_rate=16000):
        current_file = os.path.abspath(__file__)
        parent_folder = os.path.dirname(current_file)
        ml_engine_root = os.path.dirname(parent_folder)

        background_noises_path = os.path.join(ml_engine_root, "data", "background_noises")


        self.sample_rate = sample_rate
        self.background_noise = {   
            "chatter": os.path.join(background_noises_path, "people_talking.wav"),
            "traffic": os.path.join(background_noises_path, "traffic.wav")
        }

    
    def add_pink_noise(self, audio, noise_level=0.005):
        pink_noise = cn.powerlaw_psd_gaussian(1, len(audio))
        return audio + (noise_level * pink_noise)


    # adds either chatter or traffic noise over the audio, attempting to replicate real app use case
    def add_background_noise(self, audio):
      
        noise_volumes = {
            "traffic": 0.5,
            "people_talking": 0.05 
        }

        noise_type = random.choice(list(self.background_noise.keys()))
        file_path = self.background_noise.get(noise_type)
        
        # Use the specific volume for this noise type
        current_volume = noise_volumes.get(noise_type, 0.05)

        if file_path and os.path.exists(file_path):
            noise_duration = librosa.get_duration(path=file_path)
            audio_duration = len(audio) / self.sample_rate

            if noise_duration > audio_duration:
                max_start = noise_duration - audio_duration
                start_sec = random.uniform(0, max_start)
                noise_wav, _ = librosa.load(
                    file_path, 
                    sr=self.sample_rate, 
                    offset=start_sec, 
                    duration=audio_duration
                )
            else:
                noise_wav, _ = librosa.load(file_path, sr=self.sample_rate)
                noise_wav = np.pad(noise_wav, (0, len(audio) - len(noise_wav)), mode='wrap')

            # Final mix using the specific volume for THIS noise
            return audio + (current_volume * noise_wav)
        
        return audio

    
    # Shifts the audio forward by adding random silence at the start. This mimics a user delay after hitting 'Record'.
    def add_time_shift(self, audio, max_shift_seconds=1.5):
        shift_limit = int(max_shift_seconds * self.sample_rate)
        shift_amount = random.randint(0, shift_limit)
        silence = np.zeros(shift_amount)
        shifted_audio = np.concatenate([silence, audio])

        return shifted_audio[:len(audio)]
    
    def change_speed(self, audio):
        rate = random.uniform(0.8,1.2)
        stretch = librosa.effects.time_stretch(audio, rate=rate)

        if len(stretch) > len(audio):
            return stretch[:len(audio)]
        else:
            return np.pad(stretch, (0,len(audio) - len(stretch)), mode='constant')
    
    def change_pitch(self, audio):
        random_steps = random.uniform(-2,2)
        
        return librosa.effects.pitch_shift(audio, sr=self.sample_rate, n_steps=random_steps)
    
    
    def apply_spec_augment(self, spectrogram, freq_mask_width=10, time_mask_width=15):
        """
        Operates on the Spectrogram (2D NumPy array).
        freq_mask_width: height of the horizontal bar.
        time_mask_width: width of the vertical bar.
        """
       
        # Get dimensions: [Frequency Bins, Time Steps]
        num_mel_bins, num_time_steps = spectrogram.shape
        
        # 1. Frequency Mask (Horizontal bar)
        # We use -80.0 because in a log-mel spectrogram, -80 is basically silence (0 amplitude)
        f_start = random.randint(0, num_mel_bins - freq_mask_width)
        spectrogram[f_start : f_start + freq_mask_width, :] = -80.0
        
        # 2. Time Mask (Vertical bar)
        t_start = random.randint(0, num_time_steps - time_mask_width)
        spectrogram[:, t_start : t_start + time_mask_width] = -80.0
        
        return spectrogram
    
    # applies one random audio-based augmentation from the ones above
    def augment(self, audio):
        random_augmentation = random.choice(["pink_noise", "background_noise", "time_shift", "change_speed", "change_pitch"])

        match random_augmentation:
            case "pink_noise":
                return self.add_pink_noise(audio)
            case "background_noise":
                return self.add_background_noise(audio)
            case "time_shift":
                return self.add_time_shift(audio)
            case "change_speed":
                return self.change_speed(audio)
            case "change_pitch":
                return self.change_pitch(audio)









