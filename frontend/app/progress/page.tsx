"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/app/components/ui/button";
import { createClient } from "@/utils/supabase/client";
import { AppShell, LotusMark, Metric } from "../components";
import {
  EMPTY_ENGAGEMENT,
  EngagementSummary,
  calculateStreak,
  parseDateList,
  todayKey,
} from "../static_data_and_types";

const supabase = createClient();
const ML_API_URL =
  process.env.NEXT_PUBLIC_ML_API_URL || "http://127.0.0.1:8000";

export default function ProgressPage() {
  const router = useRouter();
  const [engagement, setEngagement] =
    useState<EngagementSummary>(EMPTY_ENGAGEMENT);
  const [status, setStatus] = useState("Loading");
  const [remindersEnabled, setRemindersEnabled] = useState(false);

  const loadEngagement = useCallback(async (userId: string) => {
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
        .eq("user_id", userId)
        .order("activity_date", { ascending: false }),
      supabase
        .from("exercise_feedback")
        .select("helpfulness_score")
        .eq("user_id", userId),
      supabase.from("check_ins").select("id").eq("user_id", userId),
      supabase
        .from("user_profile")
        .select("current_streak, streak_dates")
        .eq("id", userId)
        .maybeSingle(),
    ]);

    const todayActivity = activityRows?.find(
      (row) => row.activity_date === today,
    );
    const starsEarned =
      feedbackRows?.reduce(
        (sum, row) => sum + Number(row.helpfulness_score || 0),
        0,
      ) || 0;
    const exercisesRated = feedbackRows?.length || 0;
    const dates = parseDateList(profile?.streak_dates);

    setEngagement({
      currentStreak: Number(profile?.current_streak || calculateStreak(dates)),
      todayCheckIns: Number(todayActivity?.check_in_count || 0),
      totalCheckIns: checkInRows?.length || 0,
      exercisesRated,
      starsEarned,
      maxStars: exercisesRated * 3,
    });
    setStatus("Ready");
  }, []);

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data }) => {
      if (!data.user) {
        router.replace("/");
        return;
      }
      setRemindersEnabled(
        window.localStorage.getItem("vivida_reminders") === "enabled",
      );
      await loadEngagement(data.user.id);
    });
  }, [loadEngagement, router]);

  async function enableReminder() {
    if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      setStatus("Push reminders unavailable on this browser");
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setStatus("Notifications blocked");
      return;
    }

    try {
      setStatus("Setting up reminders");
      const configResponse = await fetch(`${ML_API_URL}/api/notifications/config`);
      const config = (await configResponse.json()) as {
        supported?: boolean;
        publicKey?: string;
      };

      if (!config.supported || !config.publicKey) {
        throw new Error("Push reminders are not configured yet");
      }

      const registration = await ensureServiceWorkerRegistration();
      const existingSubscription = await registration.pushManager.getSubscription();
      const subscription =
        existingSubscription ||
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: base64UrlToUint8Array(config.publicKey),
        }));

      await postAuthenticated("/api/notifications/subscribe", {
        subscription: subscription.toJSON(),
        reminder_hour_utc: localHourToUtc(18),
        user_agent: navigator.userAgent,
      });

      window.localStorage.setItem("vivida_reminders", "enabled");
      setRemindersEnabled(true);
      setStatus("Reminders enabled");

      await postAuthenticated("/api/notifications/test", {});
    } catch (error) {
      console.error(error);
      setStatus(error instanceof Error ? error.message : "Reminder setup failed");
    }
  }

  async function disableReminder() {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await postAuthenticated("/api/notifications/unsubscribe", {
          endpoint: subscription.endpoint,
        });
        await subscription.unsubscribe();
      }
      window.localStorage.removeItem("vivida_reminders");
      setRemindersEnabled(false);
      setStatus("Reminders disabled");
    } catch (error) {
      console.error(error);
      setStatus("Could not disable reminders");
    }
  }

  async function postAuthenticated(path: string, body: object) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) {
      throw new Error("Please sign in again before enabling reminders");
    }

    const response = await fetch(`${ML_API_URL}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      let message = "Reminder request failed";
      try {
        const errorBody = (await response.json()) as { detail?: string };
        message = errorBody.detail || message;
      } catch {
        message = `${message} (${response.status})`;
      }
      throw new Error(message);
    }

    return response.json();
  }

  return (
    <AppShell title="Progress" status={status} showNav>
      <section className="grid gap-4 rounded-lg border border-[var(--line)] bg-white p-4 shadow-xl shadow-purple-950/5">
        <LotusMark />
        <h2 className="text-2xl font-black">Your lotus trail</h2>
        <p className="leading-6">
          Each day of use opens the trail a little further. Feedback stars help
          identify which exercises you found most useful!
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Metric
            label="Current streak"
            value={`${engagement.currentStreak} day${engagement.currentStreak === 1 ? "" : "s"}`}
          />
          <Metric
            label="Today"
            value={`${engagement.todayCheckIns} check-in${engagement.todayCheckIns === 1 ? "" : "s"}`}
          />
          <Metric
            label="Total check-ins"
            value={`${engagement.totalCheckIns}`}
          />
          <Metric
            label="Stars"
            value={`${engagement.starsEarned}/${engagement.maxStars || 0}`}
          />
        </div>
        <Button
          className="h-12 rounded-lg bg-[var(--sage)] font-black text-white"
          onClick={enableReminder}
        >
          {remindersEnabled ? "Send test reminder" : "Enable reminders"}
        </Button>
        {remindersEnabled && (
          <Button
            className="h-12 rounded-lg border border-[var(--line)] bg-white font-black"
            onClick={disableReminder}
          >
            Disable reminders
          </Button>
        )}
      </section>
    </AppShell>
  );
}

async function ensureServiceWorkerRegistration() {
  const existing = await navigator.serviceWorker.getRegistration();
  if (existing) {
    return existing;
  }
  return navigator.serviceWorker.register("/sw.js");
}

function base64UrlToUint8Array(base64UrlData: string) {
  const padding = "=".repeat((4 - (base64UrlData.length % 4)) % 4);
  const base64 = (base64UrlData + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const buffer = new Uint8Array(rawData.length);

  for (let index = 0; index < rawData.length; index += 1) {
    buffer[index] = rawData.charCodeAt(index);
  }

  return buffer;
}

function localHourToUtc(localHour: number) {
  const date = new Date();
  date.setHours(localHour, 0, 0, 0);
  return date.getUTCHours();
}
