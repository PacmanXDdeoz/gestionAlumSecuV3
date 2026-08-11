import datetime
import unittest

from sqlalchemy import text

from app import create_app, db
from app.auth.models import Docente, Rol
from app.models import (
    Alumno,
    AnotacionAlumno,
    Calificacion,
    CalificacionMateria,
    Grupos,
    Horario,
    Materia,
)


class PublicEdicionTestCase(unittest.TestCase):
    """Flujo de búsqueda QR + edición del docente + PDF de credencial.

    Incluye la regla anti-IDOR: solo el admin o un docente que imparta una
    materia del alumno (currículum del grupo) puede editar o descargar el QR.

    Misma convención que test_qr_generation.py: escribe en la base de
    testing, es idempotente y en tearDown solo borra los datos creados
    por este test (nunca db.drop_all()).
    """

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS alejandra'))
            db.create_all()
            Rol.seed_defaults()
            # Limpieza de corridas previas (idempotente); grupo dedicado '9E'
            # Los registros con claves foráneas al alumno (calificaciones,
            # calificaciones_materia, anotaciones) se borran antes que él.
            # Se borran TODOS los alumnos que apunten al grupo 9E (aunque
            # algún test haya cambiado el nombre), no solo name='Pepe'.
            grupo_prev = Grupos.query.filter_by(grado='9', grupo='E').first()
            alumnos_prev = (Alumno.query.filter_by(name='Pepe').all()
                            if grupo_prev is None
                            else Alumno.query.filter_by(group_id=grupo_prev.id).all())
            for a in alumnos_prev:
                Calificacion.query.filter_by(alumnos_id=a.id).delete()
                CalificacionMateria.query.filter_by(alumnos_id=a.id).delete()
                AnotacionAlumno.query.filter_by(alumno_id=a.id).delete()
                db.session.delete(a)
            # Horarios de corridas previas (apuntan al grupo 9E o a los
            # docentes de prueba): borrarlos ANTES de docentes/grupo evita
            # IntegrityError por las FKs de horarios.docente_id/grupo_id.
            Horario.query.filter(
                Horario.grupo_id == (grupo_prev.id if grupo_prev is not None else -1)
            ).delete(synchronize_session=False)
            for email in ('edit@example.com', 'nose@example.com', 'hist@example.com', 'adm@example.com'):
                Docente.query.filter_by(email=email).delete()
            if grupo_prev is not None:
                db.session.delete(grupo_prev)
            for nombre in ('Español', 'Historia'):
                m = Materia.query.filter_by(nombre=nombre).first()
                if m is not None:
                    m.docentes = []
                    m.grupos = []
            db.session.commit()

            grupo = Grupos(grado='9', grupo='E')
            grupo.save()
            self.grupo_id = grupo.id

            # Materias del catálogo: se reutilizan si ya existen
            self.materias_creadas = []
            esp = Materia.query.filter_by(nombre='Español').first()
            if esp is None:
                esp = Materia(nombre='Español', descripcion='Lengua')
                db.session.add(esp)
                self.materias_creadas.append('Español')
            hist = Materia.query.filter_by(nombre='Historia').first()
            if hist is None:
                hist = Materia(nombre='Historia', descripcion='Historia')
                db.session.add(hist)
                self.materias_creadas.append('Historia')
            db.session.flush()

            # Alumno en el grupo 9E (currículum del grupo: solo Español)
            alumno = Alumno(
                name='Pepe', lastname_p='López', lastname_m='Mora',
                group_id=self.grupo_id, genero='M', password='CODIGO1234',
            )
            alumno.save()
            self.alumno_id = alumno.id
            self.codigo = alumno.password

            # Grupo con currículum configurado (solo Español)
            grupo.materias = [esp]
            db.session.commit()

            # Docente 'edit@' imparte Español → tiene acceso al alumno
            edit = Docente(name='Docente Edit', email='edit@example.com', rol=2)
            edit.set_password('123456')
            edit.materias = [esp]
            db.session.add(edit)
            db.session.commit()

            # Docente 'nose@' sin materias → denegado
            nose = Docente(name='Docente Sin Materias', email='nose@example.com', rol=2)
            nose.set_password('123456')
            db.session.add(nose)
            db.session.commit()

            # Docente 'hist@' imparte Historia (fuera del currículum del 9E) → denegado
            hist_d = Docente(name='Docente Historia', email='hist@example.com', rol=2)
            hist_d.set_password('123456')
            hist_d.materias = [hist]
            db.session.add(hist_d)
            db.session.commit()

            # Admin (rol 1) sin materias → acceso total
            adm = Docente(name='Admin', email='adm@example.com', rol=1)
            adm.set_password('123456')
            db.session.add(adm)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            grupo = Grupos.query.filter_by(grado='9', grupo='E').first()
            alumnos = (Alumno.query.filter_by(name='Pepe').all()
                       if grupo is None
                       else Alumno.query.filter_by(group_id=grupo.id).all())
            for a in alumnos:
                Calificacion.query.filter_by(alumnos_id=a.id).delete()
                CalificacionMateria.query.filter_by(alumnos_id=a.id).delete()
                AnotacionAlumno.query.filter_by(alumno_id=a.id).delete()
                db.session.delete(a)
            Horario.query.filter(
                Horario.grupo_id == (grupo.id if grupo is not None else -1)
            ).delete(synchronize_session=False)
            for email in ('edit@example.com', 'nose@example.com', 'hist@example.com', 'adm@example.com'):
                Docente.query.filter_by(email=email).delete()
            if grupo is not None:
                db.session.delete(grupo)
            for nombre in self.materias_creadas:
                Materia.query.filter_by(nombre=nombre).delete()
            db.session.commit()
            db.session.remove()

    def _login(self, email='edit@example.com', password='123456'):
        return self.client.post('/login', data={
            'email': email,
            'password': password,
        }, follow_redirects=False)

    # ── Resolución de códigos QR (ID numérico o código de acceso) ──────
    def test_find_by_code_or_id(self):
        with self.app.app_context():
            self.assertIsNotNone(Alumno.find_by_code_or_id('CODIGO1234'))
            self.assertIsNotNone(Alumno.find_by_code_or_id(str(self.alumno_id)))
            self.assertIsNone(Alumno.find_by_code_or_id('NOEXISTE1'))
            self.assertIsNone(Alumno.find_by_code_or_id('999999'))

    def test_boleta_resuelve_por_id_numerico(self):
        # Los QR de alumnos creados por rutas públicas codifican el ID
        res = self.client.get(f'/calificaciones?codigoAlumno={self.alumno_id}')
        self.assertEqual(200, res.status_code)
        self.assertIn('Pepe', res.get_data(as_text=True))

    def test_boleta_resuelve_por_codigo(self):
        res = self.client.get(f'/calificaciones?codigoAlumno={self.codigo}')
        self.assertEqual(200, res.status_code)
        self.assertIn('Pepe', res.get_data(as_text=True))

    # ── Boleta por URL directa del QR (escaneo nativo) ──────────────────
    def test_boleta_por_url_directa_del_qr(self):
        # El QR de la credencial codifica /buscar/<id>: al escanearlo con
        # la cámara del celular se abre la boleta directamente.
        res = self.client.get(f'/buscar/{self.alumno_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        self.assertIn('Pepe', html)
        self.assertIn('López', html)

    def test_boleta_url_directa_invalida_404(self):
        res = self.client.get('/buscar/999999')
        self.assertEqual(404, res.status_code)

    # ── Vista de edición del docente ────────────────────────────────────
    def test_editar_requiere_login(self):
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar', follow_redirects=False)
        self.assertEqual(302, res.status_code)
        self.assertIn('/login', res.location)

    def test_editar_get_renders_form(self):
        self._login()
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        self.assertIn('Guardar cambios', html)
        self.assertIn('Descargar Código QR (PDF)', html)
        self.assertIn('value="Pepe"', html)

    def test_editar_post_actualiza_datos(self):
        self._login()
        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'García',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': 0,
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)
        with self.app.app_context():
            alumno = db.session.get(Alumno, self.alumno_id)
            self.assertEqual('García', alumno.lastname_p)

    def test_editar_post_guarda_profesor_asignado(self):
        """El select de profesor persiste el docente asignado al alumno."""
        self._login()
        with self.app.app_context():
            tutor = Docente.get_by_email('edit@example.com')
            tutor_id = tutor.id

        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'López',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': tutor_id,
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            alumno = db.session.get(Alumno, self.alumno_id)
            self.assertEqual(tutor_id, alumno.tutor_id)
            self.assertIsNotNone(alumno.tutor)

        # La boleta muestra al profesor asignado
        res = self.client.get(f'/buscar/{self.alumno_id}')
        html = res.get_data(as_text=True)
        self.assertIn('Docente Edit', html)

    def test_editar_post_quita_profesor_asignado(self):
        """Seleccionar '— Sin asignar —' deja el alumno sin tutor."""
        self._login()
        with self.app.app_context():
            tutor = Docente.get_by_email('edit@example.com')
            alumno = db.session.get(Alumno, self.alumno_id)
            alumno.tutor_id = tutor.id
            db.session.commit()

        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'López',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': 0,
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            alumno = db.session.get(Alumno, self.alumno_id)
            self.assertIsNone(alumno.tutor_id)

    # ── Calificación desde la vista de edición ──────────────────────────
    def test_editar_post_guarda_calificacion(self):
        """El POST con materia_id + calificacion persiste la nota.

        Español está en ``MATERIA_COLUMNS_MAP``: sin registro explícito de
        ``CalificacionMateria``, la nota se escribe en la columna fija del
        esquema ``Calificacion``.
        """
        self._login()
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id

        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'López',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': 0,
            'materia_id': esp_id,
            'calificacion': '9.5',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            alumno = db.session.get(Alumno, self.alumno_id)
            self.assertTrue(alumno.calificaciones)
            self.assertEqual(9.5, float(alumno.calificaciones[0].español))

    def test_editar_post_sin_calificacion_no_toca_nota(self):
        """Sin nota no se crea registro ni se altera la calificación."""
        self._login()
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id

        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'López',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': 0,
            'materia_id': esp_id,
            'calificacion': '',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            alumno = db.session.get(Alumno, self.alumno_id)
            self.assertFalse(alumno.calificaciones)

    def test_editar_get_preselecciona_materia_del_roster(self):
        """GET con ?materia_id= preselecciona la materia en el select."""
        self._login()
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id

        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar?materia_id={esp_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        self.assertIn(f'value="{esp_id}"', html)
        self.assertIn('selected', html)

    # ── Materia fijada desde el roster (?materia_id=) ─────────────────
    def test_editar_con_materia_id_bloquea_el_select(self):
        """Entrar desde el roster de una materia (?materia_id= válido) fija
        la materia: el select se muestra deshabilitado (no cambiable), el
        valor viaja en un input hidden para el POST (los selects con disabled
        no se envían) y se ve el aviso de materia fijada."""
        self._login()
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id

        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar?materia_id={esp_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)

        # El bloque del select de materia está deshabilitado y muestra la materia
        # (se toma desde el <select> completo: el atributo `disabled` puede
        # aparecer antes que id= dentro del tag).
        idx_id = html.index('id="materia_id"')
        idx_sel = html.rindex('<select', 0, idx_id)
        fin = html.index('</select>', idx_id)
        bloque_select = html[idx_sel:fin]
        self.assertIn('disabled', bloque_select)
        self.assertIn('Español', bloque_select)

        # El valor viaja en un input hidden (los selects disabled no se envían):
        # el primer name="materia_id" es el hidden, antes del select.
        self.assertIn('<input type="hidden" name="materia_id"', html)
        idx_hidden = html.index('name="materia_id"')
        self.assertIn(f'value="{esp_id}"', html[idx_hidden:idx_hidden + 120])

        # Aviso visible de que la materia no se puede cambiar
        self.assertIn('Materia fijada desde el listado', html)

    def test_editar_sin_materia_id_no_bloquea_el_select(self):
        """Entrar directo a la edición (sin ?materia_id=) deja el select de
        materia editable, sin hidden ni aviso de fijado."""
        self._login()
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)

        idx_id = html.index('id="materia_id"')
        idx_sel = html.rindex('<select', 0, idx_id)
        fin = html.index('</select>', idx_id)
        self.assertNotIn('disabled', html[idx_sel:fin])
        self.assertNotIn('<input type="hidden" name="materia_id"', html)
        self.assertNotIn('Materia fijada desde el listado', html)

    def test_editar_materia_id_invalido_no_bloquea(self):
        """Un ?materia_id= fuera de las materias disponibles no bloquea
        (anti-IDOR): cae a la primera disponible y el select sigue editable."""
        self._login()
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar?materia_id=999999')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        idx_id = html.index('id="materia_id"')
        idx_sel = html.rindex('<select', 0, idx_id)
        fin = html.index('</select>', idx_id)
        self.assertNotIn('disabled', html[idx_sel:fin])
        self.assertNotIn('<input type="hidden" name="materia_id"', html)

    def test_editar_get_carga_calificacion_actual(self):
        """La nota actual de la materia preseleccionada llega al input."""
        self._login()
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id
            cm = CalificacionMateria(alumnos_id=self.alumno_id, materia_id=esp_id, calificacion=8)
            db.session.add(cm)
            db.session.commit()

        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar?materia_id={esp_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        # El input de calificación debe traer la nota actual (8.0)
        self.assertIn('value="8.0"', html)

    def test_editar_docente_no_califica_materia_fuera_del_curriculum(self):
        """El select de materias se limita al currículum del grupo.

        Regresión del revisor: un docente que imparte Español (en el
        currículum del 9E) y además Historia (fuera del currículum) no debe
        poder calificar Historia desde esta vista. Las materias disponibles
        = intersección (materias del docente ∩ currículum del grupo).
        """
        self._login()
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            hist = Materia.query.filter_by(nombre='Historia').first()
            edit = Docente.get_by_email('edit@example.com')
            edit.materias = [esp, hist]
            db.session.commit()
            esp_id = esp.id
            hist_id = hist.id

        # La vista solo debe ofrecer Español (la materia del currículum).
        # El aserto se acota al bloque del select de materia (en el HTML hay
        # otros selects, como el de grupo, con valores numéricos repetidos).
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        inicio = html.index('id="materia_id"')
        fin = html.index('</select>', inicio)
        select_materia = html[inicio:fin]
        self.assertIn(f'value="{esp_id}"', select_materia)
        self.assertNotIn(f'value="{hist_id}"', select_materia)
        self.assertIn('Español', select_materia)
        self.assertNotIn('Historia', select_materia)

        # Y el POST calificando Historia no debe pasar (opción inválida)
        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'López',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': 0,
            'materia_id': hist_id,
            'calificacion': '9.0',
        }, follow_redirects=False)
        # No redirige: re-render del formulario con error de validación
        self.assertEqual(200, res.status_code)
        with self.app.app_context():
            cm = CalificacionMateria.query.filter_by(
                alumnos_id=self.alumno_id, materia_id=hist_id
            ).first()
            self.assertIsNone(cm)

    # ── Anti-IDOR: quién puede editar ───────────────────────────────────
    def test_editar_denegado_docente_sin_materias(self):
        self._login('nose@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
        self.assertEqual(401, res.status_code)

    def test_editar_denegado_docente_materia_fuera_del_curriculum(self):
        self._login('hist@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
        self.assertEqual(401, res.status_code)

    def test_editar_permite_admin_sin_materias(self):
        self._login('adm@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
        self.assertEqual(200, res.status_code)

    # ── PDF de credencial QR ────────────────────────────────────────────
    def test_qr_pdf_requiere_login(self):
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-pdf', follow_redirects=False)
        self.assertEqual(302, res.status_code)

    def test_qr_pdf_descarga(self):
        self._login()
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-pdf')
        self.assertEqual(200, res.status_code)
        self.assertEqual('application/pdf', res.content_type)
        self.assertTrue(res.data.startswith(b'%PDF'))

    def test_qr_pdf_denegado_docente_sin_materias(self):
        self._login('nose@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-pdf')
        self.assertEqual(401, res.status_code)

    def test_qr_pdf_permite_admin(self):
        self._login('adm@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-pdf')
        self.assertEqual(200, res.status_code)
        self.assertTrue(res.data.startswith(b'%PDF'))

    # ── Imagen PNG de credencial QR ────────────────────────────────────
    def test_qr_imagen_requiere_login(self):
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-imagen', follow_redirects=False)
        self.assertEqual(302, res.status_code)

    def test_qr_imagen_descarga(self):
        self._login()
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-imagen')
        self.assertEqual(200, res.status_code)
        self.assertEqual('image/png', res.content_type)
        # Firma PNG: 8 bytes mágicos
        self.assertTrue(res.data.startswith(b'\x89PNG\r\n\x1a\n'))
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(res.data))
        # Imagen compacta (no carta): lienzo ≈ QR (900px) + margen pequeño,
        # sin grandes zonas en blanco para facilitar el compartir.
        ancho, alto = img.size
        self.assertLess(ancho, 1275)   # ya no es carta (1275 px)
        self.assertLess(alto, 1650)    # ya no es carta (1650 px)
        self.assertGreater(ancho, 700)  # sigue siendo de alta resolución
        self.assertGreater(alto, 700)
        # El contenido (tinta) ocupa casi todo el lienzo
        bbox = img.convert('L').point(lambda p: 255 if p < 200 else 0).getbbox()
        self.assertIsNotNone(bbox)
        l, t, r, b = bbox
        self.assertGreater(r - l, ancho * 0.5)   # el QR domina el ancho
        self.assertGreater(b - t, alto * 0.5)    # QR + nombre dominan el alto

    def test_qr_imagen_optimizada(self):
        """La imagen PNG sale comprimida (paleta sin dithering): pesa una
        fracción del RGB original y conserva el contenido."""
        self._login()
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-imagen')
        self.assertEqual(200, res.status_code)
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(res.data))
        # Paleta indexada (P) y mucho más ligera que los ~70 KiB del RGB
        self.assertEqual('P', img.mode)
        self.assertLess(len(res.data), 40 * 1024)
        self.assertGreater(len(res.data), 5 * 1024)
        # El contenido sigue ahí: tinta en QR y nombre
        bbox = img.convert('L').point(lambda p: 255 if p < 200 else 0).getbbox()
        self.assertIsNotNone(bbox)
        l, t, r, b = bbox
        self.assertGreater(r - l, img.size[0] * 0.5)
        self.assertGreater(b - t, img.size[1] * 0.5)

    def test_qr_imagen_nombre_largo_mantiene_proporcion(self):
        """Un nombre largo no ensancha la imagen: la fuente se escala para
        que el lienzo siga siendo compacto (ancho ≈ QR + margen)."""
        self._login()
        with self.app.app_context():
            alumno = db.session.get(Alumno, self.alumno_id)
            # Nombre largo (50 chars = límite de la columna) que dispara
            # el escalado de fuente para no ensanchar el lienzo.
            alumno.name = 'Guadalupe del Rosario Hernandez Gonzalez Lopez'[:50]
            db.session.commit()
            alumno_id = alumno.id

        try:
            res = self.client.get(f'/docente/alumno/{alumno_id}/qr-imagen')
            self.assertEqual(200, res.status_code)
            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(res.data))
            ancho, alto = img.size
            # El lienzo se mantiene compacto: ancho fijo ≈ QR (900) + 2*margen
            self.assertLessEqual(ancho, 1020)
            self.assertLess(alto, 1600)
        finally:
            # Restaurar el nombre: la limpieza idempotente de setUp/tearDown
            # localiza al alumno por name='Pepe'.
            with self.app.app_context():
                alumno = db.session.get(Alumno, alumno_id)
                if alumno is not None:
                    alumno.name = 'Pepe'
                    db.session.commit()

    def test_qr_imagen_denegado_docente_sin_materias(self):
        self._login('nose@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-imagen')
        self.assertEqual(401, res.status_code)

    def test_qr_imagen_permite_admin(self):
        self._login('adm@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/qr-imagen')
        self.assertEqual(200, res.status_code)
        self.assertEqual('image/png', res.content_type)

    # ── Docente que imparte cada materia en la boleta pública ──────────
    def test_boleta_muestra_docente_que_imparte_la_materia(self):
        """La boleta pública muestra el docente que imparte cada materia al
        grupo del alumno (fuente de verdad: horarios docente–materia–grupo)."""
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            edit = Docente.get_by_email('edit@example.com')
            horario = Horario(
                docente_id=edit.id, materia_id=esp.id, grupo_id=self.grupo_id,
                dia_semana=1, hora_inicio=datetime.time(7, 0),
                hora_fin=datetime.time(8, 0), salon='A1',
            )
            db.session.add(horario)
            db.session.commit()
            horario_id = horario.id

        try:
            res = self.client.get(f'/buscar/{self.alumno_id}')
            self.assertEqual(200, res.status_code)
            html = res.get_data(as_text=True)
            self.assertIn('Docente Edit', html)
            # El docente aparece asociado a la materia (mismo contexto)
            idx = html.index('Español')
            self.assertIn('Docente Edit', html[idx:idx + 300])
        finally:
            with self.app.app_context():
                h = db.session.get(Horario, horario_id)
                if h is not None:
                    db.session.delete(h)
                    db.session.commit()

    def test_boleta_sin_horario_no_muestra_docente(self):
        """Sin horario asignado al grupo, la boleta no muestra 'Imparte:'."""
        res = self.client.get(f'/buscar/{self.alumno_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        # El bloque 'Imparte:' no debe aparecer para ninguna materia
        self.assertNotIn('Imparte:', html)

    # ── Docente por materia en la vista de edición ─────────────────────
    def test_editar_muestra_docente_que_imparte_la_materia(self):
        """La vista de edición muestra el docente que imparte la materia
        seleccionada (misma fuente que la boleta: horarios del grupo)."""
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            edit = Docente.get_by_email('edit@example.com')
            horario = Horario(
                docente_id=edit.id, materia_id=esp.id, grupo_id=self.grupo_id,
                dia_semana=1, hora_inicio=datetime.time(7, 0),
                hora_fin=datetime.time(8, 0), salon='A1',
            )
            db.session.add(horario)
            db.session.commit()
            horario_id = horario.id

        try:
            self._login('edit@example.com')
            res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
            self.assertEqual(200, res.status_code)
            html = res.get_data(as_text=True)
            self.assertIn('Imparte:', html)
            self.assertIn('Docente Edit', html)
            # El docente aparece asociado a la materia en el select
            idx = html.index('id="materia_id"')
            bloque = html[idx:idx + 1500]
            self.assertIn('Imparte:', bloque)
            self.assertIn('Docente Edit', bloque)
            # El mapa tojson de docentes viaja en el bloque script (el JS
            # lo usa para actualizar la línea al cambiar de materia). Con
            # comillas -> es el JSON, no el texto servido del div.
            self.assertIn('"Prof. Docente Edit"', html)
        finally:
            with self.app.app_context():
                h = db.session.get(Horario, horario_id)
                if h is not None:
                    db.session.delete(h)
                    db.session.commit()

    def test_editar_sin_horario_no_muestra_docente(self):
        """Sin horario, la vista de edición indica que no hay docentes
        asignados en el horario del grupo (la línea 'Imparte:' del div
        inicial queda en vacío/aviso, no con nombres)."""
        self._login('edit@example.com')
        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        # El div servido en el estado inicial muestra el aviso, no nombres
        idx = html.index('id="imparte-materia"')
        bloque = html[idx:idx + 500]
        self.assertIn('No hay docentes asignados en el horario del grupo.', bloque)
        self.assertNotIn('Prof.', bloque)
        self.assertNotIn('Docente Edit', bloque)

    # ── Nota/comentario del docente por materia ────────────────────────
    def test_editar_post_guarda_nota_texto(self):
        """El POST con nota_texto persiste el comentario del docente."""
        self._login('edit@example.com')
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id

        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'López',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': 0,
            'materia_id': esp_id,
            'nota_texto': 'Muy buen avance este trimestre.',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            cm = CalificacionMateria.query.filter_by(
                alumnos_id=self.alumno_id, materia_id=esp_id
            ).first()
            self.assertIsNotNone(cm)
            self.assertEqual('Muy buen avance este trimestre.', cm.nota_texto)

    def test_boleta_muestra_nota_del_docente(self):
        """La boleta pública muestra la nota compartida del docente."""
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            cm = CalificacionMateria(
                alumnos_id=self.alumno_id, materia_id=esp.id,
                nota_texto='Necesita repasar la tabla de multiplicar.',
            )
            db.session.add(cm)
            db.session.commit()

        res = self.client.get(f'/buscar/{self.alumno_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        self.assertIn('Necesita repasar la tabla de multiplicar.', html)

    def test_nota_texto_no_tapa_calificacion_de_columna_fija(self):
        """Un CalificacionMateria solo con nota NO oculta la calificación
        guardada en la columna fija del esquema (Español → columna 'español')."""
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id
            calif = Calificacion(alumnos_id=self.alumno_id, español=8.5)
            db.session.add(calif)
            db.session.commit()
            # Registro de CalificacionMateria con calificación None (solo nota)
            cm = CalificacionMateria(
                alumnos_id=self.alumno_id, materia_id=esp_id,
                nota_texto='Participa bien en clase.',
            )
            db.session.add(cm)
            db.session.commit()

        res = self.client.get(f'/buscar/{self.alumno_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        # La calificación 8.5 de la columna fija sigue apareciendo
        self.assertIn('8.5', html)
        # Y la nota de texto también
        self.assertIn('Participa bien en clase.', html)

    def test_editar_get_carga_nota_actual(self):
        """El GET de edición carga la nota del docente en el textarea."""
        self._login('edit@example.com')
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id
            cm = CalificacionMateria(
                alumnos_id=self.alumno_id, materia_id=esp_id,
                nota_texto='Observación previa guardada.',
            )
            db.session.add(cm)
            db.session.commit()

        res = self.client.get(f'/docente/alumno/{self.alumno_id}/editar?materia_id={esp_id}')
        self.assertEqual(200, res.status_code)
        html = res.get_data(as_text=True)
        self.assertIn('Observación previa guardada.', html)

    def test_editar_post_nota_vacia_borra_la_nota(self):
        """Enviar nota_texto vacía borra la nota anterior de la materia."""
        self._login('edit@example.com')
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id
            cm = CalificacionMateria(
                alumnos_id=self.alumno_id, materia_id=esp_id,
                nota_texto='Se borrará.',
            )
            db.session.add(cm)
            db.session.commit()

        res = self.client.post(f'/docente/alumno/{self.alumno_id}/editar', data={
            'name': 'Pepe',
            'lastname_p': 'López',
            'lastname_m': 'Mora',
            'genero': 'M',
            'group_id': self.grupo_id,
            'password': 'CODIGO1234',
            'tutor_id': 0,
            'materia_id': esp_id,
            'nota_texto': '',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            cm = CalificacionMateria.query.filter_by(
                alumnos_id=self.alumno_id, materia_id=esp_id
            ).first()
            self.assertIsNotNone(cm)
            self.assertIsNone(cm.nota_texto)

    # ── Nota por materia en el roster (reemplaza a la anotación global) ──
    def test_api_roster_incluye_nota_por_materia(self):
        """El roster de la materia incluye la nota/comentario por materia
        (``nota_texto_materia``) y ya NO serializa la anotación global antigua
        (``nota_texto``)."""
        self._login('adm@example.com')
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id
            cm = CalificacionMateria(
                alumnos_id=self.alumno_id, materia_id=esp_id,
                nota_texto='Nota por materia del roster.',
            )
            db.session.add(cm)
            db.session.commit()

        res = self.client.get(f'/api/materia/{esp_id}/alumnos')
        self.assertEqual(200, res.status_code)
        data = res.get_json()
        alumno = next(a for a in data['alumnos'] if a['id'] == self.alumno_id)
        self.assertEqual('Nota por materia del roster.', alumno['nota_texto_materia'])
        # La anotación global quedó en desuso: no debe serializarse
        self.assertNotIn('nota_texto', alumno)

    def test_api_update_docente_guarda_nota_por_materia(self):
        """El endpoint update_docente guarda la nota/comentario por materia
        (la misma que la boleta y la vista de edición)."""
        self._login('edit@example.com')
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id

        res = self.client.post(f'/api/alumno/{self.alumno_id}/update_docente', json={
            'materia_nombre': 'Español',
            'nota_texto': 'Muy buen avance este trimestre.',
        })
        self.assertEqual(200, res.status_code)
        payload = res.get_json()
        self.assertTrue(payload['success'])
        # La respuesta devuelve la nota normalizada (lo que el frontend muestra)
        self.assertEqual('Muy buen avance este trimestre.', payload['nota_texto_materia'])

        with self.app.app_context():
            cm = CalificacionMateria.query.filter_by(
                alumnos_id=self.alumno_id, materia_id=esp_id
            ).first()
            self.assertIsNotNone(cm)
            self.assertEqual('Muy buen avance este trimestre.', cm.nota_texto)

    def test_api_update_docente_nota_vacia_borra_la_nota(self):
        """Enviar nota_texto vacía por update_docente borra la nota de la materia."""
        self._login('edit@example.com')
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id
            cm = CalificacionMateria(
                alumnos_id=self.alumno_id, materia_id=esp_id,
                nota_texto='Se borrará.',
            )
            db.session.add(cm)
            db.session.commit()

        res = self.client.post(f'/api/alumno/{self.alumno_id}/update_docente', json={
            'materia_nombre': 'Español',
            'nota_texto': '',
        })
        self.assertEqual(200, res.status_code)

        with self.app.app_context():
            cm = CalificacionMateria.query.filter_by(
                alumnos_id=self.alumno_id, materia_id=esp_id
            ).first()
            self.assertIsNotNone(cm)
            self.assertIsNone(cm.nota_texto)

    def test_api_nota_antigua_eliminada(self):
        """El endpoint de la anotación global antigua ya no existe (404)."""
        self._login('edit@example.com')
        res = self.client.post(f'/api/alumno/{self.alumno_id}/nota', json={
            'texto': 'X', 'materia_nombre': 'Español',
        })
        self.assertEqual(404, res.status_code)

    # ── Escala de colores de la boleta pública ─────────────────────────
    def test_boleta_colores_calificaciones(self):
        """10-9 verde, 8-7 amarillo, 6 o menos rojo (boleta pública)."""
        with self.app.app_context():
            esp = Materia.query.filter_by(nombre='Español').first()
            esp_id = esp.id
            for nota, clase in [
                (10, 'bg-[#0bb218]'),
                (9, 'bg-[#0bb218]'),
                (9.5, 'bg-[#0bb218]'),
                (8, 'bg-[#f59e0b]'),
                (7, 'bg-[#f59e0b]'),
                (7.5, 'bg-[#f59e0b]'),
                (6, 'bg-[#ef4444]'),
                (5.9, 'bg-[#ef4444]'),
                (0, 'bg-[#ef4444]'),
            ]:
                cm = CalificacionMateria.query.filter_by(
                    alumnos_id=self.alumno_id, materia_id=esp_id
                ).first()
                if cm is None:
                    cm = CalificacionMateria(alumnos_id=self.alumno_id, materia_id=esp_id)
                    db.session.add(cm)
                cm.calificacion = nota
                db.session.commit()

                res = self.client.get(f'/buscar/{self.alumno_id}')
                self.assertEqual(200, res.status_code)
                html = res.get_data(as_text=True)
                self.assertIn(clase, html, f'nota {nota} debe usar {clase}')


if __name__ == '__main__':
    unittest.main()
