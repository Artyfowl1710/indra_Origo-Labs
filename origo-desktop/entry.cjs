// Electron's loader owns require.main. Always invoke the explicit package entry.
if(process.env.ORIGO_RELEASE_SMOKE==='1')require('./release-smoke.cjs');
else require('./main.cjs').launch();
