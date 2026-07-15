# main.py — Digitalización del Agua (app de campo)
# Sustituye al plugin QField cuando la cámara no conecta: aquí usamos
# plyer.camera, que llama directamente al intent nativo de la cámara de Android.

# ── CAPTURADOR DE ERRORES ──
# Se instala ANTES de cualquier otro import, para que cualquier fallo
# (incluso al importar kivy/plyer) quede registrado en un archivo que
# se pueda leer luego desde el propio móvil con un gestor de archivos,
# sin necesitar PC ni adb.
import sys
import traceback as _traceback
import time as _time
import os as _os


def _carpeta_crash_log():
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        return activity.getExternalFilesDir(None).getAbsolutePath()
    except Exception:
        return _os.path.expanduser("~")


def _log_crash(exc_type, exc_value, exc_tb):
    try:
        folder = _carpeta_crash_log()
        _os.makedirs(folder, exist_ok=True)
        ruta = _os.path.join(folder, "crash_log.txt")
        with open(ruta, "a", encoding="utf-8") as f:
            f.write("\n\n=== " + _time.strftime("%Y-%m-%d %H:%M:%S") + " ===\n")
            _traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _log_crash

try:
    with open(_os.path.join(_carpeta_crash_log(), "crash_log.txt"), "a", encoding="utf-8") as _f:
        _f.write("\n\n=== " + _time.strftime("%Y-%m-%d %H:%M:%S") + " === Arranque de la app iniciado\n")
except Exception:
    pass


def _log_debug(mensaje):
    """Registra un paso intermedio en debug_log.txt (no hace falta que haya
    un error para verlo; sirve para rastrear qué ocurre paso a paso)."""
    try:
        ruta = _os.path.join(_carpeta_crash_log(), "debug_log.txt")
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(_time.strftime("%Y-%m-%d %H:%M:%S") + " - " + str(mensaje) + "\n")
    except Exception:
        pass
# ── FIN CAPTURADOR DE ERRORES ──

import os
import shutil
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.metrics import dp
from kivy.clock import Clock

import data_store as ds
from export_shapefile import exportar_shapefile
from generar_ficha_pdf import generar_todas_las_fichas

try:
    from plyer import camera, gps
except Exception:
    camera = None
    gps = None

try:
    from android.permissions import request_permissions, Permission
    ANDROID = True
except Exception:
    ANDROID = False


def pedir_permisos():
    if ANDROID:
        request_permissions([
            Permission.CAMERA,
            Permission.ACCESS_FINE_LOCATION,
            Permission.ACCESS_COARSE_LOCATION,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
        ])


# ───────────────────────── PANTALLA: IMPORTAR PADRÓN ─────────────────────────

class PantallaImportar(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        root.add_widget(Label(text="Digitalización del Agua", font_size=dp(22),
                               size_hint_y=None, height=dp(40), bold=True))
        root.add_widget(Label(text="Importa el Padrón (CSV o Shapefile) para empezar,\n"
                                    "o continúa con los puntos ya cargados.",
                               size_hint_y=None, height=dp(50)))

        btn_importar = Button(text="Importar Padrón (CSV)", size_hint_y=None, height=dp(56))
        btn_importar.bind(on_release=lambda *_: self.abrir_selector("csv"))
        root.add_widget(btn_importar)

        btn_importar_shp = Button(text="Importar Shapefile (ZIP)", size_hint_y=None, height=dp(56))
        btn_importar_shp.bind(on_release=lambda *_: self.abrir_selector("shapefile"))
        root.add_widget(btn_importar_shp)

        btn_importar_qgs = Button(text="Importar capa desde carpeta QGIS (.qgs)", size_hint_y=None, height=dp(56))
        btn_importar_qgs.bind(on_release=lambda *_: self.abrir_selector_carpeta())
        root.add_widget(btn_importar_qgs)

        btn_continuar = Button(text="Ver puntos cargados", size_hint_y=None, height=dp(56))
        btn_continuar.bind(on_release=lambda *_: self.ir_a_lista())
        root.add_widget(btn_continuar)

        self.info = Label(text="", size_hint_y=None, height=dp(30))
        root.add_widget(self.info)
        root.add_widget(Label())  # relleno
        self.add_widget(root)

    def on_pre_enter(self):
        n = len(ds.cargar_puntos())
        self.info.text = f"Puntos cargados actualmente: {n}"

    def abrir_selector(self, tipo, *_):
        self._tipo_importacion = tipo
        _log_debug(f"Boton 'Importar' pulsado, tipo={tipo}")
        self.info.text = "Abriendo selector de archivos..."
        try:
            from plyer import filechooser
            if tipo == "csv":
                filtros = [["Archivos CSV", "*.csv"]]
            else:
                filtros = [["Archivos ZIP", "*.zip"]]
            _log_debug("plyer.filechooser importado correctamente, llamando a open_file")
            filechooser.open_file(on_selection=self._al_elegir_archivo, filters=filtros)
            _log_debug("Llamada a open_file() realizada sin excepcion")
        except Exception as e:
            _log_debug(f"EXCEPCION al abrir selector: {e!r}")
            self.info.text = f"No se pudo abrir el selector de archivos: {e}"

    def _al_elegir_archivo(self, seleccion):
        _log_debug(f"Callback on_selection recibido con: {seleccion!r}")
        if not seleccion:
            def avisar_vacio(_dt):
                self.info.text = "No se seleccionó ningún archivo (selección vacía)."
            Clock.schedule_once(avisar_vacio, 0)
            return
        ruta = seleccion[0]

        def hacer_importacion(_dt):
            _log_debug(f"Resolviendo ruta local para: {ruta!r}")
            ruta_local = _resolver_a_ruta_local(ruta)
            _log_debug(f"Ruta local resuelta: {ruta_local!r}")
            if ruta_local:
                self._importar(ruta_local)
            else:
                self.info.text = "No se pudo leer el archivo seleccionado."

        Clock.schedule_once(hacer_importacion, 0)

    def _importar(self, path):
        try:
            if getattr(self, "_tipo_importacion", "csv") == "shapefile":
                from importar_shapefile import importar_padron_shapefile_zip
                nuevos = importar_padron_shapefile_zip(path)
            else:
                nuevos = ds.importar_padron_csv(path)
            self._fusionar_e_importar(nuevos)
        except Exception as e:
            _log_debug(f"EXCEPCION al importar: {e!r}")
            self.info.text = f"Error al importar: {e}"

    def ir_a_lista(self):
        self.manager.current = "lista"

    # ---- importación desde carpeta de proyecto QGIS (.qgs), sin comprimir ----
    def abrir_selector_carpeta(self, *_):
        _log_debug("Boton 'Importar desde carpeta QGIS' pulsado")
        self.info.text = "Abriendo selector de carpeta..."
        try:
            from plyer import filechooser
            filechooser.choose_dir(on_selection=self._al_elegir_carpeta_qgis)
        except Exception as e:
            _log_debug(f"EXCEPCION al abrir selector de carpeta: {e!r}")
            self.info.text = f"No se pudo abrir el selector de carpetas: {e}"

    def _al_elegir_carpeta_qgis(self, seleccion):
        _log_debug(f"Carpeta seleccionada: {seleccion!r}")
        if not seleccion:
            def avisar(_dt):
                self.info.text = "No se seleccionó ninguna carpeta."
            Clock.schedule_once(avisar, 0)
            return
        tree_uri = seleccion[0]

        def procesar(_dt):
            self.info.text = "Leyendo la carpeta..."
            try:
                import android_saf
                from importar_shapefile import listar_capas_vectoriales_qgs

                archivos = android_saf.listar_archivos_carpeta(tree_uri)
                _log_debug(f"Archivos encontrados en la carpeta: {[a[0] for a in archivos]}")
                archivo_qgs = next((a for a in archivos if a[0].lower().endswith(".qgs")), None)
                if not archivo_qgs:
                    self.info.text = "No se encontró ningún archivo .qgs en esa carpeta."
                    return

                carpeta_tmp = os.path.join(ds.data_dir(), "qgis_tmp")
                os.makedirs(carpeta_tmp, exist_ok=True)
                ruta_qgs_local = os.path.join(carpeta_tmp, archivo_qgs[0])
                android_saf.copiar_uri_a_archivo(archivo_qgs[1], ruta_qgs_local)

                capas = listar_capas_vectoriales_qgs(ruta_qgs_local)
                if not capas:
                    self.info.text = "El proyecto QGIS no tiene capas vectoriales (shapefile)."
                    return

                self._archivos_carpeta = archivos
                self._carpeta_tree_uri = tree_uri
                self._mostrar_popup_capas(capas)
            except Exception as e:
                _log_debug(f"EXCEPCION al procesar carpeta QGIS: {e!r}")
                self.info.text = f"Error al leer la carpeta: {e}"

        Clock.schedule_once(procesar, 0)

    def _mostrar_popup_capas(self, capas):
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        scroll_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        scroll_layout.bind(minimum_height=scroll_layout.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(scroll_layout)
        box.add_widget(scroll)

        popup = Popup(title="Elige la capa a importar", content=box, size_hint=(0.9, 0.9))

        for capa in capas:
            btn = Button(text=capa["nombre"], size_hint_y=None, height=dp(50))
            btn.bind(on_release=lambda inst, c=capa: (popup.dismiss(), self._importar_capa_elegida(c)))
            scroll_layout.add_widget(btn)

        b_cancel = Button(text="Cancelar", size_hint_y=None, height=dp(48))
        b_cancel.bind(on_release=lambda *_: popup.dismiss())
        box.add_widget(b_cancel)
        popup.open()

    def _importar_capa_elegida(self, capa):
        self.info.text = f"Importando capa '{capa['nombre']}'..."
        try:
            import android_saf

            nombre_base = capa["archivo_shp"][:-4]  # sin ".shp"
            extensiones = (".shp", ".shx", ".dbf", ".prj", ".cpg")
            carpeta_tmp = os.path.join(ds.data_dir(), "qgis_tmp")

            copiados = 0
            for nombre_archivo, uri_archivo in self._archivos_carpeta:
                base, ext = os.path.splitext(nombre_archivo)
                if base == nombre_base and ext.lower() in extensiones:
                    android_saf.copiar_uri_a_archivo(
                        uri_archivo, os.path.join(carpeta_tmp, nombre_archivo)
                    )
                    copiados += 1
            _log_debug(f"Copiados {copiados} archivos de la capa '{nombre_base}'")

            from importar_shapefile import leer_puntos_desde_carpeta
            nuevos = leer_puntos_desde_carpeta(carpeta_tmp, nombre_shp=capa["archivo_shp"])
            self._fusionar_e_importar(nuevos)
        except Exception as e:
            _log_debug(f"EXCEPCION al importar capa elegida: {e!r}")
            self.info.text = f"Error al importar la capa: {e}"

    def _fusionar_e_importar(self, nuevos):
        existentes = ds.cargar_puntos()
        claves_existentes = set()
        for p in existentes:
            if p.get("NFijo"):
                claves_existentes.add(("nfijo", p["NFijo"]))
            elif p.get("RefCatastral"):
                claves_existentes.add(("ref", p["RefCatastral"]))

        agregados = 0
        for p in nuevos:
            if p.get("NFijo") and ("nfijo", p["NFijo"]) in claves_existentes:
                continue
            if p.get("RefCatastral") and ("ref", p["RefCatastral"]) in claves_existentes:
                continue
            existentes.append(p)
            agregados += 1
        for i, p in enumerate(existentes):
            p["_id"] = i
        ds.guardar_puntos(existentes)
        self.info.text = f"Importados {agregados} puntos nuevos ({len(nuevos)} en la capa)."


def _resolver_a_ruta_local(ruta):
    """En Android, el selector nativo puede devolver una URI 'content://' en
    vez de una ruta de archivo normal. La copiamos a un archivo temporal
    dentro de la carpeta privada de la app para poder abrirla con open()."""
    if not ruta:
        return None
    if not str(ruta).startswith("content://"):
        return ruta if os.path.exists(ruta) else None
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Uri = autoclass("android.net.Uri")
        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        uri = Uri.parse(ruta)
        entrada = resolver.openInputStream(uri)

        destino = os.path.join(ds.data_dir(), "padron_importado.csv")
        buffer_java = bytearray(4096)
        with open(destino, "wb") as salida:
            while True:
                leido = entrada.read(buffer_java)
                if leido == -1:
                    break
                salida.write(bytes(buffer_java[:leido]))
        entrada.close()
        return destino
    except Exception:
        return None


# ───────────────────────── PANTALLA: LISTA DE PUNTOS ─────────────────────────

class PantallaLista(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        cab = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        b_atras = Button(text="←", size_hint_x=None, width=dp(48))
        b_atras.bind(on_release=lambda *_: setattr(self.manager, "current", "importar"))
        cab.add_widget(b_atras)
        cab.add_widget(Label(text="Puntos pendientes / capturados"))
        root.add_widget(cab)

        self.scroll_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.scroll_layout.bind(minimum_height=self.scroll_layout.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.scroll_layout)
        root.add_widget(scroll)

        acciones = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        b_shp = Button(text="Exportar Shapefile")
        b_shp.bind(on_release=self.exportar_shp)
        b_pdf = Button(text="Generar Fichas PDF")
        b_pdf.bind(on_release=self.generar_pdfs)
        acciones.add_widget(b_shp)
        acciones.add_widget(b_pdf)
        root.add_widget(acciones)

        self.estado = Label(text="", size_hint_y=None, height=dp(30))
        root.add_widget(self.estado)
        self.add_widget(root)

    def on_pre_enter(self):
        self.refrescar()

    def refrescar(self):
        self.scroll_layout.clear_widgets()
        for p in ds.cargar_puntos():
            estado_txt = "[OK]" if p.get("Completado") else "[...]"
            fila = Button(
                text=f"{estado_txt}  {p.get('NFijo','')}  —  {p.get('Direccion','(sin dirección)')}",
                size_hint_y=None, height=dp(52), halign="left",
            )
            fila.bind(on_release=lambda inst, punto=p: self.abrir_ficha(punto))
            self.scroll_layout.add_widget(fila)

    def abrir_ficha(self, punto):
        pantalla_ficha = self.manager.get_screen("ficha")
        pantalla_ficha.cargar_punto(punto)
        self.manager.current = "ficha"

    def exportar_shp(self, *_):
        puntos = ds.cargar_puntos()
        if not puntos:
            self.estado.text = "No hay puntos para exportar."
            return
        carpeta = exportar_shapefile(puntos)
        self.estado.text = f"Shapefile guardado en:\n{carpeta}"

    def generar_pdfs(self, *_):
        puntos = [p for p in ds.cargar_puntos() if p.get("Completado")]
        if not puntos:
            self.estado.text = "No hay fichas completadas todavia."
            return
        carpeta = os.path.join(ds.data_dir(), "fichas_pdf")
        generar_todas_las_fichas(puntos, carpeta)
        self.estado.text = f"{len(puntos)} fichas PDF generadas en:\n{carpeta}"


# ───────────────────────── PANTALLA: FICHA DE CAMPO ─────────────────────────

CALIBRES = ["", "13-A", "15-A", "13/15-A", "20-B", "25-C", "30-D", "32-D", "40-E",
            "50-F", "65-G", "80-H", "100-I", "125-J", "150-K", "200-L", "250-M",
            "300-N", "400-O", "500-P"]
DIAMETROS = ["", "DN16", "DN20", "DN25", "DN32", "DN40", "DN50", "DN63", "DN75",
             "DN90", "DN110", "DN125", "DN140", "DN160", "DN180", "DN200",
             "DN225", "DN250", "DN280", "DN315", "DN355", "DN400", "DN450", "DN500"]
ALOJAMIENTOS = ["", "Suelo", "Pared", "Hornacina"]
TIPOS_EDIF = ["", "Vivienda unifamiliar", "Viviendas en bloque", "Local comercial",
              "Local institucional", "Industria", "Otros"]
TIPOS_USO = ["", "Doméstico", "Institucional", "Comercial", "Industrial", "Otros"]

CAMPOS_FOTO = [("FotoSituacion", "Situación"), ("FotoInmueble", "Inmueble"),
               ("FotoContador", "Contador"), ("FotoArqueta", "Arqueta")]


class PantallaFicha(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.punto = None
        self.inputs = {}
        self.foto_widgets = {}

        root = BoxLayout(orientation="vertical")
        cab = BoxLayout(size_hint_y=None, height=dp(48), padding=(dp(8), 0), spacing=dp(8))
        b_atras = Button(text="←", size_hint_x=None, width=dp(48))
        b_atras.bind(on_release=self.volver)
        cab.add_widget(b_atras)
        self.titulo = Label(text="Ficha de campo")
        cab.add_widget(self.titulo)
        root.add_widget(cab)

        scroll = ScrollView()
        self.form = GridLayout(cols=2, size_hint_y=None, spacing=dp(6), padding=dp(10))
        self.form.bind(minimum_height=self.form.setter("height"))
        scroll.add_widget(self.form)
        root.add_widget(scroll)

        acciones = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8), padding=(dp(8), dp(4)))
        b_gps = Button(text="Capturar GPS")
        b_gps.bind(on_release=self.capturar_gps)
        b_guardar = Button(text="Guardar")
        b_guardar.bind(on_release=self.guardar)
        acciones.add_widget(b_gps)
        acciones.add_widget(b_guardar)
        root.add_widget(acciones)

        self.estado = Label(text="", size_hint_y=None, height=dp(24))
        root.add_widget(self.estado)
        self.add_widget(root)

    def cargar_punto(self, punto):
        self.punto = punto
        self.titulo.text = f"{punto.get('NFijo','')} — {punto.get('Direccion','')}"
        self.form.clear_widgets()
        self.inputs = {}
        self.foto_widgets = {}
        self.estado.text = ""

        self._solo_lectura("Nº Fijo", punto.get("NFijo", ""))
        self._solo_lectura("Dirección", punto.get("Direccion", ""))
        self._solo_lectura("Ref. Catastral", punto.get("RefCatastral", ""))

        self._spinner("TipEdifica", "Tipo de edificación", TIPOS_EDIF)
        self._texto("NContador", "Nº Contador")
        self._texto("NSerieCont", "Nº Serie contador")
        self._texto("ModRadio", "Módulo Radio")
        self._texto("MarcaModel", "Marca / Modelo")
        self._texto("Lectura", "Lectura (m³)")
        self._texto("FecLectura", "Fecha lectura",
                    valor_defecto=datetime.now().strftime("%d/%m/%Y %H:%M"))
        self._spinner("Alojamiento", "Alojamiento", ALOJAMIENTOS)
        self._spinner("Calibre", "Calibre", CALIBRES)
        self._spinner("Diametros", "Diámetros", DIAMETROS)
        self._spinner("TipUsoComu", "Tipo de uso/consumo", TIPOS_USO)

        self._checkbox("Exterior", "Exterior")
        self._checkbox("Interior", "Interior")
        self._checkbox("UbicarExte", "Ubicar exterior")
        self._checkbox("ValAcometi", "Válvula de acometida")
        self._checkbox("Individual", "Individual")
        self._checkbox("LlaveContador", "Llave de contador")
        self._checkbox("CambioTapa", "Cambio de tapa")
        self._checkbox("SeBorra", "Se borra")

        self._texto("CoordGPS", "Coordenadas GPS (o pulsa Capturar GPS)")
        self._texto("Observaciones", "Observaciones")

        self.form.add_widget(Label(text="Fotografías", size_hint_y=None, height=dp(34)))
        self.form.add_widget(Label(text="", size_hint_y=None, height=dp(34)))
        for campo, etiqueta in CAMPOS_FOTO:
            self._foto(campo, etiqueta)

        for campo, valor in punto.items():
            if campo in self.inputs:
                w = self.inputs[campo]
                if isinstance(w, CheckBox):
                    w.active = bool(valor)
                elif isinstance(w, Spinner) and valor:
                    w.text = valor
                elif isinstance(w, TextInput) and valor:
                    w.text = str(valor)

    # -- helpers de construcción de formulario --
    def _fila(self, etiqueta, widget):
        self.form.add_widget(Label(text=etiqueta, size_hint_y=None, height=dp(40),
                                    halign="left", valign="middle"))
        widget.size_hint_y = None
        widget.height = dp(40)
        self.form.add_widget(widget)

    def _solo_lectura(self, etiqueta, valor):
        self._fila(etiqueta, Label(text=valor or "—"))

    def _texto(self, campo, etiqueta, valor_defecto=""):
        ti = TextInput(text=valor_defecto, multiline=False)
        self.inputs[campo] = ti
        self._fila(etiqueta, ti)

    def _spinner(self, campo, etiqueta, opciones):
        sp = Spinner(text=opciones[0], values=opciones)
        self.inputs[campo] = sp
        self._fila(etiqueta, sp)

    def _checkbox(self, campo, etiqueta):
        box = BoxLayout(size_hint_y=None, height=dp(40))
        cb = CheckBox()
        self.inputs[campo] = cb
        box.add_widget(cb)
        box.add_widget(Label(text=etiqueta))
        self.form.add_widget(Label(text="", size_hint_y=None, height=dp(40)))
        self.form.add_widget(box)

    def _foto(self, campo, etiqueta):
        cont = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(140), spacing=dp(4))
        img = Image(size_hint_y=None, height=dp(90))
        btn = Button(text=f"Foto: {etiqueta}", size_hint_y=None, height=dp(44))
        btn.bind(on_release=lambda *_: self._tomar_foto(campo, img))
        cont.add_widget(img)
        cont.add_widget(btn)
        self.foto_widgets[campo] = img
        self.form.add_widget(Label(text="", size_hint_y=None, height=dp(140)))
        self.form.add_widget(cont)

    # -- cámara y GPS --
    def _tomar_foto(self, campo, img_widget):
        if camera is None:
            self.estado.text = "Camara no disponible en este dispositivo/emulador."
            return
        destino = os.path.join(ds.photos_dir(), f"{self.punto['_id']}_{campo}.jpg")
        try:
            camera.take_picture(filename=destino, on_complete=lambda path: self._foto_lista(campo, img_widget, path))
        except Exception as e:
            self.estado.text = f"Error de camara: {e}"

    def _foto_lista(self, campo, img_widget, path):
        def actualizar(_dt):
            if path and os.path.exists(path):
                self.punto[campo] = path
                img_widget.source = path
                img_widget.reload()
                self.estado.text = f"Foto {campo} capturada."
            else:
                self.estado.text = "No se recibio la foto (cancelada)."
        Clock.schedule_once(actualizar, 0)

    def capturar_gps(self, *_):
        if gps is None:
            self.estado.text = "GPS no disponible en este dispositivo/emulador."
            return
        try:
            gps.configure(on_location=self._gps_recibido)
            gps.start(minTime=1000, minDistance=0)
            self.estado.text = "Buscando senal GPS..."
        except Exception as e:
            self.estado.text = f"Error de GPS: {e}"

    def _gps_recibido(self, **kwargs):
        lat = kwargs.get("lat")
        lon = kwargs.get("lon")
        if lat is not None and lon is not None:
            def actualizar(_dt):
                self.inputs["CoordGPS"].text = f"{lat}, {lon}"
                self.estado.text = "GPS capturado."
            Clock.schedule_once(actualizar, 0)
            try:
                gps.stop()
            except Exception:
                pass

    def guardar(self, *_):
        if not self.punto:
            return
        for campo, widget in self.inputs.items():
            if isinstance(widget, CheckBox):
                self.punto[campo] = widget.active
            elif isinstance(widget, Spinner):
                self.punto[campo] = widget.text if widget.text != widget.values[0] else ""
            elif isinstance(widget, TextInput):
                self.punto[campo] = widget.text
        self.punto["Completado"] = True
        ds.actualizar_punto(self.punto)
        self.estado.text = "Guardado correctamente."

    def volver(self, *_):
        self.manager.current = "lista"
        self.manager.get_screen("lista").refrescar()


# ───────────────────────── APP ─────────────────────────

class DigitalizacionAguaApp(App):
    def build(self):
        pedir_permisos()
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(PantallaImportar(name="importar"))
        sm.add_widget(PantallaLista(name="lista"))
        sm.add_widget(PantallaFicha(name="ficha"))
        return sm


if __name__ == "__main__":
    DigitalizacionAguaApp().run()
