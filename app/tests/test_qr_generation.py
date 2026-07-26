import os
import unittest

from sqlalchemy import text

from app import create_app, db
from app.models import Alumno


class QRGenerationTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS alejandra'))
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_register_alumno_generates_qr(self):
        response = self.client.post('/alumno/nuevo', data={
            'name': 'Juan',
            'lastname_p': 'Pérez',
            'lastname_m': 'Sánchez',
            'genero': 'M',
            'group_id': 1,
            'password': '12345',
            'status': 'y'
        }, follow_redirects=False)

        self.assertEqual(302, response.status_code)

        with self.app.app_context():
            alumno = Alumno.query.filter_by(name='Juan').first()
            self.assertIsNotNone(alumno)
            self.assertIsNotNone(alumno.codigo_qr)
            self.assertTrue(os.path.exists(os.path.join(self.app.static_folder, alumno.codigo_qr)))


if __name__ == '__main__':
    unittest.main()
