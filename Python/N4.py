# n4_storage.py
import os
import csv
import json

CAMINHO_BASE_N4 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "N4"))
PASTA_PARAMETROS = os.path.join(CAMINHO_BASE_N4, "Parametros")
PASTA_DADOS = os.path.join(CAMINHO_BASE_N4, "Dados_Brutos")

ARQUIVO_PESSOAS = os.path.join(PASTA_PARAMETROS, "pessoas.csv")
ARQUIVO_SENSORES = os.path.join(PASTA_PARAMETROS, "sensores_cadastrados.txt")
ARQUIVO_SESSOES = os.path.join(PASTA_PARAMETROS, "sessoes_ativas.json")

def garantir_diretorios():
    """Garante que as pastas do N4 existam no sistema operacional."""
    os.makedirs(PASTA_PARAMETROS, exist_ok=True)
    os.makedirs(PASTA_DADOS, exist_ok=True)

def carregar_pessoas():
    """
    Lê pessoas.csv e retorna um dicionário indexado pelo UID:
    {
       "5D 1D BD 06": {
           "nome": "Filipe Silva",
           "email": "filipe@exemplo.com",
           "telefone": "+5535999999999",
           "chave_publica": "...",
           "status": "ativo"
       }
    }
    """
    garantir_diretorios()
    pessoas = {}

    # Se o arquivo não existir, cria o arquivo com cabeçalho e exemplos
    if not os.path.exists(ARQUIVO_PESSOAS):
        with open(ARQUIVO_PESSOAS, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["tag_uid", "nome", "email", "telefone", "chave_publica", "status"])
            writer.writerow(["5D 1D BD 06", "Filipe Silva", "filipe@exemplo.com", "+5535999999999", "CHAVE_PUB_1", "ativo"])
            writer.writerow(["15 78 D6 06", "Orientador", "orientador@exemplo.com", "+5535988888888", "CHAVE_PUB_2", "ativo"])

    with open(ARQUIVO_PESSOAS, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for linha in reader:
            uid = linha.get("tag_uid", "").strip().upper()
            if uid and not uid.startswith("#"):
                pessoas[uid] = {
                    "nome": linha.get("nome", "").strip(),
                    "email": linha.get("email", "").strip(),
                    "telefone": linha.get("telefone", "").strip(),
                    "chave_publica": linha.get("chave_publica", "").strip(),
                    "status": linha.get("status", "ativo").strip().lower()
                }

    print(f"[N4] {len(pessoas)} pessoas carregadas da base cadastral.")
    return pessoas

def carregar_sensores_cadastrados():
    """Lê sensores_cadastrados.txt e retorna dict { MAC: ID_INT } e próximo ID livre."""
    garantir_diretorios()
    sensores = {}
    maior_id = 0

    if os.path.exists(ARQUIVO_SENSORES):
        with open(ARQUIVO_SENSORES, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#"):
                    partes = linha.split(",", 1)
                    if len(partes) == 2:
                        mac = partes[0].strip().upper()
                        try:
                            sensor_id = int(partes[1].strip())
                            sensores[mac] = sensor_id
                            if sensor_id > maior_id:
                                maior_id = sensor_id
                        except ValueError:
                            continue

    proximo_id = maior_id + 1 if maior_id >= 1 else 1
    print(f"[N4] {len(sensores)} sensores comissionados carregados. Próximo ID livre: {proximo_id}")
    return sensores, proximo_id

def salvar_novo_sensor(mac, sensor_id):
    """Anexa um novo sensor comissionado ao arquivo de texto."""
    garantir_diretorios()
    with open(ARQUIVO_SENSORES, "a", encoding="utf-8") as f:
        f.write(f"{mac.upper()},{sensor_id}\n")
    print(f"[N4] Registro persistido: MAC {mac} -> ID {sensor_id}")

def carregar_sessoes_ativas():
    """Recupera as sessões ativas do disco após reinício do script."""
    garantir_diretorios()
    if os.path.exists(ARQUIVO_SESSOES):
        try:
            with open(ARQUIVO_SESSOES, "r", encoding="utf-8") as f:
                dados = json.load(f)
                # Garante que as chaves dos sensores sejam inteiros
                return {int(k): v for k, v in dados.items()}
        except Exception as e:
            print(f"[N4] Erro ao ler sessoes_ativas.json: {e}")
    return {}

def salvar_sessoes_ativas(sessoes):
    """Grava o estado atual de todas as sessões ativas em disco."""
    garantir_diretorios()
    try:
        with open(ARQUIVO_SESSOES, "w", encoding="utf-8") as f:
            json.dump(sessoes, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[N4] Erro ao salvar sessoes_ativas.json: {e}")