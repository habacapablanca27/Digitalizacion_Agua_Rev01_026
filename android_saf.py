# android_saf.py
# Cuando el usuario selecciona una CARPETA en Android (en vez de subir un
# .zip), Android no entrega una ruta de archivo normal: entrega una "URI de
# árbol" (content://...tree/...) gestionada por el sistema (Storage Access
# Framework). Este módulo lista los archivos de esa carpeta y los copia a
# la carpeta privada de la app usando solo clases estándar de Android
# (android.provider.DocumentsContract), sin depender de AndroidX
# (evita añadir dependencias nuevas al build, que ya ha dado bastantes
# sorpresas en este proyecto).

import os


def listar_archivos_carpeta(tree_uri_str):
    """Devuelve una lista de (nombre_archivo, uri_documento_str) con los
    archivos de primer nivel dentro de la carpeta seleccionada."""
    from jnius import autoclass

    DocumentsContract = autoclass("android.provider.DocumentsContract")
    Document = autoclass("android.provider.DocumentsContract$Document")
    Uri = autoclass("android.net.Uri")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")

    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()

    tree_uri = Uri.parse(tree_uri_str)
    doc_id = DocumentsContract.getTreeDocumentId(tree_uri)
    hijos_uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree_uri, doc_id)

    columnas = [Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME]
    cursor = resolver.query(hijos_uri, columnas, None, None, None)
    resultados = []
    if cursor is not None:
        try:
            idx_id = cursor.getColumnIndex(Document.COLUMN_DOCUMENT_ID)
            idx_nombre = cursor.getColumnIndex(Document.COLUMN_DISPLAY_NAME)
            while cursor.moveToNext():
                doc_id_hijo = cursor.getString(idx_id)
                nombre = cursor.getString(idx_nombre)
                uri_hijo = DocumentsContract.buildDocumentUriUsingTree(tree_uri, doc_id_hijo)
                resultados.append((nombre, uri_hijo.toString()))
        finally:
            cursor.close()
    return resultados


def copiar_uri_a_archivo(uri_str, destino_path):
    """Copia el contenido de una content:// URI a un archivo local normal."""
    from jnius import autoclass

    Uri = autoclass("android.net.Uri")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()

    uri = Uri.parse(uri_str)
    entrada = resolver.openInputStream(uri)
    buffer_java = bytearray(8192)
    os.makedirs(os.path.dirname(destino_path), exist_ok=True)
    with open(destino_path, "wb") as salida:
        while True:
            leido = entrada.read(buffer_java)
            if leido == -1:
                break
            salida.write(bytes(buffer_java[:leido]))
    entrada.close()
    return destino_path
