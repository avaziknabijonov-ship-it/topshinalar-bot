'use strict';
const { contextBridge, ipcRenderer } = require('electron');

// Exposed only to the app's own local pages (setup / offline); the main process re-checks the sender.
contextBridge.exposeInMainWorld('desktopConfig', {
  get: () => ipcRenderer.invoke('config:get'),
  save: url => ipcRenderer.invoke('config:save', url),
  retry: () => ipcRenderer.invoke('config:retry'),
});
