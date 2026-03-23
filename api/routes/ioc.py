"""IOC Enrichment — AbuseIPDB + VirusTotal lookups with MongoDB caching."""
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException
from db.mongo import get_collection
from api.dependencies import get_current_user
from shared.config import settings

router = APIRouter(prefix="/ioc", tags=["ioc"])

CACHE_TTL_HOURS = 24


async def _check_abuseipdb(ip: str) -> dict:
    if not settings.ABUSEIPDB_API_KEY:
        return {"source": "abuseipdb", "error": "No API key configured"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.abuseipdb.com/api/v2/check",
            headers={"Key": settings.ABUSEIPDB_API_KEY, "Accept": "application/json"},
            params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": True},
        )
        if r.status_code != 200:
            return {"source": "abuseipdb", "error": f"HTTP {r.status_code}"}
        d = r.json().get("data", {})
        score = d.get("abuseConfidenceScore", 0)
        return {
            "source":           "abuseipdb",
            "confidence_score": score,
            "threat_level":     "malicious" if score >= 80 else "suspicious" if score >= 25 else "clean",
            "country":          d.get("countryCode", ""),
            "isp":              d.get("isp", ""),
            "domain":           d.get("domain", ""),
            "total_reports":    d.get("totalReports", 0),
            "last_reported":    d.get("lastReportedAt", ""),
            "usage_type":       d.get("usageType", ""),
            "is_tor":           d.get("isTor", False),
            "is_public":        d.get("isPublic", True),
        }


async def _check_virustotal(ip: str) -> dict:
    if not settings.VIRUSTOTAL_API_KEY:
        return {"source": "virustotal", "error": "No API key configured"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
            headers={"x-apikey": settings.VIRUSTOTAL_API_KEY},
        )
        if r.status_code != 200:
            return {"source": "virustotal", "error": f"HTTP {r.status_code}"}
        attrs = r.json().get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        total = sum(stats.values()) or 1
        score = round((malicious + suspicious) / total * 100)
        return {
            "source":        "virustotal",
            "malicious":     malicious,
            "suspicious":    suspicious,
            "harmless":      stats.get("harmless", 0),
            "score":         score,
            "threat_level":  "malicious" if malicious >= 3 else "suspicious" if malicious >= 1 else "clean",
            "country":       attrs.get("country", ""),
            "asn":           attrs.get("asn", ""),
            "as_owner":      attrs.get("as_owner", ""),
            "reputation":    attrs.get("reputation", 0),
        }


@router.get("/enrich")
async def enrich_ioc(ip: str, tenant_id: str = Depends(get_current_user)):
    """Check an IP against AbuseIPDB and VirusTotal. Results cached 24h."""
    if not ip or ip in ("0.0.0.0", "127.0.0.1", "localhost"):
        raise HTTPException(status_code=400, detail="Invalid IP address")

    ioc_col = get_collection("ioc_cache")

    # Return cached result if fresh
    cached = await ioc_col.find_one({"ip": ip, "tenant_id": tenant_id}, {"_id": 0})
    if cached and cached.get("cached_at"):
        age = datetime.utcnow() - cached["cached_at"]
        if age < timedelta(hours=CACHE_TTL_HOURS):
            return {**cached, "from_cache": True}

    # Live lookups
    abuse  = await _check_abuseipdb(ip)
    vt     = await _check_virustotal(ip)

    # Compute overall verdict
    levels = [abuse.get("threat_level"), vt.get("threat_level")]
    if "malicious" in levels:
        verdict = "malicious"
    elif "suspicious" in levels:
        verdict = "suspicious"
    else:
        verdict = "clean"

    result = {
        "ip":         ip,
        "tenant_id":  tenant_id,
        "verdict":    verdict,
        "abuseipdb":  abuse,
        "virustotal": vt,
        "cached_at":  datetime.utcnow(),
        "from_cache": False,
    }

    await ioc_col.replace_one(
        {"ip": ip, "tenant_id": tenant_id},
        result,
        upsert=True,
    )
    result.pop("_id", None)
    return result


@router.get("/bulk")
async def bulk_enrich(ips: str, tenant_id: str = Depends(get_current_user)):
    """Enrich multiple IPs at once. Pass comma-separated list."""
    ip_list = [i.strip() for i in ips.split(",") if i.strip()][:10]
    results = []
    for ip in ip_list:
        try:
            r = await enrich_ioc(ip=ip, tenant_id=tenant_id)
            results.append(r)
        except Exception as e:
            results.append({"ip": ip, "error": str(e)})
    return {"results": results}
