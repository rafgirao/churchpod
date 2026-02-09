-- 1. Table for Podcast Metadata (Settings)
CREATE TABLE IF NOT EXISTS podcast_meta (
    id int PRIMARY KEY DEFAULT 1,
    title text NOT NULL,
    description text,
    author text,
    email text,
    link text,
    image_url text,
    CONSTRAINT single_row CHECK (id = 1) -- Ensures only one row exists for settings
);

-- 2. Table for Podcast Episodes
CREATE TABLE IF NOT EXISTS episodes (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at timestamptz DEFAULT now(),
    title text NOT NULL,
    description text,
    audio_url text NOT NULL,
    image_url text,
    duration text,
    pub_date timestamptz DEFAULT now()
);

-- Enable RLS (Optional but recommended)
ALTER TABLE podcast_meta ENABLE ROW LEVEL SECURITY;
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;

-- Allow public read access to both
CREATE POLICY "Allow public read for meta" ON podcast_meta FOR SELECT USING (true);
CREATE POLICY "Allow public read for episodes" ON episodes FOR SELECT USING (true);

-- Insert initial metadata from your current settings (Example)
INSERT INTO podcast_meta (id, title, description, author, email, link, image_url)
VALUES (1, 'My Church Podcast', 'Church preaching and messages.', 'My Church', 'contact@example.com', 'https://example.com', 'https://images.unsplash.com/photo-1585829365234-78d1b6c06639')
ON CONFLICT (id) DO NOTHING;
