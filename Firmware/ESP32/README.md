# MoT — Nó Sensor e Gateway ESP32 | Guia de instalação na Arduino IDE

Este guia explica como preparar a **Arduino IDE**, instalar o suporte a **ESP32**, adicionar as bibliotecas utilizadas pelos códigos e compilar/gravar os firmwares do **nó sensor e do gateway MoT**.

> **Escopo:** o nó sensor utiliza LoRa, RFID, DHT22 e display; o gateway utiliza LoRa, Wi-Fi e MQTT. **Configure o broker MQTT no firmware do gateway e na aplicação Python, nunca nos nós sensores.**

## 1. Requisitos

- Computador com Windows, Linux ou macOS e acesso à internet para instalação.
- Arduino IDE 2.x: https://www.arduino.cc/en/software
- Placa ESP32 compatível com o projeto (o comentário do código indica **PK-LoRa, ESP32 + RFM95 + RC522 + DHT22**).
- Cabo USB com suporte a dados e, se necessário, driver USB-serial correspondente à placa.
- Hardware e conexões compatíveis com os pinos especificados no código.

## 2. Instalar a Arduino IDE

1. Acesse https://www.arduino.cc/en/software.
2. Baixe a Arduino IDE para seu sistema operacional e instale-a.
3. Abra a Arduino IDE.

## 3. Adicionar suporte ao ESP32

1. Abra **Arquivo > Preferências** (ou **Arduino IDE > Settings/Preferences** no macOS).
2. Em **URLs adicionais para Gerenciadores de Placas**, adicione:

   ```text
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```

   Se já houver URLs, mantenha-as e acrescente esta em uma nova linha ou pela janela de edição.
3. Confirme e abra **Ferramentas > Placa > Gerenciador de Placas**.
4. Pesquise **esp32** e instale **esp32 by Espressif Systems**.
5. Conecte a placa ao computador e escolha **Ferramentas > Placa**. Selecione o modelo exato da placa. **ESP32 Dev Module** é apenas uma opção genérica para placas ESP32 clássicas compatíveis; confirme o modelo real antes de gravar.
6. Em **Ferramentas > Porta**, selecione a porta serial da placa.

> A versão do pacote ESP32 utilizada originalmente no projeto não foi informada. Se surgir incompatibilidade, registre a versão instalada e teste uma versão compatível com a placa e as bibliotecas; não há versão específica comprovada pelos arquivos enviados.

## 4. Instalar as bibliotecas utilizadas

Abra **Sketch > Incluir Biblioteca > Gerenciar Bibliotecas...** (ou o ícone de Bibliotecas na barra lateral). Pesquise e instale:

| Biblioteca / cabeçalho usado | Como localizar | Finalidade |
|---|---|---|
| `LoRa.h` | **LoRa** — Sandeep Mistry | Comunicação com o rádio LoRa RFM95 |
| `MFRC522.h` | **MFRC522** — Miguel Balboa / comunidade | Leitura de tags RFID com RC522 |
| `DHTesp.h` | **DHTesp** — beegee_tokyo | Leitura de temperatura e umidade do DHT22 |
| `Adafruit_GFX.h` | **Adafruit GFX Library** — Adafruit | Gráficos e fontes do display |
| `Adafruit_GC9A01A.h` | **Adafruit GC9A01A** — Adafruit | Controle do display GC9A01A |

Os seguintes cabeçalhos também aparecem nos códigos, mas **não precisam ser instalados como bibliotecas externas separadas** quando o pacote ESP32 adequado já está instalado:

- `SPI.h`: barramento SPI, fornecido pelo framework Arduino.
- `Preferences.h`: armazenamento não volátil (NVS) do ESP32.
- `esp_mac.h`: funcionalidades de MAC do ESP32, fornecidas pelo pacote da Espressif.
- `Fonts/FreeSansBold24pt7b.h`, `Fonts/FreeSansBold12pt7b.h`, `Fonts/FreeSans9pt7b.h`: fontes incluídas com **Adafruit GFX Library**.
- `Arduino.h`: núcleo do Arduino.
- `mot_packets.h`: **arquivo local do próprio projeto**, não uma biblioteca do Gerenciador.

> **Importante:** os arquivos fornecidos não especificam as versões exatas das bibliotecas. O README identifica dependências a partir dos `#include`, sem atribuir versões que não foram confirmadas.

## 5. Abrir o firmware do sensor na Arduino IDE

Baixe o projeto disponibilizado no GitHub e abra `BSS_Sensor_Display.ino` na Arduino IDE. O repositório já disponibiliza os arquivos preparados para uso; não é necessário reorganizar pastas nem renomear arquivos.

## 6. Conferir as configurações de hardware

Os valores abaixo foram extraídos do arquivo `BSS_Sensor_Display.ino`. **Não altere os pinos sem conferir o esquema elétrico da sua placa.**

| Periférico | Pino ESP32 |
|---|---|
| SPI SCK | GPIO 5 |
| SPI MISO | GPIO 19 |
| SPI MOSI | GPIO 27 |
| LoRa NSS / CS | GPIO 18 |
| LoRa RESET | GPIO 14 |
| LoRa DIO0 | GPIO 26 |
| RFID SS | GPIO 23 |
| RFID RESET | GPIO 13 |
| Display CS | GPIO 25 |
| Display DC | GPIO 33 |
| Display RESET | GPIO 22 |
| DHT22 (dados) | GPIO 32 |
| LED vermelho | GPIO 15 |
| LED amarelo | GPIO 2 |
| LED verde | GPIO 4 |
| Botão | GPIO 39 |

**Parâmetros LoRa presentes no código:** frequência `915E6` (915 MHz), potência `10 dBm`, spreading factor `7`, largura de banda `125 kHz` e coding rate `4/8` (`LoRa.setCodingRate4(8)`). O gateway precisa usar parâmetros de rádio compatíveis. Confira também a regulamentação aplicável à região de operação.

O protocolo MoT definido no cabeçalho utiliza **frames de 24 bytes** (`MOT_PACKET_SIZE 24`).

## 7. Compilar e gravar o firmware

1. Abra o sketch principal `BSS_Sensor_Display.ino`.
2. Selecione a placa ESP32 correta e a porta serial em **Ferramentas**.
3. Clique em **Verificar** (ícone ✓) para compilar.
4. Corrija eventuais mensagens de biblioteca ausente ou seleção incorreta de placa.
5. Clique em **Carregar** (seta) para gravar o firmware.
6. Se a placa exigir modo de gravação manual, siga as instruções do fabricante para os botões **BOOT/EN**.
7. Abra **Ferramentas > Monitor Serial** e configure **115200 baud**, conforme `Serial.begin(115200)`.

Na inicialização, o código imprime mensagens de identificação do nó, MAC do ESP32 e status do rádio RFM95, RFID RC522, DHT22 e display GC9A01A. O comportamento posterior depende dos periféricos e da comunicação com o gateway.

## 8. Como o nó sensor participa do sistema

```text
[Nó sensor ESP32]
  ├─ RFM95 (LoRa)
  ├─ RC522 (RFID)
  ├─ DHT22 (temperatura/umidade)
  └─ GC9A01A (display)
        |
        | comunicação LoRa / frames MoT de 24 bytes
        v
[Gateway com firmware próprio]
        |
        | MQTT (configurado SOMENTE no gateway)
        v
[Broker MQTT] <----> [Aplicação Python]
```

O firmware do gateway é descrito na seção seguinte. Não há endereço MQTT para configurar nos `.ino` do sensor.

Se utilizar um broker próprio, o broker do WistekIoT em `www.tpm.dev.br`, ou um broker público como `broker.emqx.io`, `broker.hivemq.com` ou `test.mosquitto.org`, configure o **endereço e a porta no firmware do gateway e no cliente Python**. Confirme as portas, a disponibilidade e a autenticação exigidas pelo serviço escolhido. Brokers públicos de teste não devem receber dados sensíveis.

## 9. Preparar e gravar o firmware do gateway

O gateway é o intermediário entre os sensores LoRa e o broker MQTT. Os arquivos enviados para ele são `BSS_Gateway.ino`, `1_PHY_Gateway.ino` e `mot_packets_Gateway.h`.

### 9.1. Abrir o firmware do gateway

Baixe o projeto disponibilizado no GitHub e abra `BSS_Gateway.ino` na Arduino IDE. A estrutura do projeto já estará preparada no repositório; não é necessário reorganizar nem renomear arquivos.

### 9.2. Bibliotecas do gateway

Além do suporte à placa **esp32 by Espressif Systems** instalado na seção 3, instale no Gerenciador de Bibliotecas:

| Cabeçalho | Biblioteca | Uso |
|---|---|---|
| `LoRa.h` | **LoRa** — Sandeep Mistry | Rádio LoRa |
| `MQTT.h` | **MQTT** — Joel Gaehwiler (256dpi) | Cliente MQTT (`MQTTClient`) |

Os cabeçalhos `SPI.h`, `WiFi.h` e `WiFiMulti.h` são fornecidos pelo ambiente Arduino/ESP32. `mot_packets.h` é um arquivo local do projeto. As versões exatas das bibliotecas não foram informadas nos códigos.

### 9.3. Configurar a rede Wi-Fi (obrigatório)

No arquivo `BSS_Gateway.ino`, dentro de `setup()`, localize a chamada `wifiMulti.addAP(...)` e substitua o nome da rede e a senha pelos dados **da sua própria rede**:

```cpp
wifiMulti.addAP("NOME_DA_SUA_REDE_2_4GHZ", "SENHA_DO_SEU_WIFI");
```

O gateway precisa se conectar ao Wi-Fi para acessar o broker MQTT. Verifique se a rede é compatível com o ESP32 (normalmente 2,4 GHz), se a senha está correta e se há acesso à rede do broker. **Não publique a senha real em repositórios públicos.** O código enviado contém credenciais de Wi-Fi preenchidas; substitua-as antes de compartilhar o firmware e altere a senha da rede se essas credenciais tiverem sido expostas publicamente.

### 9.4. Configurar broker e tópicos MQTT (obrigatório)

No início de `BSS_Gateway.ino`, ajuste as constantes:

```cpp
const char* MQTT_BROKER = "SEU_BROKER_MQTT";
const int MQTT_PORT = 1883;
const char* TOPIC_DL = "mot/seu_projeto_123/gateway/downlink"; // Python -> Gateway
const char* TOPIC_UL = "mot/seu_projeto_123/gateway/uplink";   // Gateway -> Python
```

O código enviado utiliza **porta 1883, QoS 1** e o cliente `WiFiClient`, sem configuração de TLS ou credenciais MQTT. Portanto, o broker escolhido deve aceitar esse modo de conexão ou o firmware precisará ser adaptado. Para Mosquitto local, use o IP ou nome de rede alcançável pelo ESP32; `localhost` no gateway não aponta para o computador com o broker.

**Os tópicos precisam corresponder exatamente aos configurados na aplicação Python (`N3.py`):**

| Direção | Gateway | Aplicação Python |
|---|---|---|
| Gateway → Python | Publica em `TOPIC_UL` | Assina o mesmo tópico de uplink |
| Python → Gateway | Assina `TOPIC_DL` | Publica no mesmo tópico de downlink |

A correspondência inclui letras maiúsculas/minúsculas e todas as barras `/`. Não basta usar o mesmo broker: os tópicos também precisam coincidir. O firmware transmite **frames binários MoT de 24 bytes**; não envie texto JSON para esses tópicos sem adaptar o receptor.

**Atenção especial aos brokers públicos/de terceiros:** em serviços como `broker.emqx.io`, `broker.hivemq.com` ou `test.mosquitto.org`, os tópicos podem ser compartilhados com outros usuários. Antes de utilizar um tópico, escolha um prefixo próprio, suficientemente específico e difícil de coincidir com o de outros projetos (por exemplo, `mot/laboratorio_x/experimento_2026_abc123/...`). Evite tópicos genéricos como `test`, `sensor/data` ou `gateway/uplink`. Mesmo um tópico aparentemente exclusivo **não garante privacidade nem reserva de nome** em um broker público: terceiros podem publicar ou assinar nele. Não envie senhas, identificadores sensíveis ou dados confidenciais sem controles de autenticação, autorização e criptografia adequados.

Se preferir não hospedar um broker, você pode avaliar o broker WistekIoT informado para o projeto (`www.tpm.dev.br`) ou outros brokers MQTT de teste. **Confirme previamente o host MQTT, a porta, a autenticação e a disponibilidade do serviço**; o endereço web, isoladamente, não confirma um endpoint MQTT funcional.

### 9.5. Verificar rádio LoRa e gravar

O gateway enviado utiliza os pinos `SCK=5`, `MISO=19`, `MOSI=27`, `NSS=18`, `RST=14` e `DIO0=26`, com frequência configurada em **915 MHz**. Confirme compatibilidade com a placa, a antena, os sensores e as regras locais de radiofrequência. Selecione a placa e a porta na Arduino IDE, clique em **Verificar** e depois em **Carregar**. Abra o Monitor Serial em **115200 baud**.

A sequência de inicialização conecta o Wi-Fi, conecta o MQTT e inicializa o rádio LoRa. Se o broker estiver inacessível, o código atual tenta reconectar e pode permanecer nessa etapa antes de iniciar o rádio. Confira os logs `[SYS]`, `[MQTT]` e `[PHY]`.

### 9.6. Teste integrado

1. Inicie o broker MQTT escolhido.
2. Configure no gateway o Wi-Fi, o broker e os dois tópicos.
3. Configure no Python (`N3.py`) **o mesmo broker, porta e tópicos correspondentes**.
4. Grave o firmware do gateway e confirme a conexão no Monitor Serial.
5. Grave o firmware do sensor, execute o Python e verifique o tráfego entre sensor ↔ gateway ↔ broker ↔ Python.

> O arquivo `N3.py` não foi disponibilizado nesta etapa; por isso, os nomes das variáveis e o local exato para alterar os tópicos no Python devem ser conferidos diretamente nele.

## 10. Solução de problemas

| Problema | O que verificar |
|---|---|
| `LoRa.h: No such file or directory` | Instale **LoRa** pelo Gerenciador de Bibliotecas. |
| `MFRC522.h: No such file or directory` | Instale **MFRC522**. |
| `DHTesp.h: No such file or directory` | Instale **DHTesp**. |
| `Adafruit_GC9A01A.h: No such file or directory` | Instale **Adafruit GC9A01A** e suas dependências. |
| `mot_packets.h: No such file or directory` | Confira se o download do repositório está completo e se o projeto foi aberto corretamente. |
| `esp_mac.h: No such file or directory` | Verifique se a placa e o pacote **esp32 by Espressif Systems** estão selecionados corretamente. |
| Porta serial não aparece | Confira cabo USB de dados, drivers USB-serial, conexão e permissões do sistema. |
| Falha ao iniciar RFM95 | Verifique alimentação, ligações SPI, NSS, RESET e compatibilidade do módulo. |
| Nenhuma mensagem LoRa recebida | Verifique gateway ligado, frequência, SF, banda, coding rate e antenas. |
| Display ou RFID não funciona | Verifique os pinos e os CS no barramento SPI compartilhado. |
| Erro de compilação após instalar bibliotecas | Registre a mensagem completa, versão do pacote ESP32 e versões das bibliotecas para diagnosticar compatibilidade. |

## 11. Referências

- Arduino IDE: https://www.arduino.cc/en/software
- Instalação do Arduino-ESP32 (Espressif): https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html
- LoRa (Sandeep Mistry): https://github.com/sandeepmistry/arduino-LoRa
- MFRC522: https://github.com/miguelbalboa/rfid
- DHTesp: https://github.com/beegee-tokyo/DHTesp
- Adafruit GFX: https://github.com/adafruit/Adafruit-GFX-Library
- Adafruit GC9A01A: https://github.com/adafruit/Adafruit_GC9A01A

---

**Nota de validação:** este guia foi elaborado a partir dos arquivos de firmware fornecidos. Não foi realizada compilação física na Arduino IDE nem teste com a placa. A seleção exata do modelo ESP32 e a compatibilidade de versões devem ser validadas no hardware utilizado.
