import requests
import time
from urllib.parse import urlencode
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
import ssl

# --- 配置项 ---
API_ACCOUNT = "011474da7ce8c4d4fe58ad3eb95595fba150872eaf35cc85d692b2b209ac61c3"
API_PASSWORD = "2128c8ba18eba394cbfb99c6c906a9b5199d9f94cd825fbcd30c41a0745281e3"
PROJECT_ID = "78478"
SERVERS = [
    "https://api.haozhuma.com",
    "https://api.haozhuma.cn",
    "https://api.haozhuyun.com",
    "https://api.haozhuyun.cn"
]
# 令牌过期错误码 (需要根据实际 API 文档替换)
TOKEN_EXPIRED_ERROR_CODE = "E0008" # 示例值

# --- 路径处理 (用于打包后定位 token.txt) ---
if getattr(sys, 'frozen', False):
    # 如果是打包后的 exe 文件
    application_path = os.path.dirname(sys.executable)
else:
    # 如果是直接运行 .py 文件
    application_path = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(application_path, "token.txt")

# --- API 请求头 ---
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

# --- GUI 应用主类 ---
class SmsApp:
    def __init__(self, root):
        """初始化应用程序窗口和变量"""
        self.root = root
        self.root.title("无尽冬日接码工具")
        self.root.geometry("600x480") # 设置窗口初始大小

        # 实例变量
        self.token = None           # API 访问令牌
        self.phone_number = None    # 当前获取到的手机号
        self.server = None          # 当前使用的 API 服务器地址
        self.is_working = False     # 标记是否有后台任务正在运行
        self.auto_fetch_job = None  # 用于存储 Tkinter 的 after 任务 ID，以便取消

        # --- 创建 GUI 元素 ---
        # 主控制框架
        control_frame = ttk.Frame(root, padding="10")
        control_frame.pack(pady=10, padx=10, fill=tk.X)
        control_frame.columnconfigure(1, weight=1) # 让第二列（显示信息）可以适当扩展

        # 账户余额显示
        ttk.Label(control_frame, text="账户余额:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.balance_var = tk.StringVar(value="未知")
        self.balance_label = ttk.Label(control_frame, textvariable=self.balance_var, width=15, anchor=tk.W)
        self.balance_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

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

        # 功能按钮
        self.get_phone_btn = ttk.Button(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=15)
        self.get_phone_btn.grid(row=1, column=2, padx=(10,5), pady=5, sticky=tk.E)

        self.copy_phone_btn = ttk.Button(control_frame, text="复制手机号码", command=self.copy_phone, width=15)
        self.copy_phone_btn.grid(row=1, column=3, padx=5, pady=5, sticky=tk.E)
        self.copy_phone_btn.config(state=tk.DISABLED) # 初始禁用

        self.copy_code_btn = ttk.Button(control_frame, text="复制验证码", command=self.copy_code, width=15)
        self.copy_code_btn.grid(row=2, column=3, padx=5, pady=5, sticky=tk.E)
        self.copy_code_btn.config(state=tk.DISABLED) # 初始禁用

        self.blacklist_btn = ttk.Button(control_frame, text="拉黑手机号码", command=self.start_blacklist_thread, width=15)
        self.blacklist_btn.grid(row=3, column=3, padx=5, pady=10, sticky=tk.E)
        self.blacklist_btn.config(state=tk.DISABLED) # 初始禁用

        # 日志输出区域
        log_frame = ttk.LabelFrame(root, text="日志输出", padding="10")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED) # 初始禁用写入
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪.")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # --- 初始化操作 ---
        self.log_message("应用程序启动...")
        self.start_initial_login_thread() # 尝试自动登录或读取令牌

    # --- 日志记录与状态更新方法 ---
    def log_message(self, message):
        """安全地向日志区域添加消息 (主线程调用)"""
        if self.root: # 检查窗口是否存在
            self.root.after(0, self._append_log, message) # 安排在主线程执行

    def _append_log(self, message):
        """内部方法，实际更新日志文本框 (必须在主线程运行)"""
        try:
            self.log_text.config(state=tk.NORMAL) # 允许写入
            self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
            self.log_text.see(tk.END) # 滚动到底部
            self.log_text.config(state=tk.DISABLED) # 禁止写入
        except tk.TclError:
            # 如果窗口在更新时被关闭，会引发 TclError，忽略它
            pass

    def set_status(self, message):
        """安全地更新状态栏文本 (主线程调用)"""
        if self.root:
             try:
                 # 安排在主线程更新 StringVar
                 self.root.after(0, self.status_var.set, message)
             except tk.TclError:
                 pass # 忽略窗口关闭时的错误

    # --- UI 状态管理 ---
    def update_ui_state(self, working):
        """根据工作状态启用/禁用 GUI 元素"""
        self.is_working = working
        # 默认状态：如果正在工作，则禁用；否则启用
        default_state = tk.DISABLED if working else tk.NORMAL
        # 检查手机号是否有效
        phone_available = bool(self.phone_number)
        # 检查验证码是否有效（非初始/错误状态）
        code_val = self.code_var.get()
        code_available = code_val and code_val not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]

        try:
            # 获取手机号按钮：只有不在工作时可用
            self.get_phone_btn.config(state=default_state)
            # 拉黑按钮：不在工作且有手机号时可用
            blacklist_state = tk.DISABLED if working or not phone_available else tk.NORMAL
            self.blacklist_btn.config(state=blacklist_state)
            # 复制手机号按钮：有手机号时可用（不受working影响，方便复制）
            copy_phone_state = tk.DISABLED if not phone_available else tk.NORMAL
            self.copy_phone_btn.config(state=copy_phone_state)
            # 复制验证码按钮：不在工作且有有效验证码时可用
            copy_code_state = tk.DISABLED if working or not code_available else tk.NORMAL
            self.copy_code_btn.config(state=copy_code_state)

            # 更新状态栏文本
            current_status = self.status_var.get()
            if working:
                # 如果状态已经是等待验证码，则不覆盖
                if "等待获取验证码" not in current_status:
                    self.set_status("正在处理...")
            # 如果不在工作，且状态不是等待验证码，则设为就绪
            elif "等待获取验证码" not in current_status:
                 self.set_status("就绪.")
        except tk.TclError:
             pass # 忽略窗口关闭时的UI更新错误

    # --- 启动后台任务的方法 ---
    def start_initial_login_thread(self):
        """启动初始化登录/令牌读取的后台线程"""
        self.set_status("正在初始化...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True)
        thread.start()

    def start_get_phone_thread(self):
        """启动获取手机号流程（包括查余额）的后台线程"""
        # 检查是否已经在工作（避免重复点击）
        if self.is_working:
             # 如果只是在等待10秒倒计时，给用户提示
             if "等待获取验证码" in self.status_var.get():
                 self.log_message("提示：正在等待10秒后获取验证码，请勿重复点击。")
             else:
                 self.log_message("错误：请等待当前操作完成。")
             return

        # 检查是否已登录
        if not self.token or not self.server:
             self.log_message("错误：无法获取手机号，请先确保登录成功。")
             # 弹出错误对话框
             messagebox.showerror("错误", "未登录或服务器无效，请重启应用或检查网络。")
             return

        # 如果存在等待验证码的计划任务，取消它
        if self.auto_fetch_job:
            try:
                self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass # 忽略窗口关闭错误
            self.auto_fetch_job = None

        # 设置为工作状态，更新UI
        self.update_ui_state(True)
        self.phone_var.set("正在获取...")
        self.code_var.set("尚未获取") # 重置验证码状态
        self.balance_var.set("查询中...")
        self.log_message("开始查询余额并获取手机号...")

        # 创建并启动后台线程
        thread = threading.Thread(target=self._get_phone_task, daemon=True)
        thread.start()

    def start_automatic_code_fetch(self):
        """在10秒延迟后，启动自动获取验证码的后台线程"""
        self.auto_fetch_job = None # 清除计划任务ID

        # 再次检查手机号是否仍然有效
        if not self.phone_number:
            self.log_message("错误：手机号在等待期间丢失，无法获取验证码。")
            self.update_ui_state(False) # 释放工作状态
            return

        # 设置为工作状态（验证码获取阶段）
        self.is_working = True
        self.set_status("正在获取验证码...")
        self.code_var.set("正在获取...")
        self.update_ui_state(True) # 禁用相关按钮
        self.log_message(f"开始为号码 {self.phone_number} 自动获取验证码...")

        # 创建并启动验证码获取线程
        thread = threading.Thread(target=self._get_code_task_automatic, daemon=True)
        thread.start()

    def start_blacklist_thread(self):
        """启动手动拉黑手机号的后台线程"""
        # 检查是否正在工作
        if self.is_working:
             if "等待获取验证码" in self.status_var.get():
                 self.log_message("提示：正在等待10秒后获取验证码，请勿重复点击。")
             else:
                 self.log_message("错误：请等待当前操作完成。")
             return

        # 检查是否有手机号可拉黑
        if not self.phone_number:
            self.log_message("错误：没有手机号码可以拉黑。")
            messagebox.showerror("错误", "没有可用的手机号码。")
            return

        # 如果正在等待验证码，取消等待
        if self.auto_fetch_job:
            try:
                self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None
            self.log_message("已取消等待获取验证码。")
            self.set_status("就绪.") # 重置状态

        # 弹出确认对话框
        if messagebox.askyesno("确认", f"确定要拉黑号码 {self.phone_number} 吗？"):
            self.update_ui_state(True) # 设置为工作状态
            self.log_message(f"尝试拉黑号码: {self.phone_number}")
            # 创建并启动拉黑线程
            thread = threading.Thread(target=self._blacklist_task, daemon=True)
            thread.start()
        else:
            self.log_message("拉黑操作已取消。")

    # --- 后台任务方法 (在独立线程中运行) ---
    def _initial_login_task(self):
        """后台执行初始化登录或读取令牌"""
        try:
            if not self.read_token(): # 尝试读取本地令牌
                try:
                    self.try_login() # 如果读取失败，尝试使用账号密码登录
                except Exception as e:
                    self.log_message(f"初始化登录失败: {e}")
                    # 在主线程中弹出错误提示
                    self.root.after(0, lambda: messagebox.showerror("登录失败", f"无法登录或连接服务器: {e}"))
            else:
                 self.log_message("使用已保存的令牌成功初始化。")
        except Exception as e:
             # 捕获其他可能的初始化错误
             self.log_message(f"初始化过程中发生未知错误: {e}")
        finally:
             # 无论成功失败，都更新状态栏
             self.set_status("初始化完成.")

    def _get_phone_task(self):
        """后台获取余额和手机号，成功后安排验证码获取"""
        phone_obtained = False # 标记是否成功获取手机号
        try:
            # 1. 获取余额
            balance = self.get_balance()
            if balance is not None:
                # 在主线程更新余额显示
                self.root.after(0, lambda b=balance: self.balance_var.set(f"{b} 元"))
            else:
                self.root.after(0, self.balance_var.set, "查询失败")
                self.log_message("警告：查询余额失败，但仍尝试获取手机号。")

            # 2. 获取手机号 (会持续尝试)
            phone = self.get_phone_number()
            if phone:
                phone_obtained = True
                # 在主线程更新手机号显示
                self.root.after(0, lambda p=phone: self.phone_var.set(p))
                # 立刻更新按钮状态，使复制/拉黑可用
                self.root.after(0, self.update_ui_state, False)

                # 安排 10 秒后开始获取验证码
                self.log_message("手机号获取成功，将在 10 秒后开始获取验证码...")
                self.set_status("等待获取验证码 (10s)...")
                try:
                    # 使用 after 安排任务在主线程的事件循环中执行
                    self.auto_fetch_job = self.root.after(10000, self.start_automatic_code_fetch)
                except tk.TclError:
                    # 如果窗口在安排任务时关闭
                    self.log_message("错误：窗口已关闭，无法安排验证码获取。")
                    phone_obtained = False # 标记为失败，以便 finally 块释放状态
            else:
                # get_phone_number 返回 None，表示遇到无法恢复的错误
                self.root.after(0, lambda: self.phone_var.set("获取失败"))
                self.log_message("获取手机号失败 (无法恢复的错误)。")

        except Exception as e:
            # 捕获此任务中的其他异常
            self.root.after(0, lambda: self.phone_var.set("获取异常"))
            self.log_message(f"获取手机号或余额时发生异常: {e}")
            self.root.after(0, self.balance_var.set, "查询异常")
        finally:
            # 只有在获取手机号彻底失败时才释放工作状态
            # 如果成功获取，工作状态将由验证码获取流程管理
            if not phone_obtained:
                self.root.after(0, self.update_ui_state, False)

    def _get_code_task_automatic(self):
        """后台自动获取验证码，处理超时和重启"""
        code = None
        restart_needed = False # 标记是否需要重启流程
        try:
            # 调用等待验证码函数，设置超时时间
            code = self.wait_for_verification_code(timeout=200)

            if code:
                # 成功获取验证码
                self.root.after(0, lambda c=code: self.code_var.set(c))
                # 更新UI状态，启用复制验证码按钮，标记工作结束
                self.root.after(0, self.update_ui_state, False)
            else:
                # wait_for_verification_code 返回 None，表示超时
                self.log_message("验证码获取超时 (200秒)。")
                self.root.after(0, lambda: self.code_var.set("获取超时"))
                # 尝试自动拉黑并重启
                if self.phone_number:
                    self.log_message(f"自动拉黑号码: {self.phone_number}")
                    # 同步调用拉黑，确保拉黑完成后再决定是否重启
                    blacklist_success = self.blacklist_phone()
                    if blacklist_success:
                        restart_needed = True
                        # 安排重启任务在主线程执行
                        self.root.after(0, self.restart_process_after_timeout)
                    else:
                        self.log_message("拉黑失败，无法自动重启流程。")
                else:
                     self.log_message("无号码可拉黑，无法自动重启流程。")
        except Exception as e:
            # 捕获此任务中的其他异常
            self.root.after(0, lambda: self.code_var.set("获取异常"))
            self.log_message(f"自动获取验证码时发生异常: {e}")
        finally:
            # 只有在不需要重启流程时，才将工作状态设为 False
            if not restart_needed:
                 self.root.after(0, self.update_ui_state, False)

    def _blacklist_task(self):
        """后台执行手动拉黑操作"""
        try:
            success = self.blacklist_phone()
            if not success:
                 self.log_message("手动拉黑手机号失败。")
        except Exception as e:
            self.log_message(f"手动拉黑手机号时发生异常: {e}")
        finally:
            # 手动拉黑操作完成后，总是释放工作状态
            self.root.after(0, self.update_ui_state, False)

    def restart_process_after_timeout(self):
        """在主线程中安全地重启获取手机号的流程"""
        try:
            self.log_message("验证码超时，自动重新开始获取手机号...")
            # 更新界面提示
            self.phone_var.set("重新获取...")
            self.code_var.set("尚未获取")
            # 确保状态已重置为非工作
            self.is_working = False
            self.update_ui_state(False)
            # 稍微延迟后启动获取流程，避免潜在冲突
            self.root.after(50, self.start_get_phone_thread)
        except tk.TclError:
             self.log_message("错误：窗口已关闭，无法重启流程。")

    # --- API 交互方法 ---
    def read_token(self):
        """从文件读取并验证令牌"""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f:
                    read_token = f.read().strip()
                if read_token:
                    # 尝试用令牌访问第一个服务器的 getSummary 接口验证有效性
                    for s in SERVERS:
                        try:
                            url = f"{s}/sms/?api=getSummary&token={read_token}"
                            response = requests.get(url, headers=headers, timeout=10, verify=True)
                            response.raise_for_status() # 检查 HTTP 错误
                            data = response.json()
                            # 检查 API 返回码是否表示成功
                            if data.get("code") == 0 or str(data.get("code")) == "0":
                                self.server = s # 记录可用的服务器
                                self.token = read_token # 存储有效的令牌
                                return True # 验证成功
                        except requests.exceptions.SSLError as ssl_err:
                             # 记录 SSL 错误，但继续尝试下一个服务器
                             self.log_message(f"验证令牌时SSL错误 ({s}): {ssl_err}")
                        except requests.exceptions.RequestException:
                             # 忽略其他连接错误，尝试下一个服务器
                             pass
                    # 如果所有服务器都验证失败
                    self.token = None
                    self.server = None
                    return False
            except Exception as e:
                # 文件读取或其他异常
                self.log_message(f"读取令牌文件时出错: {e}")
        return False # 文件不存在或读取失败

    def save_token(self):
        """将当前令牌保存到文件"""
        if not self.token: return # 没有令牌则不保存
        try:
            with open(TOKEN_FILE, 'w') as f:
                f.write(self.token)
        except Exception as e:
            self.log_message(f"保存令牌到文件时出错: {e}")

    def try_login(self):
        """使用账号密码尝试登录所有服务器，直到成功"""
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                response = requests.get(login_url, headers=headers, timeout=15, verify=True)
                response.raise_for_status()
                data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0":
                    # 登录成功
                    self.server = s # 记录服务器
                    self.token = data["token"] # 存储令牌
                    self.save_token() # 保存令牌到文件
                    return # 成功登录后退出循环
            except requests.exceptions.SSLError as ssl_err:
                 self.log_message(f"登录时SSL错误 ({s}): {ssl_err}")
            except requests.exceptions.Timeout:
                 pass # 超时则尝试下一个服务器
            except requests.exceptions.RequestException:
                 pass # 其他连接错误也尝试下一个
            except Exception as e:
                 # JSON 解析错误或其他未知错误
                 self.log_message(f"处理服务器 {s} 响应时发生未知错误: {e}")
        # 如果循环结束仍未成功登录
        self.server = None
        self.token = None
        raise Exception("所有服务器登录尝试均失败") # 抛出异常

    def handle_api_error(self, data, operation_name):
        """处理 API 返回的错误，特别是令牌过期"""
        error_code = data.get("code")
        error_msg = data.get('msg', '未知错误')

        # 定义哪些消息是正常的等待消息，不应记录为错误
        is_waiting_msg = "尚未接收" in error_msg or "等待" == error_msg or "没有可用" in error_msg

        # 检查是否是令牌过期错误
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
             self.log_message("令牌过期或无效，尝试重新登录...")
             self.token = None # 清除无效令牌
             try:
                 self.try_login() # 尝试重新登录
                 return True # 返回 True 表示已处理（需要调用方重试）
             except Exception as e:
                 self.log_message(f"重新登录失败: {e}")
                 # 在主线程弹出错误提示
                 self.root.after(0, lambda: messagebox.showerror("登录失败", f"令牌过期后无法重新登录: {e}"))
                 return False # 返回 False 表示处理失败
        # 如果不是令牌过期，且不是成功的响应码，且不是等待消息，则记录为操作失败
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg:
             self.log_message(f"{operation_name}失败: 代码={error_code}, 消息={error_msg}")

        # 对于其他错误或等待消息，返回 False 表示不需要特殊处理（如重试）
        return False

    def get_balance(self):
        """获取账户余额"""
        if not self.token or not self.server: return None # 未登录
        url = f"{self.server}/sms/?api=getSummary&token={self.token}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0":
                # 成功获取余额
                return data.get("money", "未知")
            else:
                # 处理可能的 API 错误（如令牌过期）
                if self.handle_api_error(data, "获取余额"):
                    return self.get_balance() # 如果处理成功（重新登录），则重试获取余额
                return None # 如果错误无法处理，返回 None
        except requests.exceptions.SSLError as ssl_err:
             self.log_message(f"获取余额时SSL错误: {ssl_err}")
        except requests.exceptions.RequestException as e:
             # 记录其他网络错误
             self.log_message(f"获取余额网络异常: {e}")
        except Exception as e:
             # 记录未知错误
             self.log_message(f"获取余额未知异常: {e}")
        return None # 出错返回 None

    def get_phone_number(self):
        """持续获取手机号码，直到成功或遇到不可恢复错误"""
        if not self.token or not self.server: return None # 未登录
        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
        retry_delay = 3 # 秒，无号码时的重试间隔
        self.log_message("正在持续获取手机号...")
        while True: # 无限循环尝试
            if not self.token: # 检查令牌是否在循环中失效（例如，handle_api_error 失败）
                self.log_message("获取手机号中断：令牌失效。")
                return None
            try:
                response = requests.get(url, headers=headers, timeout=20, verify=True)
                data = response.json()
                code = data.get("code")
                msg = data.get("msg", "")

                # 1. 检查是否成功获取
                if code == 0 or str(code) == "0":
                    phone = data.get("phone")
                    if phone:
                        # 成功获取
                        self.phone_number = phone
                        # 在主线程重置验证码显示
                        self.root.after(0, lambda: self.code_var.set("尚未获取"))
                        self.log_message(f"成功获取手机号: {self.phone_number}")
                        return self.phone_number # 返回号码，退出循环
                    else:
                        # API 成功但没给号码，视为临时问题，重试
                        self.log_message("API响应成功但未包含手机号，稍后重试...")
                        time.sleep(retry_delay)
                        continue # 继续下一次循环

                # 2. 检查是否是明确的无号码或等待状态
                elif str(code) == "-1" and ("没有可用手机号" in msg or "请稍后再试" in msg or "等待" == msg):
                     self.log_message(f"暂时没有可用手机号或需等待({msg})，{retry_delay}秒后自动重试...")
                     time.sleep(retry_delay)
                     continue # 继续下一次循环

                # 3. 处理其他 API 错误
                else:
                    if self.handle_api_error(data, "获取手机号"):
                        # 令牌已刷新，更新 URL 并立即重试
                        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
                        self.log_message("令牌已更新，立即重试获取手机号...")
                        continue # 继续下一次循环
                    else:
                        # 无法处理的 API 错误或重新登录失败，停止尝试
                        self.log_message("获取手机号时遇到无法恢复的API错误，停止尝试。")
                        self.phone_number = None
                        return None # 退出循环并返回 None

            # 4. 处理网络层面的错误
            except requests.exceptions.SSLError as ssl_err:
                 # SSL 错误也视为可重试
                 self.log_message(f"获取手机号时SSL错误: {ssl_err}，稍后重试...")
                 time.sleep(5) # 等待时间稍长
                 continue # 继续下一次循环
            except requests.exceptions.Timeout:
                 # 超时也重试
                 self.log_message("获取手机号请求超时，稍后重试...")
                 time.sleep(5)
                 continue # 继续下一次循环
            except requests.exceptions.RequestException as e:
                 # 其他网络错误（如连接被拒）视为不可恢复
                 self.log_message(f"获取手机号时发生网络错误: {e}，停止尝试。")
                 self.phone_number = None
                 return None # 退出循环并返回 None
            except Exception as e:
                 # 未知异常也停止
                 self.log_message(f"获取手机号时发生未知异常: {e}，停止尝试。")
                 self.phone_number = None
                 return None # 退出循环并返回 None

    def wait_for_verification_code(self, timeout=200):
        """等待验证码，轮询间隔4秒，超时200秒"""
        if not self.token or not self.server or not self.phone_number: return None # 必要信息缺失
        start_time = time.time()
        polling_interval = 4 # 轮询间隔（秒）

        while time.time() - start_time < timeout: # 在超时时间内循环
            if not self.token: return None # 令牌在等待期间失效

            # 构造请求参数和 URL
            params = {"api": "getMessage", "token": self.token, "sid": PROJECT_ID, "phone": self.phone_number}
            url = f"{self.server}/sms/?{urlencode(params)}"

            try:
                # 发起 GET 请求
                response = requests.get(url, headers=headers, timeout=15, verify=True)
                data = response.json()
                code = data.get("code")
                msg = data.get("msg", "")

                # 1. 检查是否成功获取验证码
                if code == 0 or str(code) == "0":
                    verification_code = data.get("yzm") or msg # 尝试从 yzm 或 msg 获取
                    if verification_code and verification_code != "ok": # 确保不是简单的 "ok"
                        # 基本验证，判断是否像验证码
                        if len(verification_code) > 1 and verification_code.isalnum():
                           self.log_message(f"成功获取验证码: {verification_code}")
                           return verification_code # 返回验证码，退出循环
                        # else: 如果是 "ok" 或不像验证码，继续等待

                # 2. 检查是否是明确的等待消息
                elif "尚未接收到短信" in msg or (code == -1 and msg == "等待"):
                    # 这是预期的等待状态，继续轮询
                    pass # 不做任何事，直接进入 sleep

                # 3. 处理其他 API 错误（包括令牌过期）
                else:
                    if self.handle_api_error(data, "获取验证码"):
                        # 令牌已刷新，更新 URL (以防服务器改变) 并立即继续下一次循环
                        url = f"{self.server}/sms/?{urlencode(params)}"
                        continue
                    else:
                        # 无法处理的 API 错误或重新登录失败，停止等待
                        return None

            # 4. 处理网络层面的错误 (SSL, Timeout, Connection)
            except requests.exceptions.SSLError as ssl_err:
                 self.log_message(f"获取验证码轮询时SSL错误: {ssl_err}，继续轮询...")
            except requests.exceptions.Timeout:
                 self.log_message("获取验证码轮询超时，继续轮询...")
            except requests.exceptions.RequestException as e:
                 self.log_message(f"获取验证码轮询时网络错误: {e}，继续轮询...")
            except Exception as e:
                 # 捕获其他未知异常
                 self.log_message(f"获取验证码轮询未知异常: {e}")

            # 等待指定的轮询间隔
            time.sleep(polling_interval)

        # 如果循环正常结束（未提前 return），说明超时
        return None

    def blacklist_phone(self):
        """将当前手机号加入黑名单，返回 True 表示成功，False 表示失败"""
        if not self.token or not self.server or not self.phone_number: return False # 必要信息缺失
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0":
                # 拉黑成功
                self.log_message(f"手机号码 {self.phone_number} 已成功拉黑。")
                # 在主线程清理 UI 显示
                self.root.after(0, self.clear_phone_details)
                return True # 返回成功
            else:
                # 处理可能的 API 错误
                if self.handle_api_error(data, "拉黑手机号"):
                    return self.blacklist_phone() # 如果令牌刷新成功，重试拉黑
                # 记录无法处理的 API 错误
                self.log_message(f"API拉黑失败: {data.get('msg', '未知错误')}")
                return False # 返回失败
        # 处理网络或SSL错误
        except requests.exceptions.SSLError as ssl_err:
             self.log_message(f"拉黑手机号时SSL错误: {ssl_err}")
        except requests.exceptions.RequestException as e:
             self.log_message(f"拉黑手机号网络异常: {e}")
        except Exception as e:
             # 处理其他未知错误
             self.log_message(f"拉黑手机号未知异常: {e}")
        return False # 出错返回失败

    # --- GUI 辅助方法 ---
    def copy_phone(self):
        """复制当前手机号到剪贴板"""
        if self.phone_number:
            try:
                self.root.clipboard_clear() # 清空剪贴板
                self.root.clipboard_append(self.phone_number) # 添加号码
                self.log_message(f"号码 {self.phone_number} 已复制到剪贴板。")
                self.set_status("号码已复制。")
            except tk.TclError:
                pass # 忽略剪贴板错误或窗口关闭错误
        else:
            self.log_message("没有号码可复制。")

    def copy_code(self):
        """复制当前验证码到剪贴板"""
        code = self.code_var.get()
        # 检查验证码是否有效
        if code and code not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(code)
                self.log_message(f"验证码 {code} 已复制到剪贴板。")
                self.set_status("验证码已复制。")
            except tk.TclError:
                pass
        else:
            self.log_message("没有有效的验证码可复制。")

    def clear_phone_details(self):
        """拉黑成功后清理手机号相关信息"""
        self.phone_number = None # 清除内部变量
        try:
            # 更新界面显示
            self.phone_var.set("已拉黑")
            self.code_var.set("尚未获取")
            # 更新按钮状态
            self.update_ui_state(self.is_working)
        except tk.TclError:
            pass # 忽略窗口关闭错误

# --- 程序主入口 ---
if __name__ == "__main__":
    # 创建 Tkinter 主窗口
    root = tk.Tk()
    # 实例化应用程序类
    app = SmsApp(root)
    # 进入 Tkinter 事件循环
    root.mainloop()
