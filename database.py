
import mysql.connector
from pathlib import Path
import pandas as pd
import streamlit as st
import tomllib


# =========================================================
# LOKASI FOLDER PROJECT
# =========================================================

BASE_DIR = Path(__file__).resolve().parent


# =========================================================
# LOKASI FILE EXCEL
# =========================================================

EXCEL_PATH = (
    BASE_DIR / "ANTAM_Harga_dan_Buyback_2021_2025.xlsx"
)


# =========================================================
# MEMBACA KONFIGURASI DATABASE
# =========================================================

def get_db_config():

    # Membaca konfigurasi dari Streamlit Secrets
    # Digunakan pada Streamlit lokal dan Streamlit Cloud

    try:
        return dict(st.secrets["mysql"])

    except Exception:

        # Jika dijalankan langsung menggunakan Python,
        # baca file .streamlit/secrets.toml

        secrets_path = (
            BASE_DIR / ".streamlit" / "secrets.toml"
        )

        with secrets_path.open("rb") as file:
            secrets = tomllib.load(file)

        return secrets["mysql"]


# =========================================================
# KONEKSI DATABASE MYSQL AIVEN
# =========================================================

def get_connection():

    db_config = get_db_config()

    config = {
        "host": db_config["host"],
        "user": db_config["user"],
        "password": db_config["password"],
        "database": db_config["database"],
        "port": int(db_config["port"]),

        # Konfigurasi SSL Aiven
        "ssl_ca": str(BASE_DIR / "aiven_ca.pem"),
        "ssl_verify_cert": True,
        "ssl_verify_identity": True
    }

    return mysql.connector.connect(**config)


# =========================================================
# IMPORT DATA EXCEL JIKA DATABASE MASIH KOSONG
# =========================================================

def import_historical_data_if_empty():

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM historical_prices"
        )

        jumlah_data = cursor.fetchone()[0]

        # Jangan import ulang jika data sudah tersedia
        if jumlah_data > 0:
            print(
                f"Data historis sudah tersedia: {jumlah_data} baris."
            )
            return

        # Periksa keberadaan file Excel
        if not EXCEL_PATH.exists():
            print(
                f"File Excel tidak ditemukan: {EXCEL_PATH}"
            )
            return

        print("Mengimpor data historis dari Excel...")

        df = pd.read_excel(EXCEL_PATH)

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
            raise ValueError(
                f"Kolom Excel tidak ditemukan: {missing_columns}"
            )

        df = df[required_columns].copy()

        # Konversi tanggal
        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        # Konversi harga jual
        df["Price"] = pd.to_numeric(
            df["Price"],
            errors="coerce"
        )

        # Konversi harga buyback
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

        # Hapus tanggal duplikat
        df = df.drop_duplicates(
            subset=["Date"],
            keep="first"
        )

        data_insert = []

        for _, row in df.iterrows():

            tanggal = row["Date"].strftime("%Y-%m-%d")

            harga_jual = float(row["Price"])

            harga_buyback = float(row["Buyback"])

            data_insert.append(
                (
                    tanggal,
                    harga_jual,
                    harga_buyback
                )
            )

        # Masukkan seluruh data ke MySQL Aiven
        cursor.executemany(
            """
            INSERT IGNORE INTO historical_prices
            (
                tanggal,
                harga_jual,
                harga_buyback
            )
            VALUES (%s, %s, %s)
            """,
            data_insert
        )

        conn.commit()

        print(
            f"Import data historis selesai: "
            f"{cursor.rowcount} baris dimasukkan."
        )

    finally:
        conn.close()


# =========================================================
# MEMBUAT TABEL DATABASE
# =========================================================

def init_database():

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # =================================================
        # TABEL USERS
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (

                id_user INT AUTO_INCREMENT PRIMARY KEY,

                username VARCHAR(50) NOT NULL UNIQUE,

                password_hash VARCHAR(255) NOT NULL,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                last_login DATETIME NULL,

                is_active TINYINT(1) DEFAULT 1

            ) ENGINE=InnoDB
        """)

        # =================================================
        # TABEL HISTORICAL PRICES
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_prices (

                id_data INT AUTO_INCREMENT PRIMARY KEY,

                tanggal DATE NOT NULL UNIQUE,

                harga_jual DECIMAL(15,2) NOT NULL,

                harga_buyback DECIMAL(15,2) NOT NULL,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP

            ) ENGINE=InnoDB
        """)

        # =================================================
        # TABEL CLASSIFICATION HISTORY
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classification_history (

                id_riwayat INT AUTO_INCREMENT PRIMARY KEY,

                id_user INT NOT NULL,

                waktu_klasifikasi DATETIME
                    DEFAULT CURRENT_TIMESTAMP,

                mode_klasifikasi VARCHAR(50),

                tanggal_data DATE NULL,

                Price_Return_1 DOUBLE NOT NULL,

                Price_Return_2 DOUBLE NOT NULL,

                Price_Return_3 DOUBLE NOT NULL,

                Buyback_Return_1 DOUBLE NOT NULL,

                Buyback_Return_2 DOUBLE NOT NULL,

                Buyback_Return_3 DOUBLE NOT NULL,

                hasil_decision_tree VARCHAR(50) NOT NULL,

                hasil_random_forest VARCHAR(50) NOT NULL,

                CONSTRAINT fk_classification_user
                    FOREIGN KEY (id_user)
                    REFERENCES users(id_user)

            ) ENGINE=InnoDB
        """)

        conn.commit()

        print("Tabel database berhasil diperiksa.")

    finally:
        conn.close()

    # Import data historis jika tabel masih kosong
    import_historical_data_if_empty()


# =========================================================
# MENJALANKAN INISIALISASI
# =========================================================

if __name__ == "__main__":

    try:
        init_database()

        print("====================================")
        print("DATABASE MYSQL AIVEN BERHASIL DISIAPKAN")
        print("Database : skripsi_antam")
        print("Host     : AIVEN")
        print("Port     : 10403")
        print("====================================")

    except mysql.connector.Error as e:

        print("GAGAL TERHUBUNG KE MYSQL AIVEN:")
        print(e)

    except Exception as e:

        print("TERJADI KESALAHAN:")
        print(e)