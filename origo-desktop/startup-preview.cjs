// Own temporary Electron profile, real product entry and backend; no model calls.
const {app,dialog}=require('electron');
const fs=require('node:fs'),path=require('node:path');
const home=path.resolve(process.env.ORIGO_HOME || '');
const outputRoot=path.resolve(__dirname,'../data/test-results');
if(!home.startsWith(outputRoot+path.sep)||!path.basename(home).startsWith('startup-preview-')){
  throw Error('A dedicated startup-preview profile is required.');
}
const output=path.join(home,'acceptance.json');
const original=fs.readFileSync(path.join(home,'config.yaml'));
const notices=[],checks=[];
let timings;
dialog.showMessageBox=async(_window,notice)=>{notices.push(notice);return {response:1};};
dialog.showErrorBox=(_title,message)=>{throw Error(message);};
const {start}=require('./main.cjs');
let origin;
function check(name,value){checks.push({name,passed:Boolean(value)});if(!value)throw Error(name);}
function write(error){fs.writeFileSync(output,JSON.stringify({checks,origin,timings,error:error||null},null,2));}
const deadline=setTimeout(()=>{write('Native startup deadline exceeded');process.exitCode=1;app.quit();},100000);
app.whenReady().then(async()=>{
  try{
    const result=await start({show:false});
    timings=result.timings;
    origin=result.origin;
    check('real backend started on loopback',new URL(origin).hostname==='127.0.0.1');
    check('local failure did not prevent workspace startup',result.localStartup.ready===false);
    check('expected local failure was reported',result.localStartup.issue===process.env.ORIGO_EXPECT_STARTUP_ISSUE);
    const window=result.window;
    for(let i=0;i<150;i++){
      if(await window.webContents.executeJavaScript('document.body.innerText.length>150'))break;
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    const content=await window.webContents.executeJavaScript('document.body.innerText');
    check('native workspace rendered',content.length>150 && !content.includes('This site can’t be reached'));
    check('window stayed hidden during fixture',!window.isVisible());
    check('saved model configuration stayed byte-identical',fs.readFileSync(path.join(home,'config.yaml')).equals(original));
    check('one actionable local setup notice',notices.length===1 && notices[0].buttons.includes('Choose model'));
    check('native title uses product branding',window.getTitle()==='Indra · Origo Labs');
    await window.loadURL(origin+'/models');
    for(let i=0;i<150;i++){
      await window.webContents.executeJavaScript(`(()=>{const skip=Array.from(document.querySelectorAll('button')).find(button=>button.textContent.trim()==='Skip for now');if(skip)skip.click();})()`);
      if(await window.webContents.executeJavaScript("document.body.innerText.includes('Models, made simple.')"))break;
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    check('model settings remain accessible',await window.webContents.executeJavaScript(
      "location.pathname==='/models' && document.body.innerText.includes('Models, made simple.')"));
    const image=await window.webContents.capturePage();
    fs.writeFileSync(path.join(home,'models.png'),image.toPNG());
    write();
    clearTimeout(deadline);
    app.quit();
  }catch(error){write(error.message);clearTimeout(deadline);app.quit();process.exitCode=1;}
});
