import tensorflow as tf
import keras
from keras import Model, Sequential


class MLP(Model):
    
    def __init__(self, input_shape: tuple[int, int] = (128, 126), hidden_dims: list[int] = [512, 256, 128], output_dim: int = 8, dropout_rate: float = 0.3):
        super(MLP, self).__init__()

        layers = []

        # input layer
        layers.append(keras.Input(shape=input_shape)) # represents our 128 x 126 spectrogram image
        layers.append(keras.layers.Flatten())   # flatten the 2d image into a 1d vector

        # 3 hidden layers
        for hidden_dim in hidden_dims:
            layers.append(keras.layers.Dense(hidden_dim, activation='relu'))
            layers.append(keras.layers.BatchNormalization())
            layers.append(keras.layers.Dropout(dropout_rate))

        # output layer
        layers.append(keras.layers.Dense(output_dim, activation='softmax'))
        
        self.network = Sequential(layers)

    def call(self, x):
        return self.network(x)


def train_mlp(model, train_ds, val_ds, epochs=50, lr=0.001):

    callbacks = [
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=0.00001),

        keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),

        keras.callbacks.LambdaCallback(on_epoch_end=lambda epoch, logs: print(
            f"Epoch {epoch+1:02d}: Train Acc: {logs['accuracy']:.4f} | Val Acc: {logs['val_accuracy']:.4f} | Loss: {logs['loss']:.4f}"
        )
        if (epoch +1) % 10 == 0 or epoch == 0 else None
        
        )
    ]

    model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=lr), 
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
    )

    print(f"STARTING MLP TRAINING")

    history = model.fit(
        train_ds, 
        validation_data=val_ds,
        epochs=epochs,
        callbacks=callbacks,
        verbose=0
    )

    print("MLP TRAINING COMPLETE")

    return history










