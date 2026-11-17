# Configuração do Broker MQTT

Este guia apresenta três opções para conectar o projeto Python (`N3.py`) e o firmware do gateway a um broker MQTT:

1. **Broker disponibilizado pelo WistekIoT**: não é necessário instalar nada localmente.
2. **Broker público gratuito**: ideal para testes e protótipos.
3. **Broker local Eclipse Mosquitto**: execução com Docker ou instalação diretamente no computador.

> **Importante:** escolha um único broker e configure **o mesmo endereço, porta e parâmetros de autenticação** no Python e **somente no firmware do gateway**. O endereço `www.tpm.dev.br` foi informado como endpoint do WistekIoT, mas a disponibilidade do serviço MQTT e sua porta não foram verificadas. Confirme os dados de conexão com o responsável pelo servidor; o fato de um endereço abrir no navegador não garante que ele aceite MQTT.

> **Arquitetura:** somente o **gateway** se conecta ao broker MQTT. Os **nós sensores** se comunicam com o gateway via LoRa e **não precisam de configuração MQTT**. O programa Python (`N3.py`) também se conecta ao broker para publicar ou receber mensagens, conforme sua implementação.

## 1. Opção mais simples: utilizar o broker WistekIoT

Caso não queira instalar Docker ou Mosquitto, utilize o broker informado pelo projeto:

| Parâmetro | Configuração |
| --- | --- |
| Host | `www.tpm.dev.br` |
| Porta | **Confirmar com o administrador** (MQTT TCP costuma usar `1883`; MQTT/TLS, `8883`) |
| Usuário e senha | Confirmar se são necessários |
| TLS | Confirmar se é exigido |

No código Python, procure as variáveis de conexão MQTT e ajuste conforme o serviço disponibilizado:

```python
MQTT_BROKER = "www.tpm.dev.br"
MQTT_PORT = 1883  # Exemplo: substituir pela porta confirmada
```

**Somente no firmware do gateway** (exemplo genérico em C++ para ESP32/ESP8266):

```cpp
const char* mqtt_server = "www.tpm.dev.br";
const int mqtt_port = 1883; // Exemplo: confirmar a porta real

// Com PubSubClient, após configurar o cliente de rede:
// mqttClient.setServer(mqtt_server, mqtt_port);
```

> Esses trechos são **exemplos de configuração**, não alterações automáticas em `N3.py` ou no firmware. Se o broker exigir TLS, credenciais ou certificados, adapte também o cliente MQTT.

## 2. Alternativa: brokers MQTT públicos gratuitos

Para testes, é possível utilizar um dos servidores abaixo:

| Broker | Host | Porta MQTT TCP (sem TLS) |
| --- | --- | --- |
| EMQX | `broker.emqx.io` | `1883` |
| HiveMQ | `broker.hivemq.com` | `1883` |
| Eclipse Mosquitto | `test.mosquitto.org` | `1883` |

Também é possível utilizar outro broker MQTT de sua preferência, desde que suporte as configurações exigidas pelo projeto.

Por exemplo, no Python:

```python
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
```

E **somente no firmware do gateway**:

```cpp
const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
```

**Atenção:** brokers públicos são compartilhados, podem ficar indisponíveis e não oferecem privacidade na porta `1883`. Não envie dados confidenciais, credenciais ou comandos sensíveis. Utilize prefixos de tópicos exclusivos para evitar colisões, por exemplo `mot/teste/seu-grupo/n3`.

## 3. Executar o Mosquitto com Docker

### 3.1 Instalar Docker

Instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/) no Windows/macOS ou o [Docker Engine](https://docs.docker.com/engine/install/) no Linux. Confirme a instalação:

```bash
docker --version
docker compose version
```

### 3.2 Criar a estrutura de arquivos

```text
mqtt-broker/
├── docker-compose.yml
└── config/
    └── mosquitto.conf
```

Crie o arquivo `docker-compose.yml`:

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./config/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - mosquitto_data:/mosquitto/data

volumes:
  mosquitto_data:
```

Crie `config/mosquitto.conf`:

```conf
listener 1883
protocol mqtt
allow_anonymous true

persistence true
persistence_location /mosquitto/data/

log_dest stdout
log_type all
```

> `allow_anonymous true` é indicado **somente para testes em redes confiáveis**. Para produção, configure autenticação, autorização, TLS e regras de firewall.

### 3.3 Iniciar e gerenciar o broker

Na pasta `mqtt-broker/`:

```bash
# Iniciar em segundo plano
docker compose up -d

# Verificar containers
docker compose ps

# Acompanhar logs
docker compose logs -f mosquitto

# Parar e remover containers (mantém o volume de dados)
docker compose down
```

### 3.4 Testar publicação e assinatura

Abra dois terminais. No primeiro:

```bash
docker exec -it mosquitto mosquitto_sub -h localhost -p 1883 -t 'mot/teste/n3' -v
```

No segundo:

```bash
docker exec -it mosquitto mosquitto_pub -h localhost -p 1883 -t 'mot/teste/n3' -m 'Teste MQTT OK'
```

A mensagem deverá aparecer no primeiro terminal.

## 4. Instalar Mosquitto diretamente no computador

### Windows

1. Acesse a página oficial: https://mosquitto.org/download/.
2. Baixe e execute o instalador para Windows.
3. Abra um terminal na pasta de instalação ou adicione o executável ao `PATH`.
4. Crie um arquivo `mosquitto.conf` com o conteúdo abaixo:

```conf
listener 1883
allow_anonymous true
log_dest stdout
```

5. Inicie manualmente o broker, informando o caminho do arquivo:

```powershell
mosquitto -c .\mosquitto.conf -v
```

Se o instalador tiver criado um serviço Mosquitto que já ocupa a porta `1883`, pare esse serviço antes de iniciar outra instância manualmente.

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
```

Para permitir clientes de outros dispositivos na rede, crie uma configuração de desenvolvimento:

```bash
sudo tee /etc/mosquitto/conf.d/development.conf > /dev/null <<'EOF_CONF'
listener 1883
allow_anonymous true
EOF_CONF

sudo systemctl enable --now mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto
```

> Em ambientes Linux, verifique se o firewall permite a porta `1883` apenas para os dispositivos autorizados.

### macOS (Homebrew)

```bash
brew install mosquitto
```

Crie um arquivo `mosquitto.conf` no diretório atual com `listener 1883` e `allow_anonymous true`, conforme o exemplo para Windows, e inicie:

```bash
mosquitto -c ./mosquitto.conf -v
```

## 5. Configurar Python e firmware do gateway para o broker local

Quando o Python estiver na **mesma máquina** que o broker:

```python
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
```

Quando o **firmware do gateway** estiver em um ESP32 ou outro dispositivo na **mesma rede local**, use o IP LAN do computador que hospeda o broker (exemplo ilustrativo):

```cpp
const char* mqtt_server = "192.168.1.100";
const int mqtt_port = 1883;
```

> **Não use `localhost` no firmware do gateway** para acessar o broker instalado no computador: `localhost` apontaria para o próprio dispositivo. No Windows, descubra o IP com `ipconfig`; no Linux, com `hostname -I`; no macOS, consulte as configurações de rede.

Se o Python estiver em outro container na mesma rede Docker, utilize o nome do serviço `mosquitto` como host, desde que os containers compartilhem uma rede Docker.

## 6. Executar o projeto Python (`N3.py`)

Depois de configurar o broker e o endereço de conexão no projeto, crie e ative o ambiente virtual, caso ainda não tenha feito isso.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt  # Somente se o arquivo existir
python N3.py
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt  # Somente se o arquivo existir
python N3.py
```

Caso o projeto não possua `requirements.txt`, instale manualmente as bibliotecas exigidas por `N3.py`. Se o gateway e o Python precisarem trocar mensagens, confira se ambos usam o **mesmo broker**, a **mesma porta** e os **tópicos MQTT compatíveis**.

## 7. Solução de problemas

| Problema | Verificação |
| --- | --- |
| `Connection refused` | Broker iniciado? Porta correta? Listener habilitado? |
| `Connection timed out` | IP/DNS, firewall, roteador, rede e porta acessível |
| Python conecta, gateway não | No firmware do gateway, não use `localhost`; utilize IP LAN ou host público |
| Nenhuma mensagem recebida | Confira tópico, assinatura, publicação e QoS |
| Porta `1883` ocupada | Outra instância ou serviço MQTT já está em execução |
| Falha de autenticação | Confira usuário, senha, ACL e TLS exigidos pelo servidor |

## Referências

- [Eclipse Mosquitto — Downloads](https://mosquitto.org/download/)
- [Eclipse Mosquitto — Docker](https://github.com/eclipse-mosquitto/mosquitto/tree/master/docker)
- [Docker — Instalação](https://docs.docker.com/engine/install/)
- [EMQX — Broker público](https://www.emqx.com/en/mqtt/public-mqtt5-broker)
- [HiveMQ — Broker público](https://www.hivemq.com/mqtt/public-mqtt-broker/)
- [Mosquitto — Servidor de testes](https://test.mosquitto.org/)
