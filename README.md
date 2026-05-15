# Vivida

Vivida is a mobile-first Progressive Web App for speech-aware wellbeing support.
It combines a Speech Emotion Recognition experiment pipeline with a Next.js PWA,
Supabase authentication/database storage, and a FastAPI machine learning service.
Users can record a short spoken check-in, receive an emotion prediction, and view a
Compassion Focused Therapy-informed guided exercise mapped to threat, drive, or soothing.

Raw audio is processed temporarily for inference and is not stored in the database.
Only derived metadata, such as predicted emotion, mapped state, model information,
latency, exercise title, feedback, and activity counts, is retained.

## Run Locally

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

By default, the deployed backend is configured to use the selected Wav2Vec2 model at:

```text
ml_engine/results/wav2vec2_best
```

The model path can be overridden with:

```bash
export VIVIDA_MODEL_PATH=/path/to/model
```

External services require environment variables when used:

```text
GEMINI_API_KEY
ELEVENLABS_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Frontend Supabase configuration is provided through `NEXT_PUBLIC_*` variables.

## Supabase Tables

The live Supabase project uses:

- `user_profile`: user profile, first name or nickname, onboarding state, and lotus streak state.
- `gse_assessments`: General Self-Efficacy Scale responses.
- `check_ins`: derived inference outputs only; no raw audio and no transcript by default.
- `exercise_feedback`: 1-3 star helpfulness ratings after exercises.
- `daily_activity`: daily check-in/exercise counts for the lotus trail.
- `push_subscriptions`: browser push notification subscription metadata.

## Train and Evaluate Models

```bash
python3 ml_engine/src/helper_functions/run_experiement.py mlp --splits 5 --epochs 100
python3 ml_engine/src/helper_functions/run_experiement.py cnn_lstm --splits 5 --epochs 100
python3 ml_engine/src/helper_functions/run_experiement.py wav2vec2 --splits 5 --epochs 5 --batch-size 8
```

Each run writes metrics, held-out test scores, latency, confusion matrices where supported,
and saved model artifacts to `ml_engine/results/`.

## Testing and Deployment

Backend tests can be run with:

```bash
pytest tests/backend
```

The GitHub Actions workflow runs frontend lint/build checks, backend tests, and a
Docker build check. The backend deployment uses `Dockerfile.backend` and `render.yaml`.
