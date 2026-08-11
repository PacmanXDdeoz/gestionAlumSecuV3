#!/usr/bin/env python3
"""Backup defensivo de la base de datos (esquema + datos).

Uso:
    python scripts/backup_db.py                     # usa .env / db_uri.secret
    python scripts/backup_db.py <URI>               # backup de una BD concreta
    python scripts/backup_db.py <URI> -o out.sql    # archivo de salida explícito

Genera un archivo SQL con CREATE TABLE + INSERT para todas las tablas de los
esquemas ``alejandra`` y ``public`` (incluida alembic_version), en
``backups/<base>_<fecha>.sql``.

No depende de pg_dump (evita problemas de versiones cliente/servidor).
"""
import argparse
import datetime
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_uri(cli_uri: str) -> str:
    if cli_uri:
        return cli_uri
    env = {}
    env_file = PROJECT_ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip().strip('"').strip("'")
    if env.get('DATABASE_URI'):
        return env['DATABASE_URI']
    # La base local de respaldo (DATABASE_URI_LOCAL) se usa como alternativa.
    if env.get('DATABASE_URI_LOCAL'):
        return env['DATABASE_URI_LOCAL']
    secret = PROJECT_ROOT / 'db_uri.secret'
    if secret.exists():
        return secret.read_text(encoding='utf-8').strip()
    raise SystemExit('No se encontró URI: usa un argumento, DATABASE_URI en .env o db_uri.secret')


def _quote_ident(conn, name: str) -> str:
    """Identificador entre comillas dobles según el dialecto."""
    return conn.dialect.identifier_preparer.quote(name)


def dump_database(uri: str, output: Path) -> None:
    engine = create_engine(uri)
    with engine.connect() as conn:
        schemas = ['alejandra', 'public']
        tables = []
        for schema in schemas:
            for table_name in inspect(conn).get_table_names(schema=schema):
                tables.append((schema, table_name))

        lines = []
        lines.append(f'-- Backup {uri.split("@")[-1]} — {datetime.datetime.now().isoformat()}')
        lines.append('-- Generado por scripts/backup_db.py\n')

        for schema, table in sorted(tables):
            full = f'{_quote_ident(conn, schema)}.{_quote_ident(conn, table)}'
            # ── Esquema (solo CREATE TABLE; constraints/índices se omiten) ──
            cols = []
            for col in inspect(conn).get_columns(table, schema=schema):
                col_sql = f'{_quote_ident(conn, col["name"])} {col["type"]}'
                if not col.get('nullable', True):
                    col_sql += ' NOT NULL'
                cols.append(col_sql)
            lines.append(f'CREATE TABLE IF NOT EXISTS {full} (')
            lines.append('    ' + ',\n    '.join(cols))
            lines.append(');')

            # ── Datos (INSERT por fila, valores escapados) ──
            rows = conn.execute(text(f'SELECT * FROM {full}')).mappings().all()
            if rows:
                keys = list(rows[0].keys())
                cols_q = ', '.join(_quote_ident(conn, k) for k in keys)
                for row in rows:
                    values = []
                    for k in keys:
                        v = row[k]
                        if v is None:
                            values.append('NULL')
                        elif isinstance(v, bool):
                            values.append('TRUE' if v else 'FALSE')
                        elif isinstance(v, (int, float)):
                            values.append(str(v))
                        else:
                            escaped = str(v).replace("'", "''")
                            values.append(f"'{escaped}'")
                    lines.append(
                        f"INSERT INTO {full} ({cols_q}) VALUES ({', '.join(values)});"
                    )
            lines.append('')
        lines.append('-- Fin del backup')

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    total_tables = len(tables)
    print(f'Backup OK: {output}')
    print(f'  {total_tables} tablas volcadas ({", ".join(sorted({t[0] for t in tables}))})')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('uri', nargs='?', default='', help='URI de conexión (opcional)')
    parser.add_argument('-o', '--output', default='', help='Archivo de salida (opcional)')
    args = parser.parse_args()

    uri = _resolve_uri(args.uri)
    if args.output:
        output = Path(args.output)
    else:
        db_name = create_engine(uri).url.database or 'db'
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output = PROJECT_ROOT / 'backups' / f'{db_name}_{stamp}.sql'
    dump_database(uri, output)


if __name__ == '__main__':
    sys.exit(main())
