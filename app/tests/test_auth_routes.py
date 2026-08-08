import unittest

from app import create_app
from app.auth.models import Docente


class AuthRouteTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()

    def test_root_redirects_to_login_then_calificaciones(self):
        res = self.client.get('/', follow_redirects=False)

        self.assertEqual(302, res.status_code)
        self.assertEqual('/login?next=%2F', res.location)

    def test_calificaciones_requires_login(self):
        res = self.client.get('/calificaciones', follow_redirects=False)

        self.assertEqual(302, res.status_code)
        self.assertEqual('/login?next=%2Fcalificaciones', res.location)

    def test_error_requires_login(self):
        res = self.client.get('/error', follow_redirects=False)

        self.assertEqual(302, res.status_code)
        self.assertIn('/login', res.location)

    def test_admin_email_is_treated_as_admin(self):
        with self.app.app_context():
            docente = Docente(name='Admin', email='admin@example.com', apellidos='Sistema')
            docente.set_password('123456')
            docente.save()
            self.assertTrue(docente.is_admin)


if __name__ == '__main__':
    unittest.main()
