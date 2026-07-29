import unittest

from app import create_app


class AppFactoryTestCase(unittest.TestCase):

    def test_create_app_defaults_to_local_config(self):
        app = create_app()
        self.assertEqual(app.config['APP_ENV'], app.config['APP_ENV_LOCAL'])


if __name__ == '__main__':
    unittest.main()
