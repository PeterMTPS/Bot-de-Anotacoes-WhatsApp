# WhatsApp Notas Bot

Um bot simples para usar o WhatsApp como bloco de notas pessoal.

Ele recebe mensagens pelo webhook da WhatsApp Cloud API, salva notas em SQLite e responde com comandos de listar, buscar e apagar.

## Requisitos

- Python 3.10 ou mais recente
- Conta na Meta Developers
- WhatsApp Business Platform / Cloud API configurada
- Uma URL pública para o webhook, como ngrok ou Cloudflare Tunnel

## Como rodar localmente

Copie o arquivo de ambiente:

```powershell
Copy-Item .env.example .env
```

Edite `.env` com seus valores.

Depois rode:

```powershell
python app.py
```

Se o Windows disser que `python` não foi encontrado, instale o Python em [python.org](https://www.python.org/downloads/) e marque a opção de adicionar ao PATH durante a instalação.

O servidor vai subir em:

```text
http://localhost:3000
```

## Testar sem WhatsApp

Você pode testar a lógica do bot pelo terminal:

```powershell
python app.py --chat
```

Exemplos:

```text
comprar leite
/listar
/buscar leite
/apagar 1
/hoje
/ajuda
```

## Comandos

Qualquer mensagem que não comece com `/` vira uma anotação.

```text
comprar arroz amanhã
```

Comandos disponíveis:

```text
/listar
/buscar texto
/apagar 3
/hoje
/ajuda
```

## Configurar webhook na Meta

No painel do app da Meta, configure:

```text
Callback URL: https://sua-url-publica/webhook
Verify token: o mesmo valor de VERIFY_TOKEN no .env
```

Assine o campo:

```text
messages
```

## Variáveis

```text
VERIFY_TOKEN: token usado para validar o webhook na Meta
WHATSAPP_TOKEN: token de acesso da WhatsApp Cloud API
PHONE_NUMBER_ID: ID do número no WhatsApp Business
PORT: porta local, padrão 3000
DB_PATH: caminho do banco SQLite, padrão notes.db
```

Se `WHATSAPP_TOKEN` ou `PHONE_NUMBER_ID` não estiverem definidos, o bot não envia mensagens pela API e apenas imprime a resposta no terminal. Isso ajuda no desenvolvimento local.

## Observação

Dentro da janela de atendimento do WhatsApp, o bot pode responder mensagens normalmente. Para iniciar conversas depois de muito tempo sem contato, a WhatsApp Cloud API exige modelos de mensagem aprovados pela Meta.
