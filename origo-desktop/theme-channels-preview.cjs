// Tests only an isolated fixture backend and owns its hidden Electron window.
const {app,BrowserWindow}=require('electron');
app.disableHardwareAcceleration();
const fs=require('node:fs'),path=require('node:path');
const origin=new URL(process.argv[2]),output=path.resolve(process.argv[3]);
const allowed=path.resolve(__dirname,'../data/test-results')+path.sep;
if(origin.hostname!=='127.0.0.1'||origin.protocol!=='http:'||!output.startsWith(allowed))throw Error('Isolated loopback fixture required');
fs.writeFileSync(path.join(output,'boot.json'),JSON.stringify({argv:process.argv,main:require.main?.filename}));
app.setPath('userData',path.join(output,'desktop'));
const checks=[];let win;
const evaluate=code=>win.webContents.executeJavaScript(code);
function record(name,passed){checks.push({name,passed:!!passed});if(!passed)throw Error(name);}
async function wait(code){
  for(let i=0;i<200;i++){
    await evaluate("(()=>{const b=Array.from(document.querySelectorAll('button')).find(e=>e.textContent.trim()==='Skip for now');if(b)b.click();})()");
    if(await evaluate(code))return;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw Error('UI condition timed out: '+code.slice(0,100));
}
const contrastCode=`(selector)=>{
 const el=document.querySelector(selector);if(!el)return 0;
 const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d');
 ctx.fillStyle='#fff';ctx.fillRect(0,0,1,1);
 const parents=[];for(let node=el;node;node=node.parentElement)parents.unshift(node);
 for(const node of parents){ctx.fillStyle=getComputedStyle(node).backgroundColor;ctx.fillRect(0,0,1,1);}
 const lum=rgb=>{const c=rgb.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
 const background=lum(Array.from(ctx.getImageData(0,0,1,1).data));
 ctx.fillStyle=getComputedStyle(el).color;ctx.fillRect(0,0,1,1);
 const ink=lum(Array.from(ctx.getImageData(0,0,1,1).data));
 return (Math.max(background,ink)+.05)/(Math.min(background,ink)+.05);
}`;
async function contrast(selector){return evaluate('('+contrastCode+')('+JSON.stringify(selector)+')');}
async function route(url,condition){await win.loadURL(origin.origin+url);await wait(condition);}
async function theme(name){
  await evaluate("Array.from(document.querySelectorAll('button[aria-haspopup=listbox]')).find(e=>e.getBoundingClientRect().width>0).click()");
  await wait("!!document.querySelector('[data-theme-option="+name+"]')");
  await evaluate("document.querySelector('[data-theme-option="+name+"]').click()");
  await wait("document.documentElement.dataset.themeName==='"+name+"'");
}
async function capture(name){fs.writeFileSync(path.join(output,name+'.png'),(await win.webContents.capturePage()).toPNG());}
app.whenReady().then(async()=>{
 try{
  win=new BrowserWindow({show:false,width:1440,height:1000,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
  for(const name of ['default','default-large','ember']){
    await route('/guide',"!!document.querySelector('.indra-guide')");
    await theme(name);
    record(name+' guide text contrast >=4.5',await contrast('.indra-guide p')>=4.5);
    record(name+' offline phone guide present',await evaluate("!!document.querySelector('#phone-control') && document.body.innerText.includes('Create your own Indra Telegram bot')"));
    await capture(name+'-guide');
    await route('/skills',"!!document.querySelector('.indra-skill-filter.is-active')");
    record(name+' active skill filter contrast >=4.5',await contrast('.indra-skill-filter.is-active')>=4.5);
    await capture(name+'-skills');
    await route('/profiles',"!!document.querySelector('[data-profile-actions] button')");
    await evaluate("document.querySelector('[data-profile-actions] button').click()");
    await wait("!!document.querySelector('[role=menu]')");
    record(name+' profile menu contrast >=4.5',await contrast('[role=menu] button')>=4.5);
    await capture(name+'-profiles');
    await route('/channels',"!!document.querySelector('#whatsapp-phone-region')");
    record(name+' Indian numbering option',await evaluate("document.querySelector('#whatsapp-phone-region').value==='IN'"));
    record(name+' hosted Telegram setup hidden by default',await evaluate("!document.body.innerText.includes('Create with QR')"));
    record(name+' integration descriptions use Indra',await evaluate("!/(Run|Connect|Use|Talk to) Hermes/.test(document.body.innerText)"));
    await evaluate("Array.from(document.querySelectorAll('button')).find(e=>e.textContent.trim()==='Connect your bot').click()");
    await wait("!!document.querySelector('input[type=password]')");
    record(name+' manual setup label contrast >=4.5',await contrast('label')>=4.5);
    record(name+' setup input contrast >=4.5',await contrast('input[type=password]')>=4.5);
    await capture(name+'-telegram');
    await route('/env',"document.body.innerText.includes('API') || document.body.innerText.includes('Keys')");
    record(name+' no obsolete key storage path',await evaluate("!document.body.innerText.includes('~/.hermes/.env')"));
    await capture(name+'-keys');
    await route('/chat',"!!document.querySelector('.indra-sidebar-toggle')");
    record(name+' new-chat collapse arrow contrast >=3',await contrast('.indra-sidebar-toggle')>=3);
    await capture(name+'-chat');
    await route('/auto-routing',"!!document.querySelector('#indra-parallel-limit:not(:disabled)')");
    record(name+' parallel setting readable',await contrast('label[for=indra-parallel-limit]')>=4.5);
    await capture(name+'-parallel');
    await route('/plugins',"document.body.innerText.includes('Extensions')");
    record(name+' extensions description is product-branded',await evaluate("!document.body.innerText.includes('hermes plugins') && !document.body.innerText.includes('~/.hermes/plugins')"));
    await capture(name+'-extensions');
  }
 }catch(error){
   checks.push({name:error.message,passed:false});
   if(win){await capture('failure');fs.writeFileSync(path.join(output,'failure.txt'),await evaluate('document.body.innerText'));}
 }finally{
   fs.writeFileSync(path.join(output,'acceptance.json'),JSON.stringify(checks,null,2));
   app.quit();process.exitCode=checks.every(row=>row.passed)?0:1;
 }
});
