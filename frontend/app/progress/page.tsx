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
    if (!("Notification" in window) || !("serviceWorker" in navigator)) {
      setStatus("Notifications unavailable");
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setStatus("Notifications blocked");
      return;
    }

    const registration = await navigator.serviceWorker.ready;
    registration.active?.postMessage({
      type: "vivida-reminder",
      title: "Vivida is ready",
      body: "A gentle reminder can bring you back before stress builds up.",
    });
    window.localStorage.setItem("vivida_reminders", "enabled");
    setRemindersEnabled(true);
    setStatus("Reminders enabled");
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
      </section>
    </AppShell>
  );
}
