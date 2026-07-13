# Digitalización del Agua — App de campo (Kivy)

App independiente para Android que sustituye al plugin QField cuando la
cámara no conecta. Permite:

- Importar el Padrón (CSV) con los puntos pendientes.
- Rellenar la ficha de cada punto (contador, lectura, características,
  ubicación, accesos, observaciones).
- Tomar las 4 fotos (Situación, Inmueble, Contador, Arqueta) con la
  cámara nativa del móvil (vía `plyer.camera`, no la cámara interna de QField).
- Capturar coordenadas GPS reales del punto.
- Exportar todo a **Shapefile** (.shp/.shx/.dbf/.prj) listo para QGIS.
- Generar una **ficha PDF por punto**, con el mismo diseño que
  `Ficha_Modelo_Valle_de_Valdebezana.xlsx` (escudo, SOMACyL, fotos, datos).

## Estructura del proyecto

```
digitalizacion_agua_app/
├── main.py                  ← app Kivy (pantallas, cámara, GPS)
├── data_store.py             ← import CSV, guardado local en JSON
├── export_shapefile.py       ← exportación a Shapefile (pyshp puro Python)
├── generar_ficha_pdf.py      ← genera el PDF de cada ficha
├── buildozer.spec            ← configuración de compilación Android
├── assets/
│   ├── escudo.png             ← escudo del ayuntamiento (de tu ficha modelo)
│   └── somacyl.png            ← logo SOMACyL (de tu ficha modelo)
└── .github/workflows/build.yml  ← compila el APK automáticamente en GitHub
```

## Cómo compilar el APK con GitHub Actions (sin instalar nada en tu PC)

1. **Crea un repositorio nuevo** en GitHub (puede ser privado).
2. Sube **todo el contenido de esta carpeta** tal cual (respetando la
   estructura, incluida la carpeta oculta `.github/`).
   - Más fácil vía web: "Add file → Upload files" y arrastras todo.
   - O por git:
     ```bash
     cd digitalizacion_agua_app
     git init
     git add .
     git commit -m "App digitalización del agua"
     git branch -M main
     git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
     git push -u origin main
     ```
3. En cuanto hagas push a `main`, GitHub Actions empieza a compilar
   solo (lo ves en la pestaña **Actions** del repo). La primera vez
   tarda bastante (~20-40 min porque descarga el SDK/NDK de Android);
   las siguientes veces es más rápido gracias a la caché.
4. Cuando termine (icono verde ✔), entra en esa ejecución → apartado
   **Artifacts** → descarga `digitalizacion-agua-apk` (es un .zip que
   contiene el `.apk`).
5. Pasa el `.apk` a tu móvil (Drive, USB, etc.), activa "Instalar de
   orígenes desconocidos" en Ajustes → Seguridad, y ábrelo para instalar.

Si algo falla en la compilación, la pestaña Actions te muestra el log
completo del error — pégamelo y lo revisamos.

## Formato esperado del CSV del Padrón

El importador reconoce variaciones típicas de cabecera, pero lo ideal
es un CSV con columnas (separador `;` o `,`):

```
NFijo;Direccion;NOrden;CATVia;RefCatastral;Lat;Lon
1;CL MAYOR 5;10;V001;1234567AB;42.912;-3.456
```

Si tu Padrón no trae Lat/Lon precargadas, no pasa nada: la app usa la
coordenada GPS que captures en campo para geolocalizar el punto en el
Shapefile.

## Notas y limitaciones conocidas

- **Cámara/GPS solo funcionan en un móvil Android real** (o emulador
  con cámara/GPS configurados) — no hay forma de probarlos en un PC.
- El diseño del PDF replica tu ficha modelo, pero con datos muy largos
  en "Observaciones" el texto puede recortarse si no cabe en el hueco;
  avísame si ves algún caso así y ajusto el tamaño de letra o el alto
  de la caja.
- `android.ndk = 25b` y `android.api = 34` en `buildozer.spec` son
  valores estables actuales; si GitHub Actions falla por versión de NDK,
  dímelo y lo ajusto.
