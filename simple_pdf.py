# simple_pdf.py
# Generador de PDF mínimo, sin dependencias externas (solo librería estándar).
# Se creó para evitar problemas de librerías de terceros (reportlab, fpdf2/fontTools)
# que incluyen código compilado en C/Cython y fallan al compilarse para Android
# (arquitectura ARM) porque python-for-android termina empaquetando binarios
# pensados para PC (x86_64).
#
# Soporta lo mínimo que necesita la ficha: rectángulos, líneas, texto con las
# fuentes estándar Helvetica/Helvetica-Bold (siempre disponibles en cualquier
# lector de PDF, no hace falta incrustar la fuente), y fotos JPEG incrustadas
# tal cual (sin recomprimir) usando el filtro DCTDecode del propio PDF.

MM = 2.8346456692913385  # puntos PDF por milímetro (1 mm = 2.8346... pt)

# Anchuras de caracter (por 1000 unidades de fuente) para Helvetica normal y
# negrita — son las métricas estándar AFM de Adobe, iguales en cualquier
# lector de PDF que use las 14 fuentes base.
_HELV = {
    ' ':278,'!':278,'"':355,'#':556,'$':556,'%':889,'&':667,"'":191,'(':333,')':333,
    '*':389,'+':584,',':278,'-':333,'.':278,'/':278,
    '0':556,'1':556,'2':556,'3':556,'4':556,'5':556,'6':556,'7':556,'8':556,'9':556,
    ':':278,';':278,'<':584,'=':584,'>':584,'?':556,'@':1015,
    'A':667,'B':667,'C':722,'D':722,'E':667,'F':611,'G':778,'H':722,'I':278,'J':500,
    'K':667,'L':556,'M':833,'N':722,'O':778,'P':667,'Q':778,'R':722,'S':667,'T':611,
    'U':722,'V':667,'W':944,'X':667,'Y':667,'Z':611,
    '[':278,'\\':278,']':278,'^':469,'_':556,'`':333,
    'a':556,'b':556,'c':500,'d':556,'e':556,'f':278,'g':556,'h':556,'i':222,'j':222,
    'k':500,'l':222,'m':833,'n':556,'o':556,'p':556,'q':556,'r':333,'s':500,'t':278,
    'u':556,'v':500,'w':722,'x':500,'y':500,'z':500,
    '{':334,'|':260,'}':334,'~':584,
}
_HELV_BOLD = {
    ' ':278,'!':333,'"':474,'#':556,'$':556,'%':889,'&':722,"'":238,'(':333,')':333,
    '*':389,'+':584,',':278,'-':333,'.':278,'/':278,
    '0':556,'1':556,'2':556,'3':556,'4':556,'5':556,'6':556,'7':556,'8':556,'9':556,
    ':':333,';':333,'<':584,'=':584,'>':584,'?':611,'@':975,
    'A':722,'B':667,'C':722,'D':722,'E':667,'F':611,'G':778,'H':722,'I':278,'J':556,
    'K':722,'L':611,'M':833,'N':722,'O':778,'P':667,'Q':778,'R':722,'S':667,'T':611,
    'U':722,'V':667,'W':944,'X':667,'Y':667,'Z':611,
    '[':333,'\\':278,']':333,'^':584,'_':556,'`':333,
    'a':556,'b':611,'c':556,'d':611,'e':556,'f':333,'g':611,'h':611,'i':278,'j':278,
    'k':556,'l':278,'m':889,'n':611,'o':611,'p':611,'q':611,'r':389,'s':556,'t':333,
    'u':611,'v':556,'w':778,'x':556,'y':556,'z':500,
    '{':389,'|':280,'}':389,'~':584,
}
# Acentos/eñes en español: aproximamos con el ancho de la letra base (visualmente
# casi idéntico, suficiente para calcular saltos de línea).
_EQUIV = {
    'á':'a','é':'e','í':'i','ó':'o','ú':'u','à':'a','è':'e','ì':'i','ò':'o','ù':'u',
    'ñ':'n','ü':'u','Á':'A','É':'E','Í':'I','Ó':'O','Ú':'U','Ñ':'N','Ü':'U',
    '¿':'?','¡':'!','º':'o','ª':'a','ç':'c','Ç':'C',
}


def _ancho_char(ch, tabla):
    if ch in tabla:
        return tabla[ch]
    if ch in _EQUIV:
        return tabla.get(_EQUIV[ch], 556)
    return 556  # valor por defecto razonable para cualquier símbolo no listado


def texto_ancho_mm(texto, size_pt, bold=False):
    tabla = _HELV_BOLD if bold else _HELV
    unidades = sum(_ancho_char(c, tabla) for c in texto)
    return (unidades / 1000.0) * size_pt * (1 / MM)


def envolver_texto(texto, ancho_max_mm, size_pt, bold=False):
    """Word-wrap simple: devuelve una lista de líneas que caben en ancho_max_mm."""
    palabras = texto.split()
    lineas = []
    actual = ""
    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        if texto_ancho_mm(prueba, size_pt, bold) <= ancho_max_mm or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _escapar_pdf_bytes(texto):
    b = texto.encode("cp1252", errors="replace")
    out = bytearray()
    for byte in b:
        if byte in (0x28, 0x29, 0x5C):  # ( ) \
            out.append(0x5C)
        out.append(byte)
    return bytes(out)


def _jpeg_info(ruta):
    """Lee cabecera JPEG para obtener (ancho_px, alto_px, n_componentes) sin
    necesitar Pillow ni ninguna otra librería."""
    with open(ruta, "rb") as f:
        datos = f.read()
    if datos[0:2] != b"\xff\xd8":
        return None
    i = 2
    n = len(datos)
    while i < n - 1:
        if datos[i] != 0xFF:
            i += 1
            continue
        marcador = datos[i + 1]
        if marcador in (0xD8, 0x01) or (0xD0 <= marcador <= 0xD7):
            i += 2
            continue
        if marcador == 0xD9:  # EOI
            break
        if i + 3 >= n:
            break
        seg_len = (datos[i + 2] << 8) + datos[i + 3]
        if marcador in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            alto = (datos[i + 5] << 8) + datos[i + 6]
            ancho = (datos[i + 7] << 8) + datos[i + 8]
            ncomp = datos[i + 9]
            return ancho, alto, ncomp
        i += 2 + seg_len
    return None


class SimplePDF:
    def __init__(self, page_w_mm=210, page_h_mm=297):
        self.page_w_pt = page_w_mm * MM
        self.page_h_pt = page_h_mm * MM
        self.content = bytearray()
        self._imagenes = []  # lista de dicts: {jpeg_bytes, w_px, h_px, ncomp}

    # ---- primitivas de dibujo (coordenadas en mm, origen arriba-izquierda) ----
    def set_fill_rgb(self, r, g, b):
        self.content += f"{r/255:.3f} {g/255:.3f} {b/255:.3f} rg\n".encode()

    def set_stroke_rgb(self, r, g, b):
        self.content += f"{r/255:.3f} {g/255:.3f} {b/255:.3f} RG\n".encode()

    def rect(self, x_mm, y_mm, w_mm, h_mm, fill=False, stroke=True, line_w_pt=0.6):
        x = x_mm * MM
        y_top = self.page_h_pt - y_mm * MM
        y_bottom = y_top - h_mm * MM
        w = w_mm * MM
        h = h_mm * MM
        self.content += f"{line_w_pt} w\n{x:.2f} {y_bottom:.2f} {w:.2f} {h:.2f} re\n".encode()
        if fill and stroke:
            self.content += b"B\n"
        elif fill:
            self.content += b"f\n"
        elif stroke:
            self.content += b"S\n"

    def line(self, x1_mm, y1_mm, x2_mm, y2_mm, line_w_pt=0.6):
        x1, y1 = x1_mm * MM, self.page_h_pt - y1_mm * MM
        x2, y2 = x2_mm * MM, self.page_h_pt - y2_mm * MM
        self.content += f"{line_w_pt} w\n{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S\n".encode()

    def text(self, x_mm, y_top_mm, texto, size_pt=8, bold=False, color=(0, 0, 0), align="L", box_w_mm=None):
        """Dibuja una línea de texto. y_top_mm = borde superior de la línea."""
        if not texto:
            return
        r, g, b = color
        x = x_mm
        if align in ("C", "R") and box_w_mm:
            ancho_txt = texto_ancho_mm(texto, size_pt, bold)
            if align == "C":
                x = x_mm + max(0, (box_w_mm - ancho_txt) / 2)
            else:
                x = x_mm + max(0, box_w_mm - ancho_txt)
        x_pt = x * MM
        baseline_mm = y_top_mm + size_pt * 0.352778 * 0.82
        y_pt = self.page_h_pt - baseline_mm * MM
        fuente = "/F2" if bold else "/F1"
        cuerpo = _escapar_pdf_bytes(texto)
        self.content += f"{r/255:.3f} {g/255:.3f} {b/255:.3f} rg\nBT {fuente} {size_pt} Tf {x_pt:.2f} {y_pt:.2f} Td (".encode()
        self.content += cuerpo
        self.content += b") Tj ET\n"

    def texto_multilinea(self, x_mm, y_top_mm, texto, ancho_mm, size_pt=8, bold=False,
                          color=(0, 0, 0), interlineado=1.15, max_lineas=None):
        lineas = envolver_texto(texto, ancho_mm, size_pt, bold)
        if max_lineas:
            lineas = lineas[:max_lineas]
        paso_mm = size_pt * 0.352778 * interlineado
        for i, linea in enumerate(lineas):
            self.text(x_mm, y_top_mm + i * paso_mm, linea, size_pt=size_pt, bold=bold, color=color)
        return y_top_mm + len(lineas) * paso_mm

    def image(self, ruta, x_mm, y_mm, w_mm, h_mm):
        """Incrusta una foto JPEG tal cual (sin recomprimir), centrada y
        respetando el aspect ratio dentro de la caja x,y,w,h (mm, origen arriba-izq)."""
        info = _jpeg_info(ruta)
        if info is None:
            return False
        ancho_px, alto_px, ncomp = info
        if ancho_px == 0 or alto_px == 0:
            return False
        with open(ruta, "rb") as f:
            jpeg_bytes = f.read()

        aspecto_caja = w_mm / h_mm
        aspecto_img = ancho_px / alto_px
        if aspecto_img > aspecto_caja:
            draw_w = w_mm
            draw_h = w_mm / aspecto_img
        else:
            draw_h = h_mm
            draw_w = h_mm * aspecto_img
        off_x = x_mm + (w_mm - draw_w) / 2
        off_y = y_mm + (h_mm - draw_h) / 2

        idx = len(self._imagenes)
        self._imagenes.append({"jpeg": jpeg_bytes, "w_px": ancho_px, "h_px": alto_px, "ncomp": ncomp})
        nombre = f"/Im{idx}"

        x_pt = off_x * MM
        y_top_pt = self.page_h_pt - off_y * MM
        y_bottom_pt = y_top_pt - draw_h * MM
        w_pt = draw_w * MM
        h_pt = draw_h * MM
        self.content += (
            f"q {w_pt:.2f} 0 0 {h_pt:.2f} {x_pt:.2f} {y_bottom_pt:.2f} cm {nombre} Do Q\n"
        ).encode()
        return True

    # ---- generación del archivo final ----
    def output(self, ruta_salida):
        buf = bytearray()
        buf += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets = [0]

        def add_obj(cuerpo_bytes):
            offsets.append(len(buf))
            buf.extend(cuerpo_bytes)

        # 1 Catalog, 2 Pages, 3 Page, 4 Content, 5 Font Helvetica, 6 Font Helvetica-Bold
        add_obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        add_obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

        xobjects = "".join(
            f"/Im{i} {7 + i} 0 R " for i in range(len(self._imagenes))
        )
        recursos = (
            f"<< /Font << /F1 5 0 R /F2 6 0 R >> "
            f"/XObject << {xobjects}>> >>"
        )
        page_obj = (
            f"3 0 obj\n<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {self.page_w_pt:.2f} {self.page_h_pt:.2f}] "
            f"/Resources {recursos} /Contents 4 0 R >>\nendobj\n"
        ).encode()
        add_obj(page_obj)

        contenido = bytes(self.content)
        add_obj(
            f"4 0 obj\n<< /Length {len(contenido)} >>\nstream\n".encode()
            + contenido + b"\nendstream\nendobj\n"
        )
        add_obj(
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>\nendobj\n"
        )
        add_obj(
            b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            b"/Encoding /WinAnsiEncoding >>\nendobj\n"
        )

        for idx, img in enumerate(self._imagenes):
            colorspace = "DeviceGray" if img["ncomp"] == 1 else "DeviceRGB"
            cabecera = (
                f"/Type /XObject /Subtype /Image /Width {img['w_px']} /Height {img['h_px']} "
                f"/ColorSpace /{colorspace} /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(img['jpeg'])}"
            )
            add_obj(
                f"{7 + idx} 0 obj\n<< {cabecera} >>\nstream\n".encode()
                + img["jpeg"] + b"\nendstream\nendobj\n"
            )

        n_objs = len(offsets) - 1
        xref_offset = len(buf)
        buf += f"xref\n0 {n_objs + 1}\n".encode()
        buf += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            buf += f"{off:010d} 00000 n \n".encode()
        buf += (
            f"trailer\n<< /Size {n_objs + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode()

        with open(ruta_salida, "wb") as f:
            f.write(buf)
