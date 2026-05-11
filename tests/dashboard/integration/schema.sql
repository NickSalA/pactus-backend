drop table if exists documents_services;
drop table if exists documents;
drop table if exists services;
drop function if exists public.sync_document_states(integer);
drop type if exists currency_type;
drop type if exists document_state;
drop type if exists document_type;

create type document_type as enum ('COMPANY', 'LABOR');
create type document_state as enum ('DRAFT', 'PENDING_SIGNATURE', 'ACTIVE', 'EXPIRING_SOON', 'EXPIRED', 'TERMINATED');
create type currency_type as enum ('PEN', 'USD', 'EUR');

create table documents (
  id serial primary key,
  organization_id integer not null,
  name varchar(255),
  client varchar(255),
  type document_type,
  start_date date,
  end_date date,
  form_data jsonb,
  state document_state,
  file_path text,
  file_name text,
  folder_id integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table services (
  id serial primary key,
  organization_id integer not null,
  name varchar(255) not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table documents_services (
  id serial primary key,
  document_id integer not null,
  service_id integer not null,
  description text,
  value double precision not null,
  currency currency_type not null,
  start_date date not null,
  end_date date not null
);

create or replace function public.sync_document_states(target_organization_id integer)
returns integer
language sql
as $$
  select 0;
$$;
