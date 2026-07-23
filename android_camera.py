# android_camera.py
# Sustituye a plyer.camera (roto en Android moderno: internamente arma el
# intent de camara pasando un Uri "file://" de la carpeta privada de la
# app, y desde Android 7 (API 24+) eso esta prohibido -> salta
# FileUriExposedException y la foto nunca vuelve).
#
# Aqui usamos el mecanismo oficial para este caso: FileProvider. Se genera
# un Uri "content://" para el archivo destino (el mismo que usan apps como
# WhatsApp o Gmail para compartir un archivo propio con otra app), y se le
# pasa ese Uri a la camara en MediaStore.EXTRA_OUTPUT. La foto la escribe
# la propia app de camara directamente en el archivo destino.
#
# Requiere que el AndroidManifest declare el <provider> de FileProvider
# (ver buildozer.spec: android.extra_manifest_application_arguments y
# android.add_resources) apuntando a la carpeta donde se guardan las fotos.

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
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " - [camera] " + str(mensaje) + "\n")
    except Exception:
        pass


def tomar_foto(destino, on_resultado):
    """Abre la camara nativa de Android para tomar una foto en resolucion
    completa y guardarla en la ruta local 'destino' (dentro de la carpeta
    privada de la app). on_resultado(ruta_o_None) se llama cuando el
    usuario toma la foto (ya guardada en 'destino') o cancela/falla (None).
    """
    try:
        from jnius import autoclass, cast
        from android import activity, mActivity
    except Exception as e:
        _log(f"EXCEPCION al importar jnius/android: {e!r}")
        on_resultado(None)
        return

    try:
        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore")
        FileProviderJ = autoclass("androidx.core.content.FileProvider")
        File = autoclass("java.io.File")

        os.makedirs(os.path.dirname(destino), exist_ok=True)
        # Si ya existiera un archivo previo con el mismo nombre (repetir
        # foto), lo quitamos: algunas camaras no sobrescriben bien un
        # Uri de FileProvider que ya apunta a un archivo con contenido.
        if os.path.exists(destino):
            os.remove(destino)
        archivo_java = File(destino)

        authority = mActivity.getPackageName() + ".fileprovider"
        uri = FileProviderJ.getUriForFile(mActivity, authority, archivo_java)
    except Exception as e:
        _log(f"EXCEPCION al preparar el Uri de FileProvider: {e!r}")
        on_resultado(None)
        return

    request_code = random.randint(100000, 999999)
    _log(f"Lanzando ACTION_IMAGE_CAPTURE, request_code={request_code}, destino={destino}")

    intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
    # Intent.putExtra() tiene muchas variantes sobrecargadas (String,
    # int, Parcelable, Serializable...) y pyjnius a veces elige mal cual
    # usar para un Uri. Con cast() se le indica explicitamente que use
    # la variante que recibe un Parcelable (Uri lo implementa), evitando
    # el error "Invalid instance of 'android/net/Uri' passed for a ...".
    Parcelable = autoclass("android.os.Parcelable")
    intent.putExtra(MediaStore.EXTRA_OUTPUT, cast(Parcelable, uri))
    intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

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
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            on_resultado(destino)
        else:
            _log("RESULT_OK pero el archivo no existe o esta vacio")
            on_resultado(None)

    activity.bind(on_activity_result=_al_recibir_resultado)

    try:
        # Algunos fabricantes (Xiaomi/MIUI, Samsung...) tienen apps de
        # camara que ignoran los flags GRANT_*_URI_PERMISSION del intent
        # y fallan igualmente al escribir en el Uri. Conceder el permiso
        # explicitamente a cada app que pueda responder al intent es la
        # forma robusta recomendada para estos casos.
        resInfoList = mActivity.getPackageManager().queryIntentActivities(intent, 0)
        it = resInfoList.iterator()
        while it.hasNext():
            info = it.next()
            paquete = info.activityInfo.packageName
            mActivity.grantUriPermission(
                paquete,
                uri,
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
    except Exception as e:
        _log(f"Aviso: no se pudo pre-conceder permiso a apps de camara: {e!r}")

    mActivity.startActivityForResult(intent, request_code)
