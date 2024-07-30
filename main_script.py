import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
import requests
import random
import time
import psutil
import os
import webbrowser
from threading import Thread
from requests.exceptions import ConnectionError, Timeout, SSLError
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from tkhtmlview import HTMLLabel
import tkinter.messagebox

# 忽略SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("XMG游戏团队")

        self.running = False  # 脚本运行状态

        self.show_welcome_message()  # 显示欢迎消息

        self.style = ttk.Style()
        self.style.configure('TButton', font=('Helvetica', 12))
        self.style.configure('TLabel', font=('Helvetica', 12))
        self.style.configure('TEntry', font=('Helvetica', 12))

        self.announcement_label = ttk.Label(root, text="公告:", anchor='w')
        self.announcement_label.pack(fill='x', padx=10, pady=5)

        self.announcement_html = HTMLLabel(root, html="<p>Loading announcement...</p>", width=80, height=10)
        self.announcement_html.pack(fill='x', padx=10, pady=5)

        self.refresh_button = ttk.Button(root, text="刷新公告", command=self.refresh_announcement)
        self.refresh_button.pack(pady=5)

        self.id_entry_label = ttk.Label(root, text="输入玩家ID:")
        self.id_entry_label.pack(pady=5)

        self.id_entry = ttk.Entry(root, width=50)
        self.id_entry.pack(pady=5)

        self.add_id_button = ttk.Button(root, text="添加ID", command=self.add_id)
        self.add_id_button.pack(pady=5)

        self.start_button = ttk.Button(root, text="开始领取", command=self.start_script)
        self.start_button.pack(pady=5)

        self.stop_button = ttk.Button(root, text="停止领取", command=self.stop_script)
        self.stop_button.pack(pady=5)

        self.automanage_button = ttk.Button(root, text="全自动托管", command=self.open_automanage)
        self.automanage_button.pack(pady=5)

        self.text_area = ScrolledText(root, wrap=tk.WORD, width=100, height=20, font=('Helvetica', 12))
        self.text_area.pack(pady=10, padx=10)

        self.create_file_if_not_exists('ids.txt', '示例玩家ID\n')
        self.create_file_if_not_exists('results.txt')
        self.create_file_if_not_exists('ip.txt')

        self.refresh_announcement()

    def create_file_if_not_exists(self, filename, content=""):
        if not os.path.exists(filename):
            with open(filename, 'w') as file:
                file.write(content)

    def log(self, message):
        self.text_area.insert(tk.END, message + '\n')
        self.text_area.see(tk.END)
        self.root.update()

    def add_id(self):
        player_id = self.id_entry.get()
        if player_id:
            with open('ids.txt', 'a') as file:
                file.write(player_id + '\n')
            self.log(f"添加玩家ID: {player_id}")
            self.id_entry.delete(0, tk.END)
        else:
            self.log("未输入玩家ID")

    def read_ids_and_passwords(self, filename):
        ids_and_passwords = []
        try:
            with open(filename, 'r') as file:
                for line in file:
                    parts = line.strip().split()
                    if len(parts) == 1:
                        ids_and_passwords.append((parts[0], None))  # 只有ID，没有密码
                    elif len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 6:
                        ids_and_passwords.append((parts[0], parts[1]))  # ID和6位数字密码
        except FileNotFoundError:
            self.log(f"文件 {filename} 未找到")
        return ids_and_passwords

    def read_results(self, filename):
        successful_ids = set()
        failed_ids = set()
        current_date = datetime.now().strftime('%Y-%m-%d')
        try:
            with open(filename, 'r') as file:
                for line in file.readlines():
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    result_date = parts[0].split('T')[0]
                    player_id = parts[3]  # 假设ID总是位于第四个位置
                    if result_date == current_date:
                        if "签到成功" in line or ("第" in line and "天签到成功" in line) or "没有可领取的每日签到任务或任务已完成" in line or "重试没有可领取的每日签到任务或任务已完成" in line:
                            successful_ids.add(player_id)
                        else:
                            failed_ids.add(player_id)
        except FileNotFoundError:
            self.log(f"文件 {filename} 未找到")

        return successful_ids, failed_ids

    def login(self, player_id, password, max_retries=3):
        url = 'https://ls.store.koppay.net/api/v2/store/login/player'
        payload = {'player_id': player_id, 'site_id': 22}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        if password:
            payload['password'] = password

        for attempt in range(max_retries):
            try:
                with requests.Session() as session:
                    response = session.post(url, json=payload, headers=headers, verify=False, timeout=10)
                    if response.status_code == 200 and 'Authorization' in response.headers:
                        return response.headers['Authorization']
            except (ConnectionError, Timeout, SSLError) as e:
                time.sleep(2)  # 等待一段时间后重试
        return None

    def get_checkin_details(self, token, player_id, max_retries=3):
        url = f'https://ls.store.koppay.net/api/v2/store/sale/biz/get/checkin/details?project_id=15&player_id={player_id}'
        headers = {
            'Authorization': token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        for attempt in range(max_retries):
            try:
                with requests.Session() as session:
                    response = session.get(url, headers=headers, verify=False, timeout=10)
                    return response.json() if response.status_code == 200 else None
            except (ConnectionError, Timeout, SSLError) as e:
                time.sleep(2)  # 等待一段时间后重试
        return None

    def daily_checkin(self, token, player_id, checkin_day, max_retries=3):
        url = 'https://ls.store.koppay.net/api/v2/store/sale/biz/add/checkin/create'
        headers = {
            'Authorization': token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        payload = {'project_id': 15, 'player_id': player_id, 'checkin_day': checkin_day}

        for attempt in range(max_retries):
            try:
                with requests.Session() as session:
                    response = session.post(url, json=payload, headers=headers, verify=False, timeout=10)
                    return response.json() if response.status_code == 200 else None
            except (ConnectionError, Timeout, SSLError) as e:
                time.sleep(2)  # 等待一段时间后重试
        return None

    def print_system_usage(self):
        process = psutil.Process()
        mem_info = process.memory_info()
        cpu_usage = psutil.cpu_percent(interval=1)

        self.log(f"当前内存使用: {mem_info.rss / 1024 ** 2:.2f} MB")
        self.log(f"当前CPU使用: {cpu_usage:.2f} %")

    def refresh_announcement(self):
        url = 'http://qd.xmg9.top/announcement.html'  # 公告URL
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            announcement = response.text.strip()
            self.announcement_html.set_html(announcement)
        except Exception as e:
            self.log(f"获取公告失败: {e}")

    def start_script(self):
        self.running = True
        self.log("开始领取任务")
        self.script_thread = Thread(target=self.run_script)
        self.script_thread.start()

    def stop_script(self):
        self.running = False
        self.log("停止领取任务")

    def open_automanage(self):
        webbrowser.open('http://www.xmg888.top')

    def run_script(self):
        ids_and_passwords = self.read_ids_and_passwords('ids.txt')
        unique_ids_and_passwords = list(set(ids_and_passwords))
        successful_ids, failed_ids = self.read_results('results.txt')

        # 过滤掉已经成功签到的ID
        ids_to_run = [(id, pwd) for id, pwd in unique_ids_and_passwords if id not in successful_ids]

        total_ids = len(ids_to_run)
        self.log(f"需要执行任务的ID总数: {total_ids}")

        for idx, (player_id, password) in enumerate(ids_to_run):
            if not self.running:
                break
            
            current_task_number = idx + 1
            self.log(f"正在执行第 {current_task_number}/{total_ids} 个任务: 玩家ID {player_id}")

            token = self.login(player_id, password)
            if not token:
                self.log(f"玩家 {player_id} 登录失败，停止执行该ID任务")
                with open('results.txt', 'a') as file:
                    file.write(f"{datetime.now()} 玩家 {player_id} 登录失败\n")
                failed_ids.add(player_id)
                continue

            checkin_details = self.get_checkin_details(token, player_id)
            if not checkin_details:
                self.log(f"玩家 {player_id} 获取每日签到详情失败，停止执行该ID任务")
                with open('results.txt', 'a') as file:
                    file.write(f"{datetime.now()} 玩家 {player_id} 获取每日签到详情失败\n")
                failed_ids.add(player_id)
                continue

            no_task = True
            if checkin_details and checkin_details['code'] == 1:
                for day_info in checkin_details['data']['activity_gifts_list']:
                    if day_info['status'] == 1:  # 检查是否可以领取
                        no_task = False
                        checkin_day = int(day_info['name_language_code'].replace('第', '').replace('日', ''))
                        for attempt in range(1, 4):
                            checkin_response = self.daily_checkin(token, player_id, checkin_day)
                            if checkin_response and checkin_response['code'] == 1:
                                self.log(f"玩家 {player_id} 第{checkin_day}天签到成功")
                                with open('results.txt', 'a') as file:
                                    file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到成功\n")
                                successful_ids.add(player_id)
                                break
                            else:
                                self.log(f"玩家 {player_id} 第{checkin_day}天签到失败，重试 {attempt}/3 次: {checkin_response}")
                                time.sleep(2)
                        else:
                            self.log(f"玩家 {player_id} 第{checkin_day}天签到最终失败")
                            with open('results.txt', 'a') as file:
                                file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到最终失败\n")
                            failed_ids.add(player_id)
            if no_task:
                self.log(f"玩家 {player_id} 没有可领取的每日签到任务或任务已完成")
                with open('results.txt', 'a') as file:
                    file.write(f"{datetime.now()} 玩家 {player_id} 没有可领取的每日签到任务或任务已完成\n")
                successful_ids.add(player_id)

            # 添加延迟，模拟人类操作
            time.sleep(random.randint(3, 6))

        self.log(f"成功的ID总数: {len(successful_ids)}")
        self.log(f"失败的ID总数: {len(failed_ids)}")

    def show_welcome_message(self):
        welcome_message = "欢迎使用XMG游戏团队工具。\n请在下面的输入框中输入玩家ID并点击'添加ID'按钮添加，然后点击'开始领取'按钮运行脚本。"
        tkinter.messagebox.showinfo("欢迎", welcome_message)

if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
