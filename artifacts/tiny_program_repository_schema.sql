PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS programs (
  program_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  source_text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS statements (
  statement_id INTEGER PRIMARY KEY AUTOINCREMENT,
  program_id INTEGER NOT NULL,
  pc INTEGER NOT NULL,
  statement_kind TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  FOREIGN KEY (program_id) REFERENCES programs(program_id) ON DELETE CASCADE,
  UNIQUE (program_id, pc)
);

CREATE TABLE IF NOT EXISTS labels (
  statement_id INTEGER PRIMARY KEY,
  label_name TEXT NOT NULL,
  FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS print_statements (
  statement_id INTEGER PRIMARY KEY,
  value_expr TEXT NOT NULL,
  FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS set_statements (
  statement_id INTEGER PRIMARY KEY,
  var_name TEXT NOT NULL,
  value_expr TEXT NOT NULL,
  FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS goto_statements (
  statement_id INTEGER PRIMARY KEY,
  target_label TEXT NOT NULL,
  FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS if_goto_statements (
  statement_id INTEGER PRIMARY KEY,
  condition_expr TEXT NOT NULL,
  target_label TEXT NOT NULL,
  FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_statements_program_pc ON statements(program_id, pc);