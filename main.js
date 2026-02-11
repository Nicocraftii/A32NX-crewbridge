const { app, BrowserWindow, Menu, Tray, ipcMain, dialog } = require('electron');
const path = require('path');
const { fork } = require('child_process');
const fs = require('fs');

let mainWindow = null;
let tray = null;
let serverProcess = null;
let serverPort = 8080;

// CORRECTION: Déterminer le chemin de base correct pour le mode packaged
const BASE_PATH = app.isPackaged 
  ? path.join(process.resourcesPath, 'app')  // Important: les fichiers sont dans resources/app
  : __dirname;

// Alternative: Si server.js est à la racine avec main.js
const SERVER_PATH = app.isPackaged
  ? path.join(process.resourcesPath, 'app', 'server.js')
  : path.join(__dirname, 'server.js');

console.log('🚀 Base path:', BASE_PATH);
console.log('📁 Server path:', SERVER_PATH);
console.log('📦 Running in:', app.isPackaged ? 'packaged app' : 'development mode');
console.log('📂 Resources path:', process.resourcesPath);

// Vérifier que server.js existe
try {
  fs.accessSync(SERVER_PATH);
  console.log('✅ server.js found');
} catch (err) {
  console.error('❌ server.js NOT found at:', SERVER_PATH);
  
  // Chercher dans d'autres emplacements possibles
  const alternativePaths = [
    path.join(process.resourcesPath, 'server.js'),
    path.join(process.resourcesPath, 'app.asar', 'server.js'),
    path.join(__dirname, 'server.js'),
    path.join(process.cwd(), 'server.js')
  ];
  
  for (const altPath of alternativePaths) {
    try {
      fs.accessSync(altPath);
      console.log('✅ Found server.js at:', altPath);
      SERVER_PATH = altPath;
      break;
    } catch (e) {}
  }
}

// Fonction pour démarrer le serveur Express
function startServer() {
  return new Promise((resolve, reject) => {
    try {
      console.log('🚀 Starting server from:', SERVER_PATH);
      
      // Lancer server.js comme un processus séparé
      serverProcess = fork(SERVER_PATH, ['--port', serverPort], {
        cwd: app.isPackaged ? path.dirname(SERVER_PATH) : BASE_PATH,
        env: { 
          ...process.env, 
          ELECTRON_RUN: 'true',
          APP_PATH: BASE_PATH
        }
      });

      serverProcess.on('message', (msg) => {
        if (msg.type === 'ready') {
          console.log(`✅ Serveur démarré sur le port ${msg.port}`);
          resolve(msg.port);
        }
      });

      serverProcess.on('error', (err) => {
        console.error('❌ Erreur serveur:', err);
        reject(err);
      });

      serverProcess.on('exit', (code) => {
        console.log(`⚠️ Server process exited with code ${code}`);
      });

    } catch (error) {
      console.error('❌ Erreur démarrage serveur:', error);
      reject(error);
    }
  });
}
// Créer la fenêtre principale
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    },
    icon: path.join(BASE_PATH, 'public', 'assets', 'icon.png'),
    show: false,
    frame: true,
    titleBarStyle: 'default'
  });

  // Charger l'interface du serveur
  mainWindow.loadURL(`http://localhost:${serverPort}`);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // GESTION DE LA MINIMISATION VERS LA TRAY
  mainWindow.on('minimize', (event) => {
    event.preventDefault();
    mainWindow.hide();
    
    // Afficher une notification si on veut
    if (tray) {
      tray.displayBalloon({
        title: 'A32NX CrewBridge',
        content: 'L\'application continue de tourner dans la barre système',
        icon: path.join(BASE_PATH, 'public', 'assets', 'icon.png')
      });
    }
  });

  mainWindow.on('close', (event) => {
    // Si on clique sur la croix, on minimise vers la tray au lieu de quitter
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      
      if (tray) {
        tray.displayBalloon({
          title: 'A32NX CrewBridge',
          content: 'L\'application continue de tourner dans la barre système',
          icon: path.join(BASE_PATH, 'public', 'assets', 'icon.png')
        });
      }
      return false;
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Menu personnalisé
  const menu = Menu.buildFromTemplate([
    {
      label: 'Fichier',
      submenu: [
        {
          label: 'Redémarrer le serveur',
          click: async () => {
            await restartServer();
          }
        },
        { type: 'separator' },
        { 
          label: 'Quitter', 
          click: () => {
            app.isQuitting = true;
            app.quit();
          }
        }
      ]
    },
    {
      label: 'Affichage',
      submenu: [
        { role: 'reload', label: 'Actualiser' },
        { role: 'forceReload', label: 'Actualiser forcé' },
        { role: 'toggleDevTools', label: 'Outils de développement' },
        { type: 'separator' },
        { role: 'resetZoom', label: 'Zoom par défaut' },
        { role: 'zoomIn', label: 'Zoom avant' },
        { role: 'zoomOut', label: 'Zoom arrière' }
      ]
    },
    {
      label: 'Aide',
      submenu: [
        {
          label: 'À propos',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'À propos de CrewBridge',
              message: 'A32NX CrewBridge v1.0.0',
              detail: 'Application de communication pour Microsoft Flight Simulator',
              buttons: ['OK']
            });
          }
        }
      ]
    }
  ]);
  Menu.setApplicationMenu(menu);

  // Tray icon (doit être créée avant ou après selon l'ordre)
  createTray();
}

// Créer l'icône dans la barre système
function createTray() {
  const iconPath = path.join(BASE_PATH, 'public', 'assets', 'icon.png');
  
  if (fs.existsSync(iconPath)) {
    tray = new Tray(iconPath);
    
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Afficher la fenêtre',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
          }
        }
      },
      {
        label: 'Masquer la fenêtre',
        click: () => {
          if (mainWindow) {
            mainWindow.hide();
          }
        }
      },
      { type: 'separator' },
      {
        label: 'Redémarrer le serveur',
        click: async () => {
          await restartServer();
        }
      },
      { type: 'separator' },
      {
        label: 'Quitter',
        click: () => {
          app.isQuitting = true;
          app.quit();
        }
      }
    ]);
    
    tray.setToolTip('A32NX CrewBridge');
    tray.setContextMenu(contextMenu);
    
    // Clic gauche sur la tray
    tray.on('click', () => {
      if (mainWindow) {
        mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
      }
    });
    
    // Double-clic sur la tray
    tray.on('double-click', () => {
      if (mainWindow) {
        mainWindow.show();
      }
    });
    
    // Afficher une notification au démarrage
    setTimeout(() => {
      tray.displayBalloon({
        title: 'A32NX CrewBridge',
        content: 'L\'application est en cours d\'exécution dans la barre système',
        icon: iconPath
      });
    }, 2000);
  } else {
    console.error('❌ Icône non trouvée:', iconPath);
  }
}

// Redémarrer le serveur
async function restartServer() {
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
  }
  
  await startServer();
  
  if (mainWindow) {
    mainWindow.loadURL(`http://localhost:${serverPort}`);
  }
}

// IPC Handlers
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Sélectionner le dossier Community'
  });
  
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
});

ipcMain.handle('get-app-path', () => {
  return {
    basePath: BASE_PATH,
    isPackaged: app.isPackaged
  };
});

ipcMain.handle('restart-server', restartServer);

// Initialisation de l'application
app.whenReady().then(async () => {
  try {
    await startServer();
    createWindow();
  } catch (error) {
    console.error('❌ Erreur au démarrage:', error);
    dialog.showErrorBox('Erreur', `Impossible de démarrer le serveur: ${error.message}`);
    app.quit();
  }
});

// Gestionnaire pour éviter de quitter quand toutes les fenêtres sont fermées
app.on('window-all-closed', (event) => {
  // Ne pas quitter automatiquement, on garde la tray
  event.preventDefault();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  } else if (mainWindow) {
    mainWindow.show();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
});

app.on('will-quit', () => {
  if (serverProcess) {
    serverProcess.kill();
  }
});

// Ajouter une variable pour suivre si on quitte vraiment
app.isQuitting = false;