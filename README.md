# Telegram Downloader

## Sobre

O script `telegram_downloader.py` foi desenvolvido para facilitar o download de arquivos de canais do Telegram. Ele permite listar canais acessíveis e baixar arquivos de mídia de forma organizada e cronológica (do primeiro ao último). Este script utiliza a biblioteca Pyrogram para interagir com a API do Telegram. Ele é projetado para ser executado localmente, garantindo que os dados baixados e as credenciais do usuário sejam mantidos em segurança no seu próprio computador.

## Bibliotecas Usadas

- **Pyrogram**: Biblioteca para interagir com a API do Telegram.
- **TQDM**: Para exibir barras de progresso durante o download.
- **Logging**: Para registrar erros e informações de execução.
- **Asyncio**: Para operações assíncronas.
- **Mimetypes**: Para determinar extensões de arquivos.

Obs: Apesar de configurado visando download de multiplos arquivos, por isso o assincronismo, como tenho internet lenta, o download de multiplos arquivos acaba sendo ruim, mas isso pode ser facilmente feito e deixo ao final o trecho do codigo que faz o download de multiplos arquivos para substituar no atual script caso queira. 

## Dependências

Certifique-se de ter o Python instalado em sua máquina. As bibliotecas necessárias estão listadas no arquivo `requirements.txt`. 

## Como Executar e Usar

### 1. Clonar o Repositório

Clone este repositório para o seu computador:

```bash
git clone https://github.com/diogomasc/telegram-downloader.git
cd telegram-downloader
```

### 2. Criar e Ativar o Ambiente Virtual

Crie um ambiente virtual para isolar as dependências:

```bash
python -m venv .venv
```

Ative o ambiente virtual:

- **Windows (PowerShell)**:
  ```bash
  .venv\Scripts\activate
  ```
- **Windows (CMD)**:
  ```cmd
  .venv\Scripts\activate.bat
  ```
- **Mac e Linux**:
  ```bash
  source .venv/bin/activate
  ```

Se houver problemas, certifique-se de que o Python está instalado e no **PATH**. Confira com:

```bash
python --version
```

Se necessário, reinstale o Python e marque a opção **Add Python to PATH** durante a instalação.

### 3. Atualizar o `pip`

Dentro do ambiente virtual, atualize o `pip` para evitar erros de compatibilidade:

```bash
python -m pip install --upgrade pip
```

### 4. Instalar Dependências

Instale as dependências necessárias:

```bash
pip install -r requirements.txt
```

### 5. (Opcional) Configurar Credenciais

Caso queira, antes de executar o script, configure suas credenciais do Telegram no arquivo `config.json`. Este arquivo deve conter seu `api_id` e `api_hash`, que podem ser obtidos no [site do Telegram](https://my.telegram.org). Caso o contrario, na primeira execução do script, ele irá solicitar seu `api_id` e `api_hash` e salvar no arquivo `config.json`.

### 6. Executar o Script

Execute o script:

```bash
python main.py
```

### 7. Parar o Download

É possível parar o download usando a combinação de teclas `Ctrl + C`, mas não é possível retomar o download do ponto em que foi interrompido.

### Segurança

Os dados de configuração, incluindo `api_id` e `api_hash`, são armazenados localmente no arquivo `config.json`. Certifique-se de que este arquivo está seguro e não compartilhe suas credenciais!

## Como prometido...

Deixo aqui o trecho do codigo que faz o download de multiplos arquivos para substituir no atual script caso queira.

```python
async def download_channel_files(self, channel_id: int):
    """Baixa todos os arquivos de um canal em ordem cronológica."""
    self.download_path = input("Digite o nome da pasta para download: ")
    os.makedirs(self.download_path, exist_ok=True)

    try:
        # Obtém todas as mensagens e as ordena pela data
        messages = []
        async for message in self.client.get_chat_history(channel_id):
            # Verifica se a mensagem contém qualquer tipo de mídia
            if message.media:
                messages.append(message)

        # Ordena as mensagens pela data (do mais antigo para o mais recente)
        messages.sort(key=lambda x: x.date)

        # Baixa os arquivos em paralelo
        download_tasks = []
        for counter, message in enumerate(messages, 1):
            if self.should_stop:
                break

            file_name = self.generate_file_name(message, counter)
            file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)

            logger.info(f"Iniciando download {counter}/{len(messages)}: {file_name}")
            download_tasks.append(self.download_file(message, file_name))

        # Executa todas as tarefas de download em paralelo
        await asyncio.gather(*download_tasks)

    except Exception as e:
        logger.error(f"Erro ao baixar arquivos do canal: {e}")
```

Caso queira, pode substituir o trecho do codigo do metodo `download_channel_files` pelo trecho acima.
