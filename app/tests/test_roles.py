"""Tests del catálogo de roles (alejandra.rol) y su integración con el login.

La tabla de roles es la fuente de verdad de los roles autorizados (admin,
docente). El login rechaza docentes con un rol que no exista en el catálogo.
"""
import unittest

from app import create_app, db
from app.auth.models import Docente, Rol, es_admin


class CatalogoRolesTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(settings_module='config.testing')
        self.client = self.app.test_client()
        # Garantiza el catálogo aunque la BD de testing se reconstruya desde cero
        with self.app.app_context():
            from app import db
            db.create_all()
            Rol.seed_defaults()

    def tearDown(self):
        with self.app.app_context():
            Docente.query.filter(Docente.email.like('rol-test%@example.com')).delete()
            from app import db
            db.session.commit()

    def test_catalogo_tiene_admin_y_docente(self):
        with self.app.app_context():
            nombres = {r.rol for r in Rol.get_all()}
            self.assertIn('admin', nombres)
            self.assertIn('docente', nombres)

    def test_es_admin_reconoce_rol_del_catalogo(self):
        with self.app.app_context():
            # rol=1 (admin) y rol=2 (docente) según el catálogo alejandra.rol
            admin = Docente(name='Admin Rol', email='rol-test-admin@example.com',
                            apellidos='Sistema', rol=1)
            self.assertTrue(es_admin(admin))
            docente = Docente(name='Docente Rol', email='rol-test-docente@example.com',
                              apellidos='X', rol=2)
            self.assertFalse(es_admin(docente))

    def test_login_acepta_rol_del_catalogo(self):
        with self.app.app_context():
            d = Docente(name='Docente Ok', email='rol-test-docente@example.com',
                        apellidos='X', rol=2)
            d.set_password('123456')
            d.save()
        res = self.client.post('/login', data={
            'email': 'rol-test-docente@example.com', 'password': '123456',
        }, follow_redirects=False)
        self.assertEqual(302, res.status_code)

    def test_fk_rechaza_rol_fuera_del_catalogo(self):
        """La FK de docentes.rol impide guardar un rol inexistente en el catálogo."""
        from sqlalchemy.exc import IntegrityError
        with self.app.app_context():
            # id 99 no existe en el catálogo de roles
            d = Docente(name='Rol Invalido', email='rol-test-invalido@example.com',
                        apellidos='X', rol=99)
            d.set_password('123456')
            with self.assertRaises(IntegrityError):
                d.save()
            db.session.rollback()


if __name__ == '__main__':
    unittest.main()
