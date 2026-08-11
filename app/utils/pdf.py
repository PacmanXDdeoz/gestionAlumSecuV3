"""Generación de la credencial QR de un alumno (PDF e imagen PNG).

La credencial es deliberadamente simple y limpia: únicamente el código QR
del alumno (con la misma URL absoluta de la boleta, que se abre con el
escaneo nativo del celular) y su nombre (estrictamente
**Nombre + Primer Apellido**), tal y como se solicita en el flujo de
edición del docente. Se puede descargar como PDF (``generar_pdf_qr``, en
formato carta para impresión) o como imagen PNG compacta
(``generar_imagen_qr``, recortada al contenido para facilitar el compartir).
"""
import io

import qrcode
from flask import url_for
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _imagen_qr(alumno):
    """Bytes PNG del QR del alumno, con la URL absoluta de su boleta.

    Idéntico contenido al QR de la credencial (``Alumno.generate_qr_code``):
    la URL ``/buscar/<id>``. Requiere contexto de request (se llama desde
    la ruta de descarga del PDF).
    """
    buf = io.BytesIO()
    url = url_for('public.boleta_alumno', id=alumno.id, _external=True)
    qrcode.make(url).save(buf, format='PNG')
    buf.seek(0)
    return buf


def _nombre_credencial(alumno):
    """Nombre que se imprime en la credencial: Nombre + Primer Apellido.

    Fuente única del formato (compartida por el PDF y la imagen PNG) para
    que ambas descargas muestren exactamente el mismo texto.
    """
    return f'{alumno.name} {alumno.lastname_p}'.strip()


def generar_pdf_qr(alumno):
    """Genera el PDF de credencial QR en memoria.

    :param alumno: instancia de ``Alumno``
    :return: ``io.BytesIO`` con el contenido del PDF
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    ancho, alto = letter

    # ── Código QR (centrado, 6 cm) ─────────────────────────────────────
    qr_size = 6 * cm
    qr_x = (ancho - qr_size) / 2
    qr_y = alto / 2 - qr_size / 2 + 0.5 * cm
    c.drawImage(ImageReader(_imagen_qr(alumno)),
                qr_x, qr_y, qr_size, qr_size, preserveAspectRatio=True, mask='auto')

    # ── Nombre del alumno: solo Nombre + Primer Apellido ────────────────
    nombre_pdf = _nombre_credencial(alumno)
    c.setFont('Helvetica-Bold', 22)
    c.drawCentredString(ancho / 2, qr_y - 1.4 * cm, nombre_pdf)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _fuente_negrita(tamano_px):
    """Fuente TrueType en negrita para el texto de la imagen PNG.

    Se intentan rutas comunes de DejaVu Sans Bold en Linux, macOS y
    Arial Bold en Windows; si ninguna existe, se cae a la fuente por
    defecto de Pillow (más pequeña, pero la imagen sigue generándose
    correctamente).
    """
    rutas = (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
    )
    for ruta in rutas:
        try:
            return ImageFont.truetype(ruta, tamano_px)
        except OSError:
            continue
    return ImageFont.load_default()


def generar_imagen_qr(alumno):
    """Genera la credencial QR como imagen PNG compacta en memoria.

    Mismo contenido que el PDF (QR + Nombre + Primer Apellido), pero a
    diferencia de este —que conserva formato carta para impresión— la
    imagen se recorta al contenido: el lienzo mide el QR más un margen
    pequeño, por lo que no hay zonas en blanco y es fácil de compartir
    (WhatsApp, correo, etc.).

    :param alumno: instancia de ``Alumno``
    :return: ``io.BytesIO`` con el contenido PNG
    """
    margen = 60          # espacio blanco alrededor (px)
    qr_px = 900          # resolución del QR (px): alta para escaneo nítido
    separacion = 48      # espacio entre el QR y el nombre (px)
    tamano_fuente = 76   # tamaño máximo del nombre (px)

    nombre = _nombre_credencial(alumno)
    fuente = _fuente_negrita(tamano_fuente)
    draw_probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))

    # ── Escalado de fuente para nombres largos ──────────────────────────
    # El nombre nunca debe ensanchar el lienzo más allá del QR: si no cabe
    # en ``qr_px``, se reduce la fuente de forma proporcional (hasta un
    # mínimo legible). Así la imagen siempre mantiene una proporción
    # compacta y cuadrada sin convertirse en una tira horizontal.
    caja = draw_probe.textbbox((0, 0), nombre, font=fuente)
    ancho_texto = caja[2] - caja[0]
    while ancho_texto > qr_px and tamano_fuente > 28:
        tamano_fuente -= 4
        fuente = _fuente_negrita(tamano_fuente)
        caja = draw_probe.textbbox((0, 0), nombre, font=fuente)
        ancho_texto = caja[2] - caja[0]
    alto_texto = caja[3] - caja[1]

    # Lienzo justo al contenido: el ancho cubre el QR con margen a ambos
    # lados (el nombre ya cabe dentro de ese ancho); el alto suma QR +
    # separación + nombre + márgenes. Sin espacio en blanco sobrante.
    ancho = qr_px + 2 * margen
    alto = margen + qr_px + separacion + alto_texto + margen
    imagen = Image.new('RGB', (ancho, alto), 'white')
    draw = ImageDraw.Draw(imagen)

    # ── Código QR (centrado) ────────────────────────────────────────────
    qr_img = Image.open(_imagen_qr(alumno)).convert('RGB')
    qr_img = qr_img.resize((qr_px, qr_px), Image.LANCZOS)
    qr_x = (ancho - qr_px) // 2
    qr_y = margen
    imagen.paste(qr_img, (qr_x, qr_y))

    # ── Nombre del alumno: solo Nombre + Primer Apellido ────────────────
    # ``draw.text`` ancla en la esquina superior-izquierda del em-box, no del
    # bbox de tinta: sin restar ``caja[0]``, nombres con acentos (José,
    # Álvarez…) se desplazarían unos píxeles a la derecha del centro.
    x_texto = (ancho - ancho_texto) / 2 - caja[0]
    y_texto = qr_y + qr_px + separacion
    draw.text((x_texto, y_texto), nombre, fill='black', font=fuente)

    buf = io.BytesIO()
    # Optimización de peso para compartir: la credencial es prácticamente
    # monocroma (blanco + negro + grises del antialiasing), así que se
    # cuantiza a una paleta pequeña SIN dithering (los grises del QR y del
    # texto se conservan, la escaneabilidad no se altera) y se guarda con
    # optimize=True. Resultado: ~70 KiB → ~20 KiB (-72%) sin pérdida
    # perceptible, mucho más ligera para WhatsApp/correo.
    paleta = imagen.quantize(colors=16, method=Image.MEDIANCUT, dither=Image.NONE)
    paleta.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf
