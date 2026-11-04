"""Bounded Modbus TCP listener. No model code or outbound client is used.

Validation order is function, quantity/value, address, execution. The MBAP
stream parser accepts fragmented and coalesced frames, drops malformed frames,
and bounds each connection's buffered data and idle lifetime.
"""

import asyncio
import struct
import time

from .register_map import area_rows


class ProtocolException(Exception):
    """Internal signal for a Modbus exception code and audit reason."""

    def __init__(self, code, reason):
        self.code = code
        self.reason = reason


class ModbusDecoy:
    def __init__(self, sim, log, device_id, host="127.0.0.1", port=5020,
                 unit_ids=(0, 1, 255), max_connections=32, idle_timeout_s=60.0):
        self.sim, self.log = sim, log
        self.device_id = dict(device_id)
        self.host, self.port = host, port
        self.unit_ids = frozenset(unit_ids)
        self.max_connections = max_connections
        self.idle_timeout_s = idle_timeout_s
        self.server = None
        self._loop = None
        self._writers = set()

    async def serve(self) -> None:
        """Bind the inbound listener and run until close or cancellation."""
        self._loop = asyncio.get_running_loop()
        self.server = await asyncio.start_server(self._client, self.host, self.port, limit=65542)
        self.port = self.server.sockets[0].getsockname()[1]
        async with self.server:
            await self.server.serve_forever()

    def close(self) -> None:
        """Stop listening and release existing connections, from any thread."""
        def shutdown():
            if self.server:
                self.server.close()
            for writer in tuple(self._writers):
                writer.close()
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(shutdown)

    async def _client(self, reader, writer):
        if len(self._writers) >= self.max_connections:
            writer.close()
            await writer.wait_closed()
            return
        self._writers.add(writer)
        buffer = bytearray()
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), self.idle_timeout_s)
                if not chunk:
                    break
                buffer.extend(chunk)
                while len(buffer) >= 7:
                    transaction, protocol, length, unit = struct.unpack_from(">HHHB", buffer)
                    if length < 2:
                        del buffer[0]
                        continue
                    # Invalid headers are scanned a byte at a time to recover
                    # after an undersized frame left trailing PDU bytes.
                    if protocol and length > 254:
                        del buffer[0]
                        continue
                    frame_size = 6 + length
                    if len(buffer) < frame_size:
                        break
                    pdu = bytes(buffer[7:frame_size])
                    del buffer[:frame_size]
                    if protocol != 0 or length > 254:
                        continue
                    # A fixed-size PDU cut short by MBAP cannot be executed.
                    if pdu[0] in (1, 2, 3, 4, 5, 6) and len(pdu) != 5:
                        continue
                    started = time.monotonic()
                    reply, reason, detail = self._dispatch(unit, pdu)
                    frame = struct.pack(">HHHB", transaction, 0, len(reply) + 1, unit) + reply
                    self._log(writer, pdu, detail, reason, len(frame), started)
                    writer.write(frame)
                    await writer.drain()
        except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError):
            pass
        finally:
            self._writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    def _values(self, area):
        snapshot = self.sim.snapshot()
        values = []
        active = {alarm["tag"] for alarm in snapshot["alarms"] if alarm["active"]}
        for row in area_rows(area):
            if row.point.endswith("_alarm_active"):
                value = row.point.removesuffix("_alarm_active") in active
            else:
                value = snapshot[row.point]
            if row.words == 2:
                number = min(0xFFFFFFFF, max(0, round(value * 10)))
                values.extend((number >> 16, number & 0xFFFF))
            elif row.scale in {"bit", "1 or 2"}:
                values.append(int(value))
            else:
                values.append(min(65535, max(0, round(value * int(row.scale[1:])))))
        return values

    @staticmethod
    def _range(address, quantity, size):
        if address + quantity > size:
            raise ProtocolException(2, "unknown_point")

    def _dispatch(self, unit, pdu):
        """Return PDU, audit reason, and complete Modbus schema fields."""
        fc = pdu[0]
        detail = dict(unit_id=unit, function_code=fc, address=None, quantity=None, values=[], exception_code=None)
        try:
            if unit not in self.unit_ids:
                raise ProtocolException(11, "unit_id")
            if fc not in (1, 2, 3, 4, 5, 6, 15, 16, 43):
                raise ProtocolException(1, "unsupported_function")
            if fc == 43:
                if len(pdu) != 4 or pdu[1] != 14 or pdu[2] not in (1, 2, 3, 4):
                    raise ProtocolException(3, "bad_value")
                if pdu[3] > 2:
                    raise ProtocolException(2, "unknown_point")
                objects = [self.device_id[key].encode("ascii") for key in
                           ("VendorName", "ProductCode", "MajorMinorRevision")]
                start = pdu[3]
                selected = range(start, start + 1) if pdu[2] == 4 else range(start, 3)
                data = b"".join(bytes((i, len(objects[i]))) + objects[i] for i in selected)
                return bytes((43, 14, pdu[2], 1, 0, 0, len(selected))) + data, "ok", detail
            if len(pdu) < 5:
                raise ProtocolException(3, "bad_value")
            address, argument = struct.unpack_from(">HH", pdu, 1)
            detail.update(address=address, quantity=argument if fc in (1, 2, 3, 4, 15, 16) else 1)
            if fc in (1, 2, 3, 4):
                limit = 2000 if fc < 3 else 125
                if len(pdu) != 5 or not 1 <= argument <= limit:
                    raise ProtocolException(3, "bad_value")
                area = {1: "Coils", 2: "Discrete inputs", 3: "Holding registers", 4: "Input registers"}[fc]
                values = self._values(area)
                self._range(address, argument, len(values))
                result = values[address:address + argument]
                if fc < 3:
                    packed = bytearray((argument + 7) // 8)
                    for i, value in enumerate(result):
                        packed[i // 8] |= bool(value) << (i % 8)
                    data = bytes(packed)
                else:
                    data = struct.pack(">" + "H" * argument, *result)
                return bytes((fc, len(data))) + data, "ok", detail
            if fc in (5, 6):
                detail["values"] = [argument]
                if len(pdu) != 5 or (fc == 5 and argument not in (0, 0xFF00)):
                    raise ProtocolException(3, "bad_value")
                values = [bool(argument)] if fc == 5 else [argument / 10]
                quantity = 1
            else:
                quantity = argument
                limit = 1968 if fc == 15 else 123
                count = (quantity + 7) // 8 if fc == 15 else quantity * 2
                if not 1 <= quantity <= limit or len(pdu) < 6 or pdu[5] != count or len(pdu) != 6 + count:
                    raise ProtocolException(3, "bad_value")
                values = ([bool(pdu[6 + i // 8] & (1 << (i % 8))) for i in range(quantity)] if fc == 15 else
                          [number / 10 for number in struct.unpack(">" + "H" * quantity, pdu[6:])])
                detail["values"] = [int(value) if fc == 15 else round(value * 10) for value in values]
            rows = area_rows("Coils" if fc in (5, 15) else "Holding registers")
            self._range(address, quantity, len(rows))
            updates = {row.point: value for row, value in zip(rows[address:address + quantity], values)}
            result = self.sim.write_many(updates, "modbus")
            if not result.ok:
                raise ProtocolException(3, result.reason)
            return pdu[:5], "ok", detail
        except ProtocolException as error:
            detail["exception_code"] = error.code
            return bytes((fc | 0x80, error.code)), error.reason, detail
        except Exception:
            detail["exception_code"] = 4
            return bytes((fc | 0x80, 4)), "internal_failure", detail

    def _log(self, writer, pdu, detail, reason, size, started):
        src = writer.get_extra_info("peername")
        self.log.write({"surface": "modbus", "src": src[0], "src_port": src[1],
                        "modbus": detail, "severity": "high" if pdu[0] in (5, 6, 15, 16) else "notice",
                        "reason": reason, "response": {"bytes": size,
                        "latency_ms": (time.monotonic() - started) * 1000}})
