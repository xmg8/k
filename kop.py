# 你提供的最新代码 (已包含你对日志的修改)
import requests
import time
from urllib.parse import urlencode
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog, Toplevel
import threading
import sys
import ssl
import mysql.connector
from mysql.connector import Error as MySQLError
from werkzeug.security import generate_password_hash, check_password_hash
import winsound # 用于播放声音 (Windows only)
import base64 # 用于简单的缓存混淆

# --- MySQL Database Configuration ---
MYSQL_HOST = "152.136.171.223"
MYSQL_USER = "wxxmg888"
MYSQL_PASSWORD = "xmg888.top"
MYSQL_DATABASE = "wxxmg888"

# --- 好猪码 API 配置 ---
API_ACCOUNT = "011474da7ce8c4d4fe58ad3eb95595fba150872eaf35cc85d692b2b209ac61c3"
API_PASSWORD = "2128c8ba18eba394cbfb99c6c906a9b5199d9f94cd825fbcd30c41a0745281e3"
PROJECT_ID = "78478"
SERVERS = [
    "https://api.haozhuma.com",
    "https://api.haozhuma.cn",
    "https://api.haozhuyun.com",
    "https://api.haozhuyun.cn"
]
TOKEN_EXPIRED_ERROR_CODE = "E0008" # 示例: 替换为实际错误码

# --- 路径处理 ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
# TOKEN_FILE 不再需要
CACHE_FILE = os.path.join(application_path, "usage_cache.dat") # 本地缓存文件

# --- API 请求头 ---
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

# --- 常量 ---
GENERIC_ERROR_MSG = "发生错误，请联系管理员。"
ADMIN_CONTACT_MSG = "，请联系管理员。"
DB_RETRY_COUNT = 10
DB_RETRY_DELAY = 2

# --- 数据库连接测试 ---
def test_database_connection():
    """测试到 MySQL 数据库的连接，带重试"""
    for attempt in range(DB_RETRY_COUNT):
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE, connect_timeout=5
            )
            if conn.is_connected(): conn.close(); return True
        except MySQLError:
            if attempt < DB_RETRY_COUNT - 1: time.sleep(DB_RETRY_DELAY)
            else: messagebox.showerror("数据库连接失败", GENERIC_ERROR_MSG + f"\n(尝试 {DB_RETRY_COUNT} 次后失败)"); return False
        except Exception:
             if attempt == DB_RETRY_COUNT - 1: messagebox.showerror("连接错误", GENERIC_ERROR_MSG)
             return False
    return False

# --- GUI 应用主类 ---
class SmsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("无尽冬日接码工具 - 未登录")
        self.root.geometry("600x510")

        self.token = None; self.phone_number = None; self.server = None
        self.is_working = False; self.auto_fetch_job = None
        self.logged_in_user_id = None; self.logged_in_username = None; self.remaining_uses = 0

        self._create_main_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_app_closing)
        self.root.after(10, self.show_login_window)

    def _create_main_widgets(self):
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(pady=10, padx=10, fill=tk.X); control_frame.columnconfigure(1, weight=1)
        ttk.Label(control_frame, text="剩余次数:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.uses_var = tk.StringVar(value="--"); self.uses_label = ttk.Label(control_frame, textvariable=self.uses_var, width=15, anchor=tk.W)
        self.uses_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(control_frame, text="当前用户:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)
        self.username_var = tk.StringVar(value="未登录"); self.username_label = ttk.Label(control_frame, textvariable=self.username_var, anchor=tk.E)
        self.username_label.grid(row=0, column=3, padx=5, pady=5, sticky=tk.E)
        ttk.Label(control_frame, text="手机号码:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.phone_var = tk.StringVar(value="尚未获取"); self.phone_entry = ttk.Entry(control_frame, textvariable=self.phone_var, state='readonly', width=20)
        self.phone_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(control_frame, text="验证码:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.code_var = tk.StringVar(value="尚未获取"); self.code_entry = ttk.Entry(control_frame, textvariable=self.code_var, state='readonly', width=20)
        self.code_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        self.get_phone_btn = ttk.Button(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=15, state=tk.DISABLED)
        self.get_phone_btn.grid(row=1, column=2, padx=(10,5), pady=5, sticky=tk.E)
        self.copy_phone_btn = ttk.Button(control_frame, text="复制手机号码", command=self.copy_phone, width=15, state=tk.DISABLED)
        self.copy_phone_btn.grid(row=1, column=3, padx=5, pady=5, sticky=tk.E)
        self.copy_code_btn = ttk.Button(control_frame, text="复制验证码", command=self.copy_code, width=15, state=tk.DISABLED)
        self.copy_code_btn.grid(row=2, column=3, padx=5, pady=5, sticky=tk.E)
        self.blacklist_btn = ttk.Button(control_frame, text="拉黑手机号码", command=self.start_blacklist_thread, width=15, state=tk.DISABLED)
        self.blacklist_btn.grid(row=3, column=3, padx=5, pady=10, sticky=tk.E)
        self.sound_enabled_var = tk.BooleanVar(value=True)
        sound_check = ttk.Checkbutton(control_frame, text="声音提示", variable=self.sound_enabled_var)
        sound_check.grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky=tk.W)
        log_frame = ttk.LabelFrame(self.root, text="日志输出", padding="10")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.status_var = tk.StringVar(value="请先登录.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def show_login_window(self):
        LoginWindow(self.root, self)

    def on_login_success(self, user_id, username, remaining_uses):
        # --- 你修改后的版本 ---
        self.logged_in_user_id = user_id; self.logged_in_username = username;
        cached_uses = self._read_usage_cache()
        if cached_uses is not None and cached_uses <= remaining_uses:
             self.remaining_uses = cached_uses
            # 移除日志
        else:
             self.remaining_uses = remaining_uses
             self._write_usage_cache(remaining_uses)
            # 移除日志
        self.root.deiconify(); self.root.title(f"无尽冬日 - 用户: {username}") # 你修改了标题
        self.username_var.set(username); self.uses_var.set(str(self.remaining_uses))
        self.status_var.set("登录成功，正在初始化 API...")
        # 移除日志
        self.start_initial_login_thread()
        self.update_ui_state(False)
        # 移除日志

    # --- 日志、状态、UI 更新 ---
    def log_message(self, message, level="INFO"):
        if level == "INFO" and self.root: self.root.after(0, self._append_log, message)
    def _append_log(self, message):
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        except tk.TclError: pass
    def set_status(self, message):
        if self.root:
             try: self.root.after(0, self.status_var.set, message)
             except tk.TclError: pass
    def update_ui_state(self, working):
        self.is_working = working; is_logged_in = bool(self.logged_in_user_id)
        can_get_phone = is_logged_in and not working and self.remaining_uses > 0
        get_phone_state = tk.NORMAL if can_get_phone else tk.DISABLED
        phone_available = bool(self.phone_number)
        code_val = self.code_var.get()
        code_available = code_val and code_val not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]
        try:
            self.get_phone_btn.config(state=get_phone_state)
            blacklist_state = tk.DISABLED if not is_logged_in or working or not phone_available else tk.NORMAL
            copy_phone_state = tk.DISABLED if not phone_available else tk.NORMAL
            copy_code_state = tk.DISABLED if not is_logged_in or working or not code_available else tk.NORMAL
            self.blacklist_btn.config(state=blacklist_state); self.copy_phone_btn.config(state=copy_phone_state); self.copy_code_btn.config(state=copy_code_state)
            if not is_logged_in: self.set_status("请先登录.")
            else:
                current_status = self.status_var.get()
                if working:
                    if "等待获取验证码" not in current_status: self.set_status("正在处理...")
                elif "等待获取验证码" not in current_status:
                     status_msg = f"就绪. 剩余次数: {self.remaining_uses}"
                     if self.remaining_uses <= 0: status_msg += " (次数不足)"
                     self.set_status(status_msg)
        except tk.TclError: pass

    # --- 启动后台任务的方法 ---
    def start_initial_login_thread(self):
        self.set_status("正在初始化 API 连接...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True); thread.start()
    def start_get_phone_thread(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working: return
        if self.remaining_uses <= 0: messagebox.showwarning("次数不足", "您的剩余使用号码数量不足，请联系管理员充值。"); self.log_message("可用号码数量不足，请联系管理员充值。"); return # 你修改了提示信息
        if not self.token or not self.server: messagebox.showerror("错误", "连接未就绪"+ADMIN_CONTACT_MSG); return
        if self.auto_fetch_job:
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None
        self.update_ui_state(True); self.phone_var.set("正在获取..."); self.code_var.set("尚未获取")
        self.log_message(f"开始获取手机号 (剩余: {self.remaining_uses})...")
        thread = threading.Thread(target=self._get_phone_task, daemon=True); thread.start()
    def start_automatic_code_fetch(self):
        self.auto_fetch_job = None
        if not self.phone_number: self.update_ui_state(False); return
        if not self.logged_in_user_id: return
        self.is_working = True; self.set_status("正在获取验证码..."); self.code_var.set("正在获取...")
        self.update_ui_state(True)
        self.log_message(f"开始为 {self.phone_number} 获取验证码...")
        thread = threading.Thread(target=self._get_code_task_automatic, daemon=True); thread.start()
    def start_blacklist_thread(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working: return
        if not self.phone_number: messagebox.showerror("错误", "没有可用的手机号码。"); return
        if self.auto_fetch_job:
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None; self.log_message("已取消等待获取验证码。"); self.set_status("就绪.")
        if messagebox.askyesno("确认", f"确定要拉黑号码 {self.phone_number} 吗？"):
            self.update_ui_state(True); self.log_message(f"尝试拉黑号码: {self.phone_number}")
            thread = threading.Thread(target=self._blacklist_task, daemon=True); thread.start()
        else: self.log_message("拉黑操作已取消。")

    # --- 后台任务方法 ---
    def _initial_login_task(self):
        """后台初始化好猪码 Token (每次启动都获取)"""
        try:
            self.try_login() # 总是尝试登录获取新 Token
            # --- 你已移除 API 初始化成功日志 ---
            self.root.after(0, self.update_ui_state, False)
        except Exception: # 捕获 try_login 可能抛出的异常
            self.log_message(GENERIC_ERROR_MSG, level="ERROR")
            self.root.after(0, lambda: messagebox.showerror("API 错误", "无法初始化接码服务"+ADMIN_CONTACT_MSG))
            self.set_status("API 连接失败"+ADMIN_CONTACT_MSG)

    def _get_phone_task(self):
        phone_obtained = False
        try:
            phone = self.get_phone_number()
            if phone:
                phone_obtained = True
                self.root.after(0, lambda p=phone: self.phone_var.set(p))
                self.root.after(0, self.update_ui_state, False)
                self._play_sound_if_enabled("SystemAsterisk")
                self.log_message("号码获取成功，10 秒后开始接收验证码...") # 你修改了日志
                self.set_status("等待获取验证码 (10s)...")
                try: self.auto_fetch_job = self.root.after(10000, self.start_automatic_code_fetch)
                except tk.TclError: phone_obtained = False
            else: self.root.after(0, lambda: self.phone_var.set("获取失败"))
        except Exception: self.root.after(0, lambda: self.phone_var.set("获取异常")); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
            if not phone_obtained: self.root.after(0, self.update_ui_state, False)
    def _get_code_task_automatic(self):
        code = None; restart_needed = False
        try:
            code = self.wait_for_verification_code(timeout=200)
            if code:
                self.root.after(0, lambda c=code: self.code_var.set(c))
                self._play_sound_if_enabled("SystemHand")
                if not self._decrement_usage():
                     messagebox.showerror("错误", "扣减次数失败"+ADMIN_CONTACT_MSG)
                     self.root.after(0, self.update_ui_state, False); return
                self.root.after(0, self.update_ui_state, False)
            else: # Timeout
                self.log_message("验证码获取超时。")
                self.root.after(0, lambda: self.code_var.set("获取超时"))
                if self.phone_number:
                    self.log_message(f"自动拉黑号码: {self.phone_number}")
                    blacklist_success = self.blacklist_phone()
                    if blacklist_success: restart_needed = True; self.root.after(0, self.restart_process_after_timeout)
                    else: pass
                else: pass
        except Exception: self.root.after(0, lambda: self.code_var.set("获取异常")); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
            if not restart_needed: self.root.after(0, self.update_ui_state, False)
    def _blacklist_task(self):
        try: self.blacklist_phone()
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally: self.root.after(0, self.update_ui_state, False)
    def restart_process_after_timeout(self):
        try:
            self.log_message("验证码超时，自动重新获取手机号...")
            self.phone_var.set("重新获取..."); self.code_var.set("尚未获取")
            self.is_working = False; self.update_ui_state(False)
            self.root.after(50, self.start_get_phone_thread)
        except tk.TclError: pass

    # --- 数据库交互方法 ---
    def _get_db_connection(self):
        last_error = None
        for attempt in range(DB_RETRY_COUNT):
            try:
                conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE, connect_timeout=5)
                if conn.is_connected(): return conn
            except MySQLError as e: last_error = e; time.sleep(DB_RETRY_DELAY)
            except Exception as e: last_error = e; break
        self.log_message(GENERIC_ERROR_MSG, level="ERROR"); messagebox.showerror("数据库连接失败", GENERIC_ERROR_MSG + f"\n(重试 {DB_RETRY_COUNT} 次失败)"); return None
    def _decrement_usage(self):
        if not self.logged_in_user_id: return False
        conn = self._get_db_connection(); cursor = None
        if not conn: return False
        try:
            cursor = conn.cursor()
            sql = "UPDATE users SET remaining_uses = GREATEST(0, remaining_uses - 1) WHERE id = %s"
            cursor.execute(sql, (self.logged_in_user_id,))
            conn.commit()
            if self.remaining_uses > 0: self.remaining_uses -= 1
            self._write_usage_cache(self.remaining_uses)
            self.log_message(f"可用号码数量已扣减，剩余: {self.remaining_uses}") # 你修改了日志
            self.root.after(0, lambda: self.uses_var.set(str(self.remaining_uses)))
            return True
        except MySQLError: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); return False
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); return False
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    # --- 本地缓存方法 ---
    def _encode_uses(self, uses):
        try: return base64.b64encode(str(uses).encode('utf-8')).decode('utf-8')
        except: return None
    def _decode_uses(self, encoded_uses):
        try: return int(base64.b64decode(encoded_uses.encode('utf-8')).decode('utf-8'))
        except: return None
    def _write_usage_cache(self, uses):
        encoded = self._encode_uses(uses)
        if encoded:
            try:
                with open(CACHE_FILE, 'w') as f: f.write(encoded)
            except IOError: pass
    def _read_usage_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f: encoded = f.read().strip()
                return self._decode_uses(encoded)
            except IOError: return None
        return None
    def _delete_usage_cache(self):
        try:
            if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
            # 不再记录缓存清除日志
        except OSError: pass

    # --- API 交互方法 ---
    # 移除 read_token 和 save_token
    def try_login(self):
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                response = requests.get(login_url, headers=headers, timeout=15, verify=True)
                response.raise_for_status(); data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0": self.server = s; self.token = data["token"]; return
            except requests.exceptions.RequestException: pass
            except Exception: pass
        self.server = None; self.token = None
        raise Exception("API 登录失败")
    def handle_api_error(self, data, operation_name):
        error_code = data.get("code"); error_msg = data.get('msg', '未知错误')
        is_waiting_msg = "尚未接收" in error_msg or "等待" == error_msg or "没有可用" in error_msg
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE: self.log_message("尝试重连..."); self.token = None # 你修改了日志
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg: pass
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            try: self.try_login(); return True
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("发生致命错误", "无法自动登录"+ADMIN_CONTACT_MSG)); return False # 你修改了弹窗标题
        if error_code != 0 and str(error_code) != "0" and not is_waiting_msg and str(error_code) != TOKEN_EXPIRED_ERROR_CODE: return False
        return True
    # --- 移除 get_balance 方法 ---
    # def get_balance(self): ...
    def get_phone_number(self):
        if not self.token or not self.server: self.log_message("未初始化"+ADMIN_CONTACT_MSG, level="ERROR"); return None
        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
        retry_delay = 3; self.log_message("正在获取手机号...")
        while True:
            if not self.token: self.log_message("失效"+ADMIN_CONTACT_MSG, level="ERROR"); return None # 你修改了日志
            try:
                response = requests.get(url, headers=headers, timeout=20, verify=True)
                data = response.json(); code = data.get("code"); msg = data.get("msg", "")
                if code == 0 or str(code) == "0":
                    phone = data.get("phone")
                    if phone: self.phone_number = phone; self.root.after(0, lambda: self.code_var.set("尚未获取")); self.log_message(f"成功获取手机号: {self.phone_number}"); return self.phone_number
                    else: time.sleep(retry_delay); continue
                elif str(code) == "-1" and ("没有可用手机号" in msg or "请稍后再试" in msg or "等待" == msg): time.sleep(retry_delay); continue
                else:
                    if self.handle_api_error(data, "获取手机号"): url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"; continue
                    else: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("错误", "获取手机号失败"+ADMIN_CONTACT_MSG)); self.phone_number = None; return None
            except requests.exceptions.RequestException: time.sleep(5); continue
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); self.phone_number = None; return None
    def wait_for_verification_code(self, timeout=200):
        if not self.token or not self.server or not self.phone_number: return None
        start_time = time.time(); polling_interval = 4
        while time.time() - start_time < timeout:
            if not self.token: return None
            params = {"api": "getMessage", "token": self.token, "sid": PROJECT_ID, "phone": self.phone_number}
            url = f"{self.server}/sms/?{urlencode(params)}"
            try:
                response = requests.get(url, headers=headers, timeout=15, verify=True)
                data = response.json(); code = data.get("code"); msg = data.get("msg", "")
                if code == 0 or str(code) == "0":
                    verification_code = data.get("yzm") or msg
                    if verification_code and verification_code != "ok":
                        if len(verification_code) > 1 and verification_code.isalnum(): self.log_message(f"成功获取验证码: {verification_code}"); return verification_code
                elif "尚未接收到短信" in msg or (code == -1 and msg == "等待"): pass
                else:
                    if self.handle_api_error(data, "获取验证码"): url = f"{self.server}/sms/?{urlencode(params)}"; continue
                    else: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("666错误", "获取验证码失败"+ADMIN_CONTACT_MSG)); return None # 你修改了弹窗标题
            except requests.exceptions.RequestException: pass
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return None
            time.sleep(polling_interval)
        return None # Timeout
    def blacklist_phone(self):
        if not self.token or not self.server or not self.phone_number: return False
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0": self.log_message(f"号码 {self.phone_number} 已拉黑。"); self.root.after(0, self.clear_phone_details); return True
            else:
                if self.handle_api_error(data, "拉黑手机号"): return self.blacklist_phone()
                self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("操作失败", "拉黑号码失败"+ADMIN_CONTACT_MSG)); return False
        except requests.exceptions.RequestException: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("网络错误", "拉黑操作网络异常"+ADMIN_CONTACT_MSG)); return False
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.root.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return False

    # --- GUI 辅助方法 ---
    def copy_phone(self):
        if self.phone_number:
            try: self.root.clipboard_clear(); self.root.clipboard_append(self.phone_number); self.log_message(f"号码 {self.phone_number} 已复制。"); self.set_status("号码已复制。")
            except tk.TclError: pass
            except Exception: self.log_message("复制号码失败。")
        else: self.log_message("没有号码可复制。")
    def copy_code(self):
        code = self.code_var.get()
        if code and code not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]:
            try: self.root.clipboard_clear(); self.root.clipboard_append(code); self.log_message(f"验证码 {code} 已复制。"); self.set_status("验证码已复制。")
            except tk.TclError: pass
            except Exception: self.log_message("复制验证码失败。")
        else: self.log_message("没有有效的验证码可复制。")
    def clear_phone_details(self):
        self.phone_number = None
        try: self.phone_var.set("已拉黑"); self.code_var.set("尚未获取"); self.update_ui_state(self.is_working)
        except tk.TclError: pass
    def _play_sound_if_enabled(self, sound_alias):
        if self.sound_enabled_var.get():
            try: winsound.PlaySound(sound_alias, winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception: pass
    def _on_app_closing(self):
        self._delete_usage_cache()
        self.root.destroy()


# --- 登录窗口类 ---
class LoginWindow(Toplevel):
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.parent = parent; self.app = app_instance
        self.title("用户登录"); self.geometry("300x170"); self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_closing); self.grab_set(); self.transient(parent)
        ttk.Label(self, text="用户名:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        self.username_entry = ttk.Entry(self, width=25); self.username_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Label(self, text="密  码:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        self.password_entry = ttk.Entry(self, show="*", width=25); self.password_entry.grid(row=1, column=1, padx=10, pady=10)
        button_frame = ttk.Frame(self); button_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(button_frame, text="登录", command=self._login).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="退出", command=self._on_closing).pack(side=tk.LEFT, padx=10)
        self.username_entry.focus_set(); self.lift(); self.focus_force()

    def _login(self):
        username = self.username_entry.get().strip(); password = self.password_entry.get()
        if not username or not password: messagebox.showwarning("输入错误", "用户名和密码不能为空。", parent=self); return
        conn = self.app._get_db_connection(); cursor = None
        if not conn: return
        try:
            cursor = conn.cursor(dictionary=True)
            sql = "SELECT id, username, password_hash, remaining_uses FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user_row = cursor.fetchone()
            if user_row and check_password_hash(user_row["password_hash"], password):
                self.destroy()
                self.app.on_login_success(user_row["id"], user_row["username"], user_row["remaining_uses"])
            else: messagebox.showerror("登录失败", "用户名或密码错误。", parent=self)
        except MySQLError: messagebox.showerror("数据库错误", GENERIC_ERROR_MSG, parent=self)
        except Exception: messagebox.showerror("严重错误", GENERIC_ERROR_MSG, parent=self)
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    def _on_closing(self):
        self.destroy(); self.parent.destroy()

# --- 程序主入口 ---
if __name__ == "__main__":
    if not test_database_connection(): sys.exit(1)
    root = tk.Tk()
    app = SmsApp(root)
    root.mainloop()
