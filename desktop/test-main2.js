const { app, BrowserWindow } = require('electron');
console.log('Electron API available:', { hasApp: !!app, hasBW: !!BrowserWindow });
app.whenReady().then(function() {
  console.log('App ready');
  app.quit();
});
