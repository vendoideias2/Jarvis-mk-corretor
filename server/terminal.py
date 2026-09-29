"""
~/nexora/server/terminal.py — Shell interativo do NEXORA 3.0.
"""

import subprocess
import time


def register(route, ApiError):
    @route("POST", "/api/terminal")
    def handle_terminal(req, query, body):
        if not body:
            raise ApiError(400, "Dados obrigatórios")
        
        command = body.get("command", "").strip()
        if not command:
            raise ApiError(400, "Comando não pode ser vazio")

        try:
            res = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "ok": True,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "exit_code": 124,
                "stdout": "",
                "stderr": "Comando excedeu o tempo limite de 30s."
            }
        except Exception as e:
            return {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e)
            }
