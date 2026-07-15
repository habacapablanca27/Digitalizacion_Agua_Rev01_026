# importar_shapefile.py
# Permite cargar el Padrón directamente desde un Shapefile (como en QGIS),
# en vez de tener que convertirlo antes a CSV. Como en el móvil no es
# práctico seleccionar varios archivos sueltos (.shp/.shx/.dbf/.prj a la
# vez), el usuario comprime esos archivos en un .zip y la app lo
# descomprime internamente.
#
# Convierte automáticamente las coordenadas si el Shapefile viene en UTM
# (detecta la zona leyendo el .prj) a Lat/Lon (WGS84), sin depender de
# pyproj/GDAL (no compilan bien para Android).

import os
import re
import math
import zipfile
import shutil
import shapefile  # pyshp

import data_store as ds

# Mapeo de campos típicos de un shapefile de contadores (QField/QGIS) a
# nuestro esquema interno. Las claves son variantes habituales de nombre
# (en minúsculas, sin espacios) que se van probando.
_ALIAS_CAMPOS = {
    "NFijo": ["nfijo", "n_fijo", "nfijo "],
    "Direccion": ["direccion", "direcci�n", "direccion "],
    "NOrden": ["numorden", "num_orden", "norden", "n_orden"],
    "CATVia": ["catvia", "cat_via", "catvia "],
    "RefCatastral": ["referencia", "refcatastral", "ref_catastral"],
    "NContador": ["ncontador", "n_contador"],
    "NSerieCont": ["nseriecont", "n_serie_cont", "nseriecon"],
    "ModRadio": ["modradio", "mod_radio"],
    "MarcaModel": ["marcamodel", "marca_modelo", "marcamode"],
    "Lectura": ["lectura"],
    "FecLectura": ["feclectura", "fec_lectura"],
    "Alojamiento": ["alojamient", "alojamiento"],
    "Calibre": ["calibre"],
    "Diametros": ["diametros"],
    "TipEdifica": ["tipedifica", "tip_edifica"],
    "TipUsoComu": ["tipusocomu", "tip_uso_comu"],
    "Observaciones": ["observacio", "observaciones"],
    "Exterior": ["exterior"],
    "Interior": ["interior"],
    "ValAcometi": ["valacometi", "val_acometi"],
    "Individual": ["individual"],
    "LlaveContador": ["llavecorte", "llave_corte", "llavecontador"],
    "UbicarExte": ["ubicarexte", "ubicar_exte"],
    "CambioTapa": ["cambiotapa", "cambio_tapa"],
    "SeBorra": ["seborra?", "se borra?", "seborra", "se_borra"],
}

_CAMPOS_BOOL = {
    "Exterior", "Interior", "ValAcometi", "Individual", "LlaveContador",
    "UbicarExte", "CambioTapa", "SeBorra",
}


def _normalizar(nombre):
    return nombre.strip().lower().replace(" ", "").replace("_", "")


def _mapear_campos_dbf(nombres_dbf):
    mapa = {}
    normalizados = {_normalizar(n): n for n in nombres_dbf}
    for campo_std, alias in _ALIAS_CAMPOS.items():
        for a in alias:
            a_norm = _normalizar(a)
            if a_norm in normalizados:
                mapa[campo_std] = normalizados[a_norm]
                break
    return mapa


def _leer_zona_utm_desde_prj(ruta_prj):
    """Lee el .prj y devuelve (zona, hemisferio_norte) si es un UTM
    reconocible, o None si no se puede determinar (o si ya es WGS84 lat/lon
    geográfico, en cuyo caso no hace falta convertir nada)."""
    if not os.path.exists(ruta_prj):
        return None
    with open(ruta_prj, "r", encoding="utf-8", errors="ignore") as f:
        contenido = f.read()
    if "Transverse_Mercator" not in contenido and "UTM" not in contenido.upper():
        return None
    m = re.search(r'Central_Meridian["\s,]+(-?\d+\.?\d*)', contenido)
    if not m:
        return None
    meridiano_central = float(m.group(1))
    zona = int(round((meridiano_central + 183) / 6))
    norte = "False_Northing\",0" in contenido or "False_Northing\", 0" in contenido
    return zona, norte if norte else True


def _utm_a_latlon(easting, northing, zona, hemisferio_norte=True):
    """Conversión UTM -> WGS84 (fórmulas estándar de Snyder), sin
    dependencias externas. Precisión de centímetros, más que suficiente
    para ubicar contadores de agua."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    e_p2 = e2 / (1 - e2)

    x = easting - 500000.0
    y = northing if hemisferio_norte else northing - 10000000.0

    meridiano_central = math.radians(-183 + zona * 6)

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))

    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu))

    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = e_p2 * math.cos(phi1) ** 2
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)

    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * e_p2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * e_p2 - 3 * c1 ** 2) * d ** 6 / 720
    )
    lon = meridiano_central + (
        d
        - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * e_p2 + 24 * t1 ** 2) * d ** 5 / 120
    ) / math.cos(phi1)

    return math.degrees(lat), math.degrees(lon)


def extraer_zip_proyecto(ruta_zip):
    """Descomprime el .zip del proyecto (carpeta completa, tal como la
    exporta QGIS/QField) a una carpeta de trabajo y la devuelve."""
    carpeta_tmp = os.path.join(ds.data_dir(), "shapefile_importado")
    if os.path.exists(carpeta_tmp):
        shutil.rmtree(carpeta_tmp)
    os.makedirs(carpeta_tmp, exist_ok=True)
    with zipfile.ZipFile(ruta_zip, "r") as z:
        z.extractall(carpeta_tmp)
    return carpeta_tmp


def _buscar_qgs_en_carpeta(carpeta):
    for raiz, _dirs, archivos in os.walk(carpeta):
        for a in archivos:
            if a.lower().endswith(".qgs"):
                return os.path.join(raiz, a)
    return None


def listar_capas_de_zip(ruta_zip):
    """Descomprime el .zip y, si contiene un proyecto .qgs, devuelve
    (carpeta_extraida, lista_de_capas). Si no hay .qgs, lista_de_capas
    sale vacía y el llamante debe usar el modo de un único .shp."""
    carpeta = extraer_zip_proyecto(ruta_zip)
    ruta_qgs = _buscar_qgs_en_carpeta(carpeta)
    if not ruta_qgs:
        return carpeta, []
    try:
        capas = listar_capas_vectoriales_qgs(ruta_qgs)
    except Exception:
        capas = []
    return carpeta, capas


def importar_padron_shapefile_zip(ruta_zip, nombre_shp=None):
    """Descomprime un .zip con el proyecto (o solo el shapefile) y
    devuelve la lista de puntos, con las coordenadas ya convertidas a
    Lat/Lon si hacía falta. Si nombre_shp se indica, carga esa capa en
    concreto (elegida por el usuario del listado del .qgs)."""
    carpeta_tmp = extraer_zip_proyecto(ruta_zip)
    return leer_puntos_desde_carpeta(carpeta_tmp, nombre_shp=nombre_shp)


def listar_capas_vectoriales_qgs(ruta_qgs):
    """Lee un archivo .qgs (proyecto QGIS, es XML) y devuelve la lista de
    capas vectoriales (shapefiles) que contiene, como
    [{"nombre": ..., "archivo_shp": ...}, ...]. Ignora capas raster,
    mbtiles y de mapa base (WMS/XYZ)."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(ruta_qgs)
    root = tree.getroot()
    capas = []
    vistos = set()
    for ml in root.iter("maplayer"):
        proveedor = ml.findtext("provider")
        datasource = ml.findtext("datasource") or ""
        nombre = ml.findtext("layername") or ""
        if proveedor != "ogr":
            continue
        if not datasource.lower().endswith(".shp"):
            continue
        archivo_shp = datasource.split("/")[-1].split("\\")[-1]
        clave = (nombre, archivo_shp)
        if clave in vistos:
            continue
        vistos.add(clave)
        capas.append({"nombre": nombre or archivo_shp, "archivo_shp": archivo_shp})
    return capas


def leer_puntos_desde_carpeta(carpeta, nombre_shp=None):
    """Lee un Shapefile de puntos que ya está en una carpeta local
    (sin comprimir). Si nombre_shp se indica, usa ese archivo en
    concreto (por si la carpeta tiene varios .shp); si no, usa el
    único que encuentre."""
    ruta_shp = None
    if nombre_shp:
        for raiz, _dirs, archivos in os.walk(carpeta):
            for a in archivos:
                if a == nombre_shp:
                    ruta_shp = os.path.join(raiz, a)
                    break
            if ruta_shp:
                break
    else:
        for raiz, _dirs, archivos in os.walk(carpeta):
            for a in archivos:
                if a.lower().endswith(".shp"):
                    ruta_shp = os.path.join(raiz, a)
                    break
            if ruta_shp:
                break

    if not ruta_shp:
        raise ValueError("No se encontró el archivo .shp esperado en la carpeta")

    base = ruta_shp[:-4]
    ruta_prj = base + ".prj"
    info_utm = _leer_zona_utm_desde_prj(ruta_prj)

    sf = shapefile.Reader(ruta_shp)
    nombres_dbf = [f[0] for f in sf.fields[1:]]
    mapa = _mapear_campos_dbf(nombres_dbf)

    puntos = []
    for i, sr in enumerate(sf.iterShapeRecords()):
        rec = sr.record.as_dict()
        punto = {c: "" for c in ds.TODOS_CAMPOS}
        punto["_id"] = i
        punto["Completado"] = False

        for campo_std, col_real in mapa.items():
            valor = rec.get(col_real, "")
            if campo_std in _CAMPOS_BOOL:
                punto[campo_std] = bool(valor)
            elif valor is not None:
                punto[campo_std] = str(valor).strip()

        puntos_geom = sr.shape.points
        if puntos_geom:
            x, y = puntos_geom[0][0], puntos_geom[0][1]
            if info_utm:
                zona, hemisferio_norte = info_utm
                lat, lon = _utm_a_latlon(x, y, zona, hemisferio_norte)
            else:
                lon, lat = x, y
            punto["Lat"] = f"{lat:.7f}"
            punto["Lon"] = f"{lon:.7f}"

        if punto.get("Lectura"):
            punto["Completado"] = True

        puntos.append(punto)

    return puntos
