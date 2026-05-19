# Mi Nueva Familia - Sistema de Gestión de Patrocinadores

Sistema automatizado para la gestión de recibos de patrocinio y consulta de antecedentes de patrocinadores de Mi Nueva Familia.

## Características

- **Generación de recibos**: Analiza comprobantes de pago con IA (Google Gemini) y genera documentos Word/PDF automáticamente
- **Mejora de imagen**: Mejora la calidad de comprobantes borrosos (modo local o con IA de HuggingFace)
- **Consulta de antecedentes**: Automatización semi-automática de consultas en:
  - Policía Nacional (Antecedentes Judiciales)
  - OFAC (Lista Clinton / Sanciones Internacionales)
  - Contraloría General (Antecedentes Fiscales)
  - Procuraduría General (Antecedentes Disciplinarios)
- **Alertas de vigencia**: Notificaciones cuando los antecedentes están por vencer (cada 3 meses)

## Instalación Rápida (Windows)

### Requisitos
- Windows 10 o superior
- Google Chrome instalado (para la consulta de antecedentes)
- Conexión a internet

### Pasos

1. **Descarga** el proyecto completo desde GitHub:
   - Haz click en el botón verde **"Code"** → **"Download ZIP"**
   - Descomprime la carpeta en tu ubicación preferida

2. **Instala** haciendo doble click en:
   ```
   INSTALAR.bat
   ```
   Esto instalará Python (si no lo tienes) y todas las dependencias automáticamente.

3. **Ejecuta** haciendo doble click en:
   ```
   INICIAR.bat
   ```
   O usa el acceso directo "Mi Nueva Familia" que se creó en tu Escritorio.

## Versión Portable (Sin Instalación)

Si vas a compartir la aplicación con personas que no tienen conocimientos técnicos ni Python instalado, puedes generar y enviarles una versión portable:

### Para Generar el Paquete Portable (Tú, como desarrollador):
1. Ejecuta haciendo doble click en:
   ```
   CREAR_PORTABLE.bat
   ```
2. Esto descargará automáticamente Python Portable, instalará todas las dependencias y creará un archivo comprimido llamado **`MiNuevaFamilia-Portable.zip`** en la carpeta del proyecto.

### Para el Destinatario Final (Quien recibe la aplicación):
1. **Descarga y extrae** el archivo `MiNuevaFamilia-Portable.zip`.
2. Haz doble click en **`INICIAR.bat`** (dentro de la carpeta descomprimida). La aplicación abrirá automáticamente el navegador web y estará lista para usar. No es necesario instalar nada en el sistema.
3. **Configuración inicial**: En la parte superior de la aplicación web, expande la sección **⚙️ Configuración del Sistema**, selecciona la carpeta donde guardas tus patrocinadores locales usando el botón **📂 Buscar** y haz click en el botón verde **Guardar Configuración Local**.

## Configuración Inicial

Al abrir la aplicación por primera vez:

1. **Archivo Excel**: Usa el botón de configuración para seleccionar tu archivo Excel de patrocinadores
2. **Carpeta base**: Selecciona la carpeta donde están las subcarpetas de cada patrocinador
3. **Clave de Gemini AI**: Necesitas una clave de API de Google Gemini para el análisis de comprobantes. Obtén una gratis en [Google AI Studio](https://aistudio.google.com/apikey)

### Configuración Opcional

**Mejora con IA (HuggingFace)**:
Para usar la mejora de imagen con IA, edita el archivo `hf_config.json`:
```json
{
    "hf_token": "TU_TOKEN_DE_HUGGINGFACE"
}
```
Obtén tu token gratis en [HuggingFace Settings](https://huggingface.co/settings/tokens)

## Uso

### Generación de Recibos
1. Selecciona la zona/región
2. Selecciona el patrocinador
3. Sube la foto del comprobante de pago
4. (Opcional) Mejora la calidad de la imagen
5. Ingresa la clave de Gemini y haz click en "Analizar"
6. Verifica los datos extraídos
7. Genera y guarda el documento

### Consulta de Antecedentes
1. Selecciona los patrocinadores
2. Selecciona las fuentes a consultar
3. Haz click en "Consultar Antecedentes"
4. Se abrirá Chrome automáticamente para cada consulta
5. Resuelve los CAPTCHAs cuando se solicite
6. Los PDFs se guardan automáticamente

## Estructura de Archivos

```
proyecto mnf/
├── app.py                     # Aplicación principal (Streamlit)
├── antecedentes_checker.py    # Módulo de consulta de antecedentes
├── doc_generator.py           # Generador de documentos Word
├── gemini_extractor.py        # Extracción de datos con IA
├── image_upscaler.py          # Mejora de calidad de imagen
├── launcher.py                # Lanzador de la aplicación
├── INSTALAR.bat               # Instalador automático
├── INICIAR.bat                # Lanzador de la aplicación
├── build_portable.py          # Script de empaquetado portable
├── CREAR_PORTABLE.bat         # Creador del paquete ZIP portable
├── requirements.txt           # Dependencias Python
├── config.json                # Configuración local (no compartir)
├── hf_config.json             # Token de HuggingFace (no compartir)
└── hf_config.example.json     # Plantilla de configuración HF
```

## Solución de Problemas

- **"Python no está instalado"**: Descarga Python desde [python.org](https://www.python.org/downloads/) y marca "Add Python to PATH"
- **"No se puede conectar a Chrome"**: Asegúrate de tener Google Chrome instalado y actualizado
- **"Error de API de Gemini"**: Verifica que tu clave de API sea válida en [Google AI Studio](https://aistudio.google.com/)
- **Los antecedentes no se descargan**: Verifica tu conexión a internet y que los sitios gubernamentales estén disponibles

## Notas Importantes

- Los archivos `config.json`, `hf_config.json` y `antecedentes_log.json` contienen datos locales y NO deben compartirse
- Las consultas de antecedentes tienen vigencia de 3 meses
- El sistema genera alertas automáticas cuando los antecedentes están próximos a vencer
