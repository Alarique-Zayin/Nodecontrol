import asyncio
import json
from typing import Any, Dict, Optional

import aiohttp


class RPCError(Exception):
    pass


class RPCAuthError(RPCError):
    pass


class RPCConnectionError(RPCError):
    pass


class BitcoinRPCClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8332,
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookie_path: Optional[str] = None,
        use_ssl: bool = False,
        timeout: int = 10,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.cookie_path = cookie_path
        self.use_ssl = use_ssl
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._id = 0
        self._lock = asyncio.Lock()
        self._pending: Dict[str, asyncio.Future] = {}

    @property
    def url(self) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _read_cookie(self) -> Optional[str]:
        if not self.cookie_path:
            return None
        try:
            with open(self.cookie_path, "r") as f:
                return f.read().strip()
        except Exception:
            return None

    async def _request(self, method: str, params: Optional[list] = None) -> Any:
        params = params or []
        payload = {"jsonrpc": "1.0", "id": str(self._id), "method": method, "params": params}
        self._id += 1
        session = await self._ensure_session()
        headers = {"Content-Type": "application/json"}

        auth = None
        if self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)
        else:
            # cookie auth via BasicAuth username is empty string and password is cookie
            cookie = None
            if self.cookie_path:
                try:
                    with open(self.cookie_path, "r") as f:
                        cookie = f.read().strip()
                except Exception:
                    cookie = None
            if cookie:
                auth = aiohttp.BasicAuth("", cookie)

        try:
            async with session.post(self.url, data=json.dumps(payload), headers=headers, auth=auth, timeout=self.timeout) as resp:
                text = await resp.text()
                if resp.status == 401:
                    raise RPCAuthError("Unauthorized to RPC")
                if resp.status >= 500:
                    raise RPCConnectionError(f"Server error: {resp.status}")
                if resp.status != 200:
                    raise RPCConnectionError(f"Unexpected status: {resp.status} - {text}")
                data = json.loads(text)
                if data.get("error"):
                    raise RPCError(data["error"])
                return data.get("result")
        except asyncio.TimeoutError:
            raise RPCConnectionError("RPC request timed out")
        except aiohttp.ClientError as e:
            raise RPCConnectionError(str(e))

    async def _with_retries(self, method: str, params: Optional[list] = None, attempts: int = 3) -> Any:
        backoff = 0.5
        for attempt in range(attempts):
            try:
                return await self._request(method, params)
            except (RPCConnectionError,) as e:
                if attempt + 1 == attempts:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

    # Convenience wrappers
    async def get_blockchain_info(self) -> Dict[str, Any]:
        return await self._with_retries("getblockchaininfo")

    async def get_block_count(self) -> int:
        return await self._with_retries("getblockcount")

    async def get_best_block_hash(self) -> str:
        return await self._with_retries("getbestblockhash")

    async def get_mempool_info(self) -> Dict[str, Any]:
        return await self._with_retries("getmempoolinfo")

    async def get_network_info(self) -> Dict[str, Any]:
        return await self._with_retries("getnetworkinfo")

    async def get_peer_info(self) -> Any:
        return await self._with_retries("getpeerinfo")

