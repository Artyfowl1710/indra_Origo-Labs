const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const crypto = require('node:crypto');
const {phoneBridge,installPhoneWindow}=require('./phone-window.cjs');
const {startOptionalLocalRouting,localStartupNotice,waitForService}=require('./local-startup.cjs');
const root = path.resolve(__dirname, '..');
const bundledNode=path.join(root,'runtime','node');
if(fs.existsSync(path.join(bundledNode,'node.exe')))process.env.PATH=bundledNode+path.delimiter+(process.env.PATH || '');
const bundledPython=path.join(root,'runtime','python');
if(fs.existsSync(path.join(bundledPython,'python.exe')))process.env.PATH=bundledPython+path.delimiter+(process.env.PATH || '');
const source = path.join(root, 'indra', 'SIH-26', 'hermes-agent');
const locations=require('./product-paths.cjs').productPaths({root,packaged:app.isPackaged,localAppData:process.env.LOCALAPPDATA || app.getPath('userData')});
const home = locations.home;
fs.mkdirSync(home, { recursive: true });
app.setPath('userData', locations.desktop);
let backend, router, phoneShare, window, quitting = false;
let phoneShareState={state:'off',message:'Phone sharing is off. Configure your private address and workstation sign-in to enable it.'};
function freePort(preferred = 0) {
  return new Promise((resolve, reject) => {
    const server = net.createServer(); server.on('error', reject);
    server.listen(preferred, '127.0.0.1', () => { const port = server.address().port; server.close(() => resolve(port)); });
  });
}
async function start({show=true}={}) {
  const startupBegan=performance.now();
  const python = locations.python;
  if (!fs.existsSync(python)) throw Error('Origo Python runtime is missing.');
  if (!fs.existsSync(path.join(source, 'hermes_cli', 'web_dist', 'index.html'))) throw Error('Build the Indra web workspace before launching.');
  window = new BrowserWindow({show,title:'Indra · Origo Labs',width:1440,height:950,minWidth:900,minHeight:650,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,preload:path.join(__dirname,'workspace-preload.cjs')}});
  window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  window.on('page-title-updated',event=>{event.preventDefault();window.setTitle('Indra · Origo Labs');});
  await window.loadFile(path.join(__dirname,'startup.html'));
  const initialWindowMs=Math.round(performance.now()-startupBegan);
  const phoneSettings=await phoneBridge(root,python,home,'read');
  const port = await freePort(phoneSettings?.enabled ? phoneSettings.port : 0); const origin = `http://127.0.0.1:${port}`;
  const logDir = locations.logs;fs.mkdirSync(logDir,{recursive:true});
  const log = fs.openSync(path.join(logDir, 'origo-product-backend.log'),'a');
  const childEnv = {...process.env, HERMES_HOME:home, PYTHONPATH:path.join(root,'indra','SIH-26'), PYTHONUTF8:'1', ORIGO_SOCIAL_TOOL_POLICY:'1'};
  if(phoneSettings){
    // Shared dashboards use the normal password/ticket gate. Never inherit
    // the generic Electron backend's loopback-auth exemption or another profile's credentials.
    for(const key of Object.keys(childEnv)){
      if(key==='HERMES_DESKTOP' || key==='HERMES_DASHBOARD_SESSION_TOKEN' || key.startsWith('HERMES_DASHBOARD_BASIC_AUTH_'))delete childEnv[key];
    }
    childEnv.HERMES_DASHBOARD_PUBLIC_URL=phoneSettings.endpoint;
  }
  let routerOrigin;
  const localStartup = await startOptionalLocalRouting({
    enabled:process.env.ORIGO_AUTO_ROUTING === '1',
    issue:process.env.ORIGO_LOCAL_STARTUP_ISSUE,
    start:async()=>{
    const routerPort = await freePort();
    routerOrigin = `http://127.0.0.1:${routerPort}`;
    const routerToken = crypto.randomBytes(32).toString('hex');
    childEnv.ORIGO_LOCAL_INFERENCE_KEY = routerToken;
    router = spawn(python, ['-m','origo_runtime','--runtime',process.env.ORIGO_RUNTIME_DIR,
      '--models',process.env.ORIGO_MODEL_DIR,'--port',String(routerPort),
      '--device',process.env.ORIGO_DEVICE || 'auto','--parent-pid',String(process.pid)], {
      cwd:root,windowsHide:true,env:{...process.env,ORIGO_ROUTER_TOKEN:routerToken,PYTHONUTF8:'1'},stdio:['ignore',log,log]
    });
    router.on('error',()=>{});
    await waitForService(routerOrigin+'/health',{child:router,headers:{Authorization:`Bearer ${routerToken}`},timeoutMs:15000});
    },
    stop:async()=>{
      if(router && router.exitCode===null)router.kill();
      delete childEnv.ORIGO_LOCAL_INFERENCE_KEY;
    },
  });
  if(localStartup.ready){
    await new Promise((resolve,reject)=>{
      const configure=spawn(python,[path.join(root,'scripts','configure_cpp_profile.py')],{
        cwd:root,windowsHide:true,env:{...childEnv,ORIGO_CPP_PROFILE:'indra-auto-home',ORIGO_CPP_ALIAS:'origo-auto',ORIGO_CPP_ORIGIN:routerOrigin,ORIGO_CPP_CONTEXT:'16384'},stdio:['ignore',log,log]
      });
      configure.on('error',reject);configure.on('exit',code=>code===0?resolve():reject(Error('Automatic routing profile setup failed.')));
    });
  }
  backend = spawn(python, ['-m','hermes_cli.main','dashboard','--no-open','--skip-build','--host','127.0.0.1','--port',String(port)], {
    cwd: source, windowsHide: true,
    env: childEnv,
    stdio:['ignore',log,log]
  });
  fs.closeSync(log);
  backend.on('error', error => { if (!quitting) dialog.showErrorBox('Indra Origo backend',error.message); });
  backend.on('exit', code => { if (!quitting && window) dialog.showErrorBox('Indra Origo backend',`Backend stopped (${code}). See logs/origo-product-backend.log.`); });
  await waitForService(origin+'/overview',{child:backend,allowAuthGate:true});
  require('./workspace-native.cjs').installWorkspaceNative(window,origin,{ipcMain:require('electron').ipcMain,dialog});
  window.webContents.on('will-navigate',(event,url)=>{try{if(new URL(url).origin!==origin)event.preventDefault();}catch{event.preventDefault();}});
  installPhoneWindow({app,root,python,home,mainWindow:window,getShareStatus:()=>phoneShareState});
  await window.loadURL(origin+'/overview');
  const localNotice=localStartupNotice(localStartup.issue);
  if(localNotice){
    dialog.showMessageBox(window,localNotice).then(result=>{
      if(result.response===0 && !window.isDestroyed())window.loadURL(origin+'/models');
    }).catch(()=>{});
  }
  if(phoneSettings?.enabled){
    phoneShareState={state:'starting',message:'Checking authenticated backend and private Tailscale sharing…'};
    const shareLog=fs.openSync(path.join(logDir,'phone-share.log'),'a');
    phoneShare=spawn(python,['-m','origo_runtime.phone_share','--home',home,'--port',String(port),
      '--parent-pid',String(process.pid),'--backend-pid',String(backend.pid)],{
      cwd:root,windowsHide:true,env:{...process.env,PYTHONUTF8:'1'},stdio:['ignore','pipe',shareLog]
    });
    fs.closeSync(shareLog);
    let pending='';
    phoneShare.stdout.on('data',chunk=>{
      pending+=chunk;
      if(pending.length>65536){phoneShare.kill();pending='';return;}
      let boundary;
      while((boundary=pending.indexOf('\n'))!==-1){
        const line=pending.slice(0,boundary);pending=pending.slice(boundary+1);
        try{const state=JSON.parse(line);if(typeof state.state==='string' && typeof state.message==='string')phoneShareState=state;}catch{}
      }
    });
    phoneShare.on('error',()=>{phoneShareState={state:'setup_required',message:'The private sharing service could not start.'};});
    phoneShare.on('exit',()=>{if(['starting','sharing'].includes(phoneShareState.state))phoneShareState={state:'stopped',message:'Phone sharing stopped. Check Tailscale setup and restart Origo to retry.'};});
  }
  const timings={initialWindowMs,workspaceReadyMs:Math.round(performance.now()-startupBegan)};
  fs.appendFileSync(path.join(logDir,'origo-product-backend.log'),JSON.stringify({event:'desktop.startup',...timings})+'\n');
  return {window,localStartup,origin,timings};
}
function launch(){
  if(app.requestSingleInstanceLock()){
    app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.focus();}});
    app.whenReady().then(()=>start()).catch(error=>{dialog.showErrorBox('Indra Origo startup',error.message);app.quit();});
  }else app.quit();
}
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{
  quitting=true;
  for(const owned of [phoneShare,backend,router]){
    if(owned && owned.exitCode===null)owned.kill();
  }
});
module.exports={start,launch};
