"""
~/nexora/server/docs.py — Biblioteca de Documentos gerados pela frota NEXORA.
"""

from pathlib import Path
import time
import store

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def register(route, ApiError):
    @route("GET", "/api/docs")
    def handle_list_docs(req, query, body):
        files = []
        for p in DOCS_DIR.glob("**/*"):
            if p.is_file():
                stat = p.stat()
                files.append({
                    "name": p.name,
                    "rel_path": str(p.relative_to(DOCS_DIR)),
                    "size_bytes": stat.st_size,
                    "updated_at": stat.st_mtime
                })
        files.sort(key=lambda x: x["updated_at"], reverse=True)
        return {"ok": True, "docs": files}

    @route("GET", "/api/docs/content")
    def handle_get_doc_content(req, query, body):
        rel = query.get("file", "").strip()
        if not rel:
            raise ApiError(400, "Parâmetro file é obrigatório")
        
        target = (DOCS_DIR / rel).resolve()
        if not str(target).startswith(str(DOCS_DIR.resolve())) or not target.exists():
            raise ApiError(404, "Documento não encontrado")
        
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "name": target.name, "content": content}

    @route("POST", "/api/docs")
    def handle_save_doc(req, query, body):
        if not body:
            raise ApiError(400, "Dados obrigatórios")
        filename = body.get("name", "").strip()
        content = body.get("content", "")
        if not filename:
            raise ApiError(400, "Nome do arquivo obrigatório")
        
        if not filename.endswith(".md"):
            filename += ".md"
            
        target = (DOCS_DIR / filename).resolve()
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "name": filename, "message": "Documento salvo com sucesso"}
