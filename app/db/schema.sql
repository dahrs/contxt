CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    native_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    is_absolute_beginner INTEGER NOT NULL DEFAULT 0,
    email TEXT,
    last_proactive_sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS interests (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (user_id, topic)
);

CREATE TABLE IF NOT EXISTS skill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK (type IN ('vocab', 'grammar', 'syntax', 'phonetic', 'register')),
    target_lang TEXT NOT NULL,
    content TEXT NOT NULL,
    level TEXT NOT NULL,
    category TEXT
);

CREATE TABLE IF NOT EXISTS skill_item_prerequisites (
    item_id INTEGER NOT NULL REFERENCES skill_items(id) ON DELETE CASCADE,
    prerequisite_id INTEGER NOT NULL REFERENCES skill_items(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, prerequisite_id)
);

-- psychological_profile/explanation_style/teaching_philosophy/social_habits are free-text -
-- generated prose, not structured fields, since they're fed straight into a prompt fragment.
CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_lang TEXT NOT NULL,
    name TEXT NOT NULL,
    origin TEXT NOT NULL,
    age INTEGER NOT NULL,
    background TEXT NOT NULL,
    physical_description TEXT NOT NULL,
    psychological_profile TEXT NOT NULL,
    social_habits TEXT NOT NULL,
    explanation_style TEXT NOT NULL,
    teaching_philosophy TEXT NOT NULL,
    correction_style TEXT NOT NULL,
    preferred_medium TEXT NOT NULL,
    vocabulary_strictness TEXT NOT NULL,
    cultural_depth TEXT NOT NULL,
    timezone TEXT NOT NULL,
    daily_routine TEXT NOT NULL,
    free_hours_json TEXT NOT NULL,
    is_beginner_teacher INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS persona_interests (
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    PRIMARY KEY (persona_id, topic)
);

-- One running relationship summary per (user, persona) pair, covering every conversation the
-- user has had with that persona - not leaked to other personas. last_summarized_message_id is
-- the high-water mark of messages already folded in, so a later catch-up only summarizes new ones.
CREATE TABLE IF NOT EXISTS persona_user_memory (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    summary TEXT NOT NULL DEFAULT '',
    last_summarized_message_id INTEGER,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (user_id, persona_id)
);

-- fsrs_card_json is the serialized form of an fsrs.Card (see fsrs.Card.to_json/from_json) -
-- the library owns that shape, so we store it opaquely rather than re-deriving its fields here.
-- due_at/reps/lapses are pulled out as real columns because they're queried directly.
CREATE TABLE IF NOT EXISTS user_item_state (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES skill_items(id) ON DELETE CASCADE,
    fsrs_card_json TEXT NOT NULL,
    reps INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT,
    due_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);

-- claude_session_id is the claude CLI's own session UUID for this conversation (set after the
-- first reply), so later turns can `--resume` it instead of resending the full transcript.
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persona_id INTEGER NOT NULL REFERENCES personas(id),
    topic TEXT NOT NULL,
    claude_session_id TEXT,
    target_item_ids_json TEXT NOT NULL,
    is_proactive INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS message_item_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES skill_items(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN ('correct', 'hesitant', 'incorrect', 'avoided'))
);

CREATE INDEX IF NOT EXISTS idx_user_item_state_due ON user_item_state (user_id, due_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id, created_at);
