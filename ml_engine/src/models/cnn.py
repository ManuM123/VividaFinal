import keras
from keras import layers, models
import time


class CNN(keras.Model):
    def __init__(self, input_shape=(128,126,1), num_classes=8):
        super(CNN, self).__init__()
        
        self.model = models.Sequential([

            layers.InputLayer(input_shape=input_shape),
            layers.BatchNormalization(),

            # Basic edges
            layers.Conv2D(32, (3,3), activation='relu', padding='same'),
            layers.MaxPooling2D(pool_size=(2,2)),
            layers.Dropout(0.2),

            # Textures
            layers.Conv2D(64, (3,3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.MaxPooling2D(pool_size=(2,2)),
            layers.Dropout(0.3),

            # Simple shapes
            layers.Conv2D(128, (3,3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.MaxPooling2D(pool_size=(2,2)),
            layers.Dropout(0.4),

            layers.Conv2D(256, (3,3), activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.MaxPooling2D(pool_size=(2,2)),
            layers.Dropout(0.5),

            layers.GlobalAveragePooling2D(),

            layers.Dense(128, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            layers.Dense(num_classes, activation='softmax')
        ])

    def call(self, x):
        return self.model(x)


def train_cnn(model, train_ds, val_ds, epochs=100, lr=0.0003):
    
    callbacks = [
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, min_lr=0.00001),

        keras.callbacks.EarlyStopping(monitor='val_loss', patience=25, restore_best_weights=True),

        keras.callbacks.LambdaCallback(on_epoch_end=lambda epoch, logs: print(
            f"Epoch {epoch+1:02d}: Train Acc: {logs['accuracy']:.4f} | Val Acc: {logs['val_accuracy']:.4f} | Loss: {logs['loss']:.4f}"
        ) if (epoch+1) % 10 == 0 or epoch == 0 else None)
    ]

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=lr),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )

    print("STARTING CNN TRAINING")

    history = model.fit(train_ds, validation_data=val_ds, epochs=epochs,callbacks=callbacks,verbose=0)

    print("CNN TRAINING COMPLETE")

    return history