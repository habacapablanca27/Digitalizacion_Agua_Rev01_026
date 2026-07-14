# generar_ficha_pdf.py
# Genera un PDF por punto, replicando el diseño de la ficha modelo
# (Ficha_Modelo_Valle_de_Valdebezana.xlsx): escudo + cabecera del
# ayuntamiento, logo SOMACyL, caja de "Situación", caja de "Contador",
# dos fotos (Inmueble/Arqueta) y bloque "A RELLENAR EN FASE DE OBRA".
#
# Usa simple_pdf.py (motor propio, sin dependencias externas) para evitar
# problemas de librerías de terceros con código compilado que no cross-compila
# bien para Android (nos pasó con reportlab y con fpdf2/fontTools).

import os
from simple_pdf import SimplePDF

AZUL = (68, 114, 196)
NEGRO = (0, 0, 0)
BLANCO = (255, 255, 255)
GRIS = (140, 140, 140)

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
ESCUDO = os.path.join(ASSETS, "escudo.png")
SOMACYL = os.path.join(ASSETS, "somacyl.png")

MARGEN = 12
ANCHO_PAG = 210
ALTO_PAG = 297
ANCHO = ANCHO_PAG - 2 * MARGEN


def _si_no(v):
    return "Sí" if v else "No"


def generar_ficha_pdf(punto, ruta_salida, municipio="", nucleo="", provincia=""):
    pdf = SimplePDF(page_w_mm=ANCHO_PAG, page_h_mm=ALTO_PAG)

    x0 = MARGEN
    y = MARGEN

    # ── CABECERA ──
    # Nota: el escudo y el logo SOMACyL están en PNG (no JPEG), y nuestro
    # motor de PDF solo incrusta JPEG directamente sin recomprimir. Como son
    # solo 2 imágenes fijas (no fotos de campo), las omitimos aquí y dejamos
    # el texto de cabecera, que es la parte que cambia con el municipio.
    alto_cab = 28
    pdf.rect(x0, y, ANCHO, alto_cab)
    pdf.text(x0 + 30, y + 4, f"AYUNTAMIENTO DE {municipio.upper()}", size_pt=12, bold=True)
    pdf.text(x0 + 30, y + 12, nucleo.upper(), size_pt=10)
    pdf.text(x0 + 30, y + 18, provincia.upper(), size_pt=10)
    y += alto_cab + 3

    # ── FILA Nº FIJO / DIRECCIÓN / TIPO EDIFICACIÓN ──
    fila_h = 14
    col1, col3 = 25, 45
    col2 = ANCHO - col1 - col3
    _celda(pdf, x0, y, col1, fila_h, "Nº FIJO", punto.get("NFijo", ""))
    _celda(pdf, x0 + col1, y, col2, fila_h, "DIRECCIÓN - Nº POLICÍA", punto.get("Direccion", ""))
    _celda(pdf, x0 + col1 + col2, y, col3, fila_h, "TIPO DE EDIFICACIÓN", punto.get("TipEdifica", ""))
    y += fila_h + 3

    # ── BLOQUE 1: Situación (foto) + columna de datos ──
    bloque1_h = 55
    foto_w = ANCHO * 0.42
    datos_w = ANCHO - foto_w
    _caja_foto(pdf, x0, y, foto_w, bloque1_h, "Situación", punto.get("FotoSituacion"))

    filas_dcha = [
        ("Exterior", _si_no(punto.get("Exterior"))),
        ("n° Módulo Radio", punto.get("ModRadio", "")),
        ("Válvula de acometida", _si_no(punto.get("ValAcometi"))),
        ("Tipo de uso consumo", punto.get("TipUsoComu", "")),
        ("Coordenadas GPS", punto.get("CoordGPS", "")),
        ("Código QR", ""),
        ("Individual", _si_no(punto.get("Individual"))),
        ("Alojamiento", punto.get("Alojamiento", "")),
    ]
    fh = bloque1_h / len(filas_dcha)
    for i, (etq, val) in enumerate(filas_dcha):
        _celda(pdf, x0 + foto_w, y + i * fh, datos_w, fh, etq, val)
    y += bloque1_h + 3

    # ── BLOQUE 2: Contador (foto) + Llave/Calibre/Diámetros, Lectura/Fecha, Marca/Observaciones ──
    bloque2_h = 42
    _caja_foto(pdf, x0, y, foto_w, bloque2_h, "Contador", punto.get("FotoContador"))

    dx = x0 + foto_w
    dw = datos_w
    fh2 = bloque2_h / 3
    w3 = dw / 3
    _celda(pdf, dx, y, w3, fh2, "Llave de contador", _si_no(punto.get("LlaveContador")))
    _celda(pdf, dx + w3, y, w3, fh2, "Calibre", punto.get("Calibre", ""))
    _celda(pdf, dx + 2 * w3, y, w3, fh2, "Diámetros", punto.get("Diametros", ""))
    _celda(pdf, dx, y + fh2, dw / 2, fh2, "Lectura", punto.get("Lectura", ""))
    _celda(pdf, dx + dw / 2, y + fh2, dw / 2, fh2, "Fecha", punto.get("FecLectura", ""))

    obs = punto.get("Observaciones", "") or ""
    extra = []
    if punto.get("UbicarExte"):
        extra.append("Ubicar exterior")
    if punto.get("CambioTapa"):
        extra.append("Cambio de tapa")
    if punto.get("SeBorra"):
        extra.append("Se borra")
    if extra:
        obs = (obs + "  |  " if obs else "") + ", ".join(extra)
    _celda(pdf, dx, y + 2 * fh2, dw / 2, fh2, "Marca/Modelo", punto.get("MarcaModel", ""))
    _celda(pdf, dx + dw / 2, y + 2 * fh2, dw / 2, fh2, "Observaciones", obs, wrap=True)
    y += bloque2_h + 3

    # ── BLOQUE 3: dos fotos (Inmueble / Arqueta) ──
    bloque3_h = 55
    mitad = ANCHO / 2
    _caja_foto(pdf, x0, y, mitad - 1.5, bloque3_h, "Inmueble", punto.get("FotoInmueble"))
    _caja_foto(pdf, x0 + mitad + 1.5, y, mitad - 1.5, bloque3_h, "Arqueta", punto.get("FotoArqueta"))
    y += bloque3_h + 4

    # ── BLOQUE FASE DE OBRA ──
    fo_h = 24
    pdf.text(x0, y, "A RELLENAR EN FASE DE OBRA", size_pt=8.5, bold=True, align="C", box_w_mm=ANCHO)
    pdf.rect(x0, y, ANCHO, fo_h)
    pdf.line(x0, y + 6, x0 + ANCHO, y + 6)
    colw = ANCHO / 4
    etiquetas_fo = ["Nº Serie contador existente / Fecha instalación",
                    "Lectura contador a sustituir", "Nº Serie contador sustitución", "Observaciones"]
    for i, et in enumerate(etiquetas_fo):
        cx = x0 + i * colw
        if i > 0:
            pdf.line(cx, y, cx, y + fo_h)
        pdf.texto_multilinea(cx + 1, y + 6.5, et, colw - 2, size_pt=6.5, bold=True)

    pdf.output(ruta_salida)


def _celda(pdf, x, y, w, h, titulo, valor, wrap=False):
    th = min(h * 0.5, 5.5)
    pdf.rect(x, y, w, th, fill=True, stroke=True)
    pdf.set_fill_rgb(*AZUL)
    pdf.rect(x, y, w, th, fill=True, stroke=True)
    tam_titulo = 7.5 if h < 8 else 8
    pdf.text(x, y + 1, titulo, size_pt=tam_titulo, bold=True, color=BLANCO, align="C", box_w_mm=w)

    pdf.set_fill_rgb(0, 0, 0)
    pdf.rect(x, y + th, w, h - th, fill=False, stroke=True)
    valor = str(valor) if valor is not None else ""
    if wrap:
        pdf.texto_multilinea(x + 1.5, y + th + 2.8, valor, w - 3, size_pt=8, max_lineas=3)
    else:
        pdf.text(x + 1.5, y + th + 2.8, valor[:60], size_pt=8)


def _caja_foto(pdf, x, y, w, h, etiqueta, ruta_foto):
    th = 6
    pdf.set_fill_rgb(*AZUL)
    pdf.rect(x, y, w, th, fill=True, stroke=True)
    pdf.text(x, y + 0.8, etiqueta, size_pt=8, bold=True, color=BLANCO, align="C", box_w_mm=w)
    pdf.rect(x, y + th, w, h - th, fill=False, stroke=True)

    incrustada = False
    if ruta_foto and os.path.exists(ruta_foto):
        try:
            incrustada = pdf.image(ruta_foto, x + 1, y + th + 1, w - 2, h - th - 2)
        except Exception:
            incrustada = False
    if not incrustada:
        pdf.text(x, y + th + (h - th) / 2 - 2, "Sin foto" if not ruta_foto else "(no se pudo cargar la foto)",
                  size_pt=7, color=GRIS, align="C", box_w_mm=w)


def generar_todas_las_fichas(puntos, carpeta_salida, municipio="", nucleo="", provincia=""):
    os.makedirs(carpeta_salida, exist_ok=True)
    rutas = []
    for p in puntos:
        nombre = f"Ficha_{p.get('NFijo') or p.get('_id')}.pdf".replace("/", "-")
        ruta = os.path.join(carpeta_salida, nombre)
        generar_ficha_pdf(p, ruta, municipio=municipio, nucleo=nucleo, provincia=provincia)
        rutas.append(ruta)
    return rutas
