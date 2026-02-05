import express from 'express';
import WinReg from 'winreg';
import os, { type } from 'os';
import https from 'https';
import { exec,spawn } from "child_process";
import fs from 'fs/promises';
import path from 'path';
import EventEmitter from 'events';

const app = express();

app.set('view engine', 'ejs');
app.set('views', './views');
app.use(express.static('public'));

async function detectLocalIp(type = "lan") {
    const nets = os.networkInterfaces();

    if (type === "lan") {
        for (const name in nets) {
            for (const net of nets[name]) {
                if (net.family === "IPv4" && !net.internal && !net.address.startsWith("100.")) {
                    return (net.address + '/lan');
                }
            }
        }
    }

    if (type === "tailscale") {
        for (const name in nets) {
            for (const net of nets[name]) {
                if (net.family === "IPv4" && !net.internal && net.address.startsWith("100.")) {
                    return (net.address + '/tailscale');
                }
            }
        }
    }

    
    if (type === "net") {
        return new Promise((resolve, reject) => {
            https.get("https://api.ipify.org", (res) => {
                let data = "";
                res.on("data", chunk => data += chunk);
                res.on("end", () => resolve(data + "/net"));
            }).on("error", err => reject({ ip: "Connection error", type }));
        });
    }

    return "Connection error";
}

const portIndex = process.argv.indexOf("--port");
const port = portIndex !== -1 ? process.argv[portIndex + 1] : 3000;

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});

const hostname = os.hostname();
const platform = os.platform();
let mfsVersion = "Unknown";


if (platform === "win32") {
    mfsVersion = "not implemented"  
} else {
    mfsVersion = `Unsupported OS (${platform})`;
}

let iptype = 'lan';

let currentStatus = {
    ip: await detectLocalIp(iptype),
    timestamp: Date.now()
};

setInterval(async () => {
    currentStatus.ip = await detectLocalIp(iptype);
    currentStatus.timestamp = Date.now();
}, 5000);


app.get('/', (req,res) => {
    res.render('index', {
        hostname,
        localip: currentStatus.ip,
        mfsVersion : mfsVersion,
    });
});



app.get("/status", (req, res) => {
    res.json(currentStatus);
});
app.use(express.urlencoded({ extended: true }));
app.use(express.json());


function encodeIP(ip) {
    return btoa(encodeURIComponent(ip).replace(/%([0-9A-F]{2})/g, (match, p1) => String.fromCharCode('0x' + p1)));
}
function decodeIP(encoded) {
    return decodeURIComponent(atob(encoded).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));
}


app.post('/connect', (req, res) => {
  const { host: ipb, code: code, client : eclient} = req.body;
  let client = decodeIP(eclient);

  if (!ipb || !code) {
    return res.status(400).json({
      success: false,
      error: 'Missing required fields: ip and code'
    });
  }
  
  let connectionIpType = ipb.split('/')[1];
  let ip = ipb.split('/')[0];
  console.log('Attempting to connect to IP:', ip, 'over', connectionIpType, 'with code:', code, '\n from ',client);
  

  res.json({
    success: true,
    hasModule: true,
    message: `Connection attempt to ${ip} over ${connectionIpType} with code ${code} initiated.`
  });
});













// Update the check-community-folder route
app.post('/check-community-folder', async (req, res) => {
  const { path: folderPath } = req.body;
  console.log(path)
  
  try {
    if (!folderPath || folderPath.trim() === '') {
      return res.json({
        success: false,
        hasModule: false,
        error: 'Please enter a folder path'
      });
    }
    
    // Normalize path
    let normalizedPath = folderPath.trim();
    
    // Convert to absolute path if it's relative
    if (!path.isAbsolute(normalizedPath)) {
      normalizedPath = path.resolve(normalizedPath);
    }
    
    // Clean up path - replace forward slashes with backslashes for Windows
    if (process.platform === 'win32') {
      normalizedPath = normalizedPath.replace(/\//g, '\\');
    }
    
    // Remove trailing slashes/backslashes
    normalizedPath = normalizedPath.replace(/[\/\\]+$/, '');
    
    console.log('🔍 Checking folder path:', normalizedPath);
    
    // Check if folder exists
    try {
      await fs.access(normalizedPath);
      const stats = await fs.stat(normalizedPath);
      
      if (!stats.isDirectory()) {
        return res.json({
          success: false,
          hasModule: false,
          error: 'Path exists but is not a folder'
        });
      }
      
      console.log('✅ Folder exists and is accessible');
      
    } catch (error) {
      console.log('❌ Folder access error:', error.message);
      
      // Try to suggest the correct path
      let suggestion = '';
      if (normalizedPath.includes('LocalCache')) {
        // Try to find the MSFS community folder automatically
        const possiblePaths = [
          path.join(process.env.APPDATA, 'Local', 'Packages', 'Microsoft.FlightSimulator_8wekyb3d8bbwe', 'LocalCache', 'Packages', 'Community'),
          path.join(process.env.LOCALAPPDATA, 'Packages', 'Microsoft.FlightSimulator_8wekyb3d8bbwe', 'LocalCache', 'Packages', 'Community'),
          path.join('C:', 'Users', process.env.USERNAME, 'AppData', 'Local', 'Packages', 'Microsoft.FlightSimulator_8wekyb3d8bbwe', 'LocalCache', 'Packages', 'Community')
        ];
         
        for (const possiblePath of possiblePaths) {
          try {
            await fs.access(possiblePath);
            suggestion = `Try this path instead: ${possiblePath}`;
            break;
          } catch (e) {
            // Continue checking other paths
          }
        }
      }
      
      return res.json({
        success: false,
        hasModule: false,
        error: 'Folder does not exist or cannot be accessed',
        suggestion: suggestion,
        attemptedPath: normalizedPath
      });
    }
    
    // Check for mobiflight-event-module folder
    const modulePath = path.join(normalizedPath, 'mobiflight-event-module');
    
    try {
      await fs.access(modulePath);
      const stats = await fs.stat(modulePath);
      
      if (stats.isDirectory()) {
        console.log('✅ mobiflight-event-module found');
        return res.json({
          success: true,
          hasModule: true,
          path: normalizedPath
        });
      } else {
        console.log('⚠️ mobiflight-event-module exists but is not a directory');
        return res.json({
          success: true,
          hasModule: false,
          path: normalizedPath
        });
      }
    } catch (error) {
      // mobiflight-event-module folder doesn't exist
      console.log('📁 mobiflight-event-module not found, ready to install');
      return res.json({
        success: true,
        hasModule: false,
        path: normalizedPath
      });
    }
  } catch (error) {
    console.error('❌ Error checking community folder:', error);
    res.status(500).json({
      success: false,
      error: `Server error: ${error.message}`
    });
  }
});

// Update the run-installer route
app.post('/run-installer', async (req, res) => {
  const { path: folderPath } = req.body;
  
  try {
    if (!folderPath || folderPath.trim() === '') {
      return res.json({
        success: false,
        error: 'No folder path provided'
      });
    }
    
    // Normalize path
    let normalizedPath = folderPath.trim();
    if (process.platform === 'win32') {
      normalizedPath = normalizedPath.replace(/\//g, '\\');
    }
    normalizedPath = normalizedPath.replace(/[\/\\]+$/, '');
    
    
    // First check if the folder exists
    try {
      await fs.access(normalizedPath);
    } catch (error) {
      return res.json({
        success: false,
        error: `Folder does not exist: ${normalizedPath}`
      });
    }
    
    // Check for Python script
    const pythonScript = path.resolve('./public/python/installer.py');
    
    try {
      await fs.access(pythonScript);
    } catch (error) {
      return res.json({
        success: false,
        error: `Python script not found at: ${pythonScript}`,
        suggestion: 'Make sure the installer.py file exists in the python folder'
      });
    }
    
    // Check for venv
    const venvActivate = path.resolve('.venv/Scripts/activate.bat');
    try {
      await fs.access(venvActivate);
    } catch (error) {
      return res.json({
        success: false,
        error: `Virtual environment not found at: ${venvActivate}`,
        suggestion: 'Make sure the .venv folder exists and is properly set up'
      });
    }
    
    // Create command - use .bat extension for Windows
    const command = `"${venvActivate}" && python "${pythonScript}" "${normalizedPath}"`;
    
    
    exec(command, { shell: 'cmd.exe', cwd: process.cwd() }, (error, stdout, stderr) => {
      
      if (error) {
        return res.json({
          success: false,
          error: `Python script failed: ${error.message}`,
          stderr: stderr || 'No stderr output',
          stdout: stdout || 'No stdout output'
        });
      }
      
      // Check if installation was successful by verifying the folder was created
      const modulePath = path.join(normalizedPath, 'mobiflight-event-module');
      
      fs.access(modulePath)
        .then(() => {
          res.json({
            success: true,
            output: stdout,
            message: 'Installation completed successfully',
            modulePath: modulePath
          });
        })
        .catch((checkError) => {
          res.json({
            success: false,
            output: stdout,
            stderr: stderr,
            error: 'Installation may have failed - module folder not found after installation',
            suggestion: 'Check if the Python script has proper permissions to create folders'
          });
        });
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});



app.post('/lvar/sim', (req, res) => {
  const { lvar, value } = req.body;
  console.log(`Received LVAR update: ${lvar} -> ${value}`);
  res.json({ success: true });
});

app.post('/lvar/client', async (req, res) => {
  const { lvar, value, client } = req.body;
  console.log(`Received LVAR update from client ${client}: ${lvar} -> ${value}`);
  // if (client == ip) return res.json({ success: true });
  const response = await fetch('http://localhost:8080/lvar/send', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ lvar, value })
  }).catch(error => {
    console.error('Error sending LVAR update:', error);
  });

  res.json({ success: true });
});


//////////////////////////////  CONSOLE ///////////////////:

const consoleEmitter = new EventEmitter();
const consoleHistory = [];
const MAX_CONSOLE_ENTRIES = 1000;

// Add route to send console messages
app.post('/console/log', (req, res) => {
  const { level, message, timestamp, source } = req.body;
  
  const logEntry = {
    level: level || 'info',
    message: message || '',
    timestamp: timestamp || new Date().toISOString(),
    source: source || 'server',
    id: Date.now() + Math.random().toString(36).substr(2, 9)
  };
  
  // Add to history (limit size)
  consoleHistory.push(logEntry);
  if (consoleHistory.length > MAX_CONSOLE_ENTRIES) {
    consoleHistory.shift();
  }
  
  // Emit to all connected clients
  consoleEmitter.emit('log', logEntry);
  
  res.json({ success: true });
});

// SSE endpoint for console updates
app.get('/console/stream', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*'
  });
  
  // Send existing history
  consoleHistory.forEach(entry => {
    res.write(`data: ${JSON.stringify(entry)}\n\n`);
  });
  
  // Send keep-alive every 30 seconds
  const keepAlive = setInterval(() => {
    res.write(': keepalive\n\n');
  }, 30000);
  
  // Listen for new logs
  const logHandler = (entry) => {
    res.write(`data: ${JSON.stringify(entry)}\n\n`);
  };
  
  consoleEmitter.on('log', logHandler);
  
  // Clean up on client disconnect
  req.on('close', () => {
    clearInterval(keepAlive);
    consoleEmitter.removeListener('log', logHandler);
  });
});

// Get all LVARs from sim
app.get('/lvars/sim', (req, res) => {
  // This would normally fetch from your simulation
  // For now, we'll return dummy data
  const mockLvars = [
    { name: 'AP_MASTER_SWITCH', value: 1, timestamp: new Date().toISOString() },
    { name: 'ENGINE_1_N1', value: 87.5, timestamp: new Date().toISOString() },
    { name: 'FLIGHT_CONTROLS', value: 0, timestamp: new Date().toISOString() },
    { name: 'ALTITUDE', value: 35000, timestamp: new Date().toISOString() },
    { name: 'AIRSPEED', value: 250, timestamp: new Date().toISOString() }
  ];
  
  res.json({ success: true, lvars: mockLvars });
});

// Update the LVAR endpoint to also log to console
app.post('/lvar/sim', (req, res) => {
  const { lvar, value } = req.body;
  
  // Log to console
  consoleEmitter.emit('log', {
    level: 'info',
    message: `LVAR Update: ${lvar} → ${value}`,
    timestamp: new Date().toISOString(),
    source: 'sim',
    id: Date.now() + Math.random().toString(36).substr(2, 9)
  });
  
  console.log(`Received LVAR update: ${lvar} -> ${value}`);
  res.json({ success: true });
});

app.post('/lvar/client', async (req, res) => {
  const { lvar, value, client } = req.body;
  
  // Log to console
  consoleEmitter.emit('log', {
    level: 'info',
    message: `LVAR from ${client}: ${lvar} → ${value}`,
    timestamp: new Date().toISOString(),
    source: 'client',
    id: Date.now() + Math.random().toString(36).substr(2, 9)
  });
  
  console.log(`Received LVAR update from client ${client}: ${lvar} -> ${value}`);
  
  const response = await fetch('http://localhost:8080/lvar/send', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ lvar, value })
  }).catch(error => {
    console.error('Error sending LVAR update:', error);
    
    consoleEmitter.emit('log', {
      level: 'error',
      message: `Failed to forward LVAR to sim: ${error.message}`,
      timestamp: new Date().toISOString(),
      source: 'server',
      id: Date.now() + Math.random().toString(36).substr(2, 9)
    });
  });

  res.json({ success: true });
});

let crewConnectProcess = null;
let crewConnectRunning = false;
let crewConnectAutoStart = false;
let serverStartTime = Date.now();

function startCrewConnectProcess() {
    return new Promise((resolve, reject) => {
        if (crewConnectProcess) {
            console.log('Crew Connect is already running');
            reject(new Error('Crew Connect is already running'));
            return;
        }

        const activateScript = path.resolve('./crew-connect/.venv/Scripts/activate.bat');
        const mainScript = path.resolve('./crew-connect/main.py');
        
        console.log('Looking for activate script at:', activateScript);
        console.log('Looking for main script at:', mainScript);
        
        // Check if files exist
        fs.access(activateScript).then(() => {
            console.log('Activate script exists');
        }).catch(err => {
            console.error('Activate script NOT FOUND:', err);
            reject(new Error(`Activate script not found at: ${activateScript}`));
            return;
        });
        
        fs.access(mainScript).then(() => {
            console.log('Main script exists');
        }).catch(err => {
            console.error('Main script NOT FOUND:', err);
            reject(new Error(`Main script not found at: ${mainScript}`));
            return;
        });
        
        // ... rest of the function
    });
}

// Function to stop Crew Connect process
function stopCrewConnectProcess() {
    return new Promise((resolve, reject) => {
        if (!crewConnectProcess) {
            reject(new Error('Crew Connect is not running'));
            return;
        }

        crewConnectProcess.kill('SIGTERM');
        
        setTimeout(() => {
            if (crewConnectProcess && !crewConnectProcess.killed) {
                crewConnectProcess.kill('SIGKILL');
            }
            
            crewConnectRunning = false;
            crewConnectProcess = null;
            
            consoleEmitter.emit('log', {
                level: 'info',
                message: 'Crew Connect stopped',
                timestamp: new Date().toISOString(),
                source: 'system'
            });
            
            resolve({ success: true, message: 'Crew Connect stopped' });
        }, 1000);
    });
}

// Add API endpoints for controlling Crew Connect
app.get('/api/crew-connect/status', (req, res) => {
    res.json({
        running: crewConnectRunning,
        pid: crewConnectProcess?.pid,
        autoStart: crewConnectAutoStart,
        uptime: serverStartTime ? Date.now() - serverStartTime : 0
    });
});

app.post('/api/crew-connect/start', async (req, res) => {
    try {
        const result = await startCrewConnectProcess();
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

app.post('/api/crew-connect/stop', async (req, res) => {
    try {
        const result = await stopCrewConnectProcess();
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

app.post('/api/crew-connect/auto-start', (req, res) => {
    const { enabled } = req.body;
    crewConnectAutoStart = Boolean(enabled);
    
    // Save to config or localStorage equivalent
    console.log(`Auto-start set to: ${crewConnectAutoStart}`);
    
    res.json({
        success: true,
        autoStart: crewConnectAutoStart
    });
});

// Auto-start Crew Connect on server start if enabled
if (process.env.CREW_CONNECT_AUTO_START === 'true') {
    crewConnectAutoStart = true;
    setTimeout(() => {
        startCrewConnectProcess();
    }, 3000);
}