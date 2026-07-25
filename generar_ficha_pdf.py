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
from simple_pdf import SimplePDF, envolver_texto

AZUL = (68, 114, 196)
NEGRO = (0, 0, 0)
BLANCO = (255, 255, 255)
GRIS = (140, 140, 140)

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
ESCUDO = os.path.join(ASSETS, "escudo.jpg")
SOMACYL = os.path.join(ASSETS, "somacyl.png")

MARGEN = 12
ANCHO_PAG = 210
ALTO_PAG = 297
ANCHO = ANCHO_PAG - 2 * MARGEN


def _si_no(v):
    # En las fichas reales del cliente, un campo Sí/No falso se deja en
    # blanco (no se escribe "No"); solo se marca cuando es verdadero.
    return "Sí" if v else ""


def _solo_fecha(v):
    """Por si el valor guardado trae hora ('24/07/2026 22:23'), en la
    ficha PDF solo se muestra la fecha."""
    v = (v or "").strip()
    return v.split(" ")[0] if v else v


def generar_ficha_pdf(punto, ruta_salida=None, municipio="", nucleo="", provincia="", pdf=None, escudo_path=None):
    """Si se pasa 'pdf' (una instancia de SimplePDF ya creada), dibuja la
    ficha en la página ACTUAL de ese documento y no lo guarda (lo usa
    generar_todas_las_fichas para juntar varias fichas en un solo archivo).
    Si no se pasa 'pdf', crea uno nuevo de una sola página y lo guarda en
    'ruta_salida' (uso normal para una ficha suelta / pruebas).
    'escudo_path': ruta al escudo extraído de la plantilla Excel elegida
    (ver plantilla_excel.py); si no se indica, se usa el genérico."""
    standalone = pdf is None
    if standalone:
        pdf = SimplePDF(page_w_mm=ANCHO_PAG, page_h_mm=ALTO_PAG)

    x0 = MARGEN
    y = MARGEN

    # ── CABECERA ──
    # Escudo (izq.) + nombre del ayuntamiento/núcleo/provincia (centro) +
    # logo SOMACyL (dcha.), igual que la ficha modelo.
    alto_cab = 28
    pdf.rect(x0, y, ANCHO, alto_cab)

    lado = alto_cab - 4
    ruta_escudo = escudo_path if (escudo_path and os.path.exists(escudo_path)) else ESCUDO
    if os.path.exists(ruta_escudo):
        try:
            pdf.image(ruta_escudo, x0 + 2, y + 2, lado, lado)
        except Exception:
            pass

    texto_x = x0 + lado + 8
    pdf.text(texto_x, y + 5, f"AYUNTAMIENTO DE {municipio.upper()}", size_pt=12, bold=True)
    pdf.text(texto_x, y + 13, nucleo.upper(), size_pt=10, bold=True)
    pdf.text(texto_x, y + 19, provincia.upper(), size_pt=10, bold=True)

    if os.path.exists(SOMACYL):
        try:
            logo_w, logo_h = 42, 16
            pdf.image(SOMACYL, x0 + ANCHO - logo_w - 3, y + (alto_cab - logo_h) / 2, logo_w, logo_h)
        except Exception:
            pass
    y += alto_cab + 3

    # ── FILA Nº FIJO / DIRECCIÓN / TIPO EDIFICACIÓN ──
    fila_h = 14
    col1, col3 = 25, 45
    col2 = ANCHO - col1 - col3
    _celda(pdf, x0, y, col1, fila_h, "Nº FIJO", punto.get("NFijo", ""))
    _celda(pdf, x0 + col1, y, col2, fila_h, "DIRECCIÓN - Nº POLICÍA", punto.get("Direccion", ""))
    _celda(pdf, x0 + col1 + col2, y, col3, fila_h, "TIPO DE EDIFICACIÓN", punto.get("TipEdifica", ""))
    y += fila_h + 3

    # ── BLOQUE 1: Situación (foto) + 2 columnas de datos, igual que el modelo ──
    # El modelo reparte estos 8 campos en 2 sub-columnas (no 1 sola):
    #   col. izq.: Exterior / Válvula de acometida / Coordenadas GPS / Individual / Alojamiento
    #   col. dcha.: nº Módulo Radio / Tipo de uso consumo / Código QR (caja grande, vacía)
    bloque1_h = 65
    foto_w = ANCHO * 0.42
    datos_w = ANCHO - foto_w
    unidad = bloque1_h / 6  # 1+1+2+1+1 = 6 unidades (se calcula antes para sincronizar la barra de "Situación")
    th_bloque1 = min(unidad * 0.5, 5.5)
    _caja_foto(pdf, x0, y, foto_w, bloque1_h, "Situación", punto.get("FotoSituacion"), th=th_bloque1)

    col_izq_w = datos_w * 0.55
    col_dcha_w = datos_w - col_izq_w
    dx_izq = x0 + foto_w
    dx_dcha = dx_izq + col_izq_w

    # "Ubicación del Contador" combina las 3 casillas del formulario
    # (Interior / Exterior / Ubicar exterior) en un único valor de texto.
    ubicacion = []
    if punto.get("Interior"):
        ubicacion.append("Interior")
    if punto.get("Exterior"):
        ubicacion.append("Exterior")
    if punto.get("UbicarExte"):
        ubicacion.append("Ubicar Exterior")
    ubicacion_txt = ", ".join(ubicacion)

    lat = str(punto.get("Latitud") or "").strip()
    lon = str(punto.get("Longitud") or "").strip()
    if lat or lon:
        coord_lineas = [t for t in (lat, lon) if t]
    else:
        # Compatibilidad con puntos capturados antes de separar Latitud/Longitud.
        coord_txt = (punto.get("CoordGPS") or "").strip()
        coord_lineas = [t.strip() for t in coord_txt.split(",") if t.strip()] if coord_txt else None

    filas_izq = [
        ("Ubicación del Contador", ubicacion_txt, None, 1),
        ("Válvula de acometida", _si_no(punto.get("ValAcometi")), None, 1),
        ("Coordenadas GPS", "", coord_lineas, 2),
        ("Individual", _si_no(punto.get("Individual")), None, 1),
        ("Alojamiento", punto.get("Alojamiento", ""), None, 1),
    ]
    yy = y
    for etq, val, lineas_fijas, unidades in filas_izq:
        h = unidad * unidades
        _celda(pdf, dx_izq, yy, col_izq_w, h, etq, val, lineas=lineas_fijas)
        yy += h

    filas_dcha = [
        ("n° Módulo Radio", punto.get("ModRadio", "")),
        ("Tipo de uso consumo", punto.get("TipUsoComu", "")),
    ]
    h_dcha_normal = unidad
    yy = y
    for etq, val in filas_dcha:
        _celda(pdf, dx_dcha, yy, col_dcha_w, h_dcha_normal, etq, val)
        yy += h_dcha_normal
    # Código QR: caja grande vacía (de momento no se genera un QR real,
    # igual que en las fichas ya rellenadas del cliente, que la dejan en
    # blanco a la espera de imprimirlo/pegarlo aparte).
    h_qr = y + bloque1_h - yy
    _celda(pdf, dx_dcha, yy, col_dcha_w, h_qr, "Código QR", "")
    y += bloque1_h + 3

    # ── BLOQUE 2: Contador (foto) + Llave/Calibre/Diámetros, Lectura/Fecha, Marca/Observaciones ──
    bloque2_h = 50
    fh2 = bloque2_h / 3
    th_bloque2 = min(fh2 * 0.5, 5.5)
    _caja_foto(pdf, x0, y, foto_w, bloque2_h, "Contador", punto.get("FotoContador"), th=th_bloque2)

    dx = x0 + foto_w
    dw = datos_w
    w3 = dw / 3
    _celda(pdf, dx, y, w3, fh2, "Llave de contador", _si_no(punto.get("LlaveContador")))
    _celda(pdf, dx + w3, y, w3, fh2, "Calibre", punto.get("Calibre", ""))
    _celda(pdf, dx + 2 * w3, y, w3, fh2, "Diámetros", punto.get("Diametros", ""))
    _celda(pdf, dx, y + fh2, dw / 2, fh2, "Lectura", punto.get("Lectura", ""))
    _celda(pdf, dx + dw / 2, y + fh2, dw / 2, fh2, "Fecha", _solo_fecha(punto.get("FecLectura", "")))

    obs = punto.get("Observaciones", "") or ""
    extra = []
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
    bloque3_h = 60
    mitad = ANCHO / 2
    _caja_foto(pdf, x0, y, mitad - 1.5, bloque3_h, "Inmueble", punto.get("FotoInmueble"))
    _caja_foto(pdf, x0 + mitad + 1.5, y, mitad - 1.5, bloque3_h, "Arqueta", punto.get("FotoArqueta"))
    y += bloque3_h + 4

    # ── BLOQUE FASE DE OBRA ──
    # Mismo estilo de caja azul (etiqueta + valor) que el resto de la
    # ficha. Estructura: título a todo el ancho, columna izq. "Nº Serie
    # contador existente" (alta, ocupa toda la columna), y a la derecha
    # "FECHA DE INSTALACIÓN" arriba y 3 columnas debajo.
    fo_h = 40
    titulo_h = 6
    pdf.set_fill_rgb(*AZUL)
    pdf.rect(x0, y, ANCHO, titulo_h, fill=True, stroke=True)
    _texto_centrado(pdf, x0, y, ANCHO, titulo_h, ["A RELLENAR EN FASE DE OBRA"], size_pt=9, bold=True, color=BLANCO)

    resto_h = fo_h - titulo_h
    col_izq_fo = ANCHO * 0.22
    col_dcha_fo = ANCHO - col_izq_fo
    _celda(pdf, x0, y + titulo_h, col_izq_fo, resto_h, "Nº Serie contador existente",
           punto.get("NSerieCont", ""))

    # "FECHA DE INSTALACIÓN": en el modelo la casilla en blanco va PEGADA
    # a la derecha de la etiqueta, en la misma fila (no debajo, a
    # diferencia del resto de campos de la ficha), y el ancho de la
    # etiqueta+casilla se alinea con las 3 columnas de abajo: la etiqueta
    # ocupa lo mismo que "Lectura..." + "Nº Serie..." juntas, y la casilla
    # en blanco ocupa lo mismo que "Observaciones".
    sub_w = col_dcha_fo / 3
    fecha_h = 9
    label_w = sub_w * 2
    valor_w = sub_w
    fx = x0 + col_izq_fo
    fy = y + titulo_h
    pdf.set_fill_rgb(*AZUL)
    pdf.rect(fx, fy, label_w, fecha_h, fill=True, stroke=True)
    _texto_centrado(pdf, fx, fy, label_w, fecha_h, ["FECHA DE INSTALACIÓN"], size_pt=8, bold=True, color=BLANCO)
    pdf.rect(fx + label_w, fy, valor_w, fecha_h, stroke=True)

    sub_y = y + titulo_h + fecha_h
    sub_h = resto_h - fecha_h
    _celda(pdf, x0 + col_izq_fo, sub_y, sub_w, sub_h, "Lectura contador a sustituir", "")
    _celda(pdf, x0 + col_izq_fo + sub_w, sub_y, sub_w, sub_h, "Nº Serie contador sustitución", "")
    _celda(pdf, x0 + col_izq_fo + 2 * sub_w, sub_y, sub_w, sub_h, "Observaciones", "")
    y += fo_h

    # ── MARCO EXTERIOR ──
    # Recuadro grueso envolviendo toda la ficha, igual que en el modelo.
    pdf.rect(x0, MARGEN, ANCHO, y - MARGEN, stroke=True, line_w_pt=1.6)

    if standalone:
        pdf.output(ruta_salida)


def _celda(pdf, x, y, w, h, titulo, valor, wrap=False, lineas=None, size_pt=8):
    tam_titulo = 7.5 if h < 8 else 8
    lineas_titulo = envolver_texto(titulo, w - 2, tam_titulo, True)[:2]
    alto_texto_titulo = len(lineas_titulo) * tam_titulo * 0.352778 * 1.15 + 1.4
    th = max(min(h * 0.5, 5.5), alto_texto_titulo)
    th = min(th, h - 2)  # deja siempre al menos 2mm para el área del valor
    pdf.set_fill_rgb(*AZUL)
    pdf.rect(x, y, w, th, fill=True, stroke=True)
    _texto_centrado(pdf, x, y, w, th, lineas_titulo, size_pt=tam_titulo, bold=True, color=BLANCO)

    pdf.set_fill_rgb(0, 0, 0)
    pdf.rect(x, y + th, w, h - th, fill=False, stroke=True)

    if lineas is None:
        valor = str(valor) if valor is not None else ""
        if wrap:
            lineas = envolver_texto(valor, w - 3, size_pt, False)[:3]
        else:
            lineas = [valor[:60]] if valor else []
    if lineas:
        _texto_centrado(pdf, x, y + th, w, h - th, lineas, size_pt=size_pt)


def _texto_centrado(pdf, x, y, w, h, lineas, size_pt=8, bold=False, color=NEGRO):
    """Dibuja una lista de líneas centradas horizontal y verticalmente
    dentro de la caja (x, y, w, h). Evita que el valor quede pegado al
    borde superior (pegado a la barra azul) o se salga por abajo."""
    paso_mm = size_pt * 0.352778 * 1.15
    alto_bloque = len(lineas) * paso_mm
    top = y + max(0, (h - alto_bloque) / 2)
    for i, linea in enumerate(lineas):
        pdf.text(x, top + i * paso_mm, linea, size_pt=size_pt, bold=bold, color=color, align="C", box_w_mm=w)


def _caja_foto(pdf, x, y, w, h, etiqueta, ruta_foto, th=6):
    pdf.set_fill_rgb(*AZUL)
    pdf.rect(x, y, w, th, fill=True, stroke=True)
    _texto_centrado(pdf, x, y, w, th, [etiqueta], size_pt=8, bold=True, color=BLANCO)
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


def generar_todas_las_fichas(puntos, ruta_salida, municipio="", nucleo="", provincia="", escudo_path=None):
    """Genera UN SOLO archivo PDF con una página por punto (antes generaba
    un archivo suelto por cada punto). 'ruta_salida' es la ruta completa
    del archivo .pdf a crear (no una carpeta)."""
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    pdf = SimplePDF(page_w_mm=ANCHO_PAG, page_h_mm=ALTO_PAG)
    for i, p in enumerate(puntos):
        if i > 0:
            pdf.nueva_pagina()
        generar_ficha_pdf(p, municipio=municipio, nucleo=nucleo, provincia=provincia, pdf=pdf, escudo_path=escudo_path)
    pdf.output(ruta_salida)
    return ruta_salida
