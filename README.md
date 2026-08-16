# 📥 Manga UP! Downloader - GUI

**Author:** EryxZar

![Manga UP Downloader](https://img.shields.io/badge/Status-Active-success) ![Python](https://img.shields.io/badge/Python-3.8+-blue) ![GUI](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet)

---

## 🇪🇸 Español

Una herramienta con interfaz gráfica (GUI) para descargar capítulos directamente desde Manga UP!. Permite la gestión de descargas, visualización de billetera (monedas y tickets) y selección rápida de rangos de capítulos.

### ⚠️ Nota Importante sobre el Inicio de Sesión
El inicio de sesión mediante OAuth de Square Enix **no se puede replicar** de forma automática desde un script de escritorio porque requiere la validación de *Play Integrity API* de Google (vinculada a un dispositivo Android real). 

Por lo tanto, el programa utiliza un sistema de **UUID**. Solo necesitas iniciar sesión UNA VEZ en la aplicación oficial (usando un proxy) y capturar tu UUID. El programa lo guardará y lo reutilizará para todas las descargas sin necesidad de volver a loguearte.

### ✨ Características
- **Interfaz Gráfica Bilingüe:** Soporte nativo para Español e Inglés.
- **Billetera Integrada:** Visualiza tus Monedas (Coins), Tickets comunes (Naranjas) y Tickets de título (Azules).
- **Lectura Inteligente:** Determina automáticamente el costo del capítulo sin llamadas excesivas a la API para evitar baneos.
- **Descargas en Alta Calidad:** Extrae y descarga directamente las imágenes `.webp` simulando el cliente de Android.
- **Rango de Selección:** Selecciona múltiples capítulos fácilmente (ej: `1-5, 8, 10`).

*(Nota: Los capítulos que requieren ver un anuncio / "Video Reward" actualmente no se pueden descargar desde el programa tiene usted que entrar a la app y ver el Ads.)*

### 🚀 Instalación y Uso

**Opción A: Usar el archivo ejecutable (Fácil)**
1. Ve a la pestaña **[Releases](https://github.com/EryxZar/Manga-UP-Rip/releases/tag/1.0)** en la derecha de esta página.
2. Descarga el archivo `.exe` más reciente.
3. Ejecútalo (no requiere instalar Python).

**Opción B: Desde el código fuente**
1. Clona este repositorio: `https://github.com/EryxZar/Manga-UP-Rip.git`
2. Instala las dependencias: `pip install requests blackboxprotobuf customtkinter`
3. Ejecuta el script: `python Manga-UP!-Rip.py` (o el nombre que le hayas dado al archivo).

### 🔑 ¿Cómo obtener tu UUID?
Para usar el programa necesitas tu UUID personal:
1. Instala una aplicación de proxy o captura de red en tu teléfono o PC (si usas pc debes usar un emulador recomiendo LDplayer 9) (como **HTTP Toolkit** o **mitmproxy**).
2. Abre la aplicación real de *Manga UP!* con el proxy activo e inicia sesión.
3. Busca cualquier petición posterior al inicio de sesión (por ejemplo: `.../start?...` o `.../my_page?...`).
4. Dentro de la URL de esa petición verás un parámetro llamado `&uuid=`.
5. Copia ese código (tiene un formato tipo `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`).
7. Abre el programa en tu PC, haz clic en **Configurar UUID**, pégalo y dale a Guardar. ¡Listo!
*(Nota: Ten en cuenta que el UUID es por dispositivo no por cuenta asi que si usaste un emulador para sacar el UUID y despues iniciaste tu cuenta en tu movil el UUID dejara de funcionar.)*

---
---

## 🇬🇧 English

A GUI tool to download chapters directly from Manga UP!. It features download management, a wallet display (coins and tickets), and quick chapter range selection.

### ⚠️ Important Note on Logging In
Square Enix's OAuth login **cannot be replicated** automatically from a desktop script because it requires Google's *Play Integrity API* validation (tied to a real Android device).

Therefore, the program uses a **UUID** system. You only need to log in ONCE on the official app (using a proxy) and capture your UUID. The program will save it and reuse it for all downloads without needing to log in again.

### ✨ Features
- **Bilingual GUI:** Native support for both Spanish and English.
- **Integrated Wallet:** View your Coins, Common Tickets (Orange), and Title Tickets (Blue).
- **Smart Fetching:** Automatically determines chapter costs without excessive API calls to prevent bans.
- **High-Quality Downloads:** Directly extracts and downloads `.webp` images simulating the Android client.
- **Range Selection:** Easily select multiple chapters (e.g., `1-5, 8, 10`).

*(Note: Chapters that require watching an ad / "Video Reward" currently cannot be downloaded from the program; you have to enter the app and watch the ad.)*

### 🚀 Installation and Usage

**Option A: Using the executable (Easy)**
1. Go to the **[Releases](https://github.com/EryxZar/Manga-UP-Rip/releases/tag/1.0)** tab on the right side of this page.
2. Download the latest `.exe` file.
3. Run it (no Python installation required).

**Option B: From source code**
1. Clone this repository: `https://github.com/EryxZar/Manga-UP-Rip.git`
2. Install the dependencies: `pip install requests blackboxprotobuf customtkinter`
3. Run the script: `python Manga-UP!-Rip.py` (or whatever you named the file).

### 🔑 How to get your UUID?
To use the program, you need your personal UUID:
1. Install a proxy or network capture app on your phone or PC (if you use a PC, you must use an emulator; I recommend LDPlayer 9) (such as **HTTP Toolkit** or **mitmproxy**).
2. Open the real *Manga UP!* app with the proxy active and log in.
3. Look for any request made after logging in (for example: `.../start?...` or `.../my_page?...`).
4. Inside the URL of that request, you will see a parameter called `&uuid=`.
5. Copy that code (it has a format like `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`).
6. Open the program on your PC, click **Configure UUID**, paste it, and save. You're good to go!

*(Note: Keep in mind that the UUID is tied to the device, not the account. If you used an emulator to get the UUID and later log into your account on your mobile phone, the extracted UUID will stop working.)*
