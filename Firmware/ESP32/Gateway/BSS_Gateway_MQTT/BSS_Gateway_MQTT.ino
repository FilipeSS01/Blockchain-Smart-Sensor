/*
  MoT LoRa Gateway - Versão Ponto a Ponto / Centralizada
  ESP32 + RFM95 (PK-LoRa) com Transporte Wi-Fi / MQTT (QoS 1)
  Frame Padronizado: 24 Bytes
  Arquivo: MoT_Gateway.ino
*/

#include <SPI.h>
#include <LoRa.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <MQTT.h>
#include "mot_packets.h"

// ================= CONFIGURAÇÕES WI-FI E MQTT =================
WiFiMulti wifiMulti;
WiFiClient wifiClient;

const char* MQTT_BROKER = "179.197.87.156";
const int   MQTT_PORT   = 1883;
const char* TOPIC_DL    = "mot_lora_mqtt_FILIPE_SILVA/gateway/downlink";  // Python -> Gateway
const char* TOPIC_UL    = "mot_lora_mqtt_FILIPE_SILVA/gateway/uplink";    // Gateway -> Python
String CLIENT_ID;

const int MQTT_QOS = 1;
MQTTClient mqttClient(512); // Buffer ampliado para o payload MQTT

// Buffer e controle de recepção Downlink MQTT
volatile bool mqtt_dl_disponivel = false;
MotFrame frameDL_mqtt;

// ================= PINAGEM PK-LoRa =================
#define SCK_PIN    5
#define MISO_PIN  19
#define MOSI_PIN  27
#define NSS_PIN   18
#define RST_PIN   14
#define DIO0_PIN  26

#define LED_VERMELHO_PIN 15
#define LED_VERDE_PIN     4

// ================= PARÂMETROS LORA =================
#define FREQUENCY_IN_HZ       915E6
#define txPower               17
#define spreadingFactor       7
#define signalBandwidth       125E3
#define codingRateDenominator 8

// Métricas de enlace medidos no Gateway
int RSSI_dBm_UL;
int RSSI_UL;
float SNR_UL;
int SNR_UL_inteiro;

// Frames Globais MoT (24 Bytes)
MotFrame frameDL;
MotFrame frameUL;

// Parâmetros de Rede do Gateway
uint8_t ID_gateway = 100;
#define HOP_LIMIT_PADRAO 1
uint8_t seq_packet_gw = 0;

// Cache Circular de Duplicatas
#define CACHE_SIZE 16
struct PacketHistory {
  uint8_t src;
  uint8_t id;
};
PacketHistory cacheDuplicatas[CACHE_SIZE];
uint8_t cacheIndex = 0;

// Assinaturas de Funções (1_PHY.ino)
void mqtt_callback(MQTTClient *client, char topic[], char bytes[], int length);
void conectar_mqtt();
void Phy_mqtt_receive_DL();
void Phy_radio_receive_UL();

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(50);

  pinMode(LED_VERMELHO_PIN, OUTPUT);
  pinMode(LED_VERDE_PIN, OUTPUT);
  digitalWrite(LED_VERMELHO_PIN, LOW);
  digitalWrite(LED_VERDE_PIN, LOW);

  // Conexão Wi-Fi
  wifiMulti.addAP("Silva 2.4G", "Silv@1234");

  Serial.print("\n[SYS] Conectando ao Wi-Fi");
  while (wifiMulti.run() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[SYS] Wi-Fi Conectado! IP: " + WiFi.localIP().toString());

  // ID do cliente MQTT
  CLIENT_ID = "BSS_Gateway " + String(WiFi.macAddress());
  CLIENT_ID.replace(":", "");

  // Inicializa MQTT
  mqttClient.begin(MQTT_BROKER, MQTT_PORT, wifiClient);
  mqttClient.onMessageAdvanced(mqtt_callback);
  conectar_mqtt();

  // Inicializa barramento SPI e RFM95
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, NSS_PIN);
  LoRa.setPins(NSS_PIN, RST_PIN, DIO0_PIN);

  if (!LoRa.begin(FREQUENCY_IN_HZ)) {
    Serial.println("[PHY] Falha crítica ao iniciar LoRa no Gateway!");
    while (true) { delay(1000); }
  }

  LoRa.setTxPower(txPower);
  LoRa.setSpreadingFactor(spreadingFactor);
  LoRa.setSignalBandwidth(signalBandwidth);
  LoRa.setCodingRate4(codingRateDenominator);

  // Limpa cache de duplicatas
  for (int i = 0; i < CACHE_SIZE; i++) {
    cacheDuplicatas[i] = {0xFF, 0xFF};
  }

  Serial.println("--- MoT Gateway (24 Bytes) Inicializado com Sucesso ---");
  digitalWrite(LED_VERDE_PIN, HIGH);
  delay(1000);
  digitalWrite(LED_VERDE_PIN, LOW);
}

// ================= LOOP =================
void loop() {
  // Monitoramento de conectividade Wi-Fi
  if (wifiMulti.run() != WL_CONNECTED) {
    Serial.println("[WIFI] Desconectado! Reconectando...");
    delay(500);
  }

  // Monitoramento MQTT
  if (!mqttClient.connected()) {
    conectar_mqtt();
  }
  mqttClient.loop();

  // Processa Downlink (MQTT -> LoRa)
  Phy_mqtt_receive_DL();

  // Processa Uplink (LoRa -> MQTT)
  Phy_radio_receive_UL();

  yield();
}