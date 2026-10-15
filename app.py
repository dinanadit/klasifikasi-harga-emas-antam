import os
import hashlib
import secrets
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import streamlit as st

from database import (
    get_connection,
    init_database
)


# ============================================================
# KONFIGURASI HALAMAN
# ============================================================

st.set_page_config(
    page_title="Klasifikasi Arah Harga Emas ANTAM",
    page_icon="🥇",
    layout="wide"
)


# ============================================================
# KONFIGURASI FILE
# ============================================================

FILE_HASIL = "hasil_final_6_fitur_antam.xlsx"

FILE_DT_MODEL = (
    "decision_tree_final_6_fitur.joblib"
)

FILE_RF_MODEL = (
    "random_forest_final_6_fitur.joblib"
)


# ============================================================
# 6 FITUR FINAL
# ============================================================

FITUR_FINAL = [
    "Price_Return_1",
    "Price_Return_2",
    "Price_Return_3",
    "Buyback_Return_1",
    "Buyback_Return_2",
    "Buyback_Return_3"
]


# ============================================================
# INISIALISASI DATABASE
# ============================================================

init_database()


# PEMERIKSAAN SEMENTARA AKUN
conn_cek = get_connection()
cursor_cek = conn_cek.cursor()

cursor_cek.execute(
    "SELECT username, is_active FROM users WHERE username = ?",
    ("user3",)
)
hasil_cek = cursor_cek.fetchone()

if hasil_cek:
    st.warning(
        f"DIAGNOSTIK: user3 ditemukan; status aktif = "
        f"{hasil_cek['is_active']}"
    )
else:
    st.warning("DIAGNOSTIK: user3 tidak ditemukan")

conn_cek.close()
# ============================================================
# SESSION STATE
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


if "id_user" not in st.session_state:
    st.session_state.id_user = None


if "username" not in st.session_state:
    st.session_state.username = None


if "page" not in st.session_state:
    st.session_state.page = "Beranda"


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 34px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .sub-title {
        font-size: 18px;
        color: #888888;
        margin-bottom: 25px;
    }

    .result-up {
        padding: 15px;
        border-radius: 8px;
        background-color: #0f5132;
        color: white;
        font-weight: bold;
        text-align: center;
    }

    .result-down {
        padding: 15px;
        border-radius: 8px;
        background-color: #842029;
        color: white;
        font-weight: bold;
        text-align: center;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# FUNGSI PASSWORD
# ============================================================

def hash_password(password):

    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()

    return f"{salt}${password_hash}"


def verify_password(password, stored_password):

    try:

        salt, stored_hash = (
            stored_password.split("$", 1)
        )

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        ).hex()

        return secrets.compare_digest(
            password_hash,
            stored_hash
        )

    except Exception:

        return False


# ============================================================
# FUNGSI USER
# ============================================================

def register_user(username, password):

    username = username.strip()

    if username == "":
        return False, "Username tidak boleh kosong."

    if len(username) < 3:
        return False, "Username minimal 3 karakter."

    if password == "":
        return False, "Password tidak boleh kosong."

    if len(password) < 6:
        return False, "Password minimal 6 karakter."

    password_hash = hash_password(password)

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users
            (
                username,
                password_hash
            )
            VALUES (?, ?)
            """,
            (
                username,
                password_hash
            )
        )

        conn.commit()

        return True, "Registrasi berhasil."

    except sqlite3.IntegrityError:

        return False, "Username sudah digunakan."

    finally:

        conn.close()


def login_user(username, password):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id_user,
                username,
                password_hash,
                is_active
            FROM users
            WHERE username = ?
            """,
            (username.strip(),)
        )

        user = cursor.fetchone()

        if user is None:
            return None

        if user["is_active"] != 1:
            return None

        if not verify_password(
            password,
            user["password_hash"]
        ):
            return None

        cursor.execute(
            """
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id_user = ?
            """,
            (user["id_user"],)
        )

        conn.commit()

        return {
            "id_user": user["id_user"],
            "username": user["username"]
        }

    finally:

        conn.close()


# ============================================================
# FORMAT
# ============================================================

def format_rupiah(value):

    try:

        value = float(value)

        return (
            "Rp "
            + f"{value:,.0f}"
            .replace(",", ".")
        )

    except Exception:

        return "-"


def format_return(value):

    try:
        return f"{float(value):.6f}"

    except Exception:
        return "-"


# ============================================================
# LOAD DATA HISTORIS DARI DATABASE
# ============================================================

@st.cache_data(ttl=60)
def load_historical_data():

    conn = get_connection()

    try:

        query = """
            SELECT
                id_data,
                tanggal,
                harga_jual,
                harga_buyback
            FROM historical_prices
            ORDER BY tanggal ASC
        """

        data = pd.read_sql_query(
            query,
            conn
        )

    finally:

        conn.close()

    if data.empty:
        return data

    data["tanggal"] = pd.to_datetime(
        data["tanggal"],
        errors="coerce"
    )

    data["harga_jual"] = pd.to_numeric(
        data["harga_jual"],
        errors="coerce"
    )

    data["harga_buyback"] = pd.to_numeric(
        data["harga_buyback"],
        errors="coerce"
    )

    data = data.dropna(
        subset=[
            "tanggal",
            "harga_jual",
            "harga_buyback"
        ]
    )

    data = data.sort_values(
        "tanggal"
    ).reset_index(
        drop=True
    )

    return data


# ============================================================
# LOAD MODEL
# ============================================================

@st.cache_resource
def load_models():

    if not os.path.exists(FILE_DT_MODEL):

        raise FileNotFoundError(
            f"File {FILE_DT_MODEL} tidak ditemukan."
        )

    if not os.path.exists(FILE_RF_MODEL):

        raise FileNotFoundError(
            f"File {FILE_RF_MODEL} tidak ditemukan."
        )

    dt_model = joblib.load(
        FILE_DT_MODEL
    )

    rf_model = joblib.load(
        FILE_RF_MODEL
    )

    return (
        dt_model,
        rf_model
    )


# ============================================================
# HITUNG 6 FITUR
# ============================================================

def calculate_six_returns(
    selling_prices,
    buyback_prices
):

    selling_prices = np.array(
        selling_prices,
        dtype=float
    )

    buyback_prices = np.array(
        buyback_prices,
        dtype=float
    )

    if len(selling_prices) != 4:
        raise ValueError(
            "Diperlukan 4 data harga jual."
        )

    if len(buyback_prices) != 4:
        raise ValueError(
            "Diperlukan 4 data harga buyback."
        )

    if np.any(
        selling_prices <= 0
    ):
        raise ValueError(
            "Harga jual harus lebih dari 0."
        )

    if np.any(
        buyback_prices <= 0
    ):
        raise ValueError(
            "Harga buyback harus lebih dari 0."
        )

    features = {

        "Price_Return_1":
            (
                selling_prices[3]
                /
                selling_prices[2]
            ) - 1,

        "Price_Return_2":
            (
                selling_prices[3]
                /
                selling_prices[1]
            ) - 1,

        "Price_Return_3":
            (
                selling_prices[3]
                /
                selling_prices[0]
            ) - 1,

        "Buyback_Return_1":
            (
                buyback_prices[3]
                /
                buyback_prices[2]
            ) - 1,

        "Buyback_Return_2":
            (
                buyback_prices[3]
                /
                buyback_prices[1]
            ) - 1,

        "Buyback_Return_3":
            (
                buyback_prices[3]
                /
                buyback_prices[0]
            ) - 1
    }

    return features


# ============================================================
# PREDIKSI MODEL
# ============================================================

def predict_direction(features):

    dt_model, rf_model = load_models()

    X = pd.DataFrame(
        [
            features
        ],
        columns=FITUR_FINAL
    )

    prediction_dt = dt_model.predict(
        X
    )[0]

    prediction_rf = rf_model.predict(
        X
    )[0]

    return (
        prediction_dt,
        prediction_rf
    )


# ============================================================
# SIMPAN RIWAYAT KLASIFIKASI
# ============================================================

def save_classification_history(
    id_user,
    mode_klasifikasi,
    tanggal_data,
    features,
    hasil_dt,
    hasil_rf
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO classification_history
            (
                id_user,
                mode_klasifikasi,
                tanggal_data,

                Price_Return_1,
                Price_Return_2,
                Price_Return_3,

                Buyback_Return_1,
                Buyback_Return_2,
                Buyback_Return_3,

                hasil_decision_tree,
                hasil_random_forest
            )
            VALUES
            (
                ?,
                ?,
                ?,

                ?,
                ?,
                ?,

                ?,
                ?,
                ?,

                ?,
                ?
            )
            """,
            (
                id_user,
                mode_klasifikasi,
                tanggal_data,

                features["Price_Return_1"],
                features["Price_Return_2"],
                features["Price_Return_3"],

                features["Buyback_Return_1"],
                features["Buyback_Return_2"],
                features["Buyback_Return_3"],

                hasil_dt,
                hasil_rf
            )
        )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# LOGIN PAGE
# ============================================================

def show_login_page():

    st.markdown(
        "<div class='main-title'>🥇 Klasifikasi Arah Harga Emas ANTAM</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<div class='sub-title'>"
        "Silakan login untuk menggunakan aplikasi."
        "</div>",
        unsafe_allow_html=True
    )

    tab_login, tab_register = st.tabs(
        [
            "Login",
            "Registrasi"
        ]
    )


    # ========================================================
    # LOGIN
    # ========================================================

    with tab_login:

        with st.form(
            "login_form"
        ):

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password"
            )

            submit_login = st.form_submit_button(
                "Login",
                use_container_width=True
            )


        if submit_login:

            user = login_user(
                username,
                password
            )

            if user is not None:

                st.session_state.logged_in = True

                st.session_state.id_user = (
                    user["id_user"]
                )

                st.session_state.username = (
                    user["username"]
                )

                st.session_state.page = (
                    "Beranda"
                )

                st.success(
                    "Login berhasil."
                )

                st.rerun()

            else:

                st.error(
                    "Username atau password salah."
                )


    # ========================================================
    # REGISTER
    # ========================================================

    with tab_register:

        with st.form(
            "register_form"
        ):

            new_username = st.text_input(
                "Username Baru"
            )

            new_password = st.text_input(
                "Password Baru",
                type="password"
            )

            confirm_password = st.text_input(
                "Konfirmasi Password",
                type="password"
            )

            submit_register = (
                st.form_submit_button(
                    "Registrasi",
                    use_container_width=True
                )
            )


        if submit_register:

            if (
                new_password
                !=
                confirm_password
            ):

                st.error(
                    "Konfirmasi password tidak sama."
                )

            else:

                success, message = (
                    register_user(
                        new_username,
                        new_password
                    )
                )

                if success:

                    st.success(
                        message
                    )

                    st.info(
                        "Silakan masuk menggunakan "
                        "akun yang baru dibuat."
                    )

                else:

                    st.error(
                        message
                    )


# ============================================================
# SIDEBAR
# ============================================================

def show_sidebar():

    with st.sidebar:

        st.markdown(
            "## 📊 Menu"
        )

        st.write(
            f"User: **{st.session_state.username}**"
        )

        st.divider()

        st.caption(
            "Navigasi"
        )

        menu = st.radio(
            "Navigasi",
            [
                "Beranda",
                "Data Historis",
                "Klasifikasi Arah Harga",
                "Perbandingan Model",
                "Riwayat Klasifikasi"
            ],
            index=[
                "Beranda",
                "Data Historis",
                "Klasifikasi Arah Harga",
                "Perbandingan Model",
                "Riwayat Klasifikasi"
            ].index(
                st.session_state.page
            ),
            label_visibility="collapsed"
        )

        if menu != st.session_state.page:

            st.session_state.page = menu

            st.rerun()

        st.divider()

        if st.button(
            "Logout",
            use_container_width=True
        ):

            st.session_state.logged_in = False
            st.session_state.id_user = None
            st.session_state.username = None
            st.session_state.page = "Beranda"

            st.rerun()


# ============================================================
# BERANDA
# ============================================================

def show_home():

    st.title(
        "🏠 Beranda"
    )

    st.write(
        f"Selamat datang, **{st.session_state.username}**."
    )

    st.write(
        """
        Aplikasi ini merupakan implementasi hasil penelitian
        klasifikasi arah perubahan harga jual emas ANTAM
        menggunakan algoritma Decision Tree dan Random Forest.
        """
    )

    st.divider()

    data = load_historical_data()

    if data.empty:

        st.warning(
            "Data historis belum tersedia di database."
        )

        return

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Jumlah Data Historis",
            f"{len(data):,}".replace(
                ",",
                "."
            )
        )

    with col2:

        st.metric(
            "Tanggal Awal",
            data["tanggal"]
            .min()
            .strftime("%d-%m-%Y")
        )

    with col3:

        st.metric(
            "Tanggal Akhir",
            data["tanggal"]
            .max()
            .strftime("%d-%m-%Y")
        )

    st.divider()

    st.subheader(
        "Fitur yang Digunakan"
    )

    fitur_df = pd.DataFrame(
        {
            "Fitur": FITUR_FINAL,
            "Kelompok": [
                "Harga Jual",
                "Harga Jual",
                "Harga Jual",
                "Buyback",
                "Buyback",
                "Buyback"
            ]
        }
    )

    st.dataframe(
        fitur_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# DATA HISTORIS
# ============================================================

def show_historical_data():

    st.title(
        "📅 Data Historis"
    )

    st.write(
        """
        Data historis harga jual dan harga buyback emas ANTAM
        yang tersimpan pada database aplikasi.
        """
    )

    data = load_historical_data()

    if data.empty:

        st.warning(
            "Belum terdapat data historis."
        )

        return

    tampil = data.copy()

    tampil["tanggal"] = (
        tampil["tanggal"]
        .dt.strftime("%Y-%m-%d")
    )

    tampil["harga_jual"] = (
        tampil["harga_jual"]
        .apply(format_rupiah)
    )

    tampil["harga_buyback"] = (
        tampil["harga_buyback"]
        .apply(format_rupiah)
    )

    tampil = tampil.rename(
        columns={
            "tanggal": "Tanggal",
            "harga_jual": "Harga Jual",
            "harga_buyback": "Harga Buyback"
        }
    )

    st.dataframe(
        tampil[
            [
                "Tanggal",
                "Harga Jual",
                "Harga Buyback"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# KLASIFIKASI ARAH HARGA
# ============================================================

def show_classification():

    st.title(
        "🔎 Klasifikasi Arah Harga"
    )

    st.write(
        """
        Pilih sumber data yang akan digunakan untuk
        menghasilkan klasifikasi arah perubahan harga
        pada observasi berikutnya.
        """
    )

    mode = st.radio(
        "Sumber Klasifikasi",
        [
            "Data Historis",
            "Input Manual"
        ],
        horizontal=True
    )


    # ========================================================
    # DATA HISTORIS
    # ========================================================

    if mode == "Data Historis":

        data = load_historical_data()

        if len(data) < 4:

            st.error(
                "Data historis minimal membutuhkan "
                "4 observasi."
            )

            return

        data_dates = data[
            "tanggal"
        ].dt.strftime(
            "%Y-%m-%d"
        ).tolist()


        selected_date = st.selectbox(
            "Pilih tanggal observasi",
            data_dates,
            index=len(data_dates) - 1
        )


        selected_datetime = pd.to_datetime(
            selected_date
        )


        data_before = data[
            data["tanggal"]
            <=
            selected_datetime
        ].copy()


        if len(data_before) < 4:

            st.error(
                "Tanggal yang dipilih belum memiliki "
                "empat observasi yang diperlukan."
            )

            return


        four_rows = data_before.tail(
            4
        ).copy()


        st.subheader(
            "Data yang Digunakan"
        )

        display_rows = four_rows.copy()

        display_rows["tanggal"] = (
            display_rows["tanggal"]
            .dt.strftime("%Y-%m-%d")
        )

        display_rows["harga_jual"] = (
            display_rows["harga_jual"]
            .apply(format_rupiah)
        )

        display_rows["harga_buyback"] = (
            display_rows["harga_buyback"]
            .apply(format_rupiah)
        )

        display_rows = display_rows.rename(
            columns={
                "tanggal": "Tanggal",
                "harga_jual": "Harga Jual",
                "harga_buyback": "Harga Buyback"
            }
        )

        st.dataframe(
            display_rows[
                [
                    "Tanggal",
                    "Harga Jual",
                    "Harga Buyback"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


        selling_prices = (
            four_rows[
                "harga_jual"
            ].tolist()
        )

        buyback_prices = (
            four_rows[
                "harga_buyback"
            ].tolist()
        )


        try:

            features = calculate_six_returns(
                selling_prices,
                buyback_prices
            )

        except Exception as error:

            st.error(
                str(error)
            )

            return


        st.subheader(
            "Enam Fitur Return"
        )

        fitur_tampil = pd.DataFrame(
            {
                "Fitur": FITUR_FINAL,
                "Nilai": [
                    format_return(
                        features[nama]
                    )
                    for nama in FITUR_FINAL
                ]
            }
        )

        st.dataframe(
            fitur_tampil,
            use_container_width=True,
            hide_index=True
        )


        st.info(
            "Klasifikasi menggunakan data yang tersedia "
            f"sampai tanggal {selected_date}. "
            "Harga pada observasi berikutnya belum digunakan "
            "sebagai input model."
        )


        if st.button(
            "🔎 Lakukan Klasifikasi",
            use_container_width=True
        ):

            try:

                (
                    hasil_dt,
                    hasil_rf
                ) = predict_direction(
                    features
                )


                save_classification_history(
                    st.session_state.id_user,
                    "Data Historis",
                    selected_date,
                    features,
                    hasil_dt,
                    hasil_rf
                )


                st.session_state.last_result = {
                    "mode": "Data Historis",
                    "tanggal": selected_date,
                    "features": features,
                    "dt": hasil_dt,
                    "rf": hasil_rf
                }


                st.success(
                    "Klasifikasi berhasil disimpan."
                )


            except Exception as error:

                st.error(
                    f"Proses klasifikasi gagal: {error}"
                )


    # ========================================================
    # INPUT MANUAL
    # ========================================================

    else:

        st.subheader(
            "Input Empat Observasi"
        )

        st.caption(
            """
            Masukkan data dari observasi paling lama
            sampai observasi terbaru.
            """
        )


        col1, col2 = st.columns(2)


        with col1:

            st.markdown(
                "### Harga Jual"
            )

            price_1 = st.number_input(
                "Harga Jual t-3",
                min_value=1.0,
                value=1000000.0,
                step=1000.0,
                key="manual_price_1"
            )

            price_2 = st.number_input(
                "Harga Jual t-2",
                min_value=1.0,
                value=1000000.0,
                step=1000.0,
                key="manual_price_2"
            )

            price_3 = st.number_input(
                "Harga Jual t-1",
                min_value=1.0,
                value=1000000.0,
                step=1000.0,
                key="manual_price_3"
            )

            price_4 = st.number_input(
                "Harga Jual t",
                min_value=1.0,
                value=1000000.0,
                step=1000.0,
                key="manual_price_4"
            )


        with col2:

            st.markdown(
                "### Harga Buyback"
            )

            buyback_1 = st.number_input(
                "Buyback t-3",
                min_value=1.0,
                value=900000.0,
                step=1000.0,
                key="manual_buyback_1"
            )

            buyback_2 = st.number_input(
                "Buyback t-2",
                min_value=1.0,
                value=900000.0,
                step=1000.0,
                key="manual_buyback_2"
            )

            buyback_3 = st.number_input(
                "Buyback t-1",
                min_value=1.0,
                value=900000.0,
                step=1000.0,
                key="manual_buyback_3"
            )

            buyback_4 = st.number_input(
                "Buyback t",
                min_value=1.0,
                value=900000.0,
                step=1000.0,
                key="manual_buyback_4"
            )


        if st.button(
            "🔎 Lakukan Klasifikasi",
            use_container_width=True
        ):

            try:

                selling_prices = [
                    price_1,
                    price_2,
                    price_3,
                    price_4
                ]

                buyback_prices = [
                    buyback_1,
                    buyback_2,
                    buyback_3,
                    buyback_4
                ]


                features = calculate_six_returns(
                    selling_prices,
                    buyback_prices
                )


                (
                    hasil_dt,
                    hasil_rf
                ) = predict_direction(
                    features
                )


                save_classification_history(
                    st.session_state.id_user,
                    "Input Manual",
                    None,
                    features,
                    hasil_dt,
                    hasil_rf
                )


                st.session_state.last_result = {
                    "mode": "Input Manual",
                    "tanggal": None,
                    "features": features,
                    "dt": hasil_dt,
                    "rf": hasil_rf
                }


                st.success(
                    "Klasifikasi berhasil disimpan."
                )


            except Exception as error:

                st.error(
                    f"Proses klasifikasi gagal: {error}"
                )


    # ========================================================
    # HASIL KLASIFIKASI
    # ========================================================

    if "last_result" in st.session_state:

        result = st.session_state.last_result

        st.divider()

        st.subheader(
            "Hasil Klasifikasi"
        )


        col1, col2 = st.columns(2)


        with col1:

            st.markdown(
                "### Decision Tree"
            )

            if result["dt"] == "Uptrend":

                st.success(
                    "UPTREND"
                )

            else:

                st.error(
                    "DOWNTREND"
                )


        with col2:

            st.markdown(
                "### Random Forest"
            )

            if result["rf"] == "Uptrend":

                st.success(
                    "UPTREND"
                )

            else:

                st.error(
                    "DOWNTREND"
                )


        if (
            result["dt"]
            ==
            result["rf"]
        ):

            st.info(
                "Kedua model menghasilkan klasifikasi "
                "yang sama."
            )

        else:

            st.warning(
                "Decision Tree dan Random Forest "
                "menghasilkan klasifikasi yang berbeda."
            )


# ============================================================
# LOAD HASIL PENELITIAN
# ============================================================

@st.cache_data
def load_research_results():

    if not os.path.exists(
        FILE_HASIL
    ):

        return None

    results = {}

    sheet_names = [
        (
            "holdout",
            "Holdout_80_20"
        ),
        (
            "prediksi",
            "Prediksi_Holdout"
        ),
        (
            "nested",
            "Nested_WalkForward"
        ),
        (
            "walk_mean",
            "WalkForward_Mean"
        ),
        (
            "walk_pooled",
            "WalkForward_Pooled"
        ),
        (
            "importance_dt",
            "Importance_DT"
        ),
        (
            "importance_rf",
            "Importance_RF"
        )
    ]


    for key, sheet in sheet_names:

        results[key] = pd.read_excel(
            FILE_HASIL,
            sheet_name=sheet
        )


    return results


# ============================================================
# PERBANDINGAN MODEL
# ============================================================

def show_model_comparison():

    st.title(
        "⚖️ Perbandingan Performa Model"
    )

    st.write(
        """
        Halaman ini menampilkan hasil evaluasi
        Decision Tree dan Random Forest berdasarkan
        hasil penelitian.
        """
    )


    try:

        results = load_research_results()

    except Exception as error:

        st.error(
            f"File hasil penelitian gagal dibaca: {error}"
        )

        return


    if results is None:

        st.error(
            f"File '{FILE_HASIL}' tidak ditemukan."
        )

        return


    # ========================================================
    # HOLDOUT
    # ========================================================

    st.subheader(
        "Hasil Evaluasi Holdout Kronologis 80:20"
    )


    holdout = results[
        "holdout"
    ].copy()


    model_holdout = holdout[
        holdout["Model"].isin(
            [
                "Decision Tree",
                "Random Forest"
            ]
        )
    ].copy()


    if model_holdout.empty:

        st.warning(
            "Data evaluasi holdout tidak tersedia."
        )

    else:

        display = model_holdout[
            [
                "Model",
                "Accuracy",
                "Precision_Macro",
                "Recall_Macro",
                "F1_Macro"
            ]
        ].copy()


        display = display.rename(
            columns={
                "Model": "Algoritma",
                "Accuracy": "Accuracy (%)",
                "Precision_Macro":
                    "Macro Precision (%)",
                "Recall_Macro":
                    "Macro Recall (%)",
                "F1_Macro":
                    "Macro F1-Score (%)"
            }
        )


        for column in [
            "Accuracy (%)",
            "Macro Precision (%)",
            "Macro Recall (%)",
            "Macro F1-Score (%)"
        ]:

            display[column] = (
                display[column]
                * 100
            ).round(2)


        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True
        )


        # ====================================================
        # METRIC CARDS
        # ====================================================

        st.subheader(
            "Ringkasan Performa"
        )


        dt_data = model_holdout[
            model_holdout["Model"]
            ==
            "Decision Tree"
        ]


        rf_data = model_holdout[
            model_holdout["Model"]
            ==
            "Random Forest"
        ]


        col1, col2 = st.columns(2)


        if not dt_data.empty:

            dt = dt_data.iloc[0]

            with col1:

                st.markdown(
                    "### Decision Tree"
                )

                st.metric(
                    "Accuracy",
                    f"{dt['Accuracy'] * 100:.2f}%"
                )

                st.metric(
                    "Macro Precision",
                    f"{dt['Precision_Macro'] * 100:.2f}%"
                )

                st.metric(
                    "Macro Recall",
                    f"{dt['Recall_Macro'] * 100:.2f}%"
                )

                st.metric(
                    "Macro F1-Score",
                    f"{dt['F1_Macro'] * 100:.2f}%"
                )


        if not rf_data.empty:

            rf = rf_data.iloc[0]

            with col2:

                st.markdown(
                    "### Random Forest"
                )

                st.metric(
                    "Accuracy",
                    f"{rf['Accuracy'] * 100:.2f}%"
                )

                st.metric(
                    "Macro Precision",
                    f"{rf['Precision_Macro'] * 100:.2f}%"
                )

                st.metric(
                    "Macro Recall",
                    f"{rf['Recall_Macro'] * 100:.2f}%"
                )

                st.metric(
                    "Macro F1-Score",
                    f"{rf['F1_Macro'] * 100:.2f}%"
                )


        # ====================================================
        # GRAFIK
        # ====================================================

        st.subheader(
            "Visualisasi Metrik"
        )


        grafik = (
            model_holdout
            .set_index("Model")
            [
                [
                    "Accuracy",
                    "Precision_Macro",
                    "Recall_Macro",
                    "F1_Macro"
                ]
            ]
            .T
            * 100
        )


        st.bar_chart(
            grafik
        )


    st.divider()


    # ========================================================
    # BASELINE
    # ========================================================

    st.subheader(
        "Baseline Kelas Mayoritas"
    )


    baseline = holdout[
        holdout["Model"]
        ==
        "Baseline"
    ]


    if not baseline.empty:

        baseline_row = (
            baseline.iloc[0]
        )


        col1, col2 = st.columns(2)


        with col1:

            st.metric(
                "Baseline Accuracy",
                f"{baseline_row['Accuracy'] * 100:.2f}%"
            )


        with col2:

            st.metric(
                "Baseline Macro F1-Score",
                f"{baseline_row['F1_Macro'] * 100:.2f}%"
            )


    st.divider()


    # ========================================================
    # CONFUSION MATRIX
    # ========================================================

    st.subheader(
        "Confusion Matrix"
    )


    prediksi = results[
        "prediksi"
    ].copy()


    if (
        "Trend" in prediksi.columns
        and
        "Prediksi_DT" in prediksi.columns
        and
        "Prediksi_RF" in prediksi.columns
    ):

        kelas = [
            "Downtrend",
            "Uptrend"
        ]


        cm_dt = pd.crosstab(
            prediksi["Trend"],
            prediksi["Prediksi_DT"]
        ).reindex(
            index=kelas,
            columns=kelas,
            fill_value=0
        )


        cm_rf = pd.crosstab(
            prediksi["Trend"],
            prediksi["Prediksi_RF"]
        ).reindex(
            index=kelas,
            columns=kelas,
            fill_value=0
        )


        col1, col2 = st.columns(2)


        with col1:

            st.markdown(
                "### Decision Tree"
            )

            st.dataframe(
                cm_dt,
                use_container_width=True
            )


        with col2:

            st.markdown(
                "### Random Forest"
            )

            st.dataframe(
                cm_rf,
                use_container_width=True
            )


    st.divider()


    # ========================================================
    # NESTED WALK-FORWARD
    # ========================================================

    st.subheader(
        "Validasi Nested Walk-Forward"
    )


    nested = results[
        "nested"
    ].copy()


    if not nested.empty:

        st.dataframe(
            nested,
            use_container_width=True,
            hide_index=True
        )


    st.subheader(
        "Rata-rata Performa Walk-Forward"
    )


    walk_mean = results[
        "walk_mean"
    ].copy()


    if not walk_mean.empty:

        st.dataframe(
            walk_mean,
            use_container_width=True,
            hide_index=True
        )


    st.divider()


    # ========================================================
    # FEATURE IMPORTANCE
    # ========================================================

    st.subheader(
        "Feature Importance"
    )


    importance_dt = results[
        "importance_dt"
    ].copy()


    importance_rf = results[
        "importance_rf"
    ].copy()


    col1, col2 = st.columns(2)


    with col1:

        st.markdown(
            "### Decision Tree"
        )

        st.dataframe(
            importance_dt,
            use_container_width=True,
            hide_index=True
        )


    with col2:

        st.markdown(
            "### Random Forest"
        )

        st.dataframe(
            importance_rf,
            use_container_width=True,
            hide_index=True
        )


    # ========================================================
    # KESIMPULAN
    # ========================================================

    st.divider()

    st.subheader(
        "Kesimpulan Perbandingan"
    )


    if (
        not dt_data.empty
        and
        not rf_data.empty
    ):

        dt_f1 = dt_data.iloc[0][
            "F1_Macro"
        ]

        rf_f1 = rf_data.iloc[0][
            "F1_Macro"
        ]


        if rf_f1 > dt_f1:

            st.info(
                """
                Berdasarkan evaluasi holdout,
                Random Forest memperoleh Macro F1-Score
                lebih tinggi dibandingkan Decision Tree.
                """
            )

        elif dt_f1 > rf_f1:

            st.info(
                """
                Berdasarkan evaluasi holdout,
                Decision Tree memperoleh Macro F1-Score
                lebih tinggi dibandingkan Random Forest.
                """
            )

        else:

            st.info(
                """
                Berdasarkan evaluasi holdout,
                kedua model memperoleh Macro F1-Score
                yang sama.
                """
            )


# ============================================================
# RIWAYAT KLASIFIKASI
# ============================================================

def show_classification_history():

    st.title(
        "📋 Riwayat Klasifikasi"
    )

    st.write(
        """
        Riwayat klasifikasi yang dilakukan oleh
        pengguna yang sedang login.
        """
    )


    conn = get_connection()

    try:

        query = """
            SELECT
                waktu_klasifikasi,
                mode_klasifikasi,
                tanggal_data,

                Price_Return_1,
                Price_Return_2,
                Price_Return_3,

                Buyback_Return_1,
                Buyback_Return_2,
                Buyback_Return_3,

                hasil_decision_tree,
                hasil_random_forest

            FROM classification_history

            WHERE id_user = ?

            ORDER BY waktu_klasifikasi DESC
        """


        history = pd.read_sql_query(
            query,
            conn,
            params=(
                st.session_state.id_user,
            )
        )

    finally:

        conn.close()


    st.metric(
        "Jumlah Klasifikasi",
        len(history)
    )


    st.divider()


    if history.empty:

        st.info(
            "Belum terdapat riwayat klasifikasi."
        )

        return


    history = history.rename(
        columns={
            "waktu_klasifikasi":
                "Waktu Klasifikasi",

            "mode_klasifikasi":
                "Mode",

            "tanggal_data":
                "Tanggal Data",

            "Price_Return_1":
                "Price Return 1",

            "Price_Return_2":
                "Price Return 2",

            "Price_Return_3":
                "Price Return 3",

            "Buyback_Return_1":
                "Buyback Return 1",

            "Buyback_Return_2":
                "Buyback Return 2",

            "Buyback_Return_3":
                "Buyback Return 3",

            "hasil_decision_tree":
                "Decision Tree",

            "hasil_random_forest":
                "Random Forest"
        }
    )


    st.dataframe(
        history,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# PROGRAM UTAMA
# ============================================================

if not st.session_state.logged_in:

    show_login_page()

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

show_sidebar()


# ============================================================
# ROUTING HALAMAN
# ============================================================

if st.session_state.page == "Beranda":

    show_home()


elif st.session_state.page == "Data Historis":

    show_historical_data()


elif (
    st.session_state.page
    ==
    "Klasifikasi Arah Harga"
):

    show_classification()


elif (
    st.session_state.page
    ==
    "Perbandingan Model"
):

    show_model_comparison()


elif (
    st.session_state.page
    ==
    "Riwayat Klasifikasi"
):

    show_classification_history()
