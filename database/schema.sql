-- ─────────────────────────────────────────────────────────────
--  CEPAT — Database Schema (SQLite)
--  Fase 1: Tabel earthquakes
--  Fase 2: Tabel intelligence_reports, situation_reports
-- ─────────────────────────────────────────────────────────────

-- ── Fase 1 ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS earthquakes (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id         TEXT    UNIQUE,
  magnitude        REAL    NOT NULL,
  depth_km         REAL,
  latitude         REAL,
  longitude        REAL,
  location_desc    TEXT,
  timestamp        TEXT,
  felt_area        TEXT    DEFAULT '',
  tsunami_potential TEXT   DEFAULT '',
  status           TEXT    DEFAULT 'NEW',          -- NEW | ACKNOWLEDGED | PROCESSED
  pipeline_status  TEXT    DEFAULT 'PENDING',      -- PENDING | PROCESSING | DONE | SKIPPED | FAILED
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_earthquakes_timestamp ON earthquakes(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_earthquakes_magnitude ON earthquakes(magnitude);
CREATE INDEX IF NOT EXISTS idx_earthquakes_status    ON earthquakes(status);
-- idx_earthquakes_pipeline dibuat oleh migrasi (db_handler._run_migrations)

-- ── Fase 2 ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intelligence_reports (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  earthquake_id      INTEGER REFERENCES earthquakes(id),
  source_name        TEXT,
  source_url         TEXT,
  source_type        TEXT    DEFAULT 'news_rss',   -- news_rss | google_news | twitter
  title              TEXT,
  content            TEXT,
  credibility_status TEXT    DEFAULT 'UNVERIFIED', -- VALID | HOAX | UNVERIFIED
  llm_reasoning      TEXT    DEFAULT '',
  published_at       TEXT    DEFAULT '',
  created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intel_earthquake ON intelligence_reports(earthquake_id);
CREATE INDEX IF NOT EXISTS idx_intel_status     ON intelligence_reports(credibility_status);

CREATE TABLE IF NOT EXISTS situation_reports (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  earthquake_id       INTEGER REFERENCES earthquakes(id) UNIQUE,
  summary             TEXT    DEFAULT '',
  affected_areas      TEXT    DEFAULT '',
  risk_level          TEXT    DEFAULT 'MEDIUM',    -- LOW | MEDIUM | HIGH | CRITICAL
  risk_justification  TEXT    DEFAULT '',
  recommendations     TEXT    DEFAULT '[]',        -- JSON array string
  notes               TEXT    DEFAULT '',
  raw_llm_output      TEXT    DEFAULT '',
  generated_by        TEXT    DEFAULT 'llm',       -- llm | fallback
  created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sitrep_earthquake  ON situation_reports(earthquake_id);
CREATE INDEX IF NOT EXISTS idx_sitrep_risk        ON situation_reports(risk_level);

-- ── Fase 3 ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS communication_drafts (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  situation_report_id  INTEGER REFERENCES situation_reports(id),
  earthquake_id        INTEGER REFERENCES earthquakes(id),
  draft_type           TEXT,                        -- 'public_id', 'public_minang', 'technical'
  content              TEXT    DEFAULT '',
  status               TEXT    DEFAULT 'DRAFT',     -- DRAFT, APPROVED, REJECTED, SENT
  approved_by          TEXT    DEFAULT '',
  approved_at          DATETIME,
  created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_commdraft_eq     ON communication_drafts(earthquake_id);
CREATE INDEX IF NOT EXISTS idx_commdraft_status ON communication_drafts(status);

CREATE TABLE IF NOT EXISTS coordination_plans (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  situation_report_id  INTEGER REFERENCES situation_reports(id),
  earthquake_id        INTEGER REFERENCES earthquakes(id),
  resource_mapping     TEXT    DEFAULT '',
  action_priorities    TEXT    DEFAULT '[]',         -- JSON array
  estimated_timeline   TEXT    DEFAULT '',
  generated_by         TEXT    DEFAULT 'llm',        -- llm | fallback
  status               TEXT    DEFAULT 'DRAFT',      -- DRAFT, APPROVED, REJECTED
  approved_by          TEXT    DEFAULT '',
  approved_at          DATETIME,
  created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_coordplan_eq     ON coordination_plans(earthquake_id);
CREATE INDEX IF NOT EXISTS idx_coordplan_status ON coordination_plans(status);

CREATE TABLE IF NOT EXISTS audit_log (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  action_type  TEXT,               -- 'APPROVE', 'REJECT', 'EDIT'
  item_table   TEXT,               -- 'communication_drafts', 'coordination_plans'
  item_id      INTEGER,
  decision     TEXT,               -- 'APPROVED', 'REJECTED', 'EDITED'
  officer_name TEXT    DEFAULT 'Petugas BPBD',
  notes        TEXT    DEFAULT '',
  timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── T3.4 — Operator User Management ─────────────────────────
CREATE TABLE IF NOT EXISTS operators (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    UNIQUE NOT NULL,
  password_hash TEXT    NOT NULL,
  full_name     TEXT    NOT NULL,
  role          TEXT    DEFAULT 'operator',    -- 'admin' | 'operator' | 'viewer'
  is_active     INTEGER DEFAULT 1,
  last_login    TEXT,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operators_username ON operators(username);
CREATE INDEX IF NOT EXISTS idx_operators_role     ON operators(role);
