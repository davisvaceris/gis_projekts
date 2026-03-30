from flask import Flask, jsonify
import psycopg2
import requests
import time

app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(
        host='db',
        database='gis_db',
        user='user',
        password='password',
        connect_timeout=5
    )


def init_db(cur):
    """Create tables if they don't exist."""
    cur.execute("""
                CREATE
                EXTENSION IF NOT EXISTS postgis;

                CREATE TABLE IF NOT EXISTS planted_trees
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY,
                    src
                    TEXT,
                    n
                    INTEGER,
                    reporting_date
                    TIMESTAMP,
                    geom
                    GEOMETRY
                (
                    Point,
                    4326
                )
                    );

                CREATE INDEX IF NOT EXISTS planted_trees_geom_idx
                    ON planted_trees USING GIST (geom);
                """)


def import_data(cur):
    """Fetch from API and insert records."""
    url = "https://discomap.eea.europa.eu/Map/MapMyTreeAPI/CitizenAction"
    print(f"Fetching data from {url}...")

    response = requests.get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    },
    timeout=30
)
    response.raise_for_status()  # raises if status != 200

    data = response.json()
    print(f"API returned {len(data)} records. Inserting...")

    # Debug: print first record to verify field names
    if data:
        print(f"Sample record: {data[0]}")

    inserted = 0
    for item in data:
        cur.execute("""
                    INSERT INTO planted_trees (id, src, n, reporting_date, geom)
                    VALUES (%s, %s, %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326)) ON CONFLICT (id) DO NOTHING;
                    """, (
                        item.get('id'),
                        item.get('src'),
                        item.get('n'),
                        item.get('reportingDate'),
                        item.get('lon'),
                        item.get('lat')
                    ))
        inserted += 1

    print(f"Done. {inserted} records processed.")
    return inserted


def init_data():
    print("Waiting for database...")
    while True:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            print("Connected. Initializing schema...")

            init_db(cur)
            conn.commit()
            print("Schema ready.")

            # Check if data already exists
            cur.execute("SELECT COUNT(*) FROM planted_trees;")
            count = cur.fetchone()[0]

            if count > 0:
                print(f"Data already present ({count} records). Skipping import.")
            else:
                import_data(cur)
                conn.commit()

            cur.close()
            conn.close()
            break  # success — exit loop

        except psycopg2.OperationalError as e:
            print(f"DB not ready yet: {e} — retrying in 2s...")
            time.sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e} — retrying in 5s...")
            time.sleep(5)

        except Exception as e:
            print(f"Unexpected error ({type(e).__name__}): {e}")
            break  # don't loop forever on unknown errors


@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM planted_trees;')
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({
            "status": "success",
            "message": "Connected to PostGIS!",
            "records_count": count
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/trees')
def get_trees():
    """Return all trees as GeoJSON."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                    SELECT json_build_object(
                                   'type', 'FeatureCollection',
                                   'features', json_agg(
                                           json_build_object(
                                                   'type', 'Feature',
                                                   'geometry', ST_AsGeoJSON(geom)::json,
                                                   'properties', json_build_object(
                                                           'id', id,
                                                           'src', src,
                                                           'n', n,
                                                           'reporting_date', reporting_date
                                                                 )
                                           )
                                               )
                           )
                    FROM planted_trees;
                    """)
        result = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    init_data()
    app.run(host='0.0.0.0', port=5000)