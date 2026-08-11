"""Regresión anti N+1: los listados deben usar un número FIJO de consultas.

Si un endpoint vuelve a consultar relaciones perezosamente por fila
(N+1), el conteo de consultas SQL se dispara con el número de registros
(decenas/cientos), mientras que con eager loading y consultas en lote se
mantiene en un tope pequeño y constante. Estos tests fijan ese tope.
"""

import datetime
import unittest

from sqlalchemy import event

from app import create_app, db
from app.auth.models import Docente
from app.models import Alumno, CalificacionMateria, Grupos, Horario, Materia


class _QueryCounter:
    """Cuenta las consultas SQL emitidas contra un engine."""

    def __init__(self, engine):
        self._engine = engine
        self.count = 0
        self._listening = False

    def start(self):
        if self._listening:  # evita doble attach y conteo duplicado
            return
        self.count = 0
        self._listening = True
        event.listen(self._engine, 'before_cursor_execute', self._on_query)

    def stop(self):
        if self._listening:
            event.remove(self._engine, 'before_cursor_execute', self._on_query)
            self._listening = False

    def _on_query(self, *args, **kwargs):
        self.count += 1


class AntiN1RegressionTestCase(unittest.TestCase):
    """Los listados optimizados no superan un tope fijo de consultas.

    El tope es deliberadamente pequeño y NO escala con el número de
    registros: un listado con N alumnos/grupos cuesta lo mismo con 10 o
    con 1000 filas. Si se reintroduce un acceso perezoso por fila, el
    conteo se dispara y este test falla.
    """

    # URL → tope máximo de consultas SQL por request.
    # Valores medidos hoy (72 alumnos / ~60 grupos en la BD de testing):
    #   /api/admin/alumnos ......... 6   /api/materia/<id>/alumnos .... 8
    #   /admin/alumnos/ ............. 3   /api/docente/<id>/datos ..... 4
    #   /admin/grupos/ .............. 4   /api/docente/<id>/horario ... 3
    #   /admin/docentes/ ............ 2   /docente/ ................... 3
    #   /calificaciones (código válido) 7   /calificaciones (inválido) . 2
    #   /buscar/ .................... 1
    # Los topes dan ~2× de holgura; una regresión N+1 multiplicaría el
    # conteo por el número de filas (60-300+), muy por encima del tope.
    MAX_QUERIES = {
        '/api/admin/alumnos': 15,
        '/admin/alumnos/': 10,
        '/admin/grupos/': 10,
        '/admin/docentes/': 8,
        '/api/docente/<id>/datos': 10,
        '/api/docente/<id>/horario': 10,
        '/docente/': 10,
        '/calificaciones?codigoAlumno=<valido>': 15,
        '/calificaciones?codigoAlumno=<invalido>': 5,
        '/buscar/': 5,
    }

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()

        with self.app.app_context():
            self.engine = db.engine

            # Limpieza idempotente de corridas previas (incluso a medias)
            self._limpiar_datos_temporales()

            # Admin de pruebas (idempotente, mismo patrón que test_auth_routes)
            Docente.query.filter_by(email='admin@example.com').delete(synchronize_session=False)
            db.session.commit()
            admin = Docente(name='Admin', email='admin@example.com', apellidos='Sistema')
            admin.set_password('123456')
            admin.save()

            # Docente temporal con materia + horario para las APIs de docente.
            # Así la plantilla del panel accede a h.materia por fila y el test
            # cubre de verdad el N+1 de horarios.
            self.docente = Docente('Doc N1', 'n1-temp@escuela.test', 'Temporal')
            self.docente.set_password('N1Temp123!')
            db.session.add(self.docente)
            db.session.commit()

            materias = Materia.query.limit(2).all()
            self.materia_id = materias[0].id if materias else None
            self.docente.materias = materias
            if materias:
                db.session.add(Horario(
                    self.docente.id, materias[0].id, 1,
                    datetime.time(7, 0), datetime.time(8, 0), 'A1',
                ))

            # Grupo + alumno temporales para la boleta pública: con un
            # currículum de 2 materias y una nota, así _materias_alumno y
            # _get_nota_materia ejercitan sus accesos perezosos de verdad.
            grupo_boleta = Grupos(grado='3', grupo='Z')
            db.session.add(grupo_boleta)
            db.session.commit()
            grupo_boleta.materias = materias
            alumno_boleta = Alumno(
                name='N1', lastname_p='Boleta', lastname_m='Prueba',
                group_id=grupo_boleta.id, genero='M', password='N1BOLETA1',
            )
            db.session.add(alumno_boleta)
            db.session.commit()
            if materias:
                db.session.add(CalificacionMateria(
                    alumnos_id=alumno_boleta.id,
                    materia_id=materias[0].id,
                    calificacion=9.5,
                ))

            db.session.commit()
            # Guardar ids como enteros: fuera del contexto el ORM queda
            # detachado y acceder a .id dispararía DetachedInstanceError
            self.docente_id = self.docente.id
            self.alumno_codigo = alumno_boleta.password
            # Código inválido garantizado: los códigos reales se generan con
            # mayúsculas + dígitos (app.utils.codes), así que una cadena de
            # minúsculas nunca coincide con un alumno existente.
            self.codigo_invalido = 'xxxxxxxxxx'

        self.client.post('/login', data={'email': 'admin@example.com', 'password': '123456'})

    def _limpiar_datos_temporales(self):
        """Elimina (idempotente) los datos temporales del test.

        Requiere un contexto de app activo. Orden correcto por FKs:
        calificaciones_materia → alumno → grupo. También recupera una
        corrida previa que quedara a medias (alumno/grupo huérfanos).
        """
        d = Docente.get_by_email('n1-temp@escuela.test')
        if d:
            Horario.query.filter_by(docente_id=d.id).delete(synchronize_session=False)
            db.session.delete(d)
        a = Alumno.query.filter_by(password='N1BOLETA1').first()
        if a:
            CalificacionMateria.query.filter_by(alumnos_id=a.id).delete(synchronize_session=False)
            db.session.delete(a)
        g = Grupos.query.filter_by(grado='3', grupo='Z').first()
        if g:
            g.materias = []
            db.session.delete(g)
        db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            self._limpiar_datos_temporales()

    def _get_con_contador(self, url):
        """Ejecuta un GET y devuelve (respuesta, nº de consultas SQL)."""
        counter = _QueryCounter(self.engine)
        counter.start()
        try:
            res = self.client.get(url)
        finally:
            counter.stop()
        return res, counter.count

    def test_listados_optimizados_mantienen_consultas_fijas(self):
        """Ningún listado optimizado supera su tope de consultas SQL."""
        urls = {
            '/api/admin/alumnos': self.MAX_QUERIES['/api/admin/alumnos'],
            '/admin/alumnos/': self.MAX_QUERIES['/admin/alumnos/'],
            '/admin/grupos/': self.MAX_QUERIES['/admin/grupos/'],
            '/admin/docentes/': self.MAX_QUERIES['/admin/docentes/'],
        }
        # URLs con ids reales (los placeholders <id> solo documentan el tope)
        if self.materia_id:
            urls[f'/api/materia/{self.materia_id}/alumnos'] = 15
        urls[f'/api/docente/{self.docente_id}/datos'] = self.MAX_QUERIES['/api/docente/<id>/datos']
        urls[f'/api/docente/{self.docente_id}/horario'] = self.MAX_QUERIES['/api/docente/<id>/horario']

        for url, tope in urls.items():
            with self.subTest(url=url):
                res, n = self._get_con_contador(url)
                self.assertEqual(res.status_code, 200, f'{url} no respondió 200')
                self.assertLessEqual(
                    n, tope,
                    f'{url} disparó {n} consultas SQL (tope {tope}). Posible '
                    f'regresión N+1: precarga las relaciones con '
                    f'selectinload/joinedload y haz los conteos en lote, '
                    f'no por fila.',
                )

    def test_boleta_publica_con_codigo_valido_mantiene_consultas_fijas(self):
        """La boleta pública con código válido no dispara consultas desmedidas."""
        if not self.materia_id:
            self.skipTest('BD sin materias: la boleta no ejercitaría el currículum')
        url = f'/calificaciones?codigoAlumno={self.alumno_codigo}'
        res, n = self._get_con_contador(url)
        self.assertEqual(res.status_code, 200, f'{url} no respondió 200')
        self.assertLessEqual(
            n, self.MAX_QUERIES['/calificaciones?codigoAlumno=<valido>'],
            f'{url} disparó {n} consultas SQL. Posible regresión: revisa '
            f'_materias_alumno/_get_nota_materia (accesos perezosos por '
            f'materia/registro en vez de precarga).',
        )

    def test_boleta_codigo_invalido_y_buscador_mantienen_consultas_fijas(self):
        """Código inexistente y página de búsqueda no añaden consultas."""
        url_invalido = f'/calificaciones?codigoAlumno={self.codigo_invalido}'
        res, n = self._get_con_contador(url_invalido)
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(
            n, self.MAX_QUERIES['/calificaciones?codigoAlumno=<invalido>'],
            f'{url_invalido} disparó {n} consultas SQL.',
        )

        res, n = self._get_con_contador('/buscar/')
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(
            n, self.MAX_QUERIES['/buscar/'],
            f'/buscar/ disparó {n} consultas SQL.',
        )

    def test_panel_docente_con_horario_mantiene_consultas_fijas(self):
        """El panel /docente/ (con horario) no dispara N+1 por materia."""
        if not self.materia_id:
            self.skipTest('BD sin materias: no se pudo crear el horario de prueba')
        self.client.get('/logout')
        self.client.post('/login', data={'email': 'n1-temp@escuela.test', 'password': 'N1Temp123!'})

        res, n = self._get_con_contador('/docente/')
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(
            n, self.MAX_QUERIES['/docente/'],
            f'/docente/ disparó {n} consultas SQL (tope '
            f'{self.MAX_QUERIES["/docente/"]}). Posible regresión N+1 en '
            f'horarios: revisa el joinedload(Horario.materia).',
        )


if __name__ == '__main__':
    unittest.main()
