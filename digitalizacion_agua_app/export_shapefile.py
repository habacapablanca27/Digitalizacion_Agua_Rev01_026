# export_shapefile.py
# Exporta todos los puntos capturados (con sus atributos y rutas de fotos) a un Shapefile.
# Usa pyshp (shapefile) porque es puro Python: no necesita GDAL/Fiona,
# que son inviables de compilar en Android con buildozer.

import os
import shapefile  # pyshp
from data_store import data_dir, CAMPOS_PADRON, CAMPOS_CAMPO

# pyshp exige nombres de campo <= 10 caracteres (límite DBF clásico) -> los recortamos
_MAX_LEN = 10

def _campo_dbf(nombre):
    return nombre[:_MAX_LEN]


def exportar_shapefile(puntos, nombre_salida="digitalizacion_agua"):
    out_dir = os.path.join(data_dir(), "export")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, nombre_salida)

    campos = CAMPOS_PADRON + CAMPOS_CAMPO
    with shapefile.Writer(out_path, shapeType=shapefile.POINT) as w:
        w.field("id", "N")
        vistos = set()
        for campo in campos:
            nombre_corto = _campo_dbf(campo)
            base = nombre_corto
            n = 1
            while nombre_corto in vistos:
                nombre_corto = f"{base[:_MAX_LEN-1]}{n}"
                n += 1
            vistos.add(nombre_corto)
            tipo = "L" if campo in ("Exterior", "Interior", "UbicarExte", "ValAcometi",
                                     "Individual", "LlaveContador", "CambioTapa",
                                     "SeBorra", "Completado") else "C"
            size = 1 if tipo == "L" else 254
            w.field(nombre_corto, tipo, size=size)

        for p in puntos:
            lat = _to_float(p.get("Lat"))
            lon = _to_float(p.get("Lon"))
            if lat is None or lon is None:
                # Si no hay coordenada precargada, usamos la del GPS capturado en campo
                lat, lon = _parse_coord_gps(p.get("CoordGPS"))
            if lat is None or lon is None:
                continue  # sin geometría no se puede escribir el punto
            w.point(lon, lat)
            valores = [p.get("_id", 0)]
            for campo in campos:
                v = p.get(campo, "")
                if campo in ("Exterior", "Interior", "UbicarExte", "ValAcometi",
                             "Individual", "LlaveContador", "CambioTapa",
                             "SeBorra", "Completado"):
                    valores.append(bool(v))
                else:
                    valores.append(str(v) if v is not None else "")
            w.record(*valores)

    # .prj en WGS84 para que QGIS lo reconozca sin preguntar
    with open(out_path + ".prj", "w") as f:
        f.write(
            'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
            '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
        )
    return out_dir


def _to_float(v):
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_coord_gps(coord_str):
    if not coord_str:
        return None, None
    try:
        lat_str, lon_str = coord_str.split(",")
        return float(lat_str.strip()), float(lon_str.strip())
    except Exception:
        return None, None
