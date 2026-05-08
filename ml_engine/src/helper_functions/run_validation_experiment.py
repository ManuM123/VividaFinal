import numpy as np
import time
import keras
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
from src.models.mlp import MLP, train_mlp
from src.models.cnn import CNN, train_cnn
from src.data_loader import get_kfold_dataloaders

def run_validation_experiment(model_type: str, n_splits: int= 5, epochs:int =50, batch_size:int =32):
    # Still get the loaders, but we ignore the raw test data for now
    folds, _, _, _ = get_kfold_dataloaders(n_splits=n_splits, batch_size=batch_size)

    model_type = model_type.lower()
    # ... [Keep your model_class and train_func logic here] ...

    all_val_accuracies = []

    for i, (train_ds, val_ds) in enumerate(folds):
        print(f"\n" + "="*30)
        print(f"VALIDATION FOLD {i+1}/{n_splits}")
        print("="*30)

        keras.backend.clear_session()
        model = model_class(input_shape=input_shape)
        
        # We only care about how it does on the validation set
        history = train_func(model, train_ds, val_ds, epochs=epochs)

        best_val_acc = max(history.history['val_accuracy'])
        all_val_accuracies.append(best_val_acc)
        print(f"Fold {i+1} Best Val Acc: {best_val_acc:.4f}")

    avg_val_acc = np.mean(all_val_accuracies)
    print(f"\nOVERALL CROSS-VALIDATION ACCURACY: {avg_val_acc:.4f}")

    return all_val_accuracies