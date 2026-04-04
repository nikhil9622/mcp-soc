from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.mongo import connect_mongo, close_mongo
from db.redis_client import connect_redis, close_redis
from db.init_db import create_indexes
from shared.config import settings
from api.routes import health, users, devices, ingest, alerts, incidents, tenants, rules, isolation, agent, graph, ioc, mitre, cases, hunting, ueba, compliance, sources, team


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_mongo()
    await connect_redis()
    await create_indexes()
    yield
    await close_mongo()
    await close_redis()


app = FastAPI(title="MCP SOC Broker", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://178.128.100.145:3000", "https://mcpsoc.dev", "https://www.mcpsoc.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(users.router)
app.include_router(devices.router)
app.include_router(ingest.router)
app.include_router(alerts.router)
app.include_router(incidents.router)
app.include_router(tenants.router)
app.include_router(rules.router)
app.include_router(isolation.router)
app.include_router(agent.router)
app.include_router(graph.router)
app.include_router(ioc.router)
app.include_router(mitre.router)
app.include_router(cases.router)
app.include_router(hunting.router)
app.include_router(ueba.router)
app.include_router(compliance.router)
app.include_router(sources.router)
app.include_router(team.router)
