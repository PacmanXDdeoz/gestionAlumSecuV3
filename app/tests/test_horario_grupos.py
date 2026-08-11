import datetime
import unittest

from sqlalchemy import inspect, text

from app import create_app, db
from app.auth.models import Docente, Rol
from app.models import Alumno, Grupos, Horario, Materia


class HorarioGruposTestCase(unittest.TestCase):
    """Filtro del roster por los grupos del docente (horarios.grupo_id).

    Un docente solo ve los alumnos de los grupos donde imparte la materia
    según su horario. Sin horario asignado para la materia, el roster es
    vacío (estricto). Misma convención de limpieza que el resto de tests:
    solo borra los datos creados por este test (nunca db.drop_all()).
    """

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS alejandra'))
            db.create_all()
            Rol.seed_defaults()

            # ── Limpieza idempotente de corridas previas ──
            for email in ('d1@example.com', 'd2@example.com', 'admh@example.com'):
                d = Docente.get_by_email(email)
                if d is not None:
                    Horario.query.filter_by(docente_id=d.id).delete(synchronize_session=False)
                    db.session.delete(d)
            Alumno.query.filter_by(name='GrupoH').delete()
            Alumno.query.filter_by(name='GrupoI').delete()
            for g in Grupos.query.filter(Grupos.grado == '9', Grupos.grupo.in_(['H', 'I'])).all():
                g.materias = []
                db.session.delete(g)
            m = Materia.query.filter_by(nombre='Español').first()
            if m is not None:
                m.grupos = []
                m.docentes = []
            db.session.commit()

            # ── Materia del catálogo (se reutiliza si existe) ──
            self.materias_creadas = []
            esp = Materia.query.filter_by(nombre='Español').first()
            if esp is None:
                esp = Materia(nombre='Español', descripcion='Lengua')
                db.session.add(esp)
                self.materias_creadas.append('Español')
            db.session.flush()
            self.materia_id = esp.id

            # ── Grupos 9H y 9I (ambos con Español en su currículum) ──
            g_h = Grupos(grado='9', grupo='H')
            g_i = Grupos(grado='9', grupo='I')
            db.session.add_all([g_h, g_i])
            db.session.flush()
            g_h.materias = [esp]
            g_i.materias = [esp]

            # ── Alumnos: uno en cada grupo ──
            a_h = Alumno(name='GrupoH', lastname_p='Uno', lastname_m='Test',
                         group_id=g_h.id, genero='M', password='GRUPOH001')
            a_i = Alumno(name='GrupoI', lastname_p='Dos', lastname_m='Test',
                         group_id=g_i.id, genero='M', password='GRUPOI001')
            db.session.add_all([a_h, a_i])
            db.session.flush()
            self.alumno_h_id = a_h.id
            self.alumno_i_id = a_i.id
            self.grupo_h_id = g_h.id
            self.grupo_i_id = g_i.id

            # ── Docente 1: imparte Español SOLO en 9H (horario con grupo) ──
            d1 = Docente(name='Docente Grupos', email='d1@example.com', rol=2)
            d1.set_password('123456')
            d1.materias = [esp]
            db.session.add(d1)
            db.session.flush()
            db.session.add(Horario(
                docente_id=d1.id, materia_id=esp.id, grupo_id=g_h.id,
                dia_semana=1,
                hora_inicio=datetime.time(7, 0),
                hora_fin=datetime.time(8, 0),
                salon='A1',
            ))

            # ── Docente 2: con la materia pero SIN horario ──
            d2 = Docente(name='Docente Sin Horario', email='d2@example.com', rol=2)
            d2.set_password('123456')
            d2.materias = [esp]
            db.session.add(d2)

            # ── Admin ──
            adm = Docente(name='Admin Horarios', email='admh@example.com', rol=1)
            adm.set_password('123456')
            db.session.add(adm)
            db.session.commit()

            # IDs como enteros (fuera del contexto el ORM queda detachado)
            self.docente_1_id = d1.id
            self.docente_2_id = d2.id
            self.admin_id = adm.id

    def tearDown(self):
        with self.app.app_context():
            for email in ('d1@example.com', 'd2@example.com', 'admh@example.com'):
                d = Docente.get_by_email(email)
                if d is not None:
                    Horario.query.filter_by(docente_id=d.id).delete(synchronize_session=False)
                    db.session.delete(d)
            Alumno.query.filter_by(name='GrupoH').delete()
            Alumno.query.filter_by(name='GrupoI').delete()
            for g in Grupos.query.filter(Grupos.grado == '9', Grupos.grupo.in_(['H', 'I'])).all():
                g.materias = []
                db.session.delete(g)
            for nombre in self.materias_creadas:
                Materia.query.filter_by(nombre=nombre).delete()
            db.session.commit()
            db.session.remove()

    def _login(self, email):
        return self.client.post('/login', data={
            'email': email,
            'password': '123456',
        }, follow_redirects=False)

    # ── Migración: la columna grupo_id existe en horarios ───────────────
    def test_horarios_tiene_columna_grupo_id(self):
        with self.app.app_context():
            cols = inspect(db.engine).get_columns('horarios', schema='alejandra')
            nombres = {c['name'] for c in cols}
            self.assertIn('grupo_id', nombres)

    # ── Filtro del roster por los grupos del docente ────────────────────
    def test_roster_docente_filtrado_por_sus_grupos(self):
        self._login('d1@example.com')
        res = self.client.get(f'/api/materia/{self.materia_id}/alumnos')
        self.assertEqual(200, res.status_code)
        data = res.get_json()
        self.assertTrue(data['filtrado_por_docente'])
        ids = [a['id'] for a in data['alumnos']]
        self.assertIn(self.alumno_h_id, ids)
        self.assertNotIn(self.alumno_i_id, ids)

    def test_roster_docente_sin_horario_es_vacio(self):
        self._login('d2@example.com')
        res = self.client.get(f'/api/materia/{self.materia_id}/alumnos')
        self.assertEqual(200, res.status_code)
        data = res.get_json()
        self.assertTrue(data['filtrado_por_docente'])
        self.assertEqual([], data['alumnos'])

    def test_roster_admin_ve_ambos_grupos_por_curriculum(self):
        self._login('admh@example.com')
        res = self.client.get(f'/api/materia/{self.materia_id}/alumnos')
        self.assertEqual(200, res.status_code)
        data = res.get_json()
        self.assertFalse(data['filtrado_por_docente'])
        self.assertTrue(data['curriculum_filtrado'])
        ids = [a['id'] for a in data['alumnos']]
        self.assertIn(self.alumno_h_id, ids)
        self.assertIn(self.alumno_i_id, ids)

    # ── CRUD de horarios en el admin ────────────────────────────────────
    def test_admin_horarios_requiere_admin(self):
        self._login('d1@example.com')
        res = self.client.get('/admin/horarios/', follow_redirects=False)
        self.assertEqual(401, res.status_code)

    def test_admin_crud_horario(self):
        self._login('admh@example.com')

        # Crear
        res = self.client.post('/admin/horarios/nuevo/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_i_id,
            'dia_semana': 3,
            'hora_inicio': '09:00',
            'hora_fin': '10:00',
            'salon': 'B2',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            h = Horario.query.filter_by(docente_id=self.docente_1_id,
                                        dia_semana=3).first()
            self.assertIsNotNone(h)
            self.assertEqual(self.grupo_i_id, h.grupo_id)
            horario_id = h.id

        # Editar (cambiar de grupo)
        res = self.client.post(f'/admin/horarios/{horario_id}/editar/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_h_id,
            'dia_semana': 4,
            'hora_inicio': '09:00',
            'hora_fin': '10:00',
            'salon': 'B2',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

        with self.app.app_context():
            h = db.session.get(Horario, horario_id)
            self.assertEqual(self.grupo_h_id, h.grupo_id)
            self.assertEqual(4, h.dia_semana)

        # Eliminar
        res = self.client.post(f'/admin/horarios/{horario_id}/eliminar/', follow_redirects=False)
        self.assertEqual(302, res.status_code)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Horario, horario_id))

    def test_admin_horario_rechaza_hora_invalida(self):
        self._login('admh@example.com')
        res = self.client.post('/admin/horarios/nuevo/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_h_id,
            'dia_semana': 1,
            'hora_inicio': '99:99',
            'hora_fin': '10:00',
            'salon': 'A1',
        }, follow_redirects=False)
        self.assertEqual(200, res.status_code)
        self.assertIn('Formato de hora inválido', res.get_data(as_text=True))

    # ── Anti-solapamiento: un docente no puede tener dos clases a la vez ──
    def test_admin_horario_rechaza_solapamiento(self):
        """Una clase que se cruza con otra del mismo docente (mismo día)
        debe rechazarse con mensaje de superposición."""
        self._login('admh@example.com')
        # El docente 1 ya tiene clase Lunes 07:00–08:00 (setUp)
        res = self.client.post('/admin/horarios/nuevo/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_i_id,
            'dia_semana': 1,  # mismo día (Lunes)
            'hora_inicio': '07:30',  # se cruza con 07:00–08:00
            'hora_fin': '08:30',
            'salon': 'B2',
        }, follow_redirects=False)
        self.assertEqual(200, res.status_code)
        self.assertIn('se superponen', res.get_data(as_text=True))

    def test_admin_horario_permite_no_solapado(self):
        """Una clase en otro día o en horas que no se cruzan sí se acepta."""
        self._login('admh@example.com')
        res = self.client.post('/admin/horarios/nuevo/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_i_id,
            'dia_semana': 2,  # martes: día distinto
            'hora_inicio': '07:00',
            'hora_fin': '08:00',
            'salon': 'B2',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

    def test_admin_horario_permite_clases_contiguas_mismo_dia(self):
        """Dos clases seguidas (07:00–08:00 y 08:00–09:00) del mismo docente
        el mismo día NO se consideran solapadas (intervalos [inicio, fin))."""
        self._login('admh@example.com')
        # El docente 1 ya tiene clase Lunes 07:00–08:00 (setUp); una clase
        # que empieza justo donde termina la anterior debe aceptarse.
        res = self.client.post('/admin/horarios/nuevo/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_i_id,
            'dia_semana': 1,
            'hora_inicio': '08:00',
            'hora_fin': '09:00',
            'salon': 'B2',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

    def test_admin_horario_editar_sin_autobloqueo(self):
        """Al editar, el propio horario no cuenta como solapado."""
        self._login('admh@example.com')
        with self.app.app_context():
            h = Horario.query.filter_by(docente_id=self.docente_1_id,
                                        dia_semana=1).first()
            horario_id = h.id
        # Mismo día y mismas horas (sin cambios reales) → debe aceptarse
        res = self.client.post(f'/admin/horarios/{horario_id}/editar/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_h_id,
            'dia_semana': 1,
            'hora_inicio': '07:00',
            'hora_fin': '08:00',
            'salon': 'A1',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

    def test_admin_horario_editar_rechaza_solapamiento_con_otro(self):
        """Editar hacia horas que cruzan otra clase del docente se rechaza."""
        self._login('admh@example.com')
        # Crear una segunda clase el lunes 08:00–09:00
        res = self.client.post('/admin/horarios/nuevo/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_i_id,
            'dia_semana': 1,
            'hora_inicio': '08:00',
            'hora_fin': '09:00',
            'salon': 'B2',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)
        with self.app.app_context():
            h = Horario.query.filter_by(docente_id=self.docente_1_id,
                                        dia_semana=1).order_by(Horario.hora_inicio).first()
            primer_id = h.id
        # Mover la PRIMERA clase (07:00–08:00) a 08:30–09:30: cruza la segunda
        res = self.client.post(f'/admin/horarios/{primer_id}/editar/', data={
            'docente_id': self.docente_1_id,
            'materia_id': self.materia_id,
            'grupo_id': self.grupo_h_id,
            'dia_semana': 1,
            'hora_inicio': '08:30',
            'hora_fin': '09:30',
            'salon': 'A1',
        }, follow_redirects=False)
        self.assertEqual(200, res.status_code)
        self.assertIn('se superponen', res.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
