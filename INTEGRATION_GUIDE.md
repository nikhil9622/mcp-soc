# MCP SOC - Full Stack Startup Guide

## 🚀 Quick Start (Development Mode)

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker Desktop (for Redis + MongoDB)
- Firebase account (for authentication)

---

## Step 1: Start Backend Services

### Option A: Docker Compose (Recommended)

```bash
# From project root
docker-compose up -d
```

This starts:
- **Redis 7** (port 6379) - Event streams
- **MongoDB 7** (port 27017) - Data storage
- **FastAPI Broker** (port 8000) - API server
- **5 ARQ Workers** - Background agents

### Option B: Manual Setup

```bash
# Terminal 1: Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Start MongoDB
docker run -d -p 27017:27017 mongo:7

# Terminal 3: Start FastAPI Broker
python -m uvicorn main:app --reload --port 8000

# Terminal 4-8: Start ARQ Workers
python -m arq agents.ingestion.WorkerSettings
python -m arq agents.detection.WorkerSettings
python -m arq agents.correlation.WorkerSettings
python -m arq agents.investigation.WorkerSettings
python -m arq agents.alerting.WorkerSettings
```

---

## Step 2: Configure Environment Variables

### Backend (.env)

Create `.env` in project root:

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=soc

# Redis
REDIS_URL=redis://localhost:6379

# AWS S3 (for raw log storage)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET=your-soc-logs-bucket

# Anthropic (for Investigation Agent)
ANTHROPIC_API_KEY=your-anthropic-key

# SendGrid (for email alerts)
SENDGRID_API_KEY=your-sendgrid-key
SENDGRID_FROM_EMAIL=alerts@yourdomain.com

# Firebase Admin (for auth)
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json

# Frontend URL (CORS)
FRONTEND_URL=http://localhost:3000
```

### Frontend (.env.local)

Create `.env.local` in `frontend/` directory:

```env
# API Backend URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Firebase Client Config
NEXT_PUBLIC_FIREBASE_API_KEY=your-api-key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=123456789
NEXT_PUBLIC_FIREBASE_APP_ID=1:123456789:web:abcdef
```

---

## Step 3: Start Frontend

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## Step 4: Verify Integration

### 4.1 Check Backend Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "redis": "connected",
  "mongodb": "connected"
}
```

### 4.2 Check API Documentation

Visit: **http://localhost:8000/docs**

You should see interactive Swagger UI with all API endpoints.

### 4.3 Test Authentication

1. Visit **http://localhost:3000**
2. Click "Sign In"
3. Create account with Firebase
4. Should redirect to `/dashboard`

### 4.4 Test API Connection

Open browser console on dashboard and check Network tab:
- Should see requests to `http://localhost:8000/alerts`
- Should see 200 OK responses
- Data should populate in UI

---

## 🔌 API Integration Status

### ✅ Completed Integrations

| Frontend Page | API Endpoint | Status |
|---------------|--------------|--------|
| Dashboard | `GET /alerts` | ✅ Connected |
| Incidents List | `GET /incidents` | ✅ Connected |
| Incident Detail | `GET /incidents/:id` | ✅ Connected |
| Alert Feedback | `POST /alerts/:id/feedback` | ✅ Connected |

### 📋 To Be Connected

| Frontend Page | API Endpoint | Status |
|---------------|--------------|--------|
| Alerts Page | `GET /alerts` | 📋 Code ready |
| Rules Page | `GET /rules` | 📋 Code ready |
| Settings Page | `GET /users/me` | 📋 Code ready |

---

## 🛠️ Troubleshooting

### Issue: Frontend can't connect to backend

**Symptoms**: Network errors in console, "Failed to fetch" alerts

**Solution**:
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify CORS settings in `main.py` include `http://localhost:3000`
3. Check `.env.local` has correct `NEXT_PUBLIC_API_URL`

### Issue: 401 Unauthorized errors

**Symptoms**: All API calls return 401

**Solution**:
1. Verify Firebase authentication is working
2. Check Firebase service account JSON exists
3. Ensure `FIREBASE_SERVICE_ACCOUNT_PATH` is correct in backend `.env`
4. Try logging out and back in

### Issue: No data showing in UI

**Symptoms**: UI loads but shows empty states

**Solution**:
1. Backend services are running but no data ingested yet
2. **Generate test data**:
   ```bash
   python scripts/generate_test_data.py
   ```
3. Or manually ingest sample event:
   ```bash
   curl -X POST http://localhost:8000/ingest/cloudtrail \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d @tests/fixtures/sample_cloudtrail.json
   ```

### Issue: ARQ workers not processing

**Symptoms**: Events stuck, no detections created

**Solution**:
1. Check worker logs: `docker-compose logs -f detection`
2. Verify Redis streams: `redis-cli XINFO STREAM soc:events:tenant_abc`
3. Restart workers: `docker-compose restart`

---

## 📊 Architecture Overview

```
┌─────────────────┐
│   Frontend      │  Next.js 14 (Port 3000)
│   (React + TS)  │  • Dashboard
└────────┬────────┘  • Incidents
         │           • Alerts
         │ HTTP/REST • Settings
         │
┌────────▼────────┐
│  FastAPI Broker │  Python (Port 8000)
│   (main.py)     │  • Auth (Firebase)
└────────┬────────┘  • API Routes
         │           • CORS
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────┐
│ Redis │ │ MongoDB │
│  :6379│ │  :27017 │
└───┬───┘ └────┬────┘
    │          │
    │   ┌──────┴────────┐
    │   │               │
┌───▼───▼───┐     ┌────▼────┐
│ 5 ARQ     │     │ S3      │
│ Workers   │     │ (Logs)  │
│ (Agents)  │     └─────────┘
└───────────┘

Event Flow:
1. CloudTrail → /ingest/cloudtrail → Ingestion Agent
2. Ingestion → Redis Stream → Detection Agent
3. Detection → Sigma Rules → Correlation Agent
4. Correlation → NetworkX → Investigation Agent
5. Investigation → Claude AI → Alerting Agent
6. Alerting → SendGrid → Email
```

---

## 🎯 Development Workflow

### Making Frontend Changes

```bash
cd frontend
npm run dev  # Hot reload enabled
```

Edit files in `frontend/app/` or `frontend/components/` - changes appear instantly.

### Making Backend Changes

```bash
# With uvicorn --reload
uvicorn main:app --reload --port 8000
```

Edit files in `api/`, `agents/`, `shared/` - server auto-restarts.

### Testing Changes

```bash
# Run backend tests
pytest

# Run specific test file
pytest tests/test_detection.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

---

## 📦 Production Deployment

See comprehensive guides:
- **Docker**: `docs/deployment-guide.md` (Section 1)
- **AWS ECS**: `docs/deployment-guide.md` (Section 2)
- **GCP Cloud Run**: `docs/deployment-guide.md` (Section 3)
- **Kubernetes**: `docs/deployment-guide.md` (Section 4)

---

## 🔐 Security Checklist

Before deploying to production:

- [ ] Change all default credentials
- [ ] Enable HTTPS/TLS (use reverse proxy like Nginx)
- [ ] Restrict CORS to production domain only
- [ ] Rotate API keys and secrets
- [ ] Enable MongoDB authentication
- [ ] Enable Redis password protection
- [ ] Use managed services (ElastiCache, DocumentDB)
- [ ] Set up VPC with private subnets
- [ ] Enable CloudWatch/logging
- [ ] Configure WAF rules
- [ ] Set up backup policies

---

## 📞 Support

**Documentation**:
- `README.md` - Project overview
- `docs/architecture.md` - System design
- `docs/operational-runbook.md` - Operations guide
- `FRONTEND_DEPLOYMENT_GUIDE.md` - Frontend setup

**API Documentation**:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Issues**:
- Check `tests/` for examples
- Review `PHASE_11_COMPLETE.md` for frontend status
- Read `FINAL_DELIVERY_REPORT.md` for project overview

---

## ✅ Success Indicators

Your system is working correctly when:

1. ✅ `curl http://localhost:8000/health` returns status "ok"
2. ✅ Frontend loads at http://localhost:3000
3. ✅ You can sign in with Firebase
4. ✅ Dashboard shows "LIVE" indicator
5. ✅ Console shows successful API requests (200 OK)
6. ✅ Docker containers all running: `docker-compose ps`
7. ✅ No errors in ARQ worker logs

---

**Ready to Launch!** 🚀

Your MCP SOC platform is now fully integrated and ready for testing!
