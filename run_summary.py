import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
import locale
from contextlib import contextmanager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PROJECT_NAME = os.path.basename(PROJECT_DIR)
APP_TITLE = f"Run Summary for {PROJECT_NAME}"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🗓️",                  # 任意（絵文字や画像）
    layout="wide"                    # 任意
)

LOCALE_CANDIDATES = {
    "ja": ["ja_JP.UTF-8", "ja_JP", "Japanese_Japan.932"],
    "en": ["en_US.UTF-8", "en_US", "C"]
}

FORMAT_CANDIDATES = [
    ("ja", '%a %m月 %d %H:%M:%S %Y'),
    ("en", '%a %b %d %H:%M:%S %Y')
]

@contextmanager
def temporary_lc_time(locale_name):
    current_locale = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, locale_name)
        yield
    finally:
        locale.setlocale(locale.LC_TIME, current_locale)


def set_default_time_locale():
    for language in ["ja", "en"]:
        for locale_name in LOCALE_CANDIDATES[language]:
            try:
                locale.setlocale(locale.LC_TIME, locale_name)
                return
            except locale.Error:
                continue
    print("ロケール設定エラー: 利用可能な ja/en ロケールが見つかりませんでした。")


def parse_datetime_flexible(value):
    for language, format_string in FORMAT_CANDIDATES:
        for locale_name in LOCALE_CANDIDATES[language]:
            try:
                with temporary_lc_time(locale_name):
                    return datetime.strptime(value, format_string)
            except (locale.Error, ValueError):
                continue
    return None

set_default_time_locale()

DB_FILE = "runs.db"
TARGET_DIR = "../DAQ/"
DISPLAY_FORMAT = '%Y-%m-%d %H:%M:%S'
DB_FORMAT = '%Y-%m-%dT%H:%M:%S'
EDITABLE_FIELDS_FILE = os.path.join(SCRIPT_DIR, "editable_columns.txt")
BASE_COLUMNS = ['RunId', 'Start time', 'Stop time', 'Duration']


def get_extra_editable_fields():
    if not os.path.exists(EDITABLE_FIELDS_FILE):
        return []

    fields = []
    with open(EDITABLE_FIELDS_FILE, encoding='utf-8') as f:
        for line in f:
            parts = [part.strip() for part in line.replace(',', '\n').splitlines()]
            for part in parts:
                if part:
                    fields.append(part)

    reserved = set(BASE_COLUMNS + ['Comment'])
    deduped = []
    seen = set()
    for field in fields:
        if field in reserved or field in seen:
            continue
        deduped.append(field)
        seen.add(field)
    return deduped


def get_editable_columns():
    return ['Comment'] + get_extra_editable_fields()

def get_creation_time(dir_path):
    timestamp = os.path.getctime(dir_path)
    dt_object = datetime.fromtimestamp(timestamp)
    return dt_object.strftime(DB_FORMAT)

def get_run_times(dir_path, info_file_path):
    if os.path.exists(info_file_path):
        start_time = None
        stop_time = None
        try:
            with open(info_file_path, encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) >= 3:
                    if lines[1].startswith("Start time = "):
                        start_str = lines[1].split("= ")[1].strip()
                        start_time = parse_datetime_flexible(start_str)
                    if lines[2].startswith("Stop time = "):
                        stop_str = lines[2].split("= ")[1].strip()
                        stop_time = parse_datetime_flexible(stop_str)
                    return start_time, stop_time, False
                else:
                    return None, None, False
        except FileNotFoundError:
            return get_creation_time(dir_path), None, True
        except ValueError:
            return None, None, False
        except Exception as e:
            print(f"get_run_times で予期せぬエラー: {e}")
            return None, None, False
    else:
        return get_creation_time(dir_path), None, True

def create_table():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            start_time TEXT,
            stop_time TEXT,
            comment TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_fields (
            run_id TEXT,
            field_name TEXT,
            value TEXT,
            PRIMARY KEY (run_id, field_name)
        )
    """)
    conn.commit()
    conn.close()

def insert_or_update_run_info(run_id, start_time, stop_time, comment=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO runs (run_id, start_time, stop_time, comment)
        VALUES (?, ?, ?, ?)
    """, (run_id, start_time, stop_time, comment))
    conn.commit()
    conn.close()

def update_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for entry in os.scandir(TARGET_DIR):
        if entry.is_dir():
            run_id = entry.name
            dir_path = os.path.join(TARGET_DIR, entry.name)
            info_file_path = os.path.join(dir_path, f"{entry.name}_info.txt")
            start_dt, stop_dt, from_creation = get_run_times(dir_path, info_file_path)

            if start_dt:
                start_str = start_dt.isoformat() if isinstance(start_dt, datetime) else start_dt
                stop_str = stop_dt.isoformat() if isinstance(stop_dt, datetime) else stop_dt

                # 既存のレコードを検索
                cursor.execute("SELECT run_id FROM runs WHERE run_id = ?", (run_id,))
                existing_record = cursor.fetchone()

                if existing_record:
                    # レコードが存在する場合は更新
                    cursor.execute("""
                        UPDATE runs
                        SET start_time = ?, stop_time = ?
                        WHERE run_id = ?
                    """, (start_str, stop_str, run_id))
                else:
                    # レコードが存在しない場合は新規挿入 (コメントは初期値 None)
                    cursor.execute("""
                        INSERT INTO runs (run_id, start_time, stop_time, comment)
                        VALUES (?, ?, ?, NULL)
                    """, (run_id, start_str, stop_str))

    conn.commit()
    conn.close()
    
def fetch_all_runs():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT run_id, start_time, stop_time, comment FROM runs ORDER BY start_time DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_extra_field_values(run_ids, field_names):
    if not run_ids or not field_names:
        return {}

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    run_placeholders = ','.join(['?'] * len(run_ids))
    field_placeholders = ','.join(['?'] * len(field_names))
    cursor.execute(
        f"""
        SELECT run_id, field_name, value
        FROM run_fields
        WHERE run_id IN ({run_placeholders})
          AND field_name IN ({field_placeholders})
        """,
        run_ids + field_names
    )
    rows = cursor.fetchall()
    conn.close()

    values_map = {}
    for run_id, field_name, value in rows:
        if run_id not in values_map:
            values_map[run_id] = {}
        values_map[run_id][field_name] = value
    return values_map

def update_comment(run_id, comment):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if comment is None or comment == "":
        cursor.execute("""
            UPDATE runs
            SET comment = NULL
            WHERE run_id = ?
        """, (run_id,))
    else:
        cursor.execute("""
            UPDATE runs
            SET comment = ?
            WHERE run_id = ?
        """, (comment, run_id))
    conn.commit()
    conn.close()


def update_extra_field(run_id, field_name, value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if value is None or value == "":
        cursor.execute(
            """
            DELETE FROM run_fields
            WHERE run_id = ? AND field_name = ?
            """,
            (run_id, field_name)
        )
    else:
        cursor.execute(
            """
            INSERT INTO run_fields (run_id, field_name, value)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id, field_name) DO UPDATE SET value = excluded.value
            """,
            (run_id, field_name, value)
        )
    conn.commit()
    conn.close()

def handle_table_change():
    if "run_table" in st.session_state and "edited_rows" in st.session_state["run_table"]:
        edited_rows = st.session_state["run_table"]["edited_rows"]
        run_id_order = st.session_state.get("run_id_order", [])
        editable_columns = st.session_state.get("editable_columns", ['Comment'])

        if run_id_order:
            updated = False # 更新があったかどうかを追跡

            for index, edited_data in edited_rows.items():
                if index >= len(run_id_order):
                    continue
                run_id_to_update = run_id_order[index]
                if run_id_to_update is None:
                    continue

                for column_name in editable_columns:
                    if column_name not in edited_data:
                        continue
                    value_to_update = edited_data.get(column_name)
                    if column_name == 'Comment':
                        update_comment(run_id_to_update, value_to_update)
                    else:
                        update_extra_field(run_id_to_update, column_name, value_to_update)
                    updated = True

            if updated:
                st.session_state["table_updated"] = not st.session_state.get("table_updated", False) # 状態を更新

# Streamlit アプリケーション
if __name__ == "__main__":

    st.title(APP_TITLE)

    create_table()

    if st.button("Update"):
        update_database()
        st.session_state["data_updated"] = not st.session_state.get("data_updated", False) # 状態を更新
        st.rerun()

    runs = fetch_all_runs()
    editable_columns = get_editable_columns()
    st.session_state["editable_columns"] = editable_columns

    if runs:
        df = pd.DataFrame(runs, columns=['RunId', 'Start time', 'Stop time', 'Comment'])
        df['Start time'] = pd.to_datetime(df['Start time']).dt.strftime(DISPLAY_FORMAT)
        df['Stop time'] = df['Stop time'].apply(lambda x: pd.to_datetime(x).strftime(DISPLAY_FORMAT) if pd.notna(x) else '')

        df['start time dt'] = pd.to_datetime(df['Start time'], errors='coerce')
        df['stop time dt'] = pd.to_datetime(df['Stop time'], errors='coerce')

        df['Duration'] = (df['stop time dt'] - df['start time dt']).apply(
            lambda x: f"{x.components.hours:02}:{x.components.minutes:02}:{x.components.seconds:02}"
            if pd.notna(x) and x.days == 0 else (str(x) if pd.notna(x) else '')
        )

        extra_columns = [column for column in editable_columns if column != 'Comment']
        run_ids = df['RunId'].tolist()
        extra_values_map = fetch_extra_field_values(run_ids, extra_columns)

        for column in extra_columns:
            df[column] = df['RunId'].apply(
                lambda run_id: extra_values_map.get(run_id, {}).get(column, '')
            )

        display_columns = BASE_COLUMNS + extra_columns + ['Comment']
        df = df[display_columns]
        st.session_state["run_id_order"] = df['RunId'].tolist()
        
        column_config = {
            "RunId": st.column_config.Column("RunId", width="small", disabled=True),
            "Start time": st.column_config.Column("Start time", disabled=True),
            "Stop time": st.column_config.Column("Stop time", disabled=True),
            "Duration": st.column_config.Column("Duration", width="small", disabled=True),
            "Comment": st.column_config.Column("Comment", width="large")
        }

        for column in extra_columns:
            column_config[column] = st.column_config.Column(column, width="small")

        edited_df = st.data_editor(
            df,
            key="run_table",
            on_change=handle_table_change,
            hide_index=True,
            column_config=column_config
        )

        if "table_updated" in st.session_state:
            pass

    else:
        st.info("No run information available.")