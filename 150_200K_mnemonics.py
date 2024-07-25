from mnemonic import Mnemonic
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip49, Bip49Coins, Bip84, Bip84Coins
from functools import lru_cache
from multiprocessing import Pool, cpu_count, Manager
import threading
import curses
import time
import logging
import configparser

# Configuração do logger
logging.basicConfig(filename='error.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Carregar configurações
config = configparser.ConfigParser()
config.read('config.ini')

# Lista de idiomas suportados
languages = config.get('Settings', 'languages').split(',')

@lru_cache(maxsize=None)
def generate_mnemonics(word_count, lang):
    """
    Gera um mnemônico com base na quantidade de palavras e idioma fornecido.

    Args:
        word_count (int): Número de palavras do mnemônico.
        lang (str): Código do idioma para o mnemônico.

    Returns:
        str: Mnemônico gerado ou None em caso de erro.
    """
    try:
        mnemo = Mnemonic(lang)
        return mnemo.generate(strength=word_count // 3 * 32)
    except Exception as e:
        logging.error(f"Error generating mnemonic for language '{lang}': {e}", exc_info=True)
        return None

@lru_cache(maxsize=None)
def generate_btc_addresses_and_wif(mnemonic_phrase, lang):
    """
    Gera endereços Bitcoin e chaves privadas em formato WIF a partir de um mnemônico.

    Args:
        mnemonic_phrase (str): Mnemônico para gerar endereços e WIF.
        lang (str): Código do idioma do mnemônico.

    Returns:
        tuple: Endereços P2PKH, P2SH, Bech32 e chave privada WIF, ou (None, None, None, None) em caso de erro.
    """
    try:
        mnemo = Mnemonic(lang)
        if not mnemo.check(mnemonic_phrase):
            raise ValueError(f"Invalid mnemonic for language '{lang}'")

        seed = Bip39SeedGenerator(mnemonic_phrase).Generate()
        bip44_acc = Bip44.FromSeed(seed, Bip44Coins.BITCOIN).Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        p2pkh_address = bip44_acc.PublicKey().ToAddress()
        p2pkh_wif = bip44_acc.PrivateKey().ToWif()

        bip49_acc = Bip49.FromSeed(seed, Bip49Coins.BITCOIN).Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        p2sh_address = bip49_acc.PublicKey().ToAddress()

        bip84_acc = Bip84.FromSeed(seed, Bip84Coins.BITCOIN).Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        bech32_address = bip84_acc.PublicKey().ToAddress()

        return p2pkh_address, p2sh_address, bech32_address, p2pkh_wif

    except Exception as e:
        logging.error(f"Error generating addresses and WIF for language '{lang}': {e}", exc_info=True)
        return None, None, None, None

def process_language(lang_code, word_counts, data):
    """
    Processa a geração de mnemônicos e endereços para um idioma específico.

    Args:
        lang_code (str): Código do idioma.
        word_counts (list): Lista de contagens de palavras para gerar mnemônicos.
        data (dict): Dicionário compartilhado para armazenamento de métricas.
    """
    mnemo = Mnemonic(lang_code)
    local_count_per_sec = 0
    local_count_per_30_sec = 0
    local_count_per_min = 0
    last_update_time = time.time()
    last_30_sec_time = time.time()
    last_min_update_time = time.time()
    
    while True:
        for count in word_counts:
            mnemonic = generate_mnemonics(count, lang_code)
            if mnemonic:
                generate_btc_addresses_and_wif(mnemonic, lang_code)
                local_count_per_sec += 1
                local_count_per_30_sec += 1
                local_count_per_min += 1

                # Atualiza a taxa a cada 0.1 segundo
                current_time = time.time()
                if current_time - last_update_time >= 0.1:
                    with data["lock"]:
                        data["total"] += local_count_per_sec
                        data["count_per_sec"] = local_count_per_sec
                        local_count_per_sec = 0
                    last_update_time = current_time
                
                # Atualiza a taxa a cada 30 segundos
                if current_time - last_30_sec_time >= 30:
                    with data["lock"]:
                        data["count_per_30_sec"] = local_count_per_30_sec
                        local_count_per_30_sec = 0
                    last_30_sec_time = current_time
                
                # Atualiza a taxa a cada minuto
                if current_time - last_min_update_time >= 60:
                    with data["lock"]:
                        data["count_per_min"] = local_count_per_min
                        local_count_per_min = 0
                    last_min_update_time = current_time

def format_number(n):
    """
    Formata números grandes para uma representação compacta.

    Args:
        n (int): Número a ser formatado.

    Returns:
        str: Representação formatada do número.
    """
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.2f}K"
    else:
        return f"{n:.2f}"

def update_display(stdscr, data):
    """
    Atualiza a exibição dos dados de desempenho usando a biblioteca curses.

    Args:
        stdscr: Objeto curses para manipulação da tela.
        data (dict): Dicionário compartilhado com métricas de desempenho.
    """
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.clear()
    
    header = "Generations/sec    | Generations/30 sec  | Generations/min    | Total Generations   | Elapsed Time"
    stdscr.addstr(0, 0, header)
    stdscr.addstr(1, 0, "-" * len(header))
    
    stdscr.refresh()

    start_time = time.time()
    
    while True:
        try:
            with data["lock"]:
                count_per_sec = data["count_per_sec"]
                count_per_30_sec = data.get("count_per_30_sec", 0)
                count_per_min = data["count_per_min"]
                total_count = data["total"]
            
            elapsed_time = time.time() - start_time
            formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))

            stdscr.addstr(2, 0, f"{format_number(count_per_sec):<18} | {format_number(count_per_30_sec):<19} | {format_number(count_per_min):<18} | {format_number(total_count):<19} | {formatted_time}")
            stdscr.clrtoeol()
            stdscr.refresh()
            
        except KeyboardInterrupt:
            break

        time.sleep(0.05)

def main(stdscr):
    """
    Função principal para configurar e iniciar o processamento e exibição.

    Args:
        stdscr: Objeto curses para manipulação da tela.
    """
    word_counts = [12, 18, 24]
    manager = Manager()
    data = manager.dict()
    data["total"] = 0
    data["count_per_sec"] = 0
    data["count_per_30_sec"] = 0
    data["count_per_min"] = 0
    data["lock"] = manager.Lock()

    display_thread = threading.Thread(target=update_display, args=(stdscr, data))
    display_thread.daemon = True
    display_thread.start()

    # Ajusta o número de processos para evitar sobrecarga
    num_processes = max(1, cpu_count() - 1)
    with Pool(num_processes) as pool:
        tasks = []
        for lang_code in languages:
            tasks.append(pool.apply_async(process_language, (lang_code, word_counts, data)))
        pool.close()
        pool.join()

if __name__ == "__main__":
    curses.wrapper(main)
