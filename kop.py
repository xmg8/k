import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkhtmlview import HTMLLabel
import requests
import threading
import time
import os
import json
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 忽略SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# 设置公告URL
announcement_url = 'https://gg.xmg888.top/'

# 设置上传玩家ID的API URL
upload_url = 'https://kopqd.xmg888.top/api/upload_id.php'

# 设置服务器获取日志的API URL
log_url = 'https://kopqd.xmg888.top/api/get_logs.php'

# 卡密验证和状态检查的URL
verify_code_url = 'https://kopqd.xmg888.top/api/verify_code.php'

# 配置文件路径
config_file = 'config.json'


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("XMG游戏团队")
        self.root.geometry("800x600")  # 设置窗口大小

        self.config = self.load_config()
        self.is_running = False

        self.create_widgets()

    def create_widgets(self):
        # 公告显示区
        self.announcement_frame = tk.Frame(self.root, width=600, height=200)
        self.announcement_frame.grid(row=0, column=0, columnspan=6, padx=10, pady=10, sticky='nsew')
        self.announcement_label = HTMLLabel(self.announcement_frame, html="<p>公告内容加载中...</p>")
        self.announcement_label.pack(fill='both', expand=True)

        # 刷新公告按钮
        self.refresh_button = tk.Button(self.root, text="刷新公告", command=self.refresh_announcement, bg='#90EE90')
        self.refresh_button.grid(row=1, column=0, padx=5, pady=5)

        # 卡密输入框
        self.code_entry = tk.Entry(self.root)
        self.code_entry.grid(row=1, column=1, padx=5, pady=5)

        # 登录按钮
        self.login_button = tk.Button(self.root, text="登录", command=self.login, bg='#87CEFA')
        self.login_button.grid(row=1, column=2, padx=5, pady=5)

        # 显示剩余时间/次数
        self.status_label = tk.Label(self.root, text="状态: 未登录", bg='#F0E68C')
        self.status_label.grid(row=1, column=3, padx=5, pady=5)

        # 玩家ID输入框
        self.id_entry = tk.Entry(self.root)
        self.id_entry.grid(row=2, column=0, padx=5, pady=5)

        # 添加ID按钮
        self.add_id_button = tk.Button(self.root, text="添加ID", command=self.add_id, bg='#ADD8E6')
        self.add_id_button.grid(row=2, column=1, padx=5, pady=5)

        # 开始领取按钮
        self.start_button = tk.Button(self.root, text="开始领取", command=self.start_retrieve, bg='#FFA500')
        self.start_button.grid(row=2, column=2, padx=5, pady=5)

        # 停止领取按钮
        self.stop_button = tk.Button(self.root, text="停止领取", command=self.stop_retrieve, bg='#FF6347')
        self.stop_button.grid(row=2, column=3, padx=5, pady=5)

        # 全自动托管按钮
        self.auto_manage_button = tk.Button(self.root, text="全自动托管", command=self.open_auto_manage, bg='#9370DB')
        self.auto_manage_button.grid(row=2, column=4, padx=5, pady=5)

        # 日志显示区
        self.log_text = scrolledtext.ScrolledText(self.root, width=80, height=20)
        self.log_text.grid(row=3, column=0, columnspan=6, padx=10, pady=10, sticky='nsew')

        # 设置列和行的权重
        for i in range(6):
            self.root.grid_columnconfigure(i, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

        # 尝试自动登录
        if self.config.get('code'):
            self.code_entry.insert(0, self.config['code'])
            self.login()

    def load_config(self):
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return {}

    def save_config(self):
        with open(config_file, 'w') as f:
            json.dump(self.config, f)

   def login(self):
       code = self.code_entry.get().strip()
       if not code:
        messagebox.showwarning("输入错误", "请输入有效的卡密")
        return

      self.config['code'] = code
      self.save_config()

      response = self.verify_code(code)
        if response and response.get('status') == 'success':
        self.log("卡密验证成功")
        self.status_label.config(text=f"状态: {response.get('message')}")
       elif response:
        self.log(f"卡密验证失败: {response.get('message')}", "error")
       else:
        self.log("卡密验证失败: 未收到有效响应", "error")


    def verify_code(self, code):
        data = {'code': code}
        try:
            response = requests.post(verify_code_url, data=data, timeout=10, verify=False)
            return response.json()
        except requests.exceptions.RequestException as e:
            self.log(f"卡密验证请求失败: {e}", "error")
            return None

    def add_id(self):
        player_id = self.id_entry.get().strip()
        if player_id:
            with open('ids.txt', 'a') as file:
                file.write(player_id + '\n')
            self.log(f"玩家ID {player_id} 已添加")
            self.id_entry.delete(0, tk.END)
        else:
            messagebox.showwarning("输入错误", "请输入有效的玩家ID")

    def refresh_announcement(self):
        try:
            response = requests.get(announcement_url, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            announcement_content = soup.find("div", class_="announcement").prettify()
            self.announcement_label.set_html(announcement_content)
        except Exception as e:
            self.log(f"获取公告失败: {e}", "error")

    def start_retrieve(self):
        if not self.is_running:
            self.is_running = True
            self.log("开始领取任务")
            self.upload_thread = threading.Thread(target=self.run_upload_and_log)
            self.upload_thread.start()

    def stop_retrieve(self):
        if self.is_running:
            self.is_running = False
            self.log("停止领取任务")

    def open_auto_manage(self):
        import webbrowser
        webbrowser.open('https://www.xmg888.top')

    def log(self, message, level="info"):
        tag = level if level in ("info", "error") else "info"
        self.log_text.insert(tk.END, f"{message}\n", tag)
        self.log_text.see(tk.END)

    def run_upload_and_log(self):
        player_ids = self.read_ids('ids.txt')
        unique_player_ids = list(set(player_ids))

        self.log(f"读取到的ID总数: {len(unique_player_ids)}")

        # 上传所有玩家ID到服务器
        for idx, player_id in enumerate(unique_player_ids):
            if not self.is_running:
                break
            self.log(f"正在上传第 {idx + 1}/{len(unique_player_ids)} 个玩家ID: {player_id}")

            response = self.upload_player_id(player_id)
            if response and response.get('status') == 'success':
                self.log(f"玩家ID {player_id} 上传成功")
            else:
                self.log(f"玩家ID {player_id} 上传失败: {response.get('message')}", "error")

            time.sleep(1)

        self.log("开始监听服务器任务日志")
        self.listen_to_server_logs()

    def listen_to_server_logs(self):
        while self.is_running:
            try:
                response = requests.get(log_url, timeout=10, verify=False)
                if response.status_code == 200:
                    logs = response.json().get('logs', [])
                    for log in logs:
                        self.log(log)
                time.sleep(5)
            except requests.exceptions.RequestException as e:
                self.log(f"获取服务器日志失败: {e}", "error")
                break

    def read_ids(self, filename):
        player_ids = []
        try:
            with open(filename, 'r') as file:
                for line in file:
                    player_ids.append(line.strip())
        except FileNotFoundError:
            self.log(f"文件 {filename} 未找到")
        return player_ids

    def upload_player_id(self, player_id):
        data = {'player_id': player_id, 'code': self.config.get('code')}
        try:
            response = requests.post(upload_url, data=data, timeout=10, verify=False)
            return response.json()
        except requests.exceptions.RequestException as e:
            self.log(f"上传玩家ID请求失败: {e}", "error")
            return None


if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
