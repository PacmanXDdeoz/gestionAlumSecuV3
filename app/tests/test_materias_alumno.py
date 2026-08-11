"""Tests del filtro por currículum del grupo en la boleta (_materias_alumno)

y del catálogo de materias por defecto (MATERIAS_DEFAULT).

Cubre: grupo con currículum (solo sus materias), grupo sin currículum,
alumno sin grupo, ruta CalificacionMateria filtrada, materia del grupo
sin nota y el seed de materias por defecto.
"""
import unittest

from app import create_app
from app.models import (
    Alumno,
    Calificacion,
    CalificacionMateria,
    Grupos,
    Materia,
    MATERIAS_DEFAULT,
)
from app.public.routes import (
    MATERIA_COLUMNS_MAP,
    _get_nota_materia,
    _get_nota_texto_materia,
    _grupo_tiene_curriculum,
    _grupos_con_materia,
    _materias_alumno,
    _set_nota_materia,
)


class MockMateria:
    def __init__(self, nombre, id):
        self.nombre = nombre
        self.id = id


class MockGroup:
    def __init__(self, materias=None):
        self._materias = materias or []

    @property
    def materias(self):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self._materias

    def first(self):
        return self._materias[0] if self._materias else None


class MockCalificacionMateria:
    def __init__(self, nombre, calificacion, nota_texto=None):
        self.materia = MockMateria(nombre, 0)
        self.calificacion = calificacion
        self.nota_texto = nota_texto


class MockCalificacion:
    def __init__(self, **notas):
        for key, value in notas.items():
            setattr(self, key, value)


class MockAlumno:
    def __init__(self, grupo=None, calificaciones_materia=None, calificaciones=None):
        self.grupo_info = grupo
        self.calificaciones_materia = calificaciones_materia or []
        self.calificaciones = calificaciones or []


class MockMateriaRoster:
    def __init__(self, grupos=None):
        self._grupos = grupos or []

    @property
    def grupos(self):
        return self

    def all(self):
        return self._grupos


class MockGrupoRoster:
    def __init__(self, id):
        self.id = id


class MateriasAlumnoTestCase(unittest.TestCase):

    def setUp(self):
        self.calificacion = MockCalificacion(español=9, matematicas=8, ciencias=7)

    def test_grupo_con_curriculum_solo_muestra_sus_materias(self):
        grupo = MockGroup([MockMateria('Español', 1), MockMateria('Matemáticas', 2)])
        alumno = MockAlumno(grupo=grupo, calificaciones=[self.calificacion])

        materias = _materias_alumno(alumno)

        self.assertEqual(['Español', 'Matemáticas'], [m['nombre'] for m in materias])
        self.assertEqual(9.0, materias[0]['nota'])
        self.assertEqual(8.0, materias[1]['nota'])

    def test_grupo_sin_curriculum_muestra_catalogo_completo(self):
        alumno = MockAlumno(grupo=MockGroup([]), calificaciones=[self.calificacion])
        self.assertEqual(13, len(_materias_alumno(alumno)))

    def test_alumno_sin_grupo_muestra_catalogo_completo(self):
        alumno = MockAlumno(grupo=None, calificaciones=[self.calificacion])
        self.assertEqual(13, len(_materias_alumno(alumno)))
        # El mapa de columnas fijas solo cubre las materias con columna
        self.assertEqual(8, len(MATERIA_COLUMNS_MAP))

    def test_calificacion_materia_filtrada_por_grupo(self):
        grupo = MockGroup([MockMateria('Español', 1), MockMateria('Ciencias', 3)])
        alumno = MockAlumno(
            grupo=grupo,
            calificaciones_materia=[
                MockCalificacionMateria('Español', 9.5),
                MockCalificacionMateria('Historia', 6),
            ],
        )

        materias = _materias_alumno(alumno)

        # Historia queda fuera porque no pertenece al currículum del grupo
        self.assertEqual(['Español', 'Ciencias'], [m['nombre'] for m in materias])
        self.assertEqual(9.5, materias[0]['nota'])
        self.assertIsNone(materias[1]['nota'])

    def test_materia_del_grupo_sin_nota(self):
        alumno = MockAlumno(
            grupo=MockGroup([MockMateria('Historia', 4)]),
            calificaciones=[self.calificacion],
        )

        materias = _materias_alumno(alumno)

        self.assertEqual('Historia', materias[0]['nombre'])
        self.assertIsNone(materias[0]['nota'])


class GruposConMateriaTestCase(unittest.TestCase):
    """Tests del filtro de roster por currículum (_grupos_con_materia)."""

    def test_materia_con_grupos_devuelve_sus_ids(self):
        materia = MockMateriaRoster([MockGrupoRoster(1), MockGrupoRoster(3)])
        self.assertEqual([1, 3], _grupos_con_materia(materia))

    def test_materia_sin_grupos_devuelve_none(self):
        """Sin currículum configurado → None (fallback al roster completo)."""
        self.assertIsNone(_grupos_con_materia(MockMateriaRoster([])))


class NotasMateriaTestCase(unittest.TestCase):
    """Tests de lectura/escritura de notas con mocks (sin BD)."""

    def test_get_nota_lee_columna_fija_para_materia_mapeada(self):
        alumno = MockAlumno(calificaciones=[MockCalificacion(español=9.5)])
        self.assertEqual(9.5, _get_nota_materia(alumno, 'Español'))

    def test_get_nota_lee_calificacion_materia_con_prioridad(self):
        alumno = MockAlumno(
            calificaciones=[MockCalificacion(español=9.5)],
            calificaciones_materia=[MockCalificacionMateria('Español', 7.0)],
        )
        # El registro explícito de CalificacionMateria gana sobre la columna
        self.assertEqual(7.0, _get_nota_materia(alumno, 'Español'))

    def test_get_nota_cm_sin_calificacion_cae_a_columna_fija(self):
        """Un CalificacionMateria con calificación None (solo nota de texto)
        no tapa la calificación de la columna fija."""
        alumno = MockAlumno(
            calificaciones=[MockCalificacion(español=9.5)],
            calificaciones_materia=[MockCalificacionMateria('Español', None, nota_texto='Nota')],
        )
        self.assertEqual(9.5, _get_nota_materia(alumno, 'Español'))

    def test_get_nota_texto_devuelve_el_comentario(self):
        alumno = MockAlumno(
            calificaciones_materia=[MockCalificacionMateria('Español', 7.0, nota_texto='Bien')],
        )
        self.assertEqual('Bien', _get_nota_texto_materia(alumno, 'Español'))

    def test_get_nota_texto_sin_comentario_devuelve_vacio(self):
        alumno = MockAlumno(calificaciones=[MockCalificacion(español=9.5)])
        self.assertEqual('', _get_nota_texto_materia(alumno, 'Español'))

    def test_get_nota_materia_sin_columna_devuelve_none(self):
        alumno = MockAlumno(calificaciones=[MockCalificacion(español=9.5)])
        self.assertIsNone(_get_nota_materia(alumno, 'Biología'))


class AlmacenamientoNotasIntegracionTestCase(unittest.TestCase):
    """Tests de _set_nota_materia/_get_nota_materia contra la BD real de testing.

    Verifica el arreglo del flujo completo: una materia del catálogo sin
    columna fija (p. ej. Biología) se guarda en CalificacionMateria en vez
    de descartarse silenciosamente.
    """

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.grupo = Grupos(grado='9', grupo='Z')
        self.grupo.save()
        self.alumno = Alumno(
            name='Test', lastname_p='Uno', lastname_m='Dos',
            group_id=self.grupo.id, genero='M', password='TESTOK1234',
        )
        self.alumno.save()

        # Materias del catálogo (sembradas por la migración de seed)
        self.espanol = Materia.query.filter_by(nombre='Español').first()
        self.biologia = Materia.query.filter_by(nombre='Biología').first()

    def tearDown(self):
        alumno = getattr(self, 'alumno', None)
        grupo = getattr(self, 'grupo', None)
        if alumno is not None:
            CalificacionMateria.query.filter_by(alumnos_id=alumno.id).delete()
            Calificacion.query.filter_by(alumnos_id=alumno.id).delete()
            Alumno.query.filter_by(id=alumno.id).delete()
        if grupo is not None:
            Grupos.query.filter_by(id=grupo.id).delete()
        if hasattr(self, 'ctx'):
            self.ctx.pop()

    def test_materia_con_columna_se_guarda_en_esquema_fijo(self):
        _set_nota_materia(self.alumno, 'Español', 8.5)
        self.assertEqual(8.5, _get_nota_materia(self.alumno, 'Español'))
        # Se escribió en la columna fija (no en CalificacionMateria)
        calif = self.alumno.calificaciones[0]
        self.assertEqual(8.5, float(calif.español))

    def test_materia_sin_columna_se_guarda_en_calificacion_materia(self):
        _set_nota_materia(self.alumno, 'Biología', 9.0)
        self.assertEqual(9.0, _get_nota_materia(self.alumno, 'Biología'))
        cm = CalificacionMateria.query.filter_by(
            alumnos_id=self.alumno.id, materia_id=self.biologia.id
        ).first()
        self.assertIsNotNone(cm)
        self.assertEqual(9.0, float(cm.calificacion))

    def test_actualizar_nota_no_duplica_registro(self):
        _set_nota_materia(self.alumno, 'Biología', 6.0)
        _set_nota_materia(self.alumno, 'Biología', 7.5)
        registros = CalificacionMateria.query.filter_by(
            alumnos_id=self.alumno.id, materia_id=self.biologia.id
        ).count()
        self.assertEqual(1, registros)
        self.assertEqual(7.5, _get_nota_materia(self.alumno, 'Biología'))


class MateriasDefaultTestCase(unittest.TestCase):
    """Tests del catálogo de materias por defecto del plantel."""

    def test_catalogo_tiene_13_materias(self):
        self.assertEqual(13, len(MATERIAS_DEFAULT))

    def test_catalogo_contiene_las_materias_esperadas(self):
        nombres = [nombre for nombre, _ in MATERIAS_DEFAULT]
        self.assertEqual([
            'Español',
            'Matemáticas',
            'Biología',
            'Química',
            'Física',
            'Historia',
            'Formación cívica y Ética',
            'Geografía',
            'Inglés',
            'Artes (música y teatro)',
            'Tecnologías (talleres)',
            'Fomento a la lectura',
            'Educación Física',
        ], nombres)

    def test_catalogo_sin_nombres_duplicados(self):
        nombres = [nombre for nombre, _ in MATERIAS_DEFAULT]
        self.assertEqual(len(nombres), len(set(nombres)))

    def test_catalogo_solo_parejas_nombre_descripcion(self):
        for item in MATERIAS_DEFAULT:
            self.assertIsInstance(item, tuple)
            self.assertEqual(2, len(item))
            self.assertTrue(item[0] and item[1])


class GrupoTieneCurriculumTestCase(unittest.TestCase):
    """Tests del aviso de la boleta (_grupo_tiene_curriculum)."""

    def test_grupo_con_materias_devuelve_true(self):
        alumno = MockAlumno(grupo=MockGroup([MockMateria('Español', 1)]))
        self.assertTrue(_grupo_tiene_curriculum(alumno))

    def test_grupo_sin_materias_devuelve_false(self):
        alumno = MockAlumno(grupo=MockGroup([]))
        self.assertFalse(_grupo_tiene_curriculum(alumno))

    def test_alumno_sin_grupo_devuelve_false(self):
        alumno = MockAlumno(grupo=None)
        self.assertFalse(_grupo_tiene_curriculum(alumno))


if __name__ == '__main__':
    unittest.main()
