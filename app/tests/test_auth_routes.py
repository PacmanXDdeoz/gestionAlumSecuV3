import unittest

from app import create_app
from app.auth.models import Docente


class AuthRouteTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()

    def test_root_serves_public_home(self):
        """La raíz es una landing pública (no redirige a login)."""
        res = self.client.get('/', follow_redirects=False)

        self.assertEqual(200, res.status_code)

    def test_docente_panel_requires_login(self):
        """El panel docente es una ruta protegida."""
        res = self.client.get('/docente/', follow_redirects=False)

        self.assertEqual(302, res.status_code)
        self.assertIn('/login', res.location)

    def test_docente_panel_requires_login(self):
        res = self.client.get('/docente/', follow_redirects=False)

        self.assertEqual(302, res.status_code)
        self.assertIn('/login', res.location)

    def test_admin_email_is_treated_as_admin(self):
        with self.app.app_context():
            # Idempotente: elimina un docente previo de una corrida anterior
            Docente.query.filter_by(email='admin@example.com').delete()
            docente = Docente(name='Admin', email='admin@example.com', apellidos='Sistema')
            docente.set_password('123456')
            docente.save()
            self.assertTrue(docente.is_admin)


if __name__ == '__main__':
    unittest.main()
