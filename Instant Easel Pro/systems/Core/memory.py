"""
memory.py: the AI's searchable memory on disk (SQLite full-text search, built into Python). Fast at any size, so a library of
gigabytes on the AI drive still answers in a blink.

    idx = memory.Index(path_to_db)
    idx.sync_folder(folder)               index every text/code file in a folder (only changed files are re-read)
    idx.add("note", "the build uses python 3.12", key="note-12")
    idx.search("which python version", k=5, kinds=("note",))   -> [dict(kind, source, text, score)]
"""
import os, re, sqlite3, threading, time

TEXT_EXT = (".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs",
            ".rb", ".php", ".sh", ".bat", ".ps1", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".xml", ".sql", ".spec")
CHUNK, OVERLAP = 1200, 200
_WORD = re.compile(r"[A-Za-z0-9_]{2,}")

def _fts_query(text):
    words = list(dict.fromkeys(w.lower() for w in _WORD.findall(text)))[:24]
    return " OR ".join(f'"{w}"' for w in words)

def chunks(text, size=CHUNK, overlap=OVERLAP):
    i = 0
    while i < len(text):
        yield i, text[i:i + size]
        i += size - overlap

class Index:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True); self.path = path; self._lock = threading.Lock()
        with self._db() as c:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS items USING fts5(kind UNINDEXED, source UNINDEXED, key UNINDEXED, text, tokenize='porter unicode61')")
            c.execute("CREATE TABLE IF NOT EXISTS files (source TEXT PRIMARY KEY, mtime REAL, size INTEGER)")

    def _db(self): return sqlite3.connect(self.path, timeout=30)

    def add(self, kind, text, source="", key=""):
        with self._lock, self._db() as c:
            if key: c.execute("DELETE FROM items WHERE key = ?", (key,))
            c.execute("INSERT INTO items (kind, source, key, text) VALUES (?, ?, ?, ?)", (kind, source, key, text))

    def remove(self, key):
        with self._lock, self._db() as c: c.execute("DELETE FROM items WHERE key = ?", (key,))

    def sync_folder(self, folder, kind="library"):
        """index the files in folder; only new or changed files are read; files that were deleted are forgotten"""
        seen = set(); added = 0
        with self._lock, self._db() as c:
            known = {s: (m, z) for s, m, z in c.execute("SELECT source, mtime, size FROM files")}
            for d, _, fs in os.walk(folder):
                for f in fs:
                    if not f.lower().endswith(TEXT_EXT): continue
                    p = os.path.join(d, f); rel = os.path.relpath(p, folder); seen.add(rel)
                    try: st = os.stat(p)
                    except OSError: continue
                    if known.get(rel) == (st.st_mtime, st.st_size): continue
                    try: body = open(p, encoding="utf-8", errors="ignore").read()
                    except OSError: continue
                    c.execute("DELETE FROM items WHERE source = ? AND kind = ?", (rel, kind))
                    c.executemany("INSERT INTO items (kind, source, key, text) VALUES (?, ?, ?, ?)",
                                  [(kind, rel, f"{rel}#{i}", t) for i, t in chunks(body)])
                    c.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?)", (rel, st.st_mtime, st.st_size)); added += 1
            for gone in set(known) - seen:
                c.execute("DELETE FROM items WHERE source = ? AND kind = ?", (gone, kind)); c.execute("DELETE FROM files WHERE source = ?", (gone,))
        return added

    def search(self, text, k=5, kinds=None):
        q = _fts_query(text)
        if not q: return []
        sql = "SELECT kind, source, text, bm25(items) FROM items WHERE items MATCH ?"
        args = [q]
        if kinds: sql += " AND kind IN (%s)" % ",".join("?" * len(kinds)); args += list(kinds)
        sql += " ORDER BY bm25(items) LIMIT ?"; args.append(k)
        try:
            with self._db() as c: rows = c.execute(sql, args).fetchall()
        except sqlite3.OperationalError: return []
        return [dict(kind=r[0], source=r[1], text=r[2], score=-r[3]) for r in rows]

    def count(self, kind=None):
        with self._db() as c:
            return c.execute("SELECT count(*) FROM items" + (" WHERE kind = ?" if kind else ""), (kind,) if kind else ()).fetchone()[0]
