import sqlite3

def connect_to_db(database):
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    return db

def query_db(db, query, args=()):
    cur = db.execute(query, args)
    ret = cur.fetchall()
    return ret if ret else None
