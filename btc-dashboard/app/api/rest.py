from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

router = APIRouter(prefix="/api/v1")


@router.get("/status")
async def status(request: Request):
    rpc = request.app.state.rpc_client
    logger: logging.Logger = request.app.state.logger if hasattr(request.app.state, "logger") else logging.getLogger("btc-dashboard")
    try:
        info = await rpc.get_blockchain_info()
        count = await rpc.get_block_count()
        best = await rpc.get_best_block_hash()
        mempool = await rpc.get_mempool_info()
        net = await rpc.get_network_info()
        # build a small recent blocks feed (last 6)
        recent = []
        try:
            for i in range(0, 6):
                h = await rpc.get_block_hash(count - i)
                b = await rpc.get_block(h, 1)
                tx_count = len(b.get('tx', [])) if isinstance(b.get('tx', []), list) else 0
                recent.append({
                    'hash': h,
                    'tx_count': tx_count,
                    'time': b.get('time'),
                })
        except Exception:
            # if RPC calls fail for blocks, ignore recent feed
            recent = []

        return JSONResponse(
            {
                "block_count": count,
                "best_block_hash": best,
                "chain": info.get("chain"),
                "headers": info.get("headers"),
                "difficulty": info.get("difficulty"),
                "mempool": mempool,
                "network": net,
                "peers": net.get('connections') if isinstance(net, dict) else None,
                "recent_blocks": recent,
            }
        )
    except Exception as e:
        # Include request id in logs if available
        rid = getattr(request.state, "request_id", None)
        if rid:
            logger = logging.LoggerAdapter(logger, {"request_id": rid})
        logger.exception("Error in /api/v1/status")
        return JSONResponse({"error": str(e), "type": type(e).__name__, "request_id": rid}, status_code=500)


@router.get("/health")
async def health(request: Request):
    """Lightweight health check. Returns 200 when RPC responds, 503 otherwise."""
    rpc = request.app.state.rpc_client
    logger: logging.Logger = request.app.state.logger if hasattr(request.app.state, "logger") else logging.getLogger("btc-dashboard")
    try:
        # Call a cheap RPC method to validate connectivity
        await rpc.get_block_count()
        return JSONResponse({"status": "ok"}, status_code=200)
    except Exception as e:
        logger.warning("Health check failed: %s", e)
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)
