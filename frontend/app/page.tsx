"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/app/components/ui/button";
import { createClient } from "@/utils/supabase/client";
import { AppShell, LotusGlyph, LotusMark } from "./components";

const supabase = createClient();

export default function HomePage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [showIntro, setShowIntro] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const [pendingRedirect, setPendingRedirect] = useState<string | null>(null);

  useEffect(() => {
    registerServiceWorker();
    supabase.auth
      .getUser()
      .then(async ({ data }) => {
        if (!data.user) {
          setAuthChecked(true);
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

        setPendingRedirect(assessment ? "/check-in" : "/onboarding");
        setAuthChecked(true);
      })
      .catch(() => {
        setAuthChecked(true);
        setAuthMessage("Could not check your session. Try signing in again.");
      });
  }, []);

  useEffect(() => {
    const introTimer = window.setTimeout(() => setShowIntro(false), 1800);

    return () => window.clearTimeout(introTimer);
  }, []);

  useEffect(() => {
    if (!showIntro && pendingRedirect) {
      router.replace(pendingRedirect);
    }
  }, [pendingRedirect, router, showIntro]);

  async function sendMagicLink() {
    if (!email.trim()) {
      return;
    }

    const redirectTo = `${window.location.origin}/auth/callback`;

    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        emailRedirectTo: redirectTo,
      },
    });

    setAuthMessage(
      error ? error.message : "Check your email for the Vivida sign-in link.",
    );
  }

  return (
    <>
      {showIntro && <IntroSplash onContinue={() => setShowIntro(false)} />}
      <div className={showIntro ? "home-page home-page--hidden" : "home-page"}>
        <AppShell title={pendingRedirect ? "Opening Vivida" : "Sign in"}>
          {pendingRedirect ? (
            <OpeningCard />
          ) : (
            <SignInCard
              authMessage={authMessage}
              email={email}
              onEmailChange={setEmail}
              onSendMagicLink={sendMagicLink}
              disabled={!authChecked}
            />
          )}
        </AppShell>
      </div>
    </>
  );
}

function OpeningCard() {
  return (
    <section className="rounded-lg border border-[var(--line)] bg-white p-4 shadow-xl shadow-purple-950/5">
      <LotusMark />
      <h2 className="mt-5 text-2xl font-black">Opening your space</h2>
      <p className="mt-2 text-sm leading-6">
        Vivida is checking your session and getting your next step ready.
      </p>
    </section>
  );
}

function SignInCard({
  authMessage,
  disabled,
  email,
  onEmailChange,
  onSendMagicLink,
}: {
  authMessage: string;
  disabled: boolean;
  email: string;
  onEmailChange: (email: string) => void;
  onSendMagicLink: () => void;
}) {
  return (
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
        onChange={(event) => onEmailChange(event.target.value)}
        placeholder="name@example.com"
      />
      <Button
        className="mt-4 flex h-12 w-full items-center justify-center rounded-lg bg-[var(--lavender)] font-black text-white disabled:opacity-50"
        disabled={disabled}
        onClick={onSendMagicLink}
      >
        Send sign-in link
      </Button>
      {authMessage && <p className="mt-3 text-sm">{authMessage}</p>}
    </section>
  );
}

function IntroSplash({ onContinue }: { onContinue: () => void }) {
  return (
    <section aria-label="Welcome to Vivida" className="intro-splash">
      <div className="intro-splash__mark" aria-hidden="true">
        <LotusGlyph className="h-[4.6rem] w-[4.6rem]" />
      </div>
      <div className="intro-splash__copy">
        <p>Welcome to Vivida</p>
        <h1>Your real-time support for stressful moments.</h1>
        <Button
          className="mt-6 h-12 rounded-lg bg-[var(--lavender)] px-6 font-black text-white"
          onClick={onContinue}
        >
          Continue
        </Button>
      </div>
    </section>
  );
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}
