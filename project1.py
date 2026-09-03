from boltfn_auth import BoltFnAuth
import os
import sys
import json
import time
import hmac
import hashlib
import getpass
import requests
from mnemonic import Mnemonic
import ecdsa
import base58
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Hash import keccak
from Crypto.Hash import RIPEMD160

api = BoltFnAuth(
    name="Bolt_FN",
    owner_id="32861a9aE3",
    secret="9cf04105354bd4a2efc2abb14d8180ea7fe2feeea6d6ae39ac1c1414bddb16f3",
    version="1.0",
    base_url="https://auth-seven-gules.vercel.app",
    app_slug="bolt-fn"
)
license1 = input("Enter Your Login Token: ")
result = api.login_license(license1)
if not result.success:
    print(f"Login failed [{result.error_code}]: {result.error_message}")
    sys.exit(1)
print(f"Welcome, days left: {result.days_left}")

def _on_lost(msg):
    print(f"Session lost: {msg}")
    try:
        api.stop_heartbeat()
    except:
        pass
    sys.exit(1)

WALLET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallets.dat")
CURVE_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

def _clear():
    os.system("cls" if os.name == "nt" else "clear")

def _pbkdf2_key(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000, dklen=32)

def _encrypt_json(data, password):
    salt = get_random_bytes(16)
    key = _pbkdf2_key(password, salt)
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    pt = json.dumps(data, ensure_ascii=False).encode()
    ct, tag = cipher.encrypt_and_digest(pt)
    return {"salt": salt.hex(), "nonce": nonce.hex(), "tag": tag.hex(), "ct": ct.hex()}

def _decrypt_json(blob, password):
    salt = bytes.fromhex(blob["salt"])
    nonce = bytes.fromhex(blob["nonce"])
    tag = bytes.fromhex(blob["tag"])
    ct = bytes.fromhex(blob["ct"])
    key = _pbkdf2_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    pt = cipher.decrypt_and_verify(ct, tag)
    return json.loads(pt.decode())

def _load_store(password):
    if not os.path.exists(WALLET_FILE):
        return None
    with open(WALLET_FILE, "r", encoding="utf-8") as f:
        blob = json.load(f)
    return _decrypt_json(blob, password)

def _save_store(store, password):
    blob = _encrypt_json(store, password)
    with open(WALLET_FILE, "w", encoding="utf-8") as f:
        json.dump(blob, f, indent=2)

def _hmac_sha512(key, data):
    return hmac.new(key, data, hashlib.sha512).digest()

def _derive_master(seed):
    I = _hmac_sha512(b"Bitcoin seed", seed)
    return I[:32], I[32:]

def _ckd_priv(parent_priv, parent_chain, index):
    hardened = index >= 0x80000000
    if hardened:
        data = b"\x00" + parent_priv + index.to_bytes(4, "big")
    else:
        sk = ecdsa.SigningKey.from_string(parent_priv, curve=ecdsa.SECP256k1)
        vk = sk.get_verifying_key()
        x = vk.pubkey.point.x()
        y = vk.pubkey.point.y()
        prefix = b"\x02" if y % 2 == 0 else b"\x03"
        pub = prefix + x.to_bytes(32, "big")
        data = pub + index.to_bytes(4, "big")
    I = _hmac_sha512(parent_chain, data)
    Il = I[:32]
    Ir = I[32:]
    il_int = int.from_bytes(Il, "big")
    pk_int = int.from_bytes(parent_priv, "big")
    if il_int >= CURVE_ORDER:
        raise ValueError("Invalid derivation")
    child_int = (il_int + pk_int) % CURVE_ORDER
    if child_int == 0:
        raise ValueError("Invalid child")
    return child_int.to_bytes(32, "big"), Ir

def _derive_path(seed, path):
    priv, chain = _derive_master(seed)
    parts = path.strip().split("/")
    if parts[0] == "m":
        parts = parts[1:]
    for p in parts:
        hardened = p.endswith("'")
        idx = int(p[:-1] if hardened else p)
        if hardened:
            idx += 0x80000000
        priv, chain = _ckd_priv(priv, chain, idx)
    return priv

def _priv_to_compressed(priv):
    sk = ecdsa.SigningKey.from_string(priv, curve=ecdsa.SECP256k1)
    vk = sk.get_verifying_key()
    x = vk.pubkey.point.x()
    y = vk.pubkey.point.y()
    prefix = b"\x02" if y % 2 == 0 else b"\x03"
    return prefix + x.to_bytes(32, "big")

def _priv_to_uncompressed(priv):
    sk = ecdsa.SigningKey.from_string(priv, curve=ecdsa.SECP256k1)
    return sk.get_verifying_key().to_string()

def _hash160(data):
    sha = hashlib.sha256(data).digest()
    h = RIPEMD160.new()
    h.update(sha)
    return h.digest()

def _btc_address(pub):
    h160 = _hash160(pub)
    v = b"\x00" + h160
    c = hashlib.sha256(hashlib.sha256(v).digest()).digest()[:4]
    return base58.b58encode(v + c).decode()

def _eth_address(priv):
    pub = _priv_to_uncompressed(priv)
    k = keccak.new(digest_bits=256)
    k.update(pub)
    return "0x" + k.digest()[-20:].hex()

def _eth_checksum(addr):
    low = addr.lower().replace("0x", "")
    k = keccak.new(digest_bits=256)
    k.update(low.encode())
    h = k.hexdigest()
    out = "0x"
    for i, ch in enumerate(low):
        out += ch.upper() if int(h[i], 16) >= 8 else ch
    return out

def _make_wallet(mnemonic_phrase):
    m = Mnemonic("english")
    if mnemonic_phrase is None:
        mnemonic_phrase = m.generate(strength=128)
    if not m.check(mnemonic_phrase):
        raise ValueError("Invalid mnemonic")
    seed = m.to_seed(mnemonic_phrase, passphrase="")
    btc_priv = _derive_path(seed, "m/44'/0'/0'/0/0")
    eth_priv = _derive_path(seed, "m/44'/60'/0'/0/0")
    btc_addr = _btc_address(_priv_to_compressed(btc_priv))
    eth_addr = _eth_checksum(_eth_address(eth_priv))
    return {
        "mnemonic": mnemonic_phrase,
        "btc_priv": btc_priv.hex(),
        "eth_priv": eth_priv.hex(),
        "btc_address": btc_addr,
        "eth_address": eth_addr,
        "created_at": int(time.time())
    }

def _fetch_btc_balance(addr):
    try:
        r = requests.get(f"https://blockstream.info/api/address/{addr}", timeout=10)
        if r.status_code == 200:
            j = r.json()
            funded = j.get("chain_stats", {}).get("funded_txo_sum", 0)
            spent = j.get("chain_stats", {}).get("spent_txo_sum", 0)
            sats = funded - spent
            return sats, sats / 1e8
        return None, None
    except:
        return None, None

def _fetch_eth_balance(addr):
    try:
        r = requests.get(f"https://api.blockcypher.com/v1/eth/main/addrs/{addr}/balance", timeout=10)
        if r.status_code == 200:
            j = r.json()
            wei = j.get("balance", 0)
            return wei, wei / 1e18
        return None, None
    except:
        return None, None

def _fetch_prices():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd", timeout=10)
        if r.status_code == 200:
            j = r.json()
            return j.get("bitcoin", {}).get("usd", 0), j.get("ethereum", {}).get("usd", 0)
        return 0, 0
    except:
        return 0, 0

def _banner():
    print("\033[96m" + "="*62 + "\033[0m")
    print("\033[1;96m  Crypto Wallet033[0m")
    print("\033[96m" + "="*62 + "\033[0m")
    print(f"\033[90m  Auth: {result.days_left} days left  |  Vault: {WALLET_FILE}\033[0m")

def _show_dashboard(wallet, btc_sats, btc_btc, eth_wei, eth_eth, btc_price, eth_price):
    _banner()
    print("")
    print(f"\033[1m  BTC\033[0m  {wallet['btc_address']}")
    if btc_sats is not None:
        usd = btc_btc * btc_price if btc_price else 0
        print(f"       Balance: \033[92m{btc_btc:.8f} BTC\033[0m  ({btc_sats} sats)  ~ ${usd:,.2f}")
    else:
        print("       Balance: \033[90m unavailable (offline)\033[0m")
    print("")
    print(f"\033[1m  ETH\033[0m  {wallet['eth_address']}")
    if eth_eth is not None:
        usd2 = eth_eth * eth_price if eth_price else 0
        print(f"       Balance: \033[92m{eth_eth:.6f} ETH\033[0m  ({eth_wei} wei)  ~ ${usd2:,.2f}")
    else:
        print("       Balance: \033[90m unavailable (offline)\033[0m")
    if btc_price and eth_price and btc_sats is not None and eth_wei is not None:
        total = btc_btc * btc_price + eth_eth * eth_price
        print("")
        print(f"  \033[1mTotal Portfolio: ${total:,.2f}\033[0m  \033[90m(BTC ${btc_price:,.0f} | ETH ${eth_price:,.0f})\033[0m")
    created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wallet["created_at"]))
    print(f"\033[90m  Created: {created}\033[0m")
    print("")

wallet = None
if os.path.exists(WALLET_FILE):
    for _ in range(3):
        try:
            data = _load_store(license1)
            if data and "mnemonic" in data:
                wallet = data
            elif data and "wallets" in data and data["wallets"]:
                wallet = data["wallets"][0]
                _save_store(wallet, license1)
            elif data and "wallets" in data:
                wallet = None
            else:
                wallet = data
            break
        except Exception as e:
            print(f"Unlock failed: {e}")
            store_password = license1
    if wallet is None and os.path.exists(WALLET_FILE):
        try:
            with open(WALLET_FILE, "r") as f:
                _ = json.load(f)
            if wallet is None:
                print("No wallet found, will create one")
        except:
            pass

if wallet is None:
    _clear()
    print("\033[1;93mNo wallet found — creating your single vault\033[0m")
    print("1. Generate new wallet")
    print("2. Import from mnemonic")
    c = input("Choose 1/2: ").strip()
    if c == "2":
        phrase = getpass.getpass("Enter mnemonic: ").strip()
        if not phrase:
            phrase = input("Enter mnemonic: ").strip()
        try:
            wallet = _make_wallet(phrase)
        except Exception as e:
            print(f"Import failed: {e}")
            sys.exit(1)
    else:
        wallet = _make_wallet(None)
        print("")
        print("\033[1;91mBACKUP THIS MNEMONIC NOW — shown once:\033[0m")
        print(f"\033[1m{wallet['mnemonic']}\033[0m")
        input("Press Enter after you backed it up... ")
    _save_store(wallet, license1)
    print("\033[92mVault saved.\033[0m")
    time.sleep(1)

btc_price, eth_price = _fetch_prices()
btc_sats, btc_btc = _fetch_btc_balance(wallet["btc_address"])
eth_wei, eth_eth = _fetch_eth_balance(wallet["eth_address"])

while True:
    if not api.is_authenticated:
        if not api.check():
            print("Session expired")
            sys.exit(1)
    _clear()
    _show_dashboard(wallet, btc_sats, btc_btc, eth_wei, eth_eth, btc_price, eth_price)
    print("\033[96m" + "-"*62 + "\033[0m")
    print("  1  Refresh balances     2  Receive / Show addresses")
    print("  3  Sign message         4  Show mnemonic (secure)")
    print("  5  Replace wallet       6  Change password")
    print("  0  Exit")
    print("\033[96m" + "-"*62 + "\033[0m")
    choice = input("\033[1mSelect:\033[0m ").strip()
    if choice == "1":
        print("Refreshing...")
        btc_price, eth_price = _fetch_prices()
        btc_sats, btc_btc = _fetch_btc_balance(wallet["btc_address"])
        eth_wei, eth_eth = _fetch_eth_balance(wallet["eth_address"])
        print("\033[92mUpdated.\033[0m")
        time.sleep(1)
    elif choice == "2":
        print("")
        print(f"BTC Address:\n  {wallet['btc_address']}")
        print(f"ETH Address:\n  {wallet['eth_address']}")
        print("")
        print("Share these to receive funds. Balances update on refresh.")
        input("Press Enter to continue...")
    elif choice == "3":
        msg = input("Message to sign: ").strip()
        if not msg:
            print("Empty message")
            time.sleep(1)
            continue
        chain = input("Sign with btc/eth [eth]: ").strip().lower() or "eth"
        priv_hex = wallet["btc_priv"] if chain == "btc" else wallet["eth_priv"]
        sk = ecdsa.SigningKey.from_string(bytes.fromhex(priv_hex), curve=ecdsa.SECP256k1)
        sig = sk.sign_deterministic(msg.encode(), hashfunc=hashlib.sha256).hex()
        print(f"Signature ({chain}): {sig}")
        print(f"Address: {wallet['btc_address'] if chain == 'btc' else wallet['eth_address']}")
        input("Press Enter to continue...")
    elif choice == "4":
        confirm = getpass.getpass("Re-enter vault password to reveal: ")
        if confirm != license1:
            print("\033[91mWrong password\033[0m")
            time.sleep(1)
            continue
        print("")
        print(f"\033[1m{wallet['mnemonic']}\033[0m")
        print("")
        input("Press Enter to hide...")
    elif choice == "5":
        print("\033[91mThis will REPLACE your single wallet. Backup current mnemonic first!\033[0m")
        yn = input("Type REPLACE to confirm: ").strip()
        if yn != "REPLACE":
            print("Cancelled")
            time.sleep(1)
            continue
        phrase = input("New mnemonic (leave empty to generate): ").strip()
        if phrase == "":
            wallet = _make_wallet(None)
            print(f"New mnemonic: {wallet['mnemonic']}")
            input("Backed up? Press Enter...")
        else:
            try:
                wallet = _make_wallet(phrase)
            except Exception as e:
                print(f"Failed: {e}")
                time.sleep(1)
                continue
        _save_store(wallet, license1)
        btc_sats, btc_btc = _fetch_btc_balance(wallet["btc_address"])
        eth_wei, eth_eth = _fetch_eth_balance(wallet["eth_address"])
        print("Wallet replaced")
        time.sleep(1)
    elif choice == "6":
        old = getpass.getpass("Current password: ")
        if old != license1:
            print("Wrong password")
            time.sleep(1)
            continue
        new = getpass.getpass("New password (6+): ")
        if len(new) < 6:
            print("Too short")
            time.sleep(1)
            continue
        new2 = getpass.getpass("Confirm new password: ")
        if new != new2:
            print("Mismatch")
            time.sleep(1)
            continue
        license1 = new
        _save_store(wallet, license1)
        print("Password changed")
        time.sleep(1)
    elif choice == "0":
        try:
            api.stop_heartbeat()
        except:
            pass
        print("Goodbye")
        sys.exit(0)
    else:
        print("Invalid")
        time.sleep(0.7)
