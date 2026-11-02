const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('origoPhone',{
  read:()=>ipcRenderer.invoke('origo-phone:read'),
  status:()=>ipcRenderer.invoke('origo-phone:status'),
  save:payload=>ipcRenderer.invoke('origo-phone:save',payload),
  disable:()=>ipcRenderer.invoke('origo-phone:disable')
});
