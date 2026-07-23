# android_compartir.py
# Abre el dialogo nativo de "Compartir" de Android para una lista de
# archivos guardados en la carpeta privada de la app (p.ej. las fichas
# PDF, o el Shapefile exportado). Reutiliza el mismo FileProvider que ya
# se configuro para la camara (ver android_camera.py y buildozer.spec),
# asi el usuario puede sacar esos archivos a Drive, WhatsApp, email,
# etc. sin necesitar acceso root para llegar a la carpeta privada.

import os


def compartir_archivos(rutas, titulo="Compartir", tipo_mime="application/pdf"):
    """rutas: lista de rutas locales absolutas de archivos ya existentes.
    Devuelve True si se pudo lanzar el dialogo de compartir, False si no
    (por ejemplo si la lista viene vacia o algo falla)."""
    rutas = [r for r in rutas if r and os.path.exists(r)]
    if not rutas:
        return False

    try:
        from jnius import autoclass, cast
        from android import mActivity
    except Exception:
        return False

    try:
        Intent = autoclass("android.content.Intent")
        FileProviderJ = autoclass("androidx.core.content.FileProvider")
        File = autoclass("java.io.File")
        ArrayList = autoclass("java.util.ArrayList")
        Parcelable = autoclass("android.os.Parcelable")

        authority = mActivity.getPackageName() + ".fileprovider"
        uris = ArrayList()
        for ruta in rutas:
            archivo_java = File(ruta)
            uri = FileProviderJ.getUriForFile(mActivity, authority, archivo_java)
            uris.add(cast(Parcelable, uri))

        intent = Intent(Intent.ACTION_SEND_MULTIPLE)
        intent.setType(tipo_mime)
        intent.putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

        chooser = Intent.createChooser(intent, titulo)
        mActivity.startActivity(chooser)
        return True
    except Exception:
        return False
