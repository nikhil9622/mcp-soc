# 🎯 MCP SOC - TESTING MADE SIMPLE

## Your Question: "How do I test with fake data first?"

**Answer**: I've created everything you need! Here's the simplest path:

---

## 🚀 SUPER QUICK START (One Command!)

### Just Run This:

```powershell
test-with-fake-data.bat
```

**That's it!** This script will:
1. ✅ Check if Docker is running
2. ✅ Start Redis + MongoDB (if Docker available)
3. ✅ Generate 15 fake incidents + 15 alerts + 30 detections
4. ✅ Start backend API
5. ✅ Open frontend
6. ✅ Open your browser to http://localhost:3000

**Time**: ~3 minutes  
**Result**: Full working SOC with realistic fake data!

---

## 📊 What Fake Data You'll See

### Dashboard (http://localhost:3000/dashboard)
- **15 Alerts** with realistic titles like:
  - 🔴 "Brute force attack detected from suspicious IP"
  - 🟠 "Privilege escalation attempt detected"
  - 🟡 "Unusual access hours detected"
  - ⚪ "Login from new geographic location"

### Incidents Page (http://localhost:3000/incidents)
- **15 Incidents** with:
  - Status: Open, Investigating, Resolved, False Positive
  - Severity: Critical, High, Medium, Low
  - Risk Scores: 40-95
  - Entity tracking (users, IPs, hosts)
  - AI-generated summaries

---

## 🎨 Three Testing Options

### Option 1: Frontend Only (Fastest - 2 min)
```powershell
start-frontend-only.bat
```
- No Docker needed
- Shows UI with built-in mock data

### Option 2: Full Stack with Fake Data ⭐ RECOMMENDED
```powershell
test-with-fake-data.bat
```
- Real backend + database
- Realistic fake data
- Full integration test

### Option 3: Manual Control
```powershell
docker-compose up -d redis mongodb
python scripts/generate_test_data.py
uvicorn main:app --reload --port 8000
cd frontend && npm run dev
```

---

## ✅ Quick Verification

After running `test-with-fake-data.bat`:

1. **Backend**: http://localhost:8000/health → Should return `{"status":"ok"}`
2. **API Docs**: http://localhost:8000/docs → Swagger UI loads
3. **Frontend**: http://localhost:3000 → Shows 15 alerts

---

## 🎯 My Recommendation

**Run this right now:**

```powershell
test-with-fake-data.bat
```

Then visit **http://localhost:3000** to see your SOC!

---

**Ready?** Double-click `test-with-fake-data.bat` and enjoy! 🚀🔒
