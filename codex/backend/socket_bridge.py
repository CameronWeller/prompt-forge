"""Adapt desktop JSONL stdio to the private app-server Unix WebSocket endpoint."""
import base64
import hashlib
import os
import socket
import struct
import sys
import threading

MAX_MESSAGE = 256 * 1024 * 1024


def read_exact(stream, count):
    data = stream.read(count)
    if len(data) != count:
        raise EOFError("Shared connection closed")
    return data


def client_frame(payload, opcode=1):
    length = len(payload)
    if length > MAX_MESSAGE:
        raise ValueError("Message exceeds bridge limit")
    header = bytes([0x80 | opcode])
    if length < 126:
        header += bytes([0x80 | length])
    elif length < 65536:
        header += bytes([0x80 | 126]) + struct.pack("!H", length)
    else:
        header += bytes([0x80 | 127]) + struct.pack("!Q", length)
    mask = os.urandom(4)
    return header + mask + bytes(value ^ mask[index % 4] for index, value in enumerate(payload))


def run(path):
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(10)
    connection.connect(str(path))
    stream = connection.makefile("rb")
    lock = threading.Lock()
    failures = []
    try:
        nonce = base64.b64encode(os.urandom(16)).decode("ascii")
        connection.sendall(("GET /rpc HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                            "Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n"
                            "Sec-WebSocket-Key: " + nonce + "\r\n\r\n").encode("ascii"))
        status = stream.readline(8192)
        if not status.startswith(b"HTTP/1.1 101 "):
            raise ConnectionError("Shared WebSocket handshake failed")
        headers = {}
        total = len(status)
        while True:
            line = stream.readline(8192)
            total += len(line)
            if not line or total > 65536:
                raise ConnectionError("Invalid shared WebSocket response")
            if line == b"\r\n":
                break
            key, value = line.split(b":", 1)
            headers[key.strip().lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        if headers.get(b"sec-websocket-accept") != expected:
            raise ConnectionError("Shared WebSocket handshake validation failed")
        connection.settimeout(None)

        def send(payload, opcode=1):
            with lock:
                connection.sendall(client_frame(payload, opcode))

        def input_loop():
            pending = bytearray()
            try:
                while True:
                    chunk = os.read(sys.stdin.fileno(), 65536)
                    if not chunk:
                        if pending.strip():
                            send(bytes(pending).rstrip(b"\r\n"))
                        break
                    pending.extend(chunk)
                    while b"\n" in pending:
                        line, _, rest = pending.partition(b"\n")
                        pending = bytearray(rest)
                        if line.strip():
                            send(bytes(line).rstrip(b"\r"))
                    if len(pending) > MAX_MESSAGE:
                        raise ValueError("Message exceeds bridge limit")
            except Exception:
                failures.append(True)
            finally:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        threading.Thread(target=input_loop, daemon=True).start()
        fragments = None
        while True:
            try:
                head = read_exact(stream, 2)
            except EOFError:
                break
            final, opcode = bool(head[0] & 0x80), head[0] & 0x0F
            if head[0] & 0x70 or head[1] & 0x80:
                raise ValueError("Unexpected shared WebSocket frame")
            length = head[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", read_exact(stream, 2))[0]
            elif length == 127:
                length = struct.unpack("!Q", read_exact(stream, 8))[0]
            if length > MAX_MESSAGE or (opcode >= 8 and (length > 125 or not final)):
                raise ValueError("Invalid shared WebSocket frame length")
            payload = read_exact(stream, length)
            if opcode == 8:
                break
            if opcode == 9:
                send(payload, 10)
                continue
            if opcode == 10:
                continue
            if opcode == 1 and fragments is None:
                fragments = bytearray(payload)
            elif opcode == 0 and fragments is not None:
                fragments.extend(payload)
            else:
                raise ValueError("Unexpected shared WebSocket message")
            if len(fragments) > MAX_MESSAGE:
                raise ValueError("Message exceeds bridge limit")
            if final:
                fragments.decode("utf-8")
                sys.stdout.buffer.write(fragments + b"\n")
                sys.stdout.buffer.flush()
                fragments = None
        if failures:
            raise ConnectionError("Shared input stream failed")
    finally:
        stream.close()
        connection.close()
