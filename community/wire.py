"""Actual fixed loopback Modbus exchanges; no request-selected target exists."""
import socket
import struct
import time


def exchange(port, pdu, deadline):
    """Validate one complete response, including exception replies and MBAP."""
    remaining = deadline-time.monotonic()
    if remaining <= 0:
        raise TimeoutError('action deadline exhausted')
    with socket.create_connection(('127.0.0.1',port),timeout=min(.15,remaining)) as connection:
        connection.settimeout(max(.001,deadline-time.monotonic()))
        connection.sendall(struct.pack('>HHHB',1,0,len(pdu)+1,1)+pdu)
        def receive(count):
            data = b''
            while len(data) < count:
                remaining = deadline-time.monotonic()
                if remaining <= 0: raise TimeoutError('action deadline exhausted')
                connection.settimeout(remaining)
                part = connection.recv(count-len(data))
                if not part: raise ConnectionError('incomplete protocol reply')
                data += part
            return data
        header = receive(7)
        transaction, protocol, length, unit = struct.unpack('>HHHB',header)
        if (transaction,protocol,unit) != (1,0,1) or not 2 <= length <= 254:
            raise ValueError('invalid protocol framing')
        reply = receive(length-1)
        if reply[0] not in (pdu[0],pdu[0]|128): raise ValueError('unexpected function')
        return reply


def stop_and_readback(port, deadline):
    """Send FC5 off, then independently reconnect and read FC1 off-bit state."""
    write = exchange(port,struct.pack('>BHH',5,1,0),deadline)
    read = exchange(port,struct.pack('>BHH',1,1,1),deadline)
    if write != struct.pack('>BHH',5,1,0) or read != b'\x01\x01\x00':
        raise ValueError('write/readback did not confirm off')
    return {'write_function':5,'address':1,'written_value':0,
            'write_reply_hex':write.hex(),'read_function':1,'read_reply_hex':read.hex(),
            'independent_read_connection':True,'off_bit_confirmed':True}


def rejected_write(port, deadline):
    """A complete FC16 request with stop below start must reject atomically."""
    pdu = struct.pack('>BHHBHH',16,0,2,4,280,270)
    reply = exchange(port,pdu,deadline)
    if reply != b'\x90\x03': raise ValueError('expected value rejection')
    return {'function_code':16,'address':0,'values':[280,270],
            'exception_code':3,'reply_hex':reply.hex()}
