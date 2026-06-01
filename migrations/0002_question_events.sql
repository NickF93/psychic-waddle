CREATE TABLE question_events (
    id bigserial PRIMARY KEY,
    raw_question_text text NOT NULL,
    review_state text NOT NULL DEFAULT 'pending',
    review_category text,
    review_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT question_events_raw_question_text_not_blank CHECK (
        length(btrim(raw_question_text)) > 0
    ),
    CONSTRAINT question_events_review_state_allowed CHECK (
        review_state IN (
            'pending',
            'reviewed',
            'ignored'
        )
    ),
    CONSTRAINT question_events_review_category_allowed CHECK (
        review_category IS NULL OR review_category IN (
            'missing_fact',
            'alias',
            'eval_case',
            'unclear',
            'off_topic',
            'private_data',
            'spam',
            'other'
        )
    ),
    CONSTRAINT question_events_review_note_not_blank CHECK (
        review_note IS NULL OR length(btrim(review_note)) > 0
    )
);

CREATE INDEX question_events_review_state_idx
    ON question_events(review_state);

CREATE INDEX question_events_created_at_idx
    ON question_events(created_at);
