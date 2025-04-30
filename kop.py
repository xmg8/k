# ... (导入和配置保持不变) ...
import requests
import time
from urllib.parse import urlencode, quote
import os
import customtkinter
from customtkinter import CTkScrollableFrame
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
import pyperclip

# --- MySQL Database Configuration ---
MYSQL_HOST = "152.136.171.223"  # 替换为你的 MySQL 服务器地址 (e.g., "localhost", "192.168.1.100")
MYSQL_USER = "wxxmg888" # 替换为你的 MySQL 用户名
MYSQL_PASSWORD = "xmg888.top" # 替换为你的 MySQL 密码
MYSQL_DATABASE = "wxxmg888" # 替换为你的数据库名称

# --- 好猪码 API 配置 ---
API_ACCOUNT = "011474da7ce8c4d4fe58ad3eb95595fba150872eaf35cc85d692b2b209ac61c3"
API_PASSWORD = "2128c8ba18eba394cbfb99c6c906a9b5199d9f94cd825fbcd30c41a0745281e3"
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
ADMIN_CONTACT_NUMBER = "954158026"
ADMIN_CONTACT_INFO_LINE1 = "如需账号或充值，请联系管理员"
ADMIN_CONTACT_INFO_LINE2 = f"QQ/微信: {ADMIN_CONTACT_NUMBER}"
ANNOUNCEMENT_TEXT = """
                           【注意事项】
-重要提示！！！【号码不保证全新，成功收到验证码即刻扣费，如不能接受请停止使用！！！】
【可先少量测试，确定可以满足要求后再使用】
- 严禁将获取的号码用于非法用途！
- 如遇问题或次数用尽，请联系管理员。
=====================================================================================
                           【使用说明】
1. 点击“获取手机号”按钮，程序会自动获取临时号码并显示，【点击复制号码可自动复制】。
2. 将此号码用于需要接收验证码的项目，账号对应项目请查看软件顶部显示。
3. 成功接收到验证码就会扣费，无论是否可用！【点击复制验证码可自动复制】。
4. 长时间未收到验证码，会自动拉黑并获取新号。
5. 成功使用验证码后，点击“获取手机号”按钮，开始再次使用。
"""
KEYRING_SERVICE_NAME = "WujinDongriJieMaTool"
SUCCESS_SOUND_ALIAS = "SystemQuestion"

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

# --- 单个号码条目控件 (保持不变) ---
class PhoneEntryWidget(customtkinter.CTkFrame):
    def __init__(self, master, app_instance, phone_info, row_index, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app_instance; self.phone_info = phone_info; self.row_index = row_index
        if self.row_index % 2 == 0: self.configure(fg_color=("gray90", "gray20"))
        else: self.configure(fg_color=("gray80", "gray15"))
        self.grid_columnconfigure((0, 1, 2), weight=1); self.grid_columnconfigure(3, weight=0)
        self.phone_label = customtkinter.CTkLabel(self, text=phone_info['phone'], width=120, anchor="w", font=customtkinter.CTkFont(size=13))
        self.phone_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.status_var = StringVar(value=phone_info.get('status', '初始化...'))
        self.status_label = customtkinter.CTkLabel(self, textvariable=self.status_var, width=100, anchor="w", font=customtkinter.CTkFont(size=12))
        self.status_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.code_var = StringVar(value=phone_info.get('code', ''))
        self.code_label = customtkinter.CTkLabel(self, textvariable=self.code_var, width=80, anchor="w", font=customtkinter.CTkFont(size=12))
        self.code_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        action_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=0, column=3, padx=5, pady=2, sticky="e")
        button_font = customtkinter.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold")
        button_height = 26; copy_num_width = 80; copy_code_width = 80; release_width = 60; blacklist_width = 60
        self.copy_phone_btn = customtkinter.CTkButton(action_frame, text="复制号码", width=copy_num_width, height=button_height, font=button_font, command=self._copy_phone)
        self.copy_phone_btn.pack(side=LEFT, padx=2)
        self.copy_code_btn = customtkinter.CTkButton(action_frame, text="复制验证码", width=copy_code_width, height=button_height, font=button_font, command=self._copy_code, state=DISABLED)
        self.copy_code_btn.pack(side=LEFT, padx=2)
        self.release_btn = customtkinter.CTkButton(action_frame, text="释放", width=release_width, height=button_height, font=button_font, command=self._release, fg_color="dodgerblue", hover_color="steelblue")
        self.release_btn.pack(side=LEFT, padx=2)
        self.blacklist_btn = customtkinter.CTkButton(action_frame, text="拉黑", width=blacklist_width, height=button_height, font=button_font, command=self._blacklist, fg_color="firebrick", hover_color="darkred")
        self.blacklist_btn.pack(side=LEFT, padx=2)
    def update_status(self, status): self.status_var.set(status); self.phone_info['status'] = status
    def update_code(self, code): self.code_var.set(code); self.phone_info['code'] = code; self.copy_code_btn.configure(state=NORMAL if code else DISABLED)
    def disable_actions(self): self.copy_phone_btn.configure(state=DISABLED); self.copy_code_btn.configure(state=DISABLED); self.release_btn.configure(state=DISABLED); self.blacklist_btn.configure(state=DISABLED)
    def _copy_phone(self): self.app.copy_text(self.phone_info['phone'], "号码")
    def _copy_code(self): code = self.code_var.get(); self.app.copy_text(code, "验证码") if code else self.app.log_message("没有验证码可复制。")
    def _release(self): self.app.start_release_specific_phone(self.phone_info)
    def _blacklist(self): self.app.start_blacklist_specific_phone(self.phone_info)

# --- GUI 应用主类 ---
class SmsApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.default_title = "接码工具" # 基础标题
        self.title(f"{self.default_title} - 未登录")
        self.geometry("850x750") # 调整高度
        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")

        self.token = None; self.server = None
        self.is_working_global = False
        self.logged_in_user_id = None; self.logged_in_username = None; self.remaining_uses = 0
        self.current_project_id = None; self.current_project_name = self.default_title

        self.active_phones = []
        self.phone_widgets = {}
        self.stop_events = {}

        self._create_main_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_app_closing)
        self.withdraw()

        if not self.attempt_auto_login():
            self.after(100, self.show_login_window)

    def _create_main_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        # --- 调整行权重 ---
        self.grid_rowconfigure(2, weight=1) # 公告区域
        self.grid_rowconfigure(3, weight=1) # 号码列表区域
        self.grid_rowconfigure(4, weight=0) # 日志区域固定高度
        # --- 结束调整 ---

        # --- 顶部标题栏 ---
        title_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color=("gray85", "gray20")) # 带点背景色
        title_frame.grid(row=0, column=0, sticky="ew")
        title_frame.grid_columnconfigure(1, weight=1) # 让项目名称扩展

        self.project_name_var = StringVar(value=self.default_title)
        project_label = customtkinter.CTkLabel(title_frame, textvariable=self.project_name_var, font=customtkinter.CTkFont(size=14, weight="bold"))
        project_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        user_info_frame = customtkinter.CTkFrame(title_frame, fg_color="transparent")
        user_info_frame.grid(row=0, column=2, padx=10, pady=5, sticky="e") # 移到第2列
        self.username_var = StringVar(value="未登录");
        customtkinter.CTkLabel(user_info_frame, textvariable=self.username_var, anchor="e").pack(side=LEFT, padx=5)
        self.uses_var = StringVar(value="次数: --");
        customtkinter.CTkLabel(user_info_frame, textvariable=self.uses_var, anchor="e").pack(side=LEFT, padx=5)
        logout_btn = customtkinter.CTkButton(user_info_frame, text="注销", command=self.logout, width=60, height=24, font=customtkinter.CTkFont(size=10), fg_color="transparent", border_width=1, text_color=("gray10", "gray90"))
        logout_btn.pack(side=LEFT, padx=5)
        # --- 结束顶部标题栏 ---

        # --- 控制按钮区域 ---
        action_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        action_frame.grid(row=1, column=0, padx=10, pady=(10,0), sticky="ew")
        # action_frame.grid_columnconfigure(?, weight=1) # 可以让某个元素扩展

        self.sound_enabled_var = BooleanVar(value=True)
        sound_check = customtkinter.CTkCheckBox(action_frame, text="声音提示", variable=self.sound_enabled_var)
        sound_check.pack(side=LEFT, padx=(10, 15), pady=5)

        customtkinter.CTkLabel(action_frame, text="监听指定号码:").pack(side=LEFT, padx=(10, 2), pady=5)
        self.listen_phone_entry = customtkinter.CTkEntry(action_frame, width=120, placeholder_text="输入号码")
        self.listen_phone_entry.pack(side=LEFT, padx=(0, 5), pady=5)
        self.listen_btn = customtkinter.CTkButton(action_frame, text="开始监听", command=self.start_listen_specific_phone, width=100, state=DISABLED)
        self.listen_btn.pack(side=LEFT, padx=(0, 15), pady=5)

        self.get_phone_btn = customtkinter.CTkButton(action_frame, text="获取新号码", command=self.start_get_phone_thread, width=120, state=DISABLED)
        self.get_phone_btn.pack(side=LEFT, padx=5, pady=5)

        self.release_all_btn = customtkinter.CTkButton(action_frame, text="释放全部", command=self.start_release_all_phones_thread, width=100, state=DISABLED, fg_color="orange", hover_color="darkorange")
        self.release_all_btn.pack(side=LEFT, padx=5, pady=5)
        # --- 结束控制按钮区域 ---

        # --- 公告区域 ---
        announcement_outer_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        announcement_outer_frame.grid(row=2, column=0, padx=20, pady=10, sticky=NSEW) # 移到第 2 行
        announcement_outer_frame.grid_rowconfigure(1, weight=1); announcement_outer_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(announcement_outer_frame, text="公告与说明:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=0, pady=(0,5), sticky="w")
        scrollable_frame_ann = customtkinter.CTkScrollableFrame(announcement_outer_frame, corner_radius=8)
        scrollable_frame_ann.grid(row=1, column=0, sticky=NSEW); scrollable_frame_ann.grid_columnconfigure(0, weight=1)
        current_row_ann = 0
        notice_title = customtkinter.CTkLabel(scrollable_frame_ann, text="【注意事项】", font=customtkinter.CTkFont(size=14, weight="bold"), anchor="center")
        notice_title.grid(row=current_row_ann, column=0, pady=(5, 2), sticky="ew"); current_row_ann += 1
        notice_lines = ["- 重要提示！！！【号码不保证全新，成功收到验证码即刻扣费，如不能接受请停止使用！！！】","【可先少量测试，确定可以满足要求后再使用】","- 严禁将获取的号码用于非法用途！","- 如遇问题或次数用尽，请联系管理员。"]
        for line in notice_lines: lbl = customtkinter.CTkLabel(scrollable_frame_ann, text=line.strip(), justify=LEFT, anchor="w"); lbl.grid(row=current_row_ann, column=0, padx=10, pady=(0, 2), sticky="w"); current_row_ann += 1
        separator = customtkinter.CTkFrame(scrollable_frame_ann, height=1, fg_color="gray50"); separator.grid(row=current_row_ann, column=0, padx=10, pady=10, sticky="ew"); current_row_ann += 1
        usage_title = customtkinter.CTkLabel(scrollable_frame_ann, text="【使用说明】", font=customtkinter.CTkFont(size=14, weight="bold"), anchor="center")
        usage_title.grid(row=current_row_ann, column=0, pady=(5, 2), sticky="ew"); current_row_ann += 1
        usage_lines = ["1. 点击“获取手机号”按钮，程序会自动获取临时号码并显示，【点击复制号码可自动复制】。","2. 将此号码用于需要接收验证码的项目，账号对应项目请查看软件顶部显示。","3. 成功接收到验证码就会扣费，无论是否可用！【点击复制验证码可自动复制】。","4. 长时间未收到验证码，会自动拉黑并获取新号。","5. 成功使用验证码后，点击“获取手机号”按钮，开始再次使用。"]
        for line in usage_lines: lbl = customtkinter.CTkLabel(scrollable_frame_ann, text=line.strip(), justify=LEFT, anchor="w"); lbl.grid(row=current_row_ann, column=0, padx=10, pady=(0, 2), sticky="w"); current_row_ann += 1

        # --- 号码列表区域 ---
        list_frame = customtkinter.CTkFrame(self, corner_radius=10)
        list_frame.grid(row=3, column=0, padx=20, pady=10, sticky=NSEW) # 移动到第 3 行
        list_frame.grid_columnconfigure(0, weight=1); list_frame.grid_rowconfigure(1, weight=1)
        customtkinter.CTkLabel(list_frame, text="当前号码:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=(5,0), sticky="w")
        self.phone_list_scrollable_frame = CTkScrollableFrame(list_frame, corner_radius=8)
        self.phone_list_scrollable_frame.grid(row=1, column=0, sticky=NSEW, padx=5, pady=5)
        self.phone_list_scrollable_frame.grid_columnconfigure(0, weight=1)

        # --- 日志区域 ---
        log_outer_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        log_outer_frame.grid(row=4, column=0, padx=20, pady=(0, 10), sticky=NSEW) # 移动到第 4 行
        log_outer_frame.grid_rowconfigure(1, weight=1); log_outer_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(log_outer_frame, text="运行日志:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=0, pady=(0,5), sticky="w")
        self.log_text = customtkinter.CTkTextbox(log_outer_frame, wrap=WORD, state=DISABLED, corner_radius=8, height=100)
        self.log_text.grid(row=1, column=0, sticky=NSEW)

        # --- 状态栏 ---
        self.status_var = StringVar(value="请先登录.")
        status_bar = customtkinter.CTkLabel(self, textvariable=self.status_var, height=25, anchor="w", padx=10)
        status_bar.grid(row=5, column=0, sticky=EW) # 移动到第 5 行

    # ... (add_phone_entry_widget, remove_phone_entry_widget, _update_row_colors, update_phone_entry_status 保持不变) ...
    def add_phone_entry_widget(self, phone_info):
        phone = phone_info['phone']
        if phone in self.phone_widgets: return
        row_index = len(self.phone_widgets)
        widget = PhoneEntryWidget(self.phone_list_scrollable_frame, self, phone_info, row_index, corner_radius=5, border_width=1)
        widget.pack(fill=X, padx=5, pady=(1, 1))
        self.phone_widgets[phone] = widget
        self._update_row_colors()
    def remove_phone_entry_widget(self, phone):
        widget = self.phone_widgets.pop(phone, None)
        if widget:
            widget.destroy()
            self._update_row_colors()
    def _update_row_colors(self):
        visible_widgets = []
        for child in self.phone_list_scrollable_frame.winfo_children():
             if isinstance(child, PhoneEntryWidget): visible_widgets.append(child)
        for i, widget in enumerate(visible_widgets):
             if i % 2 == 0: widget.configure(fg_color=("gray90", "gray20"))
             else: widget.configure(fg_color=("gray80", "gray15"))
    def update_phone_entry_status(self, phone, status, code=None):
        widget = self.phone_widgets.get(phone)
        if widget:
            widget.update_status(status)
            if code is not None: widget.update_code(code)
            if status in ["已拉黑", "获取超时", "获取失败", "拉黑失败", "拉黑异常", "获取异常", "已中断", "已释放", "释放失败"]:
                widget.disable_actions()


    def on_login_success(self, user_id, username, remaining_uses, project_id, project_name, remember=False, password=None, auto_login=False):
        self.logged_in_user_id = user_id; self.logged_in_username = username;
        self.current_project_id = project_id; self.current_project_name = project_name or self.default_title
        cached_uses = self._read_usage_cache()
        if cached_uses is not None and cached_uses <= remaining_uses: self.remaining_uses = cached_uses
        else: self.remaining_uses = remaining_uses; self._write_usage_cache(remaining_uses)
        if remember:
            try:
                keyring.set_password(KEYRING_SERVICE_NAME, username, password if password else "")
                keyring.set_password(KEYRING_SERVICE_NAME, "last_user", username)
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

        self.deiconify()
        # --- 修改：更新顶部标题栏的标签 ---
        self.project_name_var.set(self.current_project_name) # 更新项目名称标签
        self.username_var.set(username)
        self.uses_var.set(f"次数: {self.remaining_uses}")
        # --- 结束修改 ---
        self.status_var.set("登录成功，正在初始化 API...")
        self.log_message("登录成功。")
        self.start_initial_login_thread()
        self.update_ui_state(False)
        self.lift(); self.focus_force()

    # ... (attempt_auto_login 保持不变) ...
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
                sql = "SELECT id, username, password_hash, remaining_uses, project_id, project_name FROM users WHERE username = %s"
                cursor.execute(sql, (username,))
                user_row = cursor.fetchone()
                if user_row and check_password_hash(user_row["password_hash"], password):
                    if user_row["remaining_uses"] <= 0:
                        messagebox.showwarning("自动登录失败", "您的可用次数不足，请联系管理员充值。")
                        try: keyring.delete_password(KEYRING_SERVICE_NAME, "auto_login")
                        except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError): pass
                        return False
                    self.after(50, lambda: self.on_login_success(
                        user_row["id"], user_row["username"], user_row["remaining_uses"],
                        user_row["project_id"], user_row["project_name"],
                        remember=True, password=password, auto_login=True
                    ))
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


    # --- 日志、状态、UI 更新 ---
    # ... (保持不变) ...
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
    def update_ui_state(self, working_global):
        self.is_working_global = working_global
        is_logged_in = bool(self.logged_in_user_id)
        can_get_phone = is_logged_in and not working_global and self.remaining_uses > 0 and self.current_project_id
        get_phone_state = NORMAL if can_get_phone else DISABLED
        listen_state = NORMAL if can_get_phone else DISABLED
        can_release_all = is_logged_in and not working_global and len(self.active_phones) > 0
        release_all_state = NORMAL if can_release_all else DISABLED
        try:
            self.get_phone_btn.configure(state=get_phone_state)
            self.listen_btn.configure(state=listen_state)
            self.release_all_btn.configure(state=release_all_state)
            if not is_logged_in: self.set_status("请先登录.")
            else:
                current_status = self.status_var.get()
                if working_global: self.set_status("正在处理...")
                else:
                     status_msg = f"就绪. 剩余次数: {self.remaining_uses}"
                     if not self.current_project_id: status_msg += " (未配置项目)"
                     elif self.remaining_uses <= 0: status_msg += " (次数不足)"
                     self.set_status(status_msg)
        except tk.TclError: pass
        except AttributeError: pass


    # --- 启动后台任务的方法 ---
    # ... (start_initial_login_thread, start_get_phone_thread, start_listen_specific_phone, start_individual_code_fetch, start_release_specific_phone, start_blacklist_specific_phone, start_release_all_phones_thread 保持不变) ...
    def start_initial_login_thread(self):
        self.set_status("正在初始化 API 连接...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True); thread.start()
    def start_get_phone_thread(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working_global: self.log_message("提示：请等待当前操作完成。"); return
        if self.remaining_uses <= 0: messagebox.showwarning("次数不足", "您的剩余使用号码数量不足，请联系管理员充值。"); self.log_message("可用号码数量不足，请联系管理员充值。"); return
        if not self.current_project_id: messagebox.showerror("错误", "当前用户未配置项目"+ADMIN_CONTACT_MSG); self.log_message("错误：未配置项目，无法获取号码。", level="ERROR"); return
        if not self.token or not self.server: messagebox.showerror("错误", "API 连接未就绪"+ADMIN_CONTACT_MSG); return
        self.update_ui_state(True)
        self.log_message(f"开始获取手机号 (项目ID: {self.current_project_id}, 剩余: {self.remaining_uses})...")
        thread = threading.Thread(target=self._get_phone_task, args=(None,), daemon=True); thread.start()
    def start_listen_specific_phone(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working_global: self.log_message("提示：请等待当前操作完成。"); return
        if self.remaining_uses <= 0: messagebox.showwarning("次数不足", "您的剩余使用号码数量不足，请联系管理员充值。"); self.log_message("可用号码数量不足，请联系管理员充值。"); return
        if not self.current_project_id: messagebox.showerror("错误", "当前用户未配置项目"+ADMIN_CONTACT_MSG); self.log_message("错误：未配置项目，无法监听号码。", level="ERROR"); return
        if not self.token or not self.server: messagebox.showerror("错误", "API 连接未就绪"+ADMIN_CONTACT_MSG); return
        specified_phone = self.listen_phone_entry.get().strip()
        if not specified_phone or not specified_phone.isdigit(): messagebox.showwarning("输入错误", "请输入有效的手机号码（只包含数字）。"); return
        if specified_phone in self.phone_widgets: messagebox.showinfo("提示", f"号码 {specified_phone} 已在监听列表中。"); return
        self.log_message(f"开始监听指定号码: {specified_phone} (项目ID: {self.current_project_id})...")
        phone_info = {'phone': specified_phone, 'status': '开始监听...', 'code': None, 'project_id': self.current_project_id, 'thread': None, 'stop_event': None}
        self.active_phones.append(phone_info)
        self.after(0, self.add_phone_entry_widget, phone_info)
        self.start_individual_code_fetch(phone_info)
        self.listen_phone_entry.delete(0, END)
        # self.after(100, lambda: self.update_ui_state(False)) # 监听不设全局忙碌
    def start_individual_code_fetch(self, phone_info):
        phone = phone_info['phone']
        self.log_message(f"开始为 {phone} (项目ID: {self.current_project_id}) 获取验证码...")
        self.after(0, self.update_phone_entry_status, phone, "等待验证码...")
        phone_info['stop_event'] = threading.Event()
        thread = threading.Thread(target=self._get_individual_code_task, args=(phone_info,), daemon=True)
        phone_info['thread'] = thread
        thread.start()
    def start_release_specific_phone(self, phone_info):
        phone = phone_info['phone']
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if phone_info.get('status') in ['已释放', '已拉黑', '释放失败', '拉黑失败']: return
        stop_event = phone_info.get('stop_event')
        if stop_event: stop_event.set()
        self.log_message(f"尝试释放号码: {phone} (项目ID: {self.current_project_id})")
        self.after(0, self.update_phone_entry_status, phone, "正在释放...")
        thread = threading.Thread(target=self._release_specific_task, args=(phone_info,), daemon=True)
        thread.start()
    def start_blacklist_specific_phone(self, phone_info):
        phone = phone_info['phone']
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if phone_info.get('status') in ['已释放', '已拉黑', '释放失败', '拉黑失败']: return
        stop_event = phone_info.get('stop_event')
        if stop_event: stop_event.set()
        if messagebox.askyesno("确认", f"确定要拉黑号码 {phone} 吗？", parent=self.phone_widgets.get(phone)):
            self.log_message(f"尝试拉黑号码: {phone} (项目ID: {self.current_project_id})")
            self.after(0, self.update_phone_entry_status, phone, "正在拉黑...")
            thread = threading.Thread(target=self._blacklist_specific_task, args=(phone_info,), daemon=True)
            thread.start()
        else:
            if stop_event: stop_event.clear()
            self.log_message(f"取消拉黑号码: {phone}")
    def start_release_all_phones_thread(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working_global: self.log_message("提示：请等待当前操作完成。"); return
        # --- 修改：检查 active_phones 中是否有可释放的号码 ---
        releasable_phones = [p for p in self.active_phones if p.get('status') not in ['已释放', '已拉黑']]
        if not releasable_phones: messagebox.showinfo("提示", "当前没有可释放的号码。"); return
        # --- 结束修改 ---
        if messagebox.askyesno("确认", "确定要释放所有当前获取的号码吗？"):
            self.update_ui_state(True)
            self.log_message("开始释放所有号码...")
            thread = threading.Thread(target=self._release_all_task, daemon=True)
            thread.start()
        else:
            self.log_message("取消释放全部号码。")


    # --- 后台任务方法 (修改 _get_individual_code_task, _release_specific_task, _blacklist_specific_task 的 finally 块) ---
    def _initial_login_task(self):
        try:
            self.try_login()
            self.after(0, self.update_ui_state, False)
        except Exception:
            self.log_message(GENERIC_ERROR_MSG, level="ERROR")
            self.after(0, lambda: messagebox.showerror("API 错误", "无法初始化接码服务"+ADMIN_CONTACT_MSG))
            self.set_status("API 连接失败"+ADMIN_CONTACT_MSG)
    def _get_phone_task(self, specified_phone=None):
        phone_info = None
        try:
            phone = self.get_phone_number(specified_phone=specified_phone)
            if phone:
                if specified_phone and phone != specified_phone:
                    self.log_message(f"警告：指定号码 {specified_phone} 不可用，获取到号码 {phone}。", level="WARN")
                phone_info = {'phone': phone, 'status': '初始化...', 'code': None, 'project_id': self.current_project_id, 'thread': None, 'stop_event': None}
                self.active_phones.append(phone_info)
                self.after(0, self.add_phone_entry_widget, phone_info)
                self._play_sound_if_enabled(SUCCESS_SOUND_ALIAS)
                self.log_message(f"号码 {phone} 获取成功，开始接收验证码...")
                self.start_individual_code_fetch(phone_info)
            else:
                 log_msg = "获取新号码失败。"
                 if specified_phone: log_msg = f"获取指定号码 {specified_phone} 失败。"
                 self.log_message(log_msg)
        except Exception:
            self.log_message(GENERIC_ERROR_MSG, level="ERROR")
            self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
            self.after(0, self.update_ui_state, False)
    def _get_individual_code_task(self, phone_info):
        phone = phone_info['phone']; project_id = phone_info['project_id']; stop_event = phone_info['stop_event']
        code = None; success = False
        try:
            code = self.wait_for_verification_code(phone, project_id, stop_event, timeout=200)
            if code:
                self.after(0, self.update_phone_entry_status, phone, "获取成功", code)
                self._play_sound_if_enabled(SUCCESS_SOUND_ALIAS)
                if not self._decrement_usage(phone, project_id, code):
                     messagebox.showerror("错误", f"号码 {phone} 扣减次数失败"+ADMIN_CONTACT_MSG)
                success = True
            elif stop_event and stop_event.is_set():
                self.after(0, self.update_phone_entry_status, phone, "已中断")
            else: # Timeout
                self.log_message(f"号码 {phone} 验证码获取超时。")
                self.after(0, self.update_phone_entry_status, phone, "获取超时")
        except Exception:
            self.after(0, self.update_phone_entry_status, phone, "获取异常")
            self.log_message(GENERIC_ERROR_MSG, level="ERROR")
        finally:
            # --- 修改：流程结束后移除 UI 和数据 ---
            try: self.active_phones.remove(phone_info)
            except ValueError: pass
            self.after(0, self.remove_phone_entry_widget, phone)
            # --- 结束修改 ---
    def _release_specific_task(self, phone_info):
        phone = phone_info['phone']; project_id = phone_info['project_id']
        try:
            success = self.release_phone(phone, project_id)
            if success:
                # --- 修改：释放成功后移除 UI 和数据 ---
                self.after(0, self.update_phone_entry_status, phone, "已释放") # 短暂显示
                try: self.active_phones.remove(phone_info)
                except ValueError: pass
                self.after(100, self.remove_phone_entry_widget, phone) # 稍后移除
                # --- 结束修改 ---
            else:
                self.after(0, self.update_phone_entry_status, phone, "释放失败")
                stop_event = phone_info.get('stop_event')
                if stop_event: stop_event.clear()
        except Exception:
             self.log_message(GENERIC_ERROR_MSG, level="ERROR")
             self.after(0, self.update_phone_entry_status, phone, "释放异常")
             stop_event = phone_info.get('stop_event')
             if stop_event: stop_event.clear()
    def _blacklist_specific_task(self, phone_info):
        phone = phone_info['phone']; project_id = phone_info['project_id']
        try:
            success = self.blacklist_phone(phone, project_id) # blacklist_phone 内部不再调用 clear_phone_details_ui
            if success:
                # --- 修改：拉黑成功后移除 UI 和数据 ---
                self.after(0, self.update_phone_entry_status, phone, "已拉黑") # 短暂显示
                try: self.active_phones.remove(phone_info)
                except ValueError: pass
                self.after(100, self.remove_phone_entry_widget, phone) # 稍后移除
                # --- 结束修改 ---
            else:
                self.after(0, self.update_phone_entry_status, phone, "拉黑失败")
                stop_event = phone_info.get('stop_event')
                if stop_event: stop_event.clear()
        except Exception:
             self.log_message(GENERIC_ERROR_MSG, level="ERROR")
             self.after(0, self.update_phone_entry_status, phone, "拉黑异常")
             stop_event = phone_info.get('stop_event')
             if stop_event: stop_event.clear()
    def _release_all_task(self):
        try:
            success = self.release_all_phones()
            if success:
                self.log_message("已请求释放所有号码。")
                self.after(0, self.clear_all_phone_entries) # 清理所有条目
            else: pass # 失败已提示
        except Exception:
             self.log_message(GENERIC_ERROR_MSG, level="ERROR")
             self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
            self.after(0, self.update_ui_state, False)
    def clear_all_phone_entries(self):
        for phone_info in self.active_phones:
            stop_event = phone_info.get('stop_event')
            if stop_event: stop_event.set()
        for widget in self.phone_widgets.values(): widget.destroy()
        self.phone_widgets.clear(); self.active_phones.clear(); self.stop_events.clear()
        self._update_row_colors()

    # --- 数据库交互方法 ---
    # ... (保持不变) ...
    def _get_db_connection(self):
        last_error = None
        for attempt in range(DB_RETRY_COUNT):
            try:
                conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE, connect_timeout=5)
                if conn.is_connected(): return conn
            except MySQLError as e: last_error = e; time.sleep(DB_RETRY_DELAY)
            except Exception as e: last_error = e; break
        self.log_message(GENERIC_ERROR_MSG, level="ERROR"); messagebox.showerror("数据库连接失败", GENERIC_ERROR_MSG + f"\n(重试 {DB_RETRY_COUNT} 次失败)"); return None
    def _decrement_usage(self, phone_number, project_id, verification_code):
        if not self.logged_in_user_id: return False
        conn = self._get_db_connection(); cursor = None
        if not conn: return False
        try:
            cursor = conn.cursor()
            conn.start_transaction()
            sql_update = "UPDATE users SET remaining_uses = GREATEST(0, remaining_uses - 1) WHERE id = %s"
            cursor.execute(sql_update, (self.logged_in_user_id,))
            sql_insert_log = """INSERT INTO usage_logs (user_id, phone_number, project_id, verification_code, usage_timestamp) VALUES (%s, %s, %s, %s, NOW())"""
            log_data = (self.logged_in_user_id, phone_number, project_id, verification_code)
            cursor.execute(sql_insert_log, log_data)
            conn.commit()
            if self.remaining_uses > 0: self.remaining_uses -= 1
            self._write_usage_cache(self.remaining_uses)
            self.log_message(f"号码 {phone_number} 次数已扣减，剩余: {self.remaining_uses}")
            self.after(0, lambda: self.uses_var.set(f"次数: {self.remaining_uses}"))
            return True
        except MySQLError: conn.rollback(); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); return False
        except Exception: conn.rollback(); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); return False
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()


    # --- 本地缓存方法 ---
    # ... (保持不变) ...
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
    # ... (try_login, handle_api_error 保持不变) ...
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
        # --- 修改：将释放/拉黑的 200 code 也视为成功 ---
        is_release_blacklist = operation_name.startswith("释放") or operation_name.startswith("拉黑")
        if is_release_blacklist and str(error_code) == "200": return True # 200 也算成功
        # --- 结束修改 ---
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE: self.log_message("API 令牌过期，尝试重连..."); self.token = None
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg: pass
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            try: self.try_login(); return True
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("API 错误", "API 令牌过期且无法自动重新登录"+ADMIN_CONTACT_MSG)); return False
        if error_code != 0 and str(error_code) != "0" and not is_waiting_msg and str(error_code) != TOKEN_EXPIRED_ERROR_CODE: return False
        return True

    def get_phone_number(self, specified_phone=None): # 恢复：主要用于随机获取
        """持续获取随机手机号码"""
        if not self.token or not self.server: self.log_message("API 未初始化"+ADMIN_CONTACT_MSG, level="ERROR"); return None
        if not self.current_project_id: self.log_message("未配置项目"+ADMIN_CONTACT_MSG, level="ERROR"); return None
        # --- 恢复：移除指定号码参数 ---
        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={self.current_project_id}"
        # --- 结束恢复 ---
        retry_delay = 3; # self.log_message("正在获取手机号...") # 调用者记录
        while True: # 恢复无限循环
            if not self.token: self.log_message("API 令牌失效"+ADMIN_CONTACT_MSG, level="ERROR"); return None
            try:
                response = requests.get(url, headers=headers, timeout=20, verify=True)
                data = response.json(); code = data.get("code"); msg = data.get("msg", "")
                if code == 0 or str(code) == "0":
                    phone = data.get("phone")
                    if phone: return phone # 直接返回号码
                    else: time.sleep(retry_delay); continue # 无号码，静默重试
                elif str(code) == "-1" and ("没有可用手机号" in msg or "请稍后再试" in msg or "等待" == msg): time.sleep(retry_delay); continue # 等待，静默重试
                else:
                    if self.handle_api_error(data, "获取手机号"): url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={self.current_project_id}"; continue # 令牌刷新后重试
                    else: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("API 错误", "获取手机号失败"+ADMIN_CONTACT_MSG)); return None # 无法处理的API错误
            except requests.exceptions.RequestException: time.sleep(5); continue # 网络错误/超时/SSL错误，静默重试
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return None # 未知异常

    def wait_for_verification_code(self, phone, project_id, stop_event, timeout=200):
        if not self.token or not self.server: return None
        start_time = time.time(); polling_interval = 4
        while time.time() - start_time < timeout:
            if stop_event and stop_event.is_set(): self.log_message(f"号码 {phone} 获取验证码被中断。"); return None
            if not self.token: return None
            params = {"api": "getMessage", "token": self.token, "sid": project_id, "phone": phone}
            url = f"{self.server}/sms/?{urlencode(params)}"
            try:
                response = requests.get(url, headers=headers, timeout=15, verify=True)
                data = response.json(); code = data.get("code"); msg = data.get("msg", "")
                if code == 0 or str(code) == "0":
                    verification_code = data.get("yzm") or msg
                    if verification_code and verification_code != "ok":
                        if len(verification_code) > 1 and verification_code.isalnum(): self.log_message(f"号码 {phone} 成功获取验证码: {verification_code}"); return verification_code
                elif "尚未接收到短信" in msg or (code == -1 and msg == "等待"): pass
                else:
                    if self.handle_api_error(data, f"获取验证码({phone})"): params["token"] = self.token; url = f"{self.server}/sms/?{urlencode(params)}"; continue
                    else: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda p=phone: messagebox.showerror("API 错误", f"号码 {p} 获取验证码失败"+ADMIN_CONTACT_MSG)); return None
            except requests.exceptions.RequestException: pass
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return None
            time.sleep(polling_interval)
        return None # Timeout

    def release_phone(self, phone, project_id): # 新增：释放单个 API
        if not self.token or not self.server: return False
        url = f"{self.server}/sms/?api=cancelRecv&token={self.token}&sid={project_id}&phone={phone}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json(); code = data.get("code")
            if code == 0 or str(code) == "0" or str(code) == "200": self.log_message(f"号码 {phone} 已成功释放。"); return True
            else:
                if self.handle_api_error(data, f"释放手机号({phone})"): return self.release_phone(phone, project_id)
                self.log_message(f"释放号码 {phone} 失败", level="WARN"); return False # 只记录警告
        except requests.exceptions.RequestException: self.log_message("释放号码网络异常", level="WARN"); return False # 网络异常视为警告
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); return False

    def release_all_phones(self): # 新增：释放全部 API
        if not self.token or not self.server: return False
        url = f"{self.server}/sms/?api=cancelAllRecv&token={self.token}"
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=True)
            data = response.json(); code = data.get("code")
            if code == 0 or str(code) == "0" or str(code) == "200": return True
            else:
                if self.handle_api_error(data, "释放全部号码"): return self.release_all_phones()
                self.log_message(f"释放全部号码失败", level="WARN"); messagebox.showwarning("操作失败", "释放全部号码失败"+ADMIN_CONTACT_MSG); return False
        except requests.exceptions.RequestException: self.log_message("释放全部号码网络异常", level="WARN"); messagebox.showerror("网络错误", "释放全部号码操作网络异常"+ADMIN_CONTACT_MSG); return False
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); messagebox.showerror("严重错误", GENERIC_ERROR_MSG); return False

    def blacklist_phone(self, phone, project_id):
        if not self.token or not self.server: return False
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={project_id}&phone={phone}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0" or str(data.get("code")) == "200":
                self.log_message(f"号码 {phone} 已拉黑。")
                # UI 清理由调用者完成
                return True
            else:
                if self.handle_api_error(data, f"拉黑手机号({phone})"): return self.blacklist_phone(phone, project_id)
                self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda p=phone: messagebox.showerror("操作失败", f"拉黑号码 {p} 失败"+ADMIN_CONTACT_MSG)); return False
        except requests.exceptions.RequestException: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("网络错误", "拉黑操作网络异常"+ADMIN_CONTACT_MSG)); return False
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return False

    # --- GUI 辅助方法 ---
    def copy_text(self, text_to_copy, text_type="文本"):
        if text_to_copy:
            try: pyperclip.copy(text_to_copy); self.log_message(f"{text_type} {text_to_copy} 已复制。"); self.set_status(f"{text_type}已复制。")
            except Exception: self.log_message(f"复制{text_type}失败。")
        else: self.log_message(f"没有{text_type}可复制。")
    def copy_phone(self): # 全局按钮复制最后一个活动号码
        active_phones = [p['phone'] for p in self.active_phones if p.get('status') not in ['已拉黑', '已释放']]
        if active_phones: self.copy_text(active_phones[-1], "号码")
        else: self.log_message("没有号码可复制。")
    def copy_code(self): # 全局按钮复制最后一个成功获取的验证码
        last_successful_code = None
        active_successful = [p for p in self.active_phones if p.get('status') == '获取成功' and p.get('code')]
        if active_successful: last_successful_code = active_successful[-1]['code']
        if last_successful_code: self.copy_text(last_successful_code, "验证码")
        else: self.log_message("没有有效的验证码可复制。")
    def clear_phone_details_ui(self, phone): # 只更新状态，不移除
        widget = self.phone_widgets.get(phone)
        if widget: widget.update_status("已拉黑"); widget.disable_actions()
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
        for phone_info in self.active_phones:
            stop_event = phone_info.get('stop_event')
            if stop_event: stop_event.set()
        self._delete_usage_cache()
        self.destroy()
    def logout(self):
        """处理注销/切换账号逻辑"""
        if self.is_working_global:
            messagebox.showwarning("请稍候", "请等待当前操作完成后再注销。")
            return

        # --- 停止所有后台线程 ---
        for phone_info in self.active_phones:
            stop_event = phone_info.get('stop_event')
            if stop_event: stop_event.set()
        # --- 结束停止 ---

        # 清理 keyring
        if self.logged_in_username:
            try:
                # 仅清除自动登录标志和最后用户，保留密码以便下次登录填充
                # keyring.delete_password(KEYRING_SERVICE_NAME, self.logged_in_username) # 不清除密码
                keyring.delete_password(KEYRING_SERVICE_NAME, "last_user")
                keyring.delete_password(KEYRING_SERVICE_NAME, "auto_login")
            except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError):
                pass # 忽略错误

        # 清理内存状态
        self.token = None; self.server = None
        self.logged_in_user_id = None; self.logged_in_username = None; self.remaining_uses = 0
        self.current_project_id = None; self.current_project_name = self.default_title

        # 清理缓存
        self._delete_usage_cache()

        # 清理号码列表 UI
        for widget in self.phone_widgets.values():
            widget.destroy()
        self.phone_widgets.clear()
        self.active_phones.clear()
        # self.stop_events.clear() # stop_events 似乎没有被使用，可以移除或保留

        # 重置 UI
        self.title(f"{self.default_title} - 未登录")
        self.project_name_var.set(self.default_title) # 重置项目名称显示
        self.username_var.set("未登录")
        self.uses_var.set("--")
        # phone_var 和 code_var 不需要重置，因为列表清空了
        self.update_ui_state(False) # 禁用按钮
        self.log_message("用户已注销。")
        self.status_var.set("已注销，请登录。")

        # --- 修改：隐藏主窗口并重新安排显示登录窗口 ---
        self.withdraw() # 隐藏主窗口
        self.after(10, self.show_login_window) # 安排显示登录窗口
        # --- 结束修改 ---


# --- 登录窗口类 ---
class LoginWindow(customtkinter.CTkToplevel):
    # ... (LoginWindow 代码保持不变) ...
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.parent = parent; self.app = app_instance
        self.title("用户登录"); self.geometry("380x320"); self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_closing); self.grab_set(); self.transient(parent)
        self.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(self, text="用户名:").grid(row=0, column=0, padx=(20, 5), pady=10, sticky="w")
        self.username_entry = customtkinter.CTkEntry(self, width=200); self.username_entry.grid(row=0, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")
        customtkinter.CTkLabel(self, text="密  码:").grid(row=1, column=0, padx=(20, 5), pady=10, sticky="w")
        self.password_entry = customtkinter.CTkEntry(self, show="*", width=200); self.password_entry.grid(row=1, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        option_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        option_frame.grid(row=2, column=0, columnspan=3, padx=20, pady=5, sticky="w")
        self.remember_var = BooleanVar()
        self.remember_check = customtkinter.CTkCheckBox(option_frame, text="记住密码", variable=self.remember_var, command=self._on_remember_change)
        self.remember_check.pack(side=LEFT, padx=(0, 10))
        self.autologin_var = BooleanVar()
        self.autologin_check = customtkinter.CTkCheckBox(option_frame, text="自动登录", variable=self.autologin_var, state=DISABLED)
        self.autologin_check.pack(side=LEFT)

        button_frame = customtkinter.CTkFrame(self, fg_color="transparent"); button_frame.grid(row=3, column=0, columnspan=3, pady=15)
        customtkinter.CTkButton(button_frame, text="退出", command=self._on_closing, width=80, fg_color="gray", hover_color="dimgray").pack(side=RIGHT, padx=10)
        customtkinter.CTkButton(button_frame, text="登录", command=self._login, width=80).pack(side=RIGHT, padx=10)

        contact_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        contact_frame.grid(row=4, column=0, columnspan=3, padx=20, pady=(10, 10), sticky="ew")
        contact_frame.grid_columnconfigure(0, weight=1)
        contact_label1 = customtkinter.CTkLabel(contact_frame, text=ADMIN_CONTACT_INFO_LINE1, font=customtkinter.CTkFont(size=12, weight="bold"))
        contact_label1.grid(row=0, column=0, sticky="w")
        contact_label2 = customtkinter.CTkLabel(contact_frame, text=ADMIN_CONTACT_INFO_LINE2, font=customtkinter.CTkFont(size=12, weight="bold"))
        contact_label2.grid(row=1, column=0, sticky="w")
        copy_contact_btn = customtkinter.CTkButton(contact_frame, text="复制联系方式", width=100, height=24, font=customtkinter.CTkFont(size=10), command=self._copy_contact)
        copy_contact_btn.grid(row=0, column=1, rowspan=2, padx=(10, 0), sticky="e")

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
            sql = "SELECT id, username, password_hash, remaining_uses, project_id, project_name FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user_row = cursor.fetchone()
            if user_row and check_password_hash(user_row["password_hash"], password):
                if user_row["remaining_uses"] <= 0:
                    messagebox.showwarning("登录失败", "您的可用次数不足，请联系管理员充值。", parent=self)
                    if auto_login:
                        try: keyring.delete_password(KEYRING_SERVICE_NAME, "auto_login")
                        except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError): pass
                    return
                self.destroy()
                self.app.on_login_success(
                    user_row["id"], user_row["username"], user_row["remaining_uses"],
                    user_row["project_id"], user_row["project_name"],
                    remember, password, auto_login
                )
            else: messagebox.showerror("登录失败", "用户名或密码错误。", parent=self)
        except MySQLError: messagebox.showerror("数据库错误", GENERIC_ERROR_MSG, parent=self)
        except Exception: messagebox.showerror("严重错误", GENERIC_ERROR_MSG, parent=self)
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    def _copy_contact(self):
        try:
            pyperclip.copy(ADMIN_CONTACT_NUMBER)
            messagebox.showinfo("已复制", f"管理员联系方式 {ADMIN_CONTACT_NUMBER} 已复制到剪贴板。", parent=self)
        except Exception as e: messagebox.showwarning("复制失败", f"无法复制到剪贴板: {e}", parent=self)

    def _on_closing(self):
        self.destroy(); self.parent.destroy()


# --- 程序主入口 ---
if __name__ == "__main__":
    try: import pyperclip
    except ImportError: messagebox.showerror("缺少库", "运行本程序需要安装 pyperclip 库。\n请运行: pip install pyperclip"); sys.exit(1)
    if not test_database_connection(): sys.exit(1)
    app = SmsApp()
    app.mainloop()
