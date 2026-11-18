"""N2 - Enlaces de conectividade do MoT: USB/Serial ou Wi-Fi/MQTT.

Classes e assinaturas preservadas do código enviado. O N2 não faz arbitragem
nem interpreta o conteúdo do frame MoT de 24 bytes.
"""
import time
from queue import Queue, Empty


class GerenciadorSerial:
    def __init__(self, porta, tamanho_pacote=24, baudrate=115200):
        self.porta = porta
        self.baudrate = baudrate
        self.tamanho_pacote = tamanho_pacote
        self.timeout_serial = 0.5
        self.ser = None

    def resetar_esp32(self):
        if not self.ser or not self.ser.is_open:
            return
        print("[Serial] Iniciando rotina de reset do ESP32...")
        self.ser.setDTR(False)
        self.ser.setRTS(False)
        time.sleep(0.1)
        self.ser.setDTR(True)
        self.ser.setRTS(True)
        time.sleep(1.5)
        self.limpar_buffers()
        print("[Serial] ESP32 resetado e pronto.")

    def limpar_buffers(self):
        if self.ser and self.ser.is_open:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

    def conectar(self):
        import serial  # dependência carregada apenas no modo Serial
        print(f"[Serial] Conectando à porta {self.porta} a {self.baudrate} bps...")
        self.ser = serial.Serial(self.porta, self.baudrate, timeout=self.timeout_serial,
                                 parity=serial.PARITY_NONE)

    def enviar_pacote(self, pacote, timeout=2):
        # Mantida a rotina do transportador original, inclusive limpeza de buffers.
        self.limpar_buffers()
        self.ser.write(bytearray(pacote))
        self.ser.flush()
        return True

    def receber_pacote(self, timeout):
        pacote_ul = b""
        tempo_inicial_rx = time.time()
        while len(pacote_ul) < self.tamanho_pacote and (time.time() - tempo_inicial_rx) < timeout:
            bytes_faltantes = self.tamanho_pacote - len(pacote_ul)
            pacote_ul += self.ser.read(bytes_faltantes)
        if len(pacote_ul) == self.tamanho_pacote:
            return list(pacote_ul)
        self.limpar_buffers()
        return None

    def desconectar(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[Serial] Porta serial fechada com sucesso.")


class GerenciadorMQTT:
    def __init__(self, broker, porta, topic_dl, topic_ul, qos=1, tamanho_pacote=24):
        # Evita exigir paho-mqtt de quem usa somente USB/Serial.
        import paho.mqtt.client as mqtt
        from paho.mqtt.client import CallbackAPIVersion
        self.broker = broker
        self.porta = porta
        self.topic_dl = topic_dl
        self.topic_ul = topic_ul
        self.qos = qos
        self.tamanho_pacote = tamanho_pacote
        # Fila substitui Event+buffer único: não perde uplinks consecutivos.
        self._fila_ul = Queue()
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("[MQTT] Conectado ao Broker MQTT com sucesso.")
            client.subscribe(self.topic_ul, qos=self.qos)
            print(f"[MQTT] Inscrito no tópico: {self.topic_ul} (QoS {self.qos})")
        else:
            print(f"[MQTT] Falha na conexão. Código: {reason_code}")

    def on_message(self, client, userdata, msg):
        if len(msg.payload) >= self.tamanho_pacote:
            self._fila_ul.put(list(msg.payload[:self.tamanho_pacote]))

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"\n[MQTT] Desconectado inesperadamente (rc={reason_code}).")

    def conectar(self):
        print(f"[MQTT] Conectando ao broker {self.broker} - porta {self.porta}...")
        self.client.connect(self.broker, self.porta, keepalive=60)
        self.client.loop_start()

    def enviar_pacote(self, pacote, timeout=2):
        # Não descartar recepções quando se envia um downlink.
        if self.client.is_connected():
            result = self.client.publish(self.topic_dl, bytes(pacote), qos=self.qos)
            try:
                result.wait_for_publish(timeout=timeout)
                return True
            except Exception as e:
                print(f"[MQTT Erro] Falha ao aguardar publicação: {e}")
                return False
        print("[MQTT] Não foi possível publicar. Cliente desconectado.")
        return False

    def receber_pacote(self, timeout):
        try:
            return self._fila_ul.get(timeout=timeout)
        except Empty:
            return None

    def desconectar(self):
        self.client.loop_stop()
        self.client.disconnect()
        print("[MQTT] Desconectado do broker com sucesso.")
