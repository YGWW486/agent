const { app, BrowserWindow } = require('electron')
console.log('app:', !!app, 'app.isPackaged:', app && app.isPackaged)
console.log('BrowserWindow:', !!BrowserWindow)
app.whenReady().then(() => {
  const win = new BrowserWindow({ width: 800, height: 600 })
  win.loadURL('data:text/html,<h1>Hello</h1>')
  console.log('Window created')
})
