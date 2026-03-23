# Docker Startup Troubleshooting Guide

## ❌ Error: "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified"

**This means**: Docker Desktop is not running.

---

## ✅ Solution 1: Start Docker Desktop

1. **Open Docker Desktop**
   - Press `Windows Key`
   - Search for "Docker Desktop"
   - Click to launch

2. **Wait for Docker to start** (30-60 seconds)
   - Look for the whale icon in system tray
   - Icon should be steady (not animated)
   - Right-click → Should show "Docker Desktop is running"

3. **Verify Docker is ready**
   ```powershell
   docker info
   ```
   Should show system information (not errors)

4. **Try again**
   ```powershell
   docker-compose up -d
   ```

---

## 🔧 Solution 2: Manual Service Startup (No Docker Required)

If Docker doesn't work, you can run everything manually with Python:

### Step 1: Install Redis & MongoDB Locally

**Option A: Using Chocolatey (Windows Package Manager)**
```powershell
# Install Chocolatey first (if not installed)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Redis and MongoDB
choco install redis-64 -y
choco install mongodb -y

# Start services
redis-server
mongod
```

**Option B: Download installers**
- Redis: https://github.com/microsoftarchive/redis/releases (download .msi)
- MongoDB: https://www.mongodb.com/try/download/community (Windows installer)

### Step 2: Start Backend Services Manually

```powershell
# Terminal 1: Start Redis (if not running as service)
redis-server

# Terminal 2: Start MongoDB (if not running as service)
mongod --dbpath C:\data\db

# Terminal 3: Install Python dependencies
pip install -r requirements.txt

# Terminal 4: Start FastAPI Broker
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 5: Start Ingestion Agent
python -m arq agents.ingestion.WorkerSettings

# Terminal 6: Start Detection Agent
python -m arq agents.detection.WorkerSettings

# Terminal 7: Start Correlation Agent
python -m arq agents.correlation.WorkerSettings

# Terminal 8: Start Investigation Agent
python -m arq agents.investigation.WorkerSettings

# Terminal 9: Start Alerting Agent
python -m arq agents.alerting.WorkerSettings
```

### Step 3: Start Frontend

```powershell
# Terminal 10: Start Next.js
cd frontend
npm install
npm run dev
```

---

## 🚀 Solution 3: Simplified Startup (Frontend Only)

If you just want to test the frontend UI without backend:

### Step 1: Use Mock Data

The frontend already has fallback logic. Just start it:

```powershell
cd frontend
npm install
npm run dev
```

Visit: http://localhost:3000

The UI will work with mock data (no backend needed).

### Step 2: (Optional) Mock API Server

Create a simple mock API:

```javascript
// frontend/mock-api.js
const express = require('express');
const cors = require('cors');
const app = express();

app.use(cors());
app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'ok', redis: 'mocked', mongodb: 'mocked' });
});

app.get('/alerts', (req, res) => {
  res.json([
    {
      alert_id: 'alt_001',
      severity: 'critical',
      title: 'Brute force detected',
      created_at: new Date().toISOString(),
    }
  ]);
});

app.get('/incidents', (req, res) => {
  res.json([
    {
      incident_id: 'inc_001',
      severity: 'high',
      status: 'open',
      summary: { summary: 'Test incident' },
      created_at: new Date().toISOString(),
    }
  ]);
});

app.listen(8000, () => console.log('Mock API running on :8000'));
```

Run it:
```powershell
npm install express cors
node mock-api.js
```

---

## 🐳 Solution 4: Fix Docker Issues

### Common Docker Desktop Issues

**Issue 1: Docker Desktop won't start**
- Open Task Manager → Services tab
- Look for "Docker Desktop Service"
- Right-click → Start

**Issue 2: WSL 2 not installed (Windows)**
```powershell
# Run as Administrator
wsl --install
# Restart computer
```

**Issue 3: Virtualization not enabled**
1. Restart computer
2. Enter BIOS (usually F2, F10, or Del during boot)
3. Enable "Intel VT-x" or "AMD-V"
4. Save and reboot

**Issue 4: Docker daemon not running**
- Uninstall Docker Desktop
- Restart computer
- Reinstall from: https://www.docker.com/products/docker-desktop

---

## 📝 Quick Diagnostic Commands

```powershell
# Check if Docker is running
docker --version
docker info

# Check if Docker Compose is available
docker-compose --version

# List running containers
docker ps

# Check Docker Desktop status
Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
```

---

## ✅ Verification Steps

After fixing Docker:

1. **Check Docker is running**
   ```powershell
   docker info
   # Should show system info, NOT errors
   ```

2. **Check images exist**
   ```powershell
   docker images
   # Should show redis, mongo, etc.
   ```

3. **Start services**
   ```powershell
   docker-compose up -d
   ```

4. **Check all containers running**
   ```powershell
   docker-compose ps
   # All should show "Up" status
   ```

5. **Test backend health**
   ```powershell
   curl http://localhost:8000/health
   # Should return JSON: {"status":"ok"}
   ```

---

## 🎯 Recommended Approach

**For Development (Easiest)**:
1. Use Solution 3 (Frontend only with mock data)
2. Test UI and design
3. Connect to real backend later

**For Full Stack Testing**:
1. Fix Docker Desktop (Solution 1)
2. Or use manual startup (Solution 2)

**For Production**:
- Use Docker Compose or Kubernetes
- See `docs/deployment-guide.md`

---

## 🆘 Still Having Issues?

### Quick Test: Frontend Only

```powershell
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000

The frontend will work standalone (with mock data fallback) so you can at least see the UI!

### Need Backend?

If Docker won't work, use **Solution 2** (Manual Startup) - it's more setup but guaranteed to work.

---

## 📞 Alternative: Cloud Services

If local setup is too complex, consider:

1. **Backend**: Deploy to Railway.app or Render.com (free tier)
2. **Frontend**: Deploy to Vercel (free tier)
3. **Databases**: MongoDB Atlas (free) + Redis Labs (free)

See `docs/deployment-guide.md` for cloud deployment instructions.

---

**TL;DR**: Open Docker Desktop, wait for it to start, then run `docker-compose up -d` again!
