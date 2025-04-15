import requests
import time
from urllib.parse import urlencode
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys # Needed for path handling when packaged

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
# Placeholder for actual error code - replace if known
TOKEN_EXPIRED_ERROR_CODE = "E0008" # Example: Replace with actual code like 'E0008' or specific number

# --- Path Handling for Packaged EXE ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

TOKEN_FILE = os.path.join(application_path, "token.txt")

# --- Global Variables (within the App context) ---
# Managed by the App class instance

# --- API Request Headers ---
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

# --- GUI Application Class ---
class SmsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("无尽冬日接码工具") # Changed Title
        self.root.geometry("600x480") # Adjusted size slightly

        # --- Instance Variables ---
        self.token = None
        self.phone_number = None
        self.server = None
        self.is_working = False # Flag to prevent concurrent operations

        # --- GUI Elements ---
        # Frame for controls
        control_frame = ttk.Frame(root, padding="10")
        control_frame.pack(pady=10, padx=10, fill=tk.X)
        control_frame.columnconfigure(1, weight=1) # Allow entry/label column to expand slightly

        # Balance Display (New)
        ttk.Label(control_frame, text="账户余额:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.balance_var = tk.StringVar(value="未知")
        self.balance_label = ttk.Label(control_frame, textvariable=self.balance_var, width=15, anchor=tk.W) # Use Label
        self.balance_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Phone Number Display
        ttk.Label(control_frame, text="手机号码:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.phone_var = tk.StringVar(value="尚未获取")
        self.phone_entry = ttk.Entry(control_frame, textvariable=self.phone_var, state='readonly', width=20)
        self.phone_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        # Verification Code Display
        ttk.Label(control_frame, text="验证码:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.code_var = tk.StringVar(value="尚未获取")
        self.code_entry = ttk.Entry(control_frame, textvariable=self.code_var, state='readonly', width=20)
        self.code_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # --- Buttons ---
        # Row 0 Buttons
        self.get_phone_btn = ttk.Button(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=15)
        self.get_phone_btn.grid(row=1, column=2, padx=(10,5), pady=5, sticky=tk.E) # Align right

        self.copy_phone_btn = ttk.Button(control_frame, text="复制手机号码", command=self.copy_phone, width=15)
        self.copy_phone_btn.grid(row=1, column=3, padx=5, pady=5, sticky=tk.E) # Align right
        self.copy_phone_btn.config(state=tk.DISABLED)

        # Row 1 Buttons
        self.get_code_btn = ttk.Button(control_frame, text="获取验证码", command=self.start_get_code_thread, width=15)
        self.get_code_btn.grid(row=2, column=2, padx=(10,5), pady=5, sticky=tk.E) # Align right
        self.get_code_btn.config(state=tk.DISABLED)

        self.copy_code_btn = ttk.Button(control_frame, text="复制验证码", command=self.copy_code, width=15) # New Button
        self.copy_code_btn.grid(row=2, column=3, padx=5, pady=5, sticky=tk.E) # Align right
        self.copy_code_btn.config(state=tk.DISABLED) # Disable initially

        # Row 2 Button (Blacklist) - Moved down slightly for balance
        self.blacklist_btn = ttk.Button(control_frame, text="拉黑手机号码", command=self.start_blacklist_thread, width=15)
        self.blacklist_btn.grid(row=3, column=3, padx=5, pady=10, sticky=tk.E) # Added pady
        self.blacklist_btn.config(state=tk.DISABLED)

        # Log Area
        log_frame = ttk.LabelFrame(root, text="日志输出", padding="10")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED) # Reduced height slightly
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Status Bar
        self.status_var = tk.StringVar(value="就绪.")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Initialisation ---
        self.log_message("应用程序启动...")
        self.start_initial_login_thread()

    # --- Logging (Simplified) ---
    def log_message(self, message):
        """Appends a message to the log text area."""
        if self.root:
            self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        """Internal method to update log area (runs in main thread)."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def set_status(self, message):
        """Updates the status bar."""
        if self.root:
            self.root.after(0, self.status_var.set, message)

    def update_ui_state(self, working):
        """Enable/disable buttons based on working state."""
        self.is_working = working
        state = tk.DISABLED if working else tk.NORMAL
        self.get_phone_btn.config(state=state)

        phone_available = bool(self.phone_number)
        code_val = self.code_var.get()
        # Check if code is actual code, not placeholder/error message
        code_available = code_val and code_val not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取..."]

        get_code_state = tk.DISABLED if working or not phone_available else tk.NORMAL
        blacklist_state = tk.DISABLED if working or not phone_available else tk.NORMAL
        copy_phone_state = tk.DISABLED if not phone_available else tk.NORMAL
        copy_code_state = tk.DISABLED if working or not code_available else tk.NORMAL # New button state

        self.get_code_btn.config(state=get_code_state)
        self.blacklist_btn.config(state=blacklist_state)
        self.copy_phone_btn.config(state=copy_phone_state)
        self.copy_code_btn.config(state=copy_code_state) # Apply state

        self.set_status("正在处理..." if working else "就绪.")

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
        self.update_ui_state(True)
        self.phone_var.set("正在获取...")
        self.code_var.set("尚未获取")
        self.balance_var.set("查询中...") # Indicate balance check
        self.log_message("开始查询余额并获取手机号...") # Simplified Log
        thread = threading.Thread(target=self._get_phone_task, daemon=True)
        thread.start()

    def start_get_code_thread(self):
        if self.is_working:
            self.log_message("错误：请等待当前操作完成。")
            return
        if not self.phone_number:
            self.log_message("错误：请先获取手机号码。")
            messagebox.showerror("错误", "没有可用的手机号码。")
            return
        self.update_ui_state(True)
        self.code_var.set("正在获取...")
        # Log message moved to _get_code_task for accuracy with phone number
        thread = threading.Thread(target=self._get_code_task, daemon=True)
        thread.start()

    def start_blacklist_thread(self):
        if self.is_working:
            self.log_message("错误：请等待当前操作完成。")
            return
        if not self.phone_number:
            self.log_message("错误：没有手机号码可以拉黑。")
            messagebox.showerror("错误", "没有可用的手机号码。")
            return
        if messagebox.askyesno("确认", f"确定要拉黑号码 {self.phone_number} 吗？"):
            self.update_ui_state(True)
            self.log_message(f"尝试拉黑号码: {self.phone_number}") # Simplified Log
            thread = threading.Thread(target=self._blacklist_task, daemon=True)
            thread.start()
        else:
            self.log_message("拉黑操作已取消。")


    # --- Background Tasks (executed in threads) ---
    def _initial_login_task(self):
        """Tries to read token or login on startup."""
        if not self.read_token():
            try:
                self.try_login()
            except Exception as e:
                self.log_message(f"初始化登录失败: {e}")
                self.root.after(0, lambda: messagebox.showerror("登录失败", f"无法登录或连接服务器: {e}"))
        else:
             self.log_message("使用已保存的令牌成功初始化。")
             # Optionally get balance on startup if needed, but requirement is on Get Phone click
             # balance = self.get_balance()
             # if balance is not None:
             #    self.root.after(0, lambda b=balance: self.balance_var.set(f"{b} 元"))
        self.set_status("初始化完成.")


    def _get_phone_task(self):
        """Gets balance and then phone number in background."""
        try:
            # --- Get Balance First ---
            balance = self.get_balance()
            if balance is not None:
                # Update UI in main thread using lambda to capture current value
                self.root.after(0, lambda b=balance: self.balance_var.set(f"{b} 元"))
            else:
                self.root.after(0, self.balance_var.set, "查询失败")
                # Decide if you want to stop here if balance fails, or continue getting phone?
                # Let's continue for now, but log the balance failure.
                self.log_message("警告：查询余额失败，但仍尝试获取手机号。")

            # --- Then Get Phone Number ---
            phone = self.get_phone_number() # This function now has simplified logging
            if phone:
                self.root.after(0, lambda p=phone: self.phone_var.set(p))
                # Log message is now inside get_phone_number on success
            else:
                self.root.after(0, lambda: self.phone_var.set("获取失败"))
                self.log_message("获取手机号失败。") # Simplified Log
        except Exception as e:
            self.root.after(0, lambda: self.phone_var.set("获取异常"))
            self.log_message(f"获取手机号或余额时发生异常: {e}") # Keep exception log
            self.root.after(0, self.balance_var.set, "查询异常")
        finally:
            self.root.after(0, self.update_ui_state, False)

    def _get_code_task(self):
        """Waits for verification code in background."""
        try:
            # Log start here, as phone_number is confirmed available
            self.log_message(f"开始为号码 {self.phone_number} 等待验证码...") # Simplified Log
            code = self.wait_for_verification_code() # This function now has simplified logging
            if code:
                self.root.after(0, lambda c=code: self.code_var.set(c))
                # Log message is now inside wait_for_verification_code on success
            else:
                self.root.after(0, lambda: self.code_var.set("获取超时或失败"))
                self.log_message("获取验证码失败或超时。") # Simplified Log
                if self.phone_number:
                    self.log_message("尝试自动拉黑超时的号码...")
                    self.blacklist_phone()

        except Exception as e:
            self.root.after(0, lambda: self.code_var.set("获取异常"))
            self.log_message(f"获取验证码时发生异常: {e}") # Keep exception log
        finally:
            self.root.after(0, self.update_ui_state, False)

    def _blacklist_task(self):
        """Blacklists phone number in background."""
        try:
            success = self.blacklist_phone() # This function now has simplified logging
            if success:
                 # Log message is inside blacklist_phone on success
                 pass
            else:
                 self.log_message("拉黑手机号失败。") # Simplified Log
        except Exception as e:
            self.log_message(f"拉黑手机号时发生异常: {e}") # Keep exception log
        finally:
            self.root.after(0, self.update_ui_state, False)

    # --- API Interaction Methods (Simplified Logging) ---

    def read_token(self):
        """从文件中读取令牌"""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f:
                    read_token = f.read().strip()
                    if read_token:
                        # self.log_message("在文件中找到令牌，尝试验证...") # Removed detail
                        for s in SERVERS:
                            try:
                                url = f"{s}/sms/?api=getSummary&token={read_token}"
                                response = requests.get(url, headers=headers, timeout=10)
                                response.raise_for_status()
                                data = response.json()
                                if data.get("code") == 0 or str(data.get("code")) == "0":
                                    # self.log_message(f"令牌有效，使用服务器: {s}") # Removed detail
                                    self.server = s
                                    self.token = read_token
                                    return True
                                # else: # Removed detail
                                     # self.log_message(f"服务器 {s} 验证令牌失败: {data.get('msg', '未知错误')}")
                            except requests.exceptions.RequestException: # Removed detail log
                                # self.log_message(f"连接服务器 {s} 验证令牌时出错: {e}")
                                continue
                        # self.log_message("文件中读取的令牌无效或所有服务器均无法验证。") # Removed detail
                        self.token = None
                        self.server = None
                        return False
            except Exception as e:
                self.log_message(f"读取令牌文件时出错: {e}") # Keep error log
        # self.log_message("未找到令牌文件。") # Removed detail
        return False

    def save_token(self):
        """将令牌保存到文件中"""
        if not self.token: return
        try:
            with open(TOKEN_FILE, 'w') as f: f.write(self.token)
            # self.log_message(f"令牌已保存到文件: {TOKEN_FILE}") # Removed detail
        except Exception as e:
            self.log_message(f"保存令牌到文件时出错: {e}") # Keep error log

    def try_login(self):
        """使用API账号密码登录"""
        # self.log_message("尝试使用账号密码登录...") # Removed detail
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                # self.log_message(f"尝试连接服务器: {s}") # Removed detail
                response = requests.get(login_url, headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                # self.log_message(f"登录响应 ({s}): {data}") # Removed detail
                if data.get("code") == 0 or str(data.get("code")) == "0":
                    # self.log_message(f"登录成功，使用服务器: {s}") # Removed detail
                    self.server = s
                    self.token = data["token"]
                    self.save_token()
                    return
                # else: # Removed detail
                    # self.log_message(f"服务器 {s} 登录失败: {data.get('msg', '未知错误')}")
            except requests.exceptions.Timeout: pass # Removed detail log
                 # self.log_message(f"服务器 {s} 连接超时。")
            except requests.exceptions.RequestException: pass # Removed detail log
                # self.log_message(f"服务器 {s} 连接失败: {e}")
            except Exception as e: # Keep unknown error log
                 self.log_message(f"处理服务器 {s} 响应时发生未知错误: {e}")

        self.server = None
        self.token = None
        raise Exception("所有服务器登录尝试均失败") # Keep exception

    def handle_api_error(self, data, operation_name):
        """Handles common API errors like expired token."""
        error_code = data.get("code")
        error_msg = data.get('msg', '未知错误')
        # Log only critical errors or token expiry
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
             self.log_message("令牌过期或无效，尝试重新登录...")
        elif error_code != 0 and str(error_code) != "0" and "尚未接收" not in error_msg and "没有可用" not in error_msg:
             # Log other potentially important errors, but not simple 'wait' messages
             self.log_message(f"{operation_name}失败: 代码={error_code}, 消息={error_msg}")

        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            self.token = None
            try:
                self.try_login()
                return True # Re-login attempt made
            except Exception as e:
                self.log_message(f"重新登录失败: {e}") # Keep error log
                self.root.after(0, lambda: messagebox.showerror("登录失败", f"令牌过期后无法重新登录: {e}"))
                return False
        return False

    def get_balance(self):
        """获取账户余额"""
        if not self.token or not self.server:
            self.log_message("获取余额失败：未登录或服务器无效。") # Keep error log
            return None
        url = f"{self.server}/sms/?api=getSummary&token={self.token}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            # self.log_message(f"获取余额响应: {data}") # Removed detail
            if data.get("code") == 0 or str(data.get("code")) == "0":
                balance = data.get("money", "未知")
                # self.log_message(f"账户余额: {balance} 元") # Removed detail (will be shown in UI)
                return balance
            else:
                if self.handle_api_error(data, "获取余额"):
                    return self.get_balance() # Retry
                return None
        except Exception as e:
            self.log_message(f"获取余额异常: {e}") # Keep error log
            return None

    def get_phone_number(self):
        """获取手机号码"""
        if not self.token or not self.server:
            # Logged by caller
            return None

        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
        attempts = 0
        max_attempts = 5

        while attempts < max_attempts:
            attempts += 1
            # self.log_message(f"尝试获取手机号 (第 {attempts} 次)...") # Removed detail
            try:
                response = requests.get(url, headers=headers, timeout=20)
                data = response.json()
                # self.log_message(f"获取手机号响应: {data}") # Removed detail

                if data.get("code") == 0 or str(data.get("code")) == "0":
                    phone = data.get("phone")
                    if phone:
                        self.phone_number = phone
                        self.root.after(0, lambda: self.code_var.set("尚未获取"))
                        self.log_message(f"成功获取手机号: {self.phone_number}") # Simplified Log
                        return self.phone_number
                    # else: # Removed detail
                        # self.log_message("API成功但未返回手机号，重试...")

                elif str(data.get("code")) == "-1" and "没有可用手机号" in data.get("msg", ""):
                     # self.log_message(f"暂时没有可用手机号: {data.get('msg')}") # Removed detail
                     if attempts < max_attempts:
                         # self.log_message("等待 3 秒后重试...") # Removed detail
                         time.sleep(3)
                         continue
                     else:
                         # self.log_message("已达到最大重试次数，获取手机号失败。") # Removed detail
                         self.phone_number = None
                         return None
                else:
                    if self.handle_api_error(data, "获取手机号"):
                        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
                        attempts -= 1
                        continue
                    else:
                        self.phone_number = None
                        return None

            except requests.exceptions.Timeout: pass # Removed detail log
                # self.log_message("获取手机号请求超时。")
            except Exception as e:
                self.log_message(f"获取手机号异常: {e}") # Keep error log

            if attempts < max_attempts:
                 time.sleep(2)

        self.phone_number = None
        return None


    def wait_for_verification_code(self, timeout=120):
        """等待验证码"""
        if not self.token or not self.server or not self.phone_number:
            # Logged by caller
            return None

        start_time = time.time()
        # Log message moved to _get_code_task

        while time.time() - start_time < timeout:
            if not self.token: return None # Token became invalid

            params = {"api": "getMessage", "token": self.token, "sid": PROJECT_ID, "phone": self.phone_number}
            url = f"{self.server}/sms/?{urlencode(params)}"
            try:
                response = requests.get(url, headers=headers, timeout=15)
                data = response.json()
                # self.log_message(f"获取验证码响应: {data}") # Removed detail

                if data.get("code") == 0 or str(data.get("code")) == "0":
                    verification_code = data.get("yzm") or data.get("msg")
                    if verification_code and verification_code != "ok":
                        # Basic check for meaningful code
                        if len(verification_code) > 1 and verification_code.isalnum():
                           self.log_message(f"成功获取验证码: {verification_code}") # Simplified Log
                           return verification_code
                        # else: # Removed detail
                            # self.log_message(f"收到消息 '{verification_code}'，继续等待验证码...")
                    # else: # Removed detail
                        # self.log_message("尚未收到验证码，继续等待...")

                elif "尚未接收到短信" in data.get("msg", ""): pass # Removed detail log
                    # self.log_message("服务器尚未收到短信，继续等待...")
                else:
                    if self.handle_api_error(data, "获取验证码"):
                        pass # Continue loop with new token
                    else:
                        return None # Unhandled error

            except requests.exceptions.Timeout: pass # Removed detail log
                # self.log_message("获取验证码请求超时，将重试...")
            except Exception as e:
                self.log_message(f"获取验证码异常: {e}") # Keep error log

            time.sleep(5)

        # Timeout logged by caller
        return None

    def blacklist_phone(self):
        """将手机号码加入黑名单"""
        if not self.token or not self.server or not self.phone_number:
            # Logged by caller
            return False

        # Log message moved to start_blacklist_thread
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            # self.log_message(f"拉黑响应: {data}") # Removed detail
            if data.get("code") == 0 or str(data.get("code")) == "0":
                self.log_message(f"手机号码 {self.phone_number} 已成功拉黑。") # Simplified Log
                self.root.after(0, self.clear_phone_details)
                return True
            else:
                if self.handle_api_error(data, "拉黑手机号"):
                    return self.blacklist_phone() # Retry
                return False
        except Exception as e:
            self.log_message(f"拉黑手机号码异常: {e}") # Keep error log
            return False

    # --- GUI Helper Methods ---
    def copy_phone(self):
        """Copies the current phone number to the clipboard."""
        if self.phone_number:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.phone_number)
            self.log_message(f"号码 {self.phone_number} 已复制到剪贴板。")
            self.set_status("号码已复制。")
        else:
            self.log_message("没有号码可复制。")

    def copy_code(self): # New Method
        """Copies the current verification code to the clipboard."""
        code = self.code_var.get()
        if code and code not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取..."]:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.log_message(f"验证码 {code} 已复制到剪贴板。")
            self.set_status("验证码已复制。")
        else:
            self.log_message("没有有效的验证码可复制。")


    def clear_phone_details(self):
        """Clears phone number and code from display and variables."""
        self.phone_number = None
        self.phone_var.set("尚未获取")
        self.code_var.set("尚未获取")
        # Don't clear balance here
        self.update_ui_state(self.is_working)


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SmsApp(root)
    root.mainloop()
