import google.generativeai as genai
import json

def extract_receipt_data(api_key: str, image_path: str):
    """
    Usa Gemini para extraer los datos de un comprobante de pago.
    """
    clean_key = api_key.strip().replace('\n', '').replace('\r', '')
    genai.configure(api_key=clean_key, transport='rest')
    
    # Buscamos un modelo que soporte contenido multimodal
    model_name = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # Preferimos los modelos flash más modernos disponibles (ej. 2.5, 3.1)
            if 'flash' in m.name and 'preview' not in m.name:
                model_name = m.name
                break
    
    if not model_name:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name
                break
                
    if not model_name:
        model_name = 'models/gemini-2.5-flash' # Fallback moderno
        
    model = genai.GenerativeModel(model_name)
    
    from PIL import Image
    try:
        img = Image.open(image_path)
    except Exception as e:
        raise ValueError(f"No se pudo abrir la imagen: {e}")
    
    prompt = """
    Extrae la siguiente información del comprobante de transferencia bancaria adjunto.
    Devuelve la respuesta ÚNICAMENTE como un objeto JSON válido con las siguientes claves:
    
    - "valor_consignacion": El valor transferido (Ej: "$200.000").
    - "fecha_consignacion": La fecha en la que se realizó la transferencia (Formato DD/MM/AAAA, Ej: "24/03/2026").
    - "numero_comprobante": El número de comprobante o referencia. REGLAS IMPORTANTES:
         1. Si es consignación de REDEBAN (Bancolombia), el número de comprobante es el que aparece junto a "APRO:".
         2. Si es transferencia de NEQUI, el número de comprobante corresponde al dato de "Referencia".
         3. Para otros bancos, toma el número de comprobante/transacción normal.
    - "mes_aporte": El mes al que pertenece el aporte, inferido por la fecha del comprobante o su concepto (Ej: "MARZO"). Si no está claro en ningún texto, devuélvelo en base a la fecha.
    
    Recuerda: SOLO devuelve un string JSON, sin bloques de código ni texto adicional.
    """
    
    response = model.generate_content([prompt, img])
    
    try:
        # Limpiar posible formataje markdown de la respuesta de Gemini (ej. ```json ... ```)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Error procesando la respuesta. Respuesta cruda:\n{response.text}")
        raise ValueError("Gemini no devolvió un JSON válido")
