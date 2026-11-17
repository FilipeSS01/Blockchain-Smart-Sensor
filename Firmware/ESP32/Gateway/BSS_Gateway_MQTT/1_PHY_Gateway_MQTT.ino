/*
  Camada Física, Enlace LoRa e Transporte MQTT
  Arquivo: 1_PHY.ino
*/

#define REG_OP_MODE       0x01
#define MODE_LORA         0x80
#define MODE_STANDBY      0x01
#define MODE_CAD          0x07
#define REG_IRQ_FLAGS     0x12
#define IRQ_CAD_DONE_MASK 0x04
#define IRQ_CAD_DETECTED  0x01

SPISettings rfm95_spiSettings(8E6, MSBFIRST, SPI_MODE0);

uint8_t rfm95_readRegister(uint8_t address) {
  digitalWrite(NSS_PIN, LOW);
  SPI.beginTransaction(rfm95_spiSettings);
  SPI.transfer(address & 0x7F);
  uint8_t response = SPI.transfer(0x00);
  SPI.endTransaction();
  digitalWrite(NSS_PIN, HIGH);
  return response;
}

void rfm95_writeRegister(uint8_t address, uint8_t value) {
  digitalWrite(NSS_PIN, LOW);
  SPI.beginTransaction(rfm95_spiSettings);
  SPI.transfer(address | 0x80);
  SPI.transfer(value);
  SPI.endTransaction();
  digitalWrite(NSS_PIN, HIGH);
}

// ================= ESCUTA DE CANAL (CAD) =================
bool Phy_canal_ocupado_CAD() {
  rfm95_writeRegister(REG_OP_MODE, MODE_LORA | MODE_STANDBY);
  rfm95_writeRegister(REG_IRQ_FLAGS, 0xFF);
  rfm95_writeRegister(REG_OP_MODE, MODE_LORA | MODE_CAD);

  unsigned long timeout = millis() + 50;
  while (!(rfm95_readRegister(REG_IRQ_FLAGS) & IRQ_CAD_DONE_MASK)) {
    if (millis() > timeout) break;
    yield();
  }

  uint8_t flags = rfm95_readRegister(REG_IRQ_FLAGS);
  rfm95_writeRegister(REG_IRQ_FLAGS, 0xFF);
  rfm95_writeRegister(REG_OP_MODE, MODE_LORA | MODE_STANDBY);

  return (flags & IRQ_CAD_DETECTED);
}

// ================= GESTÃO DE DUPLICATAS =================
bool Gateway_pacote_duplicado(uint8_t src, uint8_t id) {
  for (int i = 0; i < CACHE_SIZE; i++) {
    if (cacheDuplicatas[i].src == src && cacheDuplicatas[i].id == id) {
      return true;
    }
  }
  return false;
}

void Gateway_salvar_cache(uint8_t src, uint8_t id) {
  cacheDuplicatas[cacheIndex].src = src;
  cacheDuplicatas[cacheIndex].id  = id;
  cacheIndex = (cacheIndex + 1) % CACHE_SIZE;
}

// ================= DOWNLINK (MQTT -> LORA) =================
void Phy_mqtt_receive_DL() {
  if (mqtt_dl_disponivel) {
    mqtt_dl_disponivel = false;

    // Copia o buffer recebido do MQTT para o frame DL de 24 bytes
    memcpy(frameDL.raw, frameDL_mqtt.raw, MOT_PACKET_SIZE);

    seq_packet_gw++;
    // Se o pacote vindo do backend/Python não especificou IDs, preenche o cabeçalho base
    if (frameDL.header.src_addr == 0) {
      frameDL.header.src_addr  = ID_gateway;
    }
    frameDL.header.packet_id = seq_packet_gw;
    frameDL.header.hop_limit = HOP_LIMIT_PADRAO;

    // Salva para não reprocessar caso capture o próprio eco
    Gateway_salvar_cache(ID_gateway, seq_packet_gw);

    Serial.printf("[DL] Despachando Downlink via LoRa. Tipo: 0x%02X | Destino: %d\n",
                  frameDL.header.pkt_type, frameDL.header.dest_addr);

    Phy_radio_send_DL();
  }
}

void Phy_radio_send_DL() {
  byte tentativas = 0;
  while (Phy_canal_ocupado_CAD() && tentativas < 5) {
    delay(random(15, 50));
    tentativas++;
  }

  LoRa.beginPacket();
  LoRa.write(frameDL.raw, MOT_PACKET_SIZE);
  LoRa.endPacket();

  digitalWrite(LED_VERMELHO_PIN, HIGH);
  delay(40);
  digitalWrite(LED_VERMELHO_PIN, LOW);
}

// ================= UPLINK (LORA -> MQTT) =================
void Phy_radio_receive_UL() {
  uint8_t packetSize = LoRa.parsePacket();

  if (packetSize >= MOT_PACKET_SIZE) {
    // Lê os 24 bytes diretamente para o frameUL
    LoRa.readBytes(frameUL.raw, MOT_PACKET_SIZE);

    RSSI_dBm_UL = LoRa.packetRssi();
    SNR_UL      = LoRa.packetSnr();

    uint8_t tipo   = frameUL.header.pkt_type;
    uint8_t origem = frameUL.header.src_addr;
    uint8_t dest   = frameUL.header.dest_addr;
    uint8_t id_pkt = frameUL.header.packet_id;

    Serial.println("=================== NOVO UPLINK ===================");
    Serial.printf("[NET] Tipo: 0x%02X | Origem: %d | Destino: %d | ID: %d\n",
                  tipo, origem, dest, id_pkt);

    // 1. Filtro de duplicatas (exceto Join, que pode vir de nós virgens com mesmo ID 0)
    if (tipo != PKT_JOIN_REQUEST) {
      if (Gateway_pacote_duplicado(origem, id_pkt)) {
        Serial.println("[NET] Pacote duplicado detectado. Descartando...");
        return;
      }
      Gateway_salvar_cache(origem, id_pkt);
    }

    // 2. Filtro de Destino: destinado ao Gateway ou Broadcast (ex: Join Request)
    if (dest == ID_gateway || dest == 0xFF) {
      Phy_mqtt_send_UL();
    }
  }
}

void Phy_mqtt_send_UL() {
  // Converte RSSI de Uplink medido pelo Gateway (Byte 5)
  if (RSSI_dBm_UL > -10.5) {
    RSSI_UL = 127;
  } else if (RSSI_dBm_UL <= -10.5 && RSSI_dBm_UL >= -74) {
    RSSI_UL = ((RSSI_dBm_UL + 74) * 2);
  } else {
    RSSI_UL = (((RSSI_dBm_UL + 74) * 2) + 256);
  }
  frameUL.header.rssi_ul = (uint8_t)RSSI_UL;

  // Converte SNR de Uplink medido pelo Gateway (Bytes 6 e 7)
  SNR_UL_inteiro = (int)(SNR_UL * 100);
  frameUL.header.snr_ul_msb = (uint8_t)(SNR_UL_inteiro / 256);
  frameUL.header.snr_ul_lsb = (uint8_t)(SNR_UL_inteiro % 256);

  // Publica o frame binário de 24 bytes via MQTT com QoS 1
  if (mqttClient.connected()) {
    bool ok = mqttClient.publish(TOPIC_UL, (char*)frameUL.raw, MOT_PACKET_SIZE, false, MQTT_QOS);
    if (ok) {
      Serial.printf("[MQTT] Uplink (Tipo 0x%02X) publicado com sucesso (24 Bytes).\n", frameUL.header.pkt_type);
    } else {
      Serial.println("[MQTT] Falha ao publicar pacote UL.");
    }
  } else {
    Serial.println("[MQTT] Desconectado. Pacote UL descartado.");
  }

  digitalWrite(LED_VERDE_PIN, HIGH);
  delay(40);
  digitalWrite(LED_VERDE_PIN, LOW);
}

// ================= CALLBACK E RECONEXÃO MQTT =================
void mqtt_callback(MQTTClient *client, char topic[], char bytes[], int length) {
  if (strcmp(topic, TOPIC_DL) == 0) {
    if (length >= MOT_PACKET_SIZE) {
      memcpy(frameDL_mqtt.raw, bytes, MOT_PACKET_SIZE);
      mqtt_dl_disponivel = true;
      Serial.println("[MQTT] Downlink recebido via tópico!");
    } else {
      Serial.printf("[MQTT] Downlink descartado: tamanho incompatível (%d bytes).\n", length);
    }
  }
}

void conectar_mqtt() {
  while (!mqttClient.connected()) {
    Serial.print("[MQTT] Conectando ao broker...");
    if (mqttClient.connect(CLIENT_ID.c_str())) {
      Serial.println(" conectado!");
      mqttClient.subscribe(TOPIC_DL, MQTT_QOS);
      Serial.printf("[MQTT] Inscrito em: %s (QoS%d)\n", TOPIC_DL, MQTT_QOS);
    } else {
      Serial.printf(" falhou (erro=%d). Nova tentativa em 3s...\n", (int)mqttClient.lastError());
      delay(3000);
    }
  }
}