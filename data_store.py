# data_store.py
# Gestión de datos locales: puntos del Padrón + fichas rellenadas en campo.
# Todo se guarda en un JSON local (app storage) para que sobreviva cierres de la app.

import json
import os
import csv
from kivy.app import App

def data_dir():
    """Carpeta de datos privada de la app (persiste entre sesiones)."""
    try:
        base = App.get_running_app().user_data_dir
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".digitalizacion_agua")
    os.makedirs(base, exist_ok=True)
    return base

def photos_dir():
    d = os.path.join(data_dir(), "fotos")
    os.makedirs(d, exist_ok=True)
    return d

def puntos_json_path():
    return os.path.join(data_dir(), "puntos.json")

# Campos precargados desde el Padrón (solo lectura en la ficha)
CAMPOS_PADRON = ["NFijo", "Direccion", "NOrden", "CATVia", "RefCatastral", "Lat", "Lon"]

# Campos que rellena el operario en campo
CAMPOS_CAMPO = [
    "TipEdifica", "NContador", "NSerieCont", "ModRadio", "MarcaModel",
    "Lectura", "FecLectura", "Alojamiento", "Calibre", "Diametros",
    "TipUsoComu", "Exterior", "Interior", "UbicarExte", "ValAcometi",
    "Individual", "LlaveContador", "CambioTapa", "SeBorra",
    "CoordGPS", "Observaciones",
    "FotoSituacion", "FotoInmueble", "FotoContador", "FotoArqueta",
    "Completado",
]

TODOS_CAMPOS = CAMPOS_PADRON + CAMPOS_CAMPO


def cargar_puntos():
    path = puntos_json_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_puntos(puntos):
    with open(puntos_json_path(), "w", encoding="utf-8") as f:
        json.dump(puntos, f, ensure_ascii=False, indent=2)


def importar_padron_csv(csv_path):
    """Lee un CSV del Padrón y lo convierte en la lista de puntos pendientes.
    Espera (o intenta adivinar) columnas: NFijo, Direccion, NOrden, CATVia,
    RefCatastral, Lat, Lon. Columnas no encontradas quedan vacías.
    """
    puntos = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(f, dialect=dialect)
        headers = reader.fieldnames or []
        mapa = _mapear_columnas(headers)
        for i, row in enumerate(reader):
            punto = {c: "" for c in TODOS_CAMPOS}
            for campo_std, col_real in mapa.items():
                punto[campo_std] = (row.get(col_real) or "").strip()
            punto["Completado"] = False
            punto["_id"] = i
            puntos.append(punto)
    return puntos


def _mapear_columnas(headers):
    """Empareja cabeceras variables del CSV con nuestros nombres estándar."""
    alias = {
        "NFijo": ["nfijo", "n fijo", "nº fijo", "numero fijo"],
        "Direccion": ["direccion", "dirección", "direccion-nº policia", "domicilio"],
        "NOrden": ["norden", "n orden", "nº orden"],
        "CATVia": ["catvia", "cat via", "cat. via", "codigo via"],
        "RefCatastral": ["refcatastral", "referencia catastral", "ref catastral", "ref. catastral"],
        "Lat": ["lat", "latitud", "y"],
        "Lon": ["lon", "lng", "longitud", "x"],
    }
    lower_headers = {h.lower().strip(): h for h in headers}
    mapa = {}
    for campo, nombres in alias.items():
        for n in nombres:
            if n in lower_headers:
                mapa[campo] = lower_headers[n]
                break
    return mapa


def actualizar_punto(punto):
    puntos = cargar_puntos()
    for i, p in enumerate(puntos):
        if p["_id"] == punto["_id"]:
            puntos[i] = punto
            break
    guardar_puntos(puntos)
