alter table public.push_subscriptions
  add column if not exists motivation_enabled boolean not null default true,
  add column if not exists motivation_hour_utc integer not null default 12 check (motivation_hour_utc between 0 and 23),
  add column if not exists last_motivation_sent_date date;

update public.push_subscriptions
set motivation_hour_utc = 9 + floor(random() * 12)::integer
where motivation_hour_utc = 12
  and last_motivation_sent_date is null;

create index if not exists push_subscriptions_motivation_idx
  on public.push_subscriptions(enabled, motivation_enabled, motivation_hour_utc, last_motivation_sent_date);
