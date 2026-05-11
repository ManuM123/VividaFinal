import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.exercises import build_guidance
from backend.inference import ModelUnavailableError, VividaInferenceEngine


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="Vivida API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = VividaInferenceEngine(os.getenv("VIVIDA_MODEL_PATH"))


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "model_available": engine.model is not None,
        "model_path": str(engine.model_path) if engine.model_path else None,
        "classifier": engine._classifier_name() if engine.model is not None else None,
        "audio_storage": "ephemeral",
    }


@app.post("/api/analyse")
async def analyse_audio(
    audio: UploadFile = File(...),
    session_id: str = Form("anonymous"),
    first_name: str = Form(""),
    transcript: str = Form(""),
) -> dict:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload.")

    suffix = Path(audio.filename or "recording.wav").suffix or ".wav"
    analysis_id = str(uuid.uuid4())
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"vivida_{analysis_id}_",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = Path(temp_file.name)

        try:
            prediction = engine.predict(temp_path)
        except ModelUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        guidance = build_guidance(
            first_name=first_name,
            transcript=transcript,
            emotion=prediction["emotion"],
            state=prediction["state"],
        )

        return {
            "analysis_id": analysis_id,
            "session_id": session_id,
            "transcript": transcript,
            "prediction": prediction,
            "guidance": guidance,
            "audio_deleted": True,
            "created_at": _now(),
        }
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.get("/")
def index():
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    return {
        "service": "Vivida ML API",
        "frontend": "Run the Next.js app from the frontend/ directory.",
    }


@app.get("/{path:path}")
def pwa_files(path: str):
    file_path = FRONTEND_DIR / path
    if FRONTEND_DIR.exists() and file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    raise HTTPException(status_code=404, detail="Not found")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
