# android_adjuntar.py
# Permite adjuntar una foto YA EXISTENTE en el dispositivo (en vez de
# tomarla con la cámara) a uno de los 4 huecos de foto de la ficha: desde
# el selector de archivos (SAF) o desde la galería/Fotos. Útil, por
# ejemplo, para adjuntar una captura de pantalla como "Foto: Situación"
# en vez de una foto real.
#
# Mismo patrón que android_filepicker.py (que ya probamos que funciona
# bien en el dispositivo): Intent nativo + copiar el contenido via
# ContentResolver a la carpeta privada de la app, sin depender de rutas
# de almacenamiento tradicionales (que es lo que falla en Android moderno).

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
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " - [adjuntar] " + str(mensaje) + "\n")
    except Exception:
        pass


def _elegir_imagen(accion, destino, on_resultado):
    try:
        from jnius import autoclass
        from android import activity, mActivity
    except Exception as e:
        _log(f"EXCEPCION al importar jnius/android: {e!r}")
        on_resultado(None)
        return

    Intent = autoclass("android.content.Intent")

    request_code = random.randint(100000, 999999)
    _log(f"Lanzando {accion}, request_code={request_code}, destino={destino}")

    intent = Intent(accion)
    if accion == "android.intent.action.OPEN_DOCUMENT":
        intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("image/*")

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
            _copiar_uri_a(uri, destino)
            _log(f"Imagen copiada a: {destino}")
            on_resultado(destino)
        except Exception as e:
            _log(f"EXCEPCION al copiar imagen elegida: {e!r}")
            on_resultado(None)

    activity.bind(on_activity_result=_al_recibir_resultado)
    mActivity.startActivityForResult(intent, request_code)


def adjuntar_archivo(destino, on_resultado):
    """Abre el selector de archivos (Files) filtrado a imágenes."""
    _elegir_imagen("android.intent.action.OPEN_DOCUMENT", destino, on_resultado)


def adjuntar_galeria(destino, on_resultado):
    """Abre el selector de Fotos/Galería."""
    _elegir_imagen("android.intent.action.GET_CONTENT", destino, on_resultado)


def _copiar_uri_a(uri, destino):
    from android import mActivity

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.exists(destino):
        os.remove(destino)

    resolver = mActivity.getContentResolver()
    entrada = resolver.openInputStream(uri)
    buffer_java = bytearray(8192)
    with open(destino, "wb") as salida:
        while True:
            leido = entrada.read(buffer_java)
            if leido == -1:
                break
            salida.write(bytes(buffer_java[:leido]))
    entrada.close()
