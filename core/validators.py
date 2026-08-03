"""Validadores reutilizables para uploads."""
from django.core.exceptions import ValidationError

# 5 MB: sobrado para una foto de perfil o un logo, y acota el abuso.
MAX_IMAGEN_BYTES = 5 * 1024 * 1024
MAX_IMAGEN_LADO = 4000  # px


def validar_imagen(archivo):
    """Limita peso y dimensiones de una imagen subida.

    Pillow ya garantiza que el archivo *es* una imagen (lo hace ImageField), pero
    nada acotaba el tamaño: un usuario logueado podía subir un archivo enorme.
    """
    if archivo is None:
        return

    size = getattr(archivo, 'size', None)
    if size and size > MAX_IMAGEN_BYTES:
        mb = MAX_IMAGEN_BYTES // (1024 * 1024)
        raise ValidationError(f"La imagen no puede pesar más de {mb} MB.")

    # `image` sólo existe mientras el archivo está en memoria/temporal al validar.
    imagen = getattr(archivo, 'image', None)
    if imagen is not None:
        ancho = getattr(imagen, 'width', 0) or 0
        alto = getattr(imagen, 'height', 0) or 0
        if ancho > MAX_IMAGEN_LADO or alto > MAX_IMAGEN_LADO:
            raise ValidationError(
                f"La imagen es demasiado grande ({ancho}×{alto}). "
                f"El máximo es {MAX_IMAGEN_LADO}×{MAX_IMAGEN_LADO} píxeles."
            )
