"""
~/nexora/server/chat.py — Conversa direta com qualquer agente especialista da frota.
"""

import subprocess
import time
import store


def register(route, ApiError):
    @route("GET", "/api/chat")
    def handle_get_chat(req, query, body):
        agent = query.get("agent", "executor").lower()
        rows = store.query(
            "SELECT * FROM chat_history WHERE agent = ? ORDER BY at ASC LIMIT 100",
            (agent,)
        )
        return {"ok": True, "agent": agent, "messages": rows}

    @route("POST", "/api/chat")
    def handle_post_chat(req, query, body):
        if not body:
            raise ApiError(400, "Corpo da mensagem obrigatório")
        
        agent = body.get("agent", "executor").lower()
        text = body.get("text", "").strip()
        if not text:
            raise ApiError(400, "Texto da mensagem não pode ser vazio")

        now = time.time()
        store.execute(
            "INSERT INTO chat_history (agent, session_name, role, text, at) VALUES (?, ?, ?, ?, ?)",
            (agent, "default", "user", text, now)
        )

        # Invoca o agente via hermes CLI
        profile_flag = ["-p", agent] if agent != "executor" else []
        start_time = time.time()
        reply_text = ""

        # 1. Tenta via hermes CLI se instalado
        profile_flag = ["-p", agent] if agent != "executor" else []
        cmd = ["hermes", *profile_flag, "chat", "-q", text, "-Q"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and res.stdout.strip():
                reply_text = res.stdout.strip()
        except Exception:
            pass

        # 2. Fallback direto via FreeLLM API (model: auto)
        if not reply_text:
            prompts = {
                "executor": "Você é o EXECUTOR, orquestrador da frota NEXORA. Traga planos e resultados claros, objetivos e de alta autoridade para o corretor de imóveis.",
                "research": "Você é o RESEARCH, pesquisador imobiliário especialista em mercado, bairros, valores de m² e histórico de empreendimentos.",
                "writer": "Você é o CONTENT WRITER, especialista oficial em redação no padrão Vendo Casas. Escreva copies persuasivas, moeda em R$ XXX.XXX,00 e termos imobiliários elegantes.",
                "developer": "Você é o DEVELOPER, especialista em automação e engenharia de software da agência. Cuide de integrações, APIs e scripts técnicos."
            }
            system_prompt = prompts.get(agent, prompts["executor"])
            try:
                import urllib.request
                import json
                req_data = json.dumps({
                    "model": "auto",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ]
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    "https://free.vendoideias.com/v1/chat/completions",
                    data=req_data,
                    headers={
                        "Authorization": "Bearer freellmapi-d647880677bf09c503f5bbea21eebba86e5a2b298727abd2",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    reply_text = resp_json["choices"][0]["message"]["content"].strip()
            except Exception as e:
                reply_text = f"Erro na conexão com FreeLLM ({e})."

        elapsed_ms = int((time.time() - start_time) * 1000)

        end_now = time.time()
        store.execute(
            "INSERT INTO chat_history (agent, session_name, role, text, at, ms) VALUES (?, ?, ?, ?, ?, ?)",
            (agent, "default", "assistant", reply_text, end_now, elapsed_ms)
        )

        return {
            "ok": True,
            "agent": agent,
            "reply": reply_text,
            "elapsed_ms": elapsed_ms
        }
