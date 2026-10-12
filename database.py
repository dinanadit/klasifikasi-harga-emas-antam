import sqlite3
from pathlib import Path
import pandas as pd


# =========================================================
# KONFIGURASI DATABASE
# =========================================================

DATABASE_PATH = Path("database.db")
EXCEL_PATH = Path("ANTAM_Harga_dan_Buyback_2021_2025.xlsx")


# =========================================================
# KONEKSI DATABASE
# =========================================================

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# IMPORT DATA EXCEL JIKA DATABASE MASIH KOSONG
# =========================================================

def import_historical_data_if_empty():

    conn = get_connection()
    cursor = conn.cursor()

    # Cek jumlah data historis yang sudah ada
    cursor.execute(
        "SELECT COUNT(*) FROM historical_prices"
    )

    jumlah_data = cursor.fetchone()[0]

    # Jika database sudah berisi data, jangan import ulang
    if jumlah_data > 0:
        conn.close()
        return

    # Jika file Excel tidak tersedia, hentikan proses import
    if not EXCEL_PATH.exists():
        conn.close()
        return

    # Baca Excel
    df = pd.read_excel(EXCEL_PATH)

    # Pastikan kolom tersedia
    required_columns = [
        "Date",
        "Price",
        "Buyback"
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        conn.close()
        raise ValueError(
            f"Kolom berikut tidak ditemukan di Excel: "
            f"{missing_columns}"
        )

    # Ambil kolom yang diperlukan
    df = df[required_columns].copy()

    # Konversi tanggal
    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    # Konversi harga
    df["Price"] = pd.to_numeric(
        df["Price"],
        errors="coerce"
    )

    df["Buyback"] = pd.to_numeric(
        df["Buyback"],
        errors="coerce"
    )

    # Hapus data tidak valid
    df = df.dropna(
        subset=[
            "Date",
            "Price",
            "Buyback"
        ]
    )

    # Urutkan berdasarkan tanggal
    df = df.sort_values("Date")

    # Hapus duplikat tanggal
    df = df.drop_duplicates(
        subset=["Date"],
        keep="first"
    )

    # Masukkan data ke database
    for _, row in df.iterrows():

        tanggal = row["Date"].strftime("%Y-%m-%d")
        harga_jual = float(row["Price"])
        harga_buyback = float(row["Buyback"])

        cursor.execute(
            """
            INSERT OR IGNORE INTO historical_prices
            (
                tanggal,
                harga_jual,
                harga_buyback
            )
            VALUES (?, ?, ?)
            """,
            (
                tanggal,
                harga_jual,
                harga_buyback
            )
        )

    conn.commit()
    conn.close()


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

    # Setelah tabel dibuat, cek apakah data historis kosong
    import_historical_data_if_empty()


# =========================================================
# MENJALANKAN INISIALISASI
# =========================================================

if __name__ == "__main__":
    init_database()
    print("Database berhasil dibuat.")