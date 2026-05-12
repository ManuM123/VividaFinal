import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createClient } from "@/utils/supabase/server";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const next = requestUrl.searchParams.get("next");

  if (code) {
    const cookieStore = await cookies();
    const supabase = createClient(cookieStore);
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      if (next?.startsWith("/")) {
        return NextResponse.redirect(new URL(next, requestUrl.origin));
      }

      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (user) {
        const { data: assessment } = await supabase
          .from("gse_assessments")
          .select("score")
          .eq("user_id", user.id)
          .eq("phase", "baseline")
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle();

        return NextResponse.redirect(
          new URL(assessment ? "/check-in" : "/onboarding", requestUrl.origin),
        );
      }
    }
  }

  return NextResponse.redirect(new URL("/", requestUrl.origin));
}
