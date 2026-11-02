const path = require('node:path');
const fs = require('node:fs');

function productPaths({root, env=process.env, packaged=false, localAppData}) {
  const bundledPython=path.join(root,'runtime','python','python.exe');
  const state=packaged?path.join(localAppData,'OrigoLabs','Indra'):path.join(root,'data');
  return {
    python:env.ORIGO_PYTHON?path.resolve(env.ORIGO_PYTHON):(fs.existsSync(bundledPython)?bundledPython:path.join(root,'.indra-python','Scripts','python.exe')),
    home:env.ORIGO_HOME?path.resolve(env.ORIGO_HOME):path.join(state,packaged?'profile':'indra-product-home'),
    desktop:env.ORIGO_DESKTOP_USER_DATA?path.resolve(env.ORIGO_DESKTOP_USER_DATA):path.join(state,packaged?'desktop':'origo-product-desktop'),
    logs:env.ORIGO_LOG_DIR?path.resolve(env.ORIGO_LOG_DIR):(packaged?path.join(state,'logs'):path.join(root,'logs')),
  };
}
module.exports={productPaths};
