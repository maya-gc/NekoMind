-- NekoMind | Script de banco de dados (SQLite 3)
-- Avaliação A3 de Modelagem de Software, 2026/2
-- Estrutura equivalente aos modelos SQLAlchemy em backend/app/database/models.py.
-- Execução: sqlite3 nekomind_demo.db < docs/banco/nekomind.sql

PRAGMA foreign_keys = ON;

-- =====================================================================
-- DDL
-- =====================================================================
DROP TRIGGER IF EXISTS trg_study_sessions_delete_tombstone;
DROP TABLE IF EXISTS audio_chunks;
DROP TABLE IF EXISTS metrics;
DROP TABLE IF EXISTS topics;
DROP TABLE IF EXISTS deleted_session_tombstones;
DROP TABLE IF EXISTS study_sessions;
DROP TABLE IF EXISTS reference_contents;

-- Material de estudo cadastrado pelo operador.
CREATE TABLE reference_contents (
    id              INTEGER      PRIMARY KEY AUTOINCREMENT,
    title           VARCHAR(200) NOT NULL,
    text            TEXT         NOT NULL,
    language        VARCHAR(16)  NOT NULL DEFAULT 'pt',
    version         INTEGER      NOT NULL DEFAULT 1 CHECK (version >= 1),
    source          VARCHAR(16)  NOT NULL DEFAULT 'typed'
                    CHECK (source IN ('typed', 'pdf', 'site')),
    points_json     TEXT         NOT NULL DEFAULT '[]',
    fair_available  BOOLEAN      NOT NULL DEFAULT 0,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Uma tentativa de explicação do estudante.
CREATE TABLE study_sessions (
    id                    INTEGER      PRIMARY KEY AUTOINCREMENT,
    title                 VARCHAR(200),
    started_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at              DATETIME,
    duration_seconds      FLOAT        NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
    status                VARCHAR(10)  NOT NULL DEFAULT 'recording'
                          CHECK (status IN ('recording', 'paused', 'processing', 'completed',
                                            'error', 'recovery', 'cancelled')),
    transcription         TEXT,
    clarity_score         FLOAT        CHECK (clarity_score IS NULL OR clarity_score BETWEEN 0 AND 10),
    is_demo               BOOLEAN      NOT NULL DEFAULT 0,
    mode                  VARCHAR(16)  NOT NULL DEFAULT 'demo' CHECK (mode IN ('demo', 'real')),
    request_id            VARCHAR(100),
    start_request_id      VARCHAR(100),
    finish_request_id     VARCHAR(100),
    device_session_id     VARCHAR(100),
    capture_source        VARCHAR(80),
    asr_provider_used     VARCHAR(80),
    topic_provider_used   VARCHAR(80),
    error_code            VARCHAR(80),
    error_message         TEXT,
    subject               VARCHAR(200),
    subject_confirmed     BOOLEAN      NOT NULL DEFAULT 0,
    metric_method_version VARCHAR(40)  NOT NULL DEFAULT 'heuristic-v1',
    journey_json          TEXT         NOT NULL DEFAULT '{}',
    deletion_pending      BOOLEAN      NOT NULL DEFAULT 0,
    reference_content_id  INTEGER,
    reference_version     INTEGER,
    reference_snapshot_json TEXT,
    content_report_json   TEXT,
    FOREIGN KEY (reference_content_id) REFERENCES reference_contents (id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

-- Tópicos identificados na fala de uma sessão.
CREATE TABLE topics (
    id          INTEGER      PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER      NOT NULL,
    name        VARCHAR(200) NOT NULL,
    relevance   FLOAT        NOT NULL DEFAULT 1.0 CHECK (relevance BETWEEN 0 AND 1),
    notes       TEXT,
    FOREIGN KEY (session_id) REFERENCES study_sessions (id) ON DELETE CASCADE
);

-- Métricas calculadas para uma sessão (contagem de palavras, cobertura etc.).
CREATE TABLE metrics (
    id          INTEGER      PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER      NOT NULL,
    name        VARCHAR(100) NOT NULL,
    value       FLOAT        NOT NULL,
    unit        VARCHAR(32),
    FOREIGN KEY (session_id) REFERENCES study_sessions (id) ON DELETE CASCADE
);

-- Trechos de áudio PCM recebidos durante a captura.
CREATE TABLE audio_chunks (
    id           INTEGER      PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER      NOT NULL,
    sequence     INTEGER      NOT NULL CHECK (sequence >= 0),
    format       VARCHAR(32)  NOT NULL DEFAULT 'pcm_s16le',
    sample_rate  INTEGER      NOT NULL DEFAULT 16000 CHECK (sample_rate > 0),
    byte_size    INTEGER      NOT NULL CHECK (byte_size >= 0),
    file_path    VARCHAR(500) NOT NULL,
    FOREIGN KEY (session_id) REFERENCES study_sessions (id) ON DELETE CASCADE
);

-- Registro de sessões excluídas, para que um pedido repetido não recrie a sessão.
CREATE TABLE deleted_session_tombstones (
    session_id        INTEGER      PRIMARY KEY,
    start_request_id  VARCHAR(100) UNIQUE,
    deleted_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_study_sessions_delete_tombstone
AFTER DELETE ON study_sessions
BEGIN
    INSERT OR IGNORE INTO deleted_session_tombstones (session_id, start_request_id)
    VALUES (OLD.id, OLD.start_request_id);
END;

-- Índices das chaves estrangeiras e das consultas mais frequentes.
CREATE INDEX idx_sessions_reference ON study_sessions (reference_content_id);
CREATE INDEX idx_sessions_started   ON study_sessions (started_at);
CREATE INDEX idx_sessions_subject   ON study_sessions (subject);
CREATE INDEX idx_topics_session     ON topics (session_id);
CREATE INDEX idx_metrics_session    ON metrics (session_id);
CREATE INDEX idx_audio_session      ON audio_chunks (session_id);

-- =====================================================================
-- DML | carga inicial de teste (3 registros por entidade)
-- =====================================================================
INSERT INTO reference_contents (title, text, source, points_json, fair_available) VALUES
('Ciclo da água',
 'A água do mar evapora com o calor do Sol. O vapor sobe, esfria e forma as nuvens. A chuva devolve a água aos rios e ao mar.',
 'typed',
 '["A água do mar evapora com o calor do Sol.","O vapor sobe, esfria e forma as nuvens.","A chuva devolve a água aos rios e ao mar."]',
 1),
('Fatos básicos da adição',
 'Quatro mais um é igual a cinco. Juntar uma cadeira a quatro cadeiras forma cinco cadeiras. A ordem das parcelas não altera a soma.',
 'pdf',
 '["Quatro mais um é igual a cinco.","Juntar uma cadeira a quatro cadeiras forma cinco cadeiras.","A ordem das parcelas não altera a soma."]',
 1),
('Hamiltoniana',
 'A Hamiltoniana representa a energia total do sistema. Na equação de Schrödinger ela governa a evolução temporal do estado.',
 'site',
 '["A Hamiltoniana representa a energia total do sistema.","Na equação de Schrödinger ela governa a evolução temporal do estado."]',
 0);

INSERT INTO study_sessions (title, started_at, ended_at, duration_seconds, status, transcription,
    clarity_score, is_demo, mode, start_request_id, capture_source, asr_provider_used, subject,
    reference_content_id, reference_version) VALUES
('Ciclo da água, missão 1', '2026-11-13 14:30:00', '2026-11-13 14:30:12', 12.0, 'completed',
 'A água do mar evapora com o calor do Sol.', 7.2, 0, 'real', 'req-0001', 'mac_microphone',
 'faster_whisper', 'Ciclo da água', 1, 1),
('Adição com cadeiras', '2026-11-19 10:05:00', '2026-11-19 10:05:09', 9.0, 'completed',
 'Eu tinha quatro cadeiras, coloquei mais uma e ficaram cinco.', 8.0, 0, 'real', 'req-0002',
 'mac_microphone', 'faster_whisper', 'Matemática', 2, 1),
('Demonstração', '2026-11-20 19:40:00', '2026-11-20 19:40:05', 5.0, 'completed',
 'Demonstração identificada.', NULL, 1, 'demo', 'req-0003', 'demo', 'mock', NULL, NULL, NULL);

INSERT INTO topics (session_id, name, relevance) VALUES
(1, 'evaporação', 0.9), (2, 'adição', 1.0), (2, 'contagem', 0.6);

INSERT INTO metrics (session_id, name, value, unit) VALUES
(1, 'word_count', 9, 'palavras'), (1, 'coverage_percent', 33.3, '%'), (2, 'word_count', 12, 'palavras');

INSERT INTO audio_chunks (session_id, sequence, byte_size, file_path) VALUES
(1, 0, 32000, 'audio/1/000.pcm'), (1, 1, 32000, 'audio/1/001.pcm'), (2, 0, 28800, 'audio/2/000.pcm');

-- Exclusões de teste: o gatilho grava o registro de exclusão (3 registros).
INSERT INTO study_sessions (title, status, start_request_id, mode) VALUES
('Teste A', 'cancelled', 'req-9001', 'demo'), ('Teste B', 'cancelled', 'req-9002', 'demo'),
('Teste C', 'cancelled', 'req-9003', 'demo');
DELETE FROM study_sessions WHERE start_request_id IN ('req-9001', 'req-9002', 'req-9003');

-- =====================================================================
-- Consultas de conferência (CRUD)
-- =====================================================================
-- Leitura: sessões com o material de referência
SELECT s.id, s.title, s.status, r.title AS material
FROM study_sessions s LEFT JOIN reference_contents r ON r.id = s.reference_content_id;
-- Atualização: nova versão do material
UPDATE reference_contents SET text = text || ' O ciclo se repete.', version = version + 1,
    updated_at = CURRENT_TIMESTAMP WHERE id = 1;
-- Atualização: confirmar o assunto de uma sessão
UPDATE study_sessions SET subject = 'Ciências', subject_confirmed = 1 WHERE id = 1;
