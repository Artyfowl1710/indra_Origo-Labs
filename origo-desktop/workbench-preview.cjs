// Developer acceptance probe against an already-running, loopback-only desktop.
// Theme changes use the real UI and are restored before exiting.
const {app,BrowserWindow}=require('electron');
const fs=require('node:fs');
const path=require('node:path');
const origin=new URL(process.argv[2]);
if(origin.protocol!=='http:' || origin.hostname!=='127.0.0.1' || !origin.port || origin.pathname!=='/' || origin.username || origin.password || origin.search || origin.hash)throw Error('Expected loopback desktop origin');
const output=path.resolve(__dirname,'../data/test-results');
app.setPath('userData',path.join(output,'workbench-preview-profile'));
let window;
const rows=[];
const evaluate=code=>window.webContents.executeJavaScript(code);
const themeButton=`Array.from(document.querySelectorAll('button[aria-haspopup="listbox"]')).find(e=>e.getBoundingClientRect().width>0)`;
async function waitFor(code){
  for(let n=0;n<100;n++){
    if(await evaluate(code))return;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw Error('Renderer acceptance condition timed out');
}
function record(test,passed){rows.push({test,passed});if(!passed)throw Error(test);}
async function theme(name){
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))`);
  await evaluate(`${themeButton}.click()`);
  await waitFor(`!!document.querySelector('[role="option"]')`);
  await evaluate(`document.querySelector('[data-theme-option='+${JSON.stringify(name)}+']').click()`);
  await waitFor(`document.documentElement.dataset.themeName===${JSON.stringify(name)}`);
  await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  // Hidden Chromium windows can present a compositor frame after DOM rAF.
  await new Promise(resolve=>setTimeout(resolve,250));
}
app.whenReady().then(async()=>{
  let original;
  try{
    fs.mkdirSync(output,{recursive:true});
    window=new BrowserWindow({show:false,width:1440,height:1000,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
    await window.loadURL(origin.origin+'/chat');
    await waitFor(`!!document.querySelector('.indra-welcome') && !!document.querySelector('button[aria-haspopup="listbox"]')`);
    await waitFor(`!!document.querySelector('textarea:not(:disabled)')`);
    original=await evaluate(`document.documentElement.dataset.themeName`);
    await theme('default');
    await waitFor(`!!document.querySelector('.origo-companion canvas:not(.origo-companion-pending)')`);
    record('real-webgl-companion-mounted',true);
    fs.writeFileSync(path.join(output,'workbench-light.png'),(await window.webContents.capturePage()).toPNG());
    await theme('midnight');
    record('rendered-dark-heading-contrast',await evaluate(`(()=>{
      const color=getComputedStyle(document.querySelector('.indra-welcome h2')).color;
      const rgb=color.match(/[\\d.]+/g)?.slice(0,3).map(Number);
      if(!rgb || !color.startsWith('rgb'))return false;
      const lum=rgb.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
      return .2126*lum[0]+.7152*lum[1]+.0722*lum[2]>.6;
    })()`));
    record('dark-composer-control-ink',await evaluate(`(()=>{const rgb=getComputedStyle(document.querySelector('.indra-chat-tool')).color.match(/[\\d.]+/g)?.slice(0,3).map(Number);return !!rgb && Math.min(...rgb)>180})()`));
    fs.writeFileSync(path.join(output,'workbench-layout.json'),JSON.stringify(await evaluate(`Object.fromEntries(['.origo-companion','.indra-welcome','.stitch-topbar','[aria-live="polite"]'].map(s=>{const e=document.querySelector(s);const r=e.getBoundingClientRect();return [s,{top:r.top,bottom:r.bottom,height:r.height,align:getComputedStyle(e).alignItems,scroll:e.scrollTop}]}))`),null,2));
    record('welcome-companion-clear-of-topbar',await evaluate(`(()=>{const mascot=document.querySelector('.origo-companion').getBoundingClientRect();const bar=document.querySelector('.stitch-topbar').getBoundingClientRect();return mascot.top>=bar.bottom && mascot.height>=100})()`));
    fs.writeFileSync(path.join(output,'workbench-dark.png'),(await window.webContents.capturePage()).toPNG());
    record('theme-picker-light-and-dark',true);
    window.setSize(420,900);
    await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
    record('mobile-composer-in-viewport',await evaluate(`(()=>{const r=document.querySelector('textarea').getBoundingClientRect();return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight && r.width>100})()`));
    record('mobile-theme-picker-visible',await evaluate(`!!(${themeButton})`));
    fs.writeFileSync(path.join(output,'workbench-mobile.png'),(await window.webContents.capturePage()).toPNG());
    await evaluate(`document.querySelector('.origo-companion canvas').dispatchEvent(new Event('webglcontextlost',{cancelable:true}))`);
    await waitFor(`!!document.querySelector('.origo-companion-fallback')`);
    record('webgl-loss-offline-fallback',true);
  }catch(error){
    rows.push({test:error.message,passed:false});
    if(window && !window.isDestroyed())fs.writeFileSync(path.join(output,'workbench-failure.png'),(await window.webContents.capturePage()).toPNG());
  }
  finally{
    if(original && window && !window.isDestroyed()){
      try{
        await theme(original);
        await waitFor(`fetch('/api/dashboard/themes',{headers:{'X-Hermes-Session-Token':window.__HERMES_SESSION_TOKEN__}}).then(r=>r.json()).then(r=>r.active===${JSON.stringify(original)})`);
        rows.push({test:'restore-original-theme',passed:true});
      }catch{rows.push({test:'restore-original-theme',passed:false});}
    }
    fs.writeFileSync(path.join(output,'workbench-renderer.json'),JSON.stringify(rows,null,2));
    console.log(JSON.stringify(rows));
    app.exit(rows.length>=8 && rows.every(row=>row.passed)?0:1);
  }
});
