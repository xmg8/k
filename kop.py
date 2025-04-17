import requests
import time
from urllib.parse import urlencode
import os
import customtkinter
from tkinter import messagebox, StringVar, BooleanVar, W, E, LEFT, DISABLED, NORMAL, END, BOTH, X, Y, SUNKEN, WORD, NSEW, EW, RIGHT
import threading
import sys
import ssl
import mysql.connector
from mysql.connector import Error as MySQLError
from werkzeug.security import generate_password_hash, check_password_hash
import winsound
import base64
import keyring
import keyring.errors
import pyperclip # 用于复制到剪贴板，需要安装: pip install pyperclip

# --- MySQL Database Configuration ---
MYSQL_HOST = "152.136.171.223"  # 替换为你的 MySQL 服务器地址 (e.g., "localhost", "192.168.1.100")
MYSQL_USER = "wxxmg888" # 替换为你的 MySQL 用户名
MYSQL_PASSWORD = "xmg888.top" # 替换为你的 MySQL 密码
MYSQL_DATABASE = "wxxmg888" # 替换为你的数据库名称

# --- 好猪码 API 配置 ---
API_ACCOUNT = "011474da7ce8c4d4fe58ad3eb95595fba150872eaf35cc85d692b2b209ac61c3"
API_PASSWORD = "2128c8ba18eba394cbfb99c6c906a9b5199d9f94cd825fbcd30c41a0745281e3"
PROJECT_ID = "78478"
SERVERS = [
    "https://api.haozhuma.com", "https://api.haozhuma.cn",
    "https://api.haozhuyun.com", "https://api.haozhuyun.cn"
]
TOKEN_EXPIRED_ERROR_CODE = "E0008"

# --- 路径处理 ---
if getattr(sys, 'frozen', False): application_path = os.path.dirname(sys.executable)
else: application_path = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(application_path, "usage_cache.dat")

# --- API 请求头 ---
headers = {'User-Agent': 'Mozilla/5.0 ...'}

# --- 常量 ---
GENERIC_ERROR_MSG = "发生错误，请联系管理员。"
ADMIN_CONTACT_MSG = "，请联系管理员。"
DB_RETRY_COUNT = 10; DB_RETRY_DELAY = 2
ADMIN_CONTACT_NUMBER = "954158026" # 单独定义号码
ADMIN_CONTACT_INFO_LINE1 = "如需账号或充值，请联系管理员"
ADMIN_CONTACT_INFO_LINE2 = f"QQ/微信: {ADMIN_CONTACT_NUMBER}"
ANNOUNCEMENT_TEXT = """
【使用说明】
1. 登录后，点击“获取手机号”按钮。
2. 程序会自动获取一个临时手机号码显示在上方。
3. 将此号码用于你需要接收验证码的服务。
4. 程序将在获取号码10秒后自动开始接收验证码。
5. 成功接收到验证码后会显示在上方，并自动扣减一次使用次数。
6. 如果长时间未收到验证码（约3分半钟），程序会自动将该号码拉黑并重新获取新号码。
7. 你也可以手动点击“拉黑号码”放弃当前号码。
8. 复制按钮可方便复制号码和验证码。
9. 声音提示可在左下角勾选开启或关闭。

【注意事项】
- 请勿将获取的号码用于非法用途。
- 如遇任何问题或次数用尽，请联系管理员。
"""
KEYRING_SERVICE_NAME = "WujinDongriJieMaTool"
SUCCESS_SOUND_ALIAS = "SystemQuestion" # 尝试 Question 声音
# --- 或者使用自定义 WAV 文件 ---
# SOUNDS_DIR = os.path.join(application_path, "sounds")
# SUCCESS_SOUND_FILE = os.path.join(SOUNDS_DIR, "success.wav")

# --- 数据库连接测试 ---
def test_database_connection():
    for attempt in range(DB_RETRY_COUNT):
        try:
            conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE, connect_timeout=5)
            if conn.is_connected(): conn.close(); return True
        except MySQLError:
            if attempt < DB_RETRY_COUNT - 1: time.sleep(DB_RETRY_DELAY)
            else: messagebox.showerror("数据库连接失败", GENERIC_ERROR_MSG + f"\n(尝试 {DB_RETRY_COUNT} 次后失败)"); return False
        except Exception:
             if attempt == DB_RETRY_COUNT - 1: messagebox.showerror("连接错误", GENERIC_ERROR_MSG)
             return False
    return False

# --- GUI 应用主类 ---
class SmsApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("无尽冬日接码工具 - 未登录")
        self.geometry("700x700") # 再次增加高度以适应可滚动公告
        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")

        self.token = None; self.phone_number = None; self.server = None
        self.is_working = False; self.auto_fetch_job = None
        self.logged_in_user_id = None; self.logged_in_username = None; self.remaining_uses = 0

        self._create_main_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_app_closing)
        self.withdraw()

        if not self.attempt_auto_login():
            self.after(100, self.show_login_window)

    def _create_main_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        # --- 调整行权重 ---
        self.grid_rowconfigure(1, weight=1) # 公告区域可扩展
        self.grid_rowconfigure(2, weight=1) # 日志区域可扩展
        # --- 结束调整 ---

        control_frame = customtkinter.CTkFrame(self, corner_radius=10)
        control_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky=NSEW)
        control_frame.grid_columnconfigure(1, weight=1); control_frame.grid_columnconfigure(3, weight=0)

        # ... (剩余次数、当前用户、手机号、验证码标签和输入框保持不变) ...
        customtkinter.CTkLabel(control_frame, text="剩余次数:", anchor="w").grid(row=0, column=0, padx=10, pady=5, sticky=W)
        self.uses_var = StringVar(value="--"); self.uses_label = customtkinter.CTkLabel(control_frame, textvariable=self.uses_var, width=100, anchor="w")
        self.uses_label.grid(row=0, column=1, padx=5, pady=5, sticky=W)
        customtkinter.CTkLabel(control_frame, text="当前用户:", anchor="e").grid(row=0, column=2, padx=10, pady=5, sticky=E)
        self.username_var = StringVar(value="未登录"); self.username_label = customtkinter.CTkLabel(control_frame, textvariable=self.username_var, anchor="e")
        self.username_label.grid(row=0, column=3, padx=5, pady=5, sticky=E)
        customtkinter.CTkLabel(control_frame, text="手机号码:", anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky=W)
        self.phone_var = StringVar(value="尚未获取"); self.phone_entry = customtkinter.CTkEntry(control_frame, textvariable=self.phone_var, state='disabled', width=150)
        self.phone_entry.grid(row=1, column=1, padx=5, pady=5, sticky=EW)
        customtkinter.CTkLabel(control_frame, text="验证码:", anchor="w").grid(row=2, column=0, padx=10, pady=5, sticky=W)
        self.code_var = StringVar(value="尚未获取"); self.code_entry = customtkinter.CTkEntry(control_frame, textvariable=self.code_var, state='disabled', width=150)
        self.code_entry.grid(row=2, column=1, padx=5, pady=5, sticky=EW)
        button_width = 130
        self.get_phone_btn = customtkinter.CTkButton(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=button_width, state=DISABLED)
        self.get_phone_btn.grid(row=1, column=2, padx=(20, 5), pady=5)
        self.copy_phone_btn = customtkinter.CTkButton(control_frame, text="复制号码", command=self.copy_phone, width=button_width, state=DISABLED)
        self.copy_phone_btn.grid(row=1, column=3, padx=5, pady=5)
        self.copy_code_btn = customtkinter.CTkButton(control_frame, text="复制验证码", command=self.copy_code, width=button_width, state=DISABLED)
        self.copy_code_btn.grid(row=2, column=3, padx=5, pady=5)
        self.blacklist_btn = customtkinter.CTkButton(control_frame, text="拉黑号码", command=self.start_blacklist_thread, width=button_width, state=DISABLED, fg_color="firebrick", hover_color="darkred")
        self.blacklist_btn.grid(row=3, column=3, padx=5, pady=10)
        self.sound_enabled_var = BooleanVar(value=True)
        sound_check = customtkinter.CTkCheckBox(control_frame, text="声音提示", variable=self.sound_enabled_var)
        sound_check.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky=W)

        # --- 公告区域 (使用 ScrollableFrame) ---
        announcement_outer_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        announcement_outer_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky=NSEW)
        announcement_outer_frame.grid_rowconfigure(1, weight=1); announcement_outer_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(announcement_outer_frame, text="公告与说明:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=0, pady=(0,5), sticky="w")
        # 创建可滚动框架
        scrollable_frame = customtkinter.CTkScrollableFrame(announcement_outer_frame, corner_radius=8)
        scrollable_frame.grid(row=1, column=0, sticky=NSEW)
        scrollable_frame.grid_columnconfigure(0, weight=1) # 让内部标签可以横向填充

        # 在可滚动框架内创建标签显示公告
        announcement_label = customtkinter.CTkLabel(scrollable_frame, text=ANNOUNCEMENT_TEXT.strip(), justify=LEFT, anchor="nw") # justify=LEFT 左对齐
        announcement_label.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        # --- 结束公告区域 ---

        # --- 日志输出区域 ---
        log_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        log_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky=NSEW)
        log_frame.grid_rowconfigure(1, weight=1); log_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(log_frame, text="运行日志:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=0, pady=(0,5), sticky="w")
        self.log_text = customtkinter.CTkTextbox(log_frame, wrap=WORD, state=DISABLED, corner_radius=8)
        self.log_text.grid(row=1, column=0, sticky=NSEW)
        # --- 结束日志区域 ---

        self.status_var = StringVar(value="请先登录.")
        status_bar = customtkinter.CTkLabel(self, textvariable=self.status_var, height=25, anchor="w", padx=10)
        status_bar.grid(row=3, column=0, sticky=EW)

    def show_login_window(self):
        if hasattr(self, 'login_window_instance') and self.login_window_instance and self.login_window_instance.winfo_exists():
            self.login_window_instance.focus_force()
        else:
            self.login_window_instance = LoginWindow(self, self)

    def on_login_success(self, user_id, username, remaining_uses, remember=False, password=None, auto_login=False):
        self.logged_in_user_id = user_id; self.logged_in_username = username;
        cached_uses = self._read_usage_cache()
        if cached_uses is not None and cached_uses <= remaining_uses: self.remaining_uses = cached_uses
        else: self.remaining_uses = remaining_uses; self._write_usage_cache(remaining_uses)

        # --- 修复：确保自动登录状态也被正确保存 ---
        if remember:
            try:
                keyring.set_password(KEYRING_SERVICE_NAME, username, password if password else "")
                keyring.set_password(KEYRING_SERVICE_NAME, "last_user", username)
                # 无论是否是自动登录触发的，只要勾选了“记住密码”，就根据 auto_login 参数保存状态
                keyring.set_password(KEYRING_SERVICE_NAME, "auto_login", "true" if auto_login else "false")
            except keyring.errors.KeyringError: pass
        else:
            try:
                last_user = keyring.get_password(KEYRING_SERVICE_NAME, "last_user")
                if last_user == username:
                    keyring.delete_password(KEYRING_SERVICE_NAME, username)
                    keyring.delete_password(KEYRING_SERVICE_NAME, "last_user")
                    keyring.delete_password(KEYRING_SERVICE_NAME, "auto_login")
            except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError): pass
        # --- 结束修复 ---

        self.deiconify(); self.title(f"无尽冬日接码工具 - 用户: {username}")
        self.username_var.set(username); self.uses_var.set(str(self.remaining_uses))
        self.status_var.set("登录成功，正在初始化 API...")
        self.log_message("登录成功。")
        self.start_initial_login_thread()
        self.update_ui_state(False)
        self.lift(); self.focus_force()

    def attempt_auto_login(self):
        try:
            auto_login_flag = keyring.get_password(KEYRING_SERVICE_NAME, "auto_login")
            if auto_login_flag != "true": return False
            username = keyring.get_password(KEYRING_SERVICE_NAME, "last_user")
            password = keyring.get_password(KEYRING_SERVICE_NAME, username)
            if not username or password is None: return False

            conn = self._get_db_connection(); cursor = None
            if not conn: return False
            try:
                cursor = conn.cursor(dictionary=True)
                sql = "SELECT id, username, password_hash, remaining_uses FROM users WHERE username = %s"
                cursor.execute(sql, (username,))
                user_row = cursor.fetchone()
                if user_row and check_password_hash(user_row["password_hash"], password):
                    # --- 修复：传递正确的 password 和 auto_login 状态 ---
                    self.after(50, lambda: self.on_login_success(user_row["id"], user_row["username"], user_row["remaining_uses"], remember=True, password=password, auto_login=True))
                    # --- 结束修复 ---
                    return True
                else: # 凭证无效
                    try:
                        keyring.delete_password(KEYRING_SERVICE_NAME, username)
                        keyring.delete_password(KEYRING_SERVICE_NAME, "last_user")
                        keyring.delete_password(KEYRING_SERVICE_NAME, "auto_login")
                    except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError): pass
                    return False
            except MySQLError: return False
            except Exception: return False
            finally:
                if cursor: cursor.close()
                if conn and conn.is_connected(): conn.close()
        except keyring.errors.KeyringError: return False
        except Exception: return False

    # ... (SmsApp 的其他方法保持不变, 包括日志、状态、UI更新、后台任务、数据库、缓存、API、GUI辅助方法) ...
    # --- 日志、状态、UI 更新 ---
    def log_message(self, message, level="INFO"):
        if level == "INFO" and self: self.after(0, self._append_log, message)
    def _append_log(self, message):
        try:
            self.log_text.configure(state=NORMAL)
            self.log_text.insert(END, f"{time.strftime('%H:%M:%S')} - {message}\n")
            self.log_text.see(END)
            self.log_text.configure(state=DISABLED)
        except tk.TclError: pass
        except AttributeError: pass
    def set_status(self, message):
        if self:
             try: self.after(0, self.status_var.set, message)
             except tk.TclError: pass
             except AttributeError: pass
    def update_ui_state(self, working):
        self.is_working = working; is_logged_in = bool(self.logged_in_user_id)
        can_get_phone = is_logged_in and not working and self.remaining_uses > 0
        get_phone_state = NORMAL if can_get_phone else DISABLED
        phone_available = bool(self.phone_number)
        code_val = self.code_var.get()
        code_available = code_val and code_val not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]
        try:
            self.get_phone_btn.configure(state=get_phone_state)
            blacklist_state = DISABLED if not is_logged_in or working or not phone_available else NORMAL
            copy_phone_state = DISABLED if not phone_available else NORMAL
            copy_code_state = DISABLED if not is_logged_in or working or not code_available else NORMAL
            self.blacklist_btn.configure(state=blacklist_state); self.copy_phone_btn.configure(state=copy_phone_state); self.copy_code_btn.configure(state=copy_code_state)
            self.phone_entry.configure(state=NORMAL if phone_available else DISABLED)
            self.code_entry.configure(state=NORMAL if code_available else DISABLED)
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
        except AttributeError: pass

    # --- 启动后台任务的方法 ---
    def start_initial_login_thread(self):
        self.set_status("正在初始化 API 连接...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True); thread.start()
    def start_get_phone_thread(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working: return
        if self.remaining_uses <= 0: messagebox.showwarning("次数不足", "您的剩余使用号码数量不足，请联系管理员充值。"); self.log_message("可用号码数量不足，请联系管理员充值。"); return
        if not self.token or not self.server: messagebox.showerror("错误", "连接未就绪"+ADMIN_CONTACT_MSG); return
        if self.auto_fetch_job:
            try: self.after_cancel(self.auto_fetch_job)
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
            try: self.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None; self.log_message("已取消等待获取验证码。"); self.set_status("就绪.")
        if messagebox.askyesno("确认", f"确定要拉黑号码 {self.phone_number} 吗？"):
            self.update_ui_state(True); self.log_message(f"尝试拉黑号码: {self.phone_number}")
            thread = threading.Thread(target=self._blacklist_task, daemon=True); thread.start()
        else: self.log_message("拉黑操作已取消。")

    # --- 后台任务方法 ---
    def _initial_login_task(self):
        try:
            self.try_login()
            self.after(0, self.update_ui_state, False)
        except Exception:
            self.log_message(GENERIC_ERROR_MSG, level="ERROR")
            self.after(0, lambda: messagebox.showerror("API 错误", "无法初始化接码服务"+ADMIN_CONTACT_MSG))
            self.set_status("API 连接失败"+ADMIN_CONTACT_MSG)
    def _get_phone_task(self):
        phone_obtained = False
        try:
            phone = self.get_phone_number()
            if phone:
                phone_obtained = True
                self.after(0, lambda p=phone: self.phone_var.set(p))
                self.after(0, self.update_ui_state, False)
                self._play_sound_if_enabled(SUCCESS_SOUND_ALIAS) # 使用统一的声音
                self.log_message("号码获取成功，10 秒后开始接收验证码...")
                self.set_status("等待获取验证码 (10s)...")
                try: self.auto_fetch_job = self.after(10000, self.start_automatic_code_fetch)
                except tk.TclError: phone_obtained = False
            else: self.after(0, lambda: self.phone_var.set("获取失败"))
        except Exception: self.after(0, lambda: self.phone_var.set("获取异常")); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
            if not phone_obtained: self.after(0, self.update_ui_state, False)
    def _get_code_task_automatic(self):
        code = None; restart_needed = False
        try:
            code = self.wait_for_verification_code(timeout=200)
            if code:
                self.after(0, lambda c=code: self.code_var.set(c))
                self._play_sound_if_enabled(SUCCESS_SOUND_ALIAS) # 使用统一的声音
                if not self._decrement_usage():
                     messagebox.showerror("错误", "扣减次数失败"+ADMIN_CONTACT_MSG)
                     self.after(0, self.update_ui_state, False); return
                self.after(0, self.update_ui_state, False)
            else: # Timeout
                self.log_message("验证码获取超时。")
                self.after(0, lambda: self.code_var.set("获取超时"))
                if self.phone_number:
                    self.log_message(f"自动拉黑号码: {self.phone_number}")
                    blacklist_success = self.blacklist_phone()
                    if blacklist_success: restart_needed = True; self.after(0, self.restart_process_after_timeout)
                    else: pass
                else: pass
        except Exception: self.after(0, lambda: self.code_var.set("获取异常")); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
            if not restart_needed: self.after(0, self.update_ui_state, False)
    def _blacklist_task(self):
        try: self.blacklist_phone()
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally: self.after(0, self.update_ui_state, False)
    def restart_process_after_timeout(self):
        try:
            self.log_message("验证码超时，自动重新获取手机号...")
            self.phone_var.set("重新获取..."); self.code_var.set("尚未获取")
            self.is_working = False; self.update_ui_state(False)
            self.after(50, self.start_get_phone_thread)
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
            self.log_message(f"可用号码数量已扣减，剩余: {self.remaining_uses}")
            self.after(0, lambda: self.uses_var.set(str(self.remaining_uses)))
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
        except OSError: pass

    # --- API 交互方法 ---
    def try_login(self):
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                response = requests.get(login_url, headers=headers, timeout=15, verify=True)
                response.raise_for_status(); data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0": self.server = s; self.token = data["token"]; return
            except requests.exceptions.RequestException: pass
            except Exception: pass
        self.server = None; self.token = None; raise Exception("API 登录失败")
    def handle_api_error(self, data, operation_name):
        error_code = data.get("code"); error_msg = data.get('msg', '未知错误')
        is_waiting_msg = "尚未接收" in error_msg or "等待" == error_msg or "没有可用" in error_msg
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE: self.log_message("API 令牌过期，尝试重连..."); self.token = None
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg: pass
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            try: self.try_login(); return True
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("API 错误", "API 令牌过期且无法自动重新登录"+ADMIN_CONTACT_MSG)); return False
        if error_code != 0 and str(error_code) != "0" and not is_waiting_msg and str(error_code) != TOKEN_EXPIRED_ERROR_CODE: return False
        return True
    def get_phone_number(self):
        if not self.token or not self.server: self.log_message("API 未初始化"+ADMIN_CONTACT_MSG, level="ERROR"); return None
        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
        retry_delay = 3; self.log_message("正在获取手机号...")
        while True:
            if not self.token: self.log_message("API 令牌失效"+ADMIN_CONTACT_MSG, level="ERROR"); return None
            try:
                response = requests.get(url, headers=headers, timeout=20, verify=True)
                data = response.json(); code = data.get("code"); msg = data.get("msg", "")
                if code == 0 or str(code) == "0":
                    phone = data.get("phone")
                    if phone: self.phone_number = phone; self.after(0, lambda: self.code_var.set("尚未获取")); self.log_message(f"成功获取手机号: {self.phone_number}"); return self.phone_number
                    else: time.sleep(retry_delay); continue
                elif str(code) == "-1" and ("没有可用手机号" in msg or "请稍后再试" in msg or "等待" == msg): time.sleep(retry_delay); continue
                else:
                    if self.handle_api_error(data, "获取手机号"): url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"; continue
                    else: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("API 错误", "获取手机号失败"+ADMIN_CONTACT_MSG)); self.phone_number = None; return None
            except requests.exceptions.RequestException: time.sleep(5); continue
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); self.phone_number = None; return None
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
                    else: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("API 错误", "获取验证码失败"+ADMIN_CONTACT_MSG)); return None
            except requests.exceptions.RequestException: pass
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return None
            time.sleep(polling_interval)
        return None # Timeout
    def blacklist_phone(self):
        if not self.token or not self.server or not self.phone_number: return False
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0": self.log_message(f"号码 {self.phone_number} 已拉黑。"); self.after(0, self.clear_phone_details); return True
            else:
                if self.handle_api_error(data, "拉黑手机号"): return self.blacklist_phone()
                self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("操作失败", "拉黑号码失败"+ADMIN_CONTACT_MSG)); return False
        except requests.exceptions.RequestException: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("网络错误", "拉黑操作网络异常"+ADMIN_CONTACT_MSG)); return False
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return False

    # --- GUI 辅助方法 ---
    def copy_phone(self):
        if self.phone_number:
            try: self.clipboard_clear(); self.clipboard_append(self.phone_number); self.log_message(f"号码 {self.phone_number} 已复制。"); self.set_status("号码已复制。")
            except tk.TclError: pass
            except Exception: self.log_message("复制号码失败。")
        else: self.log_message("没有号码可复制。")
    def copy_code(self):
        code = self.code_var.get()
        if code and code not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]:
            try: self.clipboard_clear(); self.clipboard_append(code); self.log_message(f"验证码 {code} 已复制。"); self.set_status("验证码已复制。")
            except tk.TclError: pass
            except Exception: self.log_message("复制验证码失败。")
        else: self.log_message("没有有效的验证码可复制。")
    def clear_phone_details(self):
        self.phone_number = None
        try: self.phone_var.set("已拉黑"); self.code_var.set("尚未获取"); self.update_ui_state(self.is_working)
        except tk.TclError: pass
    def _play_sound_if_enabled(self, sound_source, is_file=False):
        if self.sound_enabled_var.get():
            try:
                flags = winsound.SND_ASYNC
                if is_file:
                    if os.path.exists(sound_source): flags |= winsound.SND_FILENAME
                    else: sound_source = "SystemDefault"; flags |= winsound.SND_ALIAS
                else: flags |= winsound.SND_ALIAS
                winsound.PlaySound(sound_source, flags)
            except Exception: pass
    def _on_app_closing(self):
        self._delete_usage_cache()
        self.destroy()


# --- 登录窗口类 ---
class LoginWindow(customtkinter.CTkToplevel):
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.parent = parent; self.app = app_instance
        self.title("用户登录"); self.geometry("380x320"); self.resizable(False, False) # 调整大小
        self.protocol("WM_DELETE_WINDOW", self._on_closing); self.grab_set(); self.transient(parent)
        self.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(self, text="用户名:").grid(row=0, column=0, padx=(20, 5), pady=10, sticky="w")
        self.username_entry = customtkinter.CTkEntry(self, width=200); self.username_entry.grid(row=0, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew") # columnspan=2
        customtkinter.CTkLabel(self, text="密  码:").grid(row=1, column=0, padx=(20, 5), pady=10, sticky="w")
        self.password_entry = customtkinter.CTkEntry(self, show="*", width=200); self.password_entry.grid(row=1, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew") # columnspan=2

        option_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        option_frame.grid(row=2, column=0, columnspan=3, padx=20, pady=5, sticky="w") # columnspan=3
        self.remember_var = BooleanVar()
        self.remember_check = customtkinter.CTkCheckBox(option_frame, text="记住密码", variable=self.remember_var, command=self._on_remember_change)
        self.remember_check.pack(side=LEFT, padx=(0, 10))
        self.autologin_var = BooleanVar()
        self.autologin_check = customtkinter.CTkCheckBox(option_frame, text="自动登录", variable=self.autologin_var, state=DISABLED)
        self.autologin_check.pack(side=LEFT)

        button_frame = customtkinter.CTkFrame(self, fg_color="transparent"); button_frame.grid(row=3, column=0, columnspan=3, pady=15) # columnspan=3
        # --- 修改按钮顺序和位置 ---
        customtkinter.CTkButton(button_frame, text="退出", command=self._on_closing, width=80, fg_color="gray", hover_color="dimgray").pack(side=RIGHT, padx=10)
        customtkinter.CTkButton(button_frame, text="登录", command=self._login, width=80).pack(side=RIGHT, padx=10)
        # --- 结束修改 ---

        # --- 管理员联系方式 (分行并添加复制按钮) ---
        contact_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        contact_frame.grid(row=4, column=0, columnspan=3, padx=20, pady=(10, 10), sticky="ew") # columnspan=3
        contact_frame.grid_columnconfigure(0, weight=1) # 让标签可以扩展

        contact_label1 = customtkinter.CTkLabel(contact_frame, text=ADMIN_CONTACT_INFO_LINE1, font=customtkinter.CTkFont(size=12, weight="bold"))
        contact_label1.grid(row=0, column=0, sticky="w")
        contact_label2 = customtkinter.CTkLabel(contact_frame, text=ADMIN_CONTACT_INFO_LINE2, font=customtkinter.CTkFont(size=12, weight="bold"))
        contact_label2.grid(row=1, column=0, sticky="w")

        copy_contact_btn = customtkinter.CTkButton(contact_frame, text="复制联系方式", width=100, height=24, font=customtkinter.CTkFont(size=10), command=self._copy_contact)
        copy_contact_btn.grid(row=0, column=1, rowspan=2, padx=(10, 0), sticky="e")
        # --- 结束添加 ---

        self._load_credentials()
        self.username_entry.focus_set(); self.lift(); self.focus_force()
        self._center_window()

    def _center_window(self):
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
            ww = self.winfo_width(); wh = self.winfo_height()
            x = (sw // 2) - (ww // 2); y = (sh // 2) - (wh // 2)
            self.geometry(f"+{x}+{y}")
        except: pass
    def _on_remember_change(self):
        if self.remember_var.get(): self.autologin_check.configure(state=NORMAL)
        else: self.autologin_check.configure(state=DISABLED); self.autologin_var.set(False)
    def _load_credentials(self):
        try:
            last_user = keyring.get_password(KEYRING_SERVICE_NAME, "last_user")
            if last_user:
                password = keyring.get_password(KEYRING_SERVICE_NAME, last_user)
                if password is not None:
                    self.username_entry.insert(0, last_user); self.password_entry.insert(0, password)
                    self.remember_var.set(True); self._on_remember_change()
                    auto_login_flag = keyring.get_password(KEYRING_SERVICE_NAME, "auto_login")
                    if auto_login_flag == "true": self.autologin_var.set(True)
        except keyring.errors.KeyringError: pass
        except Exception: pass
    def _login(self):
        username = self.username_entry.get().strip(); password = self.password_entry.get()
        remember = self.remember_var.get(); auto_login = self.autologin_var.get()
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
                self.app.on_login_success(user_row["id"], user_row["username"], user_row["remaining_uses"], remember, password, auto_login)
            else: messagebox.showerror("登录失败", "用户名或密码错误。", parent=self)
        except MySQLError: messagebox.showerror("数据库错误", GENERIC_ERROR_MSG, parent=self)
        except Exception: messagebox.showerror("严重错误", GENERIC_ERROR_MSG, parent=self)
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    def _copy_contact(self):
        """复制管理员联系号码到剪贴板"""
        try:
            pyperclip.copy(ADMIN_CONTACT_NUMBER)
            messagebox.showinfo("已复制", f"管理员联系方式 {ADMIN_CONTACT_NUMBER} 已复制到剪贴板。", parent=self)
        except Exception as e:
            messagebox.showwarning("复制失败", f"无法复制到剪贴板: {e}", parent=self)

    def _on_closing(self):
        self.destroy(); self.parent.destroy()

# --- 程序主入口 ---
if __name__ == "__main__":
    # 检查 pyperclip 是否安装
    try:
        import pyperclip
    except ImportError:
        messagebox.showerror("缺少库", "运行本程序需要安装 pyperclip 库。\n请运行: pip install pyperclip")
        sys.exit(1)

    if not test_database_connection(): sys.exit(1)
    app = SmsApp()
    app.mainloop()
