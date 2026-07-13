# generar_ficha_pdf.py
# Genera un PDF por punto, replicando el diseño de la ficha modelo
# (Ficha_Modelo_Valle_de_Valdebezana.xlsx): escudo + cabecera del
# ayuntamiento, logo SOMACyL, caja de "Situación", caja de "Contador",
# dos fotos (Inmueble/Arqueta) y bloque "A RELLENAR EN FASE DE OBRA".
#
# Usa fpdf2 (paquete "fpdf2", import "fpdf") en vez de reportlab: es
# puro Python, sin extensiones en C, así que compila sin problemas
# dentro de python-for-android/buildozer.

import os
from fpdf import FPDF

AZUL = (68, 114, 196)      # RGB equivalente a HexColor("#4472C4")
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
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_margin(0)

    x0 = MARGEN
    y = MARGEN

    # ── CABECERA ──
    alto_cab = 28
    pdf.rect(x0, y, ANCHO, alto_cab)
    if os.path.exists(ESCUDO):
        pdf.image(ESCUDO, x0 + 2, y + 2, w=24, h=24)
    pdf.set_xy(x0 + 30, y + 4)
    pdf.set_text_color(*NEGRO)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(ANCHO - 30, 6, f"AYUNTAMIENTO DE {municipio.upper()}")
    pdf.set_xy(x0 + 30, y + 11)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(ANCHO - 30, 5, nucleo.upper())
    pdf.set_xy(x0 + 30, y + 16)
    pdf.cell(ANCHO - 30, 5, provincia.upper())
    if os.path.exists(SOMACYL):
        pdf.image(SOMACYL, x0 + ANCHO - 45, y + 5, w=40, h=18)
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
    pdf.set_xy(x0, y)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*NEGRO)
    pdf.cell(ANCHO, 5, "A RELLENAR EN FASE DE OBRA", align="C")
    pdf.rect(x0, y, ANCHO, fo_h)
    pdf.line(x0, y + 6, x0 + ANCHO, y + 6)
    colw = ANCHO / 4
    etiquetas_fo = ["Nº Serie contador existente / Fecha instalación",
                    "Lectura contador a sustituir", "Nº Serie contador sustitución", "Observaciones"]
    pdf.set_font("Helvetica", "B", 6.5)
    for i, et in enumerate(etiquetas_fo):
        cx = x0 + i * colw
        if i > 0:
            pdf.line(cx, y, cx, y + fo_h)
        pdf.set_xy(cx + 1, y + 6.5)
        pdf.multi_cell(colw - 2, 3, et)

    pdf.output(ruta_salida)


def _celda(pdf, x, y, w, h, titulo, valor, wrap=False):
    th = min(h * 0.5, 5.5)
    pdf.set_xy(x, y)
    pdf.set_fill_color(*AZUL)
    pdf.set_text_color(*BLANCO)
    pdf.set_font("Helvetica", "B", 7.5 if h < 8 else 8)
    pdf.cell(w, th, titulo, border=1, align="C", fill=True)

    valor = str(valor) if valor is not None else ""
    pdf.set_xy(x, y + th)
    pdf.set_text_color(*NEGRO)
    pdf.set_font("Helvetica", "", 8)
    if wrap:
        y_antes = pdf.get_y()
        pdf.multi_cell(w, max((h - th) / 2, 3.2), valor, border=1)
        alto_usado = pdf.get_y() - y_antes
        if alto_usado < (h - th):
            pdf.rect(x, y_antes, w, h - th)
    else:
        pdf.cell(w, h - th, valor[:60], border=1, align="L")


def _caja_foto(pdf, x, y, w, h, etiqueta, ruta_foto):
    th = 6
    pdf.set_xy(x, y)
    pdf.set_fill_color(*AZUL)
    pdf.set_text_color(*BLANCO)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(w, th, etiqueta, border=1, align="C", fill=True)
    pdf.rect(x, y + th, w, h - th)
    if ruta_foto and os.path.exists(ruta_foto):
        try:
            margen_img = 1
            pdf.image(ruta_foto, x + margen_img, y + th + margen_img,
                      w=w - 2 * margen_img, h=h - th - 2 * margen_img)
        except Exception:
            pdf.set_xy(x, y + th + (h - th) / 2 - 2)
            pdf.set_font("Helvetica", "I", 7)
            pdf.set_text_color(*GRIS)
            pdf.cell(w, 4, "(no se pudo cargar la foto)", align="C")
    else:
        pdf.set_xy(x, y + th + (h - th) / 2 - 2)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(*GRIS)
        pdf.cell(w, 4, "Sin foto", align="C")


def generar_todas_las_fichas(puntos, carpeta_salida, municipio="", nucleo="", provincia=""):
    os.makedirs(carpeta_salida, exist_ok=True)
    rutas = []
    for p in puntos:
        nombre = f"Ficha_{p.get('NFijo') or p.get('_id')}.pdf".replace("/", "-")
        ruta = os.path.join(carpeta_salida, nombre)
        generar_ficha_pdf(p, ruta, municipio=municipio, nucleo=nucleo, provincia=provincia)
        rutas.append(ruta)
    return rutas
