create type document_state as enum (
    'DRAFT',
    'PENDING_SIGNATURE',
    'ACTIVE',
    'EXPIRING_SOON',
    'EXPIRED',
    'TERMINATED'
);

create type currency_type as enum ('PEN', 'USD', 'EUR');

create table documents (
    id integer primary key,
    organization_id integer not null,
    type varchar(255),
    start_date date,
    end_date date,
    form_data jsonb default '{}'::jsonb,
    state document_state,
    file_path text,
    file_name text,
    folder_id integer,
    created_at timestamptz not null,
    updated_at timestamptz not null
);

create table services (
    id integer primary key,
    organization_id integer not null,
    name varchar(255) not null,
    description text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table company_contracts (
    id integer primary key,
    document_id integer not null unique references documents(id) on delete cascade,
    ruc varchar(255),
    client varchar(255),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table labor_contracts (
    id integer primary key,
    document_id integer not null unique references documents(id) on delete cascade,
    worker_name varchar(255),
    worker_document_number varchar(255),
    position varchar(255),
    salary_value double precision,
    salary_currency currency_type,
    salary_periodicity varchar(255),
    contract_modality varchar(255),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table company_contract_services (
    id integer primary key,
    company_contract_id integer not null references company_contracts(id) on delete cascade,
    service_id integer not null references services(id),
    description text,
    value double precision not null,
    currency currency_type not null,
    start_date date not null,
    end_date date not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
