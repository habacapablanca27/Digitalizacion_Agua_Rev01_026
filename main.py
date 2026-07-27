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
import copy
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
from kivy.uix.image import Image, AsyncImage
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import ObjectProperty, NumericProperty

import data_store as ds
from export_shapefile import exportar_shapefile
from generar_ficha_pdf import generar_todas_las_fichas

try:
    from plyer import camera, gps
except Exception:
    camera = None
    gps = None

try:
    import android_camera
except Exception:
    android_camera = None

try:
    import android_compartir
except Exception:
    android_compartir = None

try:
    import android_adjuntar
except Exception:
    android_adjuntar = None

try:
    import android_filepicker
except Exception:
    android_filepicker = None

try:
    from plantilla_excel import leer_plantilla_excel
except Exception:
    leer_plantilla_excel = None

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

        # El botón de "carpeta QGIS" se quitó temporalmente: usa un mecanismo
        # de Android (elegir carpeta) que no está respondiendo bien y podía
        # dejar la app esperando una respuesta que nunca llega. Usa el ZIP
        # mientras tanto (hace lo mismo, incluida la selección de capas).

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
            from android_filepicker import elegir_archivo
            _log_debug("android_filepicker importado correctamente, llamando a elegir_archivo")
            elegir_archivo(self._al_elegir_archivo)
            _log_debug("Llamada a elegir_archivo() realizada sin excepcion")
        except Exception as e:
            _log_debug(f"EXCEPCION al abrir selector: {e!r}")
            self.info.text = f"No se pudo abrir el selector de archivos: {e}"

    def _al_elegir_archivo(self, ruta_local):
        _log_debug(f"Callback de seleccion recibido con: {ruta_local!r}")

        def continuar(_dt):
            if not ruta_local:
                self.info.text = "No se seleccionó ningún archivo (selección vacía o cancelada)."
                return
            self._importar(ruta_local)

        Clock.schedule_once(continuar, 0)

    def _importar(self, path):
        try:
            if getattr(self, "_tipo_importacion", "csv") == "shapefile":
                self._importar_zip_con_capas(path)
            else:
                nuevos = ds.importar_padron_csv(path)
                self._fusionar_e_importar(nuevos)
        except Exception as e:
            _log_debug(f"EXCEPCION al importar: {e!r}")
            self.info.text = f"Error al importar: {e}"

    def _importar_zip_con_capas(self, ruta_zip):
        """Si el .zip trae un proyecto .qgs con varias capas, deja elegir
        cuál importar (igual que en QGIS). Si no, importa el único .shp
        que encuentre (comportamiento anterior)."""
        from importar_shapefile import listar_capas_de_zip, leer_puntos_desde_carpeta

        carpeta, capas = listar_capas_de_zip(ruta_zip)
        if capas:
            self._carpeta_zip_actual = carpeta
            self._mostrar_popup_capas(capas, origen="zip")
        else:
            nuevos = leer_puntos_desde_carpeta(carpeta)
            self._fusionar_e_importar(nuevos)

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

    def _mostrar_popup_capas(self, capas, origen="carpeta"):
        self._todas_las_capas_disponibles = capas
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(Label(
            text="Elige la capa que tiene los contadores (puntos) a digitalizar",
            size_hint_y=None, height=dp(40)))

        scroll_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        scroll_layout.bind(minimum_height=scroll_layout.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(scroll_layout)
        box.add_widget(scroll)

        popup = Popup(title="Elige la capa a importar (puntos)", content=box, size_hint=(0.9, 0.9))

        # Selección única (como un grupo de radio-botones): marcar una
        # casilla desmarca automáticamente las demás, porque solo se
        # puede importar UNA capa de puntos a la vez.
        checks = []

        def _marcar_solo_esta(cb_elegida, *_):
            if not cb_elegida.active:
                return
            for cb, _capa in checks:
                if cb is not cb_elegida:
                    cb.active = False

        for capa in capas:
            fila = BoxLayout(size_hint_y=None, height=dp(48))
            cb = CheckBox(size_hint_x=None, width=dp(44))
            cb.bind(active=_marcar_solo_esta)
            fila.add_widget(cb)
            lbl = Label(text=capa["nombre"], halign="left", valign="middle", shorten=True, shorten_from="right")
            lbl.bind(size=lambda inst, tam: setattr(inst, "text_size", tam))
            fila.add_widget(lbl)
            scroll_layout.add_widget(fila)
            checks.append((cb, capa))

        def continuar(*_):
            elegidas = [capa for cb, capa in checks if cb.active]
            if not elegidas:
                self.info.text = "Elige una capa antes de continuar."
                return
            capa = elegidas[0]
            popup.dismiss()
            if origen == "zip":
                self._importar_capa_de_zip_elegida(capa)
            else:
                self._importar_capa_elegida(capa)

        def cancelar(*_):
            popup.dismiss()

        fila_botones = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        b_cancelar = Button(text="Cancelar")
        b_cancelar.bind(on_release=cancelar)
        b_continuar = Button(text="Continuar")
        b_continuar.bind(on_release=continuar)
        fila_botones.add_widget(b_cancelar)
        fila_botones.add_widget(b_continuar)
        box.add_widget(fila_botones)
        popup.open()

    def _importar_capa_de_zip_elegida(self, capa):
        self.info.text = f"Importando capa '{capa['nombre']}'..."
        try:
            from importar_shapefile import leer_puntos_desde_carpeta
            nuevos = leer_puntos_desde_carpeta(self._carpeta_zip_actual, nombre_shp=capa["archivo_shp"])
            _log_debug(f"Capa de puntos '{capa['nombre']}' leida: {len(nuevos)} puntos")
            self._fusionar_e_importar(nuevos)
            restantes = [c for c in self._todas_las_capas_disponibles
                         if c["archivo_shp"] != capa["archivo_shp"]]
            _log_debug(f"Capas de fondo disponibles para elegir: {[c['nombre'] for c in restantes]}")
            if restantes:
                self._mostrar_popup_capas_fondo(restantes, self._carpeta_zip_actual)
        except Exception as e:
            _log_debug(f"EXCEPCION al importar capa de zip: {e!r}")
            self.info.text = f"Error al importar la capa: {e}"

    def _mostrar_popup_capas_fondo(self, capas_restantes, carpeta):
        """Deja elegir qué otras capas (parcelas, límite, construcciones...)
        se ven de fondo en el mapa, como referencia visual (no editables)."""
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(Label(
            text="¿Qué otras capas quieres ver de fondo en el mapa?\n(elige pocas para que el mapa no vaya lento)",
            size_hint_y=None, height=dp(60)))

        fila_todas = BoxLayout(size_hint_y=None, height=dp(40))
        cb_todas = CheckBox(size_hint_x=None, width=dp(44))
        fila_todas.add_widget(cb_todas)
        fila_todas.add_widget(Label(text="Seleccionar todas", bold=True))
        box.add_widget(fila_todas)

        scroll_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        scroll_layout.bind(minimum_height=scroll_layout.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(scroll_layout)
        box.add_widget(scroll)

        checks = []
        for capa in capas_restantes:
            fila = BoxLayout(size_hint_y=None, height=dp(44))
            cb = CheckBox(size_hint_x=None, width=dp(44))
            fila.add_widget(cb)
            # Con nombres de capa largos, un Label sin limite de ancho se
            # dibuja centrado en su hueco y se desborda tapando el propio
            # checkbox. Con text_size fijado al ancho real de la fila (y
            # "shorten" para acortar con "…" si aun asi no cabe), el
            # texto queda siempre DESPUES del checkbox y legible.
            lbl = Label(text=capa["nombre"], halign="left", valign="middle", shorten=True, shorten_from="right")
            lbl.bind(size=lambda inst, tam: setattr(inst, "text_size", tam))
            fila.add_widget(lbl)
            scroll_layout.add_widget(fila)
            checks.append((cb, capa))

        _actualizando_todas = {"en_curso": False}

        def _marcar_todas(_inst, activo):
            if _actualizando_todas["en_curso"]:
                return
            _actualizando_todas["en_curso"] = True
            for cb, _capa in checks:
                cb.active = activo
            _actualizando_todas["en_curso"] = False

        cb_todas.bind(active=_marcar_todas)

        popup = Popup(title="Capas de fondo (opcional)", content=box, size_hint=(0.9, 0.9))

        def continuar(*_):
            elegidas = [capa for cb, capa in checks if cb.active]
            popup.dismiss()
            self._cargar_capas_fondo(carpeta, elegidas)

        def cancelar(*_):
            popup.dismiss()

        def atras(*_):
            # Por si se eligió la capa de puntos equivocada en el paso
            # anterior: vuelve a ese paso sin tener que cancelar todo el
            # proceso de importación desde el principio.
            popup.dismiss()
            self._mostrar_popup_capas(self._todas_las_capas_disponibles, origen="zip")

        fila_botones = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        b_atras = Button(text="Atrás")
        b_atras.bind(on_release=atras)
        b_cancelar = Button(text="Cancelar")
        b_cancelar.bind(on_release=cancelar)
        b_continuar = Button(text="Continuar")
        b_continuar.bind(on_release=continuar)
        fila_botones.add_widget(b_atras)
        fila_botones.add_widget(b_cancelar)
        fila_botones.add_widget(b_continuar)
        box.add_widget(fila_botones)
        popup.open()

    def _cargar_capas_fondo(self, carpeta, capas_elegidas):
        if not capas_elegidas:
            return
        self.info.text = "Cargando capas de fondo..."
        _log_debug(f"Cargando capas de fondo elegidas: {[c['nombre'] for c in capas_elegidas]}")
        try:
            from importar_shapefile import guardar_capas_fondo
            ruta_salida = os.path.join(ds.data_dir(), "capas_fondo.json")
            resultado = guardar_capas_fondo(carpeta, capas_elegidas, ruta_salida)
            for capa in resultado:
                _log_debug(
                    f"  Capa '{capa['nombre']}': tipo={capa['tipo']}, "
                    f"anillos={len(capa['anillos'])}, trazos={capa['trazos']}, "
                    f"etiquetas={len(capa.get('etiquetas', []))}"
                )
            nombres_guardados = {c["nombre"] for c in resultado}
            for capa in capas_elegidas:
                if capa["nombre"] not in nombres_guardados:
                    _log_debug(f"  AVISO: la capa '{capa['nombre']}' se eligio pero no se guardo (sin geometria valida?)")
            self.info.text = "Capas de fondo listas. Ya se verán en el mapa."
        except Exception as e:
            _log_debug(f"EXCEPCION al cargar capas de fondo: {e!r}")
            self.info.text = f"No se pudieron cargar las capas de fondo: {e}"

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
        b_mapa = Button(text="Ver mapa", size_hint_x=None, width=dp(100))
        b_mapa.bind(on_release=lambda *_: setattr(self.manager, "current", "mapa"))
        cab.add_widget(b_mapa)
        root.add_widget(cab)

        self.buscador = TextInput(
            hint_text="Buscar por dirección (ej. CL MAYOR)...",
            multiline=False, size_hint_y=None, height=dp(44),
        )
        self.buscador.bind(text=lambda _inst, texto: self.refrescar(texto))
        root.add_widget(self.buscador)

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

        acciones2 = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        b_compartir = Button(text="Compartir PDFs")
        b_compartir.bind(on_release=self.compartir_pdfs)
        b_config = Button(text="Plantilla a utilizar", size_hint_x=None, width=dp(180))
        b_config.bind(on_release=self.abrir_config_ficha)
        acciones2.add_widget(b_config)
        acciones2.add_widget(b_compartir)
        root.add_widget(acciones2)

        self.estado = Label(text="", size_hint_y=None, height=dp(30))
        root.add_widget(self.estado)
        self.add_widget(root)

    def on_pre_enter(self):
        self.refrescar(self.buscador.text if hasattr(self, "buscador") else "")

    def refrescar(self, filtro_texto=""):
        self.scroll_layout.clear_widgets()
        filtro_texto = (filtro_texto or "").strip().lower()
        for p in ds.cargar_puntos():
            if filtro_texto and filtro_texto not in (p.get("Direccion", "") or "").lower():
                continue
            estado_txt = "[OK]" if p.get("Completado") else "[...]"
            fila = Button(
                text=f"{estado_txt}  {p.get('NFijo','')}  —  {p.get('Direccion','(sin dirección)')}",
                size_hint_y=None, height=dp(52), halign="left",
            )
            # Mismo color que ya usan los marcadores del mapa (y que
            # venía definido en las reglas de QGIS): rojo = pendiente,
            # verde = completado, magenta = marcado para borrar.
            if p.get("SeBorra"):
                fila.background_color = (0.85, 0.25, 0.75, 1)
            elif p.get("Completado"):
                fila.background_color = (0.25, 0.65, 0.3, 1)
            else:
                fila.background_color = (0.65, 0.3, 0.3, 1)
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

    def abrir_config_ficha(self, *_):
        cfg = ds.cargar_configuracion()
        cont = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        cont.add_widget(Label(
            text="Elige el Excel modelo ya preparado (con el escudo/nombre\n"
                 "de tu municipio) y se rellena todo solo.",
            size_hint_y=None, height=dp(44),
        ))

        b_elegir = Button(text="Elegir plantilla Excel…", size_hint_y=None, height=dp(44))
        cont.add_widget(b_elegir)

        cont.add_widget(Label(text="Municipio (Ayuntamiento de...)", size_hint_y=None, height=dp(20)))
        in_municipio = TextInput(text=cfg["municipio"], multiline=False, size_hint_y=None, height=dp(40))
        cont.add_widget(in_municipio)

        cont.add_widget(Label(text="Núcleo / localidad", size_hint_y=None, height=dp(20)))
        in_nucleo = TextInput(text=cfg["nucleo"], multiline=False, size_hint_y=None, height=dp(40))
        cont.add_widget(in_nucleo)

        cont.add_widget(Label(text="Provincia", size_hint_y=None, height=dp(20)))
        in_provincia = TextInput(text=cfg["provincia"], multiline=False, size_hint_y=None, height=dp(40))
        cont.add_widget(in_provincia)

        escudo_pendiente = {"ruta": cfg.get("escudo_path", "")}

        popup = Popup(title="Plantilla a utilizar", content=cont, size_hint=(0.9, 0.8))

        def _tras_elegir_archivo(ruta):
            if not ruta:
                self.estado.text = "No se eligio ningun archivo."
                return
            if leer_plantilla_excel is None:
                self.estado.text = "Falta soporte de Excel en esta build (openpyxl)."
                return
            try:
                datos = leer_plantilla_excel(ruta)
            except Exception as e:
                self.estado.text = f"No se pudo leer el Excel: {e}"
                return

            def actualizar(_dt):
                if datos["municipio"]:
                    in_municipio.text = datos["municipio"]
                if datos["nucleo"]:
                    in_nucleo.text = datos["nucleo"]
                if datos["provincia"]:
                    in_provincia.text = datos["provincia"]
                if datos["escudo_bytes"]:
                    ruta_escudo = os.path.join(ds.data_dir(), "plantilla_escudo." + datos["escudo_ext"])
                    with open(ruta_escudo, "wb") as f:
                        f.write(datos["escudo_bytes"])
                    escudo_pendiente["ruta"] = ruta_escudo
                self.estado.text = "Plantilla leida. Revisa los datos y pulsa Guardar."
            Clock.schedule_once(actualizar, 0)

        def _elegir_archivo(*_):
            if not (ANDROID and android_filepicker is not None):
                self.estado.text = "Elegir archivo solo esta disponible en el movil."
                return
            tipos = ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
            android_filepicker.elegir_archivo(_tras_elegir_archivo, tipos_mime=tipos)

        b_elegir.bind(on_release=_elegir_archivo)

        def _guardar(*_):
            ds.guardar_configuracion(
                in_municipio.text.strip(), in_nucleo.text.strip(), in_provincia.text.strip(),
                escudo_path=escudo_pendiente["ruta"],
            )
            self.estado.text = "Datos de ficha guardados."
            popup.dismiss()

        b_guardar = Button(text="Guardar", size_hint_y=None, height=dp(44))
        b_guardar.bind(on_release=_guardar)
        cont.add_widget(b_guardar)
        popup.open()

    def generar_pdfs(self, *_):
        puntos = [p for p in ds.cargar_puntos() if p.get("Completado")]
        if not puntos:
            self.estado.text = "No hay fichas completadas todavia."
            return
        cfg = ds.cargar_configuracion()
        ruta_pdf = os.path.join(ds.data_dir(), "fichas_pdf", "Fichas_Medidores.pdf")
        generar_todas_las_fichas(
            puntos, ruta_pdf,
            municipio=cfg["municipio"], nucleo=cfg["nucleo"], provincia=cfg["provincia"],
            escudo_path=cfg.get("escudo_path") or None,
        )
        self._ruta_pdf = ruta_pdf
        self.estado.text = (
            f"{len(puntos)} fichas generadas en un solo PDF. Pulsa 'Compartir PDFs' "
            f"para guardarlo en Drive, enviarlo por WhatsApp/email, etc."
        )

    def compartir_pdfs(self, *_):
        ruta_pdf = getattr(self, "_ruta_pdf", None) or os.path.join(ds.data_dir(), "fichas_pdf", "Fichas_Medidores.pdf")
        if not os.path.exists(ruta_pdf):
            self.estado.text = "Todavia no se ha generado el PDF de fichas."
            return
        if ANDROID and android_compartir is not None:
            ok = android_compartir.compartir_archivos([ruta_pdf], titulo="Compartir fichas PDF")
            if not ok:
                self.estado.text = "No se pudo abrir el dialogo de compartir."
        else:
            self.estado.text = f"El PDF esta en:\n{ruta_pdf}"


# ───────────────────────── PANTALLA: FICHA DE CAMPO ─────────────────────────

CALIBRES = ["", "13-A", "15-A", "13/15-A", "20-B", "25-C", "30-D", "32-D", "40-E",
            "50-F", "65-G", "80-H", "100-I", "125-J", "150-K", "200-L", "250-M",
            "300-N", "400-O", "500-P"]
# En QGIS, lo que se ve en la lista es "13-A?", "20-B"... pero lo que se
# GUARDA en el campo es solo el número ("13", "20"...). Este mapeo hace
# que guardemos el mismo valor real, aunque en pantalla se vea la
# etiqueta completa (igual que en QGIS).
CALIBRE_VALORES = {
    "13-A": "13", "15-A": "15", "13/15-A": "13/15", "20-B": "20", "25-C": "25",
    "30-D": "30", "32-D": "32", "40-E": "40", "50-F": "50", "65-G": "65",
    "80-H": "80", "100-I": "100", "125-J": "125", "150-K": "150", "200-L": "200",
    "250-M": "250", "300-N": "300", "400-O": "400", "500-P": "500",
}
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
        b_guardar = Button(text="Guardar")
        b_guardar.bind(on_release=self.guardar)
        acciones.add_widget(b_guardar)
        root.add_widget(acciones)

        acciones2 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8), padding=(dp(8), 0))
        b_salir = Button(text="Salir sin guardar")
        b_salir.bind(on_release=self.salir_sin_guardar)
        b_ver_mapa = Button(text="Ver en el mapa")
        b_ver_mapa.bind(on_release=self.ver_en_mapa)
        acciones2.add_widget(b_salir)
        acciones2.add_widget(b_ver_mapa)
        root.add_widget(acciones2)

        self.estado = Label(text="", size_hint_y=None, height=dp(24))
        root.add_widget(self.estado)
        self.add_widget(root)

    def cargar_punto(self, punto):
        self.punto = punto
        self._punto_original = copy.deepcopy(punto)
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
                    valor_defecto=datetime.now().strftime("%d/%m/%Y"))
        self._texto("HoraLectur", "Hora lectura",
                    valor_defecto=datetime.now().strftime("%H:%M:%S"))
        self._texto("FecHoraLec", "Fecha y hora lectura (registro)",
                    valor_defecto=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        self._spinner("Alojamiento", "Alojamiento", ALOJAMIENTOS)
        self._spinner("Calibre", "Calibre", CALIBRES)
        self._spinner("Diametros", "Diámetros", DIAMETROS)
        self._spinner("TipUsoComu", "Tipo de uso/consumo", TIPOS_USO)

        self._checkbox("Exterior", "Exterior")
        self._checkbox("Interior", "Interior")
        self._checkbox("UbicarExte", "Ubicar exterior")
        self._conectar_dependencias_ubicacion()
        self._checkbox("ValAcometi", "Válvula de acometida")
        self._checkbox("Individual", "Individual")
        self._checkbox("LlaveContador", "Llave de contador")
        self._checkbox("CambioTapa", "Cambio de tapa")
        self._checkbox("SeBorra", "Se borra")

        lat_inicial = str(punto.get("Latitud") or punto.get("Lat") or "")
        lon_inicial = str(punto.get("Longitud") or punto.get("Lon") or "")
        self._texto("Latitud", "Latitud (o pulsa Capturar GPS)", valor_defecto=lat_inicial)
        self._texto("Longitud", "Longitud", valor_defecto=lon_inicial)
        self._texto("Observaciones", "Observaciones")

        self.form.add_widget(Label(text="Fotografías", size_hint_y=None, height=dp(34)))
        self.form.add_widget(Label(text="", size_hint_y=None, height=dp(34)))
        for campo, etiqueta in CAMPOS_FOTO:
            self._foto(campo, etiqueta)

        CALIBRE_ETIQUETAS = {v: k for k, v in CALIBRE_VALORES.items()}
        for campo, valor in punto.items():
            if campo in self.inputs:
                w = self.inputs[campo]
                if isinstance(w, CheckBox):
                    w.active = bool(valor)
                elif isinstance(w, Spinner) and valor:
                    w.text = CALIBRE_ETIQUETAS.get(valor, valor) if campo == "Calibre" else valor
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

    def _conectar_dependencias_ubicacion(self):
        """Reproduce las reglas que ya tenía definidas el proyecto QGIS
        para estos 3 campos (mismo 'valor por defecto' condicional que
        vimos en el formulario de atributos):
        - Exterior e Interior son excluyentes (marcar uno desmarca el otro).
        - Marcar "Ubicar exterior" implica que el contador SÍ está dentro
          (Interior=True) pero se localiza/lee desde fuera, así que
          también desmarca Exterior.
        - Marcar Exterior desmarca tanto Interior como Ubicar exterior.
        """
        cb_ext = self.inputs["Exterior"]
        cb_int = self.inputs["Interior"]
        cb_ubi = self.inputs["UbicarExte"]
        self._actualizando_ubicacion = False

        def _al_cambiar(campo):
            def _handler(_inst, activo):
                if self._actualizando_ubicacion or not activo:
                    return
                self._actualizando_ubicacion = True
                try:
                    if campo == "Exterior":
                        cb_int.active = False
                        cb_ubi.active = False
                    elif campo == "Interior":
                        cb_ext.active = False
                    elif campo == "UbicarExte":
                        cb_ext.active = False
                        cb_int.active = True
                finally:
                    self._actualizando_ubicacion = False
            return _handler

        cb_ext.bind(active=_al_cambiar("Exterior"))
        cb_int.bind(active=_al_cambiar("Interior"))
        cb_ubi.bind(active=_al_cambiar("UbicarExte"))

    def _foto(self, campo, etiqueta):
        cont = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(4))
        # AsyncImage decodifica la foto en un hilo aparte (Kivy Loader).
        # Con "Image" normal, una foto de camara a resolucion completa
        # bloqueaba el hilo principal unos segundos al mostrarla, y la
        # app parecia congelada (no respondia ni el boton atras).
        img = AsyncImage(size_hint_y=None, height=dp(90), nocache=True)

        # Si el punto ya tenia una foto guardada de antes (p.ej. al volver
        # a entrar en una ficha ya rellenada), se muestra directamente.
        # Antes esto no pasaba: el recuadro se creaba siempre en blanco y
        # solo se rellenaba justo despues de tomar una foto NUEVA.
        ruta_existente = self.punto.get(campo) if self.punto else None
        if ruta_existente and os.path.exists(ruta_existente):
            img.source = ruta_existente

        fila_botones = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        btn_camara = Button(text=f"Cámara: {etiqueta}")
        btn_camara.bind(on_release=lambda *_: self._tomar_foto(campo, img))
        btn_menu = Button(text="···", size_hint_x=None, width=dp(44))
        btn_menu.bind(on_release=lambda *_: self._abrir_menu_adjuntar(campo, img))
        fila_botones.add_widget(btn_camara)
        fila_botones.add_widget(btn_menu)

        cont.add_widget(img)
        cont.add_widget(fila_botones)
        self.foto_widgets[campo] = img
        self.form.add_widget(Label(text="", size_hint_y=None, height=dp(150)))
        self.form.add_widget(cont)

    def _abrir_menu_adjuntar(self, campo, img_widget):
        cont = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        popup = Popup(title="Adjuntar foto", content=cont, size_hint=(0.85, 0.35))

        b1 = Button(text="Adjuntar un archivo")
        b2 = Button(text="Adjuntar de la galería")

        def _elegir(modo):
            popup.dismiss()
            self._adjuntar(campo, img_widget, modo)

        b1.bind(on_release=lambda *_: _elegir("archivo"))
        b2.bind(on_release=lambda *_: _elegir("galeria"))
        cont.add_widget(b1)
        cont.add_widget(b2)
        popup.open()

    def _adjuntar(self, campo, img_widget, modo):
        if not (ANDROID and android_adjuntar is not None):
            self.estado.text = "Adjuntar archivos solo esta disponible en el movil."
            return
        destino = os.path.join(ds.photos_dir(), f"{self.punto['_id']}_{campo}.jpg")
        callback = lambda path: self._foto_lista(campo, img_widget, path)
        try:
            if modo == "archivo":
                android_adjuntar.adjuntar_archivo(destino, callback)
            else:
                android_adjuntar.adjuntar_galeria(destino, callback)
        except Exception as e:
            self.estado.text = f"Error al adjuntar: {e}"

    # -- cámara y GPS --
    def _tomar_foto(self, campo, img_widget):
        destino = os.path.join(ds.photos_dir(), f"{self.punto['_id']}_{campo}.jpg")

        if ANDROID and android_camera is not None:
            # Camara propia via FileProvider (ver android_camera.py):
            # evita el FileUriExposedException que rompia plyer.camera.
            try:
                android_camera.tomar_foto(
                    destino,
                    lambda path: self._foto_lista(campo, img_widget, path),
                )
            except Exception as e:
                self.estado.text = f"Error de camara: {e}"
            return

        # Fuera de Android (p.ej. pruebas en escritorio) no hay FileProvider
        # ni intents nativos: se deja plyer como antes, solo para ese caso.
        if camera is None:
            self.estado.text = "Camara no disponible en este dispositivo/emulador."
            return
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
                # Se guarda YA (no se espera a pulsar "Guardar"): si tomas
                # una foto y sales sin guardar el resto del formulario, la
                # foto no se pierde. "Salir sin guardar" revierte esto si
                # hace falta (ver salir_sin_guardar).
                ds.actualizar_punto(self.punto)
                self.estado.text = f"Foto {campo} guardada."
            else:
                self.estado.text = "No se recibio la foto (cancelada)."
        Clock.schedule_once(actualizar, 0)

    def guardar(self, *_):
        if not self.punto:
            return
        # Misma restricción que ya tenía definida el proyecto QGIS: un
        # contador no puede ser Exterior e Interior a la vez. Con las
        # casillas conectadas (ver _conectar_dependencias_ubicacion) esto
        # no debería llegar a pasar, pero se deja como red de seguridad.
        if self.inputs["Exterior"].active and self.inputs["Interior"].active:
            self.estado.text = "Un contador no puede ser Exterior e Interior a la vez."
            return
        for campo, widget in self.inputs.items():
            if isinstance(widget, CheckBox):
                self.punto[campo] = widget.active
            elif isinstance(widget, Spinner):
                texto = widget.text if widget.text != widget.values[0] else ""
                if campo == "Calibre":
                    texto = CALIBRE_VALORES.get(texto, texto)
                self.punto[campo] = texto
            elif isinstance(widget, TextInput):
                self.punto[campo] = widget.text
        self.punto["Completado"] = True
        ds.actualizar_punto(self.punto)
        self.estado.text = "Guardado correctamente."

    def volver(self, *_):
        self.manager.current = "lista"
        self.manager.get_screen("lista").refrescar()

    def ver_en_mapa(self, *_):
        """Va directo al mapa centrado en este punto (resaltado en
        amarillo), para poder seguir digitalizando el siguiente punto
        cercano desde ahí, sin tener que pasar por la lista."""
        if not self.punto:
            return
        pantalla_mapa = self.manager.get_screen("mapa")
        pantalla_mapa._id_seleccionado = self.punto.get("_id")
        self.manager.current = "mapa"

    def salir_sin_guardar(self, *_):
        # Revierte el punto a como estaba justo al abrir la ficha. Como las
        # fotos se guardan al momento de tomarlas (ver _foto_lista), esto
        # tambien deshace fotos tomadas/adjuntadas durante esta sesion si
        # no se pulso "Guardar".
        if self.punto and getattr(self, "_punto_original", None) is not None:
            ds.actualizar_punto(self._punto_original)
        self.volver()


# ───────────────────────── PANTALLA: MAPA ─────────────────────────

class PantallaMapa(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.mapview = None
        self.capa_fondo_widget = None
        self.capa_marcadores = None
        self._id_seleccionado = None
        self.root_box = BoxLayout(orientation="vertical")

        cab = BoxLayout(size_hint_y=None, height=dp(48), padding=(dp(8), 0), spacing=dp(8))
        b_atras = Button(text="<-", size_hint_x=None, width=dp(48))
        b_atras.bind(on_release=lambda *_: setattr(self.manager, "current", "lista"))
        cab.add_widget(b_atras)
        cab.add_widget(Label(text="Mapa de puntos"))
        b_capas = Button(text="Capas", size_hint_x=None, width=dp(70))
        b_capas.bind(on_release=self._abrir_panel_capas)
        cab.add_widget(b_capas)
        self.root_box.add_widget(cab)

        # El mapa va dentro de un FloatLayout para poder superponer la cruceta
        # central y el botón de "añadir punto aquí" encima del mapa.
        from kivy.uix.floatlayout import FloatLayout
        self.contenedor_mapa = FloatLayout()
        self.root_box.add_widget(self.contenedor_mapa)

        self.cruceta = Label(text="+", font_size=dp(28), bold=True, color=(1, 0, 0, 1),
                              size_hint=(None, None), size=(dp(30), dp(30)),
                              pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.contenedor_mapa.add_widget(self.cruceta)

        b_agregar = Button(text="Añadir punto aquí", size_hint=(None, None),
                            size=(dp(190), dp(50)), pos_hint={"center_x": 0.5, "y": 0.03})
        b_agregar.bind(on_release=lambda *_: self._agregar_punto_en_centro())
        self.contenedor_mapa.add_widget(b_agregar)

        b_zoom_mas = Button(text="+", bold=True, font_size=dp(22), size_hint=(None, None),
                             size=(dp(48), dp(48)), pos_hint={"right": 0.98, "y": 0.14})
        b_zoom_mas.bind(on_release=lambda *_: self._cambiar_zoom(1))
        self.contenedor_mapa.add_widget(b_zoom_mas)

        b_zoom_menos = Button(text="-", bold=True, font_size=dp(22), size_hint=(None, None),
                               size=(dp(48), dp(48)), pos_hint={"right": 0.98, "y": 0.03})
        b_zoom_menos.bind(on_release=lambda *_: self._cambiar_zoom(-1))
        self.contenedor_mapa.add_widget(b_zoom_menos)

        ruta_icono_norte = os.path.join(os.path.dirname(__file__), "assets", "icono_norte.png")
        ruta_icono_rotar = os.path.join(os.path.dirname(__file__), "assets", "icono_rotar.png")

        b_norte = Button(
            background_normal=ruta_icono_norte, background_down=ruta_icono_norte, border=(0, 0, 0, 0),
            size_hint=(None, None), size=(dp(48), dp(48)), pos_hint={"x": 0.02, "y": 0.14},
        )
        b_norte.bind(on_release=lambda *_: self._orientar_al_norte())
        self.contenedor_mapa.add_widget(b_norte)

        self._rotacion_activa = False
        b_rotar = Button(
            background_normal=ruta_icono_rotar, background_down=ruta_icono_rotar, border=(0, 0, 0, 0),
            size_hint=(None, None), size=(dp(48), dp(48)), pos_hint={"x": 0.02, "y": 0.03},
        )
        b_rotar.bind(on_release=lambda *_: self._alternar_rotacion())
        self.contenedor_mapa.add_widget(b_rotar)

        self.info = Label(text="", size_hint_y=None, height=dp(28))
        self.root_box.add_widget(self.info)
        self.add_widget(self.root_box)

    def _cambiar_zoom(self, delta):
        if self.mapview is None:
            return
        nuevo_zoom = self.mapview.zoom + delta
        maximo = self.mapview.map_source.max_zoom
        minimo = self.mapview.map_source.min_zoom
        self.mapview.zoom = max(minimo, min(maximo, nuevo_zoom))

    def _orientar_al_norte(self):
        if self.mapview is not None:
            self.mapview.orientar_al_norte()

    def _alternar_rotacion(self):
        # Pausado por ahora: con las capas de fondo otra vez en modo
        # "window" (para no romper el dibujo de parcelas/límites, ver
        # nota en on_pre_enter), rotar solo giraría la foto de fondo y
        # dejaría las parcelas/marcadores/etiquetas fijos -> peor que no
        # rotar nada. Se retoma cuando se pueda validar bien en el móvil.
        self.info.text = "La rotación está pausada por ahora (ver nota del chat)."

    def on_pre_enter(self):
        # Quita solo el mapa anterior (mantiene cruceta/botón que ya están añadidos una vez)
        if self.mapview is not None:
            self.contenedor_mapa.remove_widget(self.mapview)
            self.mapview = None
        try:
            from kivy_garden.mapview import MapView, MapMarker, MapSource
            from kivy_garden.mapview.clustered_marker_layer import ClusteredMarkerLayer
        except Exception as e:
            _log_debug(f"EXCEPCION al importar mapview: {e!r}")
            self.info.text = f"No se pudo cargar el mapa: {e}"
            return

        # MapView "normal" solo pinta UNA fuente de mapa. Para el modo
        # "Híbrida" (satélite PNOA de fondo + callejero OSM semi-
        # transparente encima) hace falta pintar una SEGUNDA fuente por
        # encima con opacidad reducida. kivy_garden.mapview no trae esto
        # de serie -- de hecho su propio código tiene un comentario
        # "XXX do overlay support" sin terminar -- pero la pieza que
        # hace falta (load_tile_for_source ya acepta un parámetro de
        # opacidad) SÍ está, simplemente nadie la conectó. Aquí se
        # conecta con una subclase mínima.
        class MapViewConSuperposicion(MapView):
            fuente_superpuesta = ObjectProperty(None, allownone=True)
            opacidad_superpuesta = NumericProperty(0.35)

            def load_tile(self, x, y, size, zoom):
                if self.tile_in_tile_map(x, y) or zoom != self._zoom:
                    return
                self.load_tile_for_source(self.map_source, 1.0, size, x, y, zoom)
                if self.fuente_superpuesta is not None:
                    self.load_tile_for_source(
                        self.fuente_superpuesta, self.opacidad_superpuesta, size, x, y, zoom
                    )
                self.tile_map_set(x, y, True)

            def get_local_xy_from(self, lat, lon, zoom):
                """Como get_window_xy_from, pero en coordenadas LOCALES del
                'scatter' (antes de aplicar zoom/rotación), que es lo que
                necesitan las capas añadidas con mode='scatter' para que
                giren en sincronía con el mapa al rotar (si se usaran las
                coordenadas de pantalla normales, quedarían en el sitio
                equivocado en cuanto se rota, porque esas ya llevan el giro
                aplicado una vez y el scatter se lo aplicaría una segunda)."""
                ms = self.map_source
                x = ms.get_x(zoom, lon) + self.delta_x
                y = ms.get_y(zoom, lat) + self.delta_y
                return x, y

            def activar_rotacion(self, activar):
                self._scatter.do_rotation = activar

            def orientar_al_norte(self):
                self._scatter.rotation = 0

        self._MapViewConSuperposicion = MapViewConSuperposicion

        # Fuentes de mapa disponibles (como el selector de "Mapas" de
        # QField). OSM es el callejero de siempre; PNOA son las
        # ortofotos aéreas oficiales del Instituto Geográfico Nacional
        # (gratuitas y de uso público, pensadas para esto). "Híbrida"
        # combina las dos: PNOA de fondo + calles de OSM encima al 35%
        # de opacidad, para ver las calles sobre la foto aérea real. No
        # incluimos "Google Maps"/"Bing" como en QField porque esos
        # necesitan una clave de API de pago; si más adelante quieres
        # integrarlos con tu propia clave, se puede añadir igual.
        fuente_osm = MapSource()
        fuente_pnoa = MapSource(
            url="https://www.ign.es/wmts/pnoa-ma?service=WMTS&request=GetTile&version=1.0.0"
                "&layer=OI.OrthoimageCoverage&style=default&format=image/jpeg"
                "&tilematrixset=GoogleMapsCompatible&tilematrix={z}&tilerow={y}&tilecol={x}",
            min_zoom=0, max_zoom=19, image_ext="jpeg",
            attribution="PNOA cedido por © Instituto Geográfico Nacional de España",
        )
        self.fuentes_mapa = {
            "Calles (OpenStreetMap)": {"base": fuente_osm, "superpuesta": None},
            "Satélite (PNOA - IGN)": {"base": fuente_pnoa, "superpuesta": None},
            "Híbrida (PNOA + calles 35%)": {"base": fuente_pnoa, "superpuesta": fuente_osm},
        }
        fuente_guardada = getattr(self, "_nombre_fuente_actual", "Calles (OpenStreetMap)")
        fuente_inicial = self.fuentes_mapa.get(fuente_guardada, self.fuentes_mapa["Calles (OpenStreetMap)"])

        puntos = [p for p in ds.cargar_puntos() if _coord_valida(p.get("Lat")) and _coord_valida(p.get("Lon"))]

        punto_seleccionado = None
        if self._id_seleccionado is not None:
            punto_seleccionado = next((p for p in puntos if p.get("_id") == self._id_seleccionado), None)

        zoom_inicial = 16
        if punto_seleccionado is not None:
            lat_centro = float(punto_seleccionado["Lat"])
            lon_centro = float(punto_seleccionado["Lon"])
            zoom_inicial = 18  # más cerca, para ver bien el punto que se venía a buscar
        elif puntos:
            lat_centro = sum(float(p["Lat"]) for p in puntos) / len(puntos)
            lon_centro = sum(float(p["Lon"]) for p in puntos) / len(puntos)
        else:
            lat_centro, lon_centro = 42.9, -3.5  # centro aproximado (Burgos) si no hay puntos aún

        self.mapview = self._MapViewConSuperposicion(
            lat=lat_centro, lon=lon_centro, zoom=zoom_inicial,
            map_source=fuente_inicial["base"],
            fuente_superpuesta=fuente_inicial["superpuesta"],
        )
        # index=len(children) inserta al final de la lista de hijos, que en Kivy
        # es la posición que se dibuja PRIMERO (más al fondo). Así el mapa queda
        # siempre detrás de la cruceta y los botones, sin importar en qué orden
        # se hayan creado esos widgets en __init__.
        self.contenedor_mapa.add_widget(self.mapview, index=len(self.contenedor_mapa.children))

        # Antes se añadía un MapMarker por punto (hasta 386 widgets a la vez),
        # lo que iba muy lento y "robaba" el gesto de pellizco para zoom.
        # Con ClusteredMarkerLayer, los puntos cercanos se agrupan en una
        # burbuja con el número de puntos, y solo se crean widgets reales
        # para lo que cae dentro del recuadro visible en cada nivel de zoom.
        self.capa_marcadores = ClusteredMarkerLayer(
            cluster_min_zoom=0,
            cluster_max_zoom=18,   # a partir de este zoom ya no se agrupan (se ven todos sueltos)
            cluster_radius="40dp",
        )
        for p in puntos:
            options = {"on_release": lambda inst, punto=p: self._abrir_ficha(punto)}
            # Mismo criterio que ya tenías definido en QGIS para la capa
            # de Contadores (por reglas): rojo = pendiente, verde =
            # completado, magenta = marcado para borrar. Se añade además
            # el amarillo para el punto que se seleccionó por última vez
            # (al volver desde "Ver en el mapa"), que no existía en QGIS
            # pero ayuda a ubicarse al seguir digitalizando.
            if p.get("_id") == self._id_seleccionado:
                options["source"] = os.path.join(os.path.dirname(__file__), "assets", "marcador_amarillo.png")
            elif p.get("SeBorra"):
                options["source"] = os.path.join(os.path.dirname(__file__), "assets", "marcador_magenta.png")
            elif p.get("Completado"):
                options["source"] = os.path.join(os.path.dirname(__file__), "assets", "marcador_verde.png")
            # si no, se deja el marcador rojo de siempre (pendiente)
            self.capa_marcadores.add_marker(
                lon=float(p["Lon"]),
                lat=float(p["Lat"]),
                cls=MapMarker,
                options=options,
            )
        self.mapview.add_layer(self.capa_marcadores, mode="window")

        self._cargar_capa_de_fondo()

        self.info.text = f"{len(puntos)} puntos con coordenadas de {len(ds.cargar_puntos())} totales."

    def _cargar_capa_de_fondo(self):
        import json
        ruta = os.path.join(ds.data_dir(), "capas_fondo.json")
        if not os.path.exists(ruta):
            _log_debug("No existe capas_fondo.json (no se ha importado ninguna capa de fondo todavia)")
            return
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                capas_fondo = json.load(f)
            _log_debug(
                "Cargando capas_fondo.json en el mapa: " +
                ", ".join(f"{c['nombre']}({len(c['anillos'])} anillos, activa={c.get('activa', True)})"
                          for c in capas_fondo)
            )
            if capas_fondo:
                self.capa_fondo_widget = CapaVectorFondo(capas_fondo)
                self.mapview.add_layer(self.capa_fondo_widget, mode="window")
        except Exception as e:
            _log_debug(f"EXCEPCION al cargar capa de fondo en el mapa: {e!r}")

    def _abrir_panel_capas(self, *_):
        cont = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        scroll_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        scroll_layout.bind(minimum_height=scroll_layout.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(scroll_layout)
        cont.add_widget(scroll)

        popup = Popup(title="Capas", content=cont, size_hint=(0.85, 0.75))

        # ── Mapa base (calles / satélite / híbrida) ──
        scroll_layout.add_widget(Label(text="Mapa base", bold=True, size_hint_y=None, height=dp(28)))

        checks_fuente = []

        def _cambiar_fuente(nombre_fuente):
            self._nombre_fuente_actual = nombre_fuente
            if self.mapview is not None:
                fuente = self.fuentes_mapa[nombre_fuente]
                self.mapview.map_source = fuente["base"]
                self.mapview.fuente_superpuesta = fuente["superpuesta"]
                # Las teselas ya cargadas se guardaron para la fuente
                # anterior; hay que tirarlas para que se vuelvan a pedir
                # con la fuente/superposición nueva.
                self.mapview.remove_all_tiles()
                self.mapview.trigger_update(True)

        def _marcar_solo_esta_fuente(cb_elegida, nombre_fuente, *_):
            if not cb_elegida.active:
                return
            for cb, _n in checks_fuente:
                if cb is not cb_elegida:
                    cb.active = False
            _cambiar_fuente(nombre_fuente)

        nombre_actual = getattr(self, "_nombre_fuente_actual", "Calles (OpenStreetMap)")
        for nombre_fuente in self.fuentes_mapa:
            fila = BoxLayout(size_hint_y=None, height=dp(44))
            cb = CheckBox(active=(nombre_fuente == nombre_actual), size_hint_x=None, width=dp(44))
            cb.bind(active=lambda inst, valor, n=nombre_fuente: _marcar_solo_esta_fuente(inst, n))
            fila.add_widget(cb)
            lbl_fuente = Label(text=nombre_fuente, halign="left", valign="middle", shorten=True, shorten_from="right")
            lbl_fuente.bind(size=lambda inst, tam: setattr(inst, "text_size", tam))
            fila.add_widget(lbl_fuente)
            scroll_layout.add_widget(fila)
            checks_fuente.append((cb, nombre_fuente))

        # ── Capas de fondo (parcelas, límites, construcciones...) ──
        if self.capa_fondo_widget and getattr(self.capa_fondo_widget, "capas", None):
            scroll_layout.add_widget(Label(text="Capas de fondo", bold=True, size_hint_y=None, height=dp(28)))

            def _on_toggle(capa, valor):
                capa["activa"] = valor
                if self.capa_fondo_widget is not None:
                    self.capa_fondo_widget.reposition()

            for capa in self.capa_fondo_widget.capas:
                fila = BoxLayout(size_hint_y=None, height=dp(44))
                cb = CheckBox(active=capa.get("activa", True), size_hint_x=None, width=dp(44))
                cb.bind(active=lambda inst, valor, c=capa: _on_toggle(c, valor))
                fila.add_widget(cb)
                lbl = Label(text=capa["nombre"], halign="left", valign="middle", shorten=True, shorten_from="right")
                lbl.bind(size=lambda inst, tam: setattr(inst, "text_size", tam))
                fila.add_widget(lbl)
                scroll_layout.add_widget(fila)

        b_cerrar = Button(text="Cerrar", size_hint_y=None, height=dp(48))
        b_cerrar.bind(on_release=lambda *_: popup.dismiss())
        cont.add_widget(b_cerrar)
        popup.open()

    def _agregar_punto_en_centro(self):
        """Crea un punto nuevo en las coordenadas del centro del mapa
        (donde está la cruceta) y abre su ficha para rellenarlo y tomarle
        las fotos, igual que al 'digitalizar' en QField."""
        if not self.mapview:
            return
        lat, lon = self.mapview.lat, self.mapview.lon
        puntos = ds.cargar_puntos()
        nuevo_id = (max((p["_id"] for p in puntos), default=-1)) + 1
        nuevo = {c: "" for c in ds.TODOS_CAMPOS}
        nuevo["_id"] = nuevo_id
        nuevo["Completado"] = False
        nuevo["Lat"] = f"{lat:.7f}"
        nuevo["Lon"] = f"{lon:.7f}"
        nuevo["Latitud"] = f"{lat:.7f}"
        nuevo["Longitud"] = f"{lon:.7f}"
        puntos.append(nuevo)
        ds.guardar_puntos(puntos)
        self._abrir_ficha(nuevo)

    def _abrir_ficha(self, punto):
        pantalla_ficha = self.manager.get_screen("ficha")
        pantalla_ficha.cargar_punto(punto)
        self.manager.current = "ficha"


class CapaVectorFondo:
    """Capa de referencia (parcelas, límite, construcciones...) dibujada
    encima del mapa. Se crea dinámicamente heredando de MapLayer solo
    cuando kivy_garden.mapview ya está disponible.

    Antes recalculaba y volvía a dibujar TODOS los puntos de TODAS las
    capas en cada pan/zoom (reposition() se llama en cada frame de
    movimiento), aunque estuvieran fuera de la pantalla — con capas
    grandes (parcelas de todo un municipio) esto era el principal
    causante de que el mapa fuera lento. Ahora:
      - se descarta cada anillo cuya caja (bounding box) no toque la
        zona visible del mapa, ANTES de convertir sus puntos a pantalla.
      - los anillos muy detallados (con muchos vértices) se "decimian"
        (se dibujan solo 1 de cada N puntos) — a la escala a la que se
        ve un mapa en un móvil, no se nota, pero ahorra mucho trabajo.
    """

    def __new__(cls, capas_fondo):
        from kivy_garden.mapview import MapLayer
        from kivy.graphics import Color, Line, Rectangle
        from kivy.core.text import Label as CoreLabel

        MAX_PUNTOS_POR_ANILLO = 120
        ZOOM_MINIMO_ETIQUETAS = 17  # de más lejos, quedaría todo lleno de texto encimado

        def _bbox_anillo(anillo):
            lats = [p[0] for p in anillo]
            lons = [p[1] for p in anillo]
            return (min(lats), min(lons), max(lats), max(lons))

        class _CapaVectorFondoReal(MapLayer):
            def __init__(self, capas, **kwargs):
                super().__init__(**kwargs)
                # Cada capa lleva ya calculada la bbox de cada anillo (una
                # sola vez, no en cada frame) y un flag "activa" para el
                # panel de capas de la pantalla del mapa.
                self.capas = capas
                self._texturas_etiquetas = {}  # (texto,color,tam) -> textura (cache)
                for capa in self.capas:
                    capa.setdefault("activa", True)
                    if "anillos_bbox" not in capa:
                        capa["anillos_bbox"] = [_bbox_anillo(a) for a in capa["anillos"]]

            def _textura_para(self, texto, estilo):
                color = tuple(estilo["color"])
                tam_pt = estilo["tam_pt"]
                halo_color = tuple(estilo.get("halo_color", (1, 1, 1)))
                halo_ancho = estilo.get("halo_ancho", 0)
                clave = (texto, color, tam_pt, halo_color, halo_ancho)
                textura = self._texturas_etiquetas.get(clave)
                if textura is None:
                    # El tamaño de fuente de QGIS esta pensado para el
                    # lienzo de impresion, no para pantalla de movil; se
                    # escala para que se pueda leer bien en el telefono.
                    tam_px = max(11, round(tam_pt * 1.8))
                    kwargs_halo = {}
                    if halo_ancho:
                        kwargs_halo = {
                            "outline_width": max(1, round(halo_ancho * 1.5)),
                            "outline_color": halo_color,
                        }
                    etiqueta = CoreLabel(
                        text=texto, font_size=dp(tam_px), bold=True,
                        color=(*color, 1), **kwargs_halo,
                    )
                    etiqueta.refresh()
                    textura = etiqueta.texture
                    self._texturas_etiquetas[clave] = textura
                return textura

            def reposition(self):
                mapa = self.parent
                if mapa is None:
                    return
                self.canvas.clear()
                bbox = mapa.get_bbox()
                v_lat1, v_lon1, v_lat2, v_lon2 = bbox
                v_lat_min, v_lat_max = min(v_lat1, v_lat2), max(v_lat1, v_lat2)
                v_lon_min, v_lon_max = min(v_lon1, v_lon2), max(v_lon1, v_lon2)

                # Para que las etiquetas no se amontonen unas encima de
                # otras (como se veia en capas con muchas parcelas
                # pequeñas juntas), se recuerda el hueco en pantalla que
                # ya ocupa cada etiqueta ya colocada en este frame, y se
                # descarta la siguiente si se solapa con alguna.
                huecos_ocupados = []

                def _hueco_libre(x, y, w, h):
                    x0, y0, x1, y1 = x - w / 2, y - h / 2, x + w / 2, y + h / 2
                    for hx0, hy0, hx1, hy1 in huecos_ocupados:
                        if x0 < hx1 and x1 > hx0 and y0 < hy1 and y1 > hy0:
                            return False
                    huecos_ocupados.append((x0, y0, x1, y1))
                    return True

                with self.canvas:
                    for capa in self.capas:
                        if not capa.get("activa", True):
                            continue
                        trazos = capa.get("trazos") or [(*capa.get("color", (0.8, 0.2, 0.2)), 1.1)]
                        cerrado = capa["tipo"] == "polygon"
                        for anillo, bb in zip(capa["anillos"], capa["anillos_bbox"]):
                            a_lat_min, a_lon_min, a_lat_max, a_lon_max = bb
                            # Descarta el anillo si su caja no toca la
                            # zona visible del mapa (no hace falta
                            # convertir ni un punto suyo a pantalla).
                            if (a_lat_max < v_lat_min or a_lat_min > v_lat_max or
                                    a_lon_max < v_lon_min or a_lon_min > v_lon_max):
                                continue

                            puntos_anillo = anillo
                            if len(puntos_anillo) > MAX_PUNTOS_POR_ANILLO:
                                paso = len(puntos_anillo) // MAX_PUNTOS_POR_ANILLO
                                puntos_anillo = puntos_anillo[::paso]

                            puntos_xy = []
                            for lat, lon in puntos_anillo:
                                x, y = mapa.get_window_xy_from(lat, lon, mapa.zoom)
                                puntos_xy.extend([x, y])
                            if len(puntos_xy) < 4:
                                continue

                            # Varios trazos por anillo = el efecto "halo"
                            # que ya traía la capa en QGIS (p.ej. Límites:
                            # una línea negra gruesa debajo y una naranja
                            # más fina encima, en ese orden).
                            for r, g, b, ancho_mm in trazos:
                                Color(r, g, b, 0.9)
                                ancho_px = max(1.0, ancho_mm * 1.6)
                                Line(points=puntos_xy, width=ancho_px, close=cerrado)

                        # Etiquetas de texto (direcciones, etc.), con el
                        # mismo color/tamaño/halo que ya tenía configurado
                        # esta capa en QGIS. Solo se dibujan si hay zoom
                        # suficiente para leerlas sin amontonarse, y se
                        # salta cualquiera que choque con otra ya puesta.
                        etiquetas = capa.get("etiquetas") or []
                        estilo = capa.get("estilo_etiqueta") or {
                            "color": (1, 1, 1), "tam_pt": 8, "halo_color": (0, 0, 0), "halo_ancho": 0.8,
                        }
                        if etiquetas and mapa.zoom >= ZOOM_MINIMO_ETIQUETAS:
                            Color(1, 1, 1, 1)
                            for texto, lat, lon in etiquetas:
                                if (lat < v_lat_min or lat > v_lat_max or
                                        lon < v_lon_min or lon > v_lon_max):
                                    continue
                                x, y = mapa.get_window_xy_from(lat, lon, mapa.zoom)
                                textura = self._textura_para(texto, estilo)
                                w, h = textura.size
                                if not _hueco_libre(x, y, w, h):
                                    continue
                                Rectangle(texture=textura, size=(w, h), pos=(x - w / 2, y - h / 2))

        return _CapaVectorFondoReal(capas_fondo)


def _coord_valida(valor):
    try:
        float(valor)
        return True
    except (TypeError, ValueError):
        return False


# ───────────────────────── APP ─────────────────────────

class DigitalizacionAguaApp(App):
    def build(self):
        pedir_permisos()
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(PantallaImportar(name="importar"))
        sm.add_widget(PantallaLista(name="lista"))
        sm.add_widget(PantallaFicha(name="ficha"))
        sm.add_widget(PantallaMapa(name="mapa"))
        return sm


if __name__ == "__main__":
    DigitalizacionAguaApp().run()
