PAKISTAN CLIMATE OBSERVATORY
=============================

FOLDER CONTENTS:
  dashboard.html         ← Open this in your browser
  export_climate_data.py ← Run this once to connect your DB

HOW TO CONNECT YOUR DATABASE
==============================

Step 1: Edit export_climate_data.py
  Open the file and change line 38:
    DB_PATH = "climate.db"
  to your actual database filename, e.g.:
    DB_PATH = "pakistan_climate.db"

Step 2: Run the export script
  Open a terminal in this folder and run:
    python export_climate_data.py

  This creates climate_data.json (takes ~30 seconds for large DBs)

Step 3: Open the dashboard
  Open dashboard.html in your browser.
  You will see a GREEN banner: "✓ Real database loaded"

THAT'S IT! No server needed.

TROUBLESHOOTING
================
Problem: "climate_data.json not found" (yellow banner)
  → You haven't run export_climate_data.py yet, or it's in a different folder

Problem: "Table 'climate' not found"
  → Check your table name. Edit the SQL in export_climate_data.py if different.

Problem: Some districts show no color on the map
  → The district name in your DB doesn't match exactly.
     Check district names in your DB: SELECT DISTINCT district FROM climate LIMIT 20;

Your DB columns used:
  date             → YYYYMMDD integer (19950101)
  district, province
  emp_max_c, emp_min_c  → for temperature
  precipitation_mm      → rainfall
  speed_                → wind speed
  s_humidity            → humidity
  v_depth               → snow depth
