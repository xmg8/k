from tkinterhtml import HtmlFrame
from threading import Thread
import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox
from tkhtmlview import HTMLLabel
import requests
import psutil
import webbrowser
import time
import random
import os
from datetime import datetime
from requests.exceptions import ConnectionError, Timeout, SSLError

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XMG游戏团队")
        self.geometry("600x600")

        self.announcement_html = HTMLLabel(self, html="", width=100, height=10)
        self.announcement_html.pack()

        # 刷新公告按钮
        self.refresh_button = tk.Button(self, text="刷新公告", command=self.refresh_announcement)
        self.refresh_button.pack()

        # 输入玩家ID
        self.id_entry = tk.Entry(self)
        self.id_entry.pack()

        # 添加ID按钮
        self.add_id_button = tk.Button(self, text="添加ID", command=self.add_id)
        self.add_id_button.pack()

        # 开始领取按钮
        self.start_button = tk.Button(self, text="开始领取", command=self.start_retrieve)
        self.start_button.pack()

        # 停止领取按钮
        self.stop_button = tk.Button(self, text="停止领取", command=self.stop_retrieve)
        self.stop_button.pack()

        # 全自动托管按钮
        self.auto_manage_button = tk.Button(self, text="全自动托管", command=self.auto_manage)
        self.auto_manage_button.pack()

        # 日志输出
        self.log_output = scrolledtext.ScrolledText(self, width=100, height=20)
        self.log_output.pack()

    def refresh_announcement(self):
        url = 'https://xmg8.github.io/kop/announcement.html'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            announcement = response.text.strip()
            self.announcement_html.set_html(announcement)
        except Exception as e:
            self.log(f"获取公告失败: {e}")

    def initialize_files(self):
        self.create_file_if_not_exists('ids.txt')
        self.create_file_if_not_exists('results.txt')
        self.create_file_if_not_exists('ip.txt')

    def create_file_if_not_exists(self, filename, content=""):
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(content)

    def add_id(self):
        player_id = self.id_entry.get().strip()
        if player_id:
            with open('ids.txt', 'a', encoding='utf-8') as file:
                file.write(player_id + "\n")
            self.id_entry.delete(0, tk.END)
            self.log(f"玩家ID {player_id} 已添加")

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.yview(tk.END)

    def read_ids_and_passwords(self, filename):
        ids_and_passwords = []
        try:
            with open(filename, 'r', encoding='utf-8') as file:
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
            with open(filename, 'r', encoding='utf-8') as file:
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

        self.log(f"成功的ID总数: {len(successful_ids)}")
        self.log(f"失败的ID总数: {len(failed_ids)}")

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
                    response = session.post(url, json=payload, headers=headers, timeout=10)
                    if response.status_code == 200 and 'Authorization' in response.headers:
                        return response.headers['Authorization']
            except (ConnectionError, Timeout, SSLError):
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
                    response = session.get(url, headers=headers, timeout=10)
                    return response.json() if response.status_code == 200 else None
            except (ConnectionError, Timeout, SSLError):
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
                    response = session.post(url, json=payload, headers=headers, timeout=10)
                    return response.json() if response.status_code == 200 else None
            except (ConnectionError, Timeout, SSLError):
                time.sleep(2)  # 等待一段时间后重试
        return None

    def show_system_usage(self):
        process = psutil.Process()
        mem_info = process.memory_info()
        cpu_usage = psutil.cpu_percent(interval=1)

        self.log(f"当前内存使用: {mem_info.rss / 1024 ** 2:.2f} MB")
        self.log(f"当前CPU使用: {cpu_usage:.2f} %")

    def open_automanage(self):
        webbrowser.open('http://www.xmg888.top')

    def refresh_announcement(self):
        url = 'https://xmg8.github.io/kop/'  # 更新为 GitHub Pages 的 URL
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            announcement = response.text.strip()
            self.announcement_html.set_content(announcement)
        except Exception as e:
            self.log(f"获取公告失败: {e}")

    def start_script(self):
        if not self.running:
            self.running = True
            self.script_thread = Thread(target=self.run_script)
            self.script_thread.start()

    def stop_script(self):
        if self.running:
            self.running = False

    def run_script(self):
        self.log("开始领取任务")
        ids_and_passwords = self.read_ids_and_passwords('ids.txt')
        unique_ids_and_passwords = list(set(ids_and_passwords))
        successful_ids, failed_ids = self.read_results('results.txt')

        ids_to_run = [(id, pwd) for id, pwd in unique_ids_and_passwords if id not in successful_ids]
        total_ids = len(ids_to_run)

        if total_ids == 0:
            self.log("没有需要执行的ID，请添加ID")
            return

        self.log(f"需要执行任务的ID总数: {total_ids}")

        for idx, (player_id, password) in enumerate(ids_to_run):
            if not self.running:
                break

            current_task_number = idx + 1
            self.log(f"正在执行第 {current_task_number}/{total_ids} 个任务: 玩家ID {player_id}")
            self.show_system_usage()

            token = self.login(player_id, password)
            if not token:
                self.log(f"玩家 {player_id} 登录失败，停止执行该ID任务")
                with open('results.txt', 'a', encoding='utf-8') as file:
                    file.write(f"{datetime.now()} 玩家 {player_id} 登录失败\n")
                failed_ids.add(player_id)
                continue

            checkin_details = self.get_checkin_details(token, player_id)
            if not checkin_details:
                self.log(f"玩家 {player_id} 获取每日签到详情失败，停止执行该ID任务")
                with open('results.txt', 'a', encoding='utf-8') as file:
                    file.write(f"{datetime.now()} 玩家 {player_id} 获取每日签到详情失败\n")
                failed_ids.add(player_id)
                continue

            no_task = True
            if checkin_details and checkin_details['code'] == 1:
                for day_info in checkin_details['data']['activity_gifts_list']:
                    if day_info['status'] == 1:  # 检查是否可以领取
                        no_task = False
                        checkin_day = int(day_info['name_language_code'].replace('第', '').replace('日', ''))
                        for attempt in range(1, 6):
                            checkin_response = self.daily_checkin(token, player_id, checkin_day)
                            if checkin_response and checkin_response['code'] == 1:
                                self.log(f"玩家 {player_id} 第{checkin_day}天签到成功")
                                with open('results.txt', 'a', encoding='utf-8') as file:
                                    file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到成功\n")
                                successful_ids.add(player_id)
                                break
                            else:
                                time.sleep(2)
                        else:
                            self.log(f"玩家 {player_id} 第{checkin_day}天签到最终失败")
                            with open('results.txt', 'a', encoding='utf-8') as file:
                                file.write(f"{datetime.now()} 玩家 {player_id} 第{checkin_day}天签到最终失败: {checkin_response}\n")
                            failed_ids.add(player_id)
            if no_task:
                self.log(f"玩家 {player_id} 没有可领取的每日签到任务或任务已完成")
                successful_ids.add(player_id)

            # 添加延迟，模拟人类操作
            time.sleep(random.randint(3, 6))

        self.log(f"成功的ID总数: {len(successful_ids)}")
        self.log(f"失败的ID总数: {len(failed_ids)}")
        self.log("领取任务完成")

    def show_welcome_message(self):
        messagebox.showinfo("欢迎", "欢迎使用XMG游戏团队工具。请确保ID文件已更新，并点击开始领取任务。")

if __name__ == "__main__":
    app = Application()
    app.mainloop()

