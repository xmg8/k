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
from werkzeug.security import generate_password_hash, check_password_hash # 仍然需要 check_password_hash

# --- MySQL Database Configuration ---
# !!! 重要安全提示 !!!
# !!! 不要在生产环境中硬编码密码 !!!
# !!! 考虑使用环境变量、配置文件或更安全的凭证管理方法 !!!
MYSQL_HOST = "152.136.171.223"  # 替换为你的 MySQL 服务器地址 (e.g., "localhost", "192.168.1.100")
MYSQL_USER = "wxxmg888" # 替换为你的 MySQL 用户名
MYSQL_PASSWORD = "xmg888.top" # 替换为你的 MySQL 密码
MYSQL_DATABASE = "wxxmg888" # 替换为你的数据库名称

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
TOKEN_FILE = os.path.join(application_path, "token.txt")

# --- API 请求头 ---
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

# --- 数据库连接测试 ---
def test_database_connection():
    """测试到 MySQL 数据库的连接"""
    print("DEBUG: Entering test_database_connection...") # 添加调试打印
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        if conn.is_connected():
            print("MySQL 数据库连接成功。")
            conn.close()
            print("DEBUG: Exiting test_database_connection (Success).") # 添加调试打印
            return True
    except MySQLError as e:
        print(f"MySQL 数据库连接错误: {e}")
        messagebox.showerror("数据库连接错误", f"无法连接到 MySQL 数据库: {e}\n请检查配置或联系管理员。")
        print("DEBUG: Exiting test_database_connection (Failure).") # 添加调试打印
        return False

# --- GUI 应用主类 ---
class SmsApp:
    def __init__(self, root):
        """初始化应用程序窗口和变量"""
        print("DEBUG: Entering SmsApp.__init__...") # 添加调试打印
        self.root = root
        self.root.title("无尽冬日接码工具 - 未登录") # 初始标题
        self.root.geometry("600x480")
        print("DEBUG: SmsApp - Withdrawing root window...") # 添加调试打印
        self.root.withdraw() # 初始隐藏主窗口

        # 实例变量
        self.token = None           # API 访问令牌
        self.phone_number = None    # 当前获取到的手机号
        self.server = None          # 当前使用的 API 服务器地址
        self.is_working = False     # 标记是否有后台任务正在运行
        self.auto_fetch_job = None  # 用于存储 Tkinter 的 after 任务 ID，以便取消
        # 用户相关状态
        self.logged_in_user_id = None
        self.logged_in_username = None
        self.remaining_uses = 0
        print("DEBUG: SmsApp - Variables initialized.") # 添加调试打印

        # --- 创建主窗口 GUI 元素 ---
        print("DEBUG: SmsApp - Calling _create_main_widgets...") # 添加调试打印
        self._create_main_widgets()
        print("DEBUG: SmsApp - _create_main_widgets finished.") # 添加调试打印

        # --- 显示登录窗口 ---
        print("DEBUG: SmsApp - Calling show_login_window...") # 添加调试打印
        self.show_login_window()
        print("DEBUG: SmsApp - show_login_window finished.") # 添加调试打印
        print("DEBUG: Exiting SmsApp.__init__.") # 添加调试打印

    def _create_main_widgets(self):
        """创建主应用程序窗口的控件"""
        print("DEBUG: Entering _create_main_widgets...") # 添加调试打印
        # 主控制框架
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(pady=10, padx=10, fill=tk.X)
        control_frame.columnconfigure(1, weight=1)

        # 剩余次数显示
        ttk.Label(control_frame, text="剩余次数:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.uses_var = tk.StringVar(value="--") # 初始值
        self.uses_label = ttk.Label(control_frame, textvariable=self.uses_var, width=15, anchor=tk.W)
        self.uses_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # 用户名显示
        ttk.Label(control_frame, text="当前用户:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)
        self.username_var = tk.StringVar(value="未登录")
        self.username_label = ttk.Label(control_frame, textvariable=self.username_var, anchor=tk.E)
        self.username_label.grid(row=0, column=3, padx=5, pady=5, sticky=tk.E)

        # 手机号码显示
        ttk.Label(control_frame, text="手机号码:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.phone_var = tk.StringVar(value="尚未获取")
        self.phone_entry = ttk.Entry(control_frame, textvariable=self.phone_var, state='readonly', width=20)
        self.phone_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        # 验证码显示
        ttk.Label(control_frame, text="验证码:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.code_var = tk.StringVar(value="尚未获取")
        self.code_entry = ttk.Entry(control_frame, textvariable=self.code_var, state='readonly', width=20)
        self.code_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # 功能按钮 (初始禁用)
        self.get_phone_btn = ttk.Button(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=15, state=tk.DISABLED)
        self.get_phone_btn.grid(row=1, column=2, padx=(10,5), pady=5, sticky=tk.E)

        self.copy_phone_btn = ttk.Button(control_frame, text="复制手机号码", command=self.copy_phone, width=15, state=tk.DISABLED)
        self.copy_phone_btn.grid(row=1, column=3, padx=5, pady=5, sticky=tk.E)

        self.copy_code_btn = ttk.Button(control_frame, text="复制验证码", command=self.copy_code, width=15, state=tk.DISABLED)
        self.copy_code_btn.grid(row=2, column=3, padx=5, pady=5, sticky=tk.E)

        self.blacklist_btn = ttk.Button(control_frame, text="拉黑手机号码", command=self.start_blacklist_thread, width=15, state=tk.DISABLED)
        self.blacklist_btn.grid(row=3, column=3, padx=5, pady=10, sticky=tk.E)

        # 日志输出区域
        log_frame = ttk.LabelFrame(self.root, text="日志输出", padding="10")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        self.status_var = tk.StringVar(value="请先登录.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        print("DEBUG: Exiting _create_main_widgets.") # 添加调试打印

    def show_login_window(self): # 修改方法名
        """显示登录窗口"""
        print("DEBUG: Entering show_login_window...") # 添加调试打印
        LoginWindow(self.root, self) # 调用 LoginWindow
        print("DEBUG: Exiting show_login_window.") # 添加调试打印

    def on_login_success(self, user_id, username, remaining_uses):
        """登录成功后的回调函数"""
        print("DEBUG: Entering on_login_success...") # 添加调试打印
        self.logged_in_user_id = user_id
        self.logged_in_username = username
        self.remaining_uses = remaining_uses

        print("DEBUG: Deiconifying root window...") # 添加调试打印
        self.root.deiconify() # 显示主窗口
        self.root.title(f"无尽冬日接码工具 - 用户: {username}") # 更新标题
        self.username_var.set(username)
        self.uses_var.set(str(remaining_uses))
        self.status_var.set("登录成功，正在初始化...")
        self.log_message(f"用户 {username} 登录成功，剩余次数: {remaining_uses}")

        print("DEBUG: Calling start_initial_login_thread...") # 添加调试打印
        self.start_initial_login_thread()
        print("DEBUG: Calling update_ui_state(False)...") # 添加调试打印
        self.update_ui_state(False) # 初始为非工作状态
        print("DEBUG: Exiting on_login_success.") # 添加调试打印

    # --- 日志记录与状态更新方法 ---
    def log_message(self, message):
        if self.root: self.root.after(0, self._append_log, message)
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

    # --- UI 状态管理 ---
    def update_ui_state(self, working):
        """根据工作状态、登录状态和剩余次数启用/禁用 GUI 元素"""
        # print(f"DEBUG: update_ui_state called with working={working}") # 可以取消注释以获得更详细的UI更新日志
        self.is_working = working
        is_logged_in = bool(self.logged_in_user_id)
        default_state = tk.DISABLED if working or not is_logged_in else tk.NORMAL
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
            self.blacklist_btn.config(state=blacklist_state)
            self.copy_phone_btn.config(state=copy_phone_state)
            self.copy_code_btn.config(state=copy_code_state)
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
        print("DEBUG: Entering start_initial_login_thread...") # 添加调试打印
        self.set_status("正在初始化 API 连接...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True)
        thread.start()
        print("DEBUG: Exiting start_initial_login_thread.") # 添加调试打印
    def start_get_phone_thread(self):
        print("DEBUG: Entering start_get_phone_thread...") # 添加调试打印
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); print("DEBUG: Not logged in, returning."); return
        if self.is_working:
             if "等待获取验证码" in self.status_var.get(): self.log_message("提示：正在等待10秒后获取验证码...")
             else: self.log_message("错误：请等待当前操作完成。")
             print("DEBUG: Already working, returning."); return
        if self.remaining_uses <= 0: messagebox.showerror("次数不足", "您的剩余使用次数不足。"); self.log_message("错误：剩余使用次数不足。"); print("DEBUG: No remaining uses, returning."); return
        if not self.token or not self.server: self.log_message("错误：API 未初始化。"); messagebox.showerror("错误", "API 连接未就绪。"); print("DEBUG: API not ready, returning."); return
        if self.auto_fetch_job:
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None; print("DEBUG: Cancelled pending auto fetch job.")
        self.update_ui_state(True)
        self.phone_var.set("正在获取...")
        self.code_var.set("尚未获取")
        self.log_message(f"开始获取手机号 (剩余次数: {self.remaining_uses})...")
        thread = threading.Thread(target=self._get_phone_task, daemon=True)
        thread.start()
        print("DEBUG: Exiting start_get_phone_thread.") # 添加调试打印
    def start_automatic_code_fetch(self):
        print("DEBUG: Entering start_automatic_code_fetch...") # 添加调试打印
        self.auto_fetch_job = None
        if not self.phone_number: self.log_message("错误：手机号丢失..."); self.update_ui_state(False); print("DEBUG: No phone number, returning."); return
        if not self.logged_in_user_id: print("DEBUG: Not logged in, returning."); return
        self.is_working = True
        self.set_status("正在获取验证码...")
        self.code_var.set("正在获取...")
        self.update_ui_state(True)
        self.log_message(f"开始为号码 {self.phone_number} 自动获取验证码...")
        thread = threading.Thread(target=self._get_code_task_automatic, daemon=True)
        thread.start()
        print("DEBUG: Exiting start_automatic_code_fetch.") # 添加调试打印
    def start_blacklist_thread(self):
        print("DEBUG: Entering start_blacklist_thread...") # 添加调试打印
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); print("DEBUG: Not logged in, returning."); return
        if self.is_working:
             if "等待获取验证码" in self.status_var.get(): self.log_message("提示：正在等待10秒后获取验证码...")
             else: self.log_message("错误：请等待当前操作完成。")
             print("DEBUG: Already working, returning."); return
        if not self.phone_number: messagebox.showerror("错误", "没有可用的手机号码。"); print("DEBUG: No phone number, returning."); return
        if self.auto_fetch_job:
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None; self.log_message("已取消等待获取验证码。"); self.set_status("就绪."); print("DEBUG: Cancelled pending auto fetch job.")
        if messagebox.askyesno("确认", f"确定要拉黑号码 {self.phone_number} 吗？"):
            self.update_ui_state(True)
            self.log_message(f"尝试拉黑号码: {self.phone_number}")
            thread = threading.Thread(target=self._blacklist_task, daemon=True)
            thread.start()
        else: self.log_message("拉黑操作已取消。")
        print("DEBUG: Exiting start_blacklist_thread.") # 添加调试打印

    # --- 后台任务方法 ---
    def _initial_login_task(self):
        print("DEBUG: Entering _initial_login_task...") # 添加调试打印
        try:
            if not self.read_token():
                try: self.try_login()
                except Exception as e:
                    self.log_message(f"初始化 API 连接失败: {e}")
                    self.root.after(0, lambda: messagebox.showwarning("API 错误", f"无法连接或登录好猪码服务: {e}"))
                    self.set_status("API 连接失败...")
                    print("DEBUG: API login failed.") # 添加调试打印
                    return
            self.log_message("API 连接初始化成功。")
            self.root.after(0, self.update_ui_state, False)
        except Exception as e: self.log_message(f"初始化 API 连接过程中发生未知错误: {e}"); self.set_status("API 初始化异常。")
        print("DEBUG: Exiting _initial_login_task.") # 添加调试打印
    def _get_phone_task(self):
        print("DEBUG: Entering _get_phone_task...") # 添加调试打印
        phone_obtained = False
        try:
            phone = self.get_phone_number()
            if phone:
                phone_obtained = True
                self.root.after(0, lambda p=phone: self.phone_var.set(p))
                self.root.after(0, self.update_ui_state, False)
                self.log_message("手机号获取成功，将在 10 秒后开始获取验证码...")
                self.set_status("等待获取验证码 (10s)...")
                try: self.auto_fetch_job = self.root.after(10000, self.start_automatic_code_fetch)
                except tk.TclError: self.log_message("错误：窗口已关闭..."); phone_obtained = False
            else:
                self.root.after(0, lambda: self.phone_var.set("获取失败"))
                self.log_message("获取手机号失败 (无法恢复的错误)。")
        except Exception as e:
            self.root.after(0, lambda: self.phone_var.set("获取异常"))
            self.log_message(f"获取手机号时发生异常: {e}")
        finally:
            if not phone_obtained: self.root.after(0, self.update_ui_state, False)
            print("DEBUG: Exiting _get_phone_task.") # 添加调试打印
    def _get_code_task_automatic(self):
        print("DEBUG: Entering _get_code_task_automatic...") # 添加调试打印
        code = None; restart_needed = False
        try:
            code = self.wait_for_verification_code(timeout=200)
            if code:
                self.root.after(0, lambda c=code: self.code_var.set(c))
                self.log_message("验证码获取成功，正在扣减次数...")
                self._decrement_usage() # <--- 扣减次数
                self.root.after(0, self.update_ui_state, False)
            else: # Timeout
                self.log_message("验证码获取超时 (200秒)。")
                self.root.after(0, lambda: self.code_var.set("获取超时"))
                if self.phone_number:
                    self.log_message(f"自动拉黑号码: {self.phone_number}")
                    blacklist_success = self.blacklist_phone()
                    if blacklist_success: restart_needed = True; self.root.after(0, self.restart_process_after_timeout)
                    else: self.log_message("拉黑失败，无法自动重启流程。")
                else: self.log_message("无号码可拉黑，无法自动重启流程。")
        except Exception as e:
            self.root.after(0, lambda: self.code_var.set("获取异常"))
            self.log_message(f"自动获取验证码时发生异常: {e}")
        finally:
            if not restart_needed: self.root.after(0, self.update_ui_state, False)
            print("DEBUG: Exiting _get_code_task_automatic.") # 添加调试打印
    def _blacklist_task(self):
        print("DEBUG: Entering _blacklist_task...") # 添加调试打印
        try:
            success = self.blacklist_phone()
            if not success: self.log_message("手动拉黑手机号失败。")
        except Exception as e: self.log_message(f"手动拉黑手机号时发生异常: {e}")
        finally: self.root.after(0, self.update_ui_state, False)
        print("DEBUG: Exiting _blacklist_task.") # 添加调试打印
    def restart_process_after_timeout(self):
        print("DEBUG: Entering restart_process_after_timeout...") # 添加调试打印
        try:
            self.log_message("验证码超时，自动重新开始获取手机号...")
            self.phone_var.set("重新获取...")
            self.code_var.set("尚未获取")
            self.is_working = False
            self.update_ui_state(False)
            self.root.after(50, self.start_get_phone_thread)
        except tk.TclError: self.log_message("错误：窗口已关闭，无法重启流程。")
        print("DEBUG: Exiting restart_process_after_timeout.") # 添加调试打印

    # --- 数据库交互方法 (使用 MySQL) ---
    def _get_db_connection(self):
        """获取 MySQL 数据库连接"""
        # print("DEBUG: Entering _get_db_connection...") # 这个可能会打印很多次，暂时注释
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE
            )
            if conn.is_connected(): return conn
            else: self.log_message("无法连接到 MySQL 数据库。"); messagebox.showerror("数据库错误", "无法连接到用户数据库。"); return None
        except MySQLError as e: self.log_message(f"MySQL 连接错误: {e}"); messagebox.showerror("数据库错误", f"无法连接到用户数据库: {e}"); return None
    def _decrement_usage(self):
        """在 MySQL 数据库中将当前用户的剩余次数减 1"""
        print("DEBUG: Entering _decrement_usage...") # 添加调试打印
        if not self.logged_in_user_id: print("DEBUG: Not logged in, cannot decrement usage."); return
        conn = self._get_db_connection(); cursor = None
        if not conn: print("DEBUG: DB connection failed, cannot decrement usage."); return
        try:
            cursor = conn.cursor()
            sql = "UPDATE users SET remaining_uses = GREATEST(0, remaining_uses - 1) WHERE id = %s"
            cursor.execute(sql, (self.logged_in_user_id,))
            conn.commit()
            if self.remaining_uses > 0: self.remaining_uses -= 1
            self.log_message(f"使用次数已扣减，剩余: {self.remaining_uses}")
            self.root.after(0, lambda: self.uses_var.set(str(self.remaining_uses)))
            self.root.after(0, self.update_ui_state, False)
        except MySQLError as e: self.log_message(f"扣减使用次数时 MySQL 错误: {e}"); messagebox.showerror("数据库错误", f"无法更新使用次数: {e}")
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()
            print("DEBUG: Exiting _decrement_usage.") # 添加调试打印

    # --- API 交互方法 (好猪码部分) ---
    def read_token(self):
        print("DEBUG: Entering read_token...") # 添加调试打印
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f: read_token = f.read().strip()
                if read_token:
                    for s in SERVERS:
                        try:
                            url = f"{s}/sms/?api=getSummary&token={read_token}"
                            response = requests.get(url, headers=headers, timeout=10, verify=True)
                            response.raise_for_status(); data = response.json()
                            if data.get("code") == 0 or str(data.get("code")) == "0": self.server = s; self.token = read_token; print("DEBUG: Token read and validated."); return True
                        except requests.exceptions.SSLError as ssl_err: self.log_message(f"验证令牌时SSL错误 ({s}): {ssl_err}")
                        except requests.exceptions.RequestException: pass
                    self.token = None; self.server = None; print("DEBUG: Token read but validation failed."); return False
            except Exception as e: self.log_message(f"读取令牌文件时出错: {e}")
        print("DEBUG: Token file not found or read failed."); return False
    def save_token(self):
        print("DEBUG: Entering save_token...") # 添加调试打印
        if not self.token: print("DEBUG: No token to save."); return
        try:
            with open(TOKEN_FILE, 'w') as f: f.write(self.token)
            print("DEBUG: Token saved.") # 添加调试打印
        except Exception as e: self.log_message(f"保存令牌到文件时出错: {e}")
    def try_login(self):
        print("DEBUG: Entering try_login (API)...") # 添加调试打印
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                response = requests.get(login_url, headers=headers, timeout=15, verify=True)
                response.raise_for_status(); data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0": self.server = s; self.token = data["token"]; self.save_token(); print(f"DEBUG: API login successful on {s}."); return
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"登录好猪码时SSL错误 ({s}): {ssl_err}")
            except requests.exceptions.Timeout: pass
            except requests.exceptions.RequestException: pass
            except Exception as e: self.log_message(f"处理好猪码服务器 {s} 响应时发生未知错误: {e}")
        self.server = None; self.token = None
        print("DEBUG: API login failed on all servers.") # 添加调试打印
        raise Exception("所有好猪码服务器登录尝试均失败")
    def handle_api_error(self, data, operation_name):
        # print(f"DEBUG: Entering handle_api_error for {operation_name}...") # 可能过于频繁
        error_code = data.get("code"); error_msg = data.get('msg', '未知错误')
        is_waiting_msg = "尚未接收" in error_msg or "等待" == error_msg or "没有可用" in error_msg
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE: self.log_message("好猪码令牌过期或无效..."); self.token = None
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg: self.log_message(f"好猪码API-{operation_name}失败: {error_code}, {error_msg}")
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            try: self.try_login(); return True
            except Exception as e: self.log_message(f"重新登录好猪码失败: {e}"); self.root.after(0, lambda: messagebox.showwarning("API 错误", f"好猪码令牌过期后无法重新登录: {e}")); return False
        return False
    def get_balance(self): # 不再核心使用
        print("DEBUG: Entering get_balance (API)...") # 添加调试打印
        if not self.token or not self.server: return None
        url = f"{self.server}/sms/?api=getSummary&token={self.token}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0": return data.get("money", "未知")
            else:
                if self.handle_api_error(data, "获取好猪码余额"): return self.get_balance()
                return None
        except requests.exceptions.SSLError as ssl_err: self.log_message(f"获取好猪码余额时SSL错误: {ssl_err}")
        except requests.exceptions.RequestException as e: self.log_message(f"获取好猪码余额网络异常: {e}")
        except Exception as e: self.log_message(f"获取好猪码余额未知异常: {e}")
        return None
    def get_phone_number(self):
        print("DEBUG: Entering get_phone_number (API)...") # 添加调试打印
        if not self.token or not self.server: return None
        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
        retry_delay = 3; self.log_message("正在持续获取手机号...")
        while True:
            if not self.token: self.log_message("获取手机号中断：好猪码令牌失效。"); return None
            try:
                response = requests.get(url, headers=headers, timeout=20, verify=True)
                data = response.json(); code = data.get("code"); msg = data.get("msg", "")
                if code == 0 or str(code) == "0":
                    phone = data.get("phone")
                    if phone: self.phone_number = phone; self.root.after(0, lambda: self.code_var.set("尚未获取")); self.log_message(f"成功获取手机号: {self.phone_number}"); print("DEBUG: Phone number obtained."); return self.phone_number
                    else: self.log_message("API响应成功但未包含手机号..."); time.sleep(retry_delay); continue
                elif str(code) == "-1" and ("没有可用手机号" in msg or "请稍后再试" in msg or "等待" == msg): self.log_message(f"暂时无号或需等待({msg})...", retry_delay); time.sleep(retry_delay); continue
                else:
                    if self.handle_api_error(data, "获取手机号"): url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"; self.log_message("好猪码令牌已更新..."); continue
                    else: self.log_message("获取手机号API错误..."); self.phone_number = None; print("DEBUG: Unrecoverable API error in get_phone_number."); return None
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"获取手机号SSL错误: {ssl_err}..."); time.sleep(5); continue
            except requests.exceptions.Timeout: self.log_message("获取手机号超时..."); time.sleep(5); continue
            except requests.exceptions.RequestException as e: self.log_message(f"获取手机号网络错误: {e}..."); self.phone_number = None; print("DEBUG: Network error in get_phone_number."); return None
            except Exception as e: self.log_message(f"获取手机号未知异常: {e}..."); self.phone_number = None; print("DEBUG: Unknown exception in get_phone_number."); return None
    def wait_for_verification_code(self, timeout=200):
        print("DEBUG: Entering wait_for_verification_code...") # 添加调试打印
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
                        if len(verification_code) > 1 and verification_code.isalnum(): self.log_message(f"成功获取验证码: {verification_code}"); print("DEBUG: Verification code obtained."); return verification_code
                elif "尚未接收到短信" in msg or (code == -1 and msg == "等待"): pass
                else:
                    if self.handle_api_error(data, "获取验证码"): url = f"{self.server}/sms/?{urlencode(params)}"; continue
                    else: print("DEBUG: Unrecoverable API error in wait_for_verification_code."); return None
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"获取验证码轮询SSL错误: {ssl_err}...")
            except requests.exceptions.Timeout: self.log_message("获取验证码轮询超时...")
            except requests.exceptions.RequestException as e: self.log_message(f"获取验证码轮询网络错误: {e}...")
            except Exception as e: self.log_message(f"获取验证码轮询未知异常: {e}")
            time.sleep(polling_interval)
        print("DEBUG: wait_for_verification_code timed out."); return None # Timeout
    def blacklist_phone(self):
        print("DEBUG: Entering blacklist_phone...") # 添加调试打印
        if not self.token or not self.server or not self.phone_number: return False
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0": self.log_message(f"手机号码 {self.phone_number} 已成功拉黑。"); self.root.after(0, self.clear_phone_details); print("DEBUG: Blacklist successful."); return True
            else:
                if self.handle_api_error(data, "拉黑手机号"): return self.blacklist_phone()
                self.log_message(f"API拉黑失败: {data.get('msg', '未知错误')}"); print("DEBUG: Blacklist API error."); return False
        except requests.exceptions.SSLError as ssl_err: self.log_message(f"拉黑手机号时SSL错误: {ssl_err}")
        except requests.exceptions.RequestException as e: self.log_message(f"拉黑手机号网络异常: {e}")
        except Exception as e: self.log_message(f"拉黑手机号未知异常: {e}")
        print("DEBUG: Blacklist failed due to exception."); return False

    # --- GUI 辅助方法 ---
    def copy_phone(self):
        if self.phone_number:
            try: self.root.clipboard_clear(); self.root.clipboard_append(self.phone_number); self.log_message(f"号码 {self.phone_number} 已复制。"); self.set_status("号码已复制。")
            except tk.TclError: pass
        else: self.log_message("没有号码可复制。")
    def copy_code(self):
        code = self.code_var.get()
        if code and code not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]:
            try: self.root.clipboard_clear(); self.root.clipboard_append(code); self.log_message(f"验证码 {code} 已复制。"); self.set_status("验证码已复制。")
            except tk.TclError: pass
        else: self.log_message("没有有效的验证码可复制。")
    def clear_phone_details(self):
        self.phone_number = None
        try: self.phone_var.set("已拉黑"); self.code_var.set("尚未获取"); self.update_ui_state(self.is_working)
        except tk.TclError: pass


# --- 登录窗口类 (极简版，移除注册) ---
class LoginWindow(Toplevel):
    def __init__(self, parent, app_instance):
        print("DEBUG: Entering LoginWindow.__init__...") # 添加调试打印
        super().__init__(parent)
        self.parent = parent
        self.app = app_instance
        self.title("用户登录")
        self.geometry("300x170")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.grab_set(); self.transient(parent)

        ttk.Label(self, text="用户名:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        self.username_entry = ttk.Entry(self, width=25); self.username_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Label(self, text="密  码:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        self.password_entry = ttk.Entry(self, show="*", width=25); self.password_entry.grid(row=1, column=1, padx=10, pady=10)

        button_frame = ttk.Frame(self); button_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(button_frame, text="登录", command=self._login).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="退出", command=self._on_closing).pack(side=tk.LEFT, padx=10)

        self.username_entry.focus_set()
        self.update_idletasks()
        # parent_x = parent.winfo_rootx(); parent_y = parent.winfo_rooty()
        # parent_width = parent.winfo_width(); parent_height = parent.winfo_height()
        # self_width = self.winfo_width(); self_height = self.winfo_height()
        # x = parent_x + (parent_width // 2) - (self_width // 2)
        # y = parent_y + (parent_height // 2) - (self_height // 2)
        # self.geometry(f"+{x}+{y}")
        # 在 LoginWindow 的 __init__ 方法末尾

        self.lift() # 将窗口提升到顶层
        self.focus_force() # 强制设置焦点
        print("DEBUG: Exiting LoginWindow.__init__.")

    def _login(self):
        """处理登录逻辑"""
        print("DEBUG: Entering LoginWindow._login...") # 添加调试打印
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
                print(f"DEBUG: Login successful for user: {username}") # 添加调试打印
                messagebox.showinfo("登录成功", f"欢迎回来, {username}!", parent=self)
                self.destroy()
                self.app.on_login_success(user_row["id"], user_row["username"], user_row["remaining_uses"])
            else:
                print(f"DEBUG: Login failed for user: {username}") # 添加调试打印
                messagebox.showerror("登录失败", "用户名或密码错误。", parent=self)
        except MySQLError as e: messagebox.showerror("数据库错误", f"登录查询出错: {e}", parent=self); print(f"DEBUG: DB error during login: {e}")
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()
            print("DEBUG: Exiting LoginWindow._login.") # 添加调试打印

    def _on_closing(self):
        """处理窗口关闭事件 (点击 X 或退出按钮)"""
        print("DEBUG: Entering LoginWindow._on_closing...") # 添加调试打印
        # 直接退出，不再询问
        self.destroy()
        self.parent.destroy() # 关闭主应用程序窗口
        print("DEBUG: Exiting LoginWindow._on_closing.") # 添加调试打印

# --- 程序主入口 ---
if __name__ == "__main__":
    print("DEBUG: Script starting...") # 添加调试打印
    # 1. 测试数据库连接
    if not test_database_connection():
        print("DEBUG: Database connection failed, exiting.") # 添加调试打印
        sys.exit(1) # 连接失败则退出
    print("DEBUG: Database connection successful.") # 添加调试打印

    # 2. 创建 Tkinter 主窗口 (初始隐藏)
    print("DEBUG: Creating Tk root window...") # 添加调试打印
    root = tk.Tk()
    print("DEBUG: Tk root window created.") # 添加调试打印

    # 3. 实例化应用程序类 (这会触发登录窗口)
    print("DEBUG: Instantiating SmsApp...") # 添加调试打印
    app = SmsApp(root)
    print("DEBUG: SmsApp instantiated.") # 添加调试打印

    # 4. 进入 Tkinter 事件循环
    print("DEBUG: Starting Tk mainloop...") # 添加调试打印
    root.mainloop()
    print("DEBUG: Tk mainloop finished.") # 添加调试打印 (正常退出时才会看到)
