CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS planted_trees (
    id INTEGER PRIMARY KEY,
    src TEXT,
    n INTEGER,
    reporting_date TIMESTAMP,
    geom GEOMETRY(Point, 4326)
);

CREATE INDEX IF NOT EXISTS planted_trees_geom_idx ON planted_trees USING GIST (geom);
