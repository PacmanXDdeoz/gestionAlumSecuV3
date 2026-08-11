import os
import unittest

from sqlalchemy import text

from app import create_app, db
from app.auth.models import Docente, Rol
from app.models import Alumno, Grupos


class QRGenerationTestCase(unittest.TestCase):
    """Test de generación de QR al registrar un alumno.

    Escribe en la base de testing. En setUp se limpian los datos de la
    corrida anterior (idempotencia) y en tearDown SOLO se eliminan los
    datos creados por este test — nunca db.drop_all(), que destruiría
    el esquema completo (fue la causa de la base remota incoherente).
    """

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()
        # Aísla el test del .env del desarrollador: la prioridad de
        # PUBLIC_BASE_URL se prueba en tests concretos, no por heredarla.
        self.app.config['PUBLIC_BASE_URL'] = ''
        with self.app.app_context():
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS alejandra'))
            db.create_all()
            Rol.seed_defaults()  # el catálogo de roles debe existir (FK de docentes.rol)
            # Limpieza de corridas previas (idempotente); grupo dedicado '9Q'
            # para no chocar con los datos sembrados por `flask seed`.
            Alumno.query.filter_by(name='Juan').delete()
            Docente.query.filter_by(email='test@example.com').delete()
            Grupos.query.filter_by(grado='9', grupo='Q').delete()
            db.session.commit()
            # Datos mínimos: un grupo y un docente autenticado
            grupo = Grupos(grado='9', grupo='Q')
            grupo.save()
            self.grupo_id = grupo.id
            docente = Docente(name='Docente Test', email='test@example.com', rol=2)  # rol=2: docente
            docente.set_password('123456')
            docente.save()

    def tearDown(self):
        with self.app.app_context():
            # Limpieza dirigida: solo los datos creados por este test
            Alumno.query.filter_by(name='Juan').delete()
            Docente.query.filter_by(email='test@example.com').delete()
            Grupos.query.filter_by(grado='9', grupo='Q').delete()
            db.session.commit()
            db.session.remove()

    def _login(self):
        return self.client.post('/login', data={
            'email': 'test@example.com',
            'password': '123456'
        }, follow_redirects=False)

    def _ruta_qr(self, alumno):
        """Ruta real del PNG del QR en el entorno de testing.

        La carpeta de QRs se redirige (config QR_CODES_FOLDER) a un
        directorio temporal fuera del proyecto, por lo que el path absoluto
        se construye con esa config, no con static_folder.
        """
        return os.path.join(self.app.config['QR_CODES_FOLDER'], f'alumno_{alumno.id}.png')

    def test_register_alumno_generates_qr(self):
        self._login()
        response = self.client.post('/alumno/nuevo', data={
            'name': 'Juan',
            'lastname_p': 'Pérez',
            'lastname_m': 'Sánchez',
            'genero': 'M',
            'group_id': self.grupo_id,
        }, follow_redirects=False)

        self.assertEqual(302, response.status_code)

        with self.app.app_context():
            alumno = Alumno.query.filter_by(name='Juan').first()
            self.assertIsNotNone(alumno)
            self.assertIsNotNone(alumno.codigo_qr)
            self.assertTrue(os.path.exists(self._ruta_qr(alumno)))

    def test_servir_qr_desde_carpeta_configurada(self):
        """GET /qr/<archivo> sirve el PNG desde QR_CODES_FOLDER (disco).

        El entorno de testing redirige QR_CODES_FOLDER a un directorio
        temporal; la ruta pública debe servir el archivo desde ahí, que es
        justo el caso del disco persistente en producción (Render).
        """
        self._login()
        self.client.post('/alumno/nuevo', data={
            'name': 'Juan',
            'lastname_p': 'Pérez',
            'lastname_m': 'Sánchez',
            'genero': 'M',
            'group_id': self.grupo_id,
        }, follow_redirects=False)

        with self.app.app_context():
            alumno = Alumno.query.filter_by(name='Juan').first()
            with open(self._ruta_qr(alumno), 'rb') as f:
                esperado = f.read()
            url = f'/qr/qrcodes/alumno_{alumno.id}.png'

        r = self.client.get(url)
        self.assertEqual(200, r.status_code)
        self.assertEqual('image/png', r.mimetype)
        self.assertEqual(esperado, r.data)
        # no-cache: el QR puede regenerarse (mismo nombre), el navegador
        # revalida con ETag/304 en vez de servir un PNG stale.
        self.assertIn('no-cache', r.headers.get('Cache-Control', ''))

    def test_servir_qr_404_si_no_existe(self):
        """Un QR inexistente responde 404 (no rompe la boleta)."""
        r = self.client.get('/qr/qrcodes/alumno_99999.png')
        self.assertEqual(404, r.status_code)

    def test_servir_qr_ignora_path_traversal(self):
        """Un filename con '../' no escapa de la carpeta: se usa el basename.

        (1) Un traversal que apunta al archivo real se resuelve por el
        basename (200, sin escapar). (2) Un traversal a un archivo fuera de
        la carpeta de QRs no existe ahí (404).
        """
        self._login()
        self.client.post('/alumno/nuevo', data={
            'name': 'Juan',
            'lastname_p': 'Pérez',
            'lastname_m': 'Sánchez',
            'genero': 'M',
            'group_id': self.grupo_id,
        }, follow_redirects=False)

        with self.app.app_context():
            alumno = Alumno.query.filter_by(name='Juan').first()
            url_ok = f'/qr/..%2F..%2Fqrcodes%2Falumno_{alumno.id}.png'

        self.assertEqual(200, self.client.get(url_ok).status_code)
        self.assertEqual(404, self.client.get('/qr/..%2F..%2Fetc%2Fpasswd').status_code)

    def test_qr_codifica_url_absoluta_de_la_boleta(self):
        """El QR codifica la URL /buscar/<id> (escaneo nativo), no el ID crudo."""
        import io
        import qrcode
        from flask import url_for

        self._login()
        self.client.post('/alumno/nuevo', data={
            'name': 'Juan',
            'lastname_p': 'Pérez',
            'lastname_m': 'Sánchez',
            'genero': 'M',
            'group_id': self.grupo_id,
        }, follow_redirects=False)

        with self.app.app_context():
            alumno = Alumno.query.filter_by(name='Juan').first()
            with self.app.test_request_context('/'):
                esperado = url_for('public.boleta_alumno', id=alumno.id, _external=True)
            self.assertTrue(esperado.endswith(f'/buscar/{alumno.id}'))

            buf = io.BytesIO()
            # Mismo guardado optimizado que generar_qr (PNG 1-bit + optimize)
            qrcode.make(esperado).save(buf, format='PNG', optimize=True)
            ruta = self._ruta_qr(alumno)
            with open(ruta, 'rb') as f:
                self.assertEqual(buf.getvalue(), f.read())

    def test_generate_qr_fuera_de_request_usa_public_base_url(self):
        """Sin request context (CLI), el QR usa PUBLIC_BASE_URL como respaldo."""
        import io
        import qrcode

        self.app.config['PUBLIC_BASE_URL'] = 'https://midominio.com'
        with self.app.app_context():
            grupo = db.session.get(Grupos, self.grupo_id)
            alumno = Alumno(name='Juan', lastname_p='CLI', lastname_m='Test',
                            group_id=grupo.id, genero='M', password='QRCLI0001')
            db.session.add(alumno)
            db.session.flush()
            alumno.generate_qr_code()  # sin request context

            buf = io.BytesIO()
            qrcode.make(f'https://midominio.com/buscar/{alumno.id}').save(buf, format='PNG', optimize=True)
            ruta = self._ruta_qr(alumno)
            with open(ruta, 'rb') as f:
                self.assertEqual(buf.getvalue(), f.read())

    def test_public_base_url_tiene_prioridad_dentro_de_request(self):
        """Si PUBLIC_BASE_URL está definido, el QR lo usa incluso en request
        (determinista e independiente del host de la petición)."""
        import io
        import qrcode

        self.app.config['PUBLIC_BASE_URL'] = 'http://192.168.100.8:5000'
        with self.app.app_context():
            grupo = db.session.get(Grupos, self.grupo_id)
            alumno = Alumno(name='Juan', lastname_p='Prioridad', lastname_m='Test',
                            group_id=grupo.id, genero='M', password='QRPRIO001')
            db.session.add(alumno)
            db.session.flush()
            with self.app.test_request_context('/login'):
                # Dentro de un request: aun así gana PUBLIC_BASE_URL
                alumno.generate_qr_code()

            buf = io.BytesIO()
            qrcode.make(f'http://192.168.100.8:5000/buscar/{alumno.id}').save(buf, format='PNG', optimize=True)
            ruta = self._ruta_qr(alumno)
            with open(ruta, 'rb') as f:
                self.assertEqual(buf.getvalue(), f.read())

    def test_cli_regenerate_qrs(self):
        """El comando flask regenerate-qrs regenera los QRs sin request."""
        self.app.config['PUBLIC_BASE_URL'] = 'https://midominio.com'
        # Alumno existente: garantiza que el comando reporte regeneración
        # (la salida 'QRs regenerados' solo aparece si hay alumnos en la BD).
        with self.app.app_context():
            grupo = db.session.get(Grupos, self.grupo_id)
            alumno = Alumno(name='Juan', lastname_p='CLI', lastname_m='Test',
                            group_id=grupo.id, genero='M', password='QRCLI0002')
            db.session.add(alumno)
            db.session.flush()
            alumno.generate_qr_code()
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=['regenerate-qrs'])
        self.assertEqual(0, result.exit_code, result.output)
        self.assertIn('QRs regenerados', result.output)

    def test_cli_regenerate_qrs_elimina_huerfanos(self):
        """El sweep del comando elimina los PNGs de alumnos ya eliminados.

        Se crea un archivo ``alumno_<id>.png`` cuyo ID no existe en la BD
        (huérfano) y se invoca el comando: debe eliminarlo. Los QRs de los
        alumnos existentes se conservan.
        """
        from pathlib import Path

        self.app.config['PUBLIC_BASE_URL'] = 'https://midominio.com'
        carpeta = Path(self.app.config['QR_CODES_FOLDER'])
        carpeta.mkdir(parents=True, exist_ok=True)

        # Huérfano: alumno inexistente (ID fuera de la secuencia real)
        huerfano = carpeta / 'alumno_99999.png'
        huerfano.write_bytes(b'qr huerfano')

        # Alumno existente con su QR (debe conservarse)
        with self.app.app_context():
            grupo = db.session.get(Grupos, self.grupo_id)
            alumno = Alumno(name='Juan', lastname_p='Sweep', lastname_m='Test',
                            group_id=grupo.id, genero='M', password='QRSWEEP001')
            db.session.add(alumno)
            db.session.flush()
            alumno.generate_qr_code()
            id_existente = alumno.id
            qr_existente = carpeta / f'alumno_{id_existente}.png'
            self.assertTrue(qr_existente.exists())

        runner = self.app.test_cli_runner()
        result = runner.invoke(args=['regenerate-qrs'])
        self.assertEqual(0, result.exit_code, result.output)

        self.assertFalse(huerfano.exists(), 'El QR huérfano debería eliminarse')
        self.assertTrue(qr_existente.exists(), 'El QR del alumno existente debería conservarse')
        self.assertIn('huérfano', result.output.lower())


if __name__ == '__main__':
    unittest.main()
