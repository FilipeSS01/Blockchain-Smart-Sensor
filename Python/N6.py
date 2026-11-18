"""N6 - Painel web local de visualização e cadastro.

Não manipula pacotes de rádio, nem toma decisões sobre custódia.
As alterações cadastrais são persistidas pelo N4.
"""
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import N4

STATIC_DIR = Path(__file__).resolve().parent / "N6" / "static"


class EstadoPainel:
    """Cópia independente da telemetria mais recente, protegida para threads."""

    def __init__(self, janela_online=30):
        self._lock = RLock()
        self._telemetria = {}
        self.janela_online = janela_online

    def atualizar(self, dados):
        with self._lock:
            self._telemetria[int(dados["sensor_id"])] = dict(dados)

    def consultar(self):
        with self._lock:
            items = [dict(d) for d in self._telemetria.values()]
        agora = datetime.now()
        for item in items:
            try:
                visto = datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")
                item["online"] = timedelta(0) <= agora - visto <= timedelta(seconds=self.janela_online)
            except (ValueError, KeyError, TypeError):
                item["online"] = False
        return sorted(items, key=lambda i: i["sensor_id"])


class PessoaCadastro(BaseModel):
    uid: str = Field(min_length=1, max_length=64)
    nome: str = Field(min_length=1, max_length=150)
    email: str = ""
    telefone: str = ""
    status: str = "ativo"


def criar_app(estado):
    """App FastAPI ligada ao estado pertencente ao N3, sem circular imports."""
    app = FastAPI(title="MoT — Nível 6", docs_url="/api/docs", redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/sensores")
    def sensores():
        cadastrados, _ = N4.carregar_sensores_cadastrados()
        sessoes = N4.carregar_sessoes_ativas()
        telemetria = {int(t["sensor_id"]): t for t in estado.consultar()}
        return [
            {
                "id": node_id,
                "mac": mac,
                "sessao": sessoes.get(node_id),
                "telemetria": telemetria.get(node_id),
                "online": telemetria.get(node_id, {}).get("online", False),
            }
            for mac, node_id in sorted(cadastrados.items(), key=lambda kv: kv[1])
        ]

    @app.get("/api/pessoas")
    def pessoas():
        return [
            {"uid": uid, "nome": pessoa["nome"], "email": pessoa["email"],
             "telefone": pessoa["telefone"], "status": pessoa["status"]}
            for uid, pessoa in N4.carregar_pessoas().items()
        ]

    @app.post("/api/pessoas", status_code=201)
    def cadastrar(pessoa: PessoaCadastro):
        try:
            N4.salvar_pessoa(pessoa.uid, pessoa.nome, pessoa.email,
                            pessoa.telefone, status=pessoa.status)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {"ok": True}

    @app.delete("/api/pessoas/{uid}")
    def excluir(uid: str):
        try:
            N4.remover_pessoa(uid)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except KeyError as e:
            raise HTTPException(404, "UID não encontrado") from e
        return {"ok": True}

    return app
