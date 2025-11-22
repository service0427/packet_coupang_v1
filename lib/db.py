"""
MySQL 데이터베이스 연결 모듈
"""

import json
import pymysql
from pathlib import Path
from contextlib import contextmanager

# Load config
config_path = Path(__file__).parent.parent / 'config.json'
with open(config_path) as f:
    config = json.load(f)

DB_CONFIG = {
    **config['database'],
    'cursorclass': pymysql.cursors.DictCursor
}

def get_connection():
    return pymysql.connect(**DB_CONFIG)

@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def execute_query(query, params=None):
    with get_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()

def execute_many(query, params_list):
    with get_cursor() as cursor:
        cursor.executemany(query, params_list)
        return cursor.rowcount

def insert_one(query, params=None):
    with get_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.lastrowid

if __name__ == '__main__':
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            print("✅ MySQL 연결 성공")
            print(f"   Host: {DB_CONFIG['host']}")
    except Exception as e:
        print(f"❌ MySQL 연결 실패: {e}")
