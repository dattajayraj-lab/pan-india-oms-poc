# Regenerating the user manuals

1. Start the app with demo data: `.\start-oms.ps1 -Reset -Demo` (from the OMS-POC folder).
2. Capture screenshots (needs Node and Microsoft Edge):
   ```powershell
   mkdir $env:TEMP\oms-shots; cd $env:TEMP\oms-shots
   npm init -y; npm i playwright-core@1.48.2
   node "<OMS-POC>\Docs\User_Manuals\_build\capture.js" .\png
   ```
   `capture.js` signs in as each demo role (superadmin, nr_coord, nr_shiftic, nr_outage, nr_protection,
   nr_alerts, re_dev, tpcomm_user, pg_user) and saves 1440x900 screenshots of every menu page.
3. Build the PDFs:
   ```powershell
   backend\.venv\Scripts\python.exe Docs\User_Manuals\_build\build_manuals.py $env:TEMP\oms-shots\png Docs\User_Manuals
   ```
Manual text lives in `manual_content.py`; the layout is in `build_manuals.py`.
