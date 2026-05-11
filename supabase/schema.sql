create extension if not exists "pgcrypto";

drop table if exists public.profiles cascade;

create table if not exists public.user_profile (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  first_name text not null default '',
  gender text not null default '',
  onboarding_answers jsonb not null default '{}'::jsonb,
  current_streak integer not null default 0,
  last_active_date date,
  streak_dates jsonb not null default '[]'::jsonb
);

comment on table public.user_profile is
  'Participant profile and lightweight engagement state. Voice recordings are never stored here.';

create table if not exists public.gse_assessments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  phase text not null default 'baseline',
  score integer not null check (score between 10 and 40),
  answers jsonb not null,
  created_at timestamptz not null default now(),
  constraint gse_phase_check check (phase in ('baseline'))
);

create table if not exists public.check_ins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  predicted_emotion text not null,
  predicted_state text not null check (predicted_state in ('threat', 'drive', 'soothing')),
  confidence numeric(6, 5),
  classifier text,
  model_version text,
  latency_ms numeric(10, 2),
  exercise_key text,
  exercise_title text,
  raw_prediction jsonb,
  audio_deleted boolean not null default true,
  created_at timestamptz not null default now()
);

comment on table public.check_ins is
  'Stores derived inference outputs only. Raw audio is processed ephemerally by the ML API and deleted immediately.';

create table if not exists public.exercise_feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  check_in_id uuid not null references public.check_ins(id) on delete cascade,
  helpfulness_score integer not null check (helpfulness_score between 1 and 3),
  created_at timestamptz not null default now(),
  unique (check_in_id)
);

create table if not exists public.daily_activity (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  activity_date date not null default current_date,
  check_in_count integer not null default 0,
  completed_exercise_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, activity_date)
);

create index if not exists gse_assessments_user_created_idx
  on public.gse_assessments(user_id, created_at desc);

create index if not exists check_ins_user_created_idx
  on public.check_ins(user_id, created_at desc);

create index if not exists exercise_feedback_user_created_idx
  on public.exercise_feedback(user_id, created_at desc);

create index if not exists daily_activity_user_date_idx
  on public.daily_activity(user_id, activity_date desc);

alter table public.user_profile enable row level security;
alter table public.gse_assessments enable row level security;
alter table public.check_ins enable row level security;
alter table public.exercise_feedback enable row level security;
alter table public.daily_activity enable row level security;

drop policy if exists "user_profile_select_own" on public.user_profile;
create policy "user_profile_select_own"
  on public.user_profile for select
  using (auth.uid() = id);

drop policy if exists "user_profile_insert_own" on public.user_profile;
create policy "user_profile_insert_own"
  on public.user_profile for insert
  with check (auth.uid() = id);

drop policy if exists "user_profile_update_own" on public.user_profile;
create policy "user_profile_update_own"
  on public.user_profile for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

drop policy if exists "gse_select_own" on public.gse_assessments;
create policy "gse_select_own"
  on public.gse_assessments for select
  using (auth.uid() = user_id);

drop policy if exists "gse_insert_own" on public.gse_assessments;
create policy "gse_insert_own"
  on public.gse_assessments for insert
  with check (auth.uid() = user_id);

drop policy if exists "check_ins_select_own" on public.check_ins;
create policy "check_ins_select_own"
  on public.check_ins for select
  using (auth.uid() = user_id);

drop policy if exists "check_ins_insert_own" on public.check_ins;
create policy "check_ins_insert_own"
  on public.check_ins for insert
  with check (auth.uid() = user_id);

drop policy if exists "exercise_feedback_select_own" on public.exercise_feedback;
create policy "exercise_feedback_select_own"
  on public.exercise_feedback for select
  using (auth.uid() = user_id);

drop policy if exists "exercise_feedback_insert_own" on public.exercise_feedback;
create policy "exercise_feedback_insert_own"
  on public.exercise_feedback for insert
  with check (auth.uid() = user_id);

drop policy if exists "daily_activity_select_own" on public.daily_activity;
create policy "daily_activity_select_own"
  on public.daily_activity for select
  using (auth.uid() = user_id);

drop policy if exists "daily_activity_insert_own" on public.daily_activity;
create policy "daily_activity_insert_own"
  on public.daily_activity for insert
  with check (auth.uid() = user_id);

drop policy if exists "daily_activity_update_own" on public.daily_activity;
create policy "daily_activity_update_own"
  on public.daily_activity for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
