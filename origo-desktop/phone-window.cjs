const {spawn} = require('node:child_process');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

function phoneBridge(root, python, home, action, payload = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(python, ['-m','origo_runtime.phone_setup','--home',home,action], {
      cwd:root,windowsHide:true,env:{...process.env,PYTHONUTF8:'1'},stdio:['pipe','pipe','ignore']
    });
    let output = '', timedOut = false;
    const timer = setTimeout(()=>{timedOut=true;child.kill();},20000);
    child.stdout.on('data',chunk=>{output+=chunk;if(output.length>16384)child.kill();});
    child.on('error',()=>{clearTimeout(timer);reject(Error('Phone setup could not start.'));});
    child.on('exit',code=>{
      clearTimeout(timer);
      try {
        const result=JSON.parse(output);
        if(code!==0 || !result.ok || timedOut)throw Error('Phone setup failed. Check the form and profile permissions.');
        resolve(result.settings);
      } catch {reject(Error('Phone setup failed. Check the form and profile permissions.'));}
    });
    child.stdin.on('error',()=>{});
    child.stdin.end(action==='save'?JSON.stringify(payload):'');
  });
}

function authorizeSetup(event, setupWindow, setupUrl) {
  if(!setupWindow || setupWindow.isDestroyed() || event.sender!==setupWindow.webContents ||
     event.senderFrame!==setupWindow.webContents.mainFrame || event.senderFrame.url!==setupUrl)
    throw Error('Phone setup is available only from the native setup window.');
}

function installPhoneWindow({app,root,python,home,mainWindow,getShareStatus}) {
  const {BrowserWindow,ipcMain,Menu}=require('electron');
  let setupWindow;
  let changing=false;
  const setupUrl=pathToFileURL(path.join(__dirname,'phone-setup.html')).href;
  function authorize(event) {
    authorizeSetup(event,setupWindow,setupUrl);
  }
  ipcMain.handle('origo-phone:read',async event=>{
    authorize(event);
    return {settings:await phoneBridge(root,python,home,'read'),share:getShareStatus()};
  });
  ipcMain.handle('origo-phone:status',event=>{authorize(event);return getShareStatus();});
  function restart() {setTimeout(()=>{app.relaunch();app.quit();},250);}
  ipcMain.handle('origo-phone:save',async (event,payload)=>{
    authorize(event);
    if(changing)throw Error('Phone setup is already being updated.');
    if(!payload || typeof payload!=='object' || JSON.stringify(payload).length>8192)throw Error('Phone setup is invalid.');
    changing=true;
    try{await phoneBridge(root,python,home,'save',payload);}finally{changing=false;}
    restart();
    return {ok:true};
  });
  ipcMain.handle('origo-phone:disable',async event=>{
    authorize(event);
    if(changing)throw Error('Phone setup is already being updated.');
    changing=true;
    try{await phoneBridge(root,python,home,'disable');}finally{changing=false;}
    restart();
    return {ok:true};
  });
  function open() {
    if(setupWindow && !setupWindow.isDestroyed()){setupWindow.focus();return;}
    setupWindow=new BrowserWindow({title:'Indra Origo · Phone pairing',width:600,height:820,minWidth:480,minHeight:650,
      parent:mainWindow,autoHideMenuBar:true,webPreferences:{preload:path.join(__dirname,'phone-preload.cjs'),
        sandbox:true,contextIsolation:true,nodeIntegration:false}});
    setupWindow.webContents.setWindowOpenHandler(()=>({action:'deny'}));
    setupWindow.webContents.on('will-navigate',event=>event.preventDefault());
    setupWindow.on('closed',()=>{setupWindow=null;});
    setupWindow.loadURL(setupUrl);
  }
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {label:'Origo',submenu:[{label:'Phone pairing…',click:open},{type:'separator'},{role:'quit'}]},
    {role:'editMenu'},{role:'viewMenu'},{role:'windowMenu'}
  ]));
  return {open};
}

module.exports={phoneBridge,installPhoneWindow,authorizeSetup};
