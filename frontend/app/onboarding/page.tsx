"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/app/components/ui/button";
import { createClient } from "@/utils/supabase/client";
import { AppShell, ScaleForm } from "../components";
import { score } from "../static_data_and_types";

const supabase = createClient();

export default function OnboardingPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [firstName, setFirstName] = useState("");
  const [baselineAnswers, setBaselineAnswers] = useState<number[]>(
    Array(10).fill(4),
  );
  const [saveMessage, setSaveMessage] = useState("");
  const baselineScore = useMemo(
    () => score(baselineAnswers),
    [baselineAnswers],
  );
  const shouldShowSupport = baselineAnswers.every((answer) => answer === 1);

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data }) => {
      if (!data.user) {
        router.replace("/");
        return;
      }

      setUserId(data.user.id);

      const [{ data: profile }, { data: assessment }] = await Promise.all([
        supabase
          .from("user_profile")
          .select("first_name")
          .eq("id", data.user.id)
          .maybeSingle(),
        supabase
          .from("gse_assessments")
          .select("score")
          .eq("user_id", data.user.id)
          .eq("phase", "baseline")
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle(),
      ]);

      if (assessment) {
        router.replace("/check-in");
        return;
      }

      if (profile?.first_name) {
        setFirstName(profile.first_name);
      }
    });
  }, [router]);

  async function saveBaseline() {
    if (!userId || !firstName.trim()) {
      return;
    }

    const cleanName = firstName.trim().slice(0, 40);
    const onboardingAnswers = {
      gse_baseline: {
        score: baselineScore,
        answers: baselineAnswers,
        completed_at: new Date().toISOString(),
      },
    };

    const { error: profileError } = await supabase.from("user_profile").upsert({
      id: userId,
      first_name: cleanName,
      onboarding_answers: onboardingAnswers,
    });

    const { error: scoreError } = await supabase
      .from("gse_assessments")
      .insert({
        user_id: userId,
        phase: "baseline",
        score: baselineScore,
        answers: baselineAnswers,
      });

    if (profileError || scoreError) {
      setSaveMessage(
        profileError?.message || scoreError?.message || "Could not save",
      );
      return;
    }

    router.replace("/check-in");
  }

  return (
    <AppShell title="Baseline">
      <section className="rounded-lg border border-[var(--line)] bg-white p-4 shadow-xl shadow-purple-950/5">
        <label className="block text-sm font-black" htmlFor="firstName">
          First name or nickname
        </label>
        <input
          id="firstName"
          className="mt-2 w-full rounded-lg border border-[var(--line)] bg-[#fffcff] px-4 py-3 outline-none focus:border-[var(--lavender)] focus:ring-4 focus:ring-purple-200"
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          placeholder="Manu"
        />
        <ScaleForm
          title="General Self-Efficacy Scale"
          score={baselineScore}
          answers={baselineAnswers}
          setAnswers={setBaselineAnswers}
        />
        {shouldShowSupport && <SupportNotice />}
        {saveMessage && (
          <p className="mt-3 text-sm text-[var(--lavender-dark)]">
            {saveMessage}
          </p>
        )}
        <Button
          className="mt-4 flex h-12 w-full items-center justify-center rounded-lg bg-[var(--lavender)] font-black text-white disabled:opacity-50"
          disabled={!firstName.trim()}
          onClick={saveBaseline}
        >
          Save
        </Button>
      </section>
    </AppShell>
  );
}

function SupportNotice() {
  return (
    <div className="mt-4 rounded-lg border border-[var(--amber)] bg-[var(--amber-soft)] p-4">
      <h2 className="text-base font-black text-[var(--foreground)]">
        Extra support is available
      </h2>
      <p className="mt-2 text-sm leading-6">
        If all of these statements feel not at all true right now, please do not
        hesitate to reach out for help. Vivida can support reflection, but it is
        not a substitute for mental health support.
      </p>
      <a
        className="mt-3 inline-flex font-black text-[var(--lavender-dark)] underline"
        href="https://www.mind.org.uk/need-urgent-help"
        rel="noreferrer"
        target="_blank"
      >
        Get support from Mind
      </a>
    </div>
  );
}
