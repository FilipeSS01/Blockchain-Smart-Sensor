"""N4 - Persistência de cadastros, sessões e frames brutos (sem cálculo)."""
import csv
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from threading import RLock

BASE_DIR = Path(__file__).resolve().parent / "N4"
_LOCK = RLock()
CAMPOS_PESSOAS = ("tag_uid", "nome", "email", "telefone", "chave_publica", "status")
# O campo 'chave_publica' é preservado somente para não perder dados legados.


def _pastas():
    parametros = BASE_DIR / "Parametros"
    brutos = BASE_DIR / "Dados_Brutos"
    parametros.mkdir(parents=True, exist_ok=True)
    brutos.mkdir(parents=True, exist_ok=True)
    return parametros, brutos


def _substituir_arquivo(destino: Path, gravar):
    """Escreve o arquivo completo e troca atomicamente após fechar."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(prefix="mot_", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(descritor, "w", encoding="utf-8", newline="") as arquivo:
            gravar(arquivo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def _normalizar_uid(uid):
    uid = " ".join(uid.strip().upper().replace(":", " ").split())
    if not re.fullmatch(r"[0-9A-F]{2}(?: [0-9A-F]{2}){3}", uid):
        raise ValueError("UID RFID deve conter 4 bytes hexadecimais (ex.: AA BB CC DD)")
    return uid


def carregar_pessoas():
    with _LOCK:
        parametros, _ = _pastas()
        arquivo = parametros / "pessoas.csv"
        if not arquivo.exists():
            _substituir_arquivo(arquivo, lambda f: csv.writer(f).writerow(CAMPOS_PESSOAS))
        pessoas = {}
        with arquivo.open("r", encoding="utf-8-sig", newline="") as f:
            for linha in csv.DictReader(f):
                uid = (linha.get("tag_uid") or "").strip().upper()
                if not uid or uid.startswith("#"):
                    continue
                pessoas[uid] = {
                    "nome": (linha.get("nome") or "").strip(),
                    "email": (linha.get("email") or "").strip(),
                    "telefone": (linha.get("telefone") or "").strip(),
                    "chave_publica": (linha.get("chave_publica") or "").strip(),
                    "status": (linha.get("status") or "ativo").strip().lower(),
                }
        return pessoas


def _gravar_pessoas(pessoas):
    destino = _pastas()[0] / "pessoas.csv"
    def escrever(f):
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_PESSOAS)
        escritor.writeheader()
        for uid, dados in pessoas.items():
            escritor.writerow({"tag_uid": uid, **dados})
    _substituir_arquivo(destino, escrever)


def salvar_pessoa(uid, nome, email="", telefone="", chave_publica="", status="ativo"):
    """Cadastra uma pessoa. Não sobrescreve um UID existente."""
    uid = _normalizar_uid(uid)
    if not nome.strip() or status not in ("ativo", "inativo"):
        raise ValueError("Nome e status (ativo/inativo) são obrigatórios")
    with _LOCK:
        pessoas = carregar_pessoas()
        if uid in pessoas:
            raise ValueError("UID já cadastrado")
        pessoas[uid] = {
            "nome": nome.strip(), "email": email.strip(), "telefone": telefone.strip(),
            "chave_publica": chave_publica.strip(), "status": status,
        }
        _gravar_pessoas(pessoas)


def remover_pessoa(uid):
    uid = _normalizar_uid(uid)
    with _LOCK:
        pessoas = carregar_pessoas()
        if uid not in pessoas:
            raise KeyError(uid)
        del pessoas[uid]
        _gravar_pessoas(pessoas)


def carregar_sensores_cadastrados():
    with _LOCK:
        arquivo = _pastas()[0] / "sensores_cadastrados.txt"
        sensores = {}
        maior_id = 0
        if arquivo.exists():
            for linha in arquivo.read_text(encoding="utf-8").splitlines():
                linha = linha.strip()
                if not linha or linha.startswith("#"):
                    continue
                partes = linha.split(",", 1)
                if len(partes) != 2:
                    continue
                try:
                    mac, node_id = partes[0].strip().upper(), int(partes[1].strip())
                except ValueError:
                    continue
                sensores[mac] = node_id
                maior_id = max(maior_id, node_id)
        return sensores, (maior_id + 1 if maior_id >= 1 else 1)


def salvar_novo_sensor(mac, sensor_id):
    with _LOCK:
        arquivo = _pastas()[0] / "sensores_cadastrados.txt"
        with arquivo.open("a", encoding="utf-8") as f:
            f.write(f"{mac.upper()},{sensor_id}\n")
            f.flush()
        print(f"[N4] Registro persistido: MAC {mac} -> ID {sensor_id}")


def carregar_sessoes_ativas():
    with _LOCK:
        arquivo = _pastas()[0] / "sessoes_ativas.json"
        if not arquivo.exists():
            return {}
        try:
            with arquivo.open("r", encoding="utf-8") as f:
                return {int(k): v for k, v in json.load(f).items()}
        except (ValueError, OSError, TypeError) as e:
            print(f"[N4] Erro ao ler sessoes_ativas.json: {e}")
            return {}


def salvar_sessoes_ativas(sessoes):
    with _LOCK:
        arquivo = _pastas()[0] / "sessoes_ativas.json"
        _substituir_arquivo(arquivo, lambda f: json.dump(sessoes, f, indent=2, ensure_ascii=False))


class RegistroBruto:
    """Registra exatamente os 24 bytes recebidos, sem aplicar transformações."""
    CABECALHO = ("Timestamp", "Tipo_Pkt", "ID_Origem", "ID_Destino", "Packet_ID", "Raw_Hex")

    def __init__(self):
        pasta = _pastas()[1]
        self.caminho = pasta / f"Sessao_MoT_{datetime.now():%Y_%m_%d_%H-%M-%S_%f}.csv"
        self._arquivo = self.caminho.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._arquivo)
        self._writer.writerow(self.CABECALHO)
        self._arquivo.flush()

    def registrar(self, pacote, timestamp=None):
        if len(pacote) != 24:
            raise ValueError("Frame bruto precisa ter 24 bytes")
        timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._writer.writerow([
            timestamp, f"0x{pacote[1]:02X}", int(pacote[9]), int(pacote[10]),
            int(pacote[8]), " ".join(f"{b:02X}" for b in pacote),
        ])
        self._arquivo.flush()

    def fechar(self):
        self._arquivo.close()
