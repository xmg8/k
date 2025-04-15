import requests
import time
from urllib.parse import urlencode
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog, Toplevel
import threading
import sys
import ssl
import mysql.connector # Import MySQL connector
from mysql.connector import Error as MySQLError # Import specific MySQL error
from werkzeug.security import generate_password_hash, check_password_hash

# --- MySQL Database Configuration ---
# !!! 重要安全提示 !!!
# !!! 不要在生产环境中硬编码密码 !!!
# !!! 考虑使用环境变量、配置文件或更安全的凭证管理方法 !!!
MYSQL_HOST = "152.136.171.223"  # 替换为你的 MySQL 服务器地址 (e.g., "localhost", "192.168.1.100")
MYSQL_USER = "wxxmg888" # 替换为你的 MySQL 用户名
MYSQL_PASSWORD = "xmg888.top" # 替换为你的 MySQL 密码
MYSQL_DATABASE = "wxxmg888" # 替换为你的数据库名称

# --- 好猪码 API 配置 (保持不变) ---
API_ACCOUNT = "011474da7ce8c4d4fe58ad3eb95595fba150872eaf35cc85d692b2b209ac61c3"
API_PASSWORD = "2128c8ba18eba394cbfb99c6c906a9b5199d9f94cd825fbcd30c41a0745281e3"
PROJECT_ID = "78478"
SERVERS = [
    "https://api.haozhuma.com",
    "https://api.haozhuma.cn",
    "https://api.haozhuyun.com",
    "https://api.haozhuyun.cn"
]
TOKEN_EXPIRED_ERROR_CODE = "E0008"

# --- 路径处理 ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(application_path, "token.txt")
# DATABASE_FILE 不再需要

# --- API 请求头 ---
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

# --- 数据库连接测试 ---
def test_database_connection():
    """测试到 MySQL 数据库的连接"""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        if conn.is_connected():
            print("MySQL 数据库连接成功。") # 可以改为日志
            conn.close()
            return True
    except MySQLError as e:
        print(f"MySQL 数据库连接错误: {e}")
        messagebox.showerror("数据库连接错误", f"无法连接到 MySQL 数据库: {e}\n请检查配置或联系管理员。")
        return False

# --- GUI 应用主类 ---
class SmsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("无尽冬日接码工具 - 未登录")
        self.root.geometry("600x480")
        self.root.withdraw()

        # 实例变量
        self.token = None
        self.phone_number = None
        self.server = None
        self.is_working = False
        self.auto_fetch_job = None
        self.logged_in_user_id = None
        self.logged_in_username = None
        self.remaining_uses = 0

        self._create_main_widgets()
        self.show_login_register_window()

    def _create_main_widgets(self):
        """创建主应用程序窗口的控件"""
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(pady=10, padx=10, fill=tk.X)
        control_frame.columnconfigure(1, weight=1)

        ttk.Label(control_frame, text="剩余次数:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.uses_var = tk.StringVar(value="--")
        self.uses_label = ttk.Label(control_frame, textvariable=self.uses_var, width=15, anchor=tk.W)
        self.uses_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(control_frame, text="当前用户:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)
        self.username_var = tk.StringVar(value="未登录")
        self.username_label = ttk.Label(control_frame, textvariable=self.username_var, anchor=tk.E)
        self.username_label.grid(row=0, column=3, padx=5, pady=5, sticky=tk.E)

        ttk.Label(control_frame, text="手机号码:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.phone_var = tk.StringVar(value="尚未获取")
        self.phone_entry = ttk.Entry(control_frame, textvariable=self.phone_var, state='readonly', width=20)
        self.phone_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(control_frame, text="验证码:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.code_var = tk.StringVar(value="尚未获取")
        self.code_entry = ttk.Entry(control_frame, textvariable=self.code_var, state='readonly', width=20)
        self.code_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        self.get_phone_btn = ttk.Button(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=15, state=tk.DISABLED)
        self.get_phone_btn.grid(row=1, column=2, padx=(10,5), pady=5, sticky=tk.E)
        self.copy_phone_btn = ttk.Button(control_frame, text="复制手机号码", command=self.copy_phone, width=15, state=tk.DISABLED)
        self.copy_phone_btn.grid(row=1, column=3, padx=5, pady=5, sticky=tk.E)
        self.copy_code_btn = ttk.Button(control_frame, text="复制验证码", command=self.copy_code, width=15, state=tk.DISABLED)
        self.copy_code_btn.grid(row=2, column=3, padx=5, pady=5, sticky=tk.E)
        self.blacklist_btn = ttk.Button(control_frame, text="拉黑手机号码", command=self.start_blacklist_thread, width=15, state=tk.DISABLED)
        self.blacklist_btn.grid(row=3, column=3, padx=5, pady=10, sticky=tk.E)

        log_frame = ttk.LabelFrame(self.root, text="日志输出", padding="10")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="请先登录.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def show_login_register_window(self):
        LoginRegisterWindow(self.root, self)

    def on_login_success(self, user_id, username, remaining_uses):
        self.logged_in_user_id = user_id
        self.logged_in_username = username
        self.remaining_uses = remaining_uses
        self.root.deiconify()
        self.root.title(f"无尽冬日接码工具 - 用户: {username}")
        self.username_var.set(username)
        self.uses_var.set(str(remaining_uses))
        self.status_var.set("登录成功，正在初始化...")
        self.log_message(f"用户 {username} 登录成功，剩余次数: {remaining_uses}")
        self.start_initial_login_thread()
        self.update_ui_state(False)

    # --- 日志记录与状态更新方法 (保持不变) ---
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

    # --- UI 状态管理 (保持不变) ---
    def update_ui_state(self, working):
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

    # --- 启动后台任务的方法 (保持不变) ---
    def start_initial_login_thread(self):
        self.set_status("正在初始化 API 连接...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True)
        thread.start()
    def start_get_phone_thread(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working:
             if "等待获取验证码" in self.status_var.get(): self.log_message("提示：正在等待10秒后获取验证码...")
             else: self.log_message("错误：请等待当前操作完成。")
             return
        if self.remaining_uses <= 0: messagebox.showerror("次数不足", "您的剩余使用次数不足。"); self.log_message("错误：剩余使用次数不足。"); return
        if not self.token or not self.server: self.log_message("错误：API 未初始化。"); messagebox.showerror("错误", "API 连接未就绪。"); return
        if self.auto_fetch_job:
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None
        self.update_ui_state(True)
        self.phone_var.set("正在获取...")
        self.code_var.set("尚未获取")
        self.log_message(f"开始获取手机号 (剩余次数: {self.remaining_uses})...")
        thread = threading.Thread(target=self._get_phone_task, daemon=True)
        thread.start()
    def start_automatic_code_fetch(self):
        self.auto_fetch_job = None
        if not self.phone_number: self.log_message("错误：手机号丢失..."); self.update_ui_state(False); return
        if not self.logged_in_user_id: return
        self.is_working = True
        self.set_status("正在获取验证码...")
        self.code_var.set("正在获取...")
        self.update_ui_state(True)
        self.log_message(f"开始为号码 {self.phone_number} 自动获取验证码...")
        thread = threading.Thread(target=self._get_code_task_automatic, daemon=True)
        thread.start()
    def start_blacklist_thread(self):
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working:
             if "等待获取验证码" in self.status_var.get(): self.log_message("提示：正在等待10秒后获取验证码...")
             else: self.log_message("错误：请等待当前操作完成。")
             return
        if not self.phone_number: messagebox.showerror("错误", "没有可用的手机号码。"); return
        if self.auto_fetch_job:
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None; self.log_message("已取消等待获取验证码。"); self.set_status("就绪.")
        if messagebox.askyesno("确认", f"确定要拉黑号码 {self.phone_number} 吗？"):
            self.update_ui_state(True)
            self.log_message(f"尝试拉黑号码: {self.phone_number}")
            thread = threading.Thread(target=self._blacklist_task, daemon=True)
            thread.start()
        else: self.log_message("拉黑操作已取消。")

    # --- 后台任务方法 (保持不变, 除了 _get_code_task_automatic 调用扣减次数) ---
    def _initial_login_task(self):
        try:
            if not self.read_token():
                try: self.try_login()
                except Exception as e:
                    self.log_message(f"初始化 API 连接失败: {e}")
                    self.root.after(0, lambda: messagebox.showwarning("API 错误", f"无法连接或登录好猪码服务: {e}"))
                    self.set_status("API 连接失败...")
                    return
            self.log_message("API 连接初始化成功。")
            self.root.after(0, self.update_ui_state, False)
        except Exception as e: self.log_message(f"初始化 API 连接过程中发生未知错误: {e}"); self.set_status("API 初始化异常。")
    def _get_phone_task(self):
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
    def _get_code_task_automatic(self):
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
    def _blacklist_task(self):
        try:
            success = self.blacklist_phone()
            if not success: self.log_message("手动拉黑手机号失败。")
        except Exception as e: self.log_message(f"手动拉黑手机号时发生异常: {e}")
        finally: self.root.after(0, self.update_ui_state, False)
    def restart_process_after_timeout(self):
        try:
            self.log_message("验证码超时，自动重新开始获取手机号...")
            self.phone_var.set("重新获取...")
            self.code_var.set("尚未获取")
            self.is_working = False
            self.update_ui_state(False)
            self.root.after(50, self.start_get_phone_thread)
        except tk.TclError: self.log_message("错误：窗口已关闭，无法重启流程。")

    # --- 数据库交互方法 (使用 MySQL) ---
    def _get_db_connection(self):
        """获取 MySQL 数据库连接"""
        try:
            # 尝试连接数据库
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            if conn.is_connected():
                return conn
            else:
                self.log_message("无法连接到 MySQL 数据库。")
                messagebox.showerror("数据库错误", "无法连接到用户数据库。")
                return None
        except MySQLError as e:
            self.log_message(f"MySQL 连接错误: {e}")
            messagebox.showerror("数据库错误", f"无法连接到用户数据库: {e}")
            return None

    def _decrement_usage(self):
        """在 MySQL 数据库中将当前用户的剩余次数减 1"""
        if not self.logged_in_user_id: return
        conn = self._get_db_connection()
        if not conn: return
        cursor = None
        try:
            cursor = conn.cursor()
            # 使用 GREATEST 防止减成负数
            sql = "UPDATE users SET remaining_uses = GREATEST(0, remaining_uses - 1) WHERE id = %s"
            cursor.execute(sql, (self.logged_in_user_id,))
            conn.commit() # 提交事务

            # 更新内存和 UI
            if self.remaining_uses > 0: self.remaining_uses -= 1
            self.log_message(f"使用次数已扣减，剩余: {self.remaining_uses}")
            self.root.after(0, lambda: self.uses_var.set(str(self.remaining_uses)))
            self.root.after(0, self.update_ui_state, False) # 更新按钮状态

        except MySQLError as e:
            self.log_message(f"扣减使用次数时 MySQL 错误: {e}")
            messagebox.showerror("数据库错误", f"无法更新使用次数: {e}")
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    # --- API 交互方法 (好猪码部分，保持不变) ---
    def read_token(self):
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f: read_token = f.read().strip()
                if read_token:
                    for s in SERVERS:
                        try:
                            url = f"{s}/sms/?api=getSummary&token={read_token}"
                            response = requests.get(url, headers=headers, timeout=10, verify=True)
                            response.raise_for_status(); data = response.json()
                            if data.get("code") == 0 or str(data.get("code")) == "0": self.server = s; self.token = read_token; return True
                        except requests.exceptions.SSLError as ssl_err: self.log_message(f"验证令牌时SSL错误 ({s}): {ssl_err}")
                        except requests.exceptions.RequestException: pass
                    self.token = None; self.server = None; return False
            except Exception as e: self.log_message(f"读取令牌文件时出错: {e}")
        return False
    def save_token(self):
        if not self.token: return
        try:
            with open(TOKEN_FILE, 'w') as f: f.write(self.token)
        except Exception as e: self.log_message(f"保存令牌到文件时出错: {e}")
    def try_login(self):
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                response = requests.get(login_url, headers=headers, timeout=15, verify=True)
                response.raise_for_status(); data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0": self.server = s; self.token = data["token"]; self.save_token(); return
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"登录好猪码时SSL错误 ({s}): {ssl_err}")
            except requests.exceptions.Timeout: pass
            except requests.exceptions.RequestException: pass
            except Exception as e: self.log_message(f"处理好猪码服务器 {s} 响应时发生未知错误: {e}")
        self.server = None; self.token = None; raise Exception("所有好猪码服务器登录尝试均失败")
    def handle_api_error(self, data, operation_name):
        error_code = data.get("code"); error_msg = data.get('msg', '未知错误')
        is_waiting_msg = "尚未接收" in error_msg or "等待" == error_msg or "没有可用" in error_msg
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE: self.log_message("好猪码令牌过期或无效..."); self.token = None
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg: self.log_message(f"好猪码API-{operation_name}失败: {error_code}, {error_msg}")
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            try: self.try_login(); return True
            except Exception as e: self.log_message(f"重新登录好猪码失败: {e}"); self.root.after(0, lambda: messagebox.showwarning("API 错误", f"好猪码令牌过期后无法重新登录: {e}")); return False
        return False
    def get_balance(self): # 不再核心使用
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
                    if phone: self.phone_number = phone; self.root.after(0, lambda: self.code_var.set("尚未获取")); self.log_message(f"成功获取手机号: {self.phone_number}"); return self.phone_number
                    else: self.log_message("API响应成功但未包含手机号..."); time.sleep(retry_delay); continue
                elif str(code) == "-1" and ("没有可用手机号" in msg or "请稍后再试" in msg or "等待" == msg): self.log_message(f"暂时无号或需等待({msg})...", retry_delay); time.sleep(retry_delay); continue
                else:
                    if self.handle_api_error(data, "获取手机号"): url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"; self.log_message("好猪码令牌已更新..."); continue
                    else: self.log_message("获取手机号API错误..."); self.phone_number = None; return None
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"获取手机号SSL错误: {ssl_err}..."); time.sleep(5); continue
            except requests.exceptions.Timeout: self.log_message("获取手机号超时..."); time.sleep(5); continue
            except requests.exceptions.RequestException as e: self.log_message(f"获取手机号网络错误: {e}..."); self.phone_number = None; return None
            except Exception as e: self.log_message(f"获取手机号未知异常: {e}..."); self.phone_number = None; return None
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
                    else: return None
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"获取验证码轮询SSL错误: {ssl_err}...")
            except requests.exceptions.Timeout: self.log_message("获取验证码轮询超时...")
            except requests.exceptions.RequestException as e: self.log_message(f"获取验证码轮询网络错误: {e}...")
            except Exception as e: self.log_message(f"获取验证码轮询未知异常: {e}")
            time.sleep(polling_interval)
        return None # Timeout
    def blacklist_phone(self):
        if not self.token or not self.server or not self.phone_number: return False
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0": self.log_message(f"手机号码 {self.phone_number} 已成功拉黑。"); self.root.after(0, self.clear_phone_details); return True
            else:
                if self.handle_api_error(data, "拉黑手机号"): return self.blacklist_phone()
                self.log_message(f"API拉黑失败: {data.get('msg', '未知错误')}"); return False
        except requests.exceptions.SSLError as ssl_err: self.log_message(f"拉黑手机号时SSL错误: {ssl_err}")
        except requests.exceptions.RequestException as e: self.log_message(f"拉黑手机号网络异常: {e}")
        except Exception as e: self.log_message(f"拉黑手机号未知异常: {e}")
        return False

    # --- GUI 辅助方法 (保持不变) ---
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

# --- 登录/注册窗口类 (使用 MySQL) ---
class LoginRegisterWindow(Toplevel):
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.parent = parent
        self.app = app_instance
        self.title("登录或注册")
        self.geometry("300x200")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.grab_set(); self.transient(parent)

        ttk.Label(self, text="用户名:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        self.username_entry = ttk.Entry(self, width=25); self.username_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Label(self, text="密  码:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        self.password_entry = ttk.Entry(self, show="*", width=25); self.password_entry.grid(row=1, column=1, padx=10, pady=10)
        button_frame = ttk.Frame(self); button_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(button_frame, text="登录", command=self._login).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="注册", command=self._register).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="退出", command=self._on_closing).pack(side=tk.LEFT, padx=10)
        self.username_entry.focus_set()
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _login(self):
        username = self.username_entry.get().strip(); password = self.password_entry.get()
        if not username or not password: messagebox.showwarning("输入错误", "用户名和密码不能为空。", parent=self); return

        conn = self.app._get_db_connection(); cursor = None
        if not conn: return
        try:
            # 使用字典 cursor 获取结果
            cursor = conn.cursor(dictionary=True)
            sql = "SELECT id, username, password_hash, remaining_uses FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user_row = cursor.fetchone()

            if user_row and check_password_hash(user_row["password_hash"], password):
                messagebox.showinfo("登录成功", f"欢迎回来, {username}!", parent=self)
                self.destroy()
                self.app.on_login_success(user_row["id"], user_row["username"], user_row["remaining_uses"])
            else:
                messagebox.showerror("登录失败", "用户名或密码错误。", parent=self)
        except MySQLError as e: messagebox.showerror("数据库错误", f"登录查询出错: {e}", parent=self)
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    def _register(self):
        username = self.username_entry.get().strip(); password = self.password_entry.get()
        if not username or not password: messagebox.showwarning("输入错误", "用户名和密码不能为空。", parent=self); return
        if len(password) < 6: messagebox.showwarning("密码太短", "密码长度至少需要6位。", parent=self); return

        password_h = generate_password_hash(password); initial_uses = 5 # 新用户初始次数
        conn = self.app._get_db_connection(); cursor = None
        if not conn: return
        try:
            cursor = conn.cursor()
            sql = "INSERT INTO users (username, password_hash, remaining_uses) VALUES (%s, %s, %s)"
            cursor.execute(sql, (username, password_h, initial_uses))
            conn.commit()
            messagebox.showinfo("注册成功", f"用户 {username} 注册成功！初始次数: {initial_uses}。请现在登录。", parent=self)
            self.username_entry.delete(0, tk.END); self.password_entry.delete(0, tk.END); self.username_entry.focus_set()
        except MySQLError as e:
            # 检查是否是唯一约束冲突错误 (MySQL error code 1062)
            if e.errno == 1062: messagebox.showerror("注册失败", "该用户名已被注册。", parent=self)
            else: messagebox.showerror("数据库错误", f"注册时写入数据库出错: {e}", parent=self)
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    def _on_closing(self):
        if messagebox.askokcancel("退出", "确定要退出程序吗？", parent=self):
            self.destroy(); self.parent.destroy()

# --- 程序主入口 ---
if __name__ == "__main__":
    # 1. 测试数据库连接
    if not test_database_connection():
        sys.exit(1) # 连接失败则退出

    # 2. 创建 Tkinter 主窗口 (初始隐藏)
    root = tk.Tk()
    # 3. 实例化应用程序类 (会触发登录窗口)
    app = SmsApp(root)
    # 4. 进入 Tkinter 事件循环
    root.mainloop()
