# Projeto Python — N3

Instruções para instalar o Python, preparar um ambiente virtual e executar `N3.py`.

## Pré-requisitos

- Python 3 instalado (versão compatível com o projeto).
- Terminal (PowerShell, Prompt de Comando ou terminal Linux/macOS).
- Arquivo `N3.py` na pasta do projeto.

## 1. Baixar e instalar o Python

Acesse o site oficial: **https://www.python.org/downloads/** e baixe o instalador adequado ao seu sistema operacional.

No Windows, execute o instalador ou o gerenciador de instalação disponibilizado no site e siga as instruções. Caso o instalador apresente a opção **Add Python to PATH**, marque-a.

No Ubuntu/Debian, você também pode instalar pelo terminal:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Confira a instalação:

**Windows:**
```powershell
python --version
```

**Linux/macOS:**
```bash
python3 --version
```

## 2. Abrir a pasta do projeto

Abra um terminal na pasta que contém `N3.py`. Se necessário, navegue até ela:

```bash
cd caminho/para/o/projeto
```

## 3. Criar o ambiente virtual

**Windows:**
```powershell
python -m venv .venv
```

**Linux/macOS:**
```bash
python3 -m venv .venv
```

## 4. Ativar o ambiente virtual

**Windows — PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows — Prompt de Comando (CMD):**
```bat
.venv\Scripts\activate.bat
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

Quando estiver ativo, normalmente aparecerá `(.venv)` no início da linha do terminal.

## 5. Instalar as dependências (se houver)

Se o projeto incluir um arquivo `requirements.txt`, execute:

```bash
python -m pip install -r requirements.txt
```

Se não houver esse arquivo e o script usar apenas bibliotecas da instalação padrão do Python, pule esta etapa.

## 6. Executar o programa

Com o ambiente virtual ativado, execute:

```bash
python N3.py
```

## 7. Encerrar o ambiente virtual

Ao terminar, execute:

```bash
deactivate
```

## Executar novamente

Nas próximas vezes, basta abrir a pasta do projeto, ativar o ambiente virtual (etapa 4) e executar `python N3.py`. Não é necessário recriar o ambiente a cada execução.

## Estrutura sugerida

```text
projeto/
├── N3.py
├── README.md
├── requirements.txt  # opcional
└── .venv/            # gerado localmente
```

> **Dica:** adicione `.venv/` ao arquivo `.gitignore` para não versionar o ambiente virtual.

## Referências

- [Download oficial do Python](https://www.python.org/downloads/)
- [Documentação oficial do `venv`](https://docs.python.org/3/library/venv.html)
- [Guia de instalação de pacotes Python](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
