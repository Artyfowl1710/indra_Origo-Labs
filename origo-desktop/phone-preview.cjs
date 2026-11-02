// Isolated renderer/IPC acceptance probe. Never saves settings or starts sharing.
const {app,BrowserWindow,ipcMain,nativeTheme}=require('electron');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {authorizeSetup}=require('./phone-window.cjs');
const output=path.resolve(__dirname,'../data/test-results');
fs.mkdirSync(output,{recursive:true});
app.setPath('userData',path.resolve(__dirname,'../data/phone-preview-desktop'));
const setupUrl=pathToFileURL(path.join(__dirname,'phone-setup.html')).href;
let trusted,foreign;
const rows=[];
async function paint(window){
  await window.webContents.executeJavaScript('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
}
app.whenReady().then(async()=>{
  try{
    ipcMain.handle('origo-phone:read',event=>{
      authorizeSetup(event,trusted,setupUrl);
      return {settings:null,share:{state:'off',message:'Phone sharing is off. Your workstation stays on this PC until you configure private access.'}};
    });
    ipcMain.handle('origo-phone:status',event=>{authorizeSetup(event,trusted,setupUrl);return {state:'off',message:'Phone sharing is off.'};});
    nativeTheme.themeSource='dark';
    trusted=new BrowserWindow({show:false,width:600,height:820,webPreferences:{preload:path.join(__dirname,'phone-preload.cjs'),sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
    await trusted.loadURL(setupUrl);
    await trusted.webContents.executeJavaScript('window.origoPhone.read()');
    await paint(trusted);
    fs.writeFileSync(path.join(output,'phone-setup-dark.png'),(await trusted.webContents.capturePage()).toPNG());
    rows.push({case:'trusted-window-read',passed:true});
    const isolated=await trusted.webContents.executeJavaScript("typeof require === 'undefined' && typeof process === 'undefined'");
    rows.push({case:'renderer-node-isolation',passed:isolated});
    nativeTheme.themeSource='light';
    await paint(trusted);
    fs.writeFileSync(path.join(output,'phone-setup-light.png'),(await trusted.webContents.capturePage()).toPNG());
    foreign=new BrowserWindow({show:false,webPreferences:{preload:path.join(__dirname,'phone-preload.cjs'),sandbox:true,contextIsolation:true,nodeIntegration:false}});
    await foreign.loadURL('data:text/html,<title>Isolated foreign renderer fixture</title>');
    const rejected=await foreign.webContents.executeJavaScript('window.origoPhone.read().then(()=>false,()=>true)');
    rows.push({case:'foreign-window-ipc-rejected',passed:rejected});
    fs.writeFileSync(path.join(output,'phone-native-renderer.json'),JSON.stringify(rows,null,2));
    console.log(JSON.stringify(rows));
    app.exit(rows.every(row=>row.passed)?0:1);
  }catch{
    console.error('Native pairing renderer verification failed.');
    app.exit(1);
  }
});
