const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('indraDesktop',Object.freeze({pickFolder:()=>ipcRenderer.invoke('indra:pick-folder')}));
