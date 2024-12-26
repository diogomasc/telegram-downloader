import os
import json
import asyncio
import signal
from pyrogram import Client, enums
from pyrogram.types import Message
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
        self.current_download = None

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
        """Carrega a configuração a partir do arquivo config.json."""
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

            # Baixa os arquivos com a numeração adequada
            for counter, message in enumerate(messages, 1):
                if self.should_stop:
                    break

                file_name = self.generate_file_name(message, counter)
                file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)

                logger.info(f"Iniciando download {counter}/{len(messages)}: {file_name}")
                await self.download_file(message, file_name)

        except Exception as e:
            logger.error(f"Erro ao baixar arquivos do canal: {e}")

    def generate_file_name(self, message: Message, counter: int) -> str:
        """Gera um nome de arquivo com a numeração e formatação apropriada."""
        # Tenta obter o nome original do arquivo
        original_name = None
        if message.document and message.document.file_name:
            original_name = message.document.file_name

        # Obtém a extensão do arquivo
        ext = self.get_file_extension(message)

        # Cria o nome base com o contador
        base_name = f"{counter:03d}_"

        # Se tiver texto na mensagem, usa como parte do nome do arquivo
        if message.caption:
            # Limpa e limita o tamanho do arquivo
            clean_caption = re.sub(r'[<>:"/\\|?*\n]', '_', message.caption)
            truncated_caption = clean_caption[:200]  # Limita o tamanho do arquivo
            return f"{base_name}{truncated_caption}{ext}"

        # Se tiver o nome original, usa com o prefixo do contador
        if original_name:
            return f"{base_name}{original_name}"

        # Nome padrão
        return f"{base_name}file{ext}"

    def get_file_extension(self, message: Message) -> str:
        """Obtém a extensão de arquivo apropriada com base no tipo de mensagem."""
        
        # Mapeamento de tipos MIME para extensões de arquivo
        mime_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/bmp': '.bmp',
            'application/zip': '.zip',
            'application/x-rar-compressed': '.rar',
            'application/x-7z-compressed': '.7z',
            'video/mp4': '.mp4',
            'audio/mpeg': '.mp3',
            'audio/ogg': '.ogg'
        }

        def get_extension_from_mime(mime_type: str) -> str:
            """Retorna a extensão de arquivo com base no tipo MIME."""
            # Tenta obter a extensão do tipo MIME do mapa ou usa a função guess_extension
            return mime_map.get(mime_type, mimetypes.guess_extension(mime_type) or '')

        # Se não obter a extensão do tipo MIME, tenta pelo nome do arquivo
        if message.document:
            return get_extension_from_mime(message.document.mime_type) or os.path.splitext(message.document.file_name)[1]
        
        if message.video:
            return '.mp4'
        
        if message.audio:
            return '.mp3'
        
        if message.voice:
            return '.ogg'
        
        if message.photo:
            return '.jpg'
        # Retorna uma string vazia se nenhum tipo de mídia for encontrado
        return ''

    async def download_file(self, message: Message, file_name: str):
        """Baixa um único arquivo com barra de progresso e exibe a velocidade de download."""
        try:
            path = os.path.join(self.download_path, file_name)

            with tqdm(total=100, desc=f"Baixando {file_name}", unit="%") as progress:
                start_time = time.time()  # Marca o tempo de início do download

                async def progress_callback(current, total):
                    if self.should_stop:
                        raise asyncio.CancelledError()
                    percent = int(current * 100 / total)
                    progress.n = percent
                    progress.refresh()

                    # Calcula a velocidade de download
                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0:
                        speed_kb_s = (current / 1024) / elapsed_time
                        progress.set_postfix(velocidade=f"{speed_kb_s:.2f} KB/s")

                await message.download(
                    file_name=path,
                    progress=progress_callback
                )

        except asyncio.CancelledError:
            if os.path.exists(path):
                os.remove(path)
            logger.info(f"Download cancelado: {file_name}")
        except Exception as e:
            logger.error(f"Erro ao baixar {file_name}: {e}")

    def handle_interrupt(self):
        """Lida com a interrupção CTRL+C."""
        self.should_stop = True
        logger.info("\nInterrompendo downloads...")

async def main():
    downloader = TelegramDownloader()

    # Configura o manipulador de interrupção
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