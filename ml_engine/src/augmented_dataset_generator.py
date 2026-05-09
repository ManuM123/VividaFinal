import os
import numpy as np
import librosa
import soundfile as sf
import random
from src.preprocessing import AudioPreprocessor
from src.data_augmentation import DataAugmentation

preprocessor = AudioPreprocessor()
augmenter = DataAugmentation()

def build_dataset(raw_data_path, npy_out, wav_out):

    
    os.makedirs(npy_out, exist_ok=True)
    os.makedirs(wav_out, exist_ok=True)

    print(f"Starting dataset build. Processing files from {raw_data_path}...")
    
    for root, _, files in os.walk(raw_data_path):
        for file_name in files:
            if file_name.endswith(".wav"):
                file_path = os.path.join(root, file_name)
                base_name = file_name[:-4]
                
                # --- 1. CLEAN & STANDARDIZE THE BASE AUDIO ---
                audio, _ = librosa.load(file_path, sr=16000)
                audio = preprocessor.apply_band_pass_filter(audio)
                audio = preprocessor.standardise_audio_length(audio) # THIS FIXES THE SHAPE
                audio = preprocessor.peak_normalisation(audio)
                
                # --- 2. ORIGINAL SPECTROGRAM ---
                orig_spec = preprocessor.extract_hybrid_features(audio)
                np.save(os.path.join(npy_out, f"orig_{base_name}.npy"), orig_spec)
                
                # --- 3. AUGMENTATION ---
                aug_audio = augmenter.augment(audio)
                # Save the wav so your supervisor can hear the 4-second standardized version
                sf.write(os.path.join(wav_out, f"aug_{base_name}.wav"), aug_audio, 16000)
                
                # --- 4. AUGMENTED SPECTROGRAM ---
                aug_spec = preprocessor.extract_hybrid_features(aug_audio)
                if random.random() > 0.5:
                    aug_spec = augmenter.apply_spec_augment(aug_spec)
                
                np.save(os.path.join(npy_out, f"aug_{base_name}.npy"), aug_spec)