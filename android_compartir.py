# android_compartir.py
# Abre el dialogo nativo de "Compartir" de Android para una lista de
# archivos guardados en la carpeta privada de la app (p.ej. las fichas
# PDF, o el Shapefile exportado). Reutiliza el mismo FileProvider que ya
# se configuro para la camara (ver android_camera.py y buildozer.spec),
# asi el usuario puede sacar esos archivos a Drive, WhatsApp, email,
# etc. sin necesitar acceso root para llegar a la carpeta privada.

import os
import time
import traceback


def _log(mensaje):
    try:
        from android import mActivity
        carpeta = mActivity.getExternalFilesDir(None).getAbsolutePath()
    except Exception:
        carpeta = os.path.expanduser("~")
    try:
        with open(os.path.join(carpeta, "debug_log.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " - [compartir] " + str(mensaje) + "\n")
    except Exception:
        pass


def compartir_archivos(rutas, titulo="Compartir", tipo_mime="application/pdf"):
    """rutas: lista de rutas locales absolutas de archivos ya existentes.
    Devuelve True si se pudo lanzar el dialogo de compartir, False si no
    (por ejemplo si la lista viene vacia o algo falla; en ese caso se deja
    constancia del motivo exacto en debug_log.txt)."""
    rutas = [r for r in rutas if r and os.path.exists(r)]
    if not rutas:
        _log("compartir_archivos: la lista de rutas quedo vacia (no habia archivos).")
        return False

    try:
        from jnius import autoclass, cast
        from android import mActivity
    except Exception as e:
        _log(f"EXCEPCION al importar jnius/android: {e!r}")
        return False

    try:
        Intent = autoclass("android.content.Intent")
        FileProviderJ = autoclass("androidx.core.content.FileProvider")
        File = autoclass("java.io.File")
        ArrayList = autoclass("java.util.ArrayList")
        Parcelable = autoclass("android.os.Parcelable")

        authority = mActivity.getPackageName() + ".fileprovider"
        _log(f"compartir_archivos: {len(rutas)} archivo(s), authority={authority}")

        uris = ArrayList()
        for ruta in rutas:
            archivo_java = File(ruta)
            uri = FileProviderJ.getUriForFile(mActivity, authority, archivo_java)
            uris.add(cast(Parcelable, uri))
        _log(f"compartir_archivos: {uris.size()} URI(s) generados correctamente")

        intent = Intent(Intent.ACTION_SEND_MULTIPLE)
        intent.setType(tipo_mime)
        intent.putParcelableArrayListExtra(Intent.EXTRA_STREAM, cast("java.util.ArrayList", uris))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

        chooser = Intent.createChooser(cast("android.content.Intent", intent), titulo)
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        mActivity.startActivity(chooser)
        _log("compartir_archivos: startActivity(chooser) lanzado sin excepciones")
        return True
    except Exception as e:
        _log(f"EXCEPCION en compartir_archivos: {e!r}\n{traceback.format_exc()}")
        return False
