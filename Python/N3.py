# main.py
import time
import os
import csv
from pathlib import Path
from datetime import datetime
from serial_manager import GerenciadorSerial
from mqtt_manager import GerenciadorMQTT
from n4_storage import (
    carregar_pessoas,
    carregar_sensores_cadastrados,
    salvar_novo_sensor,
    carregar_sessoes_ativas,
    salvar_sessoes_ativas
)


# =======================================================================
#                     1 - Configurações Gerais do MoT
# =======================================================================
TAMANHO_PACOTE = 24
ID_GATEWAY = 100
HOP_LIMIT_PADRAO = 1

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "N4" / "Dados_Brutos"
BROKER = "179.197.87.156"
MQTT_PORTA = 1883
MQTT_TOPIC_DL = "mot_lora_mqtt_FILIPE_SILVA/gateway/downlink"
MQTT_TOPIC_UL = "mot_lora_mqtt_FILIPE_SILVA/gateway/uplink"

# Tipos de Pacote do Protocolo MoT (Byte 1)
PKT_JOIN_REQUEST        = 0x01
PKT_JOIN_ACCEPT         = 0x02

# Autenticação de Operador e Objeto
PKT_AUTH_REQUEST        = 0x10
PKT_AUTH_RESPONSE       = 0x11
PKT_OBJ_CUSTODY_REQ     = 0x12
PKT_OBJ_CUSTODY_RESP    = 0x13

# Telemetria
PKT_DATA_POLL           = 0x20
PKT_DATA_REPLY          = 0x21

# Handover e Custódia
PKT_CUSTODY_START       = 0x30
PKT_CUSTODY_CONFIRMED   = 0x31
PKT_CUSTODY_ABORT       = 0x32
PKT_HANDOVER_AGREED     = 0x33

# =======================================================================
#                     2 - Inicialização de Dados do Nível 4 (N4)
# =======================================================================
CADASTRO_PESSOAS = carregar_pessoas()
tabela_sensores, proximo_id_sensor = carregar_sensores_cadastrados()
sessoes_ativas = carregar_sessoes_ativas()

# Controle de estado em memória
operadores_autenticados = {}  # { node_id: uid_operador }
intencoes_pendentes = {}      # { uid_objeto: { "node_id": sid, "uid_operador": uid_op } }

print(f"[N4] {len(sessoes_ativas)} sessão(ões) ativa(s) recuperada(s).")

seq_packet_gw = 0

# =======================================================================
#                     3 - Seleção de Interface (Serial ou MQTT)
# =======================================================================
print("\n" + "="*50)
print("             SYS - PROTOCOLO MoT (24 BYTES)")
print("="*50)
print("[1] Comunicação Direta (Serial/USB com Gateway)")
print("[2] Comunicação em Nuvem (MQTT)")
modo_escolhido = input("Escolha o modo de operação (1 ou 2): ").strip()

conexao = None

if modo_escolhido == "1":
    n_serial = input("Digite o número da porta COM (Ex: 3): ").strip()
    porta_com = f"COM{n_serial}"
    conexao = GerenciadorSerial(porta_com, tamanho_pacote=TAMANHO_PACOTE)
    conexao.conectar()
    conexao.resetar_esp32()
elif modo_escolhido == "2":
    BROKER = BROKER
    PORTA  = MQTT_PORTA
    TOPIC_DL = MQTT_TOPIC_DL
    TOPIC_UL = MQTT_TOPIC_UL
    conexao = GerenciadorMQTT(BROKER, porta=PORTA, topic_dl=TOPIC_DL, topic_ul=TOPIC_UL, qos=1, tamanho_pacote=TAMANHO_PACOTE)
    conexao.conectar()
    time.sleep(1.5)
else:
    print("[SYS] Modo inválido. Encerrando.")
    exit()

# =======================================================================
#                     4 - Estrutura de Logs (Nível 4)
# =======================================================================

LOG_DIR.mkdir(parents=True, exist_ok=True)
arquivo_log = LOG_DIR / f"Sessao_MoT_{datetime.now():%Y_%m_%d_%H-%M-%S}.csv"
f_log = open(arquivo_log, 'w', newline='', encoding='utf-8')
csv_writer = csv.writer(f_log)

cabecalho = [
    "Timestamp", "Tipo_Pkt", "ID_Origem", "ID_Destino", "Packet_ID",
    "RSSI_DL", "SNR_DL", "RSSI_UL", "SNR_UL",
    "Temp_C", "Umidade_Pct", "UID_Objeto", "Responsavel", "Raw_Hex"
]
csv_writer.writerow(cabecalho)
f_log.flush()

# =======================================================================
#                     5 - Utilitários de Pacote (MoT 24 Bytes)
# =======================================================================
def decodificar_rssi(byte_rssi):
    if byte_rssi == 127:
        return -10.0
    elif byte_rssi >= 128:
        return int(((byte_rssi - 256) / 2) - 74)
    else:
        return int((byte_rssi / 2) - 74)

def decodificar_snr(msb, lsb):
    valor_int = (msb << 8) | lsb
    if valor_int >= 0x8000:
        valor_int -= 0x10000
    return valor_int / 100.0

def criar_frame_base(pkt_type, dest_id):
    global seq_packet_gw
    seq_packet_gw = (seq_packet_gw + 1) % 256
    frame = [0] * TAMANHO_PACOTE
    frame[0] = 0x01
    frame[1] = pkt_type
    frame[8] = seq_packet_gw
    frame[9] = ID_GATEWAY
    frame[10] = dest_id
    frame[12] = HOP_LIMIT_PADRAO
    return frame

# =======================================================================
#                     6 - Handlers dos Eventos do MoT
# =======================================================================
def tratar_join_request(raw_pkt):
    global proximo_id_sensor
    mac_bytes = raw_pkt[13:19]
    mac_str = ":".join(f"{b:02X}" for b in mac_bytes)

    if mac_str not in tabela_sensores:
        id_atribuido = proximo_id_sensor
        tabela_sensores[mac_str] = id_atribuido
        proximo_id_sensor += 1
        salvar_novo_sensor(mac_str, id_atribuido)
        print(f"\n[JOIN] >>> NOVO DISPOSITIVO REGISTRADO! <<<")
        print(f"[JOIN] MAC: {mac_str} -> Atribuído Node_ID: {id_atribuido}")
    else:
        id_atribuido = tabela_sensores[mac_str]
        print(f"\n[JOIN] Nó já cadastrado no N4. MAC: {mac_str} -> Node_ID: {id_atribuido}")

    resp = criar_frame_base(PKT_JOIN_ACCEPT, dest_id=0xFF)
    resp[13:19] = mac_bytes
    resp[19] = id_atribuido
    resp[20] = ID_GATEWAY
    resp[21] = HOP_LIMIT_PADRAO

    conexao.enviar_pacote(resp)
    print(f"[JOIN] JOIN_ACCEPT despachado para o sensor {id_atribuido}.")

def tratar_auth_request(raw_pkt):
    """Etapa 1: Validação do crachá do Operador (Pessoa)."""
    global CADASTRO_PESSOAS
    sensor_id = int(raw_pkt[9])
    uid_bytes = raw_pkt[13:17]
    uid_str = " ".join(f"{b:02X}" for b in uid_bytes)

    CADASTRO_PESSOAS = carregar_pessoas()

    print(f"\n[AUTH] Sensor ID {sensor_id} requisitou validação de Operador: [{uid_str}]")

    pessoa = CADASTRO_PESSOAS.get(uid_str)
    
    if pessoa and pessoa.get("status") == "ativo":
        aprovado = 1
        operadores_autenticados[sensor_id] = uid_str
        print(f"[AUTH] >>> OPERADOR AUTORIZADO! Responsável: {pessoa['nome']} <<<")
    else:
        aprovado = 0
        operadores_autenticados.pop(sensor_id, None)
        motivo = "Status inativo" if pessoa else "Tag não cadastrada"
        print(f"[AUTH] >>> OPERADOR NEGADO! ({motivo}) <<<")

    resp = criar_frame_base(PKT_AUTH_RESPONSE, dest_id=sensor_id)
    resp[13:17] = uid_bytes
    resp[17] = aprovado

    conexao.enviar_pacote(resp)
    print(f"[AUTH] Resposta despachada para o sensor {sensor_id}.")

def tratar_obj_custody_req(raw_pkt):
    """Etapa 2: Associação da Tag do Objeto com o Operador logado."""
    sensor_id = int(raw_pkt[9])
    uid_op_bytes = raw_pkt[13:17]
    uid_obj_bytes = raw_pkt[17:21]

    uid_op_str  = " ".join(f"{b:02X}" for b in uid_op_bytes)
    uid_obj_str = " ".join(f"{b:02X}" for b in uid_obj_bytes)

    print(f"\n[CUSTÓDIA] Nó {sensor_id} solicitou custódia do Objeto: [{uid_obj_str}] (Operador: [{uid_op_str}])")

    # Verifica se o objeto já pertence a outro nó ativo
    no_detentor = None
    for n_id, sess in sessoes_ativas.items():
        if sess.get("uid_objeto") == uid_obj_str:
            no_detentor = n_id
            break

    resp = criar_frame_base(PKT_OBJ_CUSTODY_RESP, dest_id=sensor_id)
    resp[13:17] = uid_op_bytes
    resp[17:21] = uid_obj_bytes

    if no_detentor is not None and no_detentor != sensor_id:
        # Objeto retido por outro nó físico
        print(f"[CUSTÓDIA] >>> OBJETO RETIDO PELO NÓ ID {no_detentor}! <<<")
        print(f"[CUSTÓDIA] Registrando intenção de transferência para Nó ID {sensor_id}...")
        
        intencoes_pendentes[uid_obj_str] = {
            "node_id": sensor_id,
            "uid_operador": uid_op_str
        }

        resp[21] = 2  # Status: 2 = Retido por outro nó
        conexao.enviar_pacote(resp)

    else:
        # Objeto Livre: Concede custódia imediata
        nome_op = CADASTRO_PESSOAS.get(uid_op_str, {}).get("nome", "Desconhecido")
        sessoes_ativas[sensor_id] = {
            "uid_objeto": uid_obj_str,
            "uid_operador": uid_op_str,
            "responsavel": nome_op,
            "inicio_sessao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ultimo_visto": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pausado_troca": False
        }
        salvar_sessoes_ativas(sessoes_ativas)

        print(f"[CUSTÓDIA] >>> CUSTÓDIA CONCEDIDA AO NÓ ID {sensor_id}! <<<")
        print(f"[CUSTÓDIA] Objeto: [{uid_obj_str}] | Responsável: {nome_op}")

        resp[21] = 1  # Status: 1 = Concedido
        conexao.enviar_pacote(resp)

def tratar_handover(raw_pkt):
    """Árbitro de Handover: Processa o consentimento mútuo do Nó Cedente."""
    sid_cedente = int(raw_pkt[9])
    uid_obj_bytes = raw_pkt[13:17]
    uid_novo_op_bytes = raw_pkt[17:21]

    uid_obj_str     = " ".join(f"{b:02X}" for b in uid_obj_bytes)
    uid_novo_op_str = " ".join(f"{b:02X}" for b in uid_novo_op_bytes)

    print("\n" + "="*60)
    print(f"[Handover] Recebido Acordo de Handover do Nó Cedente {sid_cedente}")
    print(f"[Handover] Objeto Apresentado : [{uid_obj_str}]")
    print(f"[Handover] Crachá do Receptor: [{uid_novo_op_str}]")

    intencao = intencoes_pendentes.get(uid_obj_str)
    if not intencao:
        print("[Handover] FALHA: Nenhuma solicitação pendente para este objeto.")
        print("="*60)
        return

    sid_receptor    = intencao["node_id"]
    uid_op_esperado = intencao["uid_operador"]

    # Validação do Operador
    if uid_novo_op_str == uid_op_esperado:
        print(f"[Handover] >>> SUCESSO: O crachá lido em {sid_cedente} coincide com o Operador do Nó {sid_receptor}! <<<")

        # 1. Notifica o Nó Cedente para liberar a posse física
        resp_cedente = criar_frame_base(PKT_CUSTODY_CONFIRMED, dest_id=sid_cedente)
        conexao.enviar_pacote(resp_cedente)
        time.sleep(0.1)

        # 2. Transfere a sessão ativa
        sessoes_ativas.pop(sid_cedente, None)
        nome_op = CADASTRO_PESSOAS.get(uid_novo_op_str, {}).get("nome", "Desconhecido")

        sessoes_ativas[sid_receptor] = {
            "uid_objeto": uid_obj_str,
            "uid_operador": uid_novo_op_str,
            "responsavel": nome_op,
            "inicio_sessao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ultimo_visto": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pausado_troca": False
        }
        salvar_sessoes_ativas(sessoes_ativas)
        intencoes_pendentes.pop(uid_obj_str, None)

        # 3. Concede formalmente a custódia no Nó Receptor
        resp_receptor = criar_frame_base(PKT_OBJ_CUSTODY_RESP, dest_id=sid_receptor)
        resp_receptor[13:17] = [int(b, 16) for b in uid_novo_op_str.split()]
        resp_receptor[17:21] = uid_obj_bytes
        resp_receptor[21]    = 1  # Concedido!
        conexao.enviar_pacote(resp_receptor)

        print(f"[Handover] >>> HANDOVER EFETIVADO COM SUCESSO! <<<")
        print(f"[Handover] Objeto [{uid_obj_str}] transferido para o Nó {sid_receptor} (Resp: {nome_op})")
        print("="*60)
    else:
        print(f"[Handover] REJEITADO: Crachá lido no cedente ({uid_novo_op_str}) difere do operador no receptor ({uid_op_esperado}).")
        print("="*60)

def tratar_custodia(raw_pkt):
    tipo_evento = raw_pkt[1]
    sensor_id   = int(raw_pkt[9])
    uid_str     = " ".join(f"{b:02X}" for b in raw_pkt[13:17])

    if tipo_evento == PKT_CUSTODY_START:
        if sensor_id in sessoes_ativas:
            sessoes_ativas[sensor_id]["pausado_troca"] = True
            resp = sessoes_ativas[sensor_id].get("responsavel", "Desconhecido")
        else:
            resp = "Desconhecido"

        salvar_sessoes_ativas(sessoes_ativas)

        print("\n" + "="*55)
        print(f"[CUSTÓDIA] Pedido de troca de custódia iniciado no Nó ID {sensor_id}!")
        print(f"[CUSTÓDIA] Titular atual: [{resp}] | Objeto: [{uid_str}]")
        print(f"[CUSTÓDIA] Polling IMEDIATAMENTE PAUSADO. Aguardando leituras...")
        print("="*55)

    elif tipo_evento == PKT_CUSTODY_ABORT:
        if sensor_id in sessoes_ativas:
            sessoes_ativas[sensor_id]["pausado_troca"] = False
            resp = sessoes_ativas[sensor_id].get("responsavel", "Desconhecido")
        else:
            resp = "Desconhecido"

        salvar_sessoes_ativas(sessoes_ativas)

        print("\n" + "-"*55)
        print(f"[CUSTÓDIA] Troca CANCELADA / TIMEOUT no Nó ID {sensor_id}!")
        print(f"[CUSTÓDIA] Custódia mantida com [{resp}]. Retomando polling normal...")
        print("-" * 55)

def tratar_data_reply(raw_pkt):
    sensor_id = int(raw_pkt[9])
    pkt_id = raw_pkt[8]

    if sensor_id in sessoes_ativas:
        sessoes_ativas[sensor_id]["ultimo_visto"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        salvar_sessoes_ativas(sessoes_ativas)

    rssi_dl = decodificar_rssi(raw_pkt[2])
    snr_dl  = decodificar_snr(raw_pkt[3], raw_pkt[4])
    rssi_ul = decodificar_rssi(raw_pkt[5])
    snr_ul  = decodificar_snr(raw_pkt[6], raw_pkt[7])

    temp_raw = raw_pkt[19]
    temp_c   = (temp_raw - 40.0) if temp_raw != 0xFF else None
    umidade  = raw_pkt[20] if raw_pkt[20] != 0xFF else None

    uid_obj_parcial = " ".join(f"{b:02X}" for b in raw_pkt[21:24])
    sessao = sessoes_ativas.get(sensor_id, {})
    responsavel = sessao.get("responsavel", "Sem Custódia")

    print(f"\n[TELEMETRIA] Nó {sensor_id} (Resp: {responsavel}) | Objeto: [{uid_obj_parcial}...] | Temp: {temp_c} °C | Umidade: {umidade} %")
    print(f"[METRICAS]   DL -> RSSI: {rssi_dl} dBm, SNR: {snr_dl:.2f} dB | UL -> RSSI: {rssi_ul} dBm, SNR: {snr_ul:.2f} dB")

    raw_hex = " ".join(f"{b:02X}" for b in raw_pkt)
    csv_writer.writerow([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        f"0x{raw_pkt[1]:02X}", sensor_id, raw_pkt[10], pkt_id,
        rssi_dl, snr_dl, rssi_ul, snr_ul,
        temp_c, umidade, uid_obj_parcial, responsavel, raw_hex
    ])
    f_log.flush()

# =======================================================================
#                     7 - Loop Principal do SYS
# =======================================================================
print("\n[SYS] Sistema em operação contínua. Pressione Ctrl+C para encerrar.\n")
ultimo_polling = time.time()
INTERVALO_POLLING_SEGUNDOS = 5.0

try:
    while True:
        # 1. Escuta não bloqueante por Uplinks LoRa
        pacote_recebido = conexao.receber_pacote(timeout=0.1)

        if pacote_recebido is not None and len(pacote_recebido) == TAMANHO_PACOTE:
            tipo_pkt = pacote_recebido[1]

            if tipo_pkt == PKT_JOIN_REQUEST:
                tratar_join_request(pacote_recebido)

            elif tipo_pkt == PKT_AUTH_REQUEST:
                tratar_auth_request(pacote_recebido)

            elif tipo_pkt == PKT_OBJ_CUSTODY_REQ:
                tratar_obj_custody_req(pacote_recebido)

            elif tipo_pkt == PKT_HANDOVER_AGREED:
                tratar_handover(pacote_recebido)

            elif tipo_pkt in (PKT_CUSTODY_START, PKT_CUSTODY_ABORT):
                tratar_custodia(pacote_recebido)

            elif tipo_pkt == PKT_DATA_REPLY:
                tratar_data_reply(pacote_recebido)

        # 2. Polling Centralizado apenas para nós ativos e não pausados
        agora = time.time()
        if agora - ultimo_polling >= INTERVALO_POLLING_SEGUNDOS:
            ultimo_polling = agora

            for node_id, dados in list(sessoes_ativas.items()):
                if dados.get("pausado_troca", False):
                    continue

                print(f"[POLLING] Solicitando dados de clima para Nó ID {node_id} (Custódia ativa)...")
                poll_pkt = criar_frame_base(PKT_DATA_POLL, dest_id=int(node_id))
                conexao.enviar_pacote(poll_pkt)
                time.sleep(0.1)

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n[SYS] Encerrando...")
finally:
    if conexao:
        conexao.desconectar()
    f_log.close()
    salvar_sessoes_ativas(sessoes_ativas)
    print(f"[SYS] Sessões ativas e dados salvos no N4.")
    print(f"[SYS] Fim da Execução.")