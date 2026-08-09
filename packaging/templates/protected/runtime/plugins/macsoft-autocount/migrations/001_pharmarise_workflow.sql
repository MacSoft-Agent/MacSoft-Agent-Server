CREATE TABLE IF NOT EXISTS payment_cases (
    id UUID PRIMARY KEY,
    company_id TEXT NOT NULL,
    account_book_id TEXT NOT NULL,
    status TEXT NOT NULL,
    debtor_code TEXT,
    amount NUMERIC(18, 2),
    payment_date DATE,
    payment_reference TEXT,
    source_channel TEXT NOT NULL,
    source_event_key TEXT NOT NULL,
    working_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, account_book_id, source_channel, source_event_key)
);

CREATE TABLE IF NOT EXISTS receiving_cases (
    id UUID PRIMARY KEY,
    company_id TEXT NOT NULL,
    account_book_id TEXT NOT NULL,
    status TEXT NOT NULL,
    supplier_code TEXT,
    supplier_invoice_no TEXT,
    po_no TEXT,
    source_channel TEXT NOT NULL,
    source_event_key TEXT NOT NULL,
    working_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, account_book_id, source_channel, source_event_key)
);

CREATE TABLE IF NOT EXISTS whatsapp_identifiers (
    id UUID PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'whatsapp',
    identifier_type TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    company_id TEXT NOT NULL,
    account_book_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    internal_user_id TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (platform, identifier_type, identifier_value)
);

CREATE TABLE IF NOT EXISTS workflow_case_events (
    id UUID PRIMARY KEY,
    case_type TEXT NOT NULL CHECK (case_type IN ('payment', 'receiving')),
    case_id UUID NOT NULL,
    case_version INTEGER NOT NULL CHECK (case_version > 0),
    company_id TEXT NOT NULL,
    account_book_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    action_type TEXT,
    action_id TEXT,
    action_digest TEXT,
    actor_user_id TEXT NOT NULL,
    actor_role TEXT,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS workflow_case_events_action_event_uq
    ON workflow_case_events (action_id, event_type)
    WHERE action_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS workflow_case_events_case_idx
    ON workflow_case_events (company_id, account_book_id, case_type, case_id, created_at);

CREATE OR REPLACE FUNCTION macsoft_reject_workflow_case_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'workflow_case_events is append-only';
END;
$$;

DROP TRIGGER IF EXISTS workflow_case_events_no_update ON workflow_case_events;
CREATE TRIGGER workflow_case_events_no_update
BEFORE UPDATE ON workflow_case_events
FOR EACH ROW EXECUTE FUNCTION macsoft_reject_workflow_case_event_mutation();
DROP TRIGGER IF EXISTS workflow_case_events_no_delete ON workflow_case_events;
CREATE TRIGGER workflow_case_events_no_delete
BEFORE DELETE ON workflow_case_events
FOR EACH ROW EXECUTE FUNCTION macsoft_reject_workflow_case_event_mutation();
