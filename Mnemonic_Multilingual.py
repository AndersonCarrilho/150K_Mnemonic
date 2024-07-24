from mnemonic import Mnemonic
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip49, Bip49Coins, Bip84, Bip84Coins
from functools import lru_cache
from multiprocessing import Pool, cpu_count
import threading

# Lista de idiomas suportados
languages = {
    'english': 'English',
    'spanish': 'Spanish',
    'french': 'French',
    'italian': 'Italian',
    'chinese_simplified': 'Chinese Simplified',
    'chinese_traditional': 'Chinese Traditional',
    'korean': 'Korean',
    'portuguese': 'Portuguese'
}

def generate_mnemonics(word_count, lang):
    mnemo = Mnemonic(lang)
    mnemonic_phrase = mnemo.generate(strength=word_count // 3 * 32)
    return mnemonic_phrase

@lru_cache(maxsize=None)
def generate_btc_addresses_and_wif(mnemonic_phrase, lang):
    # Validate mnemonic
    try:
        mnemo = Mnemonic(lang)
        if not mnemo.check(mnemonic_phrase):
            raise ValueError(f"Invalid mnemonic for language '{lang}'")

        # Generate the seed from the mnemonic
        seed_generator = Bip39SeedGenerator(mnemonic_phrase)
        seed = seed_generator.Generate()

        # Generate the P2PKH (Legacy) address and WIF
        bip44_mst = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
        bip44_acc = bip44_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        p2pkh_address = bip44_acc.PublicKey().ToAddress()
        p2pkh_wif = bip44_acc.PrivateKey().ToWif()

        # Generate the P2SH (Segwit) address
        bip49_mst = Bip49.FromSeed(seed, Bip49Coins.BITCOIN)
        bip49_acc = bip49_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        p2sh_address = bip49_acc.PublicKey().ToAddress()

        # Generate the Bech32 (Native Segwit) address
        bip84_mst = Bip84.FromSeed(seed, Bip84Coins.BITCOIN)
        bip84_acc = bip84_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        bech32_address = bip84_acc.PublicKey().ToAddress()

        return p2pkh_address, p2sh_address, bech32_address, p2pkh_wif

    except Exception as e:
        print(f"Error generating addresses and WIF: {e}")
        return None, None, None, None

def process_language(lang_code, lang_name, word_counts):
    for count in word_counts:
        mnemonic = generate_mnemonics(count, lang_code)
        p2pkh, p2sh, bech32, wif = generate_btc_addresses_and_wif(mnemonic, lang_code)

        if p2pkh is not None:
            print(f"Mnemonic ({count} words): {mnemonic}")
            print(f"P2PKH Address: {p2pkh}")
            print(f"P2SH Address: {p2sh}")
            print(f"Bech32 Address: {bech32}")
            print(f"WIF: {wif}")
        else:
            print(f"Failed to generate data for mnemonic: {mnemonic}")

        print()
    print("-" * 50)

def main():
    word_counts = [12, 18, 24]

    while True:
        with Pool(cpu_count()) as pool:
            tasks = []
            for lang_code, lang_name in languages.items():
                tasks.append(pool.apply_async(process_language, (lang_code, lang_name, word_counts)))

            for task in tasks:
                task.get()

if __name__ == "__main__":
    main()
