export const GSE_QUESTIONS = [
  "I can always manage to solve difficult problems if I try hard enough",
  "If someone opposes me, I can find the means and ways to get what I want",
  "It is easy for me to stick to my aims and accomplish my goals",
  "I am confident that I could deal efficiently with unexpected events",
  "Thanks to my resourcefulness, I know how to handle unforeseen situations",
  "I can solve most problems if I invest the necessary effort",
  "I can remain calm when facing difficulties because I can rely on my coping abilities",
  "When I am confronted with a problem, I can usually find several solutions",
  "If I am in trouble, I can usually think of a solution",
  "I can usually handle whatever comes my way",
];

export const SCALE_OPTIONS = [
  ["1", "Not at all true"],
  ["2", "Hardly true"],
  ["3", "Moderately true"],
  ["4", "Exactly true"],
] as const;

export type PredictionState = {
  key: "threat" | "drive" | "soothing";
  name: string;
  colour: string;
  summary: string;
};

export type AnalyseResponse = {
  analysis_id: string;
  session_id: string;
  transcript: string;
  prediction: {
    emotion: string;
    confidence: number;
    classifier: string;
    latency_ms: number;
    model_path?: string | null;
    model_available?: boolean;
    state: PredictionState;
  };
  guidance: {
    title: string;
    subtitle?: string;
    intro: string;
    personalised_line: string;
    steps: string[];
    voice_script: string;
    animation?:
      | "expanding_lotus"
      | "steady_orbit"
      | "safe_base"
      | "softening_sentence"
      | "two_voice_shift"
      | "heart_safe_place";
    haptics?: number[];
    phases?: { label: string; body: string }[];
    reflection_prompt?: string;
    breath_pattern?: string;
    duration_seconds?: number;
  };
};

export type EngagementSummary = {
  currentStreak: number;
  todayCheckIns: number;
  totalCheckIns: number;
  exercisesRated: number;
  starsEarned: number;
  maxStars: number;
};

export type SpeechRecognitionConstructor = new () => SpeechRecognition;

export type SpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  start: () => void;
  stop: () => void;
};

export type SpeechRecognitionEvent = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      [index: number]: { transcript: string };
    };
  };
};

export const EMPTY_ENGAGEMENT: EngagementSummary = {
  currentStreak: 0,
  todayCheckIns: 0,
  totalCheckIns: 0,
  exercisesRated: 0,
  starsEarned: 0,
  maxStars: 0,
};

export function score(answers: number[]) {
  return answers.reduce((sum, answer) => sum + answer, 0);
}

export function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

export function parseDateList(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

export function calculateStreak(dates: string[]) {
  const dateSet = new Set(dates);
  const cursor = new Date(`${todayKey()}T00:00:00`);
  let streak = 0;

  while (dateSet.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }

  return streak;
}

export function titleCase(value: string) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "-";
}

export function stateClass(stateKey: PredictionState["key"]) {
  if (stateKey === "threat") {
    return "bg-[var(--lotus-soft)]";
  }
  if (stateKey === "drive") {
    return "bg-[var(--sky-soft)]";
  }
  return "bg-[var(--sage-soft)]";
}
