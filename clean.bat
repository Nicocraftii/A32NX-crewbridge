@echo off
echo 🔪 Arrêt de tous les processus Electron...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM "A32NX-Crewbridge.exe" 2>nul
taskkill /F /IM "CrewBridge.exe" 2>nul
taskkill /F /IM "A32NX CrewBridge.exe" 2>nul
timeout /t 2 /nobreak >nul

echo 🗑️ Nettoyage des dossiers...
rmdir /s /q dist 2>nul
rmdir /s /q node_modules 2>nul
del package-lock.json 2>nul

echo 🧹 Nettoyage du cache npm...
npm cache clean --force

echo 📦 Réinstallation des dépendances...
npm install express@4.18.3
npm install ejs@3.1.10
npm install winreg@1.2.5
npm install --save-dev electron@28.3.3 electron-packager@17.1.2

echo ✅ Prêt pour le build !
pause