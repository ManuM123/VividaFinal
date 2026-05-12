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
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "signup">("signup");
  const [authMessage, setAuthMessage] = useState("");
  const [showIntro, setShowIntro] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
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

        await openAppForUser(data.user.id);
        setAuthChecked(true);
      })
      .catch(() => {
        setAuthChecked(true);
        setAuthMessage("Could not check your session. Try signing in again.");
      });
  }, []);

  useEffect(() => {
    const introTimer = window.setTimeout(() => setShowIntro(false), 2800);

    return () => window.clearTimeout(introTimer);
  }, []);

  useEffect(() => {
    if (!showIntro && pendingRedirect) {
      router.replace(pendingRedirect);
    }
  }, [pendingRedirect, router, showIntro]);

  async function openAppForUser(userId: string) {
    const { data: assessment } = await supabase
      .from("gse_assessments")
      .select("score")
      .eq("user_id", userId)
      .eq("phase", "baseline")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    setShowIntro(false);
    setPendingRedirect(assessment ? "/check-in" : "/onboarding");
  }

  async function submitAuth() {
    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setAuthMessage("Enter your email and password.");
      return;
    }

    if (password.length < 6) {
      setAuthMessage("Password must be at least 6 characters.");
      return;
    }

    setIsSubmitting(true);
    setAuthMessage("");

    const result =
      authMode === "signup"
        ? await supabase.auth.signUp({
            email: cleanEmail,
            password,
          })
        : await supabase.auth.signInWithPassword({
            email: cleanEmail,
            password,
          });

    setIsSubmitting(false);

    if (result.error) {
      setAuthMessage(result.error.message);
      return;
    }

    if (!result.data.session || !result.data.user) {
      setAuthMessage(
        "Account created. If Vivida does not open, disable email confirmation in Supabase Auth settings and try logging in.",
      );
      return;
    }

    await openAppForUser(result.data.user.id);
  }

  return (
    <>
      {showIntro && <IntroSplash />}
      <div className={showIntro ? "home-page home-page--hidden" : "home-page"}>
        <AppShell title={pendingRedirect ? "Opening Vivida" : "Sign in"}>
          {pendingRedirect ? (
            <OpeningCard />
          ) : (
            <SignInCard
              authMode={authMode}
              authMessage={authMessage}
              email={email}
              password={password}
              onAuthModeChange={setAuthMode}
              onEmailChange={setEmail}
              onPasswordChange={setPassword}
              onSubmit={submitAuth}
              disabled={!authChecked || isSubmitting}
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
  authMode,
  authMessage,
  disabled,
  email,
  password,
  onAuthModeChange,
  onEmailChange,
  onPasswordChange,
  onSubmit,
}: {
  authMode: "login" | "signup";
  authMessage: string;
  disabled: boolean;
  email: string;
  password: string;
  onAuthModeChange: (mode: "login" | "signup") => void;
  onEmailChange: (email: string) => void;
  onPasswordChange: (password: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="rounded-lg border border-[var(--line)] bg-white p-4 shadow-xl shadow-purple-950/5">
      <LotusMark />
      <h2 className="mt-5 text-2xl font-black">Welcome to Vivida</h2>
      <p className="mt-2 text-sm leading-6">
        Create an account or log back in with your email and password.
      </p>
      <div className="mt-5 grid grid-cols-2 rounded-lg border border-[var(--line)] bg-[#fffcff] p-1">
        <button
          className={`h-10 rounded-md text-sm font-black ${
            authMode === "signup"
              ? "bg-[var(--lavender)] text-white"
              : "text-[var(--lavender-dark)]"
          }`}
          type="button"
          onClick={() => {
            onAuthModeChange("signup");
          }}
        >
          Sign up
        </button>
        <button
          className={`h-10 rounded-md text-sm font-black ${
            authMode === "login"
              ? "bg-[var(--lavender)] text-white"
              : "text-[var(--lavender-dark)]"
          }`}
          type="button"
          onClick={() => {
            onAuthModeChange("login");
          }}
        >
          Log in
        </button>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!disabled) {
            onSubmit();
          }
        }}
      >
        <label className="mt-5 block text-sm font-black" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          className="mt-2 w-full rounded-lg border border-[var(--line)] bg-[#fffcff] px-4 py-3 outline-none focus:border-[var(--lavender)] focus:ring-4 focus:ring-purple-200"
          autoComplete="email"
          inputMode="email"
          type="email"
          value={email}
          onChange={(event) => onEmailChange(event.target.value)}
          placeholder="name@example.com"
        />
        <label className="mt-4 block text-sm font-black" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          className="mt-2 w-full rounded-lg border border-[var(--line)] bg-[#fffcff] px-4 py-3 outline-none focus:border-[var(--lavender)] focus:ring-4 focus:ring-purple-200"
          autoComplete={
            authMode === "signup" ? "new-password" : "current-password"
          }
          type="password"
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
          placeholder="At least 6 characters"
        />
        <Button
          className="mt-4 flex h-12 w-full items-center justify-center rounded-lg bg-[var(--lavender)] font-black text-white disabled:opacity-50"
          disabled={disabled}
          type="submit"
        >
          {authMode === "signup" ? "Create account" : "Log in"}
        </Button>
      </form>
      {authMessage && <p className="mt-3 text-sm">{authMessage}</p>}
    </section>
  );
}

function IntroSplash() {
  return (
    <section aria-label="Welcome to Vivida" className="intro-splash">
      <div className="intro-splash__mark" aria-hidden="true">
        <LotusGlyph className="h-[4.6rem] w-[4.6rem]" />
      </div>
      <div className="intro-splash__copy">
        <p>Welcome to Vivida</p>
        <h1>Your real-time support for stressful moments.</h1>
      </div>
    </section>
  );
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}
