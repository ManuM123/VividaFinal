# Vivida

Vivida is a mobile-first PWA for speech-aware stress support and self-efficacy evaluation.
It combines a speech emotion recognition experiment pipeline with a Next.js PWA, Supabase
participant data storage, and a FastAPI ML service. Raw audio is processed ephemerally for
inference and deleted immediately after feature extraction/prediction.

## Run the MVP

Install backend runtime dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the ML API:

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Run the PWA:

```bash
cd frontend
npm run dev
```

Open http://localhost:3000.

The app will use the best saved Keras model if one exists in `ml_engine/results/`.
The final study build should use the selected trained model artifact as the backend model.

## Supabase Tables

The live Supabase project uses:

- `user_profile`: participant profile, nickname/first name, onboarding answers, and lotus streak state.
- `gse_assessments`: baseline General Self-Efficacy Scale responses only.
- `check_ins`: derived inference outputs only; no raw audio and no transcript by default.
- `exercise_feedback`: 1-3 star helpfulness ratings after exercises.
- `daily_activity`: daily check-in/exercise counts for the lotus trail.

## Train and Evaluate Models

```bash
python3 ml_engine/src/helper_functions/run_experiement.py mlp --splits 5 --epochs 100
python3 ml_engine/src/helper_functions/run_experiement.py cnn_2d --splits 5 --epochs 100
python3 ml_engine/src/helper_functions/run_experiement.py cnn_lstm --splits 5 --epochs 100
python3 ml_engine/src/helper_functions/run_experiement.py ast --splits 5 --epochs 5 --batch-size 8
```

Each run writes metrics, held-out test scores, latency, confusion matrices where supported,
and saved model artifacts to `ml_engine/results/`.
