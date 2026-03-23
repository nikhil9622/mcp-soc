# 🧪 Testing MCP SOC with Simulated Data

## Step-by-Step Testing Guide

This guide shows you how to test your SOC platform with fake data before connecting to real sources.

---

## 📋 Testing Strategy

```
Step 1: Frontend Only (Mock Data)
  ↓
Step 2: Backend + Simulated Data
  ↓
Step 3: Full Integration Test
  ↓
Step 4: Real Data Connection
```

---

## 🎯 STEP 1: Test Frontend Only (Fastest - START HERE!)

**What**: View the UI with built-in mock data  
**Time**: 2 minutes  
**Requirements**: Node.js only

### How to Run:

```powershell
# Just run this:
start-frontend-only.bat
```

Or manually:

```powershell
cd frontend
npm install
npm run dev
```

### What You'll See:

- **Dashboard**: http://localhost:3000/dashboard
- **Incidents**: http://localhost:3000/incidents
- Mock alerts and incidents load instantly
- All UI features work (search, filter, etc.)

### ✅ Success Indicators:

- [x] Page loads without errors
- [x] Mock data displays in cards
- [x] Severity badges show colors
- [x] Search/filter works
- [x] "LIVE" indicator pulses

**Status**: ✅ This already works! No backend needed.

---

## 🔧 STEP 2: Backend with Simulated Data

**What**: Full backend with realistic test data  
**Time**: 10 minutes  
**Requirements**: Docker or local Python/Redis/MongoDB

### Option A: Using Docker (Recommended)

#### 2.1 Start Services

```powershell
# Make sure Docker Desktop is running
docker info

# Start Redis and MongoDB
docker-compose up -d redis mongodb

# Wait 10 seconds for services to be ready
timeout /t 10
```

#### 2.2 Generate Test Data

```powershell
# Install Python dependencies
pip install -r requirements.txt

# Run the data generator
python scripts/generate_test_data.py
```

**Expected Output:**

```
============================================================
MCP SOC - Test Data Generator
============================================================

Generating 50 security events...
✅ Created 50 events
Generating 30 detections...
✅ Created 30 detections
Generating 15 incidents...
✅ Created 15 incidents
Generating alerts for 15 incidents...
✅ Created 15 alerts

✅ Test Data Generation Complete!

Summary:
  • Events:     50
  • Detections: 30
  • Incidents:  15
  • Alerts:     15

Tenant ID: demo_tenant
```

#### 2.3 Start Backend API

```powershell
# Start FastAPI
uvicorn main:app --reload --port 8000
```

#### 2.4 Test API Endpoints

```powershell
# Check health
curl http://localhost:8000/health

# Should return: {"status":"ok","redis":"connected","mongodb":"connected"}
```

---

## 🌐 STEP 3: Full Integration Test

**What**: Connect frontend to backend with test data  
**Time**: 5 minutes  
**Requirements**: Step 2 completed

### 3.1 Start Frontend

```powershell
cd frontend
npm run dev
```

### 3.2 Test Full Flow

1. **Visit**: http://localhost:3000
2. **Sign in** (or skip if demo mode)
3. **Check Dashboard**: Should show 15 real alerts from database
4. **Check Incidents**: Should show 15 real incidents
5. **Test Filters**: Try filtering by severity
6. **Test Search**: Search for "brute force"

### ✅ Success Indicators:

- [x] Dashboard loads alerts from API
- [x] Incidents page loads incidents from API
- [x] Console shows `GET /alerts` → 200 OK
- [x] Data refreshes every 30 seconds
- [x] No CORS errors

---

## 🎨 What the Test Data Looks Like

The generator creates realistic security scenarios:

### Sample Incidents:
- 🔴 **Critical**: "Brute force attack detected from suspicious IP"
- 🟠 **High**: "Privilege escalation attempt detected"
- 🟡 **Medium**: "Unusual access hours detected"
- ⚪ **Low**: "Login from new geographic location"

### Data Distribution:
- **15 incidents** across all severity levels
- **30 detections** with MITRE ATT&CK mapping
- **50 events** spread over 72 hours
- **Multiple users**: alice, bob, charlie, admin, analyst
- **Multiple IPs**: 203.0.113.1, 192.0.2.50, 198.51.100.1

---

## 🚀 Quick Start Commands

### Fastest Way (Frontend Only):
```powershell
start-frontend-only.bat
```

### Full Stack with Test Data:
```powershell
# Terminal 1: Start Docker services
docker-compose up -d redis mongodb

# Terminal 2: Generate test data
pip install -r requirements.txt
python scripts/generate_test_data.py

# Terminal 3: Start backend
uvicorn main:app --reload --port 8000

# Terminal 4: Start frontend
cd frontend
npm run dev
```

Then visit: **http://localhost:3000**

---

## 🐛 Common Issues & Solutions

### Issue: "Docker not running"
**Solution**: Open Docker Desktop, wait for whale icon to be steady

### Issue: "No data showing in UI"
**Solution**: 
```powershell
python scripts/generate_test_data.py
```

### Issue: "CORS errors"
**Solution**: Check backend is running on port 8000

### Issue: "401 Unauthorized"
**Solution**: For testing, you can bypass auth (see detailed guide)

---

## ✅ Verification Checklist

Before moving to real data:

- [ ] Frontend loads without errors
- [ ] Dashboard shows 15 alerts
- [ ] Incidents page shows 15 incidents
- [ ] Severity filters work
- [ ] Search functionality works
- [ ] API returns 200 OK
- [ ] Data refreshes automatically
- [ ] No console errors

---

## 📞 Quick Reference

| Command | Purpose |
|---------|---------|
| `start-frontend-only.bat` | Test UI only (fastest) |
| `python scripts/generate_test_data.py` | Create fake data |
| `docker-compose up -d` | Start all services |
| `uvicorn main:app --reload` | Start API only |
| `npm run dev` (in frontend/) | Start UI |
| `curl http://localhost:8000/health` | Check backend |

---

**🎯 Recommended Path:**

1. **Start here**: Run `start-frontend-only.bat` (2 min)
2. **See the UI**: Visit http://localhost:3000
3. **Then add backend**: Run the full stack commands above
4. **Generate data**: `python scripts/generate_test_data.py`
5. **Refresh browser**: See real data from database!

**Ready?** Just run `start-frontend-only.bat` now! 🚀
