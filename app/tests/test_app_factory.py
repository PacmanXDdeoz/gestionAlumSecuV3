import unittest

from app import create_app


class AppFactoryTestCase(unittest.TestCase):

    def test_create_app_defaults_to_local_config(self):
        app = create_app()
        self.assertEqual(app.config['APP_ENV'], app.config['APP_ENV_LOCAL'])

    def test_security_headers_en_todas_las_respuestas(self):
        """Fase 1 (pilar 4): toda respuesta lleva las cabeceras de seguridad.

        El CSP es laxo a propósito (Tailwind CDN + estilos/scripts inline), así
        que la regresión fija la presencia de las cabeceras y las directivas
        clave, no la lista completa de fuentes.
        """
        app = create_app('config.testing')
        client = app.test_client()

        res = client.get('/')
        self.assertEqual(200, res.status_code)

        self.assertEqual('DENY', res.headers.get('X-Frame-Options'))
        self.assertEqual('nosniff', res.headers.get('X-Content-Type-Options'))
        self.assertEqual(
            'strict-origin-when-cross-origin',
            res.headers.get('Referrer-Policy'),
        )

        csp = res.headers.get('Content-Security-Policy')
        self.assertIsNotNone(csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("script-src 'self'", csp)
        # El diseño actual depende del CDN de Tailwind y de estilos inline
        self.assertIn('https://cdn.tailwindcss.com', csp)

        # HSTS: solo sobre HTTPS (en la LAN de pruebas HTTP no debe aparecer)
        self.assertNotIn('Strict-Transport-Security', res.headers)

        # Las páginas de error también llevan las cabeceras
        res_404 = client.get('/ruta/que/no/existe')
        self.assertEqual(404, res_404.status_code)
        self.assertEqual('DENY', res_404.headers.get('X-Frame-Options'))


if __name__ == '__main__':
    unittest.main()
