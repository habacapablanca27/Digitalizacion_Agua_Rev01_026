# estilos_qgs.py
# Lee el color/grosor de línea que cada capa YA TENÍA definido en QGIS
# (guardado dentro del proyecto .qgs, que es un XML), para que el mapa de
# la app la pinte igual, en vez de asignarle un color al azar de una
# paleta fija. Soporta capas con "halo" (varios trazos apilados, como
# "Límites": una línea negra gruesa debajo y una naranja más fina encima).

import xml.etree.ElementTree as ET


def leer_estilos_desde_qgs(ruta_qgs):
    """Devuelve {nombre_capa: [(r, g, b, ancho_mm), ...]}. La lista de
    trazos va en el mismo orden en que QGIS los dibuja (el primero es el
    de más abajo), así que al dibujarlos en ese orden se reproduce el
    mismo efecto (p.ej. el halo negro+naranja de "Límites").
    Si algo falla al leer el .qgs, devuelve {} (el llamante debe usar
    entonces los colores por defecto de siempre, sin romper nada)."""
    try:
        tree = ET.parse(ruta_qgs)
    except Exception:
        return {}
    root = tree.getroot()

    estilos = {}
    for ml in root.iter("maplayer"):
        if ml.get("type") != "vector":
            continue
        nombre = ml.findtext("layername") or ""
        renderer = ml.find("renderer-v2")
        if renderer is None:
            continue
        symbols_el = renderer.find("symbols")
        if symbols_el is None:
            continue

        trazos = []
        for symbol in symbols_el.findall("symbol"):
            for layer_el in symbol.findall("layer"):
                clase = layer_el.get("class", "")
                opciones = _leer_opciones(layer_el)
                if clase == "SimpleLine":
                    color = _parse_color(opciones.get("line_color"))
                    ancho = _parse_float(opciones.get("line_width"), 0.5)
                elif clase == "SimpleFill":
                    # Solo dibujamos contornos (no rellenos), así que de un
                    # relleno usamos el color/grosor de SU borde.
                    color = _parse_color(opciones.get("outline_color"))
                    ancho = _parse_float(opciones.get("outline_width"), 0.3)
                else:
                    color = None
                    ancho = None
                if color:
                    trazos.append((color[0], color[1], color[2], ancho))
        if trazos:
            estilos[nombre] = trazos
    return estilos


def leer_etiquetas_desde_qgs(ruta_qgs):
    """Devuelve {nombre_capa: nombre_campo} para las capas que tengan
    etiquetas activadas en QGIS (ej. las 'CON_DIRECCIONES', que muestran
    el nombre de la calle/dirección escrito sobre el mapa). Solo soporta
    el caso más común (una etiqueta = un campo tal cual, sin fórmulas);
    si la capa no tiene etiquetas o usa una expresión, no aparece aquí."""
    try:
        tree = ET.parse(ruta_qgs)
    except Exception:
        return {}
    root = tree.getroot()

    etiquetas_por_capa = {}
    for ml in root.iter("maplayer"):
        if ml.get("type") != "vector":
            continue
        if ml.get("labelsEnabled") != "1":
            continue
        nombre = ml.findtext("layername") or ""
        labeling = ml.find("labeling")
        if labeling is None or labeling.get("type") != "simple":
            continue
        text_style = labeling.find(".//text-style")
        if text_style is None:
            continue
        if text_style.get("isExpression") == "1":
            continue  # fórmula compleja; no la intentamos reproducir
        campo = text_style.get("fieldName")
        if campo:
            etiquetas_por_capa[nombre] = campo
    return etiquetas_por_capa


def _leer_opciones(layer_el):
    """El XML de un 'layer' de símbolo QGIS mete sus opciones en un
    <Option type="Map"> con hijos <Option name=... value=.../>. Esto los
    junta en un dict {nombre: valor} para leerlos facil."""
    opciones = {}
    opts_map = layer_el.find("Option")
    if opts_map is not None:
        for opt in opts_map.findall("Option"):
            n = opt.get("name")
            v = opt.get("value")
            if n:
                opciones[n] = v
    return opciones


def _parse_color(valor):
    """QGIS guarda el color como 'R,G,B,A,rgb:...' (0-255). Devuelve
    (r,g,b) en 0-1 para usar directo con kivy.graphics.Color."""
    if not valor:
        return None
    partes = valor.split(",")
    try:
        r, g, b = int(partes[0]), int(partes[1]), int(partes[2])
        return (r / 255.0, g / 255.0, b / 255.0)
    except Exception:
        return None


def _parse_float(valor, defecto):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto
