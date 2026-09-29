"""
~/nexora/server/server.py — Servidor HTTP Central do NEXORA 3.0.
Python 3 standard library only.
"""

import sys
sys.modules.setdefault("server", sys.modules["__main__"])

import gzip
import json
import os
import time
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

START_TIME = time.time()
BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_FILE = BASE_DIR / "dashboard.html"

MAX_BODY_BYTES = 30 * 1024 * 1024  # 30 MB
RAW_BODY_PATHS = {"/api/transcribe"}

ROUTES = {}  # (METHOD, path) -> handler


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Raw:
    def __init__(self, body: bytes, content_type: str = "application/octet-stream", headers: dict | None = None):
        self.body = body
        self.content_type = content_type
        self.headers = headers or {}


class Stream:
    def __init__(self, generator, content_type: str = "text/event-stream"):
        self.generator = generator
        self.content_type = content_type


def route(method: str, path: str):
    def decorator(fn):
        ROUTES[(method.upper(), path)] = fn
        return fn
    return decorator


@route("GET", "/api/ping")
def handle_ping(req, query, body):
    return {"ok": True, "uptime_s": round(time.time() - START_TIME, 2)}


@route("GET", "/")
@route("GET", "/index.html")
def handle_index(req, query, body):
    if not DASHBOARD_FILE.exists():
        # Fallback elegante caso o dashboard.html ainda não tenha sido baixado
        html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>NEXORA 3.0 — Mission Control</title>
<style>
body { background: #0c0b0a; color: #ece8e1; font-family: system-ui, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
.card { background: #161514; border: 1px solid #2d2926; padding: 40px; border-radius: 12px; max-width: 600px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
h1 { color: #d4a359; margin-top: 0; }
p { line-height: 1.6; color: #a8a29e; }
.badge { display: inline-block; background: #222; border: 1px solid #333; padding: 4px 12px; border-radius: 20px; font-size: 13px; margin: 6px; color: #22c55e; }
</style>
</head>
<body>
<div class="card">
  <h1>☤ NEXORA 3.0</h1>
  <p><strong>Fleet Mission Control Backend Ativo na porta 8800.</strong></p>
  <p>Todos os 4 agentes especialistas estão online e respondendo via FreeLLM.</p>
  <div>
    <span class="badge">● EXECUTOR</span>
    <span class="badge">● RESEARCH</span>
    <span class="badge">● CONTENT WRITER</span>
    <span class="badge">● DEVELOPER</span>
  </div>
  <p style="font-size: 13px; margin-top: 25px; color: #78716c;">Coloque o arquivo template em <code>~/nexora/dashboard.html</code> para carregar o cockpit completo.</p>
</div>
</body>
</html>"""
        return Raw(html.encode("utf-8"), "text/html; charset=utf-8")

    data = DASHBOARD_FILE.read_bytes()
    stat = DASHBOARD_FILE.stat()
    etag = f'"{stat.st_mtime}-{stat.st_size}"'
    
    if req.headers.get("If-None-Match") == etag:
        raise ApiError(304, "Not Modified")

    headers = {
        "ETag": etag,
        "Cache-Control": "no-cache"
    }

    # Gzip se aceito pelo cliente
    if "gzip" in req.headers.get("Accept-Encoding", "").lower():
        data = gzip.compress(data)
        headers["Content-Encoding"] = "gzip"

    return Raw(data, "text/html; charset=utf-8", headers)


class NexoraRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silencia logs repetitivos normais do HTTP
        pass

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)
        flat_query = {k: v[0] for k, v in query_params.items()}

        # 1. Verifica existência de rota
        handler = ROUTES.get((method, path))
        if not handler:
            # Verifica se rota existe sob outro método (405)
            allowed = [m for m, p in ROUTES if p == path]
            if allowed:
                self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
                self.send_header("Allow", ", ".join(allowed))
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "Method Not Allowed"}).encode("utf-8"))
                return
            
            # Não existe em nenhum método (404)
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": f"Path '{path}' not found"}).encode("utf-8"))
            return

        # 2. Leitura e validação de body para POST
        body = None
        if method == "POST":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_BODY_BYTES:
                self.send_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                self.send_header("Content-Type", "application/json")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "Payload exceeds 30 MB limit"}).encode("utf-8"))
                self.close_connection = True
                return

            raw_bytes = self.rfile.read(content_length) if content_length > 0 else b""

            if path in RAW_BODY_PATHS:
                body = raw_bytes
            else:
                if raw_bytes:
                    try:
                        parsed_json = json.loads(raw_bytes.decode("utf-8"))
                        if not isinstance(parsed_json, dict):
                            self._send_error(400, "JSON body must be an object")
                            return
                        body = parsed_json
                    except json.JSONDecodeError:
                        self._send_error(400, "Invalid JSON payload")
                        return
                else:
                    body = {}

        # 3. Execução do Handler
        try:
            result = handler(self, flat_query, body)
            if isinstance(result, Raw):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", result.content_type)
                self.send_header("Content-Length", str(len(result.body)))
                for hk, hv in result.headers.items():
                    self.send_header(hk, hv)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(result.body)
            elif isinstance(result, Stream):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", result.content_type)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                for chunk in result.generator:
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8")
                    self.wfile.write(chunk)
                    self.wfile.flush()
            else:
                if isinstance(result, dict) and "ok" not in result:
                    result["ok"] = True
                payload_bytes = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload_bytes)

        except ApiError as e:
            self._send_error(e.status, e.message)
        except Exception as e:
            traceback.print_exc()
            self._send_error(500, f"Internal server error: {e}")

    def _send_error(self, status: int, message: str):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": False, "error": message}).encode("utf-8"))


def _load_modules():
    import roster
    modules = (
        "settings", "avatars", "chat", "voice", "missions", "workforce",
        "cron", "docs", "health", "traffic", "files", "terminal", "models"
    )
    for mod_name in modules:
        try:
            mod = __import__(mod_name)
            if hasattr(mod, "register"):
                mod.register(route, ApiError)
        except ModuleNotFoundError:
            pass
        except Exception as e:
            print(f"[NEXORA] Erro ao carregar módulo {mod_name}: {e}")


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8800))
    _load_modules()
    try:
        server = ThreadingHTTPServer((host, port), NexoraRequestHandler)
        print(f"[NEXORA] Servidor ativo em http://{host}:{port} ({len(ROUTES)} rotas registradas)")
        server.serve_forever()
    except OSError as e:
        print(f"[NEXORA] Porta {port} já está em uso ou inacessível: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
