import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
import locale

st.set_page_config(layout="wide")

try:
    locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')
except locale.Error as e:
    print(f"ロケール設定エラー: {e}")

DB_FILE = "runs.db"
TARGET_DIR = "../DAQ/"
FORMAT_STRING = '%a %m月 %d %H:%M:%S %Y'
DISPLAY_FORMAT = '%Y-%m-%d %H:%M:%S'
DB_FORMAT = '%Y-%m-%dT%H:%M:%S'

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
                        start_time = datetime.strptime(start_str, FORMAT_STRING)
                    if lines[2].startswith("Stop time = "):
                        stop_str = lines[2].split("= ")[1].strip()
                        stop_time = datetime.strptime(stop_str, FORMAT_STRING)
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
        if entry.is_dir() and entry.name.startswith("run"):
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

def handle_comment_change():
    if "run_table" in st.session_state and "edited_rows" in st.session_state["run_table"]:
        edited_rows = st.session_state["run_table"]["edited_rows"]
        runs = fetch_all_runs() # 現在の Run 情報を取得

        if runs:
            df_runs = pd.DataFrame(runs, columns=['RunId', 'Start time', 'Stop time', 'Comment'])
            updated = False # 更新があったかどうかを追跡

            for index, edited_data in edited_rows.items():
                run_id_to_update = df_runs.iloc[index]['RunId']
                comment_to_update = edited_data.get('Comment')
                if run_id_to_update is not None:
                    update_comment(run_id_to_update, comment_to_update)
                    updated = True

            if updated:
                st.session_state["comments_updated"] = not st.session_state.get("comments_updated", False) # 状態を更新

# Streamlit アプリケーション
if __name__ == "__main__":
    st.title("Run Summary")

    create_table()

    if st.button("Update"):
        update_database()
        st.session_state["data_updated"] = not st.session_state.get("data_updated", False) # 状態を更新
        st.rerun()

    runs = fetch_all_runs()

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
        df = df[['RunId', 'Start time', 'Stop time', 'Duration', 'Comment']]
        
        column_config = {
            "RunId": st.column_config.Column("RunId", width="small", disabled=True),
            "Start time": st.column_config.Column("Start time", disabled=True),
            "Stop time": st.column_config.Column("Stop time", disabled=True),
            "Duration": st.column_config.Column("Duration", width="small", disabled=True),
            "Comment": st.column_config.Column("Comment", width="large")
        }

        edited_df = st.data_editor(
            df,
            key="run_table",
            on_change=handle_comment_change,
            hide_index=True,
            column_config=column_config
        )

        if "comments_updated" in st.session_state:
            pass

    else:
        st.info("No run information available.")