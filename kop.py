import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkhtmlview import HTMLLabel
import requests
import threading
import time
import os
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 忽略SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# 设置公告URL
announcement_url = 'https://gg.xmg888.top/'

# 设置上传玩家ID的API URL
upload_url = 'https://kopqd.xmg888.top/api/upload_id'

# 设置服务器获取日志的API URL
log_url = 'https://kopqd.xmg888.top/api/get_logs'

# 卡密验证和状态检查的URL
verify_code_url = 'https://kopqd.xmg888.top/api/verify_code'

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("XMG游戏团队")
        self.root.geometry("800x600")  # 设置窗口大小

        self.create_widgets()
        self.initialize_files()

        self.is_running = False
        self.current_code = None

    def create_widgets(self):
        # 公告显示区
        self.announcement_frame = tk.Frame(self.root, width=600, height=200)
        self.announcement_frame.grid(row=0, column=0, columnspan=6, padx=10, pady=10, sticky='nsew')
        self.announcement_label = HTMLLabel(self.announcement_frame, html="<p>公告内容加载中...</p>")
        self.announcement_label.pack(fill='both', expand=True)

        # 刷新公告按钮
        self.refresh_button = tk.Button(self.root, text="刷新公告", command=self.refresh_announcement, bg='#90EE90')
        self.refresh_button.grid(row=1, column=0, padx=5, pady=5)

        # 卡密输入框标签
        self.code_label = tk.Label(self.root, text="请输入卡密:")
        self.code_label.grid(row=1, column=1, padx=5, pady=5, sticky='e')

        # 卡密输入框
        self.code_entry = tk.Entry(self.root)
        self.code_entry.grid(row=1, column=2, padx=5, pady=5)

        # 玩家ID输入框标签
        self.id_label = tk.Label(self.root, text="请输入玩家ID:")
        self.id_label.grid(row=2, column=1, padx=5, pady=5, sticky='e')

        # 玩家ID输入框
        self.id_entry = tk.Entry(self.root)
        self.id_entry.grid(row=2, column=2, padx=5, pady=5)

        # 添加ID按钮
        self.add_id_button = tk.Button(self.root, text="添加ID", command=self.add_id, bg='#ADD8E6')
        self.add_id_button.grid(row=2, column=3, padx=5, pady=5)

        # 显示卡密剩余时间的标签
        self.time_label = tk.Label(self.root, text="卡密剩余时间: 未知")
        self.time_label.grid(row=1, column=3, padx=5, pady=5, sticky='w')

        # 开始领取按钮
        self.start_button = tk.Button(self.root, text="开始领取", command=self.start_retrieve, bg='#FFA500')
        self.start_button.grid(row=3, column=1, padx=5, pady=5)

        # 停止领取按钮
        self.stop_button = tk.Button(self.root, text="停止领取", command=self.stop_retrieve, bg='#FF6347')
        self.stop_button.grid(row=3, column=2, padx=5, pady=5)

        # 全自动托管按钮
        self.auto_manage_button = tk.Button(self.root, text="全自动托管", command=self.open_auto_manage, bg='#9370DB')
        self.auto_manage_button.grid(row=3, column=3, padx=5, pady=5)

        # 日志显示区
        self.log_text = scrolledtext.ScrolledText(self.root, width=80, height=20)
        self.log_text.grid(row=4, column=0, columnspan=6, padx=10, pady=10, sticky='nsew')

        # 设置列和行的权重
        for i in range(6):
            self.root.grid_columnconfigure(i, weight=1)
        self.root.grid_rowconfigure(4, weight=1)

    def initialize_files(self):
        self.ids_file = 'ids.txt'
        self.results_file = 'results.txt'
        self.create_file_if_not_exists(self.ids_file)
        self.create_file_if_not_exists(self.results_file)

    def create_file_if_not_exists(self, filename, content=""):
        if not os.path.exists(filename):
            with open(filename, 'w') as file:
                file.write(content)

    def add_id(self):
        player_id = self.id_entry.get().strip()
        code = self.code_entry.get().strip()
        if player_id and code:
            self.verify_code_and_add_id(player_id, code)
        else:
            messagebox.showwarning("输入错误", "请输入有效的玩家ID和卡密")

    def verify_code_and_add_id(self, player_id, code):
        data = {'code': code}
        try:
            response = requests.post(verify_code_url, json=data, timeout=10, verify=False)
            response_data = response.json()

            if response_data.get('status') == 'success':
                self.current_code = code  # 保存当前使用的卡密
                with open(self.ids_file, 'a') as file:
                    file.write(player_id + '\n')
                self.log(f"玩家ID {player_id} 已添加")
                self.id_entry.delete(0, tk.END)

                # 显示卡密的剩余时间
                remaining_time = response_data.get('remaining_time', '未知')
                self.time_label.config(text=f"卡密剩余时间: {remaining_time}")
            else:
                self.log(f"卡密验证失败: {response_data.get('message')}", "error")
        except Exception as e:
            self.log(f"卡密验证请求失败: {e}", "error")

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
        player_ids = self.read_ids(self.ids_file)
        unique_player_ids = list(set(player_ids))

        self.log(f"读取到的ID总数: {len(unique_player_ids)}")

        # 上传所有玩家ID到服务器
        for idx, player_id in enumerate(unique_player_ids):
            if not self.is_running:
                break

            # 在每个任务执行前检查卡密状态
            if not self.check_code_validity():
                self.log(f"卡密已失效，任务中止", "error")
                break

            self.log(f"正在上传第 {idx + 1}/{len(unique_player_ids)} 个玩家ID: {player_id}")

            response = self.upload_player_id(player_id)
            if response and response.get('status') == 'success':
                self.log(f"玩家ID {player_id} 上传成功")
            else:
                self.log(f"玩家ID {player_id} 上传失败: {response.get('message')}", "error")

            # 模拟人类操作延迟
            time.sleep(1)

        # 上传完成后开始监听服务器日志
        self.log("开始监听服务器任务日志")
        self.listen_to_server_logs()

    def check_code_validity(self):
        if not self.current_code:
            return False
        data = {'code': self.current_code}
        try:
            response = requests.post(verify_code_url, json=data, timeout=10, verify=False)
            response_data = response.json()
            return response_data.get('status') == 'success'
        except Exception as e:
            self.log(f"卡密验证请求失败: {e}", "error")
            return False

    def listen_to_server_logs(self):
        while self.is_running:
            try:
                response = requests.get(log_url, timeout=10, verify=False)
                if response.status_code == 200:
                    logs = response.json().get('logs', [])
                    for log in logs:
                        self.log(log)
                time.sleep(5)  # 每隔5秒获取一次日志
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
        data = {'player_id': player_id}
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
