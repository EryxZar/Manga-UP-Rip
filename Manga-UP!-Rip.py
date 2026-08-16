"""
Manga UP! Downloader - GUI
Author: EryxZar

El login por OAuth de Square Enix no se puede replicar de forma confiable desde
un script de escritorio: el flujo real pasa por Play Integrity API de Google
(attestation atada al dispositivo Android), que no se puede falsificar desde
Python. Por eso el programa no intenta loguearse solo.

En su lugar: el usuario se loguea UNA VEZ en la app real de Manga UP! (con un
proxy tipo mitmproxy/HTTP Toolkit) y pega aquí el uuid que queda vinculado a su
cuenta (aparece en cualquier petición a la API después del login exitoso, ej:
".../start?...&uuid=XXXXXXXX-...", ".../my_page?...&uuid=XXXXXXXX-..."). Ese
uuid se guarda en config.json y se reusa en todas las peticiones de lectura.

Cambios de esta versión:
  - Se agregó la descarga real de imágenes (antes era un TODO). Se portó la
    lógica ya probada del script de consola: chapter_read_confirm -> se
    determina el método de lectura (gratis / ticket / coin) -> viewer/read
    devuelve las URLs de página -> se descargan con el header de imagen
    (Dalvik UA) que usa la app real.
  - Se agregó un panel de billetera (estilo Webtoon) que muestra Coin,
    Ticket naranja (común, sirve en cualquier serie con opción de ticket
    verde) y Ticket azul (de título/serie específico, campo "65" según lo
    reportado por el usuario).
  - NOTA sobre los índices de campo de "my_page" (billetera): estos números
    se dedujeron por prueba y error contra respuestas reales. Si el número
    de ticket azul no coincide con lo que ves en la app, revisa el log de
    depuración (se imprime el nodo completo cada vez que se actualiza la
    billetera) y ajusta el índice en extraer_billetera().
  - Los capítulos que solo se pueden desbloquear viendo un anuncio (video
    reward) todavía no están soportados en la GUI -> se saltan con un aviso;
    para esos, usa la versión de consola (que sí permite inyectar el token
    capturado manualmente).
  - Etiquetas de capítulo simplificadas: ya no se distingue en la lista si un
    capítulo de pago se desbloquea con ticket bonus/título/común o con coin;
    todos muestran "TICKET/COIN-N" donde N es el costo en coin del capítulo.
  - NUEVO: clasificación de la lista SIN llamadas de red por capítulo.
    chapter_list (la misma respuesta que ya usamos para sacar id/título) ya
    trae el costo real ("4", el mismo campo que antes solo veíamos dentro de
    chapter_read_confirm) y un campo "22" que, por los casos observados,
    parece indicar el estado de desbloqueo:
        - sin "4" (ausente)            -> gratis (proto3 omite costo=0)
        - "4" presente y "22"==2       -> de pago, ticket ya usable ahora
        - "4" presente y "22"==1       -> de pago, ticket aún NO disponible
                                          (a veces viene "17" con la fecha,
                                          ej. "8月14日にチケットが使えます")
        - "4" presente y "22" con otro valor / ausente -> de pago genérico
    Esto es SOLO para la etiqueta que se muestra en la lista -> es una pista
    rápida, no una fuente 100% confirmada (se dedujo de pocos casos). La
    descarga real SIEMPRE vuelve a confirmar con chapter_read_confirm justo
    antes de bajar cada capítulo, así que aunque la etiqueta se equivoque en
    algún caso raro, la descarga en sí sigue siendo correcta.
    Con esto, chapter_read_confirm ya NO se llama para toda la lista -> solo
    se llama una vez (al primer capítulo de pago que haya) para leer el
    estado de recarga del ticket bonus (dato global de la cuenta, no por
    capítulo), y después una vez por cada capítulo que el usuario realmente
    decide descargar.
"""
from __future__ import annotations
import json
import os
import re
import sys
import threading
import time
from datetime import datetime

import requests
import blackboxprotobuf

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

# ------------------------------------------------------------------
# Textos (ES/EN)
# ------------------------------------------------------------------
T = {
    "es": {
        "app_title": "Manga UP! Downloader",
        "lang_sel": "Selecciona tu idioma / Select your language",
        "no_uuid": "🔴 Sin UUID configurado",
        "uuid_btn": "Configurar UUID",
        "change_uuid": "Cambiar UUID",
        "url_ph": "Ingresa URL o ID de la serie (ej: 1380)",
        "analyze": "Analizar",
        "ep_list": "Lista de Capítulos",
        "quick_sel": "Selección Rápida\n(Ej: 1-5, 8, 10)",
        "ranges": "Rangos...",
        "select": "Seleccionar",
        "clear": "Limpiar Selección",
        "download": "📥 DESCARGAR",
        "uuid_label": "UUID vinculado a tu cuenta:",
        "uuid_help": ("Se consigue logueándote una vez en la app real (con un proxy) y "
                      "copiando el uuid de cualquier petición posterior al login, ej:\n"
                      "  .../start?...&uuid=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"),
        "save": "Guardar",
        "err_empty": "Completa todos los campos.",
        "err_uuid_fmt": "Eso no parece un uuid válido (formato: 8-4-4-4-12 caracteres hex).",
        "err_no_uuid": "Primero configura tu uuid (botón arriba a la derecha).",
        "err_url": "URL o ID inválido.",
        "err_fmt": "Formato de rango inválido. Usa comas y guiones (ej: 1, 3, 5-10)",
        "err_no_sel": "No has seleccionado ningún capítulo para descargar.",
        "uuid_saved": "UUID guardado: {}",
        "analyzing": "\nAnalizando serie ID {}...",
        "no_series": "No se encontró la serie, no tiene capítulos, o el uuid no tiene acceso.",
        "series_info": "Serie ID {} | {} capítulos encontrados.",
        "classifying": "🔍 Etiquetando {} capítulo(s) desde la lista (sin llamadas extra)...",
        "progress_classify": "🔍 Clasificando {}/{}",
        "progress_download": "📥 Descargando {}/{}",
        "analysis_ok": "✅ Análisis completado.",
        "sel_range": "Seleccionados por rango: {}",
        "init_dl": "\n🚀 INICIANDO DESCARGA...",
        "dl_done": "\n✅ PROCESO DE DESCARGA FINALIZADO.",
        "eval_cap": "\n--- Descargando: {} ---",
        "ads_skip": "  📺 Este capítulo solo se desbloquea viendo un anuncio (no soportado aún en la GUI). Usa la versión de consola. Saltando...",
        "no_pages": "  ❌ No se pudieron obtener páginas (¿monedas/tickets insuficientes?). Saltando...",
        "dl_pages_found": "  {} páginas encontradas. Descargando...",
        "dl_chapter_ok": "  ✅ {}/{} páginas descargadas.",
        "dl_chapter_fail": "  ⚠️ Solo se descargaron {}/{} páginas.",
        "wallet_err": "[-] No se pudo consultar la billetera.",
        "gift_ticket_found": "🎁 Tienes {} ticket(s) de regalo para esta serie (vence: {}).",
        "fatal_err": "Error fatal en Cap {}: {}",
        "bonus_available": "✅ disponible",
        "bonus_recharge": "⏳ recarga en {}h {:02d}m",
        "bonus_recharge_raw": "⏳ {}",
        "label_free": "GRATIS/YA-DESBLOQ.",
        "label_acquired": "ADQUIRIDO",
        "label_acquired_expires": "ADQUIRIDO (vence: {})",
    },
    "en": {
        "app_title": "Manga UP! Downloader",
        "lang_sel": "Select your language / Selecciona tu idioma",
        "no_uuid": "🔴 No UUID configured",
        "uuid_btn": "Configure UUID",
        "change_uuid": "Change UUID",
        "url_ph": "Enter URL or series ID (e.g., 1380)",
        "analyze": "Analyze",
        "ep_list": "Chapter List",
        "quick_sel": "Quick Select\n(E.g., 1-5, 8, 10)",
        "ranges": "Ranges...",
        "select": "Select",
        "clear": "Clear Selection",
        "download": "📥 DOWNLOAD",
        "uuid_label": "UUID linked to your account:",
        "uuid_help": ("Get it by logging into the real app once (with a proxy) and copying "
                      "the uuid from any request after login, e.g.:\n"
                      "  .../start?...&uuid=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"),
        "save": "Save",
        "err_empty": "Please fill in all fields.",
        "err_uuid_fmt": "That doesn't look like a valid uuid (format: 8-4-4-4-12 hex chars).",
        "err_no_uuid": "Configure your uuid first (button top-right).",
        "err_url": "Invalid URL or ID.",
        "err_fmt": "Invalid range format. Use commas and hyphens (e.g., 1, 3, 5-10)",
        "err_no_sel": "You haven't selected any chapters to download.",
        "uuid_saved": "UUID saved: {}",
        "analyzing": "\nAnalyzing series ID {}...",
        "no_series": "Series not found, has no chapters, or the uuid has no access.",
        "series_info": "Series ID {} | {} chapters found.",
        "classifying": "🔍 Labeling {} chapter(s) from the list (no extra calls)...",
        "progress_classify": "🔍 Classifying {}/{}",
        "progress_download": "📥 Downloading {}/{}",
        "analysis_ok": "✅ Analysis completed.",
        "sel_range": "Selected by range: {}",
        "init_dl": "\n🚀 STARTING DOWNLOAD...",
        "dl_done": "\n✅ DOWNLOAD PROCESS FINISHED.",
        "eval_cap": "\n--- Downloading: {} ---",
        "ads_skip": "  📺 This chapter only unlocks by watching an ad (not supported in the GUI yet). Use the console version. Skipping...",
        "no_pages": "  ❌ Couldn't fetch pages (insufficient coins/tickets?). Skipping...",
        "dl_pages_found": "  {} pages found. Downloading...",
        "dl_chapter_ok": "  ✅ {}/{} pages downloaded.",
        "dl_chapter_fail": "  ⚠️ Only {}/{} pages downloaded.",
        "wallet_err": "[-] Couldn't fetch the wallet.",
        "gift_ticket_found": "🎁 You have {} gift ticket(s) for this series (expires: {}).",
        "fatal_err": "Fatal error in Ch {}: {}",
        "bonus_available": "✅ available",
        "bonus_recharge": "⏳ recharges in {}h {:02d}m",
        "bonus_recharge_raw": "⏳ {}",
        "label_free": "FREE/UNLOCKED",
        "label_acquired": "ACQUIRED",
        "label_acquired_expires": "ACQUIRED (expires: {})",
    },
}

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "Download")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "manga_up_debug.log")

UUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')

IMG_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 9; SM-G9880 Build/PQ3A.190705.05150936)"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# ------------------------------------------------------------------
# Cliente de la API de Manga UP!
# ------------------------------------------------------------------
class MangaUpApi:
    def __init__(self):
        self.base_url = "https://ja-android.manga-up.com/v2/api"
        self.secret = "ccb203a682ba10f07c286873dab0452a"
        self.app_ver = "8110001"
        self.os_ver = "28"
        self.uuid = None  # se setea desde la GUI con el uuid pegado por el usuario

    def _headers(self):
        return {
            "User-Agent": "okhttp/4.12.0",
            "Accept-Encoding": "gzip",
            "Connection": "Keep-Alive",
        }

    def _base_params(self, api_name):
        return {
            "api": api_name,
            "secret": self.secret,
            "hash": "0" * 32,
            "uuid": self.uuid,
            "os": "android",
            "app_ver": self.app_ver,
            "os_ver": self.os_ver,
        }

    def hacer_peticion(self, endpoint, api_name, extra_params=None):
        if not self.uuid:
            print("[-] No hay uuid configurado.")
            return None

        params = self._base_params(api_name)
        if extra_params:
            params.update(extra_params)

        try:
            response = requests.get(f"{self.base_url}/{endpoint}", params=params, headers=self._headers(), timeout=20)
            print(f"[DEBUG] {endpoint} -> status {response.status_code}")
            if response.status_code == 200:
                return response.content
            print(f"[DEBUG] {endpoint} body (primeros 300 bytes): {response.content[:300]!r}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] {endpoint} excepción de red: {e}")
            return None

    def hacer_peticion_post(self, endpoint, api_name, extra_params=None):
        if not self.uuid:
            print("[-] No hay uuid configurado.")
            return None

        params = self._base_params(api_name)
        if extra_params:
            params.update(extra_params)

        try:
            response = requests.post(f"{self.base_url}/{endpoint}", data=params, headers=self._headers(), timeout=20)
            print(f"[DEBUG] POST {endpoint} -> status {response.status_code}")
            if response.status_code == 200:
                return response.content
            return None
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] {endpoint} excepción de red (POST): {e}")
            return None

    def decodificar_protobuf(self, raw_bytes):
        try:
            message, _ = blackboxprotobuf.decode_message(raw_bytes)

            def clean(obj):
                if isinstance(obj, bytes):
                    try:
                        return obj.decode("utf-8")
                    except UnicodeDecodeError:
                        return obj.hex()
                if isinstance(obj, dict):
                    return {k: clean(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [clean(item) for item in obj]
                return obj

            return clean(message)
        except Exception as e:
            print(f"[DEBUG] Error decodificando protobuf: {e}")
            return None

    # -- Endpoints ------------------------------------------------------
    def obtener_lista_capitulos(self, title_id):
        raw_bytes = self.hacer_peticion("chapter_list", "chapter_list", extra_params={"title_id": title_id})
        if raw_bytes:
            return self.decodificar_protobuf(raw_bytes)
        return None

    def obtener_confirmacion_lectura(self, chapter_id):
        raw_bytes = self.hacer_peticion("chapter_read_confirm", "chapter_read_confirm", extra_params={"chapter_id": chapter_id})
        if not raw_bytes:
            return None
        return self.decodificar_protobuf(raw_bytes)

    def obtener_paginas_capitulo(self, chapter_id, chapter_status="free_chapter", extra_params=None):
        params = {"chapter_id": chapter_id, "chapter_status": chapter_status}
        if extra_params:
            params.update(extra_params)
        raw_bytes = self.hacer_peticion("viewer/read", "viewer/read", extra_params=params)
        if not raw_bytes:
            return None
        return self.decodificar_protobuf(raw_bytes)

    def obtener_billetera(self):
        raw_bytes = self.hacer_peticion("my_page", "my_page")
        if not raw_bytes:
            return None
        return self.decodificar_protobuf(raw_bytes)

    def obtener_app_setting(self):
        raw_bytes = self.hacer_peticion("app_setting", "app_setting")
        if not raw_bytes:
            return None
        return self.decodificar_protobuf(raw_bytes)

    def descargar_imagen(self, url, ruta_destino, retries=3):
        headers = {
            "User-Agent": IMG_USER_AGENT,
            "Accept-Encoding": "gzip",
            "Connection": "Keep-Alive",
        }
        for intento in range(retries):
            try:
                resp = requests.get(url, headers=headers, timeout=20)
                if resp.status_code == 200:
                    with open(ruta_destino, "wb") as f:
                        f.write(resp.content)
                    return True
                print(f"[DEBUG] HTTP {resp.status_code} descargando imagen (intento {intento + 1}/{retries})")
            except requests.exceptions.RequestException as e:
                print(f"[DEBUG] Error de red descargando imagen (intento {intento + 1}/{retries}): {e}")
            time.sleep(0.5)
        return False


# ------------------------------------------------------------------
# Parseo de respuestas protobuf
# ------------------------------------------------------------------
def extraer_capitulos(data):
    try:
        capitulos_raw = data.get("1", {}).get("48", {}).get("1", [])
        capitulos = []
        for cap in capitulos_raw:
            capitulos.append({
                "id": cap.get("1"),
                "title": cap.get("2"),
                "costo_coin": cap.get("4"),
                "tipo_desbloqueo": cap.get("22"),
                "ticket_fecha": cap.get("17", ""),
                "ya_adquirido": cap.get("21") is not None,
                "expira_ts": cap.get("12"),
            })
        return capitulos
    except Exception as e:
        print(f"[DEBUG] Error extrayendo capítulos: {e}")
        return []


def extraer_paginas(data):
    try:
        items = data.get("1", {}).get("15", {}).get("1", {}).get("1", [])
        urls = []
        for item in items:
            pagina = item.get("1")
            if isinstance(pagina, dict):
                url = pagina.get("1", "")
                if isinstance(url, str) and url.startswith("http"):
                    urls.append(url)
        return urls
    except Exception as e:
        print(f"[DEBUG] Error extrayendo páginas: {e}")
        return []


def determinar_metodo_lectura(confirm_data):
    nodo_58 = confirm_data.get("1", {}).get("58", {}) if confirm_data else {}
    costo_coin = nodo_58.get("1", {}).get("4")

    if not costo_coin:
        return "free_chapter", {}, "(gratis / ya desbloqueado)", {}

    recarga_texto = nodo_58.get("2", {}).get("3", "")
    opcion = nodo_58.get("9")
    texto = ""
    ad_disponible = False

    if isinstance(opcion, dict):
        texto = opcion.get("2", "")
    elif isinstance(opcion, list):
        opciones_txt = []
        for o in opcion:
            if not isinstance(o, dict):
                continue
            texto_o = o.get("2", "")
            opciones_txt.append(texto_o)
            if o.get("1") == 4 or "広告動画" in texto_o:
                ad_disponible = True
        texto = f"(sin fondos suficientes: {', '.join(opciones_txt)})"

    if "ボーナスチケット" in texto:
        disponible = ("チャージ完了" in recarga_texto) or not recarga_texto
        estado = "disponible ahora" if disponible else f"recarga en {recarga_texto}"
        info = {
            "costo_coin": costo_coin,
            "bonus_disponible": disponible,
            "bonus_recarga_texto": recarga_texto,
        }
        return "ticket_chapter", {"bonus_ticket": 1}, f"{texto} ({estado})", info

    if "作品チケット" in texto:
        return "ticket_chapter", {"title_ticket": 1}, texto, {"costo_coin": costo_coin}
    if "共通チケット" in texto:
        return "ticket_chapter", {"common_ticket": 1}, texto, {"costo_coin": costo_coin}

    extra = {"limited_free_coin": costo_coin}
    if ad_disponible:
        extra["ad_disponible"] = True

    return "coin_chapter", extra, texto or "コインで読む", {"costo_coin": costo_coin}


def etiquetar(chapter_status, costo_coin):
    if chapter_status == "free_chapter":
        return "GRATIS/YA-DESBLOQ."
    valor = costo_coin if costo_coin is not None else "?"
    if chapter_status == "ticket_chapter":
        return f"TICKET/COIN-{valor}"
    return f"COIN-{valor}"


def es_desbloqueado_gratis(cap):
    return bool(cap.get("ya_adquirido")) or not cap.get("costo_coin")


def etiquetar_desde_lista(cap, lang="es"):
    textos = T.get(lang, T["es"])
    if cap.get("ya_adquirido"):
        expira_ts = cap.get("expira_ts")
        if expira_ts:
            try:
                fecha = datetime.fromtimestamp(expira_ts).strftime("%Y-%m-%d %H:%M")
                return textos["label_acquired_expires"].format(fecha)
            except (ValueError, OSError, OverflowError):
                return textos["label_acquired"]
        return textos["label_acquired"]
    costo = cap.get("costo_coin")
    if not costo:
        return textos["label_free"]
    tipo = cap.get("tipo_desbloqueo")
    if tipo == 2:
        return f"TICKET/COIN-{costo}"
    return f"COIN-{costo}"


def obtener_estado_bonus_ticket(api, capitulos):
    primer_pago = next(
        (c for c in capitulos if c.get("costo_coin") and not c.get("ya_adquirido")), None
    )
    if not primer_pago:
        return {}
    confirm_data = api.obtener_confirmacion_lectura(primer_pago["id"])
    nodo_58 = confirm_data.get("1", {}).get("58", {}) if confirm_data else {}
    recarga_texto = nodo_58.get("2", {}).get("3", "")
    disponible = ("チャージ完了" in recarga_texto) or not recarga_texto
    return {"disponible": disponible, "texto": recarga_texto}


def extraer_billetera(data):
    try:
        nodo = data.get("1", {}).get("56", {})
        ticket_info = nodo.get("6", {})
        return {
            "coin": nodo.get("1", 0),
            "ticket_naranja_actual": ticket_info.get("1", 0),
            "ticket_naranja_max": ticket_info.get("2", 0),
            "ticket_naranja_recarga": ticket_info.get("3", ""),
            "ticket_azul": nodo.get("7", 0),
            "raw": nodo,
        }
    except Exception as e:
        print(f"[DEBUG] Error extrayendo billetera: {e}")
        return None


def extraer_cuenta(data):
    try:
        nodo = data.get("1", {}).get("29", {})
        return {
            "nombre": nodo.get("4", ""),
            "avatar_url": nodo.get("3", ""),
        }
    except Exception as e:
        print(f"[DEBUG] Error extrayendo cuenta: {e}")
        return None


def extraer_tickets_regalo(data):
    try:
        items = data.get("8", {}).get("2")
        if items is None:
            items = data.get("1", {}).get("8", {}).get("2", [])
        regalos = []
        for item in items:
            if not isinstance(item, dict):
                continue
            regalos.append({
                "ticket_id": item.get("1"),
                "title_id": item.get("2"),
                "cantidad": item.get("3", 0),
                "vence": item.get("4", ""),
                "titulo": item.get("5", ""),
            })
        return regalos
    except Exception as e:
        print(f"[DEBUG] Error extrayendo tickets de regalo: {e}")
        return []


def parsear_recarga_tiempo(texto_jp):
    m = re.search(r'(\d+)\s*時間\s*(\d+)\s*分', texto_jp or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def sanitizar_nombre(nombre):
    return re.sub(r'[\\/*?:"<>|]', "-", str(nombre)).strip()


def cargar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def guardar_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# GUI
# ------------------------------------------------------------------
class PrintRedirector:
    def __init__(self, textbox, root, log_path):
        self.textbox = textbox
        self.root = root
        self.log_file = open(log_path, "a", encoding="utf-8")
        self.log_file.write(f"\n===== Sesión iniciada: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        self.log_file.flush()
        self._buffer = ""

    def write(self, text):
        if not text:
            return

        self.log_file.write(text)
        self.log_file.flush()

        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line and not line.lstrip().startswith("[DEBUG]"):
                self._append_line(line)

    def _append_line(self, line):
        self.textbox.configure(state="normal")
        self.textbox.insert(tk.END, line + "\n")
        self.textbox.see(tk.END)
        self.textbox.configure(state="disabled")
        self.root.update_idletasks()

    def flush(self):
        pass


class MangaUpDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Manga UP! Downloader")
        self.geometry("880x760")

        self.api = MangaUpApi()
        self.chapters_data = []
        self.checkboxes = {}
        self.current_series_id = None
        self.tickets_regalo = []

        self.ticket_azul_count = None
        self.bonus_recarga_info = None

        self.lang = "es"
        self._build_language_selector()

    def t(self, key, *args):
        text = T[self.lang].get(key, key)
        return text.format(*args) if args else text

    def _build_language_selector(self):
        self.lang_frame = ctk.CTkFrame(self)
        self.lang_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        ctk.CTkLabel(self.lang_frame, text=T["es"]["lang_sel"], font=("Arial", 16, "bold")).pack(pady=20, padx=40)
        btn_frame = ctk.CTkFrame(self.lang_frame, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="Español", command=lambda: self._set_language("es"), width=120).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="English", command=lambda: self._set_language("en"), width=120).pack(side="right", padx=10)

    def _set_language(self, chosen_lang):
        self.lang = chosen_lang
        self.lang_frame.destroy()
        self.title(self.t("app_title"))
        self._build_gui()
        sys.stdout = PrintRedirector(self.log_console, self, LOG_FILE)

        config = cargar_config()
        uuid_guardado = config.get("uuid")
        if uuid_guardado and UUID_RE.match(uuid_guardado):
            self.api.uuid = uuid_guardado
            self.update_uuid_status(uuid_guardado)
            self.start_wallet_refresh_thread()

    def _build_gui(self):
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.status_indicator = ctk.CTkLabel(
            self.header_frame, text=self.t("no_uuid"), font=("Arial", 14, "bold"), text_color="red"
        )
        self.status_indicator.pack(side="left", padx=10)

        self.uuid_btn = ctk.CTkButton(self.header_frame, text=self.t("uuid_btn"), command=self.open_uuid_window)
        self.uuid_btn.pack(side="right", padx=10)

        self.wallet_frame = ctk.CTkFrame(self)
        self.wallet_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.coin_label = ctk.CTkLabel(self.wallet_frame, text="🪙 --", font=("Arial", 13, "bold"))
        self.coin_label.pack(side="left", padx=(10, 18))

        self.naranja_label = ctk.CTkLabel(
            self.wallet_frame, text="🟠 --/--", font=("Arial", 13, "bold"), text_color="orange"
        )
        self.naranja_label.pack(side="left", padx=(0, 18))

        self.azul_label = ctk.CTkLabel(
            self.wallet_frame, text="🔵 --", font=("Arial", 13, "bold"), text_color="#4da6ff"
        )
        self.azul_label.pack(side="left", padx=(0, 18))

        self.wallet_refresh_btn = ctk.CTkButton(
            self.wallet_frame, text="🔄", width=36, command=self.start_wallet_refresh_thread
        )
        self.wallet_refresh_btn.pack(side="right", padx=10)

        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(fill="x", padx=10, pady=5)

        self.url_entry = ctk.CTkEntry(self.search_frame, placeholder_text=self.t("url_ph"), width=500)
        self.url_entry.pack(side="left", padx=10, pady=10, expand=True, fill="x")

        self.analyze_btn = ctk.CTkButton(self.search_frame, text=self.t("analyze"), command=self.start_analysis_thread)
        self.analyze_btn.pack(side="right", padx=10)

        self.center_frame = ctk.CTkFrame(self)
        self.center_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.episodes_scroll = ctk.CTkScrollableFrame(self.center_frame, label_text=self.t("ep_list"))
        self.episodes_scroll.pack(side="left", fill="both", expand=True, padx=(5, 5), pady=5)

        self.action_frame = ctk.CTkFrame(self.center_frame, width=250)
        self.action_frame.pack(side="right", fill="y", padx=(5, 5), pady=5)

        ctk.CTkLabel(self.action_frame, text=self.t("quick_sel"), font=("Arial", 12, "bold")).pack(pady=10)
        self.range_entry = ctk.CTkEntry(self.action_frame, placeholder_text=self.t("ranges"), width=200)
        self.range_entry.pack(pady=5, padx=10)
        self.range_entry.bind("<Return>", lambda event: self.apply_range_selection())

        ctk.CTkButton(self.action_frame, text=self.t("select"), command=self.apply_range_selection).pack(pady=5)
        ctk.CTkButton(self.action_frame, text=self.t("clear"), command=self.clear_selection, fg_color="gray").pack(pady=5)

        self.download_btn = ctk.CTkButton(
            self.action_frame, text=self.t("download"), command=self.start_download_thread,
            fg_color="green", hover_color="darkgreen", height=40
        )
        self.download_btn.pack(side="bottom", pady=20, padx=10, fill="x")

        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(fill="x", padx=10, pady=5)

        self.progress_label = ctk.CTkLabel(self.log_frame, text="", font=("Arial", 12, "bold"), anchor="w")
        self.progress_label.pack(fill="x", padx=5, pady=(5, 0))

        # NUEVO: Etiqueta dedicada al progreso de descarga de páginas en línea.
        self.page_progress_label = ctk.CTkLabel(self.log_frame, text="", font=("Arial", 12), anchor="w", text_color="#4da6ff")
        self.page_progress_label.pack(fill="x", padx=5, pady=(0, 0))

        self.log_console = ctk.CTkTextbox(self.log_frame, height=150, state="normal")
        self.log_console.pack(fill="both", expand=True, padx=5, pady=5)

    def open_uuid_window(self):
        win = ctk.CTkToplevel(self)
        win.title(self.t("uuid_btn"))
        win.geometry("420x260")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text=self.t("uuid_label"), font=("Arial", 13, "bold")).pack(pady=(15, 5), padx=15)

        uuid_entry = ctk.CTkEntry(win, width=350, placeholder_text="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
        if self.api.uuid:
            uuid_entry.insert(0, self.api.uuid)
        uuid_entry.pack(pady=5, padx=15)

        ctk.CTkLabel(
            win, text=self.t("uuid_help"), font=("Arial", 11), justify="left", wraplength=380, text_color="gray"
        ).pack(pady=10, padx=15)

        def do_save():
            uuid_val = uuid_entry.get().strip()
            if not uuid_val:
                messagebox.showerror("Error", self.t("err_empty"))
                return
            if not UUID_RE.match(uuid_val):
                messagebox.showerror("Error", self.t("err_uuid_fmt"))
                return

            self.api.uuid = uuid_val
            config = cargar_config()
            config["uuid"] = uuid_val
            guardar_config(config)

            print(self.t("uuid_saved", uuid_val))
            self.update_uuid_status(uuid_val)
            self.start_wallet_refresh_thread()
            win.destroy()

        ctk.CTkButton(win, text=self.t("save"), command=do_save).pack(pady=15)

    def update_uuid_status(self, uuid_val):
        self.status_indicator.configure(text=f"🟢 {uuid_val[:8]}...", text_color="green")
        self.uuid_btn.configure(text=self.t("change_uuid"))

    def start_wallet_refresh_thread(self):
        if not self.api.uuid:
            return
        threading.Thread(target=self._refresh_wallet, daemon=True).start()

    def _refresh_wallet(self):
        data = self.api.obtener_billetera()
        billetera = extraer_billetera(data) if data else None
        if not billetera:
            print(self.t("wallet_err"))
        else:
            print(f"[DEBUG] Billetera cruda (nodo 56): {billetera['raw']}")
        self.after(0, lambda: self._actualizar_billetera_ui(billetera))

        setting_data = self.api.obtener_app_setting()
        if setting_data:
            cuenta = extraer_cuenta(setting_data)
            self.tickets_regalo = extraer_tickets_regalo(setting_data)
            if cuenta and cuenta.get("nombre"):
                self.after(0, lambda: self.status_indicator.configure(
                    text=f"🟢 {cuenta['nombre']}", text_color="green"
                ))

    def _actualizar_billetera_ui(self, billetera):
        if not billetera:
            self.coin_label.configure(text="🪙 --")
            self.naranja_label.configure(text="🟠 --/--")
            self.ticket_azul_count = None
            self._render_azul_label()
            return
        self.coin_label.configure(text=f"🪙 {billetera['coin']}")
        self.naranja_label.configure(text=f"🟠 {billetera['ticket_naranja_actual']}/{billetera['ticket_naranja_max']}")
        self.ticket_azul_count = billetera['ticket_azul']
        self._render_azul_label()

    def _actualizar_bonus_ui(self, estado_bonus):
        if not estado_bonus:
            return
        self.bonus_recarga_info = estado_bonus
        self._render_azul_label()

    def _render_azul_label(self):
        count_text = str(self.ticket_azul_count) if self.ticket_azul_count is not None else "--"
        extra = ""
        if self.bonus_recarga_info is not None:
            if self.bonus_recarga_info.get("disponible"):
                extra = f" {self.t('bonus_available')}"
            else:
                recarga = self.bonus_recarga_info.get("texto", "")
                parsed = parsear_recarga_tiempo(recarga)
                if parsed:
                    horas, minutos = parsed
                    extra = f" {self.t('bonus_recharge', horas, minutos)}"
                elif recarga:
                    extra = f" {self.t('bonus_recharge_raw', recarga)}"
        self.azul_label.configure(text=f"🔵 {count_text}{extra}")

    def _set_progress(self, text):
        self.progress_label.configure(text=text)

    def _set_progress_async(self, text):
        self.after(0, lambda: self._set_progress(text))

    # NUEVO: Lógica para actualizar el progreso por página (1/62) en línea
    def _set_page_progress(self, text):
        self.page_progress_label.configure(text=text)

    def _set_page_progress_async(self, text):
        self.after(0, lambda: self._set_page_progress(text))

    def get_series_id(self):
        val = self.url_entry.get().strip()
        if not val:
            return None
        if val.isdigit():
            return val
        match = re.search(r'titles/(\d+)', val)
        return match.group(1) if match else None

    def start_analysis_thread(self):
        if not self.api.uuid:
            messagebox.showwarning("Atención / Warning", self.t("err_no_uuid"))
            return

        series_id = self.get_series_id()
        if not series_id:
            messagebox.showwarning("Error", self.t("err_url"))
            return

        self.analyze_btn.configure(state="disabled")
        print(self.t("analyzing", series_id))

        for widget in self.episodes_scroll.winfo_children():
            widget.destroy()
        self.checkboxes.clear()

        threading.Thread(target=self._process_analysis, args=(series_id,), daemon=True).start()

    def _process_analysis(self, series_id):
        try:
            data = self.api.obtener_lista_capitulos(series_id)
            capitulos = extraer_capitulos(data) if data else []

            if not capitulos:
                print(self.t("no_series"))
                return

            self.current_series_id = series_id
            print(self.t("series_info", series_id, len(capitulos)))

            for regalo in self.tickets_regalo:
                if str(regalo.get("title_id")) == str(series_id):
                    print(self.t("gift_ticket_found", regalo.get("cantidad", 0), regalo.get("vence", "?")))

            print(self.t("classifying", len(capitulos)))
            for cap in capitulos:
                cap["etiqueta"] = etiquetar_desde_lista(cap, self.lang)
                cap["libre"] = es_desbloqueado_gratis(cap)

            estado_bonus = obtener_estado_bonus_ticket(self.api, capitulos)

            self.chapters_data = capitulos
            self.after(0, self._render_checkboxes)
            self.after(0, lambda: self._actualizar_bonus_ui(estado_bonus))
            print(self.t("analysis_ok"))
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self._set_progress_async("")
            self.after(0, lambda: self.analyze_btn.configure(state="normal"))

    def _render_checkboxes(self):
        for idx, cap in enumerate(self.chapters_data, 1):
            etiqueta = cap.get("etiqueta", "?")
            color = "white" if cap.get("libre") else "yellow"
            display_text = f"[{idx}] {cap['title']}  [{etiqueta}]"
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(self.episodes_scroll, text=display_text, variable=var, text_color=color)
            chk.pack(anchor="w", pady=2, padx=5)
            self.checkboxes[idx] = {"var": var, "cap": cap}

    @staticmethod
    def _color_por_etiqueta(etiqueta):
        if etiqueta.startswith("GRATIS") or etiqueta.startswith("ADQUIRIDO"):
            return "white"
        return "yellow"

    def apply_range_selection(self):
        range_str = self.range_entry.get().strip()
        if not range_str:
            return
        selected = set()
        try:
            for part in range_str.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    selected.update(range(start, end + 1))
                else:
                    selected.add(int(part))
            for idx, chk_dict in self.checkboxes.items():
                if idx in selected:
                    chk_dict["var"].set(True)
            print(self.t("sel_range", sorted(selected)))
        except ValueError:
            messagebox.showwarning("Error", self.t("err_fmt"))

    def clear_selection(self):
        for chk_dict in self.checkboxes.values():
            chk_dict["var"].set(False)
        self.range_entry.delete(0, 'end')

    def start_download_thread(self):
        if not self.api.uuid:
            messagebox.showwarning("Atención / Warning", self.t("err_no_uuid"))
            return

        seleccionados = [d["cap"] for d in self.checkboxes.values() if d["var"].get()]
        if not seleccionados:
            messagebox.showwarning("Aviso / Warning", self.t("err_no_sel"))
            return

        self.download_btn.configure(state="disabled")
        threading.Thread(target=self._process_download, args=(seleccionados,), daemon=True).start()

    def _process_download(self, capitulos):
        print(self.t("init_dl"))
        series_dir = os.path.join(DOWNLOAD_DIR, str(self.current_series_id))
        os.makedirs(series_dir, exist_ok=True)

        total = len(capitulos)
        exitosos = 0
        for idx, cap in enumerate(capitulos, 1):
            self._set_progress_async(self.t("progress_download", idx, total))
            print(self.t("eval_cap", cap["title"]))
            try:
                if self._descargar_capitulo(cap, series_dir):
                    exitosos += 1
            except Exception as e:
                print(self.t("fatal_err", cap["title"], str(e)))

            time.sleep(0.5)

        self._set_progress_async("")
        print(self.t("dl_done"))
        self.after(0, lambda: self.download_btn.configure(state="normal"))
        self.start_wallet_refresh_thread()

    def _descargar_capitulo(self, capitulo, series_dir):
        confirm_data = self.api.obtener_confirmacion_lectura(capitulo["id"])
        chapter_status, extra_params, _texto, info = determinar_metodo_lectura(confirm_data)
        capitulo["chapter_status"] = chapter_status
        capitulo["extra_params"] = extra_params
        capitulo["costo_coin"] = info.get("costo_coin", capitulo.get("costo_coin"))

        if extra_params.get("ad_disponible") and chapter_status == "coin_chapter":
            print(self.t("ads_skip"))
            return False

        data = self.api.obtener_paginas_capitulo(capitulo["id"], chapter_status, extra_params)
        urls = extraer_paginas(data) if data else []

        if not urls and chapter_status != "free_chapter":
            confirm_data2 = self.api.obtener_confirmacion_lectura(capitulo["id"])
            chapter_status2, extra_params2, _texto2, _info2 = determinar_metodo_lectura(confirm_data2)
            if (chapter_status2, extra_params2) != (chapter_status, extra_params):
                data = self.api.obtener_paginas_capitulo(capitulo["id"], chapter_status2, extra_params2)
                urls = extraer_paginas(data) if data else []

        if not urls:
            print(self.t("no_pages"))
            return False

        carpeta_capitulo = os.path.join(series_dir, sanitizar_nombre(capitulo["title"]))
        os.makedirs(carpeta_capitulo, exist_ok=True)

        print(self.t("dl_pages_found", len(urls)))
        ok = 0
        
        # NUEVO: Bucle de descarga con actualización del progreso de página
        for i, url in enumerate(urls, 1):
            self._set_page_progress_async(f"  {i}/{len(urls)}")
            
            destino = os.path.join(carpeta_capitulo, f"{i:03d}.webp")
            if os.path.exists(destino):
                ok += 1
                continue
            if self.api.descargar_imagen(url, destino):
                ok += 1

        self._set_page_progress_async("") # Limpiamos el texto al finalizar el capítulo

        if ok == len(urls):
            print(self.t("dl_chapter_ok", ok, len(urls)))
            return True

        print(self.t("dl_chapter_fail", ok, len(urls)))
        return False


if __name__ == "__main__":
    app = MangaUpDownloaderApp()
    app.mainloop()