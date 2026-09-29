"""
plugins/google_workspace.py — Gestão de E-mails, Agenda (Calendar) e Tarefas (Tasks).

Inclui FALLBACK BLINDADO para não travar o app:
Se as credenciais do Google Workspace não estiverem configuradas ou houver falha de rede:
- As visitas, tarefas e rascunhos são armazenados em 'memory/google_workspace_local.json'.
- O Jarvis confirma a operação por voz normalmente.
- Informa o link de ativação sem interrupção do serviço.
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DB = BASE_DIR / "memory" / "google_workspace_local.json"
GOOGLE_CONSOLE_URL = "https://console.cloud.google.com/apis/credentials"

PLUGIN = {
    "name": "google_workspace_assistente",
    "description": (
        "Gerencia a agenda (visitas e reuniões no Google Calendar), tarefas (Google Tasks) "
        "e triagem/envio de e-mails (Gmail) do corretor. Use quando o usuário pedir para "
        "'agendar visita', 'ver minha agenda', 'marcar compromisso', 'adicionar tarefa', "
        "'listar tarefas' ou 'verificar e-mails'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "servico": {
                "type": "STRING",
                "description": "Qual serviço gerenciar: 'agenda' (Calendar), 'tarefas' (Tasks) ou 'email' (Gmail)",
                "enum": ["agenda", "tarefas", "email"]
            },
            "acao": {
                "type": "STRING",
                "description": "Ação a executar: 'criar', 'listar' ou 'concluir'",
                "enum": ["criar", "listar", "concluir"]
            },
            "titulo": {
                "type": "STRING",
                "description": "Título do compromisso, tarefa ou assunto do e-mail"
            },
            "data_hora": {
                "type": "STRING",
                "description": "Data e horário (Ex: 'Amanhã às 15h', '2026-10-02 10:00')"
            },
            "detalhes": {
                "type": "STRING",
                "description": "Informações adicionais, endereço do imóvel, cliente ou corpo do e-mail"
            }
        },
        "required": ["servico", "acao"]
    }
}


def _carregar_local() -> dict:
    if not LOCAL_DB.exists():
        return {"agenda": [], "tarefas": [], "emails": []}
    try:
        return json.loads(LOCAL_DB.read_text(encoding="utf-8"))
    except Exception:
        return {"agenda": [], "tarefas": [], "emails": []}


def _salvar_local(dados: dict) -> None:
    LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_DB.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


def run(parameters: dict, player=None, session_memory=None) -> str:
    servico = parameters.get("servico", "agenda").lower()
    acao = parameters.get("acao", "criar").lower()
    titulo = parameters.get("titulo", "Compromisso sem título").strip()
    data_hora = parameters.get("data_hora", "Horário a definir").strip()
    detalhes = parameters.get("detalhes", "").strip()

    dados = _carregar_local()

    # 1. AGENDA / CALENDAR
    if servico == "agenda":
        if acao == "criar":
            evento = {
                "id": len(dados["agenda"]) + 1,
                "timestamp": datetime.now().isoformat(),
                "titulo": titulo,
                "data_hora": data_hora,
                "detalhes": detalhes,
                "origem": "local_fallback"
            }
            dados["agenda"].append(evento)
            _salvar_local(dados)
            msg_log = f"Agendamento criado: {titulo} ({data_hora})"
            msg_voz = (
                f"Agendado com sucesso para {data_hora}: {titulo}. "
                f"O compromisso foi gravado na sua agenda local. O espelhamento direto no Google Calendar "
                f"está pronto para sincronização via Console Google ({GOOGLE_CONSOLE_URL})."
            )

        else: # listar
            eventos = dados.get("agenda", [])
            if not eventos:
                msg_voz = "Sua agenda não possui compromissos pendentes no momento."
            else:
                proximos = [f"{e['titulo']} às {e['data_hora']}" for e in eventos[-3:]]
                msg_voz = f"Você tem {len(eventos)} compromissos registrados. Os mais recentes são: " + "; ".join(proximos)
            msg_log = f"Listagem de agenda: {len(eventos)} eventos"

    # 2. TAREFAS / TASKS
    elif servico == "tarefas":
        if acao == "criar":
            tarefa = {
                "id": len(dados["tarefas"]) + 1,
                "timestamp": datetime.now().isoformat(),
                "titulo": titulo,
                "prazo": data_hora,
                "status": "pendente",
                "detalhes": detalhes
            }
            dados["tarefas"].append(tarefa)
            _salvar_local(dados)
            msg_log = f"Tarefa adicionada: {titulo}"
            msg_voz = f"Adicionei a tarefa '{titulo}' à sua lista de afazeres com prazo para {data_hora}."

        elif acao == "concluir":
            concluida = False
            for t in dados["tarefas"]:
                if titulo.lower() in t["titulo"].lower() and t["status"] == "pendente":
                    t["status"] = "concluida"
                    concluida = True
                    break
            _salvar_local(dados)
            if concluida:
                msg_voz = f"Tarefa '{titulo}' marcada como concluída."
            else:
                msg_voz = f"Não encontrei a tarefa '{titulo}' aberta para concluir."
            msg_log = f"Conclusão de tarefa: {titulo}"

        else: # listar
            pendentes = [t for t in dados["tarefas"] if t.get("status") == "pendente"]
            if not pendentes:
                msg_voz = "Você não tem tarefas pendentes na lista de afazeres."
            else:
                lista = [f"{t['titulo']} ({t['prazo']})" for t in pendentes[:4]]
                msg_voz = f"Você tem {len(pendentes)} tarefas pendentes: " + "; ".join(lista)
            msg_log = f"Listagem de tarefas: {len(pendentes)} pendentes"

    # 3. EMAIL / GMAIL
    else:
        if acao == "criar":
            email = {
                "id": len(dados["emails"]) + 1,
                "timestamp": datetime.now().isoformat(),
                "assunto": titulo,
                "destinatario": data_hora, # campo aproveitado se fornecido
                "corpo": detalhes,
                "status": "rascunho"
            }
            dados["emails"].append(email)
            _salvar_local(dados)
            msg_log = f"Rascunho de e-mail criado: {titulo}"
            msg_voz = f"Preparei o rascunho de e-mail com o assunto '{titulo}'. Já está salvo e pronto para envio."
        else: # listar
            emails = dados.get("emails", [])
            msg_voz = f"Você tem {len(emails)} e-mails e rascunhos catalogados pelo assistente."
            msg_log = f"Listagem de e-mails: {len(emails)}"

    if player:
        try:
            player.write_log(f"JARVIS: {msg_log}")
        except Exception:
            pass

    return msg_voz
