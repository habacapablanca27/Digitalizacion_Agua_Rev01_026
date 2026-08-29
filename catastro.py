# catastro.py — Búsqueda de ubicación usando el servicio web público de la
# Sede Electrónica del Catastro (Oficina Virtual del Catastro, OVC).
# No hace falta clave de API, es un servicio gratuito del gobierno.
#
# AVISO: esta integración se hizo sin poder probarla contra el servicio
# real (sin acceso a internet desde el entorno donde se escribió). Los
# nombres de parámetros y de etiquetas XML son los documentados
# públicamente para este servicio, pero si algo no encaja a la primera,
# el error que se lance aquí incluye el XML crudo en el debug_log.txt
# para poder ajustarlo rápido sin tener que adivinar.

import requests
import xml.etree.ElementTree as ET

_BASE_CALLEJERO = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx"
_BASE_COORD = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx"

# Lista fija de las 52 provincias (no cambian), con la grafía que usa
# Catastro en sus propios desplegables (sin tildes en varios nombres,
# tal cual sale en su web). Para "Provincia" no hace falta llamar a
# ningún servicio -- para "Municipio" sí haría falta (son ~8000 y
# dependen de la provincia elegida), pendiente de implementar con una
# consulta en vivo a Catastro.
PROVINCIAS = [
    "A CORUÑA", "ALAVA", "ALBACETE", "ALICANTE", "ALMERIA", "ASTURIAS",
    "AVILA", "BADAJOZ", "BALEARES", "BARCELONA", "BURGOS", "CACERES",
    "CADIZ", "CANTABRIA", "CASTELLON", "CEUTA", "CIUDAD REAL", "CORDOBA",
    "CUENCA", "GIRONA", "GRANADA", "GUADALAJARA", "GUIPUZCOA", "HUELVA",
    "HUESCA", "JAEN", "LA RIOJA", "LAS PALMAS", "LEON", "LLEIDA", "LUGO",
    "MADRID", "MALAGA", "MELILLA", "MURCIA", "NAVARRA", "OURENSE",
    "PALENCIA", "PONTEVEDRA", "SALAMANCA", "SANTA CRUZ DE TENERIFE",
    "SEGOVIA", "SEVILLA", "SORIA", "TARRAGONA", "TERUEL", "TOLEDO",
    "VALENCIA", "VALLADOLID", "VIZCAYA", "ZAMORA", "ZARAGOZA",
]


def _log(mensaje):
    try:
        from main import _log_debug
        _log_debug(mensaje)
    except Exception:
        pass


def _quitar_namespace(elem):
    """El XML que devuelve Catastro trae namespace por defecto en cada
    etiqueta; se quita para poder buscar con rutas simples tipo './/rc'."""
    for e in elem.iter():
        if "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    return elem


def _pedir_xml(url, params, timeout=12):
    resp = requests.get(url, params=params, timeout=timeout)
    _log(f"catastro GET {resp.url} -> HTTP {resp.status_code}")
    resp.raise_for_status()
    _log(f"catastro respuesta cruda (primeros 800 car.): {resp.text[:800]!r}")
    return _quitar_namespace(ET.fromstring(resp.content))


def _texto_error(root):
    des = root.find(".//lerr/des")
    if des is not None and des.text:
        return des.text
    return "Catastro no devolvió resultados (o el formato de la respuesta no es el esperado)."


def _armar_rc(rc_elem):
    """El RC completo (20 caracteres) viene partido en varios trozos
    (pc1+pc2+car+cc1+cc2) dentro de <rc>...</rc>; se juntan."""
    partes = ["pc1", "pc2", "car", "cc1", "cc2"]
    return "".join(rc_elem.findtext(p, "") for p in partes)


def coordenadas_desde_rc(referencia_catastral, provincia="", municipio=""):
    """Referencia Catastral -> (lat, lon) en WGS84 grados.
    Este servicio en concreto (Consulta_CPMRC) solo acepta los primeros
    14 caracteres de la referencia (la parte de "parcela"; los últimos
    6 identifican la unidad dentro del edificio y no hacen falta aquí)
    -- confirmado con el error real que devuelve Catastro si se le
    manda la referencia completa de 20: "LA REFERENCIA CATASTRAL DEBE
    SER DE 14 POSICIONES"."""
    referencia_catastral = referencia_catastral.strip().upper()[:14]
    root = _pedir_xml(f"{_BASE_COORD}/Consulta_CPMRC", {
        "Provincia": provincia, "Municipio": municipio,
        "SRS": "EPSG:4326", "RC": referencia_catastral,
    })
    xcen = root.find(".//xcen")
    ycen = root.find(".//ycen")
    if xcen is None or ycen is None or not xcen.text or not ycen.text:
        raise ValueError(_texto_error(root))
    # xcen = longitud, ycen = latitud (convención habitual de Catastro
    # para coordenadas geográficas, igual que x=este/lon, y=norte/lat).
    return float(ycen.text), float(xcen.text)


def buscar_por_direccion(provincia, municipio, via, numero=""):
    """Provincia+Municipio+Vía(+Número) -> lista de (rc, descripción)."""
    params = {
        "Provincia": provincia.strip().upper(),
        "Municipio": municipio.strip().upper(),
        "TipoVia": "", "NombreVia": via.strip(),
    }
    if numero.strip():
        params["Numero"] = numero.strip()
    root = _pedir_xml(f"{_BASE_CALLEJERO}/Consulta_DNPLOC", params)
    resultados = []
    for bi in root.findall(".//bico/bi"):
        rc_elem = bi.find("./idbi/rc")
        if rc_elem is None:
            continue
        rc = _armar_rc(rc_elem)
        descripcion = bi.findtext("./ldt", "") or rc
        resultados.append((rc, descripcion))
    if not resultados:
        raise ValueError(_texto_error(root))
    return resultados


def buscar_por_poligono_parcela(provincia, municipio, poligono, parcela):
    """Provincia+Municipio+Polígono+Parcela -> lista de (rc, descripción).
    Es la búsqueda más relevante para catastro rústico (contadores de
    agua en fincas/parcelas rurales, sin dirección de calle)."""
    root = _pedir_xml(f"{_BASE_CALLEJERO}/Consulta_DNPPP", {
        "Provincia": provincia.strip().upper(),
        "Municipio": municipio.strip().upper(),
        "Poligono": poligono.strip(),
        "Parcela": parcela.strip(),
    })
    resultados = []
    for bi in root.findall(".//bico/bi"):
        rc_elem = bi.find("./idbi/rc")
        if rc_elem is None:
            continue
        rc = _armar_rc(rc_elem)
        descripcion = bi.findtext("./ldt", "") or rc
        resultados.append((rc, descripcion))
    if not resultados:
        raise ValueError(_texto_error(root))
    return resultados
