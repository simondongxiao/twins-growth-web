-- Run once in a NEW Supabase project's SQL editor. No child records go here.
-- Existing family projects: review tables/policies before applying. Do not drop data.
create table if not exists public.growth_families (
  id uuid primary key default gen_random_uuid(),
  label text not null default '家庭成长空间',
  created_at timestamptz not null default now()
);
create table if not exists public.growth_members (
  family_id uuid not null references public.growth_families(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  primary key (family_id, user_id)
);
create table if not exists public.growth_events (
  id uuid primary key,
  family_id uuid not null references public.growth_families(id) on delete cascade,
  created_by uuid not null references auth.users(id),
  received_at timestamptz not null default now(),
  payload jsonb not null,
  constraint growth_payload_shape check (
    jsonb_typeof(payload) = 'object'
    and payload ?& array['id','kind','child','text','created_at']
    and payload->>'id' = id::text
    and payload->>'kind' in ('baseline','observation','profile','proposal','plan','retract')
    and payload->>'child' in ('A','B','both')
    and jsonb_typeof(payload->'text') = 'string'
    and length(payload->>'text') <= 8000
    and octet_length(payload::text) <= 20000
  )
);
create index if not exists growth_events_family on public.growth_events(family_id, id);
alter table public.growth_families enable row level security;
alter table public.growth_members enable row level security;
alter table public.growth_events enable row level security;
revoke all on public.growth_families, public.growth_members, public.growth_events from anon;
revoke all on public.growth_families, public.growth_members, public.growth_events from authenticated;
grant select on public.growth_families, public.growth_members, public.growth_events to authenticated;
grant insert on public.growth_events to authenticated;
-- Members can only inspect their OWN membership. Membership can only be provisioned by administrator.
drop policy if exists growth_members_own on public.growth_members;
create policy growth_members_own on public.growth_members for select to authenticated
using (user_id = (select auth.uid()));
drop policy if exists growth_families_read on public.growth_families;
create policy growth_families_read on public.growth_families for select to authenticated
using (exists (select 1 from public.growth_members m where m.family_id=id and m.user_id=(select auth.uid())));
drop policy if exists growth_events_read on public.growth_events;
create policy growth_events_read on public.growth_events for select to authenticated
using (exists (select 1 from public.growth_members m where m.family_id=growth_events.family_id and m.user_id=(select auth.uid())));
drop policy if exists growth_events_insert on public.growth_events;
create policy growth_events_insert on public.growth_events for insert to authenticated
with check (created_by = (select auth.uid()) and exists (select 1 from public.growth_members m where m.family_id=growth_events.family_id and m.user_id=(select auth.uid())));
-- No update/delete policy. Corrections/retractions are new audit events.
-- Users CANNOT register themselves as a member of another family.
-- Provision auth accounts in Dashboard > Authentication. Turn OFF public signups.
-- Then replace the two UUIDs below with the actual auth.users IDs and run:
/*
with household as (
 insert into public.growth_families(label) values ('家庭成长空间') returning id
), users(user_id) as (
 values ('PARENT_A_AUTH_USER_UUID'::uuid), ('PARENT_B_AUTH_USER_UUID'::uuid)
)
insert into public.growth_members(family_id,user_id)
select household.id, users.user_id from household cross join users returning family_id,user_id;
*/
