import os
import json
import asyncio
import signal
from pyrogram import Client, enums
from pyrogram.types import Message
from pyrogram.errors import FileReferenceExpired
import re
from tqdm import tqdm
import logging
from pathlib import Path
import mimetypes
import time

# Modificar a configuração do logging para mostrar apenas erros
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Desabilitar logs específicos do Pyrogram
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pyrogram.session.session").setLevel(logging.ERROR)
logging.getLogger("pyrogram.connection.connection").setLevel(logging.ERROR)
logging.getLogger("pyrogram.dispatcher").setLevel(logging.ERROR)

class TelegramDownloader:
    def __init__(self):
        self.config_file = 'config.json'
        self.client = None
        self.download_path = None
        self.should_stop = False
        self.max_retries = 3
        self.retry_delay = 5  # segundos

    async def initialize(self):
        """Inicializa o cliente do Telegram com as credenciais do usuário."""
        config = self.load_config()

        if not config:
            api_id = input("Digite seu API ID: ")
            api_hash = input("Digite seu API Hash: ")
            config = {'api_id': api_id, 'api_hash': api_hash}
            self.save_config(config)

        self.client = Client(
            "my_account",
            api_id=config['api_id'],
            api_hash=config['api_hash']
        )

        try:
            await self.client.start()
            return True
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            return False

    def load_config(self):
        """Carrega a configuração do arquivo config.json."""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return None

    def save_config(self, config):
        """Salva a configuração no arquivo config.json."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f)

    async def list_channels(self):
        """Lista todos os canais acessíveis."""
        channels = []
        try:
            async for dialog in self.client.get_dialogs():
                if dialog.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
                    channels.append({
                        'name': dialog.chat.title,
                        'id': dialog.chat.id
                    })
            
            channels.sort(key=lambda x: x['name'])
            if not channels:
                print("Nenhum canal encontrado.")
            else:
                print("\nCanais disponíveis:\n")
                for i, channel in enumerate(channels, 1):
                    print(f"{i}. {channel['name']} (ID: {channel['id']})")
            
        except Exception as e:
            logger.error(f"Erro ao listar canais: {e}")
        return channels

    async def download_channel_files(self, channel_id: int):
        """Baixa todos os arquivos de um canal em ordem cronológica."""
        try:
            self.download_path = input("Digite o nome da pasta para download: ")
            os.makedirs(self.download_path, exist_ok=True)
            
            print("Coletando informações dos arquivos...\n")
            messages = []
            async for message in self.client.get_chat_history(channel_id):
                if message.media:
                    messages.append(message)

            messages.reverse()  # Inverte para ordem cronológica
            total_files = len(messages)
            
            print(f"Total de arquivos no canal: {total_files}\n")
            
            print("Iniciando downloads...")
            for position, message in enumerate(messages, 1):
                if self.should_stop:
                    break

                file_name = self.generate_file_name(message, position)
                file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)

                print(f"\nBaixando arquivo {position}/{total_files}")
                print(f"Nome: {file_name}")
                
                success = await self.download_file_with_retry(message, file_name)
                
                if success:
                    print(f"Progresso: {position}/{total_files} arquivos baixados")
                else:
                    print(f"Falha ao baixar: {file_name}")

        except Exception as e:
            logger.error(f"Erro ao baixar arquivos do canal: {e}")
            print(f"Erro durante o download: {str(e)}")

    async def download_file_with_retry(self, message: Message, file_name: str, retry_count=0):
        """Tenta baixar um arquivo com suporte a retry em caso de erro de referência expirada."""
        try:
            path = os.path.join(self.download_path, file_name)
            
            with tqdm(total=100, desc=f"Baixando {file_name}", unit="%") as progress:
                start_time = time.time()

                async def progress_callback(current, total):
                    if self.should_stop:
                        raise asyncio.CancelledError()
                    percent = int(current * 100 / total)
                    progress.n = percent
                    progress.refresh()

                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0:
                        speed_kb_s = (current / 1024) / elapsed_time
                        progress.set_postfix(velocidade=f"{speed_kb_s:.2f} KB/s")

                # Obtém uma nova referência da mensagem antes de tentar o download
                try:
                    fresh_message = await self.client.get_messages(
                        message.chat.id,
                        message.id
                    )

                    if fresh_message is None:
                        print(f"Não foi possível obter a mensagem: {message.id}")
                        return False

                    await fresh_message.download(
                        file_name=path,
                        progress=progress_callback
                    )
                    return True

                except FileReferenceExpired:
                    if retry_count < self.max_retries:
                        print(f"\nReferência expirada, tentando novamente em {self.retry_delay} segundos...")
                        await asyncio.sleep(self.retry_delay)
                        return await self.download_file_with_retry(message, file_name, retry_count + 1)
                    else:
                        print(f"\nFalha após {self.max_retries} tentativas: {file_name}")
                        return False

        except asyncio.CancelledError:
            if os.path.exists(path):
                os.remove(path)
            print(f"\nDownload cancelado: {file_name}")
            return False

        except Exception as e:
            print(f"\nErro ao baixar {file_name}: {e}")
            return False

    def generate_file_name(self, message: Message, counter: int) -> str:
        """Gera um nome de arquivo com a numeração e formatação apropriada."""
        original_name = None
        if message.document and message.document.file_name:
            original_name = message.document.file_name

        ext = self.get_file_extension(message)
        base_name = f"{counter:03d}_"

        if message.caption:
            clean_caption = re.sub(r'[<>:"/\\|?*\n]', '_', message.caption)
            truncated_caption = clean_caption[:200]
            return f"{base_name}{truncated_caption}{ext}"

        if original_name:
            return f"{base_name}{original_name}"

        return f"{base_name}file{ext}"

    def get_file_extension(self, message: Message) -> str:
        """Obtém a extensão de arquivo apropriada com base no tipo de mensagem."""
        mime_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'video/mp4': '.mp4',
            'audio/mpeg': '.mp3',
            'audio/ogg': '.ogg'
        }

        if message.document:
            mime_type = message.document.mime_type
            return mime_map.get(mime_type, os.path.splitext(message.document.file_name)[1] or '')
        elif message.video:
            return '.mp4'
        elif message.audio:
            return '.mp3'
        elif message.voice:
            return '.ogg'
        elif message.photo:
            return '.jpg'
        return ''

    def handle_interrupt(self):
        """Lida com a interrupção CTRL+C."""
        self.should_stop = True
        logger.info("\nInterrompendo downloads...")
        print("\nDownload interrompido.")

async def main():
    downloader = TelegramDownloader()

    signal.signal(signal.SIGINT, lambda s, f: downloader.handle_interrupt())

    if not await downloader.initialize():
        return

    while True:
        print("\nMenu:")
        print("1. Listar Canais")
        print("2. Baixar Arquivos")
        print("3. Sair")

        choice = input("\nEscolha uma opção: ")

        if choice == "1":
            channels = await downloader.list_channels()
        elif choice == "2":
            channel_id = input("Digite o ID do canal: ")
            try:
                await downloader.download_channel_files(int(channel_id))
            except ValueError:
                print("ID de canal inválido!")
        elif choice == "3":
            await downloader.client.stop()
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    asyncio.run(main())