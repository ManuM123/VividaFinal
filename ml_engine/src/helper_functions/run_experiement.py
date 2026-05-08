# import numpy as np
# import time
# import keras
# import matplotlib.pyplot as plt
# import seaborn as sns
# from sklearn.metrics import classification_report, confusion_matrix
# from src.models.mlp import MLP, train_mlp
# from src.models.cnn import CNN, train_cnn
# from src.data_loader import get_kfold_dataloaders

# def run_experiment(model_type: str, n_splits: int= 5, epochs:int =50, batch_size:int =32):
#     folds, _, x_test_raw, y_test_raw = get_kfold_dataloaders(n_splits=n_splits, batch_size=batch_size)

#     model_type = model_type.lower()

#     if model_type == "mlp":
#         input_shape = (128,126)
#         train_func = train_mlp
#         model_class = MLP
#         cmap_colour = 'Blues'

#     elif model_type == "cnn":
#         x_test_raw = x_test_raw[..., np.newaxis]
#         input_shape = (128,126,1)
#         train_func = train_cnn
#         model_class = CNN
#         cmap_colour = 'Greens'

#     elif model_type == 'ast':
#         print("AST Pipeline not done yet")
#         return
    
#     else:
#         raise ValueError("Invalid model type, please choose either mlp, cnn or ast")
    

#     all_val_accuracies = []
#     last_model = None

#     for i, (train_ds, val_ds) in enumerate(folds):
#         print(f"\n" + "="*30)
#         print(f"STARTING FOLD {i+1}/5")
#         print("="*30)

#         keras.backend.clear_session()

#         model = model_class(input_shape=input_shape)

#         history = train_func(model, train_ds, val_ds, epochs=epochs)

#         best_val_acc = max(history.history['val_accuracy'])
#         all_val_accuracies.append(best_val_acc)
#         last_model = model
#         print(f"Fold {i+1} Best Val Acc: {best_val_acc:.4f}")

    
#     print("\n" + "="*30)
#     print(f"{model_type.upper()} TEST SET RUN")
#     print("="*30)

#     y_pred_probs = last_model.predict(x_test_raw)
#     y_pred = np.argmax(y_pred_probs, axis=1)

#     test_acc = np.mean(y_pred == y_test_raw)
#     print(f"TEST ACCURACY: {test_acc:.4f}\n")

#     emotions = ['Neutral', 'Calm', 'Happy', 'Sad', 'Angry', 'Fearful', 'Disgust', 'Surprised']

#     # Classification Report
#     print("CLASSIFICATION REPORT:")
#     print(classification_report(y_test_raw, y_pred, target_names=emotions, zero_division=0))

#     # Inference latency
#     start_time = time.time()
#     _ = model.predict(x_test_raw[0:1], verbose=0)
#     latency_ms = (time.time() - start_time) * 1000
#     print(f"\n Inference Latency: {latency_ms:.2f} ms")

#         # Confusion Matrix
#     cm = confusion_matrix(y_test_raw, y_pred)

#     plt.figure(figsize=(10,8))
#     sns.heatmap(cm, annot=True, fmt='d', cmap=cmap_colour, xticklabels=emotions, yticklabels=emotions)
#     plt.title(f"{model_type.upper()} Test Set Confusion Matrix", fontsize=16)
#     plt.ylabel('True Emotion', fontsize=12)
#     plt.xlabel('Predicted Emotion', fontsize=12)
#     plt.tight_layout()
#     plt.show()

#     return test_acc, all_val_accuracies



    
import numpy as np
import time
import keras
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix

from src.models.mlp import MLP, train_mlp
from src.models.cnn import CNN, train_cnn
from src.data_loader import get_kfold_dataloaders

def run_experiment(model_type: str, n_splits: int = 5, epochs: int = 100, batch_size: int = 32):
    # We unpack the test set variables into `_` to explicitly ignore them and prevent data leakage
    folds, _, _, _ = get_kfold_dataloaders(n_splits=n_splits, batch_size=batch_size)

    model_type = model_type.lower()

    if model_type == "mlp":
        input_shape = (128,126)
        train_func = train_mlp
        model_class = MLP
        cmap_colour = 'Blues'

    elif model_type == "cnn":
        input_shape = (128,126,1)
        train_func = train_cnn
        model_class = CNN
        cmap_colour = 'Greens'

    elif model_type == 'ast':
        print("AST Pipeline not done yet")
        return
    
    else:
        raise ValueError("Invalid model type, please choose either mlp, cnn or ast")
    
    all_val_accuracies = []
    last_model = None
    last_val_ds = None

    for i, (train_ds, val_ds) in enumerate(folds):
        print(f"\n" + "="*30)
        print(f"STARTING FOLD {i+1}/{n_splits}")
        print("="*30)

        # Clear session to keep the GPU memory fresh
        keras.backend.clear_session()

        model = model_class(input_shape=input_shape)

        # Start the high-speed training
        history = train_func(model, train_ds, val_ds, epochs=epochs)

        best_val_acc = max(history.history['val_accuracy'])
        all_val_accuracies.append(best_val_acc)
        
        # Save the model and validation dataset of the current fold for diagnostics
        last_model = model
        last_val_ds = val_ds
        
        print(f"Fold {i+1} Best Val Acc: {best_val_acc:.4f}")

    # Calculate the average across all folds
    mean_val_acc = np.mean(all_val_accuracies)

    print("\n" + "="*30)
    print(f"{model_type.upper()} CROSS-VALIDATION COMPLETE")
    print(f"Average Validation Accuracy: {mean_val_acc:.4f}")
    print("="*30)

    
    print("\n" + "="*30)
    print(f"DIAGNOSTIC RUN (USING FOLD {n_splits} VALIDATION DATA)")
    print("="*30)

    # Extract the true labels from the TensorFlow dataset
    y_true = []
    for x, y in last_val_ds:
        y_true.extend(y.numpy())
    y_true = np.array(y_true)
    
    # If labels are one-hot encoded, convert to 1D array
    if len(y_true.shape) > 1 and y_true.shape[1] > 1:
        y_true = np.argmax(y_true, axis=1)

    # Generate predictions
    y_pred_probs = last_model.predict(last_val_ds)
    y_pred = np.argmax(y_pred_probs, axis=1)

    emotions = ['Neutral', 'Calm', 'Happy', 'Sad', 'Angry', 'Fearful', 'Disgust', 'Surprised']

    # Classification Report
    print("CLASSIFICATION REPORT:")
    print(classification_report(y_true, y_pred, target_names=emotions, zero_division=0))

    # --- INFERENCE LATENCY ---
    # Grab one batch from the validation set, then extract just the first sample
    sample_batch, _ = next(iter(last_val_ds))
    single_sample = sample_batch[0:1] 
    
    start_time = time.time()
    _ = last_model.predict(single_sample, verbose=0)
    latency_ms = (time.time() - start_time) * 1000
    print(f"\n⚡ Inference Latency: {latency_ms:.2f} ms per sample\n")

    # Confusion Matrix
    cm = confusion_matrix(y_true, y_pred)

    plt.figure(figsize=(10,8))
    sns.heatmap(cm, annot=True, fmt='d', cmap=cmap_colour, xticklabels=emotions, yticklabels=emotions)
    plt.title(f"{model_type.upper()} Validation Confusion Matrix (Fold {n_splits})", fontsize=16)
    plt.ylabel('True Emotion', fontsize=12)
    plt.xlabel('Predicted Emotion', fontsize=12)
    plt.tight_layout()
    plt.show()

    # Return the mean validation accuracy as your "score to beat"
    return mean_val_acc, all_val_accuracies








