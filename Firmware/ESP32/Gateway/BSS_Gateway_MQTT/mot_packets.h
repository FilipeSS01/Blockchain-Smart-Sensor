#pragma once
#include <Arduino.h>

#define MOT_PACKET_SIZE 24

// Identificadores de Pacote (Byte 1)
enum MotPacketType : uint8_t {
  PKT_JOIN_REQUEST        = 0x01,
  PKT_JOIN_ACCEPT         = 0x02,

  // Autenticação de Operador (Pessoa)
  PKT_AUTH_REQUEST        = 0x10,
  PKT_AUTH_RESPONSE       = 0x11,

  // Solicitação de Custódia do Objeto
  PKT_OBJ_CUSTODY_REQ     = 0x12,
  PKT_OBJ_CUSTODY_RESP    = 0x13, // 1=Concedido, 2=Retido por outro nó, 0=Negado

  // Operação Telemétrica
  PKT_DATA_POLL           = 0x20,
  PKT_DATA_REPLY          = 0x21,

  // Processo de Handover (Troca de Custódia)
  PKT_CUSTODY_START       = 0x30, // Botão 3s no Nó Cedente
  PKT_HANDOVER_AGREED     = 0x33, // Cedente leu Objeto + Novo Operador
  PKT_CUSTODY_CONFIRMED   = 0x31, // Notificação ao Cedente que foi liberado
  PKT_CUSTODY_ABORT       = 0x32  // Timeout ou Cancelamento
};

#pragma pack(push, 1)

// ================= CABEÇALHO PADRÃO (BYTES 0 A 12) =================
struct MotHeader {
  // MoT Core
  uint8_t config;           // Byte 0: Configuração
  uint8_t pkt_type;         // Byte 1: Tipo do pacote

  // FÍSICA
  uint8_t rssi_dl;          // Byte 2: RSSIDL (medido no sensor)
  uint8_t snr_dl_msb;       // Byte 3: SNRDL (MSB)
  uint8_t snr_dl_lsb;       // Byte 4: SNRDL (LSB)
  uint8_t rssi_ul;          // Byte 5: RSSIUL (medido no gateway)
  uint8_t snr_ul_msb;       // Byte 6: SNRUL (MSB)
  uint8_t snr_ul_lsb;       // Byte 7: SNRUL (LSB)

  // REDE
  uint8_t packet_id;        // Byte 8: Identificador do pacote
  uint8_t src_addr;         // Byte 9: Endereço de origem
  uint8_t dest_addr;        // Byte 10: Endereço de destino
  uint8_t net_reserved;     // Byte 11: 0 (livre/reservado)
  uint8_t hop_limit;        // Byte 12: Limite de saltos
};

// ================= PAYLOADS MODULARES (BYTES 13 A 23) =================

// 1. Momento 1: Comissionamento / Registro
struct PayloadJoin {
  uint8_t mac[6];           // Bytes 13..18: MAC de fábrica do ESP32
  uint8_t assigned_id;      // Byte 19: Novo ID atribuído pelo Gateway
  uint8_t gateway_id;       // Byte 20: ID oficial do Gateway
  uint8_t hop_limit;        // Byte 21: Limite de saltos padrão
  uint8_t padding[2];       // Bytes 22..23: Zerados
};

// 2. Momento 2A: Autenticação do Operador (Pessoa)
struct PayloadAuth {
  uint8_t uid[4];           // Bytes 13..16: UID do cartão do Operador
  uint8_t auth_status;      // Byte 17: Resposta (1 = Aprovado, 0 = Negado)
  uint8_t padding[6];       // Bytes 18..23: Zerados
};

// 3. Momento 2B: Associação de Custódia do Objeto
struct PayloadObjCustody {
  uint8_t uid_operador[4];  // Bytes 13..16: UID do Operador autenticado
  uint8_t uid_objeto[4];    // Bytes 17..20: UID do Objeto monitorado
  uint8_t status;           // Byte 21: 1=Concedido, 2=Retido por outro nó, 0=Negado
  uint8_t padding[2];       // Bytes 22..23: Zerados
};

// 4. Handover Físico (Nó A -> Python)
struct PayloadHandover {
  uint8_t uid_objeto[4];    // Bytes 13..16: Objeto que está sendo liberado
  uint8_t uid_novo_op[4];   // Bytes 17..20: Tag do novo operador lida no leitor
  uint8_t padding[3];       // Bytes 21..23: Zerados
};

// 5. Operação: Clima e Telemetria com Custódia
struct PayloadClima {
  // TRANSP
  uint8_t transp_reserved;  // Byte 13: 0 (livre/reservado)
  uint8_t echo_dl_cnt_msb;  // Byte 14: Eco contador DL (MSB)
  uint8_t echo_dl_cnt_lsb;  // Byte 15: Eco contador DL (LSB)
  uint8_t ul_pkt_cnt_msb;   // Byte 16: Contador pacotes UL (MSB)
  uint8_t ul_pkt_cnt_lsb;   // Byte 17: Contador pacotes UL (LSB)

  // APP
  uint8_t hw_code;          // Byte 18: Código do hardware
  uint8_t temperature;      // Byte 19: Temp (°C + 40 offset)
  uint8_t humidity;         // Byte 20: Umidade (%)
  uint8_t uid_custodia[3];  // Bytes 21..23: Primeiros 3 bytes do UID do objeto monitorado
};

// ================= UNION GERAL (24 BYTES EXATOS) =================
union MotFrame {
  uint8_t      raw[MOT_PACKET_SIZE]; // Array plano para I/O do rádio
  MotHeader    header;               // Acesso genérico (Bytes 0..12)

  struct {
    MotHeader   header;
    PayloadJoin payload;
  } join;

  struct {
    MotHeader   header;
    PayloadAuth payload;
  } auth;

  struct {
    MotHeader         header;
    PayloadObjCustody payload;
  } obj_custody;

  struct {
    MotHeader       header;
    PayloadHandover payload;
  } handover;

  struct {
    MotHeader    header;
    PayloadClima payload;
  } clima;
};

#pragma pack(pop)