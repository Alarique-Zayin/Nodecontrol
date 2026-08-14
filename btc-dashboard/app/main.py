from fastapi import FastAPI, Request
import logging
import time
import os
import uuid
from pythonjsonlogger import jsonlogger
from prometheus_client import Counter, Histogram, make_asgi_app, REGISTRY
from fastapi.responses import FileResponse
import jinja2
from jinja2 import select_autoescape
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# When running this file directly (python app/main.py), the package
# imports like `from app.config import ...` can fail because the
# interpreter sets sys.path[0] to the `app/` directory. Ensure the
# project root is on sys.path so `app` can be imported as a package.
if __package__ is None:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
else:
    # when imported as a module, resolve project_root relative to package
    project_root = Path(__file__).resolve().parents[1]

from app.config import Settings
from app.services.rpc import BitcoinRPCClient
from app.services.cache import MetricsCache
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json


templates = Jinja2Templates(directory=str(project_root / "app" / "templates"))
# Replace the Jinja2 environment with one that has caching disabled to avoid
# a runtime `TypeError: unhashable type: 'dict'` seen in some Jinja2 versions
# when template globals are used as cache keys.
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(project_root / "app" / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=0,
)
templates.env = env


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title="Bitcoin Node Dashboard")

    # Configure basic structured JSON file logging for the app
    logger = logging.getLogger("btc-dashboard")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        # console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(ch)

        # file handler with JSON formatter + rotation
        logs_dir = project_root / "logs"
        os.makedirs(logs_dir, exist_ok=True)
        rfh = RotatingFileHandler(logs_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5)
        rfh.setLevel(logging.INFO)
        json_formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s')
        rfh.setFormatter(json_formatter)
        logger.addHandler(rfh)

    app.state.logger = logger

    # Prometheus metrics (create safely to avoid DuplicateTimeseries on reload)
    if "http_requests_total" in REGISTRY._names_to_collectors:
        REQUEST_COUNT = REGISTRY._names_to_collectors["http_requests_total"]
    else:
        REQUEST_COUNT = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status_code"],
        )

    if "http_request_duration_seconds" in REGISTRY._names_to_collectors:
        REQUEST_LATENCY = REGISTRY._names_to_collectors["http_request_duration_seconds"]
    else:
        REQUEST_LATENCY = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["method", "path"],
        )

    # Request-ID middleware (assign X-Request-ID if not provided)
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    # Logging + metrics middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        rid = getattr(request.state, "request_id", "-")
        adapter = logging.LoggerAdapter(logger, {"request_id": rid})
        adapter.info("request.start", extra={"method": request.method, "path": request.url.path})
        try:
            resp = await call_next(request)
            status = resp.status_code
        except Exception as e:
            status = 500
            adapter.exception("request.exception %s", e)
            raise
        finally:
            elapsed = time.time() - start
            REQUEST_COUNT.labels(method=request.method, path=request.url.path, status_code=str(status)).inc()
            REQUEST_LATENCY.labels(method=request.method, path=request.url.path).observe(elapsed)
            adapter.info("request.end", extra={"status_code": status, "duration_s": elapsed})
        return resp

    # Mount Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.on_event("startup")
    async def startup_event():
        app.state.settings = settings
        app.state.rpc_client = BitcoinRPCClient(
            host=settings.RPC_HOST,
            port=settings.RPC_PORT,
            username=settings.RPC_USER,
            password=settings.RPC_PASSWORD,
            cookie_path=settings.RPC_COOKIE_PATH,
            use_ssl=settings.USE_SSL,
        )
        # init sqlite cache
        data_dir = project_root / "data"
        os.makedirs(data_dir, exist_ok=True)
        app.state.cache = MetricsCache(data_dir / "metrics.db")

        # websocket connection manager
        class ConnectionManager:
            def __init__(self):
                self.active: set[WebSocket] = set()

            async def connect(self, websocket: WebSocket):
                await websocket.accept()
                self.active.add(websocket)

            def disconnect(self, websocket: WebSocket):
                self.active.discard(websocket)

            async def broadcast(self, message: str):
                to_remove = []
                for ws in list(self.active):
                    try:
                        await ws.send_text(message)
                    except Exception:
                        to_remove.append(ws)
                for ws in to_remove:
                    self.active.discard(ws)

        app.state.ws_manager = ConnectionManager()

        # background poller task - pushes metrics to WS and records to cache
        async def poller():
            rpc: BitcoinRPCClient = app.state.rpc_client
            cache: MetricsCache = app.state.cache
            mgr = app.state.ws_manager
            interval = getattr(settings, 'POLL_INTERVAL', 2)
            while True:
                try:
                    info = await rpc.get_blockchain_info()
                    count = await rpc.get_block_count()
                    best = await rpc.get_best_block_hash()
                    mempool = await rpc.get_mempool_info()
                    net = await rpc.get_network_info()
                    ts = int(time.time())
                    # store metrics
                    await cache.insert('Chain Height', ts, float(count or 0))
                    await cache.insert('Mempool Tx', ts, float(mempool.get('size', 0) if isinstance(mempool, dict) else 0))
                    await cache.insert('Connected Peers', ts, float(net.get('connections', 0) if isinstance(net, dict) else 0))

                    # broadcast a compact metric message
                    # include recent blocks in broadcast
                    recent_blocks = []
                    try:
                        for i in range(0, 6):
                            h = await rpc.get_block_hash(count - i)
                            b = await rpc.get_block(h, 1)
                            tx_count = len(b.get('tx', [])) if isinstance(b.get('tx', []), list) else 0
                            recent_blocks.append({'hash': h, 'tx_count': tx_count, 'time': b.get('time')})
                    except Exception:
                        recent_blocks = []

                    msg = {'type':'metric','metrics':{'Chain Height': count, 'Mempool Tx': mempool.get('size') if isinstance(mempool, dict) else 0, 'Connected Peers': net.get('connections') if isinstance(net, dict) else 0}, 'best_block_hash': best, 'recent_blocks': recent_blocks}
                    try:
                        await mgr.broadcast(json.dumps(msg))
                    except Exception:
                        # ignore broadcast errors
                        pass
                except Exception as e:
                    logger.exception('Background poller error')
                await asyncio.sleep(interval)

        # start poller
        app.state._poller_task = asyncio.create_task(poller())
        # Log the effective RPC endpoint (do not log credentials)
        logger.info("RPC endpoint: %s:%s ssl=%s", settings.RPC_HOST, settings.RPC_PORT, settings.USE_SSL)
        # Additional startup diagnostics
        try:
            logger.info("POLL_INTERVAL=%s REDIS_URL_SET=%s", settings.POLL_INTERVAL, bool(getattr(settings, 'REDIS_URL', None)))
        except Exception:
            logger.info("POLL_INTERVAL/REDIS diagnostics not available in settings")

    @app.on_event("shutdown")
    async def shutdown_event():
        rpc: BitcoinRPCClient = app.state.rpc_client
        await rpc.close()
        # cancel background task
        try:
            app.state._poller_task.cancel()
        except Exception:
            pass


    # mount static and include routers (use absolute path so script runs
    # correctly regardless of current working directory)
    app.mount("/static", StaticFiles(directory=str(project_root / "app" / "static")), name="static")

    from app.api.rest import router as rest_router

    app.include_router(rest_router)

    @app.websocket('/ws')
    async def websocket_endpoint(websocket: WebSocket):
        mgr: 'ConnectionManager' = app.state.ws_manager
        await mgr.connect(websocket)
        try:
            while True:
                # keep connection open; server pushes messages
                await websocket.receive_text()
        except WebSocketDisconnect:
            mgr.disconnect(websocket)
        except Exception:
            mgr.disconnect(websocket)

    @app.get("/")
    async def index(request: Request):
        # Render the template via Jinja2Templates (now using a no-cache env).
        # Note: TemplateResponse expects (request, name, context).
        return templates.TemplateResponse(request, "index.html")

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
