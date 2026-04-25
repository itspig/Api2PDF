$ErrorActionPreference = "Stop"

python -m pip install -r requirements.txt pyinstaller==6.11.1
python -m PyInstaller `
  --clean `
  --noconfirm `
  --onefile `
  --noupx `
  --name api2pdf `
  --collect-data trafilatura `
  --collect-data reportlab `
  --collect-data certifi `
  --collect-submodules lxml `
  --exclude-module trafilatura.gui `
  --exclude-module gooey `
  --exclude-module matplotlib `
  --exclude-module numpy `
  --exclude-module reportlab.graphics.samples `
  --exclude-module reportlab.graphics.testdrawings `
  run.py

Write-Host "Built dist/api2pdf.exe"
