"""Generación de códigos alfanuméricos seguros (códigos de acceso de alumnos)."""
import secrets
import string


def generar_codigo(longitud=10):
    """Genera un código alfanumérico aleatorio de ``longitud`` caracteres.

    Usa ``secrets`` (criptográficamente seguro). Alfabeto sin caracteres
    ambiguos para facilitar la lectura.
    """
    alfabeto = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))
