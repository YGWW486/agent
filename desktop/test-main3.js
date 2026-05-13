// Check what electron provides
var e = require('electron');
console.log('electron keys:', Object.keys(e));
console.log('electron type:', typeof e);
console.log('electron prototype:', Object.getPrototypeOf(e));

// Try accessing via process
console.log('process.type:', process.type);
console.log('process.versions:', JSON.stringify(process.versions));

// Check if electron is the npm stub
console.log('electron path:', require.resolve('electron'));
