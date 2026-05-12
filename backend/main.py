import os
import json
import tempfile
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from random import randint
from urllib.parse import quote

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.exercises import build_guidance, personalise_guidance, synthesize_guidance_audio
from backend.inference import ModelUnavailableError, VividaInferenceEngine


def _load_local_env(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


ROOT_DIR = Path(__file__).resolve().parents[1]
_load_local_env(ROOT_DIR / ".env")
FRONTEND_DIR = ROOT_DIR / "frontend"
_load_local_env(FRONTEND_DIR / ".env.local")
DEBUG_AUDIO_DIR = Path(os.getenv("VIVIDA_DEBUG_AUDIO_DIR", ROOT_DIR / "debug_audio"))
TTS_RATE_LIMIT = int(os.getenv("VIVIDA_TTS_RATE_LIMIT", "6"))
TTS_RATE_WINDOW_SECONDS = int(os.getenv("VIVIDA_TTS_RATE_WINDOW_SECONDS", "3600"))
TTS_MAX_TEXT_CHARS = int(os.getenv("VIVIDA_TTS_MAX_TEXT_CHARS", "2200"))
_tts_rate_bucket: dict[str, list[float]] = {}

app = FastAPI(title="Vivida API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = VividaInferenceEngine(os.getenv("VIVIDA_MODEL_PATH"))


class TTSRequest(BaseModel):
    text: str


class NotificationSubscriptionRequest(BaseModel):
    subscription: dict
    reminder_hour_utc: int = 18
    user_agent: str = ""


class NotificationUnsubscribeRequest(BaseModel):
    endpoint: str


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "model_available": engine.model is not None,
        "model_path": str(engine.model_path) if engine.model_path else None,
        "classifier": engine._classifier_name() if engine.model is not None else None,
        "audio_storage": "ephemeral",
        "tts": "gemini" if os.getenv("GEMINI_API_KEY") else "browser_fallback",
        "push_notifications": "configured" if _vapid_public_key() else "missing_vapid",
    }


@app.post("/api/analyse")
async def analyse_audio(
    audio: UploadFile = File(...),
    session_id: str = Form("anonymous"),
    first_name: str = Form(""),
    transcript: str = Form(""),
    client_debug: str = Form(""),
) -> dict:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload.")

    suffix = Path(audio.filename or "recording.wav").suffix or ".wav"
    analysis_id = str(uuid.uuid4())
    temp_path = None
    debug_enabled = os.getenv("VIVIDA_DEBUG_AUDIO") == "1"

    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"vivida_{analysis_id}_",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = Path(temp_file.name)

        debug_upload_path = None
        if debug_enabled:
            DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            debug_upload_path = DEBUG_AUDIO_DIR / f"{analysis_id}_upload{suffix}"
            debug_upload_path.write_bytes(audio_bytes)
            print(f"Vivida debug: saved uploaded audio to {debug_upload_path}")

        try:
            prediction = engine.predict(temp_path)
        except ModelUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        debug_info = None
        if debug_enabled:
            client_debug_payload = None
            if client_debug:
                try:
                    client_debug_payload = json.loads(client_debug)
                except json.JSONDecodeError:
                    client_debug_payload = client_debug

            debug_info = {
                "analysis_id": analysis_id,
                "saved_upload_path": str(debug_upload_path) if debug_upload_path else None,
                "client_debug": client_debug_payload,
                "upload": {
                    "filename": audio.filename,
                    "content_type": audio.content_type,
                    "bytes": len(audio_bytes),
                    "temp_path": str(temp_path),
                },
                "model": {
                    "path": str(engine.model_path) if engine.model_path else None,
                    "classifier": engine._classifier_name(),
                    "available": engine.model is not None,
                },
                "preprocessing": engine.debug_audio(
                    temp_path,
                    output_dir=DEBUG_AUDIO_DIR,
                    analysis_id=analysis_id,
                ),
                "prediction": prediction,
            }
            debug_json_path = DEBUG_AUDIO_DIR / f"{analysis_id}_debug.json"
            debug_json_path.write_text(json.dumps(debug_info, indent=2))
            print(f"Vivida debug: wrote analysis trace to {debug_json_path}")

        guidance = build_guidance(
            first_name=first_name,
            transcript=transcript,
            emotion=prediction["emotion"],
            state=prediction["state"],
        )
        guidance = await personalise_guidance(
            first_name=first_name,
            transcript=transcript,
            emotion=prediction["emotion"],
            state=prediction["state"],
            guidance=guidance,
        )

        return {
            "analysis_id": analysis_id,
            "session_id": session_id,
            "transcript": transcript,
            "prediction": prediction,
            "guidance": guidance,
            "audio_deleted": True,
            "debug": debug_info,
            "created_at": _now(),
        }
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@app.post("/api/tts")
async def tts(request: Request, payload: TTSRequest) -> Response:
    _enforce_tts_rate_limit(_client_key(request))
    if len(payload.text or "") > TTS_MAX_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="TTS text is too long.")

    try:
        audio = await synthesize_guidance_audio(payload.text)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Gemini TTS unavailable: {exc.__class__.__name__}",
        ) from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/notifications/config")
def notification_config() -> dict:
    public_key = _vapid_public_key()
    return {
        "supported": bool(public_key),
        "publicKey": public_key,
    }


@app.post("/api/notifications/subscribe")
async def subscribe_notifications(
    request: Request,
    payload: NotificationSubscriptionRequest,
) -> dict:
    user = await _require_supabase_user(request)
    token = _supabase_bearer_token(request)
    subscription = payload.subscription
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Invalid push subscription.")

    reminder_hour = max(0, min(23, int(payload.reminder_hour_utc)))
    await _supabase_request(
        "POST",
        "/rest/v1/push_subscriptions?on_conflict=user_id,endpoint",
        body={
            "user_id": user["id"],
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "subscription": subscription,
            "user_agent": payload.user_agent[:500],
            "enabled": True,
            "daily_reminders_enabled": True,
            "reminder_hour_utc": reminder_hour,
            "motivation_enabled": True,
            "motivation_hour_utc": _random_motivation_hour(),
            "updated_at": _now(),
        },
        prefer="resolution=merge-duplicates,return=minimal",
        access_token=token,
    )
    return {"ok": True, "reminder_hour_utc": reminder_hour}


@app.post("/api/notifications/unsubscribe")
async def unsubscribe_notifications(
    request: Request,
    payload: NotificationUnsubscribeRequest,
) -> dict:
    user = await _require_supabase_user(request)
    token = _supabase_bearer_token(request)
    await _supabase_request(
        "PATCH",
        (
            "/rest/v1/push_subscriptions"
            f"?user_id=eq.{user['id']}&endpoint=eq.{_rest_filter_value(payload.endpoint)}"
        ),
        body={"enabled": False, "updated_at": _now()},
        prefer="return=minimal",
        access_token=token,
    )
    return {"ok": True}


@app.post("/api/notifications/test")
async def test_notification(request: Request) -> dict:
    user = await _require_supabase_user(request)
    token = _supabase_bearer_token(request)
    subscriptions = await _list_user_push_subscriptions(user["id"], token)
    if not subscriptions:
        raise HTTPException(status_code=404, detail="No active push subscription.")

    sent = 0
    for subscription in subscriptions:
        if await _send_subscription_notification(
            subscription,
            title="Vivida is here",
            message="Your gentle reminder is ready. One small check-in is enough.",
            tag="vivida-test",
            access_token=token,
        ):
            sent += 1

    if sent == 0:
        raise HTTPException(status_code=502, detail="No active push endpoint accepted the test.")

    return {"ok": True, "sent": sent}


@app.post("/api/notifications/run-daily-reminders")
async def run_daily_reminders(request: Request) -> dict:
    _require_cron_secret(request)
    reminder_subscriptions = await _list_due_push_subscriptions()
    motivation_subscriptions = await _list_due_motivation_subscriptions()
    today = date.today().isoformat()
    reminder_sent = 0
    reminder_skipped = 0
    motivation_sent = 0

    for subscription in reminder_subscriptions:
        user_id = subscription["user_id"]
        if await _has_checked_in_today(user_id, today):
            reminder_skipped += 1
            continue

        first_name = await _get_first_name(user_id)
        message = _daily_reminder_message(first_name)
        delivered = await _send_subscription_notification(
            subscription,
            title="A gentle check-in is ready",
            message=message,
            tag=f"vivida-daily-{today}",
        )
        if delivered:
            reminder_sent += 1
            await _mark_subscription_sent(subscription["id"], today)

    for subscription in motivation_subscriptions:
        first_name = await _get_first_name(subscription["user_id"])
        delivered = await _send_subscription_notification(
            subscription,
            title="In case you forgot",
            message=_motivational_message(first_name),
            tag=f"vivida-motivation-{today}",
        )
        if delivered:
            motivation_sent += 1
            await _mark_motivation_sent(subscription["id"], today)

    return {
        "ok": True,
        "reminders_checked": len(reminder_subscriptions),
        "reminders_sent": reminder_sent,
        "reminders_skipped": reminder_skipped,
        "motivations_checked": len(motivation_subscriptions),
        "motivations_sent": motivation_sent,
    }


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


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_tts_rate_limit(client_key: str) -> None:
    now = time.time()
    window_start = now - TTS_RATE_WINDOW_SECONDS
    recent_calls = [
        timestamp
        for timestamp in _tts_rate_bucket.get(client_key, [])
        if timestamp >= window_start
    ]

    if len(recent_calls) >= TTS_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Voice guide limit reached. Please try again later.",
        )

    recent_calls.append(now)
    _tts_rate_bucket[client_key] = recent_calls


def _vapid_public_key() -> str:
    return os.getenv("VAPID_PUBLIC_KEY", "").strip()


def _vapid_private_key() -> str:
    return os.getenv("VAPID_PRIVATE_KEY", "").strip()


def _vapid_claim_email() -> str:
    return os.getenv("VAPID_CLAIM_EMAIL", "admin@vivida.app").strip()


def _vapid_claim_subject() -> str:
    claim = _vapid_claim_email()
    if claim.startswith(("mailto:", "https://", "http://")):
        return claim
    return f"mailto:{claim}"


def _supabase_url() -> str:
    return os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")


def _supabase_service_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def _supabase_auth_key() -> str:
    return (
        os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or _supabase_service_key()
    )


def _supabase_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Supabase session.")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Supabase session.")
    return token


async def _require_supabase_user(request: Request) -> dict:
    token = _supabase_bearer_token(request)

    supabase_url = _supabase_url()
    auth_key = _supabase_auth_key()
    if not supabase_url or not auth_key:
        raise HTTPException(status_code=503, detail="Supabase auth is not configured.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": auth_key,
                "Authorization": f"Bearer {token}",
            },
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Invalid Supabase session.")

    user = response.json()
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid Supabase session.")
    return user


def _require_cron_secret(request: Request) -> None:
    expected = os.getenv("VIVIDA_CRON_SECRET", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Cron secret is not configured.")

    supplied = request.headers.get("x-cron-secret", "")
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        supplied = auth_header.split(" ", 1)[1].strip()

    if supplied != expected:
        raise HTTPException(status_code=401, detail="Invalid cron secret.")


async def _supabase_request(
    method: str,
    path: str,
    *,
    body: object | None = None,
    prefer: str | None = None,
    access_token: str | None = None,
) -> object:
    supabase_url = _supabase_url()
    api_key = _supabase_auth_key() if access_token else _supabase_service_key()
    if not supabase_url or not api_key:
        detail = (
            "Supabase auth is not configured."
            if access_token
            else "Supabase service access is not configured."
        )
        raise HTTPException(status_code=503, detail=detail)

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {access_token or api_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.request(
            method,
            f"{supabase_url.rstrip('/')}{path}",
            headers=headers,
            json=body,
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Supabase request failed.")
    if response.content:
        try:
            return response.json()
        except json.JSONDecodeError:
            return {}
    return {}


def _rest_filter_value(value: str) -> str:
    return quote(value, safe="")


async def _list_user_push_subscriptions(
    user_id: str,
    access_token: str | None = None,
) -> list[dict]:
    result = await _supabase_request(
        "GET",
        (
            "/rest/v1/push_subscriptions"
            "?select=id,user_id,endpoint,p256dh,auth,subscription"
            f"&user_id=eq.{user_id}&enabled=eq.true"
        ),
        access_token=access_token,
    )
    return result if isinstance(result, list) else []


async def _list_due_push_subscriptions() -> list[dict]:
    current_hour = datetime.now(timezone.utc).hour
    today = date.today().isoformat()
    result = await _supabase_request(
        "GET",
        (
            "/rest/v1/push_subscriptions"
            "?select=id,user_id,endpoint,p256dh,auth,subscription,reminder_hour_utc,last_sent_date"
            "&enabled=eq.true&daily_reminders_enabled=eq.true"
            f"&reminder_hour_utc=lte.{current_hour}"
            f"&or=(last_sent_date.is.null,last_sent_date.neq.{today})"
        ),
    )
    return result if isinstance(result, list) else []


async def _list_due_motivation_subscriptions() -> list[dict]:
    current_hour = datetime.now(timezone.utc).hour
    today = date.today().isoformat()
    result = await _supabase_request(
        "GET",
        (
            "/rest/v1/push_subscriptions"
            "?select=id,user_id,endpoint,p256dh,auth,subscription,motivation_hour_utc,last_motivation_sent_date"
            "&enabled=eq.true&motivation_enabled=eq.true"
            f"&motivation_hour_utc=lte.{current_hour}"
            f"&or=(last_motivation_sent_date.is.null,last_motivation_sent_date.neq.{today})"
        ),
    )
    return result if isinstance(result, list) else []


async def _has_checked_in_today(user_id: str, activity_date: str) -> bool:
    result = await _supabase_request(
        "GET",
        (
            "/rest/v1/daily_activity"
            "?select=check_in_count"
            f"&user_id=eq.{user_id}&activity_date=eq.{activity_date}"
            "&limit=1"
        ),
    )
    if not isinstance(result, list) or not result:
        return False
    return int(result[0].get("check_in_count") or 0) > 0


async def _get_first_name(user_id: str) -> str:
    result = await _supabase_request(
        "GET",
        f"/rest/v1/user_profile?select=first_name&id=eq.{user_id}&limit=1",
    )
    if isinstance(result, list) and result:
        return str(result[0].get("first_name") or "").strip()[:40]
    return ""


async def _mark_subscription_sent(subscription_id: str, sent_date: str) -> None:
    await _supabase_request(
        "PATCH",
        f"/rest/v1/push_subscriptions?id=eq.{subscription_id}",
        body={"last_sent_date": sent_date, "updated_at": _now()},
        prefer="return=minimal",
    )


async def _mark_motivation_sent(subscription_id: str, sent_date: str) -> None:
    await _supabase_request(
        "PATCH",
        f"/rest/v1/push_subscriptions?id=eq.{subscription_id}",
        body={
            "last_motivation_sent_date": sent_date,
            "motivation_hour_utc": _random_motivation_hour(),
            "updated_at": _now(),
        },
        prefer="return=minimal",
    )


async def _disable_push_subscription(
    subscription_id: str,
    access_token: str | None = None,
) -> None:
    await _supabase_request(
        "PATCH",
        f"/rest/v1/push_subscriptions?id=eq.{subscription_id}",
        body={"enabled": False, "updated_at": _now()},
        prefer="return=minimal",
        access_token=access_token,
    )


async def _send_subscription_notification(
    subscription: dict,
    *,
    title: str,
    message: str,
    tag: str,
    access_token: str | None = None,
) -> bool:
    if not _vapid_public_key() or not _vapid_private_key():
        raise HTTPException(status_code=503, detail="VAPID keys are not configured.")

    subscription_info = subscription.get("subscription") or {
        "endpoint": subscription.get("endpoint"),
        "keys": {
            "p256dh": subscription.get("p256dh"),
            "auth": subscription.get("auth"),
        },
    }
    payload = json.dumps(
        {
            "title": title,
            "message": message,
            "tag": tag,
            "url": "/check-in",
            "interaction": False,
        }
    )

    try:
        from pywebpush import WebPushException, webpush

        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=_vapid_private_key(),
            vapid_claims={"sub": _vapid_claim_subject()},
        )
        return True
    except Exception as exc:
        if exc.__class__.__name__ == "WebPushException":
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in {400, 401, 403, 404, 410} and subscription.get("id"):
                await _disable_push_subscription(subscription["id"], access_token)
            return False
        raise HTTPException(
            status_code=502,
            detail=f"Push send failed: {exc.__class__.__name__}",
        ) from exc


def _daily_reminder_message(first_name: str) -> str:
    name = _clean_notification_name(first_name)
    prefix = f"{name}, your lotus could use a little light today." if name else "Your lotus could use a little light today."
    return f"{prefix} One gentle check-in is enough."


def _motivational_message(first_name: str) -> str:
    name = _clean_notification_name(first_name)
    if name:
        return (
            f"In case you forgot {name}, you are absolutely capable of creating "
            "the version of you that you can't stop thinking about."
        )
    return (
        "In case you forgot, you are absolutely capable of creating the version "
        "of you that you can't stop thinking about."
    )


def _random_motivation_hour() -> int:
    return randint(9, 20)


def _clean_notification_name(first_name: str) -> str:
    return "".join(ch for ch in first_name if ch.isalpha() or ch in "'-").strip()[:32]
