import sqlite3

db = sqlite3.connect("E:/桌面/RAG/data/chroma_db/chroma.sqlite3")
cursor = db.cursor()

# 所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tables:", tables)

# segments 结构
cursor.execute("PRAGMA table_info(segments)")
print("\nSegments columns:", [c[1] for c in cursor.fetchall()])

# segments 数据
cursor.execute("SELECT * FROM segments")
segs = cursor.fetchall()
print("Segments count:", len(segs))
for s in segs:
    print("  ", s)

# collections
cursor.execute("SELECT * FROM collections")
cols = cursor.fetchall()
print("\nCollections:", len(cols))
for c in cols:
    print("  ", c)

db.close()
