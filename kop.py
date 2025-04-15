import requests
import time
from urllib.parse import urlencode
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
import ssl

# --- Configuration ---
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

# --- Path Handling ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(application_path, "token.txt")

# --- API Headers ---
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

# --- GUI Application Class ---
class SmsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("无尽冬日接码工具")
        self.root.geometry("600x480")

        self.token = None
        self.phone_number = None
        self.server = None
        self.is_working = False
        self.auto_fetch_job = None # 存储 'after' 任务 ID

        # --- GUI Elements ---
        control_frame = ttk.Frame(root, padding="10")
        control_frame.pack(pady=10, padx=10, fill=tk.X)
        control_frame.columnconfigure(1, weight=1)

        ttk.Label(control_frame, text="账户余额:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.balance_var = tk.StringVar(value="未知")
        self.balance_label = ttk.Label(control_frame, textvariable=self.balance_var, width=15, anchor=tk.W)
        self.balance_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(control_frame, text="手机号码:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.phone_var = tk.StringVar(value="尚未获取")
        self.phone_entry = ttk.Entry(control_frame, textvariable=self.phone_var, state='readonly', width=20)
        self.phone_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(control_frame, text="验证码:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.code_var = tk.StringVar(value="尚未获取")
        self.code_entry = ttk.Entry(control_frame, textvariable=self.code_var, state='readonly', width=20)
        self.code_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # Buttons
        self.get_phone_btn = ttk.Button(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=15)
        self.get_phone_btn.grid(row=1, column=2, padx=(10,5), pady=5, sticky=tk.E)

        self.copy_phone_btn = ttk.Button(control_frame, text="复制手机号码", command=self.copy_phone, width=15)
        self.copy_phone_btn.grid(row=1, column=3, padx=5, pady=5, sticky=tk.E)
        self.copy_phone_btn.config(state=tk.DISABLED)

        self.copy_code_btn = ttk.Button(control_frame, text="复制验证码", command=self.copy_code, width=15)
        self.copy_code_btn.grid(row=2, column=3, padx=5, pady=5, sticky=tk.E)
        self.copy_code_btn.config(state=tk.DISABLED)

        self.blacklist_btn = ttk.Button(control_frame, text="拉黑手机号码", command=self.start_blacklist_thread, width=15)
        self.blacklist_btn.grid(row=3, column=3, padx=5, pady=10, sticky=tk.E)
        self.blacklist_btn.config(state=tk.DISABLED)

        # Log Area
        log_frame = ttk.LabelFrame(root, text="日志输出", padding="10")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Status Bar
        self.status_var = tk.StringVar(value="就绪.")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Initialisation ---
        self.log_message("应用程序启动...")
        self.start_initial_login_thread()

    # --- Logging & Status ---
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

    # --- UI State Management ---
    def update_ui_state(self, working):
        """更新UI元素状态"""
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

    # --- Thread Starters ---
    def start_initial_login_thread(self):
        self.set_status("正在初始化...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True)
        thread.start()

    def start_get_phone_thread(self):
        if self.is_working:
            self.log_message("错误：请等待当前操作完成。")
            return
        if not self.token or not self.server:
             self.log_message("错误：无法获取手机号，请先确保登录成功。")
             messagebox.showerror("错误", "未登录或服务器无效，请重启应用或检查网络。")
             return
        if self.auto_fetch_job:
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None
        self.update_ui_state(True) # 开始工作，禁用按钮
        self.phone_var.set("正在获取...")
        self.code_var.set("尚未获取")
        self.balance_var.set("查询中...")
        self.log_message("开始查询余额并获取手机号...")
        thread = threading.Thread(target=self._get_phone_task, daemon=True)
        thread.start()

    def start_automatic_code_fetch(self):
        self.auto_fetch_job = None
        if not self.phone_number:
            self.log_message("错误：手机号在等待期间丢失，无法获取验证码。")
            self.update_ui_state(False) # 释放工作状态
            return
        self.is_working = True # 标记为正在工作（获取验证码阶段）
        self.set_status("正在获取验证码...")
        self.code_var.set("正在获取...")
        self.update_ui_state(True) # 再次禁用按钮（除了复制号码）
        self.log_message(f"开始为号码 {self.phone_number} 自动获取验证码...")
        thread = threading.Thread(target=self._get_code_task_automatic, daemon=True)
        thread.start()

    def start_blacklist_thread(self):
        if self.is_working:
            self.log_message("错误：请等待当前操作完成。")
            return
        if not self.phone_number:
            self.log_message("错误：没有手机号码可以拉黑。")
            messagebox.showerror("错误", "没有可用的手机号码。")
            return
        if self.auto_fetch_job: # 如果正在等待10秒倒计时
            try: self.root.after_cancel(self.auto_fetch_job)
            except tk.TclError: pass
            self.auto_fetch_job = None
            self.log_message("已取消等待获取验证码。")
            self.set_status("就绪.") # 重置状态
        if messagebox.askyesno("确认", f"确定要拉黑号码 {self.phone_number} 吗？"):
            self.update_ui_state(True) # 开始工作
            self.log_message(f"尝试拉黑号码: {self.phone_number}")
            thread = threading.Thread(target=self._blacklist_task, daemon=True)
            thread.start()
        else:
            self.log_message("拉黑操作已取消。")

    # --- Background Tasks ---
    def _initial_login_task(self):
        try:
            if not self.read_token():
                try: self.try_login()
                except Exception as e:
                    self.log_message(f"初始化登录失败: {e}")
                    self.root.after(0, lambda: messagebox.showerror("登录失败", f"无法登录或连接服务器: {e}"))
            else:
                 self.log_message("使用已保存的令牌成功初始化。")
        except Exception as e:
             self.log_message(f"初始化过程中发生未知错误: {e}")
        finally:
             self.set_status("初始化完成.") # 确保状态更新

    def _get_phone_task(self):
        """获取余额和手机号，成功后更新UI并安排验证码获取"""
        phone_obtained = False
        try:
            balance = self.get_balance()
            if balance is not None:
                self.root.after(0, lambda b=balance: self.balance_var.set(f"{b} 元"))
            else:
                self.root.after(0, self.balance_var.set, "查询失败")
                self.log_message("警告：查询余额失败，但仍尝试获取手机号。")

            phone = self.get_phone_number() # Continuous attempt
            if phone:
                phone_obtained = True
                # --- Fix 2: Update UI and button states *immediately* after getting phone ---
                self.root.after(0, lambda p=phone: self.phone_var.set(p))
                self.root.after(0, self.update_ui_state, False) # 更新按钮状态，传入False表示非工作状态
                # --- End Fix 2 ---

                self.log_message("手机号获取成功，将在 10 秒后开始获取验证码...")
                self.set_status("等待获取验证码 (10s)...")
                try:
                    self.auto_fetch_job = self.root.after(10000, self.start_automatic_code_fetch)
                except tk.TclError:
                    self.log_message("错误：窗口已关闭，无法安排验证码获取。")
                    phone_obtained = False # 标记为失败以释放工作状态
            else:
                self.root.after(0, lambda: self.phone_var.set("获取失败"))
                self.log_message("获取手机号失败 (无法恢复的错误)。")

        except Exception as e:
            self.root.after(0, lambda: self.phone_var.set("获取异常"))
            self.log_message(f"获取手机号或余额时发生异常: {e}")
            self.root.after(0, self.balance_var.set, "查询异常")
        finally:
            # 只有在获取手机号彻底失败时才释放工作状态
            # 如果成功获取手机号，工作状态由后续的验证码获取流程管理
            if not phone_obtained:
                self.root.after(0, self.update_ui_state, False)

    def _get_code_task_automatic(self):
        code = None
        restart_needed = False
        try:
            code = self.wait_for_verification_code(timeout=200)
            if code:
                self.root.after(0, lambda c=code: self.code_var.set(c))
                # 成功获取验证码后，更新一次UI状态以启用复制验证码按钮
                self.root.after(0, self.update_ui_state, False) # 传入False表示工作结束
            else: # Timeout occurred
                self.log_message("验证码获取超时 (200秒)。")
                self.root.after(0, lambda: self.code_var.set("获取超时"))
                if self.phone_number:
                    self.log_message(f"自动拉黑号码: {self.phone_number}")
                    blacklist_success = self.blacklist_phone() # Runs synchronously
                    if blacklist_success:
                        restart_needed = True
                        # 使用 after 确保在主线程中安全调用
                        self.root.after(0, self.restart_process_after_timeout)
                    else:
                        self.log_message("拉黑失败，无法自动重启流程。")
                else:
                     self.log_message("无号码可拉黑，无法自动重启流程。")
        except Exception as e:
            self.root.after(0, lambda: self.code_var.set("获取异常"))
            self.log_message(f"自动获取验证码时发生异常: {e}")
        finally:
            # 只有在不需要重启时才最终释放工作状态
            if not restart_needed:
                 self.root.after(0, self.update_ui_state, False)

    def _blacklist_task(self):
        """手动拉黑的后台任务"""
        try:
            success = self.blacklist_phone()
            if not success:
                 self.log_message("手动拉黑手机号失败。")
        except Exception as e:
            self.log_message(f"手动拉黑手机号时发生异常: {e}")
        finally:
            # 手动拉黑完成后，总是释放工作状态
            self.root.after(0, self.update_ui_state, False)

    def restart_process_after_timeout(self):
        """在主线程中安全地重启获取手机号流程"""
        try:
            self.log_message("验证码超时，自动重新开始获取手机号...")
            self.phone_var.set("重新获取...")
            self.code_var.set("尚未获取")
            # 启动获取流程，它会自己管理 is_working 状态
            self.start_get_phone_thread()
        except tk.TclError:
             self.log_message("错误：窗口已关闭，无法重启流程。")

    # --- API Interaction Methods ---
    def read_token(self):
        # ... (保持不变) ...
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f: read_token = f.read().strip()
                if read_token:
                    for s in SERVERS:
                        try:
                            url = f"{s}/sms/?api=getSummary&token={read_token}"
                            response = requests.get(url, headers=headers, timeout=10, verify=True)
                            response.raise_for_status()
                            data = response.json()
                            if data.get("code") == 0 or str(data.get("code")) == "0":
                                self.server = s; self.token = read_token; return True
                        except requests.exceptions.SSLError as ssl_err: self.log_message(f"验证令牌时SSL错误 ({s}): {ssl_err}")
                        except requests.exceptions.RequestException: pass
                    self.token = None; self.server = None; return False
            except Exception as e: self.log_message(f"读取令牌文件时出错: {e}")
        return False

    def save_token(self):
        # ... (保持不变) ...
        if not self.token: return
        try:
            with open(TOKEN_FILE, 'w') as f: f.write(self.token)
        except Exception as e: self.log_message(f"保存令牌到文件时出错: {e}")

    def try_login(self):
        # ... (保持不变) ...
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                response = requests.get(login_url, headers=headers, timeout=15, verify=True)
                response.raise_for_status()
                data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0":
                    self.server = s; self.token = data["token"]; self.save_token(); return
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"登录时SSL错误 ({s}): {ssl_err}")
            except requests.exceptions.Timeout: pass
            except requests.exceptions.RequestException: pass
            except Exception as e: self.log_message(f"处理服务器 {s} 响应时发生未知错误: {e}")
        self.server = None; self.token = None
        raise Exception("所有服务器登录尝试均失败")

    def handle_api_error(self, data, operation_name):
        # ... (保持不变) ...
        error_code = data.get("code"); error_msg = data.get('msg', '未知错误')
        # 仅在非特定等待消息且非令牌过期时记录为“失败”
        is_waiting_msg = "尚未接收" in error_msg or "等待" == error_msg or "没有可用" in error_msg
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
             self.log_message("令牌过期或无效，尝试重新登录...")
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg:
             self.log_message(f"{operation_name}失败: 代码={error_code}, 消息={error_msg}")

        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            self.token = None
            try: self.try_login(); return True # 标记需要重试
            except Exception as e:
                self.log_message(f"重新登录失败: {e}")
                self.root.after(0, lambda: messagebox.showerror("登录失败", f"令牌过期后无法重新登录: {e}"))
                return False # 标记失败
        return False # 其他情况标记为不需要特殊处理（如重试）

    def get_balance(self):
        # ... (保持不变) ...
        if not self.token or not self.server: return None
        url = f"{self.server}/sms/?api=getSummary&token={self.token}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0": return data.get("money", "未知")
            else:
                if self.handle_api_error(data, "获取余额"): return self.get_balance()
                return None
        except requests.exceptions.SSLError as ssl_err: self.log_message(f"获取余额时SSL错误: {ssl_err}")
        except requests.exceptions.RequestException as e: self.log_message(f"获取余额网络异常: {e}")
        except Exception as e: self.log_message(f"获取余额未知异常: {e}")
        return None

    def get_phone_number(self):
        # ... (保持不变) ...
        if not self.token or not self.server: return None
        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
        retry_delay = 3
        self.log_message("正在持续获取手机号...")
        while True:
            if not self.token: self.log_message("获取手机号中断：令牌失效。"); return None
            try:
                response = requests.get(url, headers=headers, timeout=20, verify=True)
                data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0":
                    phone = data.get("phone")
                    if phone:
                        self.phone_number = phone
                        self.root.after(0, lambda: self.code_var.set("尚未获取"))
                        self.log_message(f"成功获取手机号: {self.phone_number}")
                        return self.phone_number
                    else: self.log_message("API响应成功但未包含手机号，稍后重试..."); time.sleep(retry_delay); continue
                elif str(data.get("code")) == "-1" and ("没有可用手机号" in data.get("msg", "") or "请稍后再试" in data.get("msg", "") or "等待" == data.get("msg", "")): # 添加 "等待"
                     self.log_message(f"暂时没有可用手机号或需等待({data.get('msg', '')})，{retry_delay}秒后自动重试..."); time.sleep(retry_delay); continue
                else:
                    if self.handle_api_error(data, "获取手机号"):
                        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
                        self.log_message("令牌已更新，立即重试获取手机号..."); continue
                    else: self.log_message("获取手机号时遇到无法恢复的API错误，停止尝试。"); self.phone_number = None; return None
            except requests.exceptions.SSLError as ssl_err: self.log_message(f"获取手机号时SSL错误: {ssl_err}，稍后重试..."); time.sleep(5); continue
            except requests.exceptions.Timeout: self.log_message("获取手机号请求超时，稍后重试..."); time.sleep(5); continue
            except requests.exceptions.RequestException as e: self.log_message(f"获取手机号时发生网络错误: {e}，停止尝试。"); self.phone_number = None; return None
            except Exception as e: self.log_message(f"获取手机号时发生未知异常: {e}，停止尝试。"); self.phone_number = None; return None

    def wait_for_verification_code(self, timeout=200):
        """等待验证码 (轮询间隔2秒, 超时200秒)"""
        if not self.token or not self.server or not self.phone_number: return None
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.token: return None # 令牌在等待期间失效
            params = {"api": "getMessage", "token": self.token, "sid": PROJECT_ID, "phone": self.phone_number}
            url = f"{self.server}/sms/?{urlencode(params)}"
            try:
                response = requests.get(url, headers=headers, timeout=15, verify=True)
                data = response.json()
                code = data.get("code")
                msg = data.get("msg", "")

                # 1. 检查是否成功获取验证码
                if code == 0 or str(code) == "0":
                    verification_code = data.get("yzm") or msg # 有时验证码在msg里
                    if verification_code and verification_code != "ok":
                        # 基本检查，确保不是简单的成功消息
                        if len(verification_code) > 1 and verification_code.isalnum():
                           self.log_message(f"成功获取验证码: {verification_code}")
                           return verification_code
                        # else: 收到 "ok" 或类似消息，继续等待

                # --- Fix 1: Explicitly handle waiting messages ---
                # 2. 检查是否是明确的等待消息
                elif "尚未接收到短信" in msg or (code == -1 and msg == "等待"):
                    # 这是预期的等待状态，继续轮询
                    pass # 不做任何事，直接进入 sleep
                # --- End Fix 1 ---

                # 3. 处理其他 API 错误（包括令牌过期）
                else:
                    if self.handle_api_error(data, "获取验证码"):
                        # 令牌已刷新，更新 URL 并立即继续下一次循环
                        url = f"{self.server}/sms/?{urlencode(params)}"
                        continue
                    else:
                        # 无法处理的 API 错误或重新登录失败，停止等待
                        return None

            # 4. 处理网络层面的错误
            except requests.exceptions.SSLError as ssl_err:
                 self.log_message(f"获取验证码轮询时SSL错误: {ssl_err}，继续轮询...")
            except requests.exceptions.Timeout:
                 self.log_message("获取验证码轮询超时，继续轮询...") # 记录一下超时，但继续
            except requests.exceptions.RequestException as e:
                 self.log_message(f"获取验证码轮询时网络错误: {e}，继续轮询...")
            except Exception as e:
                 self.log_message(f"获取验证码轮询未知异常: {e}") # 未知异常也继续轮询

            # 轮询间隔
            time.sleep(2)

        # 如果循环正常结束，说明超时
        return None

    def blacklist_phone(self):
        # ... (保持不变) ...
        if not self.token or not self.server or not self.phone_number: return False
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0":
                self.log_message(f"手机号码 {self.phone_number} 已成功拉黑。")
                self.root.after(0, self.clear_phone_details); return True
            else:
                if self.handle_api_error(data, "拉黑手机号"): return self.blacklist_phone()
                self.log_message(f"API拉黑失败: {data.get('msg', '未知错误')}")
                return False
        except requests.exceptions.SSLError as ssl_err: self.log_message(f"拉黑手机号时SSL错误: {ssl_err}")
        except requests.exceptions.RequestException as e: self.log_message(f"拉黑手机号网络异常: {e}")
        except Exception as e: self.log_message(f"拉黑手机号未知异常: {e}")
        return False

    # --- GUI Helper Methods ---
    def copy_phone(self):
        # ... (保持不变) ...
        if self.phone_number:
            try: self.root.clipboard_clear(); self.root.clipboard_append(self.phone_number); self.log_message(f"号码 {self.phone_number} 已复制到剪贴板。"); self.set_status("号码已复制。")
            except tk.TclError: pass
        else: self.log_message("没有号码可复制。")
    def copy_code(self):
        # ... (保持不变) ...
        code = self.code_var.get()
        if code and code not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]:
            try: self.root.clipboard_clear(); self.root.clipboard_append(code); self.log_message(f"验证码 {code} 已复制到剪贴板。"); self.set_status("验证码已复制。")
            except tk.TclError: pass
        else: self.log_message("没有有效的验证码可复制。")
    def clear_phone_details(self):
        # ... (保持不变) ...
        self.phone_number = None
        try:
            self.phone_var.set("已拉黑")
            self.code_var.set("尚未获取")
            self.update_ui_state(self.is_working) # 更新按钮状态
        except tk.TclError: pass

# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SmsApp(root)
    root.mainloop()
