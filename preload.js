const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  restartServer: () => ipcRenderer.invoke('restart-server'),
  

  onServerStatus: (callback) => {
    ipcRenderer.on('server-status', (event, status) => callback(status));
  }
});