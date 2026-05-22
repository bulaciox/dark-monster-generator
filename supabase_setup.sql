-- Run this once in the Supabase SQL Editor (Dashboard > SQL Editor).
-- Creates the table used to record every generation.

create table if not exists generations (
    id uuid primary key default gen_random_uuid(),
    prompt text not null,
    image_url text not null,
    created_at timestamptz not null default now()
);
