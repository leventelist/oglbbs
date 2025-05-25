import sqlite3


# === SQLite Setup ===
def init_db(db_file="bbs.db"):
    db = sqlite3.connect(db_file)
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT,
            content TEXT NOT NULL,
            is_private INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
    """)
    db.commit()
    return db


def add_user_with_password(db, username, password):
    cur = db.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        db.commit()
    except sqlite3.IntegrityError:
      print(f"User {username} already exists.")
    except sqlite3.Error as e:
      print(f"Error adding user {username}: {e}")


def get_user(db, username):
    cur = db.cursor()
    cur.execute("SELECT username, password FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    return user


def change_login_time(db, username):
    cur = db.cursor()
    cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?", (username,))
    db.commit()
    return cur.rowcount > 0


def change_password(db, username, new_password):
    cur = db.cursor()
    try:
        cur.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username))
        db.commit()
        return cur.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error changing password for {username}: {e}")
        return False


def store_message(db, sender, content):
  db.execute("INSERT INTO messages (sender, content) VALUES (?, ?)", (sender, content))
  db.commit()


def store_private_message(db, sender, recipient, content):
  db.execute("INSERT INTO messages (sender, recipient, content, is_private) VALUES (?, ?, ?, 1)", (sender, recipient, content))
  db.commit()


def list_messages(db, limit=5):
  cur = db.cursor()
  cur.execute("SELECT sender, content, timestamp FROM messages WHERE is_private = 0 AND deleted = 0 ORDER BY id DESC LIMIT ?", (limit,))
  return cur.fetchall()


def list_private_messages(db, recipient, limit=5):
  cur = db.cursor()
  cur.execute("SELECT id, sender, content, timestamp FROM messages WHERE recipient = ? AND is_private = 1 AND deleted = 0 ORDER BY id DESC LIMIT ?", (recipient, limit))
  return cur.fetchall()


def delete_message(db, msg_id, recipient):
  cur = db.cursor()
  cur.execute("UPDATE messages SET deleted = 1 WHERE id = ? AND recipient = ? AND is_private = 1", (msg_id, recipient))
  if cur.rowcount:
    db.commit()
    return True
  else:
    return False


def shutdown(db):
  db.close()
  print("Database connection closed.")