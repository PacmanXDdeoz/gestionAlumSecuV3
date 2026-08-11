import unittest

from sqlalchemy import text

from app import create_app, db
from app.auth.models import Docente, Rol


class ResponsiveLayoutTestCase(unittest.TestCase):
    """Estructura responsive global (base.html): hamburguesa móvil, sidebar
    off-canvas y footer dentro de la columna de contenido.

    Fija el marcado para que una refactorización posterior no rompa el
    sidebar en móvil ni el pie de página.
    """

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text('CREATE SCHEMA IF NOT EXISTS alejandra'))
            db.create_all()
            Rol.seed_defaults()
            if Docente.get_by_email('admin@example.com') is None:
                adm = Docente(name='Admin', email='admin@example.com', apellidos='Sistema')
                adm.set_password('123456')
                adm.save()

    def _login_admin(self):
        self.client.post('/login', data={'email': 'admin@example.com', 'password': '123456'})

    def test_panel_tiene_hamburguesa_sidebar_y_footer(self):
        self._login_admin()
        res = self.client.get('/admin/')
        html = res.get_data(as_text=True)
        self.assertEqual(200, res.status_code)
        self.assertIn('id="sidebarToggle"', html)
        self.assertIn('id="mainSidebar"', html)
        self.assertIn('id="sidebarBackdrop"', html)
        self.assertIn('class="footer-credit"', html)

    def test_buscar_es_responsiva(self):
        res = self.client.get('/buscar/')
        html = res.get_data(as_text=True)
        self.assertEqual(200, res.status_code)
        self.assertIn('id="sidebarToggle"', html)
        # El input no debe desbordar en pantallas estrechas
        self.assertIn('min-w-0', html)
        self.assertIn('max-w-[25rem]', html)


if __name__ == '__main__':
    unittest.main()
