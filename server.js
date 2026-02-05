import express from 'express';
import WinReg from 'winreg';
import os, { type } from 'os';
import https from 'https';
import { exec,spawn } from "child_process";
import fs from 'fs/promises';
import path from 'path';
import EventEmitter from 'events';
import { stat } from 'fs';

const app = express();

let crewConnectAlive = false;
let serverStatus = false; 
let clientStatus = false;
let GLOBALCODE = 'null';

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
        crewConnectRunning: crewConnectAlive,
        serverStatus: serverStatus,
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

let lastAck = Date.now();
let pingToken = '';


app.get('/ping', (req, res) => {
  pingToken = Date.now().toString();
  res.json({ token: pingToken });
});

app.post('/pong', (req, res) => {
  const { token, code } = req.body;

  if (token === pingToken && code === 657) {
    lastAck = Date.now();
    crewConnectAlive = true;
    return res.json({ success: true });
  }

  res.status(400).json({ success: false });
});

setInterval(() => {
  if (Date.now() - lastAck > 6000) {
    crewConnectAlive = false;
  }
}, 1000);

app.get('/status/crewconnect', (req, res) => {
  res.json({ running: crewConnectAlive });
});


app.post('/toggle-server', (req, res) => {
    serverStatus = !serverStatus;
    console.log('Server status toggled. Now:', serverStatus ? 'Running' : 'Stopped');
    res.json({ success: true, serverStatus });
}); 

app.get('/app-info', (req, res) => {
  res.json({
        mode: serverStatus ? 'server' : (clientStatus ? 'client' : 'none'),
        code: GLOBALCODE,
        
    });
});

app.get('/generate-code', (req, res) => {
    const code = Math.floor(100000 + Math.random() * 900000).toString();
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    let randomLetters = '';
    for (let i = 0; i < 5; i++) {
        randomLetters += letters.charAt(Math.floor(Math.random() * letters.length));
    }
    GLOBALCODE = code + randomLetters;
    res.json({ code: code + randomLetters });
});