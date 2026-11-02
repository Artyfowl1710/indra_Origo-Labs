// Local inference is optional; an unavailable engine must not hide the workspace.
async function startOptionalLocalRouting({enabled, issue, start, stop}) {
  if (!enabled) return {ready:false, issue:issue || null};
  try {
    await start();
    return {ready:true, issue:null};
  } catch {
    await stop();
    return {ready:false, issue:'service-failed'};
  }
}

function localStartupNotice(issue) {
  const reason = {
    'runtime-missing':'The local inference runtime is not installed.',
    'runtime-unverified':'The local inference runtime could not be verified, so it was not started.',
    'models-missing':'One or more required local model files are missing.',
    'service-failed':'The local inference service could not start. Details are in logs/origo-product-backend.log.',
  }[issue];
  if (!reason) return null;
  return {
    type:'warning', title:'Indra · Local inference',
    message:'Indra is open. Local inference is unavailable.',
    detail:reason+'\n\nYour saved model selection is unchanged. You can use a configured API provider or connect your own model server. To use the configured local models, restore the local setup and restart Indra.',
    buttons:['Choose model','Continue'], defaultId:1, cancelId:1, noLink:true,
  };
}

async function waitForService(url,{child,headers,timeoutMs=45000,allowAuthGate=false}={}){
  const deadline=performance.now()+timeoutMs;
  while(performance.now()<deadline){
    if(child && (child.exitCode!==null || child.signalCode)){
      throw Error('The service exited during startup.');
    }
    try{
      const response=await fetch(url,{headers,signal:AbortSignal.timeout(Math.max(1,Math.min(500,Math.ceil(deadline-performance.now()))))});
      if(response.ok || allowAuthGate && [401,403].includes(response.status))return;
    }catch{}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw Error('Service startup timed out. See logs/origo-product-backend.log.');
}

module.exports={startOptionalLocalRouting,localStartupNotice,waitForService};
