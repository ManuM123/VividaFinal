"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/utils/supabase/client";
import { AppShell, Button, LotusMark } from "./shared_components";

const supabase = createClient();

export default function HomePage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [status, setStatus] = useState("Sign in");

  useEffect(() => {
    registerServiceWorker();
    supabase.auth.getUser().then(async ({ data }) => {
      if (!data.user) {
        setStatus("Sign in");
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

      router.replace(assessment ? "/check-in" : "/onboarding");
    });
  }, [router]);

  async function sendMagicLink() {
    if (!email.trim()) {
      return;
    }

    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    setAuthMessage(
      error ? error.message : "Check your email for the Vivida sign-in link.",
    );
  }

  return (
    <AppShell title="Sign in" status={status}>
      <section className="rounded-lg border border-[var(--line)] bg-white p-4 shadow-xl shadow-purple-950/5">
        <LotusMark />
        <h2 className="mt-5 text-2xl font-black">Welcome to Vivida</h2>
        <p className="mt-2 text-sm leading-6">
          Sign in once and use the link sent to your email whenever you need to
          sign back in, no password required!
        </p>
        <label className="mt-5 block text-sm font-black" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          className="mt-2 w-full rounded-lg border border-[var(--line)] bg-[#fffcff] px-4 py-3 outline-none focus:border-[var(--lavender)] focus:ring-4 focus:ring-purple-200"
          inputMode="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
        />
        <Button
          className="mt-4 flex h-12 w-full items-center justify-center rounded-lg bg-[var(--lavender)] font-black text-white"
          onClick={sendMagicLink}
        >
          Send sign-in link
        </Button>
        {authMessage && <p className="mt-3 text-sm">{authMessage}</p>}
      </section>
    </AppShell>
  );
}

function registerServiceWorker() {
  if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}
