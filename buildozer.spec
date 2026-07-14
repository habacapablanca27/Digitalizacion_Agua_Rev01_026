[app]
title = Digitalizacion del Agua
package.name = digitalizacionagua
package.domain = org.bohoral

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,csv,json
version = 1.0.0

requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,plyer,pyshp,fpdf2,pillow

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/assets/escudo.png

android.permissions = CAMERA,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,INTERNET

android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
