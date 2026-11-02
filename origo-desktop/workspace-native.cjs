function trustedFrame(event,window,origin){
 if(!window||window.isDestroyed()||event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame)return false;
 try{return new URL(event.senderFrame.url).origin===origin;}catch{return false;}
}
function installWorkspaceNative(window,origin,{ipcMain,dialog}){
 let choosing=false;
 ipcMain.handle('indra:pick-folder',async event=>{
  if(!trustedFrame(event,window,origin))throw Error('Folder selection is available only in Indra.');
  if(choosing)return null;choosing=true;
  try{const result=await dialog.showOpenDialog(window,{title:'Choose a project folder for Indra',properties:['openDirectory']});return result.canceled?null:result.filePaths[0]??null;}finally{choosing=false;}
 });
 const session=window.webContents.session;let microphoneAllowed=false;
 session.setPermissionRequestHandler(async(wc,permission,callback,details)=>{
  let same=false;try{same=wc===window.webContents&&new URL(details.requestingUrl||wc.getURL()).origin===origin;}catch{}
  if(!same||permission!=='media'||!details.mediaTypes?.includes('audio')||details.mediaTypes.includes('video'))return callback(false);
  if(!microphoneAllowed){const answer=await dialog.showMessageBox(window,{type:'question',title:'Allow microphone?',message:'Allow Indra to capture your microphone while voice is active?',detail:'Google Live sends audio to Google. Local or harness voice uses the selected speech provider. Stop or close voice to release the microphone.',buttons:['Allow microphone','Cancel'],defaultId:1,cancelId:1});microphoneAllowed=answer.response===0;}
  callback(microphoneAllowed);
 });
 window.on('closed',()=>ipcMain.removeHandler('indra:pick-folder'));
}
module.exports={trustedFrame,installWorkspaceNative};
