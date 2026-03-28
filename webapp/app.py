from flask import Flask, jsonify
import os
import psycopg2
import requests
import time

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(
        host='db',
        database='gis_db',
        user='user',
        password='password'
    )

def init_data():
    print("Importing data from API...")
    while True:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Import data from API
            response = requests.get("https://discomap.eea.europa.eu/Map/MapMyTreeAPI/CitizenAction")
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    cur.execute("""
                        INSERT INTO citizen_actions (id, src, lon, lat, n, reporting_date, geom)
                        VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326))
                        ON CONFLICT (id) DO NOTHING;
                    """, (
                        item['id'], 
                        item['src'], 
                        item['lon'], 
                        item['lat'], 
                        item['n'], 
                        item['reportingDate'],
                        item['lon'],
                        item['lat']
                    ))
                conn.commit()
                print(f"Successfully imported {len(data)} records.")
            
            cur.close()
            conn.close()
            break
        except Exception as e:
            print(f"Database/Table not ready yet... {e}")
            time.sleep(2)

@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM citizen_actions;')
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({
            "status": "success",
            "message": "Connected to PostGIS!",
            "records_count": count
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    init_data()
    app.run(host='0.0.0.0', port=5000)
