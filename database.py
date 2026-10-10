import sqlite3
from pathlib import Path


# =========================================================
# KONFIGURASI DATABASE
# =========================================================

DATABASE_PATH = Path("database.db")


# =========================================================
# KONEKSI DATABASE
# =========================================================

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# MEMBUAT TABEL
# =========================================================

def init_database():

    conn = get_connection()
    cursor = conn.cursor()

    # =====================================================
    # TABEL USERS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id_user INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)

    # =====================================================
    # TABEL HISTORICAL PRICES
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_prices (
            id_data INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL UNIQUE,
            harga_jual REAL NOT NULL,
            harga_buyback REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =====================================================
    # TABEL CLASSIFICATION HISTORY
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classification_history (
            id_riwayat INTEGER PRIMARY KEY AUTOINCREMENT,

            id_user INTEGER NOT NULL,

            waktu_klasifikasi TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            mode_klasifikasi TEXT NOT NULL,

            tanggal_data TEXT,

            Price_Return_1 REAL NOT NULL,
            Price_Return_2 REAL NOT NULL,
            Price_Return_3 REAL NOT NULL,

            Buyback_Return_1 REAL NOT NULL,
            Buyback_Return_2 REAL NOT NULL,
            Buyback_Return_3 REAL NOT NULL,

            hasil_decision_tree TEXT NOT NULL,
            hasil_random_forest TEXT NOT NULL,

            FOREIGN KEY (id_user)
                REFERENCES users(id_user)
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# MENJALANKAN INISIALISASI
# =========================================================

if __name__ == "__main__":
    init_database()
    print("Database berhasil dibuat.")