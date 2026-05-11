"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AudioLines, HeartPulse, Play, RotateCcw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { createClient } from "@/utils/supabase/client";
import {
  AppShell,
  BreathStage,
  LotusProgress,
  Metric,
} from "../components";
import {
  AnalyseResponse,
  EMPTY_ENGAGEMENT,
  EngagementSummary,
  SpeechRecognition,
  SpeechRecognitionConstructor,
  calculateStreak,
  parseDateList,
  stateClass,
  titleCase,
  todayKey,
} from "../static_data_and_types";

declare global {
  interface Window {
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitAudioContext?: typeof AudioContext;
  }
}

const supabase = createClient();
const ML_API_URL = process.env.NEXT_PUBLIC_ML_API_URL || "http://127.0.0.1:8000";
const CONSENT_KEY = "vivida_voice_consent_v1";

export default function CheckInPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [firstName, setFirstName] = useState("");
  const [transcript, setTranscript] = useState("");
  const [status, setStatus] = useState("Ready");
  const [isRecording, setIsRecording] = useState(false);
  const [result, setResult] = useState<AnalyseResponse | null>(null);
  const [savedCheckInId, setSavedCheckInId] = useState<string | null>(null);
  const [feedbackScore, setFeedbackScore] = useState<number | null>(null);
  const [hoveredFeedbackScore, setHoveredFeedbackScore] = useState<number | null>(null);
  const [feedbackSaved, setFeedbackSaved] = useState(false);
  const [hasVoiceConsent, setHasVoiceConsent] = useState(
    () => typeof window !== "undefined" && window.localStorage.getItem(CONSENT_KEY) === "accepted",
  );
  const [engagement, setEngagement] = useState<EngagementSummary>(EMPTY_ENGAGEMENT);
  const [streakDates, setStreakDates] = useState<string[]>([]);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const loadEngagement = useCallback(async (activeUserId: string) => {
    const today = todayKey();
    const [
      { data: activityRows },
      { data: feedbackRows },
      { data: checkInRows },
      { data: profile },
    ] = await Promise.all([
      supabase
        .from("daily_activity")
        .select("activity_date, check_in_count, completed_exercise_count")
        .eq("user_id", activeUserId)
        .order("activity_date", { ascending: false }),
      supabase.from("exercise_feedback").select("helpfulness_score").eq("user_id", activeUserId),
      supabase.from("check_ins").select("id").eq("user_id", activeUserId),
      supabase
        .from("user_profile")
        .select("current_streak, streak_dates")
        .eq("id", activeUserId)
        .maybeSingle(),
    ]);

    const todayActivity = activityRows?.find((row) => row.activity_date === today);
    const starsEarned =
      feedbackRows?.reduce((sum, row) => sum + Number(row.helpfulness_score || 0), 0) || 0;
    const exercisesRated = feedbackRows?.length || 0;
    const dates = parseDateList(profile?.streak_dates);

    setStreakDates(dates);
    setEngagement({
      currentStreak: Number(profile?.current_streak || calculateStreak(dates)),
      todayCheckIns: Number(todayActivity?.check_in_count || 0),
      totalCheckIns: checkInRows?.length || 0,
      exercisesRated,
      starsEarned,
      maxStars: exercisesRated * 3,
    });
  }, []);

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data }) => {
      if (!data.user) {
        router.replace("/");
        return;
      }

      const { data: assessment } = await supabase
        .from("gse_assessments")
        .select("score")
        .eq("user_id", data.user.id)
        .eq("phase", "baseline")
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (!assessment) {
        router.replace("/onboarding");
        return;
      }

      const { data: profile } = await supabase
        .from("user_profile")
        .select("first_name")
        .eq("id", data.user.id)
        .maybeSingle();

      setUserId(data.user.id);
      setFirstName(profile?.first_name || "");
      await loadEngagement(data.user.id);
      setStatus("Ready");
    });
  }, [loadEngagement, router]);

  async function startRecording() {
    if (!hasVoiceConsent) {
      setStatus("Consent required");
      return;
    }

    try {
      vibrate([20, 30, 20]);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = handleRecordingStop;
      recorder.start();
      startSpeechRecognition();
      setIsRecording(true);
      setStatus("Listening");
      setResult(null);
    } catch {
      setStatus("Microphone unavailable");
    }
  }

  function stopRecording() {
    vibrate([35, 35, 35]);
    recognitionRef.current?.stop();
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    setStatus("Analysing");
  }

  async function handleRecordingStop() {
    streamRef.current?.getTracks().forEach((track) => track.stop());

    try {
      const blob = new Blob(chunksRef.current, {
        type: mediaRecorderRef.current?.mimeType || "audio/webm",
      });
      const wavBlob = await convertToWav(blob);
      const data = await analyseRecording(wavBlob);
      const checkInId = await saveCheckIn(data);
      if (!checkInId) {
        throw new Error("Could not save check-in metadata");
      }
      await recordDailyActivity("checkin");
      setSavedCheckInId(checkInId);
      setFeedbackScore(null);
      setFeedbackSaved(false);
      setResult(data);
      vibrate(data.guidance.haptics || [25, 35, 25]);
      setStatus("Guidance ready");
      if (userId) {
        await loadEngagement(userId);
      }
    } catch (error) {
      console.error(error);
      setStatus(error instanceof Error ? error.message : "Analysis failed");
    }
  }

  async function analyseRecording(wavBlob: Blob) {
    const form = new FormData();
    form.append("audio", wavBlob, "vivida-checkin.wav");
    form.append("session_id", userId || "anonymous");
    form.append("first_name", firstName);
    form.append("transcript", transcript.trim());

    const response = await fetch(`${ML_API_URL}/api/analyse`, {
      method: "POST",
      body: form,
    });

    if (!response.ok) {
      let message = "Analysis request failed";
      try {
        const errorBody = (await response.json()) as { detail?: string };
        message = errorBody.detail || message;
      } catch {
        message = `${message} (${response.status})`;
      }
      throw new Error(message);
    }
    return (await response.json()) as AnalyseResponse;
  }

  async function saveCheckIn(data: AnalyseResponse) {
    if (!userId) {
      return null;
    }

    const { data: row, error } = await supabase
      .from("check_ins")
      .insert({
        user_id: userId,
        predicted_emotion: data.prediction.emotion,
        predicted_state: data.prediction.state.key,
        confidence: data.prediction.confidence,
        classifier: data.prediction.classifier,
        model_version: data.prediction.model_path || data.prediction.classifier,
        latency_ms: data.prediction.latency_ms,
        exercise_key: data.prediction.state.key,
        exercise_title: data.guidance.title,
        raw_prediction: data.prediction,
        audio_deleted: true,
      })
      .select("id")
      .single();

    if (error) {
      setStatus(error.message);
      return null;
    }

    return (row?.id as string | undefined) || null;
  }

  async function saveFeedback(scoreValue: number) {
    if (!userId || !savedCheckInId) {
      return;
    }

    setFeedbackScore(scoreValue);
    const { error } = await supabase.from("exercise_feedback").insert({
      user_id: userId,
      check_in_id: savedCheckInId,
      helpfulness_score: scoreValue,
    });

    if (error) {
      setStatus(error.message);
      return;
    }

    await recordDailyActivity("exercise");
    await loadEngagement(userId);
    setFeedbackSaved(true);
    setStatus("Feedback saved");
  }

  async function recordDailyActivity(kind: "checkin" | "exercise") {
    if (!userId) {
      return;
    }

    const today = todayKey();
    const { data: existing } = await supabase
      .from("daily_activity")
      .select("id, check_in_count, completed_exercise_count")
      .eq("user_id", userId)
      .eq("activity_date", today)
      .maybeSingle();

    if (existing) {
      await supabase
        .from("daily_activity")
        .update({
          check_in_count:
            Number(existing.check_in_count || 0) + (kind === "checkin" ? 1 : 0),
          completed_exercise_count:
            Number(existing.completed_exercise_count || 0) +
            (kind === "exercise" ? 1 : 0),
          updated_at: new Date().toISOString(),
        })
        .eq("id", existing.id);
    } else {
      await supabase.from("daily_activity").insert({
        user_id: userId,
        activity_date: today,
        check_in_count: kind === "checkin" ? 1 : 0,
        completed_exercise_count: kind === "exercise" ? 1 : 0,
      });
    }

    if (kind === "checkin") {
      const dates = Array.from(new Set([...streakDates, today])).sort();
      const currentStreak = calculateStreak(dates);
      setStreakDates(dates);
      setEngagement((current) => ({ ...current, currentStreak }));
      await supabase
        .from("user_profile")
        .update({
          current_streak: currentStreak,
          last_active_date: today,
          streak_dates: dates,
          updated_at: new Date().toISOString(),
        })
        .eq("id", userId);
    }
  }

  function startSpeechRecognition() {
    const SpeechRecognitionClass =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionClass) {
      return;
    }

    const recognition = new SpeechRecognitionClass();
    recognitionRef.current = recognition;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-GB";
    let finalTranscript = transcript.trim();

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript = `${finalTranscript} ${text}`.trim();
        } else {
          interim += text;
        }
      }
      setTranscript(`${finalTranscript} ${interim}`.trim());
    };
    recognition.start();
  }

  function playGuide() {
    if (!result?.guidance.voice_script || !("speechSynthesis" in window)) {
      return;
    }
    window.speechSynthesis.cancel();
    vibrate(result.guidance.haptics || [20, 40, 20]);
    const utterance = new SpeechSynthesisUtterance(result.guidance.voice_script);
    utterance.rate = 0.92;
    utterance.pitch = 0.96;
    window.speechSynthesis.speak(utterance);
  }

  return (
    <AppShell title={result ? "Guided reset" : "Voice check-in"} status={status} showNav>
      {!result && (
        <section className="grid gap-4 rounded-lg border border-[var(--line)] bg-white p-4 shadow-xl shadow-purple-950/5">
          <LotusProgress engagement={engagement} />
          {!hasVoiceConsent && (
            <div className="rounded-lg border border-[var(--line)] bg-[var(--sage-soft)] p-4">
              <p className="text-xs font-black uppercase text-[var(--sage)]">
                Voice privacy
              </p>
              <p className="mt-2 text-sm leading-6">
                Vivida sends your recording to the ML backend only for emotion
                analysis. The raw audio is deleted after processing; the app
                stores only the predicted emotion, state, confidence, latency,
                and your exercise feedback.
              </p>
              <Button
                className="mt-3 h-11 w-full rounded-lg bg-[var(--sage)] font-black text-white"
                onClick={() => {
                  window.localStorage.setItem(CONSENT_KEY, "accepted");
                  setHasVoiceConsent(true);
                  setStatus("Ready");
                }}
              >
                I understand
              </Button>
            </div>
          )}
          <BreathStage active={isRecording} label={isRecording ? "Recording" : "Ready"} />
          {transcript && (
            <p className="rounded-lg border border-[var(--line)] bg-[#fffcff] px-4 py-3 text-sm leading-6">
              {transcript}
            </p>
          )}
          <Button
            className={`flex h-14 items-center justify-center gap-3 rounded-lg font-black text-white ${
              isRecording ? "bg-[var(--foreground)]" : "bg-[var(--lotus)]"
            }`}
            disabled={!hasVoiceConsent}
            onClick={isRecording ? stopRecording : startRecording}
          >
            <AudioLines className="h-5 w-5" aria-hidden="true" />
            {isRecording ? "Stop" : "Start"}
          </Button>
        </section>
      )}

      {result && (
        <section className="grid gap-4 rounded-lg border border-[var(--line)] bg-white p-4 shadow-xl shadow-purple-950/5">
          <div className={`rounded-lg p-4 ${stateClass(result.prediction.state.key)}`}>
            <p className="text-xs font-black uppercase">Detected state</p>
            <h2 className="mt-1 text-3xl font-black">{result.prediction.state.name}</h2>
            <p className="mt-2 leading-6">{result.prediction.state.summary}</p>
          </div>

          <div className="grid grid-cols-3 gap-2 max-[460px]:grid-cols-1">
            <Metric label="Emotion" value={titleCase(result.prediction.emotion)} />
            <Metric label="Confidence" value={`${Math.round(result.prediction.confidence * 100)}%`} />
            <Metric label="Latency" value={`${Math.round(result.prediction.latency_ms)} ms`} />
          </div>

          <ExerciseGuide result={result} />

          <div className="rounded-lg border border-[var(--line)] p-4">
            <p className="text-xs font-black uppercase">How helpful was this?</p>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {[1, 2, 3].map((value) => (
                <Button
                  className={`h-14 rounded-lg border font-black transition-colors ${
                    value <= (hoveredFeedbackScore || feedbackScore || 0)
                      ? "border-[var(--amber)] bg-[var(--amber-soft)] text-[var(--foreground)]"
                      : "border-[var(--line)] bg-[var(--amber-soft)]/35 text-[var(--muted-foreground)]"
                  }`}
                  key={value}
                  disabled={feedbackSaved}
                  onMouseEnter={() => setHoveredFeedbackScore(value)}
                  onMouseLeave={() => setHoveredFeedbackScore(null)}
                  onFocus={() => setHoveredFeedbackScore(value)}
                  onBlur={() => setHoveredFeedbackScore(null)}
                  onClick={() => saveFeedback(value)}
                >
                  ★
                </Button>
              ))}
            </div>
            {feedbackSaved && (
              <p className="mt-3 text-sm font-bold text-[var(--sage)]">
                Saved. Your lotus trail gained another petal.
              </p>
            )}
          </div>

          <div className="grid grid-cols-[1fr_auto] gap-3 max-[460px]:grid-cols-1">
            <Button
              className="flex h-12 items-center justify-center gap-2 rounded-lg bg-[var(--lavender)] font-black text-white"
              onClick={playGuide}
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              Play guide
            </Button>
            <Button
              className="flex h-12 items-center justify-center gap-2 rounded-lg border border-[var(--line)] bg-white px-5 font-black"
              onClick={() => {
                setTranscript("");
                setResult(null);
              }}
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              New check-in
            </Button>
          </div>
        </section>
      )}
    </AppShell>
  );
}

function ExerciseGuide({ result }: { result: AnalyseResponse }) {
  const phases = result.guidance.phases || [];
  const [activePhase, setActivePhase] = useState(0);
  const selectedPhase = phases[activePhase];

  function selectPhase(index: number) {
    setActivePhase(index);
    vibrate(result.guidance.haptics || [20, 40, 20]);
  }

  return (
    <div className="rounded-lg border border-[var(--line)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase text-[var(--lavender)]">Exercise</p>
          <h2 className="mt-1 text-2xl font-black">{result.guidance.title}</h2>
          {result.guidance.subtitle && (
            <p className="mt-2 text-sm font-bold leading-5 text-[var(--muted-foreground)]">
              {result.guidance.subtitle}
            </p>
          )}
        </div>
        <button
          aria-label="Play haptic cue"
          className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-[var(--lavender-soft)] text-[var(--lavender-dark)]"
          type="button"
          onClick={() => vibrate(result.guidance.haptics || [20, 40, 20])}
        >
          <HeartPulse className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
      <p className="mt-3 leading-6">{result.guidance.intro}</p>
      <ExerciseMotion
        animation={result.guidance.animation}
        stateKey={result.prediction.state.key}
      />
      {phases.length > 0 && (
        <div className="mt-4">
          <div className="grid grid-cols-3 gap-2 max-[460px]:grid-cols-1">
            {phases.map((phase, index) => (
              <button
                className={`min-h-12 rounded-lg border px-3 py-2 text-sm font-black ${
                  index === activePhase
                    ? "border-[var(--lavender)] bg-[var(--lavender-soft)] text-[var(--lavender-dark)]"
                    : "border-[var(--line)] bg-white text-[var(--foreground)]"
                }`}
                key={phase.label}
                type="button"
                onClick={() => selectPhase(index)}
              >
                {phase.label}
              </button>
            ))}
          </div>
          {selectedPhase && (
            <p className="mt-3 rounded-lg bg-[#fffcff] px-3 py-3 text-sm font-bold leading-5">
              {selectedPhase.body}
            </p>
          )}
        </div>
      )}
      {result.guidance.breath_pattern && (
        <p className="mt-3 rounded-lg bg-[var(--sage-soft)] px-3 py-2 text-sm font-bold text-[var(--sage)]">
          {result.guidance.breath_pattern}
        </p>
      )}
      <ol className="mt-4 list-decimal space-y-2 pl-5 leading-6">
        {result.guidance.steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      {result.guidance.reflection_prompt && (
        <p className="mt-4 flex gap-2 rounded-lg bg-[var(--amber-soft)] px-3 py-3 text-sm font-bold leading-5">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{result.guidance.reflection_prompt}</span>
        </p>
      )}
    </div>
  );
}

function ExerciseMotion({
  animation,
  stateKey,
}: {
  animation?: AnalyseResponse["guidance"]["animation"];
  stateKey: string;
}) {
  const variant =
    animation === "steady_orbit" || animation === "two_voice_shift"
      ? "animate-[orbit_7s_linear_infinite] border-[var(--sky)]"
      : animation === "safe_base" || animation === "heart_safe_place"
        ? "animate-[breathe_6s_ease-in-out_infinite] border-[var(--sage)]"
        : "animate-[breathe_5s_ease-in-out_infinite] border-[var(--lotus)]";

  return (
    <div className="mt-4 grid h-44 place-items-center rounded-lg bg-[linear-gradient(160deg,var(--lavender-soft),#f7fbf5)]">
      <div className={`relative grid h-28 w-28 place-items-center rounded-full border-2 ${variant}`}>
        {animation === "two_voice_shift" && (
          <span className="absolute -left-7 h-10 w-10 rounded-full bg-[var(--lotus)]/75" />
        )}
        {animation === "heart_safe_place" && (
          <span className="absolute h-20 w-20 rounded-full bg-[var(--sage-soft)]" />
        )}
        <div
          className={`relative h-12 w-12 rounded-full ${
            stateKey === "drive"
              ? "bg-[var(--sky)]"
              : stateKey === "soothing"
                ? "bg-[var(--sage)]"
                : "bg-[var(--lotus)]"
          }`}
        />
      </div>
      <style jsx>{`
        @keyframes breathe {
          0%,
          100% {
            transform: scale(0.82);
          }
          50% {
            transform: scale(1.18);
          }
        }
        @keyframes orbit {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}

function vibrate(pattern: number[]) {
  if ("vibrate" in navigator) {
    navigator.vibrate(pattern);
  }
}

async function convertToWav(blob: Blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const audioContext = new AudioContextClass();
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  const wavBuffer = encodeWav(audioBuffer);
  await audioContext.close();
  return new Blob([wavBuffer], { type: "audio/wav" });
}

function encodeWav(audioBuffer: AudioBuffer) {
  const channelData = audioBuffer.getChannelData(0);
  const sampleRate = audioBuffer.sampleRate;
  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(44 + channelData.length * bytesPerSample);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + channelData.length * bytesPerSample, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, channelData.length * bytesPerSample, true);

  let offset = 44;
  for (let i = 0; i < channelData.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, channelData[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += 2;
  }
  return buffer;
}

function writeString(view: DataView, offset: number, value: string) {
  for (let i = 0; i < value.length; i += 1) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}
