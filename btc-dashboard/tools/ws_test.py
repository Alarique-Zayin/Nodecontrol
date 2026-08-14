import asyncio
import json
import sys

import websockets

async def run():
    # obtain short-lived token from server
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:8000/ws-token') as r:
                if r.status != 200:
                    print('token endpoint error', r.status)
                    return
                jd = await r.json()
                token = jd.get('token')
        url = 'ws://127.0.0.1:8000/ws' + (('?token='+token) if token else '')
        async with websockets.connect(url) as ws:
            print('connected')
            for i in range(3):
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                print('MSG', msg)
    except Exception as e:
        print('error', e)

if __name__ == '__main__':
    asyncio.run(run())
