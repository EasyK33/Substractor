# -*- coding: utf-8 -*-
import base64
import concurrent.futures
import ctypes
import datetime
import gzip
import io
import json
import os
import platform
import random
import re
import socket
import ssl
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import urllib.parse
import urllib.request
import zlib

import customtkinter as ctk
from PIL import Image

try:
    from Crypto.Cipher import AES, PKCS1_v1_5
    from Crypto.PublicKey import RSA
    from Crypto.Util.Padding import unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


if platform.system() == "Windows":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("easykill.substractor.app.1")
    except Exception:
        pass

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# ====================================================================
# 1. Вспомогательные классы UI
# ====================================================================
class ToolTip:
    def __init__(self, widget, text=""):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.after_id = None
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event=None):
        self._cancel()
        self.after_id = self.widget.after(300, self._show)

    def _on_leave(self, _event=None):
        self._cancel()
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

    def _cancel(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(
            tw, text=self.text, justify="left", 
            fg_color="#2b2b2b", text_color="#f1f2f6", 
            font=ctk.CTkFont(size=11), corner_radius=6
        )
        lbl.pack(ipadx=8, ipady=6)


# ====================================================================
# 2. CORE PARSER (Движок дешифровки и парсинга)
# ====================================================================
class CoreParser:
    SUPPORTED_SCHEMES = (
        "vless://", "vmess://", "trojan://", "ss://",
        "hysteria://", "hysteria2://", "hy2://",
        "yptun://", "freeturn://", "qwdtt://", "wdtt://",
    )

    HAPP_RSA_KEYS = [
        """-----BEGIN PRIVATE KEY-----
MIICeQIBADANBgkqhkiG9w0BAQEFAASCAmMwggJfAgEAAoGBALGxLs9SrVuJCVUP3at/p5cqv2gbX9KtjHepZqFk/4mrfmbhZv9n6YHp4Fas/Mn/NmlktYtCity84q36wtoIfIfUcs2S2LiOVoRBfrH3teAGbwYrTz6Ustaq4UOFZE3Gyt/MnI12lWinMFGYIkpNzw5tjI9uu/1Pflrwp3laqOdTAgMBAAECgYEAmip7zmyQ88XlTuPBEzZiFQmFn7GAZa0lHfzfik+yVaNwu5n8XsOtGIXtmcXkXO0MLEywJe7Jw9ItaX0S6VBLmasv9+fCkraNUTw7USb1GwE46tbDO5mcC6ihEhv/zMLR+8fagaSTrTNIrJwx7r269hQOOG9QtfZKmOZ/0JL38eECQQDcjv3sSf8OukBnPo0zgapnWaQfSQRf+QAcs/WUGBgvWRUrjnkQb95wmQwma0rsD59bDQ3QhzGulgBts4CjX2+PAkEAzj7QwBnxMhlSTpGzaBhSjTgDqZhTLkxa1Fr2nIUiAPvWgcNH7WOuc8upDIKPS19tkFzWJWCyKwkGmhwLywpp/QJBANE13czFv+djanXEksGZrF7OW+zFIR48Hgwb88VfOYmoEXm4ckPSKYha1HiY63+RrhH7BvCXXNwDMzLbwxi1DScCQQC5QgtYwvS4v64DDTVN56sfVpVTnZP6HnPoE905Mw0cPRqtbLALOGLXeLTcm9oDJjDQX9Ort3PS3ESl4VNminAxAkEA2cdvMHzv/FOMNADj8vyxJTybS8zWdFaYkhoAL3ilwz4oMYudsGFau9kbLxmDy9DA2928Iu/KWTSNVNMWpbeJsw==
-----END PRIVATE KEY-----""",
        """-----BEGIN PRIVATE KEY-----
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
-----END PRIVATE KEY-----""",
        """-----BEGIN PRIVATE KEY-----
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
-----END PRIVATE KEY-----""",
        """-----BEGIN PRIVATE KEY-----
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
-----END PRIVATE KEY-----""",
    ]

    @staticmethod
    def get_any(data_dict, *keys, default=None):
        if not isinstance(data_dict, dict):
            return default
        for key in keys:
            val = data_dict.get(key)
            if val not in (None, ""):
                return val
        return default

    @staticmethod
    def extract_flag_data(text):
        """Возвращает словарь с кодом для CDN, самим эмодзи и альфа-2 кодом (например: DE)."""
        if not text: return None
        for i in range(len(text) - 1):
            c1, c2 = ord(text[i]), ord(text[i + 1])
            if 127462 <= c1 <= 127487 and 127462 <= c2 <= 127487:
                code = f"{hex(c1)[2:]}-{hex(c2)[2:]}"
                emoji = text[i:i+2]
                alpha2 = chr(c1 - 127462 + 65) + chr(c2 - 127462 + 65)
                return {"code": code, "emoji": emoji, "alpha2": alpha2}
        return None

    @staticmethod
    def decode_b64_bytes(text, urlsafe=False):
        cleaned = re.sub(r"\s+", "", text.strip())
        if not cleaned: return b""
        if not urlsafe:
            cleaned = cleaned.replace("-", "+").replace("_", "/")
        cleaned += "=" * (-len(cleaned) % 4)
        return base64.urlsafe_b64decode(cleaned) if urlsafe else base64.b64decode(cleaned)

    @staticmethod
    def decode_b64_json(text, use_zlib=False, urlsafe=False):
        try:
            raw = CoreParser.decode_b64_bytes(text, urlsafe=urlsafe)
            if use_zlib: raw = zlib.decompress(raw)
            parsed = json.loads(raw.decode("utf-8", errors="ignore"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception: return {}

    @staticmethod
    def try_decrypt_happ_rsa(text):
        if not CRYPTO_AVAILABLE: return None
        try:
            raw_data = CoreParser.decode_b64_bytes(text)
            if len(raw_data) < 64: return None
            for pem in CoreParser.HAPP_RSA_KEYS:
                try:
                    key = RSA.import_key(pem.strip())
                    cipher_rsa = PKCS1_v1_5.new(key)
                    k_size = key.size_in_bytes()
                    sess = cipher_rsa.decrypt(raw_data[:k_size], b"ERR")
                    if sess == b"ERR" or len(sess) < 16: continue
                    iv = sess[16:32] if len(sess) >= 32 else b"\x00" * 16
                    dec = unpad(AES.new(sess[:16], AES.MODE_CBC, iv).decrypt(raw_data[k_size:]), AES.block_size)
                    
                    if dec.startswith(b"\x1f\x8b"):
                        try: dec = gzip.decompress(dec)
                        except Exception: pass
                    elif dec[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
                        try: dec = zlib.decompress(dec)
                        except Exception: pass
                        
                    txt = dec.decode("utf-8", errors="ignore")
                    if "{" in txt or "://" in txt: return txt
                except Exception: continue
        except Exception: pass
        return None

    @staticmethod
    def try_decode_base64_subscription(text):
        cleaned = re.sub(r"\s+", "", text)
        if not cleaned: return None
        for pad in ("", "=", "==", "==="):
            try:
                decoded = base64.b64decode(cleaned + pad, validate=False).decode("utf-8", errors="ignore")
                if any(k in decoded.lower() for k in (*CoreParser.SUPPORTED_SCHEMES, "outbounds", "proxies")):
                    return decoded
            except Exception: pass
        return None

    @staticmethod
    def decode_profile_title(title_val):
        if title_val and title_val.startswith("base64:"):
            try:
                return CoreParser.decode_b64_bytes(title_val.split("base64:", 1)[1]).decode("utf-8", errors="ignore").strip()
            except Exception: pass
        return title_val or ""

    @staticmethod
    def extract_direct_link_data(url):
        u_clean = url.strip()
        u_low = u_clean.lower()

        if u_low.startswith("vmess://"):
            return CoreParser.decode_b64_json(u_clean.split("#", 1)[0][8:])
        if u_low.startswith("yptun://"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(u_clean).query)
            return CoreParser.decode_b64_json(qs["c"][0], use_zlib=True, urlsafe=True) if "c" in qs else {}
        if u_low.startswith("freeturn://"):
            return CoreParser.decode_b64_json(u_clean.split("://", 1)[1].split("#", 1)[0])
        if u_low.startswith(("qwdtt://", "wdtt://")):
            proto_name = "qwdtt" if u_low.startswith("qwdtt://") else "wdtt"
            frag = urllib.parse.unquote(u_clean.split("#", 1)[1]).strip() if "#" in u_clean else ""
            no_frag = u_clean.split("#", 1)[0]
            payload = no_frag.split("://", 1)[1]

            if "?" in no_frag or "=" in payload:
                parsed = urllib.parse.urlparse(no_frag)
                qs = urllib.parse.parseqs(parsed.query)
                res = {"protocol": proto_name}
                if parsed.netloc and parsed.netloc.lower() != "config": res["host"] = parsed.netloc
                for k, v in qs.items(): res[k] = urllib.parse.unquote(v[0]) if len(v) == 1 else v
                if frag and "name" not in res: res["name"] = frag
                return res
            if ":" in payload:
                parts = payload.split(":")
                if len(parts) >= 5:
                    res = {"protocol": proto_name, "peer": f"{parts[0]}:{parts[1]}"}
                    if len(parts) >= 6: res.update({"alt_port": parts[2], "local_port": parts[3], "pass": parts[4], "hashes": ":".join(parts[5:])})
                    else: res.update({"local_port": parts[2], "pass": parts[3], "hashes": parts[4]})
                    if frag: res["name"] = frag
                    return res
            dec = CoreParser.decode_b64_json(payload)
            if dec and frag and "name" not in dec: dec["name"] = frag
            return dec
        return {}

    @staticmethod
    def format_decoded_dict(data_dict, header=None):
        lines = [f"{'=' * 60}\n  {header}\n{'=' * 60}"] if header else []
        for k, v in data_dict.items():
            if k == "wg" and isinstance(v, str): lines.extend(["\n--- [wg] WireGuard Config ---", v.strip(), "-" * 30])
            elif isinstance(v, (dict, list)): lines.append(f"{k}: {json.dumps(v, ensure_ascii=False, indent=2)}")
            else: lines.append(f"{k}: {v}")
        return "\n".join(lines)

    @staticmethod
    def parse_protocol_info(url):
        u_low = url.lower()
        if u_low.startswith("vless://"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            net, sec = qs.get("type", ["tcp"])[0].upper(), qs.get("security", ["none"])[0].lower()
            tr = "REALITY" if sec == "reality" else ("TLS" if sec == "tls" else ("XHTTP" if net in ("HTTP", "HHTTP", "XHTTP") else net))
            return f"VLESS / {tr}"
        if u_low.startswith("vmess://"):
            d = CoreParser.extract_direct_link_data(url)
            return f"VMESS / {str(d.get('net', 'tcp')).upper()}"
        for prefix, label in (("yptun://", "YPTUN / WG"), ("freeturn://", "FREETURN / WG"), ("qwdtt://", "QWDTT / WG"), ("wdtt://", "WDTT / WG"), ("trojan://", "TROJAN / TLS"), ("ss://", "SHADOWSOCKS")):
            if u_low.startswith(prefix): return label
        if "hysteria" in u_low or u_low.startswith("hy2://"): return "HYSTERIA / TLS"
        return "VPN"

    @staticmethod
    def extract_host_port(url):
        data = CoreParser.extract_direct_link_data(url)
        if data:
            if "add" in data and "port" in data:
                try: return str(data["add"]).strip(), int(data["port"])
                except Exception: pass
            for key in ("peer", "server", "endpoint"):
                val = data.get(key)
                if isinstance(val, str) and ":" in val:
                    h, p = val.rsplit(":", 1)
                    if h not in ("127.0.0.1", "localhost") and p.isdigit(): return h.strip(), int(p)
            if isinstance(data.get("wg"), str):
                m = re.search(r"(?i)Endpoint\s*=\s*([^\s:]+):(\d+)", data["wg"])
                if m and m.group(1) not in ("127.0.0.1", "localhost"): return m.group(1), int(m.group(2))
        try:
            if "://" in url:
                netloc = url.split("://", 1)[1].split("#", 1)[0].split("?", 1)[0].split("@")[-1]
                if ":" in netloc:
                    h, p = netloc.rsplit(":", 1)
                    return h.strip(), int(p)
                if netloc: return netloc.strip(), 443
        except Exception: pass
        return None, None

    @staticmethod
    def _parse_vless_node(ob, node_name):
        stream, settings = ob.get("streamSettings", {}), ob.get("settings", {})
        vnext = (settings.get("vnext") or [{}])[0] if isinstance(settings.get("vnext"), list) else {}
        host = ob.get("server") or ob.get("address") or vnext.get("address") or ""
        port = ob.get("server_port") or ob.get("port") or vnext.get("port") or 443
        users = vnext.get("users") or ob.get("users") or []
        user = users[0] if isinstance(users, list) and users else {}
        uuid_val = user.get("id") or ob.get("uuid") or ob.get("id") or ""

        tr = ob.get("transport", {})
        net = str(CoreParser.get_any(stream, "network") or CoreParser.get_any(tr, "type") or ob.get("network") or "tcp").lower()
        tls_val = ob.get("tls", {})
        sb_tls = tls_val if isinstance(tls_val, dict) else {}
        r_set, sb_r, cl_r = stream.get("realitySettings", {}), sb_tls.get("reality", {}), ob.get("reality-opts", {})

        is_reality = stream.get("security") == "reality" or bool(sb_r.get("enabled")) or bool(r_set) or bool(cl_r)
        is_tls = stream.get("security") == "tls" or bool(sb_tls.get("enabled")) or str(tls_val).lower() == "true" or tls_val is True
        sec = "reality" if is_reality else ("tls" if is_tls else "none")

        t_set = stream.get("tlsSettings", {})
        sni = CoreParser.get_any(t_set, "serverName") or CoreParser.get_any(r_set, "serverName") or CoreParser.get_any(sb_tls, "server_name") or CoreParser.get_any(sb_r, "server_name") or ob.get("servername") or ob.get("sni") or ""
        ws_path = stream.get("wsSettings", {}).get("path") or tr.get("path") or ob.get("ws-opts", {}).get("path") or ""

        params = [f"type={net}", f"security={sec}"]
        if sni: params.append(f"sni={urllib.parse.quote(str(sni))}")
        if sec == "reality":
            pbk = CoreParser.get_any(r_set, "publicKey", "public_key") or CoreParser.get_any(sb_r, "public_key", "publicKey") or CoreParser.get_any(cl_r, "public-key", "publicKey") or ""
            sid = CoreParser.get_any(r_set, "shortId", "short_id") or CoreParser.get_any(sb_r, "short_id", "shortId") or CoreParser.get_any(cl_r, "short-id", "shortId") or ""
            spx = CoreParser.get_any(r_set, "spiderX", "spider_x") or CoreParser.get_any(sb_r, "spider_x", "spiderX") or CoreParser.get_any(cl_r, "spider-x", "spiderX") or ""
            fp = CoreParser.get_any(t_set, "fingerprint") or CoreParser.get_any(r_set, "fingerprint") or CoreParser.get_any(sb_tls.get("utls", {}), "fingerprint") or ob.get("client-fingerprint") or ""
            for k, val in (("pbk", pbk), ("sid", sid), ("spx", spx), ("fp", fp)):
                if val: params.append(f"{k}={urllib.parse.quote(str(val))}")
        if ws_path: params.append(f"path={urllib.parse.quote(str(ws_path))}")
        flow = user.get("flow") or ob.get("flow") or ""
        if flow: params.append(f"flow={urllib.parse.quote(str(flow))}")

        return f"vless://{uuid_val}@{host}:{port}?{'&'.join(params)}#{urllib.parse.quote(node_name)}", f"VLESS / {net.upper()}"

    @staticmethod
    def _parse_hysteria_node(ob, node_name):
        stream, settings = ob.get("streamSettings", {}), ob.get("settings", {})
        host = ob.get("server") or settings.get("address") or ""
        port = ob.get("server_port") or ob.get("port") or settings.get("port") or 443
        auth = ob.get("password") or ob.get("auth_str") or stream.get("hysteriaSettings", {}).get("auth") or settings.get("auth") or ob.get("auth") or ""
        tls_d = ob.get("tls") if isinstance(ob.get("tls"), dict) else {}
        t_set = stream.get("tlsSettings", {})
        sni = ob.get("sni") or ob.get("servername") or t_set.get("serverName") or tls_d.get("server_name") or ""
        insecure = bool(tls_d.get("insecure") or ob.get("skip-cert-verify") or t_set.get("allowInsecure"))

        params = []
        if sni: params.append(f"sni={urllib.parse.quote(str(sni))}")
        if insecure: params.append("insecure=1")
        obfs_d = ob.get("obfs") if isinstance(ob.get("obfs"), dict) else {}
        obfs_t = obfs_d.get("type") or ob.get("obfs") or ""
        if isinstance(obfs_t, str) and obfs_t:
            params.append(f"obfs={urllib.parse.quote(obfs_t)}")
            obfs_p = obfs_d.get("password") or ob.get("obfs-password") or ""
            if obfs_p: params.append(f"obfs-password={urllib.parse.quote(str(obfs_p))}")

        q = f"?{'&'.join(params)}" if params else ""
        return f"hy2://{urllib.parse.quote(str(auth))}@{host}:{port}{q}#{urllib.parse.quote(node_name)}", "HYSTERIA / TLS"

    @staticmethod
    def _parse_trojan_node(ob, node_name):
        srvs = ob.get("settings", {}).get("servers", [])
        srv = srvs[0] if isinstance(srvs, list) and srvs else {}
        addr = srv.get("address") or ob.get("server") or ""
        port = srv.get("port") or ob.get("server_port") or ob.get("port") or 443
        pwd = srv.get("password") or ob.get("password") or ""
        if not addr or not pwd: return None, None
        sb_tls = ob.get("tls") if isinstance(ob.get("tls"), dict) else {}
        sni = ob.get("streamSettings", {}).get("tlsSettings", {}).get("serverName") or sb_tls.get("server_name") or ob.get("sni") or ob.get("servername") or ""
        q = f"?sni={urllib.parse.quote(str(sni))}" if sni else ""
        return f"trojan://{urllib.parse.quote(str(pwd))}@{addr}:{port}{q}#{urllib.parse.quote(node_name)}", "TROJAN / TLS"

    @staticmethod
    def parse_subscription_text(text_to_parse):
        results, seen = [], set()

        def convert_hy(m):
            line, host, port = m.group(0), m.group(1), m.group(2)
            a_m, s_m, h_m = re.search(r"[?&]auth=([^&#]+)", line), re.search(r"[?&]sni=([^&#]+)", line), re.search(r"#(.*)$", line)
            if a_m: return f"hy2://{a_m.group(1)}@{host}:{port}?sni={s_m.group(1) if s_m else 'bing.com'}#{h_m.group(1) if h_m else 'VPN Сервер'}"
            return line

        text_to_parse = re.sub(r"hysteria://([^:/]+):(\d+)\?[^\s#]+(?:#(.*))?", convert_hy, text_to_parse)
        pattern = r"(?:vless|hysteria2?|hy2|trojan|ss|vmess|yptun|freeturn|qwdtt|wdtt)://[^\s\"']+"

        for raw_u in re.findall(pattern, text_to_parse, re.IGNORECASE):
            u = raw_u.rstrip("\",'}")
            if u in seen: continue
            frag_name = urllib.parse.unquote(u.split("#")[-1]).strip() if "#" in u else ""
            d = CoreParser.extract_direct_link_data(u)
            r_name = str(d.get("name") or d.get("remark") or d.get("title") or d.get("ps") or "").strip() if d else ""

            if u.lower().startswith("vmess://"):
                if not frag_name: name = r_name
                elif r_name and CoreParser.extract_flag_data(r_name) and not CoreParser.extract_flag_data(frag_name): name = r_name
                else: name = frag_name
            else:
                name = r_name if r_name else frag_name

            seen.add(u)
            results.append({"name": name or "VPN Сервер", "protocol_info": CoreParser.parse_protocol_info(u), "payload": u})

        try:
            cfgs = json.loads(text_to_parse)
            for idx, cfg in enumerate(cfgs if isinstance(cfgs, list) else [cfgs]):
                if not isinstance(cfg, dict): continue
                rem = str(cfg.get("remarks") or "").strip()
                for ob in (cfg.get("outbounds") or cfg.get("proxies") or []):
                    if not isinstance(ob, dict): continue
                    proto = str(ob.get("type") or ob.get("protocol") or "").lower()
                    tag = str(ob.get("tag") or ob.get("remarks") or ob.get("name") or "").strip()
                    if proto in ("direct", "freedom", "block", "blackhole", "dns", "selector", "urltest", "static") or tag.lower() in ("direct", "freedom", "block", "blackhole", "dns", "auto"): continue
                    n_name = rem or (tag if tag and tag.lower() not in ("proxy", "outbound") else f"Сервер #{idx + 1}")
                    link, p_info = None, None
                    if proto == "vless": link, p_info = CoreParser._parse_vless_node(ob, n_name)
                    elif proto in ("hysteria", "hysteria2", "hy2"): link, p_info = CoreParser._parse_hysteria_node(ob, n_name)
                    elif proto == "trojan": link, p_info = CoreParser._parse_trojan_node(ob, n_name)
                    if link and link not in seen:
                        seen.add(link)
                        results.append({"name": n_name, "protocol_info": p_info, "payload": link})
        except Exception: pass
        return results


# ====================================================================
# 3. ОСНОВНОЙ КЛАСС ИНТЕРФЕЙСА (UI)
# ====================================================================
class SubstractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Substractor")
        w, h = 960, 780
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{(self.winfo_screenheight() - h) // 2}")
        self.minsize(820, 600)

        try:
            base = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(os.path.abspath(__file__))
            ico = os.path.join(base, "icon.ico")
            if os.path.exists(ico): self.after(200, lambda: self.iconbitmap(ico))
        except Exception: pass

        self.current_servers = []
        self.filtered_servers = []
        self.raw_subscription_text = ""
        self.profile_title = ""
        self.flag_cache = {}
        self.flag_waiters = {}

        self._build_ui()

    def get_local_file(self, filename):
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, filename)

    def bind_entry_events(self, entry_widget):
        inner = entry_widget._entry

        def _on_ctrl(event):
            if event.keycode == 86 or event.char == "\x16" or event.keysym.lower() in ("v", "m", "cyrillic_em"):
                self.paste_to_widget(entry_widget)
                return "break"
            if event.keycode == 67 or event.char == "\x03" or event.keysym.lower() in ("c", "с", "cyrillic_es"):
                self.copy_from_widget(entry_widget)
                return "break"
            return None

        inner.bind("<Control-KeyPress>", _on_ctrl)
        inner.bind("<Key>", lambda e: _on_ctrl(e) if (e.state & 0x4 or e.state & 0x20000) else None)

        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="Вставить", command=lambda: self.paste_to_widget(entry_widget))
        context_menu.add_command(label="Копировать", command=lambda: self.copy_from_widget(entry_widget))
        context_menu.add_command(label="Очистить", command=lambda: entry_widget.delete(0, tk.END))
        inner.bind("<Button-3>", lambda e: context_menu.tk_popup(e.x_root, e.y_root))

    def paste_to_widget(self, entry_widget):
        try:
            txt = self.clipboard_get()
            if txt:
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, txt.strip())
        except Exception: pass

    def copy_from_widget(self, entry_widget):
        try:
            inner = entry_widget._entry
            txt = inner.selection_get() if inner.select_present() else entry_widget.get()
            if txt:
                self.clipboard_clear()
                self.clipboard_append(txt)
        except Exception: pass

    def _build_ui(self):
        # 1. Поле ввода
        self.frame_input = ctk.CTkFrame(self)
        self.frame_input.pack(fill="x", padx=20, pady=(15, 5))

        self.entry_url = ctk.CTkEntry(self.frame_input, placeholder_text="Вставьте ссылку на подписку (или прямую vless://, yptun://, freeturn://, qwdtt://, wdtt://...)", height=35)
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=10)
        self.bind_entry_events(self.entry_url)

        self.btn_history = ctk.CTkButton(self.frame_input, text="🕒", width=35, height=35, fg_color="#4a4a4a", hover_color="#3a3a3a", command=self.show_history_menu)
        self.btn_history.pack(side="left", padx=(5, 10), pady=10)

        self.btn_fetch = ctk.CTkButton(self.frame_input, text="Получить ссылки", width=140, height=35, command=self.fetch_subscription)
        self.btn_fetch.pack(side="right", padx=(0, 10), pady=10)

        # 2. Настройки заголовков
        self.frame_settings = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_settings.pack(fill="x", padx=20, pady=(2, 5))

        self.var_random_headers = tk.BooleanVar(value=True)
        self.chk_random = ctk.CTkCheckBox(self.frame_settings, text="Использовать случайные данные устройства (HWID, версии, модель)", variable=self.var_random_headers, font=ctk.CTkFont(size=12), command=self.toggle_custom_headers)
        self.chk_random.pack(side="top", anchor="w", padx=5)

        self.frame_custom_headers = ctk.CTkFrame(self.frame_settings, fg_color=("#2b2b2b", "#242424"), corner_radius=8)

        self.entry_hwid = self._add_labeled_entry(self.frame_custom_headers, "HWID устройства (16 симв.):", 210)
        self.entry_app_ver = self._add_labeled_entry(self.frame_custom_headers, "Версия приложения (Happ):", 155)
        self.entry_os_ver = self._add_labeled_entry(self.frame_custom_headers, "Версия iOS:", 120)
        self.entry_device_model = self._add_labeled_entry(self.frame_custom_headers, "Модель устройства:", 160)

        col_btn = ctk.CTkFrame(self.frame_custom_headers, fg_color="transparent")
        col_btn.pack(side="left", padx=(5, 12), pady=8)
        ctk.CTkLabel(col_btn, text=" ", font=ctk.CTkFont(size=11)).pack(anchor="w")
        btn_box = ctk.CTkFrame(col_btn, fg_color="transparent")
        btn_box.pack(anchor="w", pady=(2, 0))
        self.btn_reroll = ctk.CTkButton(btn_box, text="🎲", width=35, height=28, fg_color="#4a4a4a", hover_color="#3a3a3a", command=self.fill_random_custom_fields)
        self.btn_reroll.pack(side="left", padx=(0, 5))
        self.btn_save_settings = ctk.CTkButton(btn_box, text="💾 Сохранить", width=90, height=28, fg_color="#2b8a3e", hover_color="#237032", command=self.save_settings)
        self.btn_save_settings.pack(side="left")

        if not self.load_settings():
            self.fill_random_custom_fields()

        # 3. Инфо подписки
        self.frame_info = ctk.CTkFrame(self, fg_color=("#333333", "#2a2a2a"))
        self.frame_info.pack(fill="x", padx=20, pady=(5, 5))
        self.label_sub_info = ctk.CTkLabel(self.frame_info, text="Информация о подписке: не загружена", font=ctk.CTkFont(size=12), text_color="#a0a0a0")
        self.label_sub_info.pack(padx=12, pady=8, anchor="w")

        # 4. Панель управления (Фильтры и основные действия)
        self.frame_controls = ctk.CTkFrame(self, fg_color=("#333333", "#2a2a2a"), corner_radius=8)
        self.frame_controls.pack(fill="x", padx=20, pady=(5, 0), ipadx=10, ipady=10)

        # Контейнер для строгого центрирования
        center_container = ctk.CTkFrame(self.frame_controls, fg_color="transparent")
        center_container.pack(expand=True)

        # Ряд 1: Фильтры
        row_filters = ctk.CTkFrame(center_container, fg_color="transparent")
        row_filters.pack(pady=(0, 10))
        
        ctk.CTkLabel(row_filters, text="Сортировка:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#a0a0a0").pack(side="left", padx=(0, 5))
        self.combo_sort = ctk.CTkComboBox(row_filters, values=["Исходный порядок", "По названию (А - Я)", "По названию (Я - А)", "По пингу (сначала быстрые)"], command=self.on_filter_changed, width=200, height=28)
        self.combo_sort.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row_filters, text="Протокол:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#a0a0a0").pack(side="left", padx=(0, 5))
        self.combo_proto = ctk.CTkComboBox(row_filters, values=["Все"], command=self.on_filter_changed, width=130, height=28)
        self.combo_proto.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row_filters, text="Страна:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#a0a0a0").pack(side="left", padx=(0, 5))
        self.combo_country = ctk.CTkComboBox(row_filters, values=["Все"], command=self.on_filter_changed, width=130, height=28)
        self.combo_country.pack(side="left")

        # Ряд 2: Кнопки
        row_actions = ctk.CTkFrame(center_container, fg_color="transparent")
        row_actions.pack()

        # Убраны жесткие цвета (fg_color/hover_color), теперь используется системный синий
        self.btn_ping = ctk.CTkButton(row_actions, text="⚡ Проверить доступность", width=180, height=30, command=self.start_ping_all)
        self.btn_ping.pack(side="left", padx=5) # Симметричный отступ
        
        self.btn_debug = ctk.CTkButton(row_actions, text="🛠 Сырые данные", width=150, height=30, fg_color="#4a4a4a", hover_color="#3a3a3a", command=self.show_raw_data)
        self.btn_debug.pack(side="left", padx=5) # Симметричный отступ

        ToolTip(self.btn_ping, "⚠ Внимание: Проверяется только TCP-соединение с портом.\nСервер может отвечать по TCP, но в реальности\nне работать как прокси (или использовать только UDP).")
        ToolTip(self.btn_debug, "Показывает расшифрованный код подписки или прямой ссылки:\nпараметры туннеля, JSON-конфиги, ключи WireGuard и метаданные.")

        # 5. Список серверов
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Список серверов")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(10, 5))

        # 6. Подвал и кнопка экспорта
        self.frame_footer = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_footer.pack(fill="x", padx=20, pady=(0, 10))
        
        ctk.CTkLabel(self.frame_footer, text="Программа разработана EasyK. Приятного использования!", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left", pady=5)

        self.btn_export = ctk.CTkButton(self.frame_footer, text="💾 Сохранить видимые сервера в .txt", width=220, height=32, fg_color="#2b8a3e", hover_color="#237032", font=ctk.CTkFont(weight="bold"), command=self.export_to_txt)
        self.btn_export.pack(side="right")
        ToolTip(self.btn_export, "Сохраняет в текстовый файл только те ссылки,\nкоторые сейчас отфильтрованы и отображаются на экране.")

    def _add_labeled_entry(self, parent, title, width):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", padx=(12, 6), pady=8)
        ctk.CTkLabel(col, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="#a0a0a0").pack(anchor="w")
        entry = ctk.CTkEntry(col, width=width, height=28)
        entry.pack(anchor="w", pady=(2, 0))
        self.bind_entry_events(entry)
        return entry

    # ================= ЛОГИКА НАСТРОЕК =================
    def load_settings(self):
        path = self.get_local_file("settings.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f: data = json.load(f)
                self.var_random_headers.set(data.get("use_random", True))
                for key, widget in (("hwid", self.entry_hwid), ("app_ver", self.entry_app_ver), ("os_ver", self.entry_os_ver), ("device", self.entry_device_model)):
                    if key in data:
                        widget.delete(0, tk.END)
                        widget.insert(0, data[key])
                self.toggle_custom_headers()
                return True
            except Exception: pass
        return False

    def save_settings(self):
        data = {
            "use_random": self.var_random_headers.get(),
            "hwid": self.entry_hwid.get().strip(),
            "app_ver": self.entry_app_ver.get().strip(),
            "os_ver": self.entry_os_ver.get().strip(),
            "device": self.entry_device_model.get().strip()
        }
        try:
            with open(self.get_local_file("settings.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Сохранение", "Настройки устройства успешно сохранены!\n\nОни будут загружаться автоматически при запуске программы.")
        except Exception as e: messagebox.showerror("Ошибка", f"Не удалось сохранить настройки:\n{e}")

    def fill_random_custom_fields(self):
        for entry, val in (
            (self.entry_hwid, "".join(random.choices("0123456789abcdef", k=16))),
            (self.entry_app_ver, random.choice(["4.6.1", "4.6.2", "4.6.3", "4.7.0"])),
            (self.entry_os_ver, random.choice(["17.4.1", "17.5.1", "18.0", "18.1"])),
            (self.entry_device_model, random.choice(["iPhone 14 Pro", "iPhone 15", "iPhone 16 Pro Max", "iPhone 17 Pro"])),
        ):
            entry.delete(0, tk.END)
            entry.insert(0, val)

    def toggle_custom_headers(self):
        if self.var_random_headers.get(): self.frame_custom_headers.pack_forget()
        else: self.frame_custom_headers.pack(side="top", fill="x", pady=(6, 2), padx=5)

    def build_request_headers(self):
        if self.var_random_headers.get():
            app_v = random.choice(["4.6.0", "4.6.1", "4.6.2", "4.6.3", "4.7.0"])
            os_v = random.choice(["17.3", "17.4.1", "17.5.1", "18.0", "18.1"])
            mod = random.choice(["iPhone 13", "iPhone 14 Pro", "iPhone 15", "iPhone 16 Pro Max", "iPhone 17 Pro"])
            hwid = "".join(random.choices("0123456789abcdef", k=16))
        else:
            hwid = self.entry_hwid.get().strip() or "0000000000000000"
            app_v = self.entry_app_ver.get().strip() or "4.7.0"
            os_v = self.entry_os_ver.get().strip() or "18.0"
            mod = self.entry_device_model.get().strip() or "iPhone 16 Pro Max"

        return {
            "User-Agent": f"Happ/{app_v}/ios/{random.randint(1000000000, 9999999999)}",
            "X-Device-OS": "iOS",
            "X-HWID": hwid,
            "X-Device-Locale": "ru",
            "X-Ver-OS": os_v,
            "X-App-Version": app_v,
            "X-Device-Model": mod,
            "Accept": "*/*",
        }

    # ================= ИСТОРИЯ =================
    def get_history_file(self): return self.get_local_file("history_urls.json")

    def load_history(self):
        p = self.get_history_file()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return []

    def save_to_history(self, url):
        h = self.load_history()
        if url in h: h.remove(url)
        h.insert(0, url)
        try:
            with open(self.get_history_file(), "w", encoding="utf-8") as f: json.dump(h[:15], f, ensure_ascii=False, indent=2)
        except Exception: pass

    def delete_from_history(self, url):
        h = self.load_history()
        if url in h:
            h.remove(url)
            try:
                with open(self.get_history_file(), "w", encoding="utf-8") as f: json.dump(h, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("Удаление", "Ссылка успешно удалена из истории!")
            except Exception: pass

    def clear_history(self):
        p = self.get_history_file()
        if os.path.exists(p):
            try:
                os.remove(p)
                messagebox.showinfo("История", "Вся история успешно очищена!")
            except Exception: pass

    def show_history_menu(self):
        h = self.load_history()
        if not h: return messagebox.showinfo("История", "Вы еще не сохраняли ссылки.")
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        for u in h:
            sub = tk.Menu(menu, tearoff=0, font=("Segoe UI", 10))
            sub.add_command(label="Вставить", command=lambda url=u: (self.entry_url.delete(0, tk.END), self.entry_url.insert(0, url)))
            sub.add_command(label="Удалить ссылку", command=lambda url=u: self.delete_from_history(url))
            menu.add_cascade(label=u if len(u) < 65 else u[:62] + "...", menu=sub)
        menu.add_separator()
        menu.add_command(label="Очистить всю историю", command=self.clear_history)
        menu.tk_popup(self.btn_history.winfo_rootx(), self.btn_history.winfo_rooty() + self.btn_history.winfo_height())

    def get_valid_filename(self, text):
        clean = re.sub(r'(?u)[^-\w\s.]', '', str(text)).strip()
        return re.sub(r'\s+', '_', clean)

    def export_to_txt(self):
        if not self.filtered_servers:
            return messagebox.showwarning("Внимание", "Нет отфильтрованных ссылок для сохранения!")
        
        def_name = "Substractor_Links"
        if self.profile_title:
            cl = self.get_valid_filename(self.profile_title)
            if cl: def_name = cl

        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")], initialfile=f"{def_name}.txt", title="Сохранить отфильтрованные ссылки")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    for s in self.filtered_servers: f.write(s["url"] + "\n")
                messagebox.showinfo("Успех", f"Успешно сохранено серверов: {len(self.filtered_servers)}\nФайл: {os.path.basename(path)}")
            except Exception as e: messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    # ================= ЗАГРУЗКА ПОДПИСКИ =================
    def fetch_subscription(self):
        url = self.entry_url.get().strip()
        if not url: return messagebox.showwarning("Ошибка", "Пожалуйста, введите ссылку!")

        self.save_to_history(url)
        self.current_servers, self.filtered_servers, self.raw_subscription_text, self.profile_title = [], [], "", ""
        for w in self.scroll_frame.winfo_children(): w.destroy()

        is_direct = url.lower().startswith(CoreParser.SUPPORTED_SCHEMES)
        self.label_sub_info.configure(text="Обработка ссылки...", text_color="#a0a0a0")
        self.btn_fetch.configure(state="disabled", text="Загрузка...")
        self.update()

        raw_text, headers_dict = None, {}
        if is_direct:
            raw_text = url
            self.label_sub_info.configure(text="Прямая ссылка", text_color="#ffffff")
        else:
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            try:
                req = urllib.request.Request(url, headers=self.build_request_headers())
                with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                    raw_text = resp.read().decode("utf-8", errors="ignore").strip()
                    headers_dict = {k.lower(): v for k, v in resp.headers.items()}
            except Exception as e:
                self.label_sub_info.configure(text="Информация о подписке: ошибка загрузки", text_color="#e74c3c")
                self.btn_fetch.configure(state="normal", text="Получить ссылки")
                return messagebox.showerror("Ошибка подключения", f"Не удалось получить данные с сервера.\n\nДетали: {e}")

        self.raw_subscription_text = raw_text
        try:
            if not is_direct:
                m_cd = re.search(r'filename=["\']?([^"\';]+)["\']?', headers_dict.get("content-disposition", ""), re.IGNORECASE)
                if m_cd: self.profile_title = urllib.parse.unquote(m_cd.group(1)).strip()

                dec = CoreParser.try_decrypt_happ_rsa(raw_text)
                text_to_parse = self.raw_subscription_text = dec if dec else (CoreParser.try_decode_base64_subscription(raw_text) or raw_text)

                def f_meta(hk, pat):
                    v = headers_dict.get(hk, "")
                    if not v:
                        m = re.search(pat, text_to_parse, re.IGNORECASE)
                        if m: v = m.group(1).strip()
                    return v

                s_info = f_meta("subscription-userinfo", r"#subscription-userinfo:\s*([^\r\n]+)")
                t_raw = f_meta("profile-title", r"#profile-title:\s*([^\r\n]+)")
                s_url = f_meta("support-url", r"#support-url:\s*([^\r\n]+)")

                if t_raw and not self.profile_title: self.profile_title = CoreParser.decode_profile_title(t_raw)

                info = []
                if self.profile_title: info.append(f"Профиль: {re.sub(r'_\d+_\d+$', '', self.profile_title)}")
                if s_info:
                    p = {k.strip().lower(): v.strip() for part in s_info.split(";") if "=" in part for k, v in [part.split("=", 1)]}
                    up, dn, tot = int(p.get("upload", 0)), int(p.get("download", 0)), int(p.get("total", 0))
                    used, total_gb = (up + dn) / (1024**3), tot / (1024**3)
                    info.append(f"Трафик: {used:.2f} ГБ из {total_gb:.2f} ГБ" if tot > 0 else f"Использовано: {used:.2f} ГБ (безлимит)")
                    exp = p.get("expire")
                    if exp and exp.isdigit() and int(exp) > 0: info.append(f"Истекает: {datetime.datetime.fromtimestamp(int(exp)).strftime('%d.%m.%Y')}")
                if s_url: info.append(f"Поддержка: {s_url}")

                self.label_sub_info.configure(text=" | ".join(info) if info else "Динамические данные не переданы", text_color="#ffffff" if info else "#a0a0a0")
            else:
                text_to_parse = raw_text

            servers_data = CoreParser.parse_subscription_text(text_to_parse)
            if not servers_data: messagebox.showinfo("Результат", "Подходящие серверы не найдены.")
            else:
                seen = set()
                protos = set()
                countries = set()

                for item in servers_data:
                    payload, name = item.get("payload", "").strip(), item.get("name", "").strip()
                    key = f"{name}::{payload}"
                    if payload and key not in seen:
                        seen.add(key)
                        proto_info = item.get("protocol_info", "VPN")
                        flag_data = CoreParser.extract_flag_data(name)
                        
                        self.current_servers.append({
                            "url": payload, "name": name or "VPN Сервер", 
                            "protocol_info": proto_info, "ping": None, "method": "", 
                            "flag_data": flag_data
                        })
                        
                        protos.add(proto_info.split(" / ")[0])
                        if flag_data:
                            countries.add(f"{flag_data['emoji']} {flag_data['alpha2']}")

                # Обновляем фильтры
                self.combo_proto.configure(values=["Все"] + sorted(list(protos)))
                self.combo_proto.set("Все")
                
                c_list = ["Все"] + sorted(list(countries))
                if any(s.get("flag_data") is None for s in self.current_servers):
                    c_list.append("🌍 Без флага")
                self.combo_country.configure(values=c_list)
                self.combo_country.set("Все")

                self.display_servers()
        except Exception as e: messagebox.showerror("Ошибка", f"Ошибка обработки данных:\n{e}")
        finally: self.btn_fetch.configure(state="normal", text="Получить ссылки")

    # ================= ПИНГ И ФИЛЬТРЫ =================
    def measure_ping(self, host, port):
        try:
            t0 = time.perf_counter()
            with socket.create_connection((host, port), timeout=1.5): return int((time.perf_counter() - t0) * 1000), "TCP"
        except Exception: pass
        try:
            t0 = time.perf_counter()
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            with socket.create_connection((host, port), timeout=2.0) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock: ssock.do_handshake()
                return int((time.perf_counter() - t0) * 1000), "TLS"
        except Exception: pass
        return 9999, "Ошибка"

    def start_ping_all(self):
        if not self.filtered_servers:
            return messagebox.showwarning("Внимание", "Нет серверов для пинга!")
        self.btn_ping.configure(state="disabled", text="Проверяем...")

        def check_one(s):
            h, p = CoreParser.extract_host_port(s["url"])
            s["ping"], s["method"] = self.measure_ping(h, p) if h and p else (9999, "Ошибка")

        def worker():
            with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
                list(ex.map(check_one, self.filtered_servers))
            self.after(0, self.finish_ping)

        threading.Thread(target=worker, daemon=True).start()

    def finish_ping(self):
        self.btn_ping.configure(state="normal", text="Проверить доступность")
        self.combo_sort.set("По пингу (сначала быстрые)")
        self.display_servers()

    def on_filter_changed(self, _choice):
        if self.current_servers: self.display_servers()

    def display_servers(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        
        f_proto = self.combo_proto.get()
        f_country = self.combo_country.get()
        mode = self.combo_sort.get()

        filtered = []
        for s in self.current_servers:
            main_proto = s["protocol_info"].split(" / ")[0]
            if f_proto != "Все" and main_proto != f_proto:
                continue

            flag = s.get("flag_data")
            c_label = f"{flag['emoji']} {flag['alpha2']}" if flag else "🌍 Без флага"
            if f_country != "Все" and c_label != f_country:
                continue
                
            filtered.append(s)

        if mode == "По названию (А - Я)": filtered.sort(key=lambda x: x["name"].lower())
        elif mode == "По названию (Я - А)": filtered.sort(key=lambda x: x["name"].lower(), reverse=True)
        elif mode == "По пингу (сначала быстрые)": filtered.sort(key=lambda x: x["ping"] if x["ping"] is not None else 9999)
        
        self.filtered_servers = filtered

        for s in filtered:
            self.add_link_card(s["url"], s["name"], s["protocol_info"], s["ping"], s["method"], s.get("flag_data"))

    def load_flag_async(self, flag_data, label_widget):
        if not flag_data: return
        code = flag_data["code"]
        if code in self.flag_cache:
            if self.flag_cache[code]: label_widget.configure(image=self.flag_cache[code], compound="left", padx=5)
            return

        if code in self.flag_waiters:
            self.flag_waiters[code].append(label_widget)
            return
        self.flag_waiters[code] = [label_widget]

        def fetch():
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{code}.png"
            img = None
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=3, context=ctx) as r:
                    pil_img = Image.open(io.BytesIO(r.read())).convert("RGBA")
                    img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(20, 20))
            except Exception: pass

            def apply():
                self.flag_cache[code] = img
                for w in self.flag_waiters.pop(code, []):
                    try:
                        if w.winfo_exists() and img: w.configure(image=img, compound="left", padx=5)
                    except Exception: pass
            self.after(0, apply)

        threading.Thread(target=fetch, daemon=True).start()

    def add_link_card(self, url, name, protocol_info, ping, method, flag_data):
        bg = ("#2b2b2b", "#242424")
        card = ctk.CTkFrame(self.scroll_frame, fg_color=bg)
        card.pack(fill="x", padx=6, pady=4)

        right = ctk.CTkFrame(card, fg_color=bg)
        right.pack(side="right", padx=(10, 10), pady=8)
        ctk.CTkButton(right, text="Скопировать", width=100, height=28, fg_color="#2b8a3e", hover_color="#237032", command=lambda u=url: (self.clipboard_clear(), self.clipboard_append(u))).pack(side="right")

        if ping is not None:
            col = "#e74c3c" if ping == 9999 else ("#2b8a3e" if ping < 150 else ("#e67e22" if ping < 350 else "#e74c3c"))
            txt = "n/a" if ping == 9999 else f"{ping} ms ({method})"
            ctk.CTkLabel(right, text=txt, font=ctk.CTkFont(size=11, weight="bold"), text_color=col, fg_color=bg).pack(side="right", padx=(0, 15))

        left = ctk.CTkFrame(card, fg_color=bg)
        left.pack(side="left", fill="x", expand=True, padx=(10, 10), pady=6)
        lbl = ctk.CTkLabel(left, text=name, font=ctk.CTkFont(weight="bold", size=13), anchor="w", fg_color=bg)
        lbl.pack(anchor="w")
        self.load_flag_async(flag_data, lbl)
        ctk.CTkLabel(left, text=protocol_info, font=ctk.CTkFont(size=11), text_color="#8a9ba8", anchor="w", fg_color=bg).pack(anchor="w", pady=(1, 0))

    # ================= ОКНО СЫРЫХ ДАННЫХ =================
    def show_raw_data(self):
        if not self.raw_subscription_text: return messagebox.showwarning("Внимание", "Сначала получите подписку!")
        base = CoreParser.try_decode_base64_subscription(self.raw_subscription_text) or self.raw_subscription_text
        direct = CoreParser.extract_direct_link_data(base)

        if direct: txt = CoreParser.format_decoded_dict(direct)
        else:
            try:
                cfgs = json.loads(base)
                txt = "\n\n\n".join(f"{'='*60}\n                   БЛОК КОНФИГУРАЦИИ #{i}\n{'='*60}\n{json.dumps(item, ensure_ascii=False, indent=2)}" for i, item in enumerate(cfgs if isinstance(cfgs, list) else [cfgs], 1))
            except Exception:
                out = []
                for idx, ln in enumerate((l.strip() for l in urllib.parse.unquote(base).splitlines() if l.strip()), 1):
                    d = CoreParser.extract_direct_link_data(ln)
                    out.append(CoreParser.format_decoded_dict(d, header=f"СЕРВЕР #{idx}") if d else ln)
                txt = "\n\n".join(out)

        win = ctk.CTkToplevel(self)
        win.title("Сырые данные (для отладки)")
        win.geometry(f"800x600+{(self.winfo_screenwidth()-800)//2}+{(self.winfo_screenheight()-600)//2}")
        win.transient(self)
        win.grab_set()
        win.focus_force()

        ctk.CTkLabel(win, text="⚠ Перед тем как отправлять кому-то этот текст — удалите/замените\nсвой UUID, пароль и токен из ссылки на подписку!", text_color="#e67e22", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(10, 5))
        tb = ctk.CTkTextbox(win, wrap="word", font=ctk.CTkFont(size=12))
        tb.pack(fill="both", expand=True, padx=10, pady=10)
        tb.insert("1.0", txt)
        ctk.CTkButton(win, text="Скопировать всё", command=lambda: (self.clipboard_clear(), self.clipboard_append(tb.get("1.0", "end-1c")))).pack(pady=(0, 10))

if __name__ == "__main__":
    app = SubstractorApp()
    app.mainloop()