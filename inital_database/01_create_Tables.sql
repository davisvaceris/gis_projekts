CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS citizen_actions (
    id INTEGER PRIMARY KEY,
    src TEXT,
    lon DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    n INTEGER,
    reporting_date TIMESTAMP,
    geom GEOMETRY(Point, 4326)
);

CREATE INDEX IF NOT EXISTS citizen_actions_geom_idx ON citizen_actions USING GIST (geom);
