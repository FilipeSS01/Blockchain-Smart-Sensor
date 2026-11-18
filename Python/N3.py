"""N3 - Servidor central e árbitro MoT (ponto único de execução).

Executar: python N3.py
A lógica de Join, autenticação, custódia, handover e polling é preservada.
"""
import threading
import time
from datetime import datetime
import uvicorn

import N4
import N5
from N6 import EstadoPainel, criar_app

TAMANHO_PACOTE = 24
ID_GATEWAY = 100
HOP_LIMIT_PADRAO = 1

BROKER = "179.197.87.156"
MQTT_PORTA = 1883
MQTT_TOPIC_DL = "mot_lora_mqtt_FILIPE_SILVA/gateway/downlink"
MQTT_TOPIC_UL = "mot_lora_mqtt_FILIPE_SILVA/gateway/uplink"

PKT_JOIN_REQUEST    = 0x01
PKT_JOIN_ACCEPT     = 0x02
PKT_AUTH_REQUEST    = 0x10
PKT_AUTH_RESPONSE   = 0x11
PKT_OBJ_CUSTODY_REQ = 0x12
PKT_OBJ_CUSTODY_RESP = 0x13
PKT_DATA_POLL       = 0x20
PKT_DATA_REPLY      = 0x21
PKT_CUSTODY_START   = 0x30
PKT_CUSTODY_CONFIRMED = 0x31
PKT_CUSTODY_ABORT   = 0x32
PKT_HANDOVER_AGREED = 0x33


class ServidorMoT:
    """N3 mantém as decisões; N4 e N5 cuidam de seus próprios dados."""

    def __init__(self, conexao, estado=None, registro_bruto=None, registro_processado=None):
        self.conexao = conexao
        self.estado = estado if estado is not None else EstadoPainel()
        self.CADASTRO_PESSOAS = N4.carregar_pessoas()
        self.tabela_sensores, self.proximo_id_sensor = N4.carregar_sensores_cadastrados()
        self.sessoes_ativas = N4.carregar_sessoes_ativas()
        self.operadores_autenticados = {}
        self.intencoes_pendentes = {}
        self.seq_packet_gw = 0
        # Logs só são criados se não forem injetados (útil em testes).
        self.registro_bruto = registro_bruto if registro_bruto is not None else N4.RegistroBruto()
        self.registro_processado = registro_processado if registro_processado is not None else N5.RegistroProcessado()
        print(f"[N4] {len(self.sessoes_ativas)} sessão(ões) ativa(s) recuperada(s).")

    def criar_frame_base(self, pkt_type, dest_id):
        self.seq_packet_gw = (self.seq_packet_gw + 1) % 256
        frame = [0] * TAMANHO_PACOTE
        frame[0] = 0x01
        frame[1] = pkt_type
        frame[8] = self.seq_packet_gw
        frame[9] = ID_GATEWAY
        frame[10] = dest_id
        frame[12] = HOP_LIMIT_PADRAO
        return frame

    # =======================================================================
    #                     6 - Handlers dos Eventos do MoT
    # =======================================================================
    def tratar_join_request(self, raw_pkt):
        mac_bytes = raw_pkt[13:19]
        mac_str = ":".join(f"{b:02X}" for b in mac_bytes)

        if mac_str not in self.tabela_sensores:
            id_atribuido = self.proximo_id_sensor
            self.tabela_sensores[mac_str] = id_atribuido
            self.proximo_id_sensor += 1
            N4.salvar_novo_sensor(mac_str, id_atribuido)
            print(f"\n[JOIN] >>> NOVO DISPOSITIVO REGISTRADO! <<<")
            print(f"[JOIN] MAC: {mac_str} -> Atribuído Node_ID: {id_atribuido}")
        else:
            id_atribuido = self.tabela_sensores[mac_str]
            print(f"\n[JOIN] Nó já cadastrado no N4. MAC: {mac_str} -> Node_ID: {id_atribuido}")

        resp = self.criar_frame_base(PKT_JOIN_ACCEPT, dest_id=0xFF)
        resp[13:19] = mac_bytes
        resp[19] = id_atribuido
        resp[20] = ID_GATEWAY
        resp[21] = HOP_LIMIT_PADRAO

        self.conexao.enviar_pacote(resp)
        print(f"[JOIN] JOIN_ACCEPT despachado para o sensor {id_atribuido}.")

    def tratar_auth_request(self, raw_pkt):
        """Etapa 1: Validação do crachá do Operador (Pessoa)."""
        sensor_id = int(raw_pkt[9])
        uid_bytes = raw_pkt[13:17]
        uid_str = " ".join(f"{b:02X}" for b in uid_bytes)

        self.CADASTRO_PESSOAS = N4.carregar_pessoas()

        print(f"\n[AUTH] Sensor ID {sensor_id} requisitou validação de Operador: [{uid_str}]")

        pessoa = self.CADASTRO_PESSOAS.get(uid_str)

        if pessoa and pessoa.get("status") == "ativo":
            aprovado = 1
            self.operadores_autenticados[sensor_id] = uid_str
            print(f"[AUTH] >>> OPERADOR AUTORIZADO! Responsável: {pessoa['nome']} <<<")
        else:
            aprovado = 0
            self.operadores_autenticados.pop(sensor_id, None)
            motivo = "Status inativo" if pessoa else "Tag não cadastrada"
            print(f"[AUTH] >>> OPERADOR NEGADO! ({motivo}) <<<")

        resp = self.criar_frame_base(PKT_AUTH_RESPONSE, dest_id=sensor_id)
        resp[13:17] = uid_bytes
        resp[17] = aprovado

        self.conexao.enviar_pacote(resp)
        print(f"[AUTH] Resposta despachada para o sensor {sensor_id}.")

    def tratar_obj_custody_req(self, raw_pkt):
        """Etapa 2: Associação da Tag do Objeto com o Operador logado."""
        sensor_id = int(raw_pkt[9])
        uid_op_bytes = raw_pkt[13:17]
        uid_obj_bytes = raw_pkt[17:21]

        uid_op_str  = " ".join(f"{b:02X}" for b in uid_op_bytes)
        uid_obj_str = " ".join(f"{b:02X}" for b in uid_obj_bytes)

        print(f"\n[CUSTÓDIA] Nó {sensor_id} solicitou custódia do Objeto: [{uid_obj_str}] (Operador: [{uid_op_str}])")

        # Verifica se o objeto já pertence a outro nó ativo
        no_detentor = None
        for n_id, sess in self.sessoes_ativas.items():
            if sess.get("uid_objeto") == uid_obj_str:
                no_detentor = n_id
                break

        resp = self.criar_frame_base(PKT_OBJ_CUSTODY_RESP, dest_id=sensor_id)
        resp[13:17] = uid_op_bytes
        resp[17:21] = uid_obj_bytes

        if no_detentor is not None and no_detentor != sensor_id:
            # Objeto retido por outro nó físico
            print(f"[CUSTÓDIA] >>> OBJETO RETIDO PELO NÓ ID {no_detentor}! <<<")
            print(f"[CUSTÓDIA] Registrando intenção de transferência para Nó ID {sensor_id}...")

            self.intencoes_pendentes[uid_obj_str] = {
                "node_id": sensor_id,
                "uid_operador": uid_op_str
            }

            resp[21] = 2  # Status: 2 = Retido por outro nó
            self.conexao.enviar_pacote(resp)

        else:
            # Objeto Livre: Concede custódia imediata
            nome_op = self.CADASTRO_PESSOAS.get(uid_op_str, {}).get("nome", "Desconhecido")
            self.sessoes_ativas[sensor_id] = {
                "uid_objeto": uid_obj_str,
                "uid_operador": uid_op_str,
                "responsavel": nome_op,
                "inicio_sessao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ultimo_visto": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pausado_troca": False
            }
            N4.salvar_sessoes_ativas(self.sessoes_ativas)

            print(f"[CUSTÓDIA] >>> CUSTÓDIA CONCEDIDA AO NÓ ID {sensor_id}! <<<")
            print(f"[CUSTÓDIA] Objeto: [{uid_obj_str}] | Responsável: {nome_op}")

            resp[21] = 1  # Status: 1 = Concedido
            self.conexao.enviar_pacote(resp)

    def tratar_handover(self, raw_pkt):
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

        intencao = self.intencoes_pendentes.get(uid_obj_str)
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
            resp_cedente = self.criar_frame_base(PKT_CUSTODY_CONFIRMED, dest_id=sid_cedente)
            self.conexao.enviar_pacote(resp_cedente)
            time.sleep(0.1)

            # 2. Transfere a sessão ativa
            self.sessoes_ativas.pop(sid_cedente, None)
            nome_op = self.CADASTRO_PESSOAS.get(uid_novo_op_str, {}).get("nome", "Desconhecido")

            self.sessoes_ativas[sid_receptor] = {
                "uid_objeto": uid_obj_str,
                "uid_operador": uid_novo_op_str,
                "responsavel": nome_op,
                "inicio_sessao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ultimo_visto": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pausado_troca": False
            }
            N4.salvar_sessoes_ativas(self.sessoes_ativas)
            self.intencoes_pendentes.pop(uid_obj_str, None)

            # 3. Concede formalmente a custódia no Nó Receptor
            resp_receptor = self.criar_frame_base(PKT_OBJ_CUSTODY_RESP, dest_id=sid_receptor)
            resp_receptor[13:17] = [int(b, 16) for b in uid_novo_op_str.split()]
            resp_receptor[17:21] = uid_obj_bytes
            resp_receptor[21]    = 1  # Concedido!
            self.conexao.enviar_pacote(resp_receptor)

            print(f"[Handover] >>> HANDOVER EFETIVADO COM SUCESSO! <<<")
            print(f"[Handover] Objeto [{uid_obj_str}] transferido para o Nó {sid_receptor} (Resp: {nome_op})")
            print("="*60)
        else:
            print(f"[Handover] REJEITADO: Crachá lido no cedente ({uid_novo_op_str}) difere do operador no receptor ({uid_op_esperado}).")
            print("="*60)

    def tratar_custodia(self, raw_pkt):
        tipo_evento = raw_pkt[1]
        sensor_id   = int(raw_pkt[9])
        uid_str     = " ".join(f"{b:02X}" for b in raw_pkt[13:17])

        if tipo_evento == PKT_CUSTODY_START:
            if sensor_id in self.sessoes_ativas:
                self.sessoes_ativas[sensor_id]["pausado_troca"] = True
                resp = self.sessoes_ativas[sensor_id].get("responsavel", "Desconhecido")
            else:
                resp = "Desconhecido"

            N4.salvar_sessoes_ativas(self.sessoes_ativas)

            print("\n" + "="*55)
            print(f"[CUSTÓDIA] Pedido de troca de custódia iniciado no Nó ID {sensor_id}!")
            print(f"[CUSTÓDIA] Titular atual: [{resp}] | Objeto: [{uid_str}]")
            print(f"[CUSTÓDIA] Polling IMEDIATAMENTE PAUSADO. Aguardando leituras...")
            print("="*55)

        elif tipo_evento == PKT_CUSTODY_ABORT:
            if sensor_id in self.sessoes_ativas:
                self.sessoes_ativas[sensor_id]["pausado_troca"] = False
                resp = self.sessoes_ativas[sensor_id].get("responsavel", "Desconhecido")
            else:
                resp = "Desconhecido"

            N4.salvar_sessoes_ativas(self.sessoes_ativas)

            print("\n" + "-"*55)
            print(f"[CUSTÓDIA] Troca CANCELADA / TIMEOUT no Nó ID {sensor_id}!")
            print(f"[CUSTÓDIA] Custódia mantida com [{resp}]. Retomando polling normal...")
            print("-" * 55)

    def tratar_data_reply(self, raw_pkt):
        dados = N5.processar_telemetria(raw_pkt)
        sensor_id = dados["sensor_id"]
        if sensor_id in self.sessoes_ativas:
            self.sessoes_ativas[sensor_id]["ultimo_visto"] = dados["timestamp"]
            N4.salvar_sessoes_ativas(self.sessoes_ativas)
        sessao = self.sessoes_ativas.get(sensor_id, {})
        dados["responsavel"] = sessao.get("responsavel", "Sem Custódia")
        print(f"\n[TELEMETRIA] Nó {sensor_id} | Temp: {dados['temperatura']} °C | Umidade: {dados['umidade']} %")
        print(f"[METRICAS] DL RSSI {dados['rssi_dl']} dBm, SNR {dados['snr_dl']} dB | UL RSSI {dados['rssi_ul']} dBm, SNR {dados['snr_ul']} dB")
        self.registro_bruto.registrar(raw_pkt, dados["timestamp"])
        self.registro_processado.registrar(dados)
        self.estado.atualizar(dados)


    def distribuir_pacote(self, pacote_recebido):
        if pacote_recebido is None or len(pacote_recebido) != TAMANHO_PACOTE:
            return
        tipo_pkt = pacote_recebido[1]
        if tipo_pkt == PKT_JOIN_REQUEST:
            self.tratar_join_request(pacote_recebido)
        elif tipo_pkt == PKT_AUTH_REQUEST:
            self.tratar_auth_request(pacote_recebido)
        elif tipo_pkt == PKT_OBJ_CUSTODY_REQ:
            self.tratar_obj_custody_req(pacote_recebido)
        elif tipo_pkt == PKT_HANDOVER_AGREED:
            self.tratar_handover(pacote_recebido)
        elif tipo_pkt in (PKT_CUSTODY_START, PKT_CUSTODY_ABORT):
            self.tratar_custodia(pacote_recebido)
        elif tipo_pkt == PKT_DATA_REPLY:
            self.tratar_data_reply(pacote_recebido)

    def executar(self, intervalo_polling=5.0):
        ultimo_polling = time.time()
        print("\n[SYS] Sistema em operação contínua. Pressione Ctrl+C para encerrar.\n")
        while True:
            pacote_recebido = self.conexao.receber_pacote(timeout=0.1)
            self.distribuir_pacote(pacote_recebido)
            agora = time.time()
            if agora - ultimo_polling >= intervalo_polling:
                ultimo_polling = agora
                for node_id, dados in list(self.sessoes_ativas.items()):
                    if dados.get("pausado_troca", False):
                        continue
                    print(f"[POLLING] Solicitando dados de clima para Nó ID {node_id} (Custódia ativa)...")
                    poll_pkt = self.criar_frame_base(PKT_DATA_POLL, dest_id=int(node_id))
                    self.conexao.enviar_pacote(poll_pkt)
                    time.sleep(0.1)
            time.sleep(0.01)

    def fechar(self):
        try:
            self.registro_bruto.fechar()
            self.registro_processado.fechar()
        finally:
            N4.salvar_sessoes_ativas(self.sessoes_ativas)


def selecionar_conexao():
    """Mantém os dois modos do N3 original."""
    from N2 import GerenciadorSerial, GerenciadorMQTT
    print("\n" + "=" * 50)
    print("             SYS - PROTOCOLO MoT (24 BYTES)")
    print("=" * 50)
    print("[1] Comunicação Direta (Serial/USB com Gateway)")
    print("[2] Comunicação em Nuvem (MQTT)")
    escolha = input("Escolha o modo de operação (1 ou 2): ").strip()
    if escolha == "1":
        n_serial = input("Digite o número da porta COM (Ex: 3): ").strip()
        porta_com = n_serial if n_serial.upper().startswith("COM") else f"COM{n_serial}"
        conexao = GerenciadorSerial(porta_com, tamanho_pacote=TAMANHO_PACOTE)
        conexao.conectar()
        conexao.resetar_esp32()
        return conexao
    if escolha == "2":
        conexao = GerenciadorMQTT(BROKER, porta=MQTT_PORTA, topic_dl=MQTT_TOPIC_DL,
                                 topic_ul=MQTT_TOPIC_UL, qos=1, tamanho_pacote=TAMANHO_PACOTE)
        conexao.conectar()
        time.sleep(1.5)
        return conexao
    raise ValueError("Modo inválido (escolha 1 ou 2)")


def main():
    conexao = None
    servidor = None
    servidor_web = None
    thread_web = None
    try:
        conexao = selecionar_conexao()
        servidor = ServidorMoT(conexao)
        app = criar_app(servidor.estado)
        config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
        servidor_web = uvicorn.Server(config)
        thread_web = threading.Thread(target=servidor_web.run, daemon=True, name="N6-Web")
        thread_web.start()
        print("[N6] Painel web: http://127.0.0.1:8000")
        servidor.executar()
    except KeyboardInterrupt:
        print("\n[SYS] Encerrando...")
    finally:
        if servidor_web:
            servidor_web.should_exit = True
        if thread_web:
            thread_web.join(timeout=3)
        if conexao:
            conexao.desconectar()
        if servidor:
            servidor.fechar()
        print("[SYS] Fim da execução.")


if __name__ == "__main__":
    main()
