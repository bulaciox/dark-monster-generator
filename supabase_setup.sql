-- Run this once in the Supabase SQL Editor (Dashboard > SQL Editor).
-- Safe to re-run: everything is idempotent.

-- ---------------------------------------------------------------------------
-- generations: one row per image version of the monster (history / timelapse).
-- kind: 'initial' (first monster of the day), 'edit' (Kontext transformation),
--       'reanchor' (full regeneration from the genome to recover sharpness),
--       'upload' (visitor-provided reference image).
-- ---------------------------------------------------------------------------
create table if not exists generations (
    id uuid primary key default gen_random_uuid(),
    prompt text not null,
    image_url text not null,
    created_at timestamptz not null default now()
);

alter table generations add column if not exists day date not null default current_date;
alter table generations add column if not exists version int;
alter table generations add column if not exists kind text not null default 'generate';
-- iteration: a day can be reset during testing; each reset starts a new
-- iteration and archived versions keep the old one ("Iteration X").
alter table generations add column if not exists iteration int not null default 1;

create index if not exists generations_day_idx on generations (day, version);

-- ---------------------------------------------------------------------------
-- submissions: every questionnaire answer, raw. The structured answers live
-- in `data` (jsonb) so the form can evolve without migrations.
-- ---------------------------------------------------------------------------
create table if not exists submissions (
    id uuid primary key default gen_random_uuid(),
    day date not null default current_date,
    data jsonb not null,
    image_url text,          -- optional visitor upload (already in Storage)
    created_at timestamptz not null default now()
);

create index if not exists submissions_day_idx on submissions (day);

-- ---------------------------------------------------------------------------
-- monster_state: one row per day = the genome of that day's monster.
-- genome accumulates every submission statistically (region scores, emotion
-- counts, ability counts, scale averages...). image_url points to the
-- CURRENT version of the monster.
-- ---------------------------------------------------------------------------
create table if not exists monster_state (
    day date primary key,
    genome jsonb not null default '{}'::jsonb,
    image_url text,
    version int not null default 0,
    edits_since_anchor int not null default 0,
    updated_at timestamptz not null default now()
);

alter table monster_state add column if not exists iteration int not null default 1;

-- ---------------------------------------------------------------------------
-- monsters: one row per visitor — their own monster, not the collective one.
-- Free text becomes `identity` (already transposed, so it never names a real
-- person, place or event); the selected emotions become `organs`. The four
-- installation outputs are organ_image_url, silhouette_image_url, story and
-- title, and `number` is the respondent number shown beside the title.
-- ---------------------------------------------------------------------------
create table if not exists monsters (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid references submissions (id),
    day date not null default current_date,
    number int not null,
    monster_type text not null default 'human',   -- human | environmental
    identity jsonb not null default '{}'::jsonb,
    organs jsonb not null default '[]'::jsonb,
    organ_image_url text,
    silhouette_image_url text,
    story text,
    title text,
    created_at timestamptz not null default now()
);

create index if not exists monsters_day_idx on monsters (day, number);

-- ---------------------------------------------------------------------------
-- free_generations: images generated from bare prompts in the Free Generate
-- tab. No processing, no system prompt -- the user's text goes straight to
-- the model so the style of the generation can be explored freely.
-- ---------------------------------------------------------------------------
create table if not exists free_generations (
    id uuid primary key default gen_random_uuid(),
    prompt text not null,
    image_url text not null,
    created_at timestamptz not null default now()
);

create index if not exists free_generations_created_idx on free_generations (created_at desc);
