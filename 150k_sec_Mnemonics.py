from mnemonic import Mnemonic
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip49, Bip49Coins, Bip84, Bip84Coins
from functools import lru_cache
from multiprocessing import Pool, cpu_count, Manager
import threading
import curses
import time

# Lista de idiomas suportados
languages = [
    'english', 'spanish', 'french', 'italian', 
    'chinese_simplified', 'chinese_traditional', 
    'korean', 'portuguese'
]

@lru_cache(maxsize=None)
def generate_mnemonics(word_count, lang):
    try:
        mnemo = Mnemonic(lang)
        mnemonic_phrase = mnemo.generate(strength=word_count // 3 * 32)
        return mnemonic_phrase
    except Exception as e:
        print(f"Error generating mnemonic for language '{lang}': {e}")
        return None

@lru_cache(maxsize=None)
def generate_btc_addresses_and_wif(mnemonic_phrase, lang):
    try:
        mnemo = Mnemonic(lang)
        if not mnemo.check(mnemonic_phrase):
            raise ValueError(f"Invalid mnemonic for language '{lang}'")

        seed_generator = Bip39SeedGenerator(mnemonic_phrase)
        seed = seed_generator.Generate()

        bip44_mst = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
        bip44_acc = bip44_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        p2pkh_address = bip44_acc.PublicKey().ToAddress()
        p2pkh_wif = bip44_acc.PrivateKey().ToWif()

        bip49_mst = Bip49.FromSeed(seed, Bip49Coins.BITCOIN)
        bip49_acc = bip49_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        p2sh_address = bip49_acc.PublicKey().ToAddress()

        bip84_mst = Bip84.FromSeed(seed, Bip84Coins.BITCOIN)
        bip84_acc = bip84_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        bech32_address = bip84_acc.PublicKey().ToAddress()

        return p2pkh_address, p2sh_address, bech32_address, p2pkh_wif

    except Exception as e:
        print(f"Error generating addresses and WIF for language '{lang}': {e}")
        return None, None, None, None

def process_language(lang_code, word_counts, data):
    total_count = 0
    count_per_sec = 0
    count_per_min = 0
    last_update_time = time.time()
    last_min_update_time = time.time()
    
    while True:
        for count in word_counts:
            mnemonic = generate_mnemonics(count, lang_code)
            if mnemonic:
                generate_btc_addresses_and_wif(mnemonic, lang_code)
                total_count += 1
                count_per_sec += 1
                count_per_min += 1

                # Atualiza a taxa a cada 0.1 segundo
                current_time = time.time()
                if current_time - last_update_time >= 0.1:
                    with data["lock"]:
                        data["total"] += count_per_sec
                        data["count_per_sec"] = count_per_sec
                        count_per_sec = 0
                        last_update_time = current_time
                
                # Atualiza a taxa a cada minuto
                if current_time - last_min_update_time >= 60:
                    with data["lock"]:
                        data["count_per_min"] = count_per_min
                        count_per_min = 0
                        last_min_update_time = current_time

def format_number(n):
    """Formata o número com separadores de milhar e duas casas decimais."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:,.2f}B".replace(',', 'X').replace('.', ',').replace('X', '.')
    elif n >= 1_000_000:
        return f"{n / 1_000_000:,.2f}M".replace(',', 'X').replace('.', ',').replace('X', '.')
    elif n >= 1_000:
        return f"{n / 1_000:,.2f}K".replace(',', 'X').replace('.', ',').replace('X', '.')
    else:
        return f"{n:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def update_display(stdscr, data):
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.clear()
    
    header = "Generations/sec    | Generations/min    | Total Generations   | Elapsed Time"
    stdscr.addstr(0, 0, header)
    stdscr.addstr(1, 0, "-" * len(header))
    
    stdscr.refresh()

    start_time = time.time()
    
    while True:
        try:
            with data["lock"]:
                count_per_sec = data["count_per_sec"]
                count_per_min = data.get("count_per_min", 0)
                total_count = data["total"]
            
            elapsed_time = time.time() - start_time
            formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))

            # Atualiza a tela com formatação adequada
            stdscr.addstr(2, 0, f"{format_number(count_per_sec):<18} | {format_number(count_per_min):<18} | {format_number(total_count):<19} | {formatted_time}")
            stdscr.clrtoeol()
            stdscr.refresh()
            
        except:
            pass  # Continue tentando atualizar a tela

        time.sleep(0.05)  # Atualiza frequentemente

def main(stdscr):
    word_counts = [12, 18, 24]
    manager = Manager()
    data = manager.dict()
    data["total"] = 0
    data["count_per_sec"] = 0
    data["lock"] = manager.Lock()

    display_thread = threading.Thread(target=update_display, args=(stdscr, data))
    display_thread.daemon = True
    display_thread.start()

    with Pool(cpu_count()) as pool:
        tasks = []
        for lang_code in languages:
            tasks.append(pool.apply_async(process_language, (lang_code, word_counts, data)))

        for task in tasks:
            task.get()

if __name__ == "__main__":
    curses.wrapper(main)
