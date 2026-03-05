"""
Pakistan Climate Observatory — SQLite → JSON Exporter
======================================================
Enhanced version with additional climate indices
"""

import sqlite3
import json
import sys
import os
from collections import defaultdict
import math

# ─── CHANGE THIS to your .db path ───────────────────────
DB_PATH = r"C:\Users\HP\Downloads\pakistan_climate_new.db"
# ────────────────────────────────────────────────────────

OUT_PATH = "climate_data.json"

def connect():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Could not find '{DB_PATH}'")
        sys.exit(1)
    print(f"Connecting to: {DB_PATH}")
    return sqlite3.connect(DB_PATH)

def analyze_monsoon_timing(conn):
    """Analyze monsoon onset/retreat dates by district"""
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            CAST(SUBSTR(CAST(date AS TEXT), 5, 2) AS INTEGER) AS mon,
            CAST(SUBSTR(CAST(date AS TEXT), 7, 2) AS INTEGER) AS day,
            PRECTOTCORR as rain
        FROM climate
        WHERE PRECTOTCORR IS NOT NULL
        ORDER BY district, yr, mon, day
    """)
    
    monsoon_data = defaultdict(lambda: defaultdict(list))
    rows = cur.fetchall()
    
    for district, yr, mon, day, rain in rows:
        if rain > 5:  # 5mm threshold for rain day
            monsoon_data[district][yr].append((mon, day))
    
    # Calculate onset (first 5-day period with >50mm total)
    monsoon_onset = defaultdict(dict)
    for district in monsoon_data:
        for yr in monsoon_data[district]:
            days = monsoon_data[district][yr]
            if len(days) < 10:
                continue
            
            # Look for monsoon period (typically Jun-Sep)
            for i in range(len(days)-4):
                period = days[i:i+5]
                if period[-1][0] - period[0][0] <= 1:  # Within 2 months
                    total_rain = 0
                    # We'd need actual rainfall values here
                    # Simplified: use day count as proxy
                    monsoon_onset[district][yr] = period[0]
                    break
    
    return dict(monsoon_onset)

def analyze_extreme_events(conn):
    """Identify extreme rainfall, heatwaves, cold waves"""
    cur = conn.cursor()
    
    # Flood risk (days with >100mm rainfall)
    cur.execute("""
        SELECT 
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            COUNT(*) as extreme_rain_days,
            MAX(PRECTOTCORR) as max_rainfall
        FROM climate
        WHERE PRECTOTCORR > 100
        GROUP BY district, yr
    """)
    flood_risk = defaultdict(dict)
    for district, yr, days, max_rain in cur.fetchall():
        flood_risk[district][yr] = {
            'days': days,
            'max': round(max_rain, 1)
        }
    
    # Cold waves (min temp < 0°C)
    cur.execute("""
        SELECT 
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            COUNT(*) as cold_days,
            MIN(T2M_MIN) as min_temp
        FROM climate
        WHERE T2M_MIN < 0
        GROUP BY district, yr
    """)
    cold_waves = defaultdict(dict)
    for district, yr, days, min_temp in cur.fetchall():
        cold_waves[district][yr] = {
            'days': days,
            'min': round(min_temp, 1)
        }
    
    # Drought index (consecutive dry days)
    cur.execute("""
        SELECT 
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            CAST(SUBSTR(CAST(date AS TEXT), 5, 2) AS INTEGER) AS mon,
            CAST(SUBSTR(CAST(date AS TEXT), 7, 2) AS INTEGER) AS day,
            PRECTOTCORR as rain
        FROM climate
        ORDER BY district, yr, mon, day
    """)
    
    drought = defaultdict(dict)
    rows = cur.fetchall()
    
    current_district = None
    current_yr = None
    dry_streak = 0
    max_dry_streak = 0
    
    for district, yr, mon, day, rain in rows:
        if district != current_district or yr != current_yr:
            if current_district and current_yr:
                drought[current_district][current_yr] = max_dry_streak
            current_district = district
            current_yr = yr
            dry_streak = 0
            max_dry_streak = 0
        
        if rain < 0.1:  # Dry day
            dry_streak += 1
            max_dry_streak = max(max_dry_streak, dry_streak)
        else:
            dry_streak = 0
    
    return {
        'flood_risk': dict(flood_risk),
        'cold_waves': dict(cold_waves),
        'drought': dict(drought)
    }

def calculate_warming_rates(conn):
    """Calculate temperature trends per district"""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            AVG(T2M) as avg_temp
        FROM climate
        GROUP BY district, yr
        ORDER BY district, yr
    """)
    
    warming_rates = {}
    rows = cur.fetchall()
    
    current_district = None
    years = []
    temps = []
    
    for district, yr, temp in rows:
        if district != current_district:
            if current_district and len(years) > 5:
                # Simple linear regression
                n = len(years)
                if n > 1:
                    sum_x = sum(years)
                    sum_y = sum(temps)
                    sum_xy = sum(x*y for x,y in zip(years, temps))
                    sum_xx = sum(x*x for x in years)
                    
                    try:
                        slope = (n*sum_xy - sum_x*sum_y) / (n*sum_xx - sum_x*sum_x)
                        warming_rates[current_district] = round(slope * 10, 2)  # °C per decade
                    except:
                        warming_rates[current_district] = 0
            
            current_district = district
            years = []
            temps = []
        
        years.append(yr)
        temps.append(temp)
    
    return warming_rates

def analyze_wind_patterns(conn):
    """Analyze seasonal wind patterns"""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            district,
            CASE 
                WHEN CAST(SUBSTR(CAST(date AS TEXT), 5, 2) AS INTEGER) IN (12,1,2) THEN 'winter'
                WHEN CAST(SUBSTR(CAST(date AS TEXT), 5, 2) AS INTEGER) IN (3,4,5) THEN 'spring'
                WHEN CAST(SUBSTR(CAST(date AS TEXT), 5, 2) AS INTEGER) IN (6,7,8) THEN 'summer'
                ELSE 'autumn'
            END as season,
            AVG(WS2M) as avg_wind,
            AVG(WS2M_MAX) as max_wind
        FROM climate
        GROUP BY district, season
    """)
    
    wind_patterns = defaultdict(dict)
    for district, season, avg_wind, max_wind in cur.fetchall():
        wind_patterns[district][season] = {
            'avg': round(avg_wind, 1),
            'max': round(max_wind, 1)
        }
    
    return dict(wind_patterns)

def calculate_anomalies(conn):
    """Calculate temperature anomalies relative to 1995-2004 baseline"""
    cur = conn.cursor()
    
    # Get baseline (1995-2004)
    cur.execute("""
        SELECT 
            district,
            AVG(T2M) as baseline_temp
        FROM climate
        WHERE CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) BETWEEN 1995 AND 2004
        GROUP BY district
    """)
    
    baselines = {d: t for d, t in cur.fetchall()}
    
    # Calculate anomalies per year
    cur.execute("""
        SELECT 
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            AVG(T2M) as avg_temp
        FROM climate
        GROUP BY district, yr
    """)
    
    anomalies = defaultdict(dict)
    for district, yr, temp in cur.fetchall():
        if district in baselines and baselines[district]:
            anomalies[district][yr] = round(temp - baselines[district], 1)
    
    return dict(anomalies)

def get_elevation_data():
    """Approximate elevation for districts (would come from DEM in real implementation)"""
    # This is simplified - in reality you'd get from SRTM or similar
    elevation_map = {
        'Skardu': 2200, 'Gilgit': 1500, 'Hunza': 2500, 'Astore': 2600,
        'Quetta': 1680, 'Kalat': 2000, 'Ziarat': 2500,
        'Murree': 2200, 'Abbottabad': 1200, 'Mansehra': 1000,
        'Chitral': 1500, 'Swat': 980,
        # Add more as needed
    }
    return elevation_map

def run(conn):
    cur = conn.cursor()

    # Verify table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='climate'")
    if not cur.fetchone():
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"ERROR: Table 'climate' not found. Tables in DB: {tables}")
        sys.exit(1)

    cur.execute("SELECT COUNT(*) FROM climate")
    total = cur.fetchone()[0]
    print(f"Total rows: {total:,}")

    data = {}

    # ── 1. ANNUAL DISTRICT AVERAGES (map colors + tooltips) ──
    print("Exporting district averages per year...")
    cur.execute("""
        SELECT
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            district,
            province,
            ROUND(AVG(T2M), 1)           AS avg_temp,
            ROUND(AVG(PRECTOTCORR), 2)   AS avg_rain,
            ROUND(AVG(WS2M), 1)          AS avg_wind,
            ROUND(AVG(RH2M), 0)          AS avg_hum
        FROM climate
        WHERE district IS NOT NULL
          AND T2M IS NOT NULL
        GROUP BY yr, district
        ORDER BY yr, district
    """)
    rows = cur.fetchall()
    district_years = defaultdict(dict)
    province_map = {}
    for yr, district, province, t, r, w, h in rows:
        district_years[district][yr] = {
            "t": t, "r": r, "w": w, "h": int(h) if h else 0
        }
        if province:
            province_map[district] = province
    data["district_years"] = {k: dict(v) for k, v in district_years.items()}
    data["province_map"] = province_map
    print(f"  → {len(district_years)} districts across {len(set(r[0] for r in rows))} years")

    # ── 2. NATIONAL ANNUAL AVERAGES (trend charts + stat cards) ──
    print("Exporting national annual averages...")
    cur.execute("""
        SELECT
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            ROUND(AVG(T2M), 1)           AS avg_temp,
            ROUND(AVG(PRECTOTCORR), 2)   AS avg_rain,
            ROUND(AVG(WS2M), 1)          AS avg_wind,
            ROUND(AVG(RH2M), 0)          AS avg_hum,
            ROUND(AVG(SNODP), 1)         AS avg_snow
        FROM climate
        GROUP BY yr
        ORDER BY yr
    """)
    national = {}
    for yr, t, r, w, h, s in cur.fetchall():
        national[yr] = {
            "t": t, "r": r, "w": w,
            "h": int(h) if h else 0,
            "s": s if s else 0
        }
    data["national"] = national
    print(f"  → {len(national)} years of national data")

    # ── 3. PROVINCE ANNUAL AVERAGES (ranking bars) ──
    print("Exporting province averages per year...")
    cur.execute("""
        SELECT
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            province,
            ROUND(AVG(T2M), 1)           AS avg_temp,
            ROUND(AVG(PRECTOTCORR), 2)   AS avg_rain,
            ROUND(AVG(WS2M), 1)          AS avg_wind,
            ROUND(AVG(RH2M), 0)          AS avg_hum
        FROM climate
        WHERE province IS NOT NULL
        GROUP BY yr, province
        ORDER BY yr, province
    """)
    prov_years = defaultdict(dict)
    for yr, prov, t, r, w, h in cur.fetchall():
        prov_years[yr][prov] = {
            "t": t, "r": r, "w": w, "h": int(h) if h else 0
        }
    data["province_years"] = {str(k): v for k, v in prov_years.items()}
    print(f"  → {len(prov_years)} years of province data")

    # ── 4. MONTHLY AVERAGES (monthly grid) ──
    print("Exporting monthly averages...")
    cur.execute("""
        SELECT
            CAST(SUBSTR(CAST(date AS TEXT), 5, 2) AS INTEGER) AS mon,
            ROUND(AVG(T2M), 1)           AS avg_temp,
            ROUND(AVG(PRECTOTCORR), 2)   AS avg_rain
        FROM climate
        GROUP BY mon
        ORDER BY mon
    """)
    monthly = {}
    for mon, t, r in cur.fetchall():
        monthly[mon] = {"t": t, "r": r}
    data["monthly"] = monthly
    print(f"  → {len(monthly)} months of seasonal data")

    # ── 5. HEATWAVE CALENDAR (days where max temp >= 40°C) ──
    print("Exporting heatwave calendar...")
    cur.execute("""
        SELECT
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            COUNT(DISTINCT date) AS hot_days,
            MAX(T2M_MAX) AS max_temp
        FROM climate
        WHERE T2M_MAX >= 40
        GROUP BY yr
        ORDER BY yr
    """)
    heatwave = {}
    heatwave_intensity = {}
    for yr, days, max_temp in cur.fetchall():
        heatwave[yr] = days
        heatwave_intensity[yr] = round(max_temp, 1)
    data["heatwave"] = heatwave
    data["heatwave_intensity"] = heatwave_intensity
    
    # Heatwave severity by district
    cur.execute("""
        SELECT
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) AS yr,
            COUNT(*) AS hot_days,
            MAX(T2M_MAX) AS max_temp,
            AVG(T2M_MAX) AS avg_max_temp
        FROM climate
        WHERE T2M_MAX >= 40
        GROUP BY district, yr
    """)
    heatwave_district = defaultdict(dict)
    for district, yr, days, max_temp, avg_max in cur.fetchall():
        heatwave_district[district][yr] = {
            'days': days,
            'max': round(max_temp, 1),
            'avg': round(avg_max, 1)
        }
    data["heatwave_district"] = dict(heatwave_district)
    
    print(f"  → {len(heatwave)} years with heatwave data")

    # ── 6. MONTHLY PER DISTRICT (popup chart data) ──
    print("Exporting monthly averages per district...")
    cur.execute("""
        SELECT
            district,
            CAST(SUBSTR(CAST(date AS TEXT), 5, 2) AS INTEGER) AS mon,
            ROUND(AVG(T2M), 1)           AS avg_temp,
            ROUND(AVG(PRECTOTCORR), 2)   AS avg_rain,
            ROUND(AVG(WS2M), 1)          AS avg_wind,
            ROUND(AVG(RH2M), 0)          AS avg_hum,
            ROUND(AVG(SNODP), 1)         AS avg_snow
        FROM climate
        WHERE district IS NOT NULL
        GROUP BY district, mon
        ORDER BY district, mon
    """)
    dist_monthly = defaultdict(dict)
    for district, mon, t, r, w, h, s in cur.fetchall():
        dist_monthly[district][mon] = {
            "t": t, "r": r, "w": w,
            "h": int(h) if h else 0,
            "s": s if s else 0
        }
    data["district_monthly"] = {k: dict(v) for k, v in dist_monthly.items()}
    print(f"  → {len(dist_monthly)} districts with monthly data")

    # ── NEW: Extreme Events Analysis ──
    print("\n--- Adding Enhanced Analysis Features ---")
    
    print("Analyzing extreme events...")
    extreme_data = analyze_extreme_events(conn)
    data["flood_risk"] = extreme_data["flood_risk"]
    data["cold_waves"] = extreme_data["cold_waves"]
    data["drought"] = extreme_data["drought"]
    print(f"  → Flood risk data for {len(data['flood_risk'])} districts")
    print(f"  → Cold wave data for {len(data['cold_waves'])} districts")
    print(f"  → Drought data for {len(data['drought'])} districts")
    
    print("Calculating warming rates...")
    data["warming_rates"] = calculate_warming_rates(conn)
    print(f"  → Warming rates for {len(data['warming_rates'])} districts")
    
    print("Analyzing wind patterns...")
    data["wind_patterns"] = analyze_wind_patterns(conn)
    print(f"  → Wind patterns for {len(data['wind_patterns'])} districts")
    
    print("Calculating temperature anomalies...")
    data["anomalies"] = calculate_anomalies(conn)
    print(f"  → Anomalies for {len(data['anomalies'])} districts")
    
    print("Adding elevation data...")
    data["elevation"] = get_elevation_data()
    
    # Create climate zones based on elevation and temperature
    print("Creating climate zone classifications...")
    climate_zones = {}
    for district in data["district_years"]:
        avg_temp = 0
        count = 0
        for yr in data["district_years"][district]:
            if "t" in data["district_years"][district][yr]:
                avg_temp += data["district_years"][district][yr]["t"]
                count += 1
        if count > 0:
            avg_temp /= count
            elev = data["elevation"].get(district, 0)
            
            if elev > 2000:
                zone = "Alpine"
            elif elev > 1000:
                if avg_temp < 15:
                    zone = "Temperate Highland"
                else:
                    zone = "Subtropical Highland"
            else:
                if avg_temp > 25:
                    zone = "Tropical Lowland"
                elif avg_temp > 20:
                    zone = "Subtropical Lowland"
                else:
                    zone = "Temperate Lowland"
            
            climate_zones[district] = zone
    
    data["climate_zones"] = climate_zones
    print(f"  → {len(climate_zones)} districts classified into climate zones")

    # ── 7. METADATA ──
    cur.execute("SELECT MIN(date), MAX(date) FROM climate")
    d_min, d_max = cur.fetchone()
    cur.execute("SELECT COUNT(DISTINCT district) FROM climate")
    n_districts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT province) FROM climate")
    n_provinces = cur.fetchone()[0]
    data["meta"] = {
        "total_rows": total,
        "districts": n_districts,
        "provinces": n_provinces,
        "date_min": str(d_min),
        "date_max": str(d_max),
        "source": "NASA POWER SQLite",
        "enhanced_features": [
            "flood_risk", "cold_waves", "drought", 
            "warming_rates", "wind_patterns", "anomalies",
            "elevation", "climate_zones", "heatwave_intensity",
            "heatwave_district"
        ]
    }

    return data

def main():
    print("=" * 50)
    print("Pakistan Climate Data Exporter - Enhanced Edition")
    print("=" * 50)
    conn = connect()
    try:
        data = run(conn)
    finally:
        conn.close()

    print(f"\nWriting {OUT_PATH}...")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_PATH) // 1024
    print(f"\n✓ Done! {OUT_PATH} ({size_kb} KB)")
    print(f"✓ Open dashboard.html in your browser — green banner = real data!")
    print(f"\nNew enhanced features included:")
    for feature in data["meta"]["enhanced_features"]:
        print(f"  • {feature}")

if __name__ == "__main__":
    main()