"""FastAPI 主程序：路由 + SSE 流式日志。

启动:
    python -m webui.app
或者:
    python start_webui.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from . import db, registrar  # noqa: E402
from .auto_loop import CONTROLLER as AUTO_LOOP  # noqa: E402

# 启动时自动释放卡死的 in_use 号（上次进程崩溃 / 强退留下的）
try:
    _released = db.release_stale_in_use(stale_seconds=1800)
    if _released > 0:
        logging.getLogger("webui").info(f"[startup] 释放 {_released} 个卡死的 in_use 号")
except Exception as _e:
    logging.getLogger("webui").warning(f"[startup] release_stale 失败: {_e}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("webui")

STATIC_DIR = Path(__file__).resolve().parent / "static"
BOOT_ID = str(int(time.time() * 1000))

app = FastAPI(title="GPT Outlook Register WebUI", docs_url=None, redoc_url=None)


# ──────────────────────── Pydantic 模型 ────────────────────────


class ImportReq(BaseModel):
    text: str = Field(..., description="多行 4 段格式 (email----password----client_id----refresh_token)")


class RegisterReq(BaseModel):
    email: Optional[str] = Field(None, description="留空 = 自动 claim 下一个 available")
    want_access_token: bool = True
    want_session_token: bool = True
    want_refresh_token: bool = True
    proxy: str = ""
    otp_timeout: int = 180
    allow_existing_login: bool = True


# ──────────────────────── API ────────────────────────


@app.get("/api/health")
def health():
    return {"ok": True, "stats": db.stats()}


@app.post("/api/import")
def api_import(req: ImportReq):
    result = db.import_accounts(req.text)
    return {"ok": True, **result, "stats": db.stats()}


@app.get("/api/accounts")
def api_accounts(status: str = "", limit: int = 50, offset: int = 0):
    items = db.list_accounts(status=status, limit=limit, offset=offset)
    total = db.count_accounts(status=status)
    return {"ok": True, "items": items, "total": total}


@app.delete("/api/accounts/{email}")
def api_delete_account(email: str):
    ok = db.delete_account(email)
    if not ok:
        raise HTTPException(404, "not found")
    return {"ok": True}


class BulkDeleteReq(BaseModel):
    status: Optional[str] = Field(None, description="available/in_use/done/failed/all")
    emails: Optional[list[str]] = Field(None, description="按 email 列表删")


@app.post("/api/accounts/bulk_delete")
def api_bulk_delete(req: BulkDeleteReq):
    """按状态或 email 列表批量删除号池。两个参数二选一（status 优先）。"""
    if req.status:
        n = db.delete_accounts_by_status(req.status)
        return {"ok": True, "deleted": n, "by": "status", "stats": db.stats()}
    if req.emails:
        n = db.delete_accounts_by_emails(req.emails)
        return {"ok": True, "deleted": n, "by": "emails", "stats": db.stats()}
    raise HTTPException(400, "需要 status 或 emails")


@app.post("/api/accounts/reset_failed")
def api_reset_failed():
    n = db.reset_failed_to_available()
    return {"ok": True, "reset": n, "stats": db.stats()}


@app.post("/api/accounts/reset/{email}")
def api_reset_account(email: str):
    """重置单个号：done / failed → available。"""
    ok = db.reset_to_available(email)
    if not ok:
        raise HTTPException(404, f"邮箱 {email} 不存在")
    return {"ok": True, "email": email}


class BulkResetReq(BaseModel):
    emails: list[str]


@app.post("/api/accounts/bulk_reset")
def api_bulk_reset(req: BulkResetReq):
    """批量重置：done / failed → available。"""
    if not req.emails:
        raise HTTPException(400, "emails 不能为空")
    n = db.bulk_reset_to_available(req.emails)
    return {"ok": True, "reset": n, "stats": db.stats()}


@app.post("/api/accounts/release_stale")
def api_release_stale(stale_seconds: int = 1800):
    n = db.release_stale_in_use(stale_seconds=stale_seconds)
    return {"ok": True, "released": n, "stats": db.stats()}


@app.get("/api/stats")
def api_stats():
    return {"ok": True, "stats": db.stats(), "boot_id": BOOT_ID}


@app.post("/api/register")
def api_register(req: RegisterReq):
    """启动注册任务，返回 run_id。前端拿 run_id 去 /api/runs/{run_id}/stream 订阅 SSE。"""
    mail_source = db.get_setting("mail_source", "outlook")
    is_cf = (mail_source == "cf_temp")

    if is_cf:
        # CF 模式：不需要 outlook 号池，用虚拟占位 account
        import time as _t
        account = {
            "email": f"cf_placeholder_{int(_t.time())}@cf.local",
            "password": "",
            "client_id": "",
            "refresh_token": "",
        }
    elif req.email:
        account = db.claim_account(req.email)
        if not account:
            raise HTTPException(400, f"邮箱 {req.email} 不可用 (不存在 / 已 in_use / 已完成)")
    else:
        account = db.claim_next()
        if not account:
            raise HTTPException(400, "号池里没有 available 账号；请先批量导入")

    options = {
        "want_access_token": req.want_access_token,
        "want_session_token": req.want_session_token,
        "want_refresh_token": req.want_refresh_token,
        "proxy": req.proxy,
        "otp_timeout": int(req.otp_timeout),
        "allow_existing_login": req.allow_existing_login,
    }
    run_id = registrar.start_registration(account, options)
    logger.info(f"[run] {run_id} -> {account['email']} (mail_source={mail_source})")
    return {"ok": True, "run_id": run_id, "email": account["email"]}


@app.get("/api/runs/{run_id}/stream")
async def api_stream(run_id: str, request: Request):
    """SSE 实时推送日志 + 事件。"""
    q = registrar.get_run_queue(run_id)
    if q is None:
        raise HTTPException(404, "run_id not found or finished")

    async def event_gen():
        loop = asyncio.get_event_loop()
        try:
            while True:
                if await request.is_disconnected():
                    break
                # 从队列取消息（用 run_in_executor 避免阻塞 event loop）
                msg = await loop.run_in_executor(None, _safe_get, q)
                if msg is None:
                    # sentinel: 任务结束
                    yield "event: end\ndata: {}\n\n"
                    break
                if msg.startswith("__EVENT__:"):
                    yield f"event: status\ndata: {msg[len('__EVENT__:'):]}\n\n"
                else:
                    yield f"event: log\ndata: {json.dumps({'line': msg}, ensure_ascii=False)}\n\n"
        finally:
            registrar.remove_run_queue(run_id)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 避免 nginx 缓冲
            "Connection": "keep-alive",
        },
    )


def _safe_get(q):
    try:
        return q.get(timeout=60)
    except Exception:
        return ""  # 心跳：返空串让 SSE 检查 disconnect


@app.get("/api/runs")
def api_runs(limit: int = 50):
    return {"ok": True, "items": db.list_runs(limit=limit)}


@app.get("/api/registered")
def api_registered(limit: int = 20, offset: int = 0, filter: str = "all"):
    items = db.list_registered(limit=limit, offset=offset, filter_rt=filter)
    total = db.count_registered(filter_rt=filter)
    return {"ok": True, "items": items, "total": total}


@app.get("/api/registered/{email}")
def api_registered_one(email: str):
    row = db.get_registered(email)
    if not row:
        raise HTTPException(404, "not found")
    return {"ok": True, "data": row}


@app.get("/api/registered/{email}/auth_json")
def api_registered_auth_json(email: str):
    """导出 Codex CLI auth.json（需要 Agent Identity 凭证）。"""
    row = db.get_registered(email)
    if not row:
        raise HTTPException(404, "not found")
    extra = row.get("extra") or {}
    agent_runtime_id = extra.get("agent_runtime_id", "")
    agent_private_key = extra.get("agent_private_key", "")
    if not agent_runtime_id or not agent_private_key:
        raise HTTPException(400, "该账号没有 Agent Identity 凭证（无 agent_runtime_id）")
    access_token = row.get("access_token", "")
    account_id = ""
    user_id = ""
    plan_type = "free"
    account_email = row.get("email", email)
    if access_token:
        try:
            from codex_agent import extract_account_info
            info = extract_account_info(access_token)
            account_id = info.get("account_id", "")
            user_id = info.get("user_id", "")
            account_email = info.get("email", "") or account_email
            plan_type = info.get("plan_type", "free")
        except Exception:
            pass
    from codex_agent import build_auth_json
    auth_json = build_auth_json(
        agent_runtime_id=agent_runtime_id,
        private_key_b64=agent_private_key,
        account_id=account_id,
        user_id=user_id,
        email=account_email,
        plan_type=plan_type,
    )
    return JSONResponse(content=auth_json, headers={
        "Content-Disposition": f'attachment; filename="auth.json"',
    })


@app.delete("/api/registered/{email}")
def api_delete_registered(email: str):
    ok = db.delete_registered(email)
    if not ok:
        raise HTTPException(404, "not found")
    return {"ok": True}


class BulkDeleteRegisteredReq(BaseModel):
    emails: Optional[list[str]] = Field(None, description="按 email 列表删；留空 + all=true 则删全部")
    all: bool = False


@app.post("/api/registered/bulk_delete")
def api_bulk_delete_registered(req: BulkDeleteRegisteredReq):
    if req.all:
        n = db.delete_all_registered()
        return {"ok": True, "deleted": n, "by": "all"}
    if req.emails:
        n = db.delete_registered_by_emails(req.emails)
        return {"ok": True, "deleted": n, "by": "emails"}
    raise HTTPException(400, "需要 emails 或 all=true")


# ──────────────────────── 邮箱来源配置 ────────────────────────


@app.get("/api/settings/mail")
def api_get_mail_config():
    return {"ok": True, "config": db.get_mail_config()}


class SaveMailConfigReq(BaseModel):
    mail_source: Optional[str] = None       # outlook / cf_temp
    cf_api_url: Optional[str] = None
    cf_admin_token: Optional[str] = None
    cf_domain: Optional[str] = None


@app.post("/api/settings/mail")
def api_save_mail_config(req: SaveMailConfigReq):
    db.save_mail_config(req.model_dump(exclude_none=True))
    return {"ok": True, "config": db.get_mail_config()}


@app.post("/api/settings/mail/test")
def api_test_mail():
    """测试 CF Temp Email 连通性：创建一个测试地址，确认 admin_token + domain 都对。"""
    mail_source = db.get_setting("mail_source", "outlook")
    if mail_source != "cf_temp":
        raise HTTPException(400, f"当前 mail_source={mail_source}，不需要测试")

    api_url = db.get_setting("cf_api_url", "")
    domain = db.get_setting("cf_domain", "")
    token = db.get_cf_admin_token()
    if not api_url:
        raise HTTPException(400, "未配置 cf_api_url")
    if not domain:
        raise HTTPException(400, "未配置 cf_domain")
    if not token:
        raise HTTPException(400, "未配置 cf_admin_token")

    import sys as _sys
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in _sys.path:
        _sys.path.insert(0, str(ROOT_DIR))
    from mail_cf import CFTempEmailProvider
    try:
        provider = CFTempEmailProvider(api_url=api_url, admin_token=token, domain=domain)
        test_email = provider.create_mailbox()
        return {"ok": True, "message": f"连接成功，测试邮箱: {test_email}"}
    except Exception as e:
        raise HTTPException(500, f"连接失败: {e}")


# ──────────────────────── SMS 接码配置 ────────────────────────


@app.get("/api/settings/sms")
def api_get_sms_config():
    return {"ok": True, "config": db.get_sms_config()}


class SaveSmsConfigReq(BaseModel):
    sms_enabled: Optional[str] = None              # "0" / "1"
    sms_provider: Optional[str] = None             # smsbower / herosms
    sms_api_key: Optional[str] = None              # 传 '***' 表示不修改
    sms_country: Optional[str] = None              # ID 或国家代码（'52' / 'th'）
    sms_service: Optional[str] = None              # OpenAI = 'dr'
    sms_max_price: Optional[str] = None
    sms_reuse_phone: Optional[str] = None
    sms_phone_success_max: Optional[str] = None
    sms_auto_country: Optional[str] = None
    sms_strict_whitelist: Optional[str] = None
    sms_allowed_countries: Optional[str] = None    # 逗号分隔的 ID 列表，自动选号时只从这里挑
    sms_auto_min_stock: Optional[str] = None
    sms_auto_max_price: Optional[str] = None
    sms_max_phone_attempts: Optional[str] = None   # 空 = 用 provider 默认；>0 = 自定义
    sms_per_phone_timeout: Optional[str] = None    # 单号等待秒数（默认 80）


@app.post("/api/settings/sms")
def api_save_sms_config(req: SaveSmsConfigReq):
    db.save_sms_config(req.model_dump(exclude_none=True))
    return {"ok": True, "config": db.get_sms_config()}


@app.post("/api/settings/sms/test")
def api_test_sms():
    """测试 SMS provider 连通性：查询余额。"""
    cfg = db.get_sms_internal_config()
    if not cfg.get("sms_api_key"):
        raise HTTPException(400, "未配置 sms_api_key")

    import sys as _sys
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in _sys.path:
        _sys.path.insert(0, str(ROOT_DIR))
    from sms_provider import create_sms_provider
    try:
        provider = create_sms_provider(cfg["sms_provider"], cfg)
        balance = provider.get_balance()
        return {
            "ok": True,
            "provider": cfg["sms_provider"],
            "balance": balance,
            "message": f"连接成功，余额: {balance}",
        }
    except Exception as e:
        raise HTTPException(500, f"连接失败: {e}")


@app.get("/api/settings/sms/countries")
def api_sms_top_countries():
    """查询当前接码平台的国家排名（价格 + 库存）。"""
    cfg = db.get_sms_internal_config()
    if not cfg.get("sms_api_key"):
        raise HTTPException(400, "未配置 sms_api_key")

    import sys as _sys
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in _sys.path:
        _sys.path.insert(0, str(ROOT_DIR))
    from sms_provider import create_sms_provider, OPENAI_SMS_COUNTRIES, SMS_COUNTRY_NAMES_CN
    try:
        provider = create_sms_provider(cfg["sms_provider"], cfg)
        rows = provider.get_top_countries(service=cfg.get("sms_service") or "dr")
        for r in rows:
            cid = str(r.get("country"))
            r["openai_sms_safe"] = cid in OPENAI_SMS_COUNTRIES
            r["name_cn"] = SMS_COUNTRY_NAMES_CN.get(cid, "未知")
        return {"ok": True, "countries": rows[:30], "openai_sms_safe": list(OPENAI_SMS_COUNTRIES)}
    except Exception as e:
        raise HTTPException(500, f"查询失败: {e}")


@app.get("/api/settings/sms/all_countries")
def api_sms_all_countries(provider: str = ""):
    """返回当前平台实际有库存的国家（动态查询）；查询失败则 fallback 到静态字典。"""
    import sys as _sys
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in _sys.path:
        _sys.path.insert(0, str(ROOT_DIR))
    from sms_provider import SMS_COUNTRY_NAMES_CN, OPENAI_SMS_COUNTRIES, create_sms_provider

    cfg = db.get_sms_internal_config()
    if provider:
        cfg["sms_provider"] = provider

    # 尝试从平台 API 动态获取有库存的国家
    if cfg.get("sms_api_key"):
        try:
            p = create_sms_provider(cfg["sms_provider"], cfg)
            rows = p.get_top_countries(service=cfg.get("sms_service") or "dr")
            countries = []
            for r in rows:
                cid = str(r.get("country") or "")
                countries.append({
                    "id": cid,
                    "name_cn": SMS_COUNTRY_NAMES_CN.get(cid, f"国家{cid}"),
                    "openai_sms_safe": cid in OPENAI_SMS_COUNTRIES,
                    "price": r.get("price"),
                    "count": r.get("count"),
                })
            if countries:
                return {"ok": True, "countries": countries,
                        "openai_sms_safe": list(OPENAI_SMS_COUNTRIES), "source": "live"}
        except Exception:
            pass

    # fallback: 静态字典
    items = sorted(SMS_COUNTRY_NAMES_CN.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 9999)
    countries = [
        {"id": cid, "name_cn": name, "openai_sms_safe": cid in OPENAI_SMS_COUNTRIES}
        for cid, name in items
    ]
    return {"ok": True, "countries": countries,
            "openai_sms_safe": list(OPENAI_SMS_COUNTRIES), "source": "static"}


# ──────────────────────── 自动导出 (CPA / SUB2API) ────────────────────────


class SaveExportConfigReq(BaseModel):
    # CPA
    cpa_enabled: Optional[str] = None       # "0" / "1"
    cpa_url: Optional[str] = None
    cpa_mgmt_key: Optional[str] = None      # 传 '***' 表示不修改
    cpa_timeout: Optional[str] = None
    # SUB2API
    sub2api_enabled: Optional[str] = None
    sub2api_url: Optional[str] = None
    sub2api_api_key: Optional[str] = None   # '***' 不修改
    sub2api_group_ids: Optional[str] = None  # 逗号分隔，例 "2" 或 "1,2,3"
    sub2api_timeout: Optional[str] = None


@app.get("/api/settings/export")
def api_get_export_config():
    return {"ok": True, "config": db.get_export_config()}


@app.post("/api/settings/export")
def api_save_export_config(req: SaveExportConfigReq):
    db.save_export_config(req.model_dump(exclude_none=True))
    return {"ok": True, "config": db.get_export_config()}


class TestExportReq(BaseModel):
    target: str = Field(..., description="cpa 或 sub2api")


@app.post("/api/settings/export/test")
def api_test_export(req: TestExportReq):
    """测试 CPA / SUB2API 连通性。"""
    from . import exporter
    cfg = db.get_export_internal_config()
    target = (req.target or "").strip().lower()
    try:
        if target == "cpa":
            return exporter.test_cpa(cfg["cpa"])
        if target == "sub2api":
            return exporter.test_sub2api(cfg["sub2api"])
        raise HTTPException(400, f"未知 target: {target}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"测试失败: {e}")


class ManualExportReq(BaseModel):
    email: str = Field(..., description="要导出的已注册账号邮箱")
    targets: list[str] = Field(default_factory=lambda: ["cpa", "sub2api"],
                                description="选择导出目标：cpa / sub2api")


@app.post("/api/registered/export_to_panel")
def api_manual_export_to_panel(req: ManualExportReq):
    """对一个已注册账号手动触发到面板的导出。

    targets 里选 cpa / sub2api 之一或全部。即使总开关未启用，本接口也会执行
    （只要 URL/密钥 等基础配置已填）。
    """
    from . import exporter
    cred = db.get_registered(req.email)
    if not cred:
        raise HTTPException(404, f"未找到已注册账号: {req.email}")

    cfg = db.get_export_internal_config()
    out = {"email": req.email, "cpa": None, "sub2api": None}
    targets = {t.strip().lower() for t in (req.targets or []) if t}

    if "cpa" in targets:
        cpa_cfg = dict(cfg["cpa"])
        cpa_cfg["enabled"] = True  # 手动触发：强制启用
        try:
            out["cpa"] = exporter.export_to_cpa(cred, cpa_cfg)
        except Exception as e:
            out["cpa"] = {"ok": False, "error": str(e)}
    if "sub2api" in targets:
        sub2api_cfg = dict(cfg["sub2api"])
        sub2api_cfg["enabled"] = True
        try:
            out["sub2api"] = exporter.export_to_sub2api(cred, sub2api_cfg)
        except Exception as e:
            out["sub2api"] = {"ok": False, "error": str(e)}

    return {"ok": True, **out}


# ──────────────────────── auto-loop ────────────────────────


class AutoLoopStartReq(BaseModel):
    """跟 RegisterReq 复用同样的字段，auto-loop 内部传给每个 run。"""
    want_access_token: bool = True
    want_session_token: bool = True
    want_refresh_token: bool = True
    proxy: str = ""              # 单代理（concurrency=1 + 无代理池时用）
    proxy_pool: str = ""         # 多代理池（每行一个）；优先于 proxy
    concurrency: int = 1         # 并发 worker 数（1-20）
    otp_timeout: int = 180
    allow_existing_login: bool = True
    cool_down_seconds: float = 3.0  # 每个 worker 跑完后冷却（防风控）


@app.post("/api/auto/start")
def api_auto_start(req: AutoLoopStartReq):
    res = AUTO_LOOP.start(req.model_dump())
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "启动失败"))
    return res


@app.post("/api/auto/pause")
def api_auto_pause():
    res = AUTO_LOOP.pause()
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "暂停失败"))
    return res


@app.post("/api/auto/resume")
def api_auto_resume():
    res = AUTO_LOOP.resume()
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "恢复失败"))
    return res


@app.post("/api/auto/stop")
def api_auto_stop():
    res = AUTO_LOOP.stop()
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "停止失败"))
    return res


@app.get("/api/auto/status")
def api_auto_status():
    return {"ok": True, **AUTO_LOOP.status()}


@app.get("/api/auto/stream")
async def api_auto_stream(request: Request):
    """SSE 推送 auto-loop 状态变化 + run_started / run_finished 事件。"""
    q = AUTO_LOOP.subscribe()

    async def gen():
        loop = asyncio.get_event_loop()
        try:
            while True:
                if await request.is_disconnected():
                    break
                # 阻塞拿消息，但每 30s 心跳
                try:
                    msg = await loop.run_in_executor(None, lambda: q.get(timeout=30))
                except Exception:
                    yield ": heartbeat\n\n"
                    continue
                if msg is None:
                    break
                kind = msg.get("kind", "state")
                data = msg.get("data", {})
                yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            AUTO_LOOP.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ──────────────────────── 静态资源 ────────────────────────


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webui.app:app", host="127.0.0.1", port=8765, reload=False)
