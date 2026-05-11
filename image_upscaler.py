"""
image_upscaler.py
-----------------
Mejora la calidad de imágenes borrosas.

Dos modos disponibles:
1. LOCAL (Pillow): Rápido, offline, usa algoritmos matemáticos.
2. IA (HuggingFace): Usa el modelo Flux.1-dev-Controlnet-Upscaler para
   resultados superiores. Requiere internet y token de HuggingFace.
"""

import os
from PIL import Image, ImageEnhance

# Token de HuggingFace — se lee de variable de entorno o hf_config.json
# NUNCA hardcodear tokens en código fuente público.
HF_TOKEN = None

def _get_hf_token():
    """Obtiene el token de HuggingFace de forma segura."""
    global HF_TOKEN
    if HF_TOKEN:
        return HF_TOKEN
    # 1. Variable de entorno
    import os as _os
    token = _os.environ.get("HF_TOKEN") or _os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        HF_TOKEN = token
        return token
    # 2. Archivo de configuración local (no se sube a git)
    import json
    config_path = _os.path.join(_os.path.dirname(__file__), "hf_config.json")
    if _os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                token = data.get("hf_token", "")
                if token:
                    HF_TOKEN = token
                    return token
        except Exception:
            pass
    return None


def upscale_image(
    input_path: str,
    output_path: str,
    upscale_factor: int = 2,
    use_ai: bool = False,
    **kwargs,
) -> str:
    """
    Mejora la resolución, nitidez y contraste de una imagen.
    
    Args:
        input_path: Ruta de la imagen original.
        output_path: Ruta donde guardar la imagen mejorada.
        upscale_factor: Factor de aumento (2, 4, 8).
        use_ai: Si True, usa el modelo de HuggingFace (mejor calidad, más lento).
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"No se encontró la imagen: {input_path}")

    if use_ai:
        return _upscale_ai(input_path, output_path, upscale_factor)
    else:
        return _upscale_local(input_path, output_path, upscale_factor)


def _upscale_local(input_path: str, output_path: str, upscale_factor: int = 2) -> str:
    """Mejora local con Pillow (rápido, offline)."""
    try:
        img = Image.open(input_path)
        
        # 1. Aumento de resolución con LANCZOS
        factor = int(upscale_factor)
        new_size = (int(img.width * factor), int(img.height * factor))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 2. Mejora de nitidez
        enhancer_sharpness = ImageEnhance.Sharpness(img)
        img = enhancer_sharpness.enhance(2.0)
        
        # 3. Mejora de contraste
        enhancer_contrast = ImageEnhance.Contrast(img)
        img = enhancer_contrast.enhance(1.3)
        
        img.save(output_path, quality=95)
        
    except Exception as e:
        raise RuntimeError(f"Error procesando la imagen localmente. Detalle: {e}")

    return output_path


def _upscale_ai(input_path: str, output_path: str, upscale_factor: int = 2) -> str:
    """Mejora con IA usando HuggingFace Flux.1-dev-Controlnet-Upscaler."""
    try:
        from gradio_client import Client, handle_file
    except ImportError:
        raise RuntimeError(
            "Se requiere 'gradio_client' para la mejora con IA. "
            "Instálalo con: pip install gradio_client"
        )

    try:
        token = _get_hf_token()
        if not token:
            raise RuntimeError(
                "No se encontró token de HuggingFace. "
                "Configúralo en hf_config.json o como variable de entorno HF_TOKEN."
            )
        client = Client(
            "jasperai/Flux.1-dev-Controlnet-Upscaler",
            hf_token=token,
        )

        result = client.predict(
            input_image=handle_file(input_path),
            prompt="high quality, sharp, detailed receipt document, clear text and numbers",
            negative_prompt="blurry, low quality, distorted",
            upscale_factor=upscale_factor,
            controlnet_conditioning_scale=0.6,
            seed=42,
            num_inference_steps=20,
            api_name="/predict",
        )

        # El resultado es la ruta al archivo generado
        if isinstance(result, str) and os.path.exists(result):
            # Copiar al output_path
            import shutil
            shutil.copy2(result, output_path)
        elif isinstance(result, (list, tuple)) and len(result) > 0:
            result_path = result[0] if isinstance(result[0], str) else str(result[0])
            if os.path.exists(result_path):
                import shutil
                shutil.copy2(result_path, output_path)
            else:
                raise RuntimeError(f"Resultado inesperado del modelo: {result}")
        else:
            raise RuntimeError(f"Resultado inesperado del modelo: {result}")

    except Exception as e:
        raise RuntimeError(f"Error con el modelo de IA de HuggingFace: {e}")

    return output_path


def check_upscaler_available() -> bool:
    """Verifica si la mejora de imagen está disponible. 
    Al ser 100% local con Pillow, siempre devuelve True."""
    return True
