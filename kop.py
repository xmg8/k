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
    # If the application is run as a bundle/frozen executable (like with PyInstaller)
    application_path = os.path.dirname(sys.executable)
else:
    # If run as a normal Python script
    application_path = os.path.dirname(os.path.abspath(__file__))

TOKEN_FILE = os.path.join(application_path, "token.txt")

# --- Global Variables (within the App context) ---
# These will be managed by the App class instance

# --- API Request Headers ---
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

# --- GUI Application Class ---
class SmsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("短信验证码获取工具")
        self.root.geometry("550x450") # Adjusted size for log area

        # --- Instance Variables ---
        self.token = None
        self.phone_number = None
        self.server = None
        self.is_working = False # Flag to prevent concurrent operations

        # --- GUI Elements ---
        # Frame for controls
        control_frame = ttk.Frame(root, padding="10")
        control_frame.pack(pady=10, padx=10, fill=tk.X)

        # Phone Number Display
        ttk.Label(control_frame, text="手机号码:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.phone_var = tk.StringVar(value="尚未获取")
        self.phone_entry = ttk.Entry(control_frame, textvariable=self.phone_var, state='readonly', width=20)
        self.phone_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Verification Code Display
        ttk.Label(control_frame, text="验证码:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.code_var = tk.StringVar(value="尚未获取")
        self.code_entry = ttk.Entry(control_frame, textvariable=self.code_var, state='readonly', width=20)
        self.code_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        # Buttons
        self.get_phone_btn = ttk.Button(control_frame, text="获取手机号", command=self.start_get_phone_thread, width=15)
        self.get_phone_btn.grid(row=0, column=2, padx=10, pady=5)

        self.copy_phone_btn = ttk.Button(control_frame, text="复制手机号码", command=self.copy_phone, width=15)
        self.copy_phone_btn.grid(row=0, column=3, padx=10, pady=5)
        self.copy_phone_btn.config(state=tk.DISABLED) # Disable initially

        self.get_code_btn = ttk.Button(control_frame, text="获取验证码", command=self.start_get_code_thread, width=15)
        self.get_code_btn.grid(row=1, column=2, padx=10, pady=5)
        self.get_code_btn.config(state=tk.DISABLED) # Disable initially

        self.blacklist_btn = ttk.Button(control_frame, text="拉黑手机号码", command=self.start_blacklist_thread, width=15)
        self.blacklist_btn.grid(row=1, column=3, padx=10, pady=5)
        self.blacklist_btn.config(state=tk.DISABLED) # Disable initially

        # Log Area
        log_frame = ttk.LabelFrame(root, text="日志输出", padding="10")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, state=tk.DISABLED) # Start disabled
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Status Bar (Optional but good practice)
        self.status_var = tk.StringVar(value="就绪.")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Initialisation ---
        self.log_message("应用程序启动...")
        self.start_initial_login_thread() # Try login/read token on startup

    # --- Logging ---
    def log_message(self, message):
        """Appends a message to the log text area."""
        if self.root: # Check if root window exists
            self.root.after(0, self._append_log, message) # Schedule update in main thread

    def _append_log(self, message):
        """Internal method to update log area (runs in main thread)."""
        self.log_text.config(state=tk.NORMAL) # Enable writing
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END) # Scroll to the end
        self.log_text.config(state=tk.DISABLED) # Disable writing

    def set_status(self, message):
        """Updates the status bar."""
        if self.root:
            self.root.after(0, self.status_var.set, message)

    def update_ui_state(self, working):
        """Enable/disable buttons based on working state."""
        self.is_working = working
        state = tk.DISABLED if working else tk.NORMAL
        self.get_phone_btn.config(state=state)

        # Only enable code/blacklist if a phone number exists and not working
        phone_available = bool(self.phone_number)
        code_blacklist_state = tk.DISABLED if working or not phone_available else tk.NORMAL
        self.get_code_btn.config(state=code_blacklist_state)
        self.blacklist_btn.config(state=code_blacklist_state)
        self.copy_phone_btn.config(state=tk.DISABLED if not phone_available else tk.NORMAL)

        # Update status
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
        self.code_var.set("尚未获取") # Reset code when getting new phone
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
             # Optionally get balance on startup
             # self.get_balance()
        self.set_status("初始化完成.")


    def _get_phone_task(self):
        """Gets phone number in background."""
        try:
            phone = self.get_phone_number()
            if phone:
                self.root.after(0, lambda: self.phone_var.set(phone))
                self.log_message(f"成功获取手机号: {phone}")
            else:
                self.root.after(0, lambda: self.phone_var.set("获取失败"))
                self.log_message("获取手机号失败，请查看日志。")
        except Exception as e:
            self.root.after(0, lambda: self.phone_var.set("获取异常"))
            self.log_message(f"获取手机号时发生异常: {e}")
        finally:
            self.root.after(0, self.update_ui_state, False) # Update UI in main thread

    def _get_code_task(self):
        """Waits for verification code in background."""
        try:
            code = self.wait_for_verification_code()
            if code:
                self.root.after(0, lambda: self.code_var.set(code))
                self.log_message(f"成功获取验证码: {code}")
            else:
                self.root.after(0, lambda: self.code_var.set("获取超时或失败"))
                self.log_message("获取验证码失败或超时。")
                # Attempt to blacklist if timeout occurred
                if self.phone_number:
                    self.log_message("尝试自动拉黑超时的号码...")
                    self.blacklist_phone() # Run blacklist directly here or start another thread if needed

        except Exception as e:
            self.root.after(0, lambda: self.code_var.set("获取异常"))
            self.log_message(f"获取验证码时发生异常: {e}")
        finally:
            self.root.after(0, self.update_ui_state, False)

    def _blacklist_task(self):
        """Blacklists phone number in background."""
        try:
            self.blacklist_phone()
            # Optionally clear phone number after blacklisting
            # self.root.after(0, self.clear_phone_details)
        except Exception as e:
            self.log_message(f"拉黑手机号时发生异常: {e}")
        finally:
            self.root.after(0, self.update_ui_state, False)

    # --- API Interaction Methods (modified for GUI logging) ---

    def read_token(self):
        """从文件中读取令牌"""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f:
                    read_token = f.read().strip()
                    if read_token:
                        self.log_message("在文件中找到令牌，尝试验证...")
                        # Try validating token against servers
                        for s in SERVERS:
                            try:
                                url = f"{s}/sms/?api=getSummary&token={read_token}"
                                response = requests.get(url, headers=headers, timeout=10)
                                response.raise_for_status()
                                data = response.json()
                                # Check for specific success code, adjust if needed
                                if data.get("code") == 0 or str(data.get("code")) == "0":
                                    self.log_message(f"令牌有效，使用服务器: {s}")
                                    self.server = s
                                    self.token = read_token
                                    return True
                                else:
                                     self.log_message(f"服务器 {s} 验证令牌失败: {data.get('msg', '未知错误')}")
                            except requests.exceptions.RequestException as e:
                                self.log_message(f"连接服务器 {s} 验证令牌时出错: {e}")
                                continue # Try next server
                        self.log_message("文件中读取的令牌无效或所有服务器均无法验证。")
                        self.token = None # Ensure token is cleared if invalid
                        self.server = None
                        return False
            except Exception as e:
                self.log_message(f"读取令牌文件时出错: {e}")
        self.log_message("未找到令牌文件。")
        return False

    def save_token(self):
        """将令牌保存到文件中"""
        if not self.token:
            self.log_message("错误：没有令牌可保存。")
            return
        try:
            with open(TOKEN_FILE, 'w') as f:
                f.write(self.token)
            self.log_message(f"令牌已保存到文件: {TOKEN_FILE}")
        except Exception as e:
            self.log_message(f"保存令牌到文件时出错: {e}")

    def try_login(self):
        """使用API账号密码登录，找到可用服务器并获取token"""
        self.log_message("尝试使用账号密码登录...")
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                self.log_message(f"尝试连接服务器: {s}")
                response = requests.get(login_url, headers=headers, timeout=15) # Increased timeout
                response.raise_for_status()
                data = response.json()
                self.log_message(f"登录响应 ({s}): {data}")
                # Check for specific success code, adjust if needed
                if data.get("code") == 0 or str(data.get("code")) == "0":
                    self.log_message(f"登录成功，使用服务器: {s}")
                    self.server = s
                    self.token = data["token"]
                    self.save_token()
                    return # Exit after successful login
                else:
                    self.log_message(f"服务器 {s} 登录失败: {data.get('msg', '未知错误')}")
            except requests.exceptions.Timeout:
                 self.log_message(f"服务器 {s} 连接超时。")
            except requests.exceptions.RequestException as e:
                self.log_message(f"服务器 {s} 连接失败: {e}")
            except Exception as e:
                 self.log_message(f"处理服务器 {s} 响应时发生未知错误: {e}")

        # If loop completes without returning, login failed
        self.server = None
        self.token = None
        raise Exception("所有服务器登录尝试均失败")

    def handle_api_error(self, data, operation_name):
        """Handles common API errors like expired token."""
        error_code = data.get("code")
        error_msg = data.get('msg', '未知错误')
        self.log_message(f"{operation_name}失败: 代码={error_code}, 消息={error_msg}")

        # Check if the error code indicates an expired token
        # IMPORTANT: Replace TOKEN_EXPIRED_ERROR_CODE with the actual code from the API documentation
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            self.log_message("令牌过期或无效，尝试重新登录...")
            self.token = None # Clear invalid token
            try:
                self.try_login()
                # If login succeeds, the original operation should be retried by the calling function
                return True # Indicates re-login attempt was made
            except Exception as e:
                self.log_message(f"重新登录失败: {e}")
                self.root.after(0, lambda: messagebox.showerror("登录失败", f"令牌过期后无法重新登录: {e}"))
                return False # Re-login failed
        return False # Error was not a token expiry, or re-login failed

    def get_balance(self):
        """获取账户余额"""
        if not self.token or not self.server:
            self.log_message("获取余额失败：未登录或服务器无效。")
            return None
        url = f"{self.server}/sms/?api=getSummary&token={self.token}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            self.log_message(f"获取余额响应: {data}")
            if data.get("code") == 0 or str(data.get("code")) == "0":
                balance = data.get("money", "未知")
                self.log_message(f"账户余额: {balance} 元")
                return balance
            else:
                # Handle potential token expiry and retry
                if self.handle_api_error(data, "获取余额"):
                    return self.get_balance() # Retry after successful re-login
                return None # Error handled, but balance not retrieved
        except Exception as e:
            self.log_message(f"获取余额异常: {e}")
            return None

    def get_phone_number(self):
        """获取手机号码"""
        if not self.token or not self.server:
            self.log_message("获取手机号失败：未登录或服务器无效。")
            return None

        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
        attempts = 0
        max_attempts = 5 # Limit retries for "no available number"

        while attempts < max_attempts:
            attempts += 1
            self.log_message(f"尝试获取手机号 (第 {attempts} 次)...")
            try:
                response = requests.get(url, headers=headers, timeout=20) # Longer timeout for getting phone
                data = response.json()
                self.log_message(f"获取手机号响应: {data}")

                # Check for success code
                if data.get("code") == 0 or str(data.get("code")) == "0":
                    phone = data.get("phone")
                    if phone:
                        self.phone_number = phone # Store the phone number
                        # Clear previous code
                        self.root.after(0, lambda: self.code_var.set("尚未获取"))
                        return self.phone_number
                    else:
                        self.log_message("API成功但未返回手机号，重试...")

                # Check for specific "no phone available" error code (replace '-1' if different)
                elif str(data.get("code")) == "-1" and "没有可用手机号" in data.get("msg", ""):
                     self.log_message(f"暂时没有可用手机号: {data.get('msg')}")
                     if attempts < max_attempts:
                         self.log_message("等待 3 秒后重试...")
                         time.sleep(3)
                         continue # Retry the loop
                     else:
                         self.log_message("已达到最大重试次数，获取手机号失败。")
                         self.phone_number = None
                         return None

                # Handle other errors (like token expiry)
                else:
                    if self.handle_api_error(data, "获取手机号"):
                        # Token expired and re-login successful, update URL and retry immediately
                        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={PROJECT_ID}"
                        attempts -= 1 # Don't count this as a failed attempt for 'no number'
                        continue
                    else:
                        # Unhandled error or re-login failed
                        self.phone_number = None
                        return None

            except requests.exceptions.Timeout:
                self.log_message("获取手机号请求超时。")
            except Exception as e:
                self.log_message(f"获取手机号异常: {e}")
                # Don't retry immediately on general exceptions unless sure it's recoverable

            # If error occurred or no phone found after check, wait before next loop iteration (if any)
            if attempts < max_attempts:
                 time.sleep(2) # Wait 2 seconds before next attempt in loop

        # If loop finishes without returning a number
        self.log_message("获取手机号失败，已达到最大尝试次数。")
        self.phone_number = None
        return None


    def wait_for_verification_code(self, timeout=120):
        """等待验证码"""
        if not self.token or not self.server or not self.phone_number:
            self.log_message("获取验证码失败：未登录、无服务器或无手机号。")
            return None

        start_time = time.time()
        self.log_message(f"开始为号码 {self.phone_number} 等待验证码 (超时 {timeout} 秒)...")

        while time.time() - start_time < timeout:
            if not self.token: # Check if token became invalid during wait
                 self.log_message("获取验证码中断：令牌失效。")
                 return None

            params = {
                "api": "getMessage",
                "token": self.token,
                "sid": PROJECT_ID,
                "phone": self.phone_number
            }
            url = f"{self.server}/sms/?{urlencode(params)}"
            try:
                response = requests.get(url, headers=headers, timeout=15) # Shorter timeout for polling
                data = response.json()
                self.log_message(f"获取验证码响应: {data}")

                # Check for success code
                if data.get("code") == 0 or str(data.get("code")) == "0":
                    verification_code = data.get("yzm") or data.get("msg") # Sometimes code might be in 'msg'
                    if verification_code and verification_code != "ok": # Check if code is meaningful
                        # Simple check to avoid generic success messages being treated as code
                        if len(verification_code) > 1 and verification_code.isalnum(): # Basic validation
                           self.log_message(f"获取到验证码: {verification_code}")
                           return verification_code
                        else:
                            self.log_message(f"收到消息 '{verification_code}'，继续等待验证码...")
                    else:
                        # API success but no code yet, or empty message
                        self.log_message("尚未收到验证码，继续等待...")

                # Check for specific "message not received yet" code (replace if needed)
                elif "尚未接收到短信" in data.get("msg", ""):
                    self.log_message("服务器尚未收到短信，继续等待...")

                # Handle other errors (like token expiry)
                else:
                    if self.handle_api_error(data, "获取验证码"):
                        # Token expired, re-login successful. Loop will continue with new token.
                        pass # Continue the while loop
                    else:
                        # Unhandled error or re-login failed
                        return None # Stop waiting

            except requests.exceptions.Timeout:
                self.log_message("获取验证码请求超时，将重试...")
            except Exception as e:
                self.log_message(f"获取验证码异常: {e}")
                # Consider stopping if the error is persistent

            # Wait before next poll
            time.sleep(5)

        self.log_message("验证码获取超时。")
        return None # Timeout reached

    def blacklist_phone(self):
        """将手机号码加入黑名单"""
        if not self.token or not self.server or not self.phone_number:
            self.log_message("拉黑失败：未登录、无服务器或无手机号。")
            return False

        self.log_message(f"尝试拉黑号码: {self.phone_number}")
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={PROJECT_ID}&phone={self.phone_number}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            self.log_message(f"拉黑响应: {data}")
            # Check for success code
            if data.get("code") == 0 or str(data.get("code")) == "0":
                self.log_message(f"手机号码 {self.phone_number} 已成功拉黑。")
                # Clear phone details after successful blacklist
                self.root.after(0, self.clear_phone_details)
                return True
            else:
                # Handle potential token expiry
                if self.handle_api_error(data, "拉黑手机号"):
                    return self.blacklist_phone() # Retry after re-login
                return False # Error handled, but blacklist failed
        except Exception as e:
            self.log_message(f"拉黑手机号码异常: {e}")
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

    def clear_phone_details(self):
        """Clears phone number and code from display and variables."""
        self.phone_number = None
        self.phone_var.set("尚未获取")
        self.code_var.set("尚未获取")
        self.update_ui_state(self.is_working) # Re-evaluate button states


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SmsApp(root)
    root.mainloop()
