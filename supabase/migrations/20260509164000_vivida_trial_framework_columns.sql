alter table public.user_profile
  add column if not exists last_active_date date;

alter table public.check_ins
  add column if not exists model_version text,
  add column if not exists exercise_key text,
  add column if not exists raw_prediction jsonb,
  add column if not exists audio_deleted boolean not null default true;

update public.check_ins set audio_deleted = true where audio_deleted is null;
