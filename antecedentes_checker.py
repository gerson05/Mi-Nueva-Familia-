"""
Módulo de consulta automatizada de antecedentes para patrocinadores.
Usa Selenium + Chrome DevTools Protocol para navegar y guardar PDFs.

Enfoque semi-automático:
- Pre-llena campos automáticamente
- Pausa para que el usuario resuelva CAPTCHAs o preguntas de seguridad
- Guarda PDF automáticamente vía CDP (sin diálogo de impresión)
"""
import os
import json
import base64
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antecedentes_log.json")
VIGENCIA_MESES = 3

URLS = {
    "policia": "https://antecedentes.policia.gov.co:7005/WebJudicial/index.xhtml",
    "ofac": "https://sanctionssearch.ofac.treas.gov",
    "contraloria": "https://www.contraloria.gov.co/web/guest/persona-natural",
    "procuraduria": "https://www.procuraduria.gov.co/Pages/Generacion-de-antecedentes.aspx",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _crear_driver():
    """Crea Chrome visible (no headless) con soporte CDP para printToPDF."""
    opts = Options()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors=yes")
    # Desactivar pop-ups de impresión
    opts.add_argument("--kiosk-printing")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    return driver


def _print_to_pdf(driver, output_path):
    """Usa CDP Page.printToPDF para guardar como PDF sin diálogo.
    Incluye URL y fecha/hora automáticamente en encabezado/pie."""
    try:
        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "displayHeaderFooter": True,
            "headerTemplate": (
                '<div style="font-size:8px; width:100%; text-align:center; '
                'margin: 0 auto; padding: 0 20px;">'
                '<span class="url"></span></div>'
            ),
            "footerTemplate": (
                '<div style="font-size:8px; width:100%; text-align:center; '
                'margin: 0 auto; padding: 0 20px;">'
                'Consultado: <span class="date"></span> &nbsp;|&nbsp; '
                'Pagina <span class="pageNumber"></span> de '
                '<span class="totalPages"></span></div>'
            ),
            "marginTop": 0.6,
            "marginBottom": 0.6,
            "marginLeft": 0.4,
            "marginRight": 0.4,
            "preferCSSPageSize": False,
        })
        pdf_bytes = base64.b64decode(result["data"])
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return True
    except Exception as e:
        raise RuntimeError(f"Error al generar PDF: {e}")


def _extraer_nombre_ofac(nombre_completo):
    """Extrae primer nombre y primer apellido.
    Formato: NOMBRE1 [NOMBRE2] APELLIDO1 [APELLIDO2]
    4+ palabras: primer nombre (pos 0) + primer apellido (pos 2)
    3 palabras: pos 0 + pos 1
    2 palabras: pos 0 + pos 1
    """
    partes = nombre_completo.strip().split()
    if len(partes) >= 4:
        return partes[0], partes[2]
    elif len(partes) == 3:
        return partes[0], partes[1]
    elif len(partes) == 2:
        return partes[0], partes[1]
    return nombre_completo, ""


def _output_dir_para_patrocinador(nombre):
    """Carpeta de destino en Downloads para un patrocinador."""
    nombre_carpeta = nombre.strip().upper()
    # Limpiar caracteres no válidos para carpetas Windows
    for char in '<>:"/\\|?*':
        nombre_carpeta = nombre_carpeta.replace(char, "")
    carpeta = os.path.join(DOWNLOADS_DIR, nombre_carpeta)
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _esperar_hasta_que_usuario_termine(driver, timeout=300, check_text=None):
    """Espera hasta que el usuario resuelva un CAPTCHA o pregunta de seguridad
    y la página muestre resultados NUEVOS (no texto que ya estaba en la página).
    Timeout default: 5 minutos."""
    url_inicial = driver.current_url
    body_inicial = ""
    try:
        body_inicial = driver.find_element(By.TAG_NAME, "body").text.upper()
    except Exception:
        pass

    # Filtrar check_text: solo considerar textos que NO estén ya en la página
    textos_nuevos = []
    if check_text:
        for txt in check_text:
            if txt.upper() not in body_inicial:
                textos_nuevos.append(txt.upper())

    for _ in range(timeout):
        time.sleep(1)
        try:
            body_actual = driver.find_element(By.TAG_NAME, "body").text.upper()

            # Si hay textos nuevos que aparecieron
            if textos_nuevos:
                for txt in textos_nuevos:
                    if txt in body_actual:
                        time.sleep(3)
                        return True

            # Si la URL cambió (navegación a página de resultado)
            if driver.current_url != url_inicial:
                time.sleep(3)
                return True

            # Si el contenido creció mucho (nuevo contenido cargado)
            if len(body_actual) > len(body_inicial) + 500:
                time.sleep(3)
                return True
        except Exception:
            pass
    return False


def _esperar_descarga(directorio, timeout=120, extension=".pdf"):
    """Monitorea un directorio por archivos nuevos descargados.
    Retorna la ruta del archivo nuevo o None si timeout."""
    archivos_antes = set(os.listdir(directorio))
    for _ in range(timeout):
        time.sleep(1)
        archivos_ahora = set(os.listdir(directorio))
        nuevos = archivos_ahora - archivos_antes
        # Filtrar archivos temporales de Chrome (.crdownload, .tmp)
        nuevos_completos = [
            f for f in nuevos
            if not f.endswith(".crdownload") and not f.endswith(".tmp")
        ]
        if nuevos_completos:
            # Esperar un poco para asegurar descarga completa
            time.sleep(2)
            return os.path.join(directorio, nuevos_completos[0])
    return None


def _esperar_recaptcha(driver, timeout=300):
    """Espera a que el usuario resuelva un reCAPTCHA.
    Detecta el checkbox marcado dentro del iframe de reCAPTCHA."""
    for _ in range(timeout):
        time.sleep(1)
        try:
            # reCAPTCHA vive en un iframe propio
            recaptcha_iframes = driver.find_elements(
                By.CSS_SELECTOR, "iframe[src*='recaptcha'], iframe[title*='reCAPTCHA']"
            )
            for rc_iframe in recaptcha_iframes:
                try:
                    driver.switch_to.frame(rc_iframe)
                    checkbox = driver.find_elements(
                        By.CSS_SELECTOR, ".recaptcha-checkbox-checked, [aria-checked='true']"
                    )
                    if checkbox:
                        driver.switch_to.parent_frame()
                        return True
                    driver.switch_to.parent_frame()
                except Exception:
                    driver.switch_to.parent_frame()
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# Log de vigencia
# ---------------------------------------------------------------------------
def cargar_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar_log(data):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def registrar_consulta(cedula, nombre, fuente, archivo):
    log = cargar_log()
    if cedula not in log:
        log[cedula] = {"nombre": nombre, "consultas": {}}
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    vigente_hasta = (datetime.now() + timedelta(days=VIGENCIA_MESES * 30)).strftime("%Y-%m-%d")
    log[cedula]["consultas"][fuente] = {
        "fecha": fecha_hoy,
        "archivo": archivo,
        "vigente_hasta": vigente_hasta,
    }
    guardar_log(log)


def obtener_vigencia(cedula, fuente):
    """Retorna (vigente: bool, fecha_str, dias_restantes) o (None, None, None)."""
    log = cargar_log()
    if cedula in log and fuente in log[cedula].get("consultas", {}):
        info = log[cedula]["consultas"][fuente]
        vigente_hasta = datetime.strptime(info["vigente_hasta"], "%Y-%m-%d")
        dias = (vigente_hasta - datetime.now()).days
        return dias > 0, info["fecha"], dias
    return None, None, None


# ---------------------------------------------------------------------------
# 1. POLICÍA NACIONAL
# ---------------------------------------------------------------------------
def consultar_policia(cedula, nombre, output_dir, callback=None):
    """Consulta antecedentes judiciales — Policía Nacional.
    Paso 1: Seleccionar radio 'Acepto' y click 'Enviar'.
    Paso 2: Ingresar cédula y consultar."""
    driver = _crear_driver()
    try:
        if callback:
            callback("Abriendo Policia Nacional...")
        driver.get(URLS["policia"])
        time.sleep(4)

        # PASO 1: Aceptar términos — son radio buttons, no checkboxes
        try:
            # Buscar el radio button "Acepto" por su label o valor
            radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            for radio in radios:
                # Intentar por value
                val = (radio.get_attribute("value") or "").lower()
                # Intentar por label cercano
                try:
                    parent = radio.find_element(By.XPATH, "..")
                    label_text = parent.text.strip().lower()
                except Exception:
                    label_text = ""
                if "acepto" in val and "no" not in val:
                    radio.click()
                    break
                if "acepto" in label_text and "no acepto" not in label_text:
                    radio.click()
                    break
            # Si no encontró por value, intentar por XPath con texto
            if not any(r.is_selected() for r in radios if "no" not in (r.get_attribute("value") or "").lower()):
                try:
                    acepto_label = driver.find_element(By.XPATH, "//label[contains(text(),'Acepto') and not(contains(text(),'No'))]")
                    acepto_label.click()
                except Exception:
                    # Click por JavaScript en el primer radio
                    driver.execute_script(
                        "var radios = document.querySelectorAll('input[type=radio]');"
                        "for(var r of radios){ if(r.value && r.value.toLowerCase().includes('acepto') && !r.value.toLowerCase().includes('no')){ r.click(); break; } }"
                    )
            time.sleep(0.5)
        except Exception:
            pass

        # Click en botón "Enviar"
        try:
            btn_enviar = None
            botones = driver.find_elements(By.CSS_SELECTOR, "input[type='submit'], button")
            for btn in botones:
                txt = (btn.text or "").strip().lower()
                val = (btn.get_attribute("value") or "").lower()
                if "enviar" in txt or "enviar" in val:
                    btn_enviar = btn
                    break
            if btn_enviar:
                btn_enviar.click()
            else:
                # Fallback: click en cualquier submit
                for btn in botones:
                    if btn.is_displayed():
                        btn.click()
                        break
            time.sleep(3)
        except Exception:
            pass

        # PASO 2: Página de consulta — ingresar cédula
        try:
            campos = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
            for campo in campos:
                if campo.is_displayed():
                    campo.clear()
                    campo.send_keys(str(cedula))
                    break
            time.sleep(0.5)
        except Exception:
            pass

        # NO hacer click automático en "Consultar" — la página puede tener CAPTCHA
        # El usuario debe completar el CAPTCHA y hacer click manualmente
        if callback:
            callback("Policia: Cedula ingresada. Completa el CAPTCHA (si hay) y haz click en 'Consultar'...")

        # Esperar resultado (el usuario completará CAPTCHA y hará click)
        _esperar_hasta_que_usuario_termine(
            driver, timeout=300,
            check_text=["NO TIENE ASUNTOS PENDIENTES", "REGISTRA ANTECEDENTES",
                        "SU CONSULTA NO ARROJO", "CERTIFICADO"]
        )

        time.sleep(2)

        # Guardar PDF
        fecha = datetime.now().strftime("%Y-%m-%d")
        archivo = f"Policia_Antecedentes_{fecha}.pdf"
        ruta = os.path.join(output_dir, archivo)
        _print_to_pdf(driver, ruta)

        registrar_consulta(cedula, nombre, "policia", archivo)
        if callback:
            callback(f"Policia: PDF guardado -> {archivo}")
        return True, archivo

    except Exception as e:
        return False, str(e)
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# 2. OFAC (Lista Clinton)
# ---------------------------------------------------------------------------
def consultar_ofac(primer_nombre, primer_apellido, cedula, nombre_completo, output_dir, callback=None):
    """Consulta OFAC — 100% automática. Campo Name = primer_nombre + primer_apellido."""
    driver = _crear_driver()
    try:
        busqueda = f"{primer_nombre} {primer_apellido}".strip()
        if callback:
            callback(f"OFAC: Buscando '{busqueda}'...")
        driver.get(URLS["ofac"])
        wait = WebDriverWait(driver, 15)

        # Campo Name
        campo_name = wait.until(EC.presence_of_element_located(
            (By.ID, "ctl00_MainContent_txtLastName")
        ))
        campo_name.clear()
        campo_name.send_keys(busqueda)
        time.sleep(0.5)

        # Click Search
        btn_search = wait.until(EC.element_to_be_clickable(
            (By.ID, "ctl00_MainContent_btnSearch")
        ))
        btn_search.click()

        if callback:
            callback("OFAC: Esperando resultados...")
        time.sleep(5)

        # Guardar PDF
        fecha = datetime.now().strftime("%Y-%m-%d")
        archivo = f"OFAC_{fecha}.pdf"
        ruta = os.path.join(output_dir, archivo)
        _print_to_pdf(driver, ruta)

        registrar_consulta(cedula, nombre_completo, "ofac", archivo)
        if callback:
            callback(f"OFAC: PDF guardado -> {archivo}")
        return True, archivo

    except Exception as e:
        return False, str(e)
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# 3. CONTRALORÍA (reCAPTCHA manual)
# ---------------------------------------------------------------------------
def consultar_contraloria(cedula, nombre, output_dir, callback=None):
    """Consulta Contraloría — Semi-automática.
    Pre-llena tipo doc y cédula. El usuario debe resolver el reCAPTCHA
    y hacer click en 'Buscar'. El sistema detecta el resultado y guarda PDF."""
    driver = _crear_driver()
    try:
        if callback:
            callback("Contraloria: Abriendo pagina...")
        driver.get(URLS["contraloria"])
        time.sleep(6)

        # La Contraloría puede tener el formulario en un iframe
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe")
        contexto_original = False
        for iframe in iframes:
            try:
                driver.switch_to.frame(iframe)
                selects_en_iframe = driver.find_elements(By.CSS_SELECTOR, "select")
                if selects_en_iframe:
                    contexto_original = True
                    break
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()

        # Scroll al formulario
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)

        # Buscar TODOS los selects y campos de texto disponibles
        tipo_llenado = False
        doc_llenado = False

        # Intentar llenar el select de Tipo Documento
        try:
            selects = driver.find_elements(By.CSS_SELECTOR, "select")
            for sel_elem in selects:
                try:
                    if sel_elem.is_displayed() and sel_elem.is_enabled():
                        sel = Select(sel_elem)
                        for opt in sel.options:
                            texto = opt.text.strip().lower()
                            if any(k in texto for k in ["dula", "ciudadan", "c.c", "cedula"]):
                                sel.select_by_visible_text(opt.text)
                                tipo_llenado = True
                                break
                        if tipo_llenado:
                            break
                except Exception:
                    continue
            time.sleep(0.5)
        except Exception:
            pass

        # Si no funcionó con Select, intentar via JavaScript
        if not tipo_llenado:
            try:
                driver.execute_script("""
                    var selects = document.querySelectorAll('select');
                    for(var s of selects){
                        for(var o of s.options){
                            if(o.text.toLowerCase().includes('dula') || o.text.toLowerCase().includes('ciudadan')){
                                s.value = o.value;
                                s.dispatchEvent(new Event('change', {bubbles: true}));
                                break;
                            }
                        }
                    }
                """)
                tipo_llenado = True
            except Exception:
                pass

        # Llenar campo de número de documento
        try:
            campos = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='tel']")
            for campo in campos:
                try:
                    if campo.is_displayed() and campo.is_enabled():
                        placeholder = (campo.get_attribute("placeholder") or "").lower()
                        name = (campo.get_attribute("name") or "").lower()
                        # Verificar que no sea un campo de búsqueda del sitio
                        if any(k in name + placeholder for k in ["search", "buscar", "q"]):
                            continue
                        campo.clear()
                        campo.send_keys(str(cedula))
                        doc_llenado = True
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback JavaScript si no llenó el campo
        if not doc_llenado:
            try:
                driver.execute_script(f"""
                    var inputs = document.querySelectorAll('input[type=text], input[type=number], input[type=tel]');
                    for(var i of inputs){{
                        var n = (i.name || '').toLowerCase();
                        var p = (i.placeholder || '').toLowerCase();
                        if(!n.includes('search') && !p.includes('buscar') && i.offsetParent !== null){{
                            i.value = '{cedula}';
                            i.dispatchEvent(new Event('input', {{bubbles: true}}));
                            i.dispatchEvent(new Event('change', {{bubbles: true}}));
                            break;
                        }}
                    }}
                """)
            except Exception:
                pass

        if callback:
            callback("Contraloria: Resuelve el reCAPTCHA en la ventana de Chrome. El sistema detectara cuando termines...")

        # Volver a default_content para poder acceder al iframe de reCAPTCHA
        if contexto_original:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

        # Esperar a que el usuario resuelva el reCAPTCHA y haga click en Buscar.
        # La Contraloría DESCARGA un PDF directamente al hacer click en Buscar,
        # NO cambia el contenido de la página. Monitoreamos la carpeta de descargas.
        # Obtener la carpeta de descargas de Chrome
        import glob
        downloads_chrome = os.path.join(os.path.expanduser("~"), "Downloads")
        archivos_antes = set(os.listdir(downloads_chrome))

        if callback:
            callback("Contraloria: Cuando resuelvas el reCAPTCHA, haz click en 'Buscar'. El PDF se descargara automaticamente...")

        # Monitorear la carpeta de descargas por un archivo nuevo
        archivo_descargado = None
        for _ in range(300):  # 5 minutos de timeout
            time.sleep(1)
            archivos_ahora = set(os.listdir(downloads_chrome))
            nuevos = archivos_ahora - archivos_antes
            # Filtrar archivos temporales
            nuevos_completos = [
                f for f in nuevos
                if not f.endswith(".crdownload") and not f.endswith(".tmp")
                and (f.lower().endswith(".pdf") or "contraloria" in f.lower()
                     or "persona" in f.lower() or "responsable" in f.lower()
                     or "certificado" in f.lower())
            ]
            if nuevos_completos:
                time.sleep(2)  # Asegurar descarga completa
                archivo_descargado = os.path.join(downloads_chrome, nuevos_completos[0])
                break

        if archivo_descargado and os.path.exists(archivo_descargado):
            # Mover el archivo descargado a la carpeta de destino
            fecha = datetime.now().strftime("%Y-%m-%d")
            archivo = f"Contraloria_Antecedentes_{fecha}.pdf"
            ruta = os.path.join(output_dir, archivo)
            import shutil
            shutil.move(archivo_descargado, ruta)

            registrar_consulta(cedula, nombre, "contraloria", archivo)
            if callback:
                callback(f"Contraloria: PDF guardado -> {archivo}")
            return True, archivo
        else:
            # Fallback: si no se detectó descarga, guardar la página como PDF
            if callback:
                callback("Contraloria: No se detecto descarga. Guardando pagina como PDF...")
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            fecha = datetime.now().strftime("%Y-%m-%d")
            archivo = f"Contraloria_Antecedentes_{fecha}.pdf"
            ruta = os.path.join(output_dir, archivo)
            _print_to_pdf(driver, ruta)
            registrar_consulta(cedula, nombre, "contraloria", archivo)
            if callback:
                callback(f"Contraloria: PDF guardado (captura de pagina) -> {archivo}")
            return True, archivo

    except Exception as e:
        return False, str(e)
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# 4. PROCURADURÍA (pregunta de seguridad dinámica — manual)
# ---------------------------------------------------------------------------
def _resolver_pregunta_matematica(texto_pregunta):
    """Intenta resolver preguntas de seguridad matemáticas.
    Ej: '¿ Cuanto es 5 + 3 ?' -> 8
    Ej: '¿ Cuanto es 12 - 4 ?' -> 8
    Ej: '¿ Cuanto es 3 * 2 ?' -> 6
    Retorna la respuesta como string o None si no pudo resolverla."""
    import re
    # Buscar patrón: número operador número
    match = re.search(r'(\d+)\s*([+\-*xX×÷/])\s*(\d+)', texto_pregunta)
    if match:
        n1 = int(match.group(1))
        op = match.group(2)
        n2 = int(match.group(3))
        if op == '+':
            return str(n1 + n2)
        elif op == '-':
            return str(n1 - n2)
        elif op in ('*', 'x', 'X', '×'):
            return str(n1 * n2)
        elif op in ('/', '÷'):
            return str(n1 // n2) if n2 != 0 else None
    return None


def consultar_procuraduria(cedula, nombre, primer_nombre, output_dir, callback=None):
    """Consulta Procuraduría — Semi-automática.
    El formulario está dentro de un iframe (apps.procuraduria.gov.co/webcert/).
    Pre-llena tipo de identificación y número de cédula usando IDs exactos.
    Intenta resolver automáticamente preguntas de seguridad matemáticas.
    Si la pregunta no es matemática, pausa para que el usuario responda."""
    driver = _crear_driver()
    try:
        if callback:
            callback("Procuraduria: Abriendo pagina...")
        driver.get(URLS["procuraduria"])
        time.sleep(6)  # SharePoint necesita más tiempo para cargar

        # ---- PASO 1: Cambiar al iframe que contiene el formulario ----
        iframe_encontrado = False
        try:
            # Buscar el iframe por src parcial
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe")
            for iframe in iframes:
                src = (iframe.get_attribute("src") or "").lower()
                if "webcert" in src or "procuraduria" in src and "inicio" in src:
                    driver.switch_to.frame(iframe)
                    iframe_encontrado = True
                    break
            # Si no encontró por src, intentar con el primer iframe visible
            if not iframe_encontrado and iframes:
                for iframe in iframes:
                    try:
                        if iframe.is_displayed():
                            driver.switch_to.frame(iframe)
                            # Verificar que tiene el formulario
                            test = driver.find_elements(By.ID, "ddlTipoID")
                            if test:
                                iframe_encontrado = True
                                break
                            driver.switch_to.default_content()
                    except Exception:
                        driver.switch_to.default_content()
        except Exception:
            pass

        if not iframe_encontrado:
            if callback:
                callback("Procuraduria: ADVERTENCIA - No se encontró el iframe del formulario. Intentando en página principal...")

        time.sleep(1)

        # ---- PASO 2: Seleccionar Tipo de Identificación (id=ddlTipoID) ----
        tipo_llenado = False
        try:
            sel_elem = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ddlTipoID"))
            )
            sel = Select(sel_elem)
            # Seleccionar "Cédula de ciudadanía" (value=1)
            sel.select_by_value("1")
            tipo_llenado = True
            time.sleep(0.5)
        except Exception:
            pass

        # Fallback: buscar cualquier select visible
        if not tipo_llenado:
            try:
                selects = driver.find_elements(By.CSS_SELECTOR, "select")
                for sel_elem in selects:
                    if sel_elem.is_displayed():
                        sel = Select(sel_elem)
                        for opt in sel.options:
                            texto = opt.text.strip().lower()
                            if "dula" in texto and "ciudadan" in texto:
                                sel.select_by_visible_text(opt.text)
                                tipo_llenado = True
                                break
                        if tipo_llenado:
                            break
            except Exception:
                pass

        if callback:
            callback("Procuraduria: Tipo de ID seleccionado..." if tipo_llenado else "Procuraduria: No se pudo seleccionar tipo de ID")

        # ---- PASO 3: Ingresar Número de Identificación (id=txtNumID) ----
        doc_llenado = False
        try:
            campo_id = driver.find_element(By.ID, "txtNumID")
            campo_id.clear()
            campo_id.send_keys(str(cedula))
            doc_llenado = True
            time.sleep(0.5)
        except Exception:
            pass

        # Fallback: primer input[type=text] visible
        if not doc_llenado:
            try:
                campos = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for campo in campos:
                    if campo.is_displayed() and campo.get_attribute("id") != "txtRespuestaPregunta":
                        campo.clear()
                        campo.send_keys(str(cedula))
                        doc_llenado = True
                        break
            except Exception:
                pass

        if callback:
            callback("Procuraduria: Cedula ingresada..." if doc_llenado else "Procuraduria: No se pudo ingresar cedula")

        # ---- PASO 4: Asegurar radio "Ordinario" seleccionado (id=rblTipoCert_0) ----
        try:
            radio_ordinario = driver.find_element(By.ID, "rblTipoCert_0")
            if not radio_ordinario.is_selected():
                radio_ordinario.click()
        except Exception:
            pass

        # ---- PASO 5: Intentar resolver la pregunta de seguridad ----
        pregunta_resuelta = False
        try:
            # Buscar el texto de la pregunta cerca del campo de respuesta
            pregunta_texto = ""
            # Buscar labels, spans, divs con texto de pregunta
            elementos = driver.find_elements(By.CSS_SELECTOR, "span, label, div, td")
            for elem in elementos:
                try:
                    txt = elem.text.strip()
                    if "cuanto" in txt.lower() or "cuánto" in txt.lower() or "resultado" in txt.lower():
                        pregunta_texto = txt
                        break
                except Exception:
                    continue

            if not pregunta_texto:
                # Intentar obtener todo el texto visible del formulario
                body_text = driver.find_element(By.TAG_NAME, "body").text
                import re
                match = re.search(r'[¿?]\s*[Cc]u[aá]nto\s+es\s+\d+\s*[+\-*xX×÷/]\s*\d+\s*[?¿]?', body_text)
                if match:
                    pregunta_texto = match.group(0)

            if pregunta_texto:
                respuesta = _resolver_pregunta_matematica(pregunta_texto)
                if respuesta:
                    campo_respuesta = driver.find_element(By.ID, "txtRespuestaPregunta")
                    campo_respuesta.clear()
                    campo_respuesta.send_keys(respuesta)
                    pregunta_resuelta = True
                    if callback:
                        callback(f"Procuraduria: Pregunta resuelta automaticamente: {pregunta_texto} = {respuesta}")
        except Exception:
            pass

        if pregunta_resuelta:
            # ---- PASO 6A: Auto-click en Generar si resolvimos la pregunta ----
            time.sleep(1)
            try:
                btn_generar = driver.find_element(By.ID, "btnExportar")
                btn_generar.click()
                if callback:
                    callback("Procuraduria: Generando certificado automaticamente...")
            except Exception:
                if callback:
                    callback("Procuraduria: No se pudo hacer click en Generar. Hazlo manualmente...")
        else:
            # ---- PASO 6B: Esperar a que el usuario responda manualmente ----
            if callback:
                callback("Procuraduria: Responde la pregunta de seguridad y haz click en 'Generar' en Chrome...")

        # ---- PASO 7: Esperar que aparezca la página de resultado con "Descargar" ----
        _esperar_hasta_que_usuario_termine(
            driver, timeout=300,
            check_text=["DESCARGUE SU CERTIFICADO", "DESCARGAR",
                        "NO REGISTRA", "ANTECEDENTES DISCIPLINARIOS"]
        )

        time.sleep(2)

        # ---- PASO 8: Click en botón "Descargar" y monitorear descarga ----
        import shutil
        downloads_chrome = os.path.join(os.path.expanduser("~"), "Downloads")
        archivos_antes = set(os.listdir(downloads_chrome))

        # Buscar y hacer click en el botón "Descargar"
        try:
            # Buscar en el iframe actual
            btns = driver.find_elements(By.CSS_SELECTOR, "a, button, input[type='submit'], input[type='button'], input[type='image']")
            for btn in btns:
                txt = (btn.text or "").strip().lower()
                val = (btn.get_attribute("value") or "").lower()
                alt = (btn.get_attribute("alt") or "").lower()
                if "descargar" in txt or "descargar" in val or "descargar" in alt:
                    btn.click()
                    if callback:
                        callback("Procuraduria: Descargando certificado...")
                    break
        except Exception:
            if callback:
                callback("Procuraduria: No se encontro boton Descargar. Hazlo manualmente...")

        # Monitorear carpeta de descargas
        archivo_descargado = None
        for _ in range(120):
            time.sleep(1)
            archivos_ahora = set(os.listdir(downloads_chrome))
            nuevos = archivos_ahora - archivos_antes
            nuevos_completos = [
                f for f in nuevos
                if not f.endswith(".crdownload") and not f.endswith(".tmp")
                and f.lower().endswith(".pdf")
            ]
            if nuevos_completos:
                time.sleep(2)
                archivo_descargado = os.path.join(downloads_chrome, nuevos_completos[0])
                break

        if archivo_descargado and os.path.exists(archivo_descargado):
            fecha = datetime.now().strftime("%Y-%m-%d")
            archivo = f"Procuraduria_Antecedentes_{fecha}.pdf"
            ruta = os.path.join(output_dir, archivo)
            shutil.move(archivo_descargado, ruta)
            registrar_consulta(cedula, nombre, "procuraduria", archivo)
            if callback:
                callback(f"Procuraduria: PDF guardado -> {archivo}")
            return True, archivo
        else:
            # Fallback: capturar la página como PDF
            if callback:
                callback("Procuraduria: No se detecto descarga. Guardando pagina como PDF...")
            if iframe_encontrado:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
            fecha = datetime.now().strftime("%Y-%m-%d")
            archivo = f"Procuraduria_Antecedentes_{fecha}.pdf"
            ruta = os.path.join(output_dir, archivo)
            _print_to_pdf(driver, ruta)
            registrar_consulta(cedula, nombre, "procuraduria", archivo)
            if callback:
                callback(f"Procuraduria: PDF guardado (captura) -> {archivo}")
            return True, archivo

    except Exception as e:
        return False, str(e)
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# Función principal de consulta masiva
# ---------------------------------------------------------------------------
def consultar_todos(patrocinadores, fuentes=None, callback=None):
    """Consulta antecedentes para múltiples patrocinadores.

    Args:
        patrocinadores: lista de dicts con keys: nombre, cedula
        fuentes: lista de fuentes a consultar (default: todas)
        callback: función(mensaje, progreso) para reportar progreso

    Returns:
        dict con resultados por patrocinador
    """
    if fuentes is None:
        fuentes = ["policia", "ofac", "contraloria", "procuraduria"]

    resultados = {}
    total = len(patrocinadores) * len(fuentes)
    completados = 0

    for pat in patrocinadores:
        nombre = pat["nombre"]
        # Limpiar cédula: quitar puntos, comas, espacios, .0 del Excel
        import re as _re
        cedula = _re.sub(r'[^0-9]', '', str(pat["cedula"]).replace(".0", ""))
        primer_nombre_ofac, primer_apellido_ofac = _extraer_nombre_ofac(nombre)
        primer_nombre = nombre.strip().split()[0] if nombre.strip() else ""
        output_dir = _output_dir_para_patrocinador(nombre)

        resultados[cedula] = {"nombre": nombre, "resultados": {}}

        for fuente in fuentes:
            completados += 1
            progreso = completados / total
            if callback:
                callback(f"[{completados}/{total}] {nombre} - {fuente.title()}...", progreso)

            try:
                if fuente == "policia":
                    ok, info = consultar_policia(cedula, nombre, output_dir, callback)
                elif fuente == "ofac":
                    ok, info = consultar_ofac(
                        primer_nombre_ofac, primer_apellido_ofac,
                        cedula, nombre, output_dir, callback
                    )
                elif fuente == "contraloria":
                    ok, info = consultar_contraloria(cedula, nombre, output_dir, callback)
                elif fuente == "procuraduria":
                    ok, info = consultar_procuraduria(cedula, nombre, primer_nombre, output_dir, callback)
                else:
                    ok, info = False, f"Fuente desconocida: {fuente}"

                resultados[cedula]["resultados"][fuente] = {"exito": ok, "detalle": info}
            except Exception as e:
                resultados[cedula]["resultados"][fuente] = {"exito": False, "detalle": str(e)}

    return resultados
