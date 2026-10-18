"""Real pinned TCP transport against loopback peer, NOT a SolarEdge hardware test.
Confirms timeout/disconnect/invalid response do not replay an uncertain write.
Device-busy responses can retry in tmodbus; those are explicit pre-write refusals.
"""
import asyncio
from importlib.metadata import version
from modbus_connection.tmodbus import ModbusConnection
from modbus_connection import ModbusTcpParams

async def case(kind):
    frames=[];tasks=set()
    async def handle(reader,writer):
        tasks.add(asyncio.current_task())
        try:
            while True:
                header=await reader.readexactly(7)
                body=await reader.readexactly(int.from_bytes(header[4:6],'big')-1)
                frames.append(header+body)
                if kind=='disconnect':break
                if kind=='invalid':
                    # Wrong function code response; cannot infer rejection.
                    writer.write(header[:4]+b'\x00\x02'+header[6:7]+b'\x03');await writer.drain()
                # timeout: accept a write and send no ACK (ambiguous execution).
        except (asyncio.IncompleteReadError,ConnectionError):pass
        finally:
            writer.close();await writer.wait_closed();tasks.discard(asyncio.current_task())
    server=await asyncio.start_server(handle,'127.0.0.1',0)
    conn=ModbusConnection(ModbusTcpParams('127.0.0.1',server.sockets[0].getsockname()[1]),timeout=.08)
    try:
        try:await conn.for_unit(1).write_register(10,5)
        except Exception:pass
        else:raise AssertionError('ambiguous test unexpectedly succeeded')
        await asyncio.sleep(.15)
        assert len(frames)==1,(kind,len(frames))
        print(kind+': one request, no replay PASS')
    finally:
        await conn.disconnect();server.close();await server.wait_closed()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)

async def main():
    assert version('modbus-connection')=='4.10.0'
    assert version('tmodbus')=='0.6.1'
    for kind in ('timeout','disconnect','invalid'):await case(kind)
asyncio.run(main())
