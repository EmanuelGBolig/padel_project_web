"""Generación de la "placa" de campeones para compartir (TP-01b).

Estrategia: usar overlays de texto de Cloudinary SOBRE la foto de campeones que
sube el organizador (que ya vive en Cloudinary en producción). Así no hace falta
subir una plantilla aparte.

Diseño defensivo: si Cloudinary no está activo (p. ej. en local), si el torneo no
está finalizado, o si falta la foto/el ganador, devolvemos None. Los llamadores
caen al fallback (la foto tal cual o la imagen OG por defecto), de modo que nunca
se rompe ni se sirve una imagen inválida.
"""

from django.conf import settings


def cloudinary_activo():
    """True si el storage de media por defecto es Cloudinary."""
    backend = settings.STORAGES.get("default", {}).get("BACKEND", "")
    return "cloudinary" in backend.lower()


def build_placa_url(public_id, torneo_nombre, campeon_nombre):
    """Construye la URL de Cloudinary con overlays de texto sobre `public_id`.

    Devuelve la URL (str). Puede lanzar excepción si Cloudinary no está disponible;
    el llamador (placa_campeones_url) la captura y cae al fallback.
    """
    import cloudinary.utils

    transformation = [
        # Canvas cuadrado 1080x1080 (ideal para feed/stories) + oscurecido para legibilidad.
        {"width": 1080, "height": 1080, "crop": "fill", "gravity": "center"},
        {"effect": "brightness:-35"},
        # "CAMPEONES" arriba, en verde de marca.
        {"overlay": {"font_family": "Arial", "font_size": 70, "font_weight": "bold",
                     "text": "CAMPEONES"},
         "color": "#10b981", "gravity": "north", "y": 90},
        # Nombre de la pareja campeona, centrado.
        {"overlay": {"font_family": "Arial", "font_size": 90, "font_weight": "bold",
                     "text": campeon_nombre},
         "color": "white", "gravity": "center", "y": 40},
        # Nombre del torneo, abajo.
        {"overlay": {"font_family": "Arial", "font_size": 48,
                     "text": torneo_nombre},
         "color": "white", "gravity": "south", "y": 110},
        # Marca.
        {"overlay": {"font_family": "Arial", "font_size": 38, "font_weight": "bold",
                     "text": "TodoPadel"},
         "color": "#10b981", "gravity": "south", "y": 50},
    ]
    url, _ = cloudinary.utils.cloudinary_url(public_id, transformation=transformation, secure=True)
    return url


def placa_campeones_url(torneo):
    """URL de la placa de campeones del torneo, o None si no se puede generar.

    Requiere: torneo finalizado, con ganador y foto de campeones, y Cloudinary activo.
    """
    if torneo.estado != "FN":  # Torneo.Estado.FINALIZADO
        return None
    if not torneo.foto_campeones or not torneo.ganador_del_torneo:
        return None
    if not cloudinary_activo():
        return None
    try:
        public_id = torneo.foto_campeones.name
        return build_placa_url(public_id, torneo.nombre, torneo.ganador_del_torneo.nombre)
    except Exception:
        return None
