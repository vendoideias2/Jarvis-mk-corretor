"""
plugins/postagens_vendocasas.py — Gerador de Postagens Padrão Vendo Casas para o Jarvis Corretor.
Segue rigorosamente as regras determinísticas do ecossistema Vendo Casas:
1. Moeda brasileira determinística: 'R$ XXX.XXX,00'.
2. Jargões imobiliários corrigidos ('quarto tipo apto' -> Suíte).
3. Estrutura de copy de alta conversão para Instagram, Facebook e WhatsApp.
4. Histórico salvo localmente em memory/postagens_vendocasas_historico.json.
"""

import json
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORICO_PATH = BASE_DIR / "memory" / "postagens_vendocasas_historico.json"

PLUGIN = {
    "name": "criar_postagem_vendocasas",
    "description": (
        "Cria uma postagem profissional de imóvel no padrão oficial Vendo Casas "
        "(para Instagram, Facebook, WhatsApp e portais). Use sempre que o corretor "
        "pedir para 'criar post', 'fazer postagem', 'gerar anúncio de imóvel' ou "
        "'divulgar imóvel'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "titulo_ou_tipo": {
                "type": "STRING",
                "description": "Tipo do imóvel e negócio (Ex: 'Casa à venda', 'Apartamento para locação', 'Sobrado alto padrão')"
            },
            "bairro": {
                "type": "STRING",
                "description": "Bairro do imóvel (Ex: 'Damha I', 'Redentora', 'Zona Sul')"
            },
            "cidade": {
                "type": "STRING",
                "description": "Cidade do imóvel (Ex: 'São José do Rio Preto', 'Mirassol', 'Cedral')"
            },
            "valor": {
                "type": "STRING",
                "description": "Valor do imóvel (Ex: '450.000', '1.2 milhão', 'R$ 750.000,00')"
            },
            "quartos": {
                "type": "STRING",
                "description": "Número de quartos e suítes (Ex: '3 quartos sendo 1 suíte')"
            },
            "vagas": {
                "type": "STRING",
                "description": "Vagas de garagem (Ex: '2 vagas cobertas')"
            },
            "area": {
                "type": "STRING",
                "description": "Área útil/construída ou total (Ex: '180m²', 'terreno de 250m²')"
            },
            "destaques": {
                "type": "STRING",
                "description": "Diferenciais do imóvel (Ex: 'piscina aquecida, churrasqueira gourmet, rica em armários')"
            }
        },
        "required": ["titulo_ou_tipo", "valor"]
    }
}


def _formatar_moeda_br(valor) -> str:
    """Formata qualquer representação de valor para 'R$ XXX.XXX,00'."""
    if not valor:
        return "Consulte"
    s = str(valor).strip()
    
    # 1. Detecção de milhões (ex: 1.5 milhão, 2 mi)
    m_mi = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:milh[oõ]es|milhao|milhão|mi)\b', s, re.IGNORECASE)
    if m_mi:
        try:
            num = float(m_mi.group(1).replace(",", ".")) * 1_000_000
            return f"R$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            pass

    # 2. Detecção de mil / k (ex: 450 mil, 500k)
    m_mil = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:mil|k)\b', s, re.IGNORECASE)
    if m_mil:
        try:
            num = float(m_mil.group(1).replace(",", ".")) * 1_000
            return f"R$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            pass

    # 3. Limpeza de caracteres não numéricos
    apenas_digitos = re.sub(r'[^\d,.]', '', s)
    if not apenas_digitos:
        return s

    if "," in apenas_digitos and "." in apenas_digitos:
        apenas_digitos = apenas_digitos.replace(".", "").replace(",", ".")
    elif "," in apenas_digitos:
        apenas_digitos = apenas_digitos.replace(",", ".")
    
    try:
        val_f = float(apenas_digitos)
        return f"R$ {val_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return s


def _salvar_historico(post_dict: dict) -> None:
    try:
        HISTORICO_PATH.parent.mkdir(parents=True, exist_ok=True)
        historico = []
        if HISTORICO_PATH.exists():
            historico = json.loads(HISTORICO_PATH.read_text(encoding="utf-8"))
        historico.append(post_dict)
        HISTORICO_PATH.write_text(json.dumps(historico, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    titulo = parameters.get("titulo_ou_tipo", "Imóvel Selecionado").strip()
    valor_fmt = _formatar_moeda_br(parameters.get("valor", ""))
    bairro = parameters.get("bairro", "").strip()
    cidade = parameters.get("cidade", "").strip()
    quartos = parameters.get("quartos", "").strip()
    vagas = parameters.get("vagas", "").strip()
    area = parameters.get("area", "").strip()
    destaques = parameters.get("destaques", "").strip()

    # Normalização de jargão imobiliário
    if "quarto tipo apto" in quartos.lower():
        quartos = re.sub(r'quarto tipo apto', 'suíte', quartos, flags=re.IGNORECASE)

    localizacao = f"{bairro}" if bairro else ""
    if cidade:
        localizacao = f"{localizacao} — {cidade}" if localizacao else cidade

    # Montagem da Legenda Oficial Padrão Vendo Casas
    linhas_caracteristicas = []
    if quartos:
        linhas_caracteristicas.append(f"▫️ {quartos}")
    if vagas:
        linhas_caracteristicas.append(f"▫️ {vagas}")
    if area:
        linhas_caracteristicas.append(f"▫️ Área: {area}")
    if destaques:
        linhas_caracteristicas.append(f"▫️ Diferenciais: {destaques}")

    bloco_caracteristicas = "\n".join(linhas_caracteristicas)

    legenda_post = (
        f"🏡 {titulo.upper()}\n"
        f"📍 {localizacao or 'Excelente Localização'}\n\n"
        f"💰 Investimento: {valor_fmt}\n\n"
        f"Destaques do Imóvel:\n"
        f"{bloco_caracteristicas}\n\n"
        f"📲 Agende sua visita ou tire suas dúvidas:\n"
        f"Link direto na bio ou envie uma mensagem no WhatsApp.\n\n"
        f"#vendocasas #imoveis #corretordeimoveis #oportunidadeimobiliaria"
    )

    registro = {
        "timestamp": datetime.now().isoformat(),
        "titulo": titulo,
        "valor": valor_fmt,
        "localizacao": localizacao,
        "legenda_completa": legenda_post
    }
    _salvar_historico(registro)

    if player:
        try:
            player.write_log(f"JARVIS: Postagem gerada com sucesso para {titulo} ({valor_fmt}).")
        except Exception:
            pass

    # Resposta falada concisa e objetiva para o corretor
    return (
        f"Criei a postagem no padrão Vendo Casas para {titulo}, no valor de {valor_fmt}. "
        f"A legenda foi estruturada com os diferenciais, gatilho de contato e já está salva no seu histórico."
    )
