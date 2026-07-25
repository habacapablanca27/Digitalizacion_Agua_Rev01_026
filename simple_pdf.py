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


import zlib


def _leer_png(ruta):
    """Decodifica un PNG (8 bits por canal, no entrelazado) usando solo
    'zlib' de la librería estándar. Necesario porque las capturas de
    pantalla de Android son PNG, y el resto del motor solo sabía incrustar
    JPEG. Devuelve un dict con los bytes de color (y de transparencia si
    los hay) listos para volver a comprimir con zlib para el PDF, o None
    si el PNG no se puede procesar (bit depth raro, entrelazado, etc. —
    en ese caso, quien llame debe mostrar el aviso de "no se pudo cargar").
    """
    with open(ruta, "rb") as f:
        datos = f.read()
    if datos[:8] != b"\x89PNG\r\n\x1a\n":
        return None

    ihdr = None
    paleta = None
    idat = bytearray()
    i = 8
    n = len(datos)
    while i + 8 <= n:
        long_chunk = int.from_bytes(datos[i:i + 4], "big")
        tipo = datos[i + 4:i + 8]
        cuerpo = datos[i + 8:i + 8 + long_chunk]
        if tipo == b"IHDR":
            ancho = int.from_bytes(cuerpo[0:4], "big")
            alto = int.from_bytes(cuerpo[4:8], "big")
            bit_depth = cuerpo[8]
            color_type = cuerpo[9]
            interlace = cuerpo[12]
            ihdr = (ancho, alto, bit_depth, color_type, interlace)
        elif tipo == b"PLTE":
            paleta = cuerpo
        elif tipo == b"IDAT":
            idat.extend(cuerpo)
        elif tipo == b"IEND":
            break
        i += 8 + long_chunk + 4  # + CRC

    if ihdr is None:
        return None
    ancho, alto, bit_depth, color_type, interlace = ihdr
    if bit_depth != 8 or interlace != 0:
        return None  # caso raro; se deja como "no se pudo cargar"
    canales_map = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in canales_map:
        return None
    canales = canales_map[color_type]

    try:
        crudo = zlib.decompress(bytes(idat))
    except Exception:
        return None

    stride = ancho * canales
    bpp = canales
    pixeles = bytearray(stride * alto)
    prev = bytearray(stride)
    pos = 0
    for fila in range(alto):
        if pos >= len(crudo):
            return None
        tipo_filtro = crudo[pos]
        pos += 1
        linea = bytearray(crudo[pos:pos + stride])
        pos += stride
        if tipo_filtro == 1:  # Sub
            for x in range(stride):
                a = linea[x - bpp] if x >= bpp else 0
                linea[x] = (linea[x] + a) & 0xFF
        elif tipo_filtro == 2:  # Up
            for x in range(stride):
                linea[x] = (linea[x] + prev[x]) & 0xFF
        elif tipo_filtro == 3:  # Average
            for x in range(stride):
                a = linea[x - bpp] if x >= bpp else 0
                linea[x] = (linea[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif tipo_filtro == 4:  # Paeth
            for x in range(stride):
                a = linea[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                linea[x] = (linea[x] + pred) & 0xFF
        pixeles[fila * stride:(fila + 1) * stride] = linea
        prev = linea

    if color_type == 3:  # paleta -> RGB
        if not paleta:
            return None
        rgb = bytearray(ancho * alto * 3)
        for idx in range(ancho * alto):
            p = pixeles[idx] * 3
            rgb[idx * 3:idx * 3 + 3] = paleta[p:p + 3]
        return {"w": ancho, "h": alto, "ncomp": 3, "color": bytes(rgb), "alpha": None}

    if color_type == 0:  # gris
        return {"w": ancho, "h": alto, "ncomp": 1, "color": bytes(pixeles), "alpha": None}

    if color_type == 2:  # RGB
        return {"w": ancho, "h": alto, "ncomp": 3, "color": bytes(pixeles), "alpha": None}

    if color_type in (4, 6):  # con canal alfa: separar color y transparencia
        canales_color = canales - 1
        color = bytearray(ancho * alto * canales_color)
        alpha = bytearray(ancho * alto)
        for idx in range(ancho * alto):
            base = idx * canales
            color[idx * canales_color:(idx + 1) * canales_color] = pixeles[base:base + canales_color]
            alpha[idx] = pixeles[base + canales_color]
        return {"w": ancho, "h": alto, "ncomp": canales_color, "color": bytes(color), "alpha": bytes(alpha)}

    return None


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
        self._paginas = []  # lista de dicts: {content: bytearray, imagenes: [...]}
        self._nueva_pagina_interna()

    def _nueva_pagina_interna(self):
        pagina = {"content": bytearray(), "imagenes": []}
        self._paginas.append(pagina)
        self.content = pagina["content"]
        self._imagenes = pagina["imagenes"]

    def nueva_pagina(self):
        """Cierra la página actual y empieza una nueva en blanco dentro del
        mismo documento (para poder juntar varias fichas en un solo PDF)."""
        self._nueva_pagina_interna()

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
        """Incrusta una foto (JPEG o PNG) centrada y respetando el aspect
        ratio dentro de la caja x,y,w,h (mm, origen arriba-izq). El JPEG se
        incrusta tal cual (sin recomprimir); el PNG se decodifica y se
        vuelve a comprimir con zlib (ver _leer_png)."""
        with open(ruta, "rb") as f:
            cabecera = f.read(8)

        es_png = cabecera == b"\x89PNG\r\n\x1a\n"
        if es_png:
            info_png = _leer_png(ruta)
            if info_png is None:
                return False
            ancho_px, alto_px = info_png["w"], info_png["h"]
        else:
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
        if es_png:
            self._imagenes.append({
                "png": True, "w_px": ancho_px, "h_px": alto_px,
                "ncomp": info_png["ncomp"], "color": info_png["color"], "alpha": info_png["alpha"],
            })
        else:
            self._imagenes.append({"png": False, "jpeg": jpeg_bytes, "w_px": ancho_px,
                                    "h_px": alto_px, "ncomp": ncomp})
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

        n_paginas = len(self._paginas)

        # Plan de numeración de objetos (antes de escribir nada), porque los
        # objetos "Pages" y "Page" necesitan referenciar objetos que se
        # escriben más adelante en el archivo:
        #   1 Catalog, 2 Pages
        #   por cada página: 1 objeto Page + 1 objeto Content + N imágenes
        #     (una imagen PNG con transparencia ocupa 2 objetos: color + máscara alfa)
        #   al final: 2 objetos de fuente (compartidos por todas las páginas)
        pagina_obj = []
        content_obj = []
        imagenes_obj = []  # lista de listas [(obj_color, obj_alpha_o_None), ...] por página
        siguiente = 3
        for pagina in self._paginas:
            pagina_obj.append(siguiente)
            content_obj.append(siguiente + 1)
            siguiente += 2
            objs_pagina = []
            for img in pagina["imagenes"]:
                tiene_alpha = img.get("png") and img.get("alpha") is not None
                if tiene_alpha:
                    objs_pagina.append((siguiente, siguiente + 1))
                    siguiente += 2
                else:
                    objs_pagina.append((siguiente, None))
                    siguiente += 1
            imagenes_obj.append(objs_pagina)
        font1_obj = siguiente
        font2_obj = siguiente + 1

        add_obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        kids = " ".join(f"{n} 0 R" for n in pagina_obj)
        add_obj(
            f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {n_paginas} >>\nendobj\n".encode()
        )

        for i, pagina in enumerate(self._paginas):
            xobjects = "".join(
                f"/Im{j} {imagenes_obj[i][j][0]} 0 R " for j in range(len(pagina["imagenes"]))
            )
            recursos = (
                f"<< /Font << /F1 {font1_obj} 0 R /F2 {font2_obj} 0 R >> "
                f"/XObject << {xobjects}>> >>"
            )
            page_bytes = (
                f"{pagina_obj[i]} 0 obj\n<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {self.page_w_pt:.2f} {self.page_h_pt:.2f}] "
                f"/Resources {recursos} /Contents {content_obj[i]} 0 R >>\nendobj\n"
            ).encode()
            add_obj(page_bytes)

            contenido = bytes(pagina["content"])
            add_obj(
                f"{content_obj[i]} 0 obj\n<< /Length {len(contenido)} >>\nstream\n".encode()
                + contenido + b"\nendstream\nendobj\n"
            )

            for j, img in enumerate(pagina["imagenes"]):
                obj_color, obj_alpha = imagenes_obj[i][j]
                colorspace = "DeviceGray" if img["ncomp"] == 1 else "DeviceRGB"

                if img.get("png"):
                    datos_color = zlib.compress(img["color"])
                    smask_ref = f" /SMask {obj_alpha} 0 R" if obj_alpha else ""
                    cabecera = (
                        f"/Type /XObject /Subtype /Image /Width {img['w_px']} /Height {img['h_px']} "
                        f"/ColorSpace /{colorspace} /BitsPerComponent 8 /Filter /FlateDecode"
                        f"{smask_ref} /Length {len(datos_color)}"
                    )
                    add_obj(
                        f"{obj_color} 0 obj\n<< {cabecera} >>\nstream\n".encode()
                        + datos_color + b"\nendstream\nendobj\n"
                    )
                    if obj_alpha:
                        datos_alpha = zlib.compress(img["alpha"])
                        cab_alpha = (
                            f"/Type /XObject /Subtype /Image /Width {img['w_px']} /Height {img['h_px']} "
                            f"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode "
                            f"/Length {len(datos_alpha)}"
                        )
                        add_obj(
                            f"{obj_alpha} 0 obj\n<< {cab_alpha} >>\nstream\n".encode()
                            + datos_alpha + b"\nendstream\nendobj\n"
                        )
                else:
                    cabecera = (
                        f"/Type /XObject /Subtype /Image /Width {img['w_px']} /Height {img['h_px']} "
                        f"/ColorSpace /{colorspace} /BitsPerComponent 8 /Filter /DCTDecode "
                        f"/Length {len(img['jpeg'])}"
                    )
                    add_obj(
                        f"{obj_color} 0 obj\n<< {cabecera} >>\nstream\n".encode()
                        + img["jpeg"] + b"\nendstream\nendobj\n"
                    )

        add_obj(
            f"{font1_obj} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            f"/Encoding /WinAnsiEncoding >>\nendobj\n".encode()
        )
        add_obj(
            f"{font2_obj} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            f"/Encoding /WinAnsiEncoding >>\nendobj\n".encode()
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
