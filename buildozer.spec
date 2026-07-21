[app]
title = Digitalizacion del Agua
package.name = digitalizacionagua
package.domain = org.bohoral

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,csv,json
version = 1.0.0

requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,plyer,pyshp,requests

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/assets/escudo.png

android.permissions = CAMERA,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET

android.api = 34
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True

# Necesario para poder usar androidx.core.content.FileProvider (arregla
# la camara: ver android_camera.py). android.enable_androidx requiere
# android.api >= 28, y ya estamos en 34.
android.enable_androidx = True
android.gradle_dependencies = androidx.core:core:1.12.0

# Declara el <provider> del FileProvider dentro de <application> del
# manifest (buildozer/p4a no tienen una opcion directa para "provider",
# por eso se inyecta como XML crudo).
android.extra_manifest_application_arguments = %(source.dir)s/src/android/extra_manifest_application_arguments.xml

# Copia file_paths.xml (que dice que carpetas puede exponer el FileProvider)
# a res/xml/ dentro del proyecto Android generado.
android.add_resources = %(source.dir)s/src/android/res/xml/file_paths.xml:xml/file_paths.xml

[buildozer]
log_level = 2
warn_on_root = 1
