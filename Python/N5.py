"""N5 - Decodificação de telemetria MoT e persistência de dados PROCESSADOS.

O N5 não conhece MQTT/Serial, nem decide custódia: recebe uma resposta
DATA_REPLY de 24 bytes, converte as grandezas e grava CSV no próprio nível.
"""
import csv
from datetime import datetime
from pathlib import Path

PASTA_DADOS_PROCESSADOS = Path(__file__).resolve().parent / "N4" / "Dados_Processados"


def decodificar_rssi(byte_rssi):
    # Reproduz as operações da implementação N3 original.
    if byte_rssi == 127:
        return -10.0
    if byte_rssi >= 128:
        return int(((byte_rssi - 256) / 2) - 74)
    return int((byte_rssi / 2) - 74)


def decodificar_snr(msb, lsb):
    valor = (msb << 8) | lsb
    if valor >= 0x8000:
        valor -= 0x10000
    return valor / 100.0


def processar_telemetria(raw_pkt):
    if len(raw_pkt) != 24 or raw_pkt[1] != 0x21:
        raise ValueError("Esperado DATA_REPLY de 24 bytes")
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tipo_pkt": f"0x{raw_pkt[1]:02X}",
        "sensor_id": int(raw_pkt[9]),
        "destino_id": int(raw_pkt[10]),
        "packet_id": int(raw_pkt[8]),
        "rssi_dl": decodificar_rssi(raw_pkt[2]),
        "snr_dl": decodificar_snr(raw_pkt[3], raw_pkt[4]),
        "rssi_ul": decodificar_rssi(raw_pkt[5]),
        "snr_ul": decodificar_snr(raw_pkt[6], raw_pkt[7]),
        "temperatura": (raw_pkt[19] - 40.0) if raw_pkt[19] != 0xFF else None,
        "umidade": raw_pkt[20] if raw_pkt[20] != 0xFF else None,
        "uid_objeto_parcial": " ".join(f"{b:02X}" for b in raw_pkt[21:24]),
        "raw_hex": " ".join(f"{b:02X}" for b in raw_pkt),
    }


class RegistroProcessado:
    """Arquivo CSV independente do histórico bruto, com flush a cada leitura."""
    CAMPOS = (
        "timestamp", "tipo_pkt", "sensor_id", "destino_id", "packet_id",
        "rssi_dl", "snr_dl", "rssi_ul", "snr_ul", "temperatura", "umidade",
        "uid_objeto_parcial", "responsavel", "raw_hex",
    )
    CABECALHO = (
        "Timestamp", "Tipo_Pkt", "ID_Origem", "ID_Destino", "Packet_ID",
        "RSSI_DL", "SNR_DL", "RSSI_UL", "SNR_UL", "Temp_C", "Umidade_Pct",
        "UID_Objeto", "Responsavel", "Raw_Hex",
    )

    def __init__(self):
        PASTA_DADOS_PROCESSADOS.mkdir(parents=True, exist_ok=True)
        self.caminho = PASTA_DADOS_PROCESSADOS / f"Sessao_MoT_{datetime.now():%Y_%m_%d_%H-%M-%S_%f}.csv"
        self._arquivo = self.caminho.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._arquivo)
        self._writer.writerow(self.CABECALHO)
        self._arquivo.flush()

    def registrar(self, dados):
        self._writer.writerow([dados.get(k) for k in self.CAMPOS])
        self._arquivo.flush()

    def fechar(self):
        self._arquivo.close()
