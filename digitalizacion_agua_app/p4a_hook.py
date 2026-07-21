# p4a_hook.py
# Hook de compilacion de python-for-android (ver buildozer.spec: p4a.hook).
#
# Se probo primero con "android.extra_manifest_application_arguments" para
# declarar el <provider> del FileProvider, pero esa opcion de buildozer
# resulto poco fiable: en la build real dejo el AndroidManifest.xml mal
# formado (fallo de Gradle en processDebugMainManifest: "Error parsing
# AndroidManifest.xml").
#
# Alternativa mas robusta (confirmada por otros desarrolladores para este
# mismo caso -- ver issues de python-for-android sobre FileProvider):
# editar directamente el AndroidManifest.xml ya generado por p4a, justo
# antes de que Gradle lo compile ("before_apk_assemble"), insertando el
# <provider> con una simple sustitucion de texto antes de "</application>".

from pathlib import Path

PROVEEDOR_XML = """
    <provider
        android:name="androidx.core.content.FileProvider"
        android:authorities="${applicationId}.fileprovider"
        android:exported="false"
        android:grantUriPermissions="true">
        <meta-data
            android:name="android.support.FILE_PROVIDER_PATHS"
            android:resource="@xml/file_paths" />
    </provider>
"""


def before_apk_assemble(toolchain):
    manifest_path = Path(toolchain._dist.dist_dir) / "src" / "main" / "AndroidManifest.xml"

    if not manifest_path.exists():
        print(f"[p4a_hook] AVISO: no se encontro {manifest_path}, no se pudo insertar el FileProvider.")
        return

    contenido = manifest_path.read_text(encoding="utf-8")

    if "androidx.core.content.FileProvider" in contenido:
        print("[p4a_hook] El FileProvider ya estaba en el manifest, no se toca de nuevo.")
        return

    if "</application>" not in contenido:
        print("[p4a_hook] AVISO: no se encontro '</application>' en el manifest, no se pudo insertar el FileProvider.")
        return

    nuevo_contenido = contenido.replace("</application>", PROVEEDOR_XML + "    </application>")
    manifest_path.write_text(nuevo_contenido, encoding="utf-8")
    print("[p4a_hook] FileProvider insertado correctamente en AndroidManifest.xml")
