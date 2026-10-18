@echo off
powershell.exe -NoProfile -WindowStyle Hidden -File "%~dp0scripts\product-stop.ps1"
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/product-ui-stop.sh
