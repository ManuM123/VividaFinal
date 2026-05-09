import keras
from keras import layers, models, regularizers

class Hybrid_CNN_LSTM(keras.Model):
    def __init__(self, input_shape=(180,126,1), num_classes=8):
        super(Hybrid_CNN_LSTM, self).__init__()

        inputs = layers.Input(shape=input_shape)
        weight_decay = 1e-4

        # CNN (Processes the mel spectrogram)
        cnn_in = layers.Lambda(lambda x: x[:, :128, :, :], name="Mel_Slicer")(inputs)

        x = layers.BatchNormalization()(cnn_in)

        x = layers.Conv2D(32, (3,3), activation='relu', padding='same',
                          kernel_regularizer=regularizers.l2(weight_decay))(x)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(32, (3,3), activation='relu', padding='same',
                          kernel_regularizer=regularizers.l2(weight_decay))(x)
        x = layers.MaxPooling2D(pool_size=(2,2))(x)
        x = layers.SpatialDropout2D(0.10)(x)

        x = layers.Conv2D(64, (3,3), activation='relu', padding='same',
                          kernel_regularizer=regularizers.l2(weight_decay))(x)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(64, (3,3), activation='relu', padding='same',
                          kernel_regularizer=regularizers.l2(weight_decay))(x)
        x = layers.MaxPooling2D(pool_size=(2,2))(x)
        x = layers.SpatialDropout2D(0.15)(x)

        x = layers.Conv2D(128, (3,3), activation='relu', padding='same',
                          kernel_regularizer=regularizers.l2(weight_decay))(x)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(128, (3,3), activation='relu', padding='same',
                          kernel_regularizer=regularizers.l2(weight_decay))(x)
        x = layers.MaxPooling2D(pool_size=(2,2))(x)
        x = layers.SpatialDropout2D(0.20)(x)

        x = layers.Conv2D(256, (3,3), activation='relu', padding='same',
                          kernel_regularizer=regularizers.l2(weight_decay))(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D(pool_size=(2,2))(x)
        x = layers.SpatialDropout2D(0.25)(x)

        cnn_out = layers.GlobalAveragePooling2D()(x)

        # LSTM (Processes the MFCCs & Chroma)
        lstm_in = layers.Lambda(lambda x: x[:, 128:, :, :], name="MFCC_Chroma_Slicer")(inputs)

        lstm_norm = layers.BatchNormalization()(lstm_in)

        y = layers.Reshape((52,126))(lstm_norm)
        y = layers.Permute((2,1))(y)

        y = layers.Bidirectional(layers.LSTM(96, return_sequences=True))(y)
        y = layers.Dropout(0.2)(y)
        y = layers.Bidirectional(layers.LSTM(64))(y)
        lstm_out = layers.Dropout(0.2)(y)

        # Concatenating together
        fused = layers.Concatenate()([cnn_out, lstm_out])

        z = layers.Dense(256, activation='relu', kernel_regularizer=regularizers.l2(weight_decay))(fused)
        z = layers.BatchNormalization()(z)
        z = layers.Dropout(0.35)(z)
        z = layers.Dense(128, activation='relu', kernel_regularizer=regularizers.l2(weight_decay))(z)
        z = layers.BatchNormalization()(z)
        z = layers.Dropout(0.25)(z)
        outputs = layers.Dense(num_classes, activation='softmax')(z)

        self.model = models.Model(inputs=inputs, outputs=outputs)

    def call(self, x):
        return self.model(x)
    

def train_hybrid_cnn_lstm(model, train_ds, val_ds, epochs=100, lr=0.0003, class_weight=None):

    callbacks = [
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=0.00001),

        keras.callbacks.EarlyStopping(monitor='val_loss', patience=18, restore_best_weights=True),

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

    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        callbacks=callbacks,
        class_weight=class_weight,
        verbose=0
    )

    print("CNN TRAINING COMPLETE")

    return history
