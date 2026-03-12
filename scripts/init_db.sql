-- AML Platform Database Initialization
-- PostgreSQL schema for Risk Score Store, Alert Store, and Audit Logs

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Risk Scores ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_scores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id       VARCHAR(50) NOT NULL,
    rule_score      DECIMAL(5,2) NOT NULL,
    ml_score        DECIMAL(5,4) NOT NULL,
    graph_score     DECIMAL(5,2) NOT NULL,
    final_score     DECIMAL(5,2) NOT NULL,
    risk_rating     VARCHAR(20) NOT NULL,
    model_version   VARCHAR(50) NOT NULL,
    top_risk_drivers JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_scores_client_id ON risk_scores (client_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_created_at ON risk_scores (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_rating ON risk_scores (risk_rating);

-- ─── Feature Store ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feature_store (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id               VARCHAR(50) NOT NULL,
    transaction_volume      DECIMAL(20,2),
    cross_border_ratio      DECIMAL(5,4),
    cash_ratio              DECIMAL(5,4),
    network_degree          INTEGER DEFAULT 0,
    pep_flag                DECIMAL(3,1) DEFAULT 0.0,
    country_risk_score      DECIMAL(5,2),
    industry_risk_score     DECIMAL(5,2),
    adverse_media_score     DECIMAL(5,2),
    transaction_count       INTEGER DEFAULT 0,
    avg_transaction_size    DECIMAL(15,2),
    distance_to_sanctioned  INTEGER,
    network_cluster_size    INTEGER DEFAULT 0,
    computed_at             TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feature_store_client ON feature_store (client_id);

-- ─── Alerts ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_type      VARCHAR(50) NOT NULL,
    client_id       VARCHAR(50) NOT NULL,
    risk_score      DECIMAL(5,2) NOT NULL,
    risk_rating     VARCHAR(20) NOT NULL,
    reason          TEXT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    assigned_to     VARCHAR(100),
    transaction_id  VARCHAR(50),
    metadata_json   JSONB,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_client_id ON alerts (client_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at DESC);

-- ─── Audit Logs (append-only) ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id    UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    event_type  VARCHAR(100) NOT NULL,
    client_id   VARCHAR(50),
    actor       VARCHAR(100),
    details     JSONB,
    ip_address  VARCHAR(50),
    timestamp   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_client_id ON audit_logs (client_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp DESC);

-- Disable UPDATE and DELETE on audit_logs for immutability
-- In production: use PostgreSQL row-level security or a separate append-only role
CREATE RULE no_update_audit AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE no_delete_audit AS ON DELETE TO audit_logs DO INSTEAD NOTHING;

-- ─── Seed some sample data ───────────────────────────────────────────────────
INSERT INTO audit_logs (event_type, actor, details) VALUES
('SYSTEM_STARTUP', 'system', '{"message": "AML Platform initialized"}'),
('DATABASE_MIGRATION', 'system', '{"version": "1.0.0", "tables_created": 4}');
