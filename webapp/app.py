from flask import Flask, request, Response, jsonify, render_template
import psycopg2
import requests
import time
from apscheduler.schedulers.background import BackgroundScheduler

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

def update_trees_job():
    """Runs every hour — imports new data and refreshes views."""
    print("Starting scheduled update job...")
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        import_data(cur)
        refresh_views(cur)
        conn.commit()
        cur.close()
        print("Scheduled update job finished successfully.")
    except Exception as e:
        print(f"Scheduled update job failed: {e}")
    finally:
        if conn:
            conn.close()

def import_data(cur):
    """Fetch from API and insert records."""
    url = "https://discomap.eea.europa.eu/Map/MapMyTreeAPI/CitizenAction"
    print(f"Fetching data from {url}...")

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        print(f"API returned {len(data)} records. Processing...")

        inserted = 0
        for item in data:
            cur.execute("""
                        INSERT INTO planted_trees (id, src, n, reporting_date, geom)
                        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326))
                        ON CONFLICT (id) DO UPDATE SET
                            src = EXCLUDED.src,
                            n = EXCLUDED.n,
                            reporting_date = EXCLUDED.reporting_date,
                            geom = EXCLUDED.geom;
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
    except Exception as e:
        print(f"Error importing data: {e}")
        raise


def update_trees_job():
    """Job to be run every hour."""
    print("Starting scheduled update job...")
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        import_data(cur)
        refresh_views(cur)
        conn.commit()
        cur.close()
        print("Scheduled update job finished successfully.")
    except Exception as e:
        print(f"Scheduled update job failed: {e}")
    finally:
        if conn:
            conn.close()

def refresh_views(cur):
    """Internal function used by scheduler and init_data."""
    views = [
        'mv_trees_base',
        'mv_trees_by_land_cover_l1',
        'mv_trees_by_land_cover_l2',
        'mv_trees_by_land_cover_l3',
    ]
    for view in views:
        print(f"Refreshing {view}...")
        cur.execute(f"REFRESH MATERIALIZED VIEW {view};")

    indexes = [
        'planted_trees_geom_idx',
        'corine_land_cover_geom_idx',
    ]
    for index in indexes:
        print(f"Reindexing {index}...")
        cur.execute(f"REINDEX INDEX {index};")

    tables = ['planted_trees', 'corine_land_cover', 'clc_data']
    for table in tables:
        cur.execute(f"ANALYZE public.{table};")

    print("All views refreshed, indexes reindexed, tables analyzed.")

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

            cur.execute("REFRESH MATERIALIZED VIEW mv_trees_by_land_cover_l1;")
            cur.execute("REFRESH MATERIALIZED VIEW mv_trees_by_land_cover_l2;")
            cur.execute("REFRESH MATERIALIZED VIEW mv_trees_by_land_cover_l3;")
            conn.commit()

            if count > 0:
                print(f"Data already present ({count} records). Skipping initial full import.")
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
def home_page():
    """Render the home page."""
    return render_template('home.html')


@app.route('/map')
def map_page():
    """Render the map page."""
    return render_template('index.html')


@app.route('/statistics')
def statistics_page():
    """Render the statistics page."""
    return render_template('statistics.html')


@app.route('/status')
def status():
    """Return DB status JSON."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM planted_trees;')
        count = cur.fetchone()[0]
        cur.execute('SELECT COALESCE(SUM(n), 0) FROM planted_trees;')
        sum_trees = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({
            "status": "success",
            "message": "Connected to PostGIS!",
            "records_count": count,
            "total_trees_planted": sum_trees
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
                                   'features', COALESCE(json_agg(
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
                                               ), '[]'::json)
                           )
                    FROM planted_trees;
                    """)
        result = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/stats/corine')
def get_corine_stats():
    level = request.args.get('level', '1')
    if level not in ['1', '2', '3']:
        level = '1'

    view_map = {
        '1': 'mv_trees_by_land_cover_l1',
        '2': 'mv_trees_by_land_cover_l2',
        '3': 'mv_trees_by_land_cover_l3',
    }
    view_name = view_map[level]

    query = f"SELECT planted_trees, label, rgb FROM {view_name} ORDER BY planted_trees DESC;"

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([
            {
                "planted_trees": row[0],
                "label": row[1],
                "rgb": row[2]
            }
            for row in rows
        ])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/refresh-views')
def refresh_views(cur):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Refresh materialized views in order
        views = [
            'mv_trees_base',
            'mv_trees_by_land_cover_l1',
            'mv_trees_by_land_cover_l2',
            'mv_trees_by_land_cover_l3',
        ]
        for view in views:
            print(f"Refreshing {view}...")
            cur.execute(f"REFRESH MATERIALIZED VIEW {view};")
        print("All views refreshed.")

        # Reindex spatial indexes
        indexes = [
            'planted_trees_geom_idx',
            'corine_land_cover_geom_idx',
        ]
        for index in indexes:
            print(f"Reindexing {index}...")
            cur.execute(f"REINDEX INDEX {index};")
        print("All indexes reindexed.")

        # Update statistics
        tables = [
            'planted_trees',
            'corine_land_cover',
            'clc_data',
        ]
        for table in tables:
            print(f"Analyzing {table}...")
            cur.execute(f"ANALYZE public.{table};")
        print("All tables analyzed.")

        conn.commit()
        cur.close()

        return jsonify({
            "status": "success",
            "message": "Views refreshed, indexes reindexed, statistics updated"
        })

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Refresh failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn:
            conn.close()

@app.route('/corine-proxy')
def corine_proxy():
    url = "https://image.discomap.eea.europa.eu/arcgis/services/Corine/CLC2018_WM/MapServer/WMSServer"
    params = request.args.to_dict()
    r = requests.get(url, params=params)
    return Response(r.content, content_type=r.headers['Content-Type'])
@app.route('/api/refresh')
def manual_refresh():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        imported = import_data(cur)
        refresh_views(cur)
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "records": imported})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/scheduler/status')
def scheduler_status():
    """Check scheduler status and next run time."""
    jobs = scheduler.get_jobs()
    return jsonify({
        "scheduler_running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "next_run": str(job.next_run_time),
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    })
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=update_trees_job,
    trigger="interval",
    hours=1,
    id="update_trees",
    max_instances=1,
    misfire_grace_time=300
)


if __name__ == '__main__':
    # Initial data setup
    init_data()

    scheduler.start()
    print("Scheduler started. Update job runs every hour.")

    try:
        app.run(host='0.0.0.0', port=5000, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler stopped.")
