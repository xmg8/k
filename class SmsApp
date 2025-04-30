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
import pyperclip

# ... (导入和配置保持不变, 确保导入 threading, CTkScrollableFrame) ...
import customtkinter
from customtkinter import CTkScrollableFrame # 明确导入
# ...
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
    
class PhoneEntryWidget(customtkinter.CTkFrame):
    """用于在列表中显示单个手机号信息的自定义控件"""
    def __init__(self, master, app_instance, phone_info, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app_instance
        self.phone_info = phone_info # 引用包含号码、状态等信息的字典

        self.grid_columnconfigure((1, 2, 3), weight=1) # 让标签和按钮列平均分配空间

        # 显示手机号
        self.phone_label = customtkinter.CTkLabel(self, text=phone_info['phone'], width=120, anchor="w")
        self.phone_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        # 显示状态
        self.status_var = StringVar(value=phone_info.get('status', '初始化...'))
        self.status_label = customtkinter.CTkLabel(self, textvariable=self.status_var, width=100, anchor="w")
        self.status_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        # 显示验证码 (初始为空)
        self.code_var = StringVar(value=phone_info.get('code', ''))
        self.code_label = customtkinter.CTkLabel(self, textvariable=self.code_var, width=80, anchor="w")
        self.code_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")

        # 操作按钮框架
        action_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=0, column=3, padx=5, pady=2, sticky="e")

        # 复制号码按钮
        self.copy_phone_btn = customtkinter.CTkButton(action_frame, text="复制号码", width=80, height=24, font=customtkinter.CTkFont(size=10), command=self._copy_phone)
        self.copy_phone_btn.pack(side=LEFT, padx=2)

        # 复制验证码按钮 (初始禁用)
        self.copy_code_btn = customtkinter.CTkButton(action_frame, text="复制验证码", width=90, height=24, font=customtkinter.CTkFont(size=10), command=self._copy_code, state=DISABLED)
        self.copy_code_btn.pack(side=LEFT, padx=2)

        # 拉黑按钮
        self.blacklist_btn = customtkinter.CTkButton(action_frame, text="拉黑", width=50, height=24, font=customtkinter.CTkFont(size=10), command=self._blacklist, fg_color="firebrick", hover_color="darkred")
        self.blacklist_btn.pack(side=LEFT, padx=2)

    def update_status(self, status):
        self.status_var.set(status)
        self.phone_info['status'] = status # 更新数据源

    def update_code(self, code):
        self.code_var.set(code)
        self.phone_info['code'] = code # 更新数据源
        self.copy_code_btn.configure(state=NORMAL if code else DISABLED) # 启用/禁用复制验证码按钮

    def disable_actions(self):
        """禁用所有操作按钮（例如拉黑后）"""
        self.copy_phone_btn.configure(state=DISABLED)
        self.copy_code_btn.configure(state=DISABLED)
        self.blacklist_btn.configure(state=DISABLED)

    def _copy_phone(self):
        self.app.copy_text(self.phone_info['phone'], "号码")

    def _copy_code(self):
        code = self.code_var.get()
        if code:
            self.app.copy_text(code, "验证码")

    def _blacklist(self):
        # 触发主 App 的拉黑流程，传递当前 phone_info
        self.app.start_blacklist_specific_phone(self.phone_info)


class SmsApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("无尽冬日接码工具 - 未登录")
        self.geometry("800x750") # 可能需要更宽更高
        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")

        self.token = None; self.server = None # API 相关
        self.is_working_global = False # 全局是否有任务在运行（用于禁用获取新号码）
        self.logged_in_user_id = None; self.logged_in_username = None; self.remaining_uses = 0
        self.current_project_id = None; self.current_project_name = "通用接码工具"

        self.active_phones = [] # 存储活动号码信息字典的列表
        self.phone_widgets = {} # 存储手机号 -> PhoneEntryWidget 实例的映射

        self._create_main_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_app_closing)
        self.withdraw()

        if not self.attempt_auto_login():
            self.after(100, self.show_login_window)

    def _create_main_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # 日志区域扩展

        # --- Top Control Frame ---
        top_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        top_frame.grid_columnconfigure(1, weight=1) # 让中间空白区域扩展

        # 获取号码按钮（移到顶部）
        self.get_phone_btn = customtkinter.CTkButton(top_frame, text="获取新号码", command=self.start_get_phone_thread, width=120, state=DISABLED)
        self.get_phone_btn.pack(side=LEFT, padx=5, pady=5)

        # 声音提示（移到顶部）
        self.sound_enabled_var = BooleanVar(value=True)
        sound_check = customtkinter.CTkCheckBox(top_frame, text="声音提示", variable=self.sound_enabled_var)
        sound_check.pack(side=LEFT, padx=10, pady=5)

        # 用户和次数信息（移到顶部右侧）
        user_info_frame = customtkinter.CTkFrame(top_frame, fg_color="transparent")
        user_info_frame.pack(side=RIGHT, padx=5, pady=5)
        self.username_var = StringVar(value="未登录");
        customtkinter.CTkLabel(user_info_frame, textvariable=self.username_var, anchor="e").pack(side=LEFT, padx=5)
        self.uses_var = StringVar(value="次数: --");
        customtkinter.CTkLabel(user_info_frame, textvariable=self.uses_var, anchor="e").pack(side=LEFT, padx=5)
        logout_btn = customtkinter.CTkButton(user_info_frame, text="注销", command=self.logout, width=60, height=24, font=customtkinter.CTkFont(size=10), fg_color="transparent", border_width=1, text_color=("gray10", "gray90"))
        logout_btn.pack(side=LEFT, padx=5)


        # --- 号码列表区域 ---
        list_frame = customtkinter.CTkFrame(self, corner_radius=10)
        list_frame.grid(row=1, column=0, padx=20, pady=10, sticky=NSEW)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        customtkinter.CTkLabel(list_frame, text="当前号码:", font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5,0))
        # 可滚动的框架用于放置号码条目
        self.phone_list_scrollable_frame = CTkScrollableFrame(list_frame, corner_radius=8)
        self.phone_list_scrollable_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.phone_list_scrollable_frame.grid_columnconfigure(0, weight=1) # 让内部控件可以横向填充

        # --- 日志区域 ---
        log_outer_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        log_outer_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky=NSEW)
        log_outer_frame.grid_rowconfigure(1, weight=1); log_outer_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(log_outer_frame, text="运行日志:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=0, pady=(0,5), sticky="w")
        self.log_text = customtkinter.CTkTextbox(log_outer_frame, wrap=WORD, state=DISABLED, corner_radius=8, height=150) # 固定日志高度
        self.log_text.grid(row=1, column=0, sticky=NSEW)

        # --- 状态栏 ---
        self.status_var = StringVar(value="请先登录.")
        status_bar = customtkinter.CTkLabel(self, textvariable=self.status_var, height=25, anchor="w", padx=10)
        status_bar.grid(row=3, column=0, sticky=EW)

    def add_phone_entry_widget(self, phone_info):
        """在列表中添加一个新的号码条目控件"""
        phone = phone_info['phone']
        if phone in self.phone_widgets: return # 防止重复添加

        widget = PhoneEntryWidget(self.phone_list_scrollable_frame, self, phone_info, corner_radius=5, border_width=1)
        widget.pack(fill=X, padx=5, pady=2) # 使用 pack 布局在滚动框架内
        self.phone_widgets[phone] = widget

    def remove_phone_entry_widget(self, phone):
        """从列表中移除一个号码条目控件"""
        widget = self.phone_widgets.pop(phone, None)
        if widget:
            widget.destroy()

    def update_phone_entry_status(self, phone, status, code=None):
        """更新列表中特定号码的状态和验证码"""
        widget = self.phone_widgets.get(phone)
        if widget:
            widget.update_status(status)
            if code is not None:
                widget.update_code(code)
            if status in ["已拉黑", "获取超时", "获取失败"]: # 禁用操作
                widget.disable_actions()

    # --- 修改后的登录成功回调 ---
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
        self.deiconify(); self.title(f"{self.current_project_name} - 用户: {username}")
        self.username_var.set(username); self.uses_var.set(f"次数: {self.remaining_uses}") # 修改显示文本
        self.status_var.set("登录成功，正在初始化 API...")
        self.log_message("登录成功。")
        self.start_initial_login_thread()
        self.update_ui_state(False)
        self.lift(); self.focus_force()

    # --- 修改后的自动登录 ---
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
                    # 延迟调用 on_login_success
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
    def update_ui_state(self, working_global): # 参数改为 working_global
        """根据全局工作状态、登录状态和剩余次数启用/禁用 GUI 元素"""
        self.is_working_global = working_global # 更新全局状态
        is_logged_in = bool(self.logged_in_user_id)
        # 获取新号码按钮：未登录、全局忙碌、次数不足或未配置项目时禁用
        can_get_phone = is_logged_in and not working_global and self.remaining_uses > 0 and self.current_project_id
        get_phone_state = NORMAL if can_get_phone else DISABLED

        try:
            self.get_phone_btn.configure(state=get_phone_state)
            # 其他按钮的状态由 PhoneEntryWidget 内部管理，这里只更新全局状态栏
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
    def start_initial_login_thread(self):
        self.set_status("正在初始化 API 连接...")
        thread = threading.Thread(target=self._initial_login_task, daemon=True); thread.start()

    def start_get_phone_thread(self):
        """获取一个新的手机号"""
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if self.is_working_global: self.log_message("提示：请等待当前操作完成。"); return # 使用全局状态
        if self.remaining_uses <= 0: messagebox.showwarning("次数不足", "您的剩余使用号码数量不足，请联系管理员充值。"); self.log_message("可用号码数量不足，请联系管理员充值。"); return
        if not self.current_project_id: messagebox.showerror("错误", "当前用户未配置项目"+ADMIN_CONTACT_MSG); self.log_message("错误：未配置项目，无法获取号码。", level="ERROR"); return
        if not self.token or not self.server: messagebox.showerror("错误", "API 连接未就绪"+ADMIN_CONTACT_MSG); return

        self.update_ui_state(True) # 设置全局忙碌状态
        self.log_message(f"开始获取手机号 (项目ID: {self.current_project_id}, 剩余: {self.remaining_uses})...")
        thread = threading.Thread(target=self._get_phone_task, daemon=True); thread.start()

    def start_individual_code_fetch(self, phone_info):
        """为单个号码启动验证码获取线程"""
        phone = phone_info['phone']
        self.log_message(f"开始为 {phone} (项目ID: {self.current_project_id}) 获取验证码...")
        self.after(0, self.update_phone_entry_status, phone, "等待验证码...") # 更新列表项状态

        phone_info['stop_event'] = threading.Event() # 创建停止事件
        thread = threading.Thread(target=self._get_individual_code_task,
                                  args=(phone_info,), # 传递整个字典
                                  daemon=True)
        phone_info['thread'] = thread # 存储线程引用
        thread.start()

    def start_blacklist_specific_phone(self, phone_info):
        """启动拉黑特定号码的后台线程"""
        phone = phone_info['phone']
        if not self.logged_in_user_id: messagebox.showerror("错误", "请先登录。"); return
        if phone_info.get('status') == '已拉黑': return # 避免重复拉黑

        # --- 停止可能在运行的验证码获取线程 ---
        stop_event = phone_info.get('stop_event')
        if stop_event: stop_event.set()
        # --- 结束停止 ---

        if messagebox.askyesno("确认", f"确定要拉黑号码 {phone} 吗？", parent=self.phone_widgets.get(phone)): # parent 设为对应控件
            self.log_message(f"尝试拉黑号码: {phone} (项目ID: {self.current_project_id})")
            self.after(0, self.update_phone_entry_status, phone, "正在拉黑...") # 更新列表项状态
            # 启动后台线程进行拉黑
            thread = threading.Thread(target=self._blacklist_specific_task, args=(phone_info,), daemon=True)
            thread.start()
        else:
            if stop_event: stop_event.clear() # 用户取消，清除停止信号
            self.log_message(f"取消拉黑号码: {phone}")

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
        """获取单个手机号并启动其验证码监听"""
        phone_info = None
        try:
            phone = self.get_phone_number() # 获取号码
            if phone:
                # --- 创建 phone_info 字典 ---
                phone_info = {
                    'phone': phone,
                    'status': '初始化...', # 初始状态
                    'code': None,
                    'project_id': self.current_project_id,
                    'thread': None,
                    'stop_event': None
                }
                self.active_phones.append(phone_info) # 添加到活动列表
                self.after(0, self.add_phone_entry_widget, phone_info) # 在主线程添加 UI 条目
                # --- 结束创建 ---
                self._play_sound_if_enabled(SUCCESS_SOUND_ALIAS)
                self.log_message(f"号码 {phone} 获取成功，开始接收验证码...")
                # --- 立即启动该号码的验证码获取 ---
                self.start_individual_code_fetch(phone_info)
                # --- 结束启动 ---
            else: # 获取号码失败（致命错误）
                self.after(0, lambda: self.update_phone_entry_status(None, "获取失败")) # 更新全局状态？或添加错误条目？
        except Exception:
            self.log_message(GENERIC_ERROR_MSG, level="ERROR")
            self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
            # 获取单个号码任务结束，释放全局工作状态
            self.after(0, self.update_ui_state, False)

    def _get_individual_code_task(self, phone_info):
        """后台为单个号码获取验证码"""
        phone = phone_info['phone']
        project_id = phone_info['project_id']
        stop_event = phone_info['stop_event']
        code = None
        try:
            # 调用修改后的 wait_for_verification_code
            code = self.wait_for_verification_code(phone, project_id, stop_event, timeout=200)

            if code: # 成功获取
                self.after(0, self.update_phone_entry_status, phone, "获取成功", code)
                self._play_sound_if_enabled(SUCCESS_SOUND_ALIAS)
                if not self._decrement_usage(phone, project_id, code): # 传递号码和项目ID及验证码
                     messagebox.showerror("错误", f"号码 {phone} 扣减次数失败"+ADMIN_CONTACT_MSG)
                     # 即使扣减失败，也标记为成功获取，但次数可能不准
            elif stop_event and stop_event.is_set(): # 被手动中断
                self.after(0, self.update_phone_entry_status, phone, "已中断")
            else: # Timeout
                self.log_message(f"号码 {phone} 验证码获取超时。")
                self.after(0, self.update_phone_entry_status, phone, "获取超时")
                self.log_message(f"自动拉黑号码: {phone}")
                self.blacklist_phone(phone, project_id) # 传递号码和项目ID

        except Exception:
            self.after(0, self.update_phone_entry_status, phone, "获取异常")
            self.log_message(GENERIC_ERROR_MSG, level="ERROR")
            # self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)) # 避免过多弹窗

    def _blacklist_specific_task(self, phone_info):
        """后台执行特定号码的拉黑操作"""
        phone = phone_info['phone']
        project_id = phone_info['project_id']
        try:
            success = self.blacklist_phone(phone, project_id) # 调用修改后的拉黑函数
            if success:
                self.after(0, self.update_phone_entry_status, phone, "已拉黑")
                # 可以在这里从 active_phones 移除，或者保留已拉黑状态
                # self.active_phones.remove(phone_info)
                # self.after(0, self.remove_phone_entry_widget, phone)
            else:
                self.after(0, self.update_phone_entry_status, phone, "拉黑失败")
        except Exception:
             self.log_message(GENERIC_ERROR_MSG, level="ERROR")
             self.after(0, self.update_phone_entry_status, phone, "拉黑异常")
             # self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG))
        finally:
             pass # 拉黑任务不影响全局 working 状态

    # --- 数据库交互方法 (带重试) ---
    def _get_db_connection(self):
        # ... (保持不变) ...
        last_error = None
        for attempt in range(DB_RETRY_COUNT):
            try:
                conn = mysql.connector.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE, connect_timeout=5)
                if conn.is_connected(): return conn
            except MySQLError as e: last_error = e; time.sleep(DB_RETRY_DELAY)
            except Exception as e: last_error = e; break
        self.log_message(GENERIC_ERROR_MSG, level="ERROR"); messagebox.showerror("数据库连接失败", GENERIC_ERROR_MSG + f"\n(重试 {DB_RETRY_COUNT} 次失败)"); return None

    def _decrement_usage(self, phone_number, project_id, verification_code): # 添加参数
        """在 MySQL 数据库中将当前用户的剩余次数减 1，并记录日志。返回 True/False"""
        if not self.logged_in_user_id: return False
        conn = self._get_db_connection(); cursor = None
        if not conn: return False
        try:
            cursor = conn.cursor()
            conn.start_transaction()
            sql_update = "UPDATE users SET remaining_uses = GREATEST(0, remaining_uses - 1) WHERE id = %s"
            cursor.execute(sql_update, (self.logged_in_user_id,))
            # --- 修改：使用传入的参数记录日志 ---
            sql_insert_log = """
                INSERT INTO usage_logs (user_id, phone_number, project_id, verification_code, usage_timestamp)
                VALUES (%s, %s, %s, %s, NOW())
            """
            log_data = (self.logged_in_user_id, phone_number, project_id, verification_code)
            cursor.execute(sql_insert_log, log_data)
            # --- 结束修改 ---
            conn.commit()
            if self.remaining_uses > 0: self.remaining_uses -= 1
            self._write_usage_cache(self.remaining_uses)
            self.log_message(f"号码 {phone_number} 次数已扣减，剩余: {self.remaining_uses}")
            self.after(0, lambda: self.uses_var.set(f"次数: {self.remaining_uses}")) # 更新 UI
            return True
        except MySQLError: conn.rollback(); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); return False
        except Exception: conn.rollback(); self.log_message(GENERIC_ERROR_MSG, level="ERROR"); return False
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    # --- 本地缓存方法 (保持不变) ---
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

    # --- API 交互方法 (需要传递 phone 和 project_id) ---
    def try_login(self): # API 登录保持不变
        for s in SERVERS:
            login_url = f"{s}/sms/?api=login&user={API_ACCOUNT}&pass={API_PASSWORD}"
            try:
                response = requests.get(login_url, headers=headers, timeout=15, verify=True)
                response.raise_for_status(); data = response.json()
                if data.get("code") == 0 or str(data.get("code")) == "0": self.server = s; self.token = data["token"]; return
            except requests.exceptions.RequestException: pass
            except Exception: pass
        self.server = None; self.token = None; raise Exception("API 登录失败")
    def handle_api_error(self, data, operation_name): # 保持不变
        error_code = data.get("code"); error_msg = data.get('msg', '未知错误')
        is_waiting_msg = "尚未接收" in error_msg or "等待" == error_msg or "没有可用" in error_msg
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE: self.log_message("API 令牌过期，尝试重连..."); self.token = None
        elif error_code != 0 and str(error_code) != "0" and not is_waiting_msg: pass
        if str(error_code) == TOKEN_EXPIRED_ERROR_CODE:
            try: self.try_login(); return True
            except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("API 错误", "API 令牌过期且无法自动重新登录"+ADMIN_CONTACT_MSG)); return False
        if error_code != 0 and str(error_code) != "0" and not is_waiting_msg and str(error_code) != TOKEN_EXPIRED_ERROR_CODE: return False
        return True
    def get_phone_number(self): # 获取单个号码
        if not self.token or not self.server: self.log_message("API 未初始化"+ADMIN_CONTACT_MSG, level="ERROR"); return None
        if not self.current_project_id: self.log_message("未配置项目"+ADMIN_CONTACT_MSG, level="ERROR"); return None
        url = f"{self.server}/sms/?api=getPhone&token={self.token}&sid={self.current_project_id}"
        # 不再无限循环，尝试一次获取
        try:
            response = requests.get(url, headers=headers, timeout=20, verify=True)
            data = response.json(); code = data.get("code"); msg = data.get("msg", "")
            if code == 0 or str(code) == "0":
                phone = data.get("phone")
                if phone: return phone # 直接返回号码
                else: self.log_message("API 未返回号码"); return None # 记录日志并返回 None
            elif str(code) == "-1" and ("没有可用手机号" in msg or "请稍后再试" in msg or "等待" == msg):
                 self.log_message(f"暂时无号或需等待({msg})"); return None # 记录日志并返回 None
            else:
                if self.handle_api_error(data, "获取手机号"):
                    # 令牌刷新后，需要调用者重试整个 get_phone_task
                    self.log_message("令牌已刷新，请重试获取号码。")
                    return None
                else: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("API 错误", "获取手机号失败"+ADMIN_CONTACT_MSG)); return None
        except requests.exceptions.RequestException: self.log_message("获取手机号网络错误"+ADMIN_CONTACT_MSG, level="ERROR"); return None # 网络错误视为致命
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return None
    def wait_for_verification_code(self, phone, project_id, stop_event, timeout=200): # 添加参数
        """等待特定号码的验证码"""
        if not self.token or not self.server: return None
        start_time = time.time(); polling_interval = 4
        while time.time() - start_time < timeout:
            if stop_event and stop_event.is_set(): self.log_message(f"号码 {phone} 获取验证码被中断。"); return None # 检查停止事件
            if not self.token: return None
            params = {"api": "getMessage", "token": self.token, "sid": project_id, "phone": phone} # 使用传入的参数
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
    def blacklist_phone(self, phone, project_id): # 添加参数
        """将特定手机号加入黑名单"""
        if not self.token or not self.server: return False
        url = f"{self.server}/sms/?api=addBlacklist&token={self.token}&sid={project_id}&phone={phone}" # 使用传入的参数
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            data = response.json()
            if data.get("code") == 0 or str(data.get("code")) == "0": self.log_message(f"号码 {phone} 已拉黑。"); self.after(0, self.clear_phone_details_ui, phone); return True # 调用 UI 清理
            else:
                if self.handle_api_error(data, f"拉黑手机号({phone})"): return self.blacklist_phone(phone, project_id) # 重试时传递参数
                self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda p=phone: messagebox.showerror("操作失败", f"拉黑号码 {p} 失败"+ADMIN_CONTACT_MSG)); return False
        except requests.exceptions.RequestException: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("网络错误", "拉黑操作网络异常"+ADMIN_CONTACT_MSG)); return False
        except Exception: self.log_message(GENERIC_ERROR_MSG, level="ERROR"); self.after(0, lambda: messagebox.showerror("严重错误", GENERIC_ERROR_MSG)); return False

    # --- GUI 辅助方法 ---
    def copy_text(self, text_to_copy, text_type="文本"): # 通用复制方法
        """复制文本到剪贴板"""
        if text_to_copy:
            try:
                pyperclip.copy(text_to_copy)
                self.log_message(f"{text_type} {text_to_copy} 已复制。")
                self.set_status(f"{text_type}已复制。")
            except Exception: self.log_message(f"复制{text_type}失败。")
        else: self.log_message(f"没有{text_type}可复制。")
    def copy_phone(self): # 保留旧接口，调用新方法
        self.copy_text(self.phone_number, "号码") # 注意：这里可能需要调整，因为 phone_number 现在不代表唯一号码
    def copy_code(self): # 保留旧接口，调用新方法
        code = self.code_var.get() # 注意：这里也需要调整
        if code and code not in ["尚未获取", "获取失败", "获取异常", "获取超时或失败", "正在获取...", "等待获取...", "已拉黑"]:
             self.copy_text(code, "验证码")
        else: self.log_message("没有有效的验证码可复制。")
    def clear_phone_details_ui(self, phone): # 清理特定号码的 UI
        """拉黑成功后清理特定号码的 UI 显示"""
        widget = self.phone_widgets.get(phone)
        if widget:
            widget.update_status("已拉黑")
            widget.disable_actions()
        # 从 active_phones 列表中移除对应项 (可选)
        self.active_phones = [p for p in self.active_phones if p['phone'] != phone]

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
        # --- 停止所有后台线程 ---
        for phone_info in self.active_phones:
            stop_event = phone_info.get('stop_event')
            if stop_event: stop_event.set()
        # --- 结束停止 ---
        self._delete_usage_cache()
        self.destroy()
    def logout(self):
        if self.is_working_global: messagebox.showwarning("请稍候", "请等待当前操作完成后再注销。"); return
        # --- 停止所有后台线程 ---
        for phone_info in self.active_phones:
            stop_event = phone_info.get('stop_event')
            if stop_event: stop_event.set()
        # --- 结束停止 ---
        if self.logged_in_username:
            try:
                keyring.delete_password(KEYRING_SERVICE_NAME, self.logged_in_username)
                keyring.delete_password(KEYRING_SERVICE_NAME, "last_user")
                keyring.delete_password(KEYRING_SERVICE_NAME, "auto_login")
            except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError): pass
        self.token = None; self.phone_number = None; self.server = None # 清理旧的单一变量
        self.logged_in_user_id = None; self.logged_in_username = None; self.remaining_uses = 0
        self.current_project_id = None; self.current_project_name = self.default_title
        self._delete_usage_cache()
        # --- 清理号码列表 ---
        for widget in self.phone_widgets.values(): widget.destroy()
        self.phone_widgets.clear()
        self.active_phones.clear()
        # --- 结束清理 ---
        self.title(f"{self.default_title} - 未登录"); self.username_var.set("未登录"); self.uses_var.set("--")
        self.update_ui_state(False)
        self.log_message("用户已注销。"); self.status_var.set("已注销，请登录。")
        self.withdraw(); self.show_login_window()


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
                # --- 修改：检查次数 ---
                if user_row["remaining_uses"] <= 0:
                    messagebox.showwarning("登录失败", "您的可用次数不足，请联系管理员充值。", parent=self)
                    if auto_login: # 如果是勾选了自动登录时失败，清除标志
                        try: keyring.delete_password(KEYRING_SERVICE_NAME, "auto_login")
                        except (keyring.errors.KeyringError, keyring.errors.PasswordDeleteError): pass
                    return
                # --- 结束检查 ---
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
