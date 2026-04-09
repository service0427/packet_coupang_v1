"""
PostgreSQL DB 연결 모듈
"""

import psycopg2
from contextlib import contextmanager

DB_CONFIG = {
    'host': '61.84.75.37',
    'port': 5432,
    'database': 'v1_coupang',
    'user': 'techb_pp',
    'password': 'Tech1324!',  # TODO: 비밀번호 확인 필요
}


@contextmanager
def get_connection():
    """DB 연결 컨텍스트 매니저"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    finally:
        if conn:
            conn.close()


def query(sql, params=None):
    """SELECT 쿼리 실행"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def execute(sql, params=None):
    """INSERT/UPDATE/DELETE 실행"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount
