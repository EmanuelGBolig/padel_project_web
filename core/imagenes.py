"""Preparar las imágenes que sube el usuario antes de validarlas y guardarlas."""
from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile

from core.validators import MAX_IMAGEN_BYTES, MAX_IMAGEN_LADO

# 2000 px de lado mayor: un comprobante de transferencia se lee perfecto y
# entra holgado abajo de MAX_IMAGEN_BYTES.
LADO_MAXIMO = 2000
# Escalera de calidad: si con 85 todavía no entra (una foto con mucho grano),
# se baja antes de rendirse.
CALIDADES = (85, 70, 55, 40)


def comprimir_para_subida(archivo, lado_maximo=LADO_MAXIMO):
    """Devuelve la imagen achicada a JPEG si no pasaría `validar_imagen`.

    La cámara de un celular moderno escupe archivos de 6 a 15 MB: pasan los
    5 MB de `MAX_IMAGEN_BYTES` siempre. Rechazarlos deja al jugador sin poder
    mandar el comprobante, así que en vez de eso se achica acá.

    Sólo se toca lo que de otro modo REBOTARÍA: pesa más de `MAX_IMAGEN_BYTES`
    o supera los `MAX_IMAGEN_LADO` px que el modelo declara como tope. Todo lo
    demás se devuelve ORIGINAL, sin recomprimir: la captura de pantalla del
    homebanking es un PNG sin pérdida de texto chico, y pasarla a JPEG para
    nada sería emborronar justo el CBU y el monto que el organizador necesita
    leer. Si algo falla al abrirla o al re-guardarla, también se devuelve el
    original: el que corta sigue siendo `validar_imagen`, no esta función.
    """
    from PIL import Image, ImageOps

    if archivo is None or not hasattr(archivo, 'read'):
        return archivo

    pesa_de_mas = (getattr(archivo, 'size', 0) or 0) > MAX_IMAGEN_BYTES
    try:
        archivo.seek(0)
        # `ImageField.to_python` ya llamó a `verify()`, que deja el objeto
        # inservible: hay que volver a abrir el archivo.
        imagen = Image.open(archivo)
        if not pesa_de_mas and max(imagen.size) <= MAX_IMAGEN_LADO:
            archivo.seek(0)
            return archivo
        # Las fotos traen la rotación en el EXIF, y al re-guardar el EXIF se
        # pierde: hay que aplicarla a los píxeles o el comprobante sale acostado.
        imagen = ImageOps.exif_transpose(imagen)
        imagen.thumbnail((lado_maximo, lado_maximo), Image.LANCZOS)
        if imagen.mode != 'RGB':
            # PNG con transparencia o con paleta: JPEG no los soporta.
            imagen = imagen.convert('RGB')
        for calidad in CALIDADES:
            buffer = BytesIO()
            imagen.save(buffer, format='JPEG', quality=calidad, optimize=True)
            if buffer.tell() <= MAX_IMAGEN_BYTES:
                break
    except Exception:
        try:
            archivo.seek(0)
        except Exception:
            pass
        return archivo

    # El nombre tiene que terminar en .jpg: lo que guardamos ES un JPEG, y el
    # storage (Cloudinary en producción) sirve el content-type por extensión.
    nombre = (getattr(archivo, 'name', None) or 'comprobante').rsplit('/', 1)[-1]
    nombre = (nombre.rsplit('.', 1)[0] or 'comprobante')[:80] + '.jpg'
    buffer.seek(0)
    return InMemoryUploadedFile(
        buffer, getattr(archivo, 'field_name', None), nombre,
        'image/jpeg', buffer.getbuffer().nbytes, None,
    )
