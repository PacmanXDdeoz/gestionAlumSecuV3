"""Generación de imágenes QR (códigos QR de los alumnos)."""
from pathlib import Path

import qrcode
from PIL import Image


def qr_codes_folder():
    """Carpeta donde se guardan los QRs de los alumnos (Path absoluto).

    Fuente única de la resolución de carpeta, compartida por
    ``Alumno.generate_qr_code`` y el comando ``flask regenerate-qrs``:

    - Si la config define ``QR_CODES_FOLDER`` (p. ej. el entorno de testing
      lo redirige a un directorio temporal fuera del proyecto), se usa esa
      ruta.
    - Si no, la carpeta estándar ``<static>/qrcodes`` del proyecto.
    """
    from flask import current_app

    configurada = current_app.config.get('QR_CODES_FOLDER')
    if configurada:
        return Path(configurada)
    return Path(current_app.static_folder) / 'qrcodes'


def generar_qr(texto, directorio, nombre_archivo):
    """Genera una imagen QR y la guarda en ``directorio/nombre_archivo``.

    :param texto: contenido a codificar en el QR
    :param directorio: carpeta destino (p. ej. ``<static>/qrcodes``)
    :param nombre_archivo: nombre del archivo (p. ej. ``alumno_1.png``)
    :return: ruta relativa a la carpeta estática (p. ej. ``qrcodes/alumno_1.png``)
    """
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / nombre_archivo
    imagen = qrcode.make(texto)

    # Optimización de peso para servir/compartir: ``qrcode.make`` ya devuelve
    # la imagen en modo '1' (binario puro, sin antialiasing), que es el más
    # ligero posible. Por defensa, si en el futuro una factory devolviera
    # RGB (grises de antialiasing), se cuantiza a una paleta de 2 colores
    # SIN dithering (el QR sigue siendo perfectamente escaneable) y siempre
    # se guarda con ``optimize=True``.
    if imagen.mode not in ('1', 'P'):
        imagen = imagen.convert('L').quantize(
            colors=2, method=Image.MEDIANCUT, dither=Image.NONE
        )
    imagen.save(ruta, format='PNG', optimize=True)
    return f'{directorio.name}/{nombre_archivo}'


def regenerar_todos_qrs():
    """Regenera el QR de todos los alumnos y elimina los PNGs huérfanos.

    Lógica compartida del comando ``flask regenerate-qrs`` y de la acción
    ``admin.regenerar_qrs`` del panel: reescribe los PNGs con la URL actual
    (``PUBLIC_BASE_URL`` o, dentro de un request, el host de la petición) y
    barre la carpeta de QRs eliminando archivos de alumnos ya borrados.

    :return: ``{'alumnos': n, 'huerfanos': m}`` con los conteos.
    """
    import re

    from app.models import Alumno

    alumnos = Alumno.query.all()
    for a in alumnos:
        a.generate_qr_code()

    ids_existentes = {a.id for a in alumnos}
    carpeta = qr_codes_folder()
    huerfanos = 0
    if carpeta.is_dir():
        patron = re.compile(r'^alumno_(\d+)\.png$')
        for archivo in carpeta.glob('alumno_*.png'):
            m = patron.match(archivo.name)
            if m and int(m.group(1)) not in ids_existentes:
                archivo.unlink()
                huerfanos += 1
    return {'alumnos': len(alumnos), 'huerfanos': huerfanos}
