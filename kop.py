import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkhtmlview import HTMLLabel
import requests
import threading
import random
import time
from datetime import datetime
import psutil
import os
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 忽略SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# 设置公告URL
announcement_url = 'http://152.136.171.223/'

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("XMG游戏团队")
        self.root.geometry("800x600")  # 设置窗口大小

        self.create_widgets()
        self.initialize_files()

        self.is_running = False

    def create_widgets(self):
        # 公告显示区
        self.announcement_frame = tk.Frame(self.root, width=600, height=200, bg='#f0f0f0', bd=2, relief="solid")
        self.announcement_frame.grid(row=0, column=0, columnspan=6, padx=10, pady=10, sticky='nsew')
        self.announcement_label = HTMLLabel(self.announcement_frame, html="<p>公告内容加载中...</p>", background='#f0f0f0')
        self.announcement_label.pack(fill='both', expand=True)

        # 刷新公告按钮
        self.refresh_button = tk.Button(self.root, text="刷新公告", command=self.refresh_announcement, bg='#4CAF50', fg='white')
        self.refresh_button.grid(row=1, column=0, padx=5, pady=5)

        # 玩家ID输入框
        self.id_entry = tk.Entry(self.root)
        self.id_entry.grid(row=1, column=1, padx=5, pady=5)

        # 添加ID按钮
        self.add_id_button = tk.Button(self.root, text="添加ID", command=self.add_id, bg='#2196F3', fg='white')
        self.add_id_button.grid(row=1, column=2, padx=5, pady=5)

        # 开始领取按钮
        self.start_button = tk.Button(self.root, text="开始领取", command=self.start_retrieve, bg='#FF9800', fg='white')
        self.start_button.grid(row=1, column=3, padx=5, pady=5)

        # 停止领取按钮
        self.stop_button = tk.Button(self.root, text="停止领取", command=self.stop_retrieve, bg='#f44336', fg='white')
        self.stop_button.grid(row=1, column=4, padx=5, pady=5)

        # 全自动托管按钮
        self.auto_manage_button = tk.Button(self.root, text="全自动托管", command=self.open_auto_manage, bg='#9C27B0', fg='white')
        self.auto_manage_button.grid(row=1, column=5, padx=5, pady=5)

        # 日志显示区
        self.log_text = scrolledtext.ScrolledText(self.root, width=80, height=20, bg='#ffffff')
        self.log_text.grid(row=2, column=0, columnspan=6, padx=10, pady=10, sticky='nsew')

        # 设置列和行的权重
        for i in range(6):
            self.root.grid_columnconfigure(i, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

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
        if player_id:
            with open(self.ids_file, 'a') as file:
                file.write(player_id + '\n')
            self.log(f"玩家ID {player_id} 已添加", "info")
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
            self.log("开始领取任务", "info")
            self.retrieve_thread = threading.Thread(target=self.run_script)
            self.retrieve_thread.start()

    def stop_retrieve(self):
        if self.is_running:
            self.is_running = False
            self.log("停止领取任务", "warning")

    def open_auto_manage(self):
        import webbrowser
        webbrowser.open('https://www.xmg888.top')

    def log(self, message, msg_type="info"):
        color = {"info": "black", "error": "red", "warning": "orange"}
        self.log_text.insert(tk.END, f"{message}\n", color[msg_type])
        self.log_text.see(tk.END)

    def run_script(self):
        ids_and_passwords = self.read_ids_and_passwords(self.ids_file)
        unique_ids_and_passwords = list(set(ids_and_passwords))
        successful_ids, failed_ids = self.read_results(self.results_file)

        # 过滤掉已经成功签到的ID
        ids_to_run = [(id, pwd) for id, pwd in unique_ids_and_passwords if id not in successful_ids]

        self.log(f"读取到的ID总数: {len(unique_ids_and_passwords)}", "info")
        self.log(f"成功的ID总数: {len(successful_ids)}", "info")
        self.log(f"失败的ID总数: {len(failed_ids)}", "info")
        self.log(f"需要执行任务的ID总数: {len(ids_to_run)}", "info")

        for idx, (player_id, password) in enumerate(ids_to_run):
            if not self.is_running:
                break
            self.log(f"正在执行第 {idx + 1}/{len(ids_to_run)} 个任务: 玩家ID {player_id}", "info")

            result_message = ""
            token = self.login(player_id, password)
            if not token:
                result_message = "领取失败"
                with open(self.results_file, 'a') as file:
                    file.write(f"{datetime.now()} 玩家 {player_id} 登录失败\n")
                failed_ids.add(player_id)
            else:
                checkin_details = self.get_checkin_details(token, player_id)
                if not checkin_details:
                    result_message = "领取失败"
                    with open(self.results_file, 'a') as file:
                        file.write(f"{datetime.now()} 玩家 {player_id} 获取每日签到详情失败\n")
                    failed_ids.add(player_id)
                else:
                    no_task = True
                    if checkin_details and checkin_details['code'] == 1:
                        for day_info in checkin_details['data']['activity_gifts_list']:
                            if day_info['status'] == 1:  # 检查是否可以领取
                                no_task = False
                                checkin_day = int(day_info['name_language_code'].replace('第', '').replace('日', ''))
                                for attempt in range(1, 6):
                                    checkin_response = self.daily_checkin(token, player_id, checkin_day)
                                    if checkin_response and checkin_response['code'] == 1:
                                        result_message = "领取成功"
                                        with open(self.results_file, 'a') as file:
                                            file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到成功\n")
                                        successful_ids.add(player_id)
                                        break
                                    else:
                                        self.log(f"第{checkin_day}天签到失败，重试 {attempt}/5 次: {checkin_response}", "warning")
                                        time.sleep(2)
                                else:
                                    result_message = "领取失败"
                                    with open(self.results_file, 'a') as file:
                                        file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到最终失败: {checkin_response}\n")
                                    failed_ids.add(player_id)
                    if no_task:
                        result_message = "领取成功"
                        with open(self.results_file, 'a') as file:
                            file.write(f"{datetime.now()} 玩家 {player_id} 没有可领取的每日签到任务或任务已完成\n")
                        successful_ids.add(player_id)

            self.log(f"玩家ID {player_id} {result_message}", "info" if result_message == "领取成功" else "error")

            # 添加延迟，模拟人类操作
            time.sleep(random.randint(3, 6))

        self.log("领取任务完成", "info")
        self.log(f"成功的ID总数: {len(successful_ids)}", "info")
        self.log(f"失败的ID总数: {len(failed_ids)}", "info")
        self.is_running = False

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
            self.log(f"文件 {filename} 未找到", "error")
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
                        if "签到成功" in line or ("第" in line and "天签到成功" in line) or "没有可领取的每日签到任务或任务已完成" in line:
                            successful_ids.add(player_id)
                        else:
                            failed_ids.add(player_id)
        except FileNotFoundError:
            self.log(f"文件 {filename} 未找到", "error")
        return successful_ids, failed_ids

    def login(self, player_id, password):
        url = 'https://ls.store.koppay.net/api/v2/store/login/player'
        payload = {'player_id': player_id, 'site_id': 22}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        if password:
            payload['password'] = password

        try:
            with requests.Session() as session:
                response = session.post(url, json=payload, headers=headers, timeout=10, verify=False)
                if response.status_code == 200 and 'Authorization' in response.headers:
                    return response.headers['Authorization']
                else:
                    self.log(f"玩家 {player_id} 登录失败，状态码: {response.status_code}, 响应: {response.text}", "error")
        except requests.exceptions.RequestException as e:
            self.log(f"玩家 {player_id} 登录请求失败: {e}", "error")
        return None

    def get_checkin_details(self, token, player_id):
        url = f'https://ls.store.koppay.net/api/v2/store/sale/biz/get/checkin/details?project_id=15&player_id={player_id}'
        headers = {
            'Authorization': token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            with requests.Session() as session:
                response = session.get(url, headers=headers, timeout=10, verify=False)
                if response.status_code == 200:
                    return response.json()
        except requests.exceptions.RequestException as e:
            self.log(f"获取每日签到详情失败: {e}", "error")
        return None

    def daily_checkin(self, token, player_id, checkin_day):
        url = 'https://ls.store.koppay.net/api/v2/store/sale/biz/add/checkin/create'
        headers = {
            'Authorization': token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        payload = {'project_id': 15, 'player_id': player_id, 'checkin_day': checkin_day}

        try:
            with requests.Session() as session:
                response = session.post(url, json=payload, headers=headers, timeout=10, verify=False)
                return response.json() if response.status_code == 200 else None
        except requests.exceptions.RequestException as e:
            self.log(f"每日签到请求失败: {e}", "error")
        return None

if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
