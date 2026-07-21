# android_filepicker.py
# Selector de archivos propio para Android, para sustituir a
# plyer.filechooser (cuyo código de resolución de URIs es antiguo y falla
# con "Permission denied: '/storage'" en Android moderno, con almacenamiento
# con alcance limitado / scoped storage).
#
# Usa directamente el Intent nativo ACTION_OPEN_DOCUMENT (el mismo mecanismo
# moderno que usan Google Drive, WhatsApp, etc. para adjuntar archivos) y
# lee el contenido vía ContentResolver, sin intentar nunca calcular una
# ruta de archivo tradicional (que es justo lo que rompía en plyer).

import os
import random
import time


def _log(mensaje):
    try:
        from android import mActivity
        carpeta = mActivity.getExternalFilesDir(None).getAbsolutePath()
    except Exception:
        carpeta = os.path.expanduser("~")
    try:
        with open(os.path.join(carpeta, "debug_log.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " - [filepicker] " + str(mensaje) + "\n")
    except Exception:
        pass


def elegir_archivo(on_resultado, tipos_mime=None):
    """Abre el selector nativo de Android para un único archivo.
    on_resultado(ruta_local_o_None) se llama cuando el usuario elige un
    archivo (ya copiado a la carpeta privada de la app) o cancela/falla
    (None). tipos_mime: lista opcional de MIME types, ej. ["application/zip"].
    """
    try:
        from jnius import autoclass
        from android import activity, mActivity
    except Exception as e:
        _log(f"EXCEPCION al importar jnius/android: {e!r}")
        on_resultado(None)
        return

    Intent = autoclass("android.content.Intent")

    request_code = random.randint(100000, 999999)
    _log(f"Lanzando ACTION_OPEN_DOCUMENT, request_code={request_code}, tipos={tipos_mime}")

    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType(tipos_mime[0] if tipos_mime else "*/*")

    def _al_recibir_resultado(request_code_recibido, result_code, data):
        if request_code_recibido != request_code:
            return
        _log(f"onActivityResult recibido: result_code={result_code}")
        try:
            activity.unbind(on_activity_result=_al_recibir_resultado)
        except Exception:
            pass
        if result_code != -1:  # Activity.RESULT_OK
            on_resultado(None)
            return
        if data is None:
            on_resultado(None)
            return
        uri = data.getData()
        if uri is None:
            on_resultado(None)
            return
        try:
            ruta_local = _copiar_uri_a_local(uri)
            _log(f"Archivo copiado a: {ruta_local}")
            on_resultado(ruta_local)
        except Exception as e:
            _log(f"EXCEPCION al copiar archivo elegido: {e!r}")
            on_resultado(None)

    activity.bind(on_activity_result=_al_recibir_resultado)
    mActivity.startActivityForResult(intent, request_code)


def _nombre_archivo_desde_uri(uri):
    try:
        from jnius import autoclass
        DocumentsContract = autoclass("android.provider.DocumentsContract")
        from android import mActivity
        resolver = mActivity.getContentResolver()
        cursor = resolver.query(uri, None, None, None, None)
        nombre = "archivo_importado"
        if cursor is not None and cursor.moveToFirst():
            idx = cursor.getColumnIndex("_display_name")
            if idx != -1:
                nombre = cursor.getString(idx)
            cursor.close()
        return nombre
    except Exception:
        return "archivo_importado"


def _copiar_uri_a_local(uri):
    """Copia el contenido de una URI 'content://' a un archivo dentro de la
    carpeta privada de la app, y devuelve esa ruta local (ya utilizable con
    open() normal, sin depender de permisos de almacenamiento)."""
    from jnius import autoclass
    from android import mActivity
    import data_store as ds

    resolver = mActivity.getContentResolver()
    entrada = resolver.openInputStream(uri)

    nombre = _nombre_archivo_desde_uri(uri)
    destino = os.path.join(ds.data_dir(), "importado_" + nombre)

    buffer_java = bytearray(8192)
    with open(destino, "wb") as salida:
        while True:
            leido = entrada.read(buffer_java)
            if leido == -1:
                break
            salida.write(bytes(buffer_java[:leido]))
    entrada.close()
    return destino
