import asyncio
import websockets

url = "ws://127.0.0.1:8000/ws/chat/1/?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQ0NDM4NDgxLCJpYXQiOjE3NDQzNTIwODEsImp0aSI6IjMzYzQ5NTZmNzkwMjQ3OGZiMzk5ODYwZTI1ODIxZDNkIiwidXNlcl9pZCI6IjIiLCJlbWFpbCI6bnVsbH0.BpxYewR_Fdc1qmgCPL7rmykggMx_9i0PNTJmC5XmP4A"
async def listen():
    async with websockets.connect(url) as ws:
        print("✅ Connected to WebSocket")
        while True:
            msg = await ws.recv()
            print("📨 Message:", msg)

asyncio.run(listen())
