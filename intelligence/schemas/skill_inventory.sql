-- Documentation-only relational shape for the filesystem skill inventory.
-- Runtime authority remains scripts/manage_skills.py and .agents/skills/.
CREATE TABLE skill_inventory (
    skill_name TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    has_skill_md INTEGER NOT NULL CHECK (has_skill_md IN (0, 1))
);
