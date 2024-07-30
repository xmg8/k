import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import threading
import webbrowser
from datetime import datetime
import os

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XMG游戏团队")
        self.geometry("600x500")

        # 公告
        self.announcement_label = tk.Label(self, text="公告:", font=("Arial", 12))
        self.announcement_label.grid(row=0, column=0, sticky="w")

        self.announcement_text = scrolledtext.ScrolledText(self, width=70, height=10, wrap=tk.WORD)
        self.announcement_text.grid(row=1, column=0, columnspan=5, padx=10, pady=5)
        self.update_announcement()

        # 输入框和按钮
        self.id_label = tk.Label(self, text="输入玩家ID:")
        self.id_label.grid(row=2, column=0, pady=5)

        self.id_entry = tk.Entry(self)
        self.id_entry.grid(row=2, column=1, pady=5)

        self.add_button = tk.Button(self, text="添加ID", command=self.add_id)
        self.add_button.grid(row=2, column=2, pady=5)

        self.start_button = tk.Button(self, text="开始领取", command=self.start_retrieve)
        self.start_button.grid(row=2, column=3, pady=5)

        self.stop_button = tk.Button(self, text="停止领取", command=self.stop_retrieve)
        self.stop_button.grid(row=2, column=4, pady=5)

        self.auto_button = tk.Button(self, text="全自动托管", command=self.open_browser)
        self.auto_button.grid(row=3, column=2, columnspan=2, pady=5)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(self, width=70, height=10, wrap=tk.WORD)
        self.log_text.grid(row=4, column=0, columnspan=5, padx=10, pady=5)

        self.retrieve_flag = False
        self.ids = []
        self.initialize_files()

    def update_announcement(self):
        try:
            response = requests.get("https://xmg8.github.io/kop/")
            response.raise_for_status()
            self.announcement_text.delete("1.0", tk.END)
            self.announcement_text.insert(tk.END, response.text)
        except requests.RequestException as e:
            self.announcement_text.delete("1.0", tk.END)
            self.announcement_text.insert(tk.END, f"获取公告失败: {e}")

    def add_id(self):
        player_id = self.id_entry.get().strip()
        if player_id:
            self.ids.append(player_id)
            self.log_text.insert(tk.END, f"添加玩家ID: {player_id}\n")
            self.log_text.yview(tk.END)
            self.id_entry.delete(0, tk.END)
        else:
            messagebox.showwarning("输入错误", "请输入有效的玩家ID")

    def start_retrieve(self):
        if not self.ids:
            messagebox.showwarning("输入错误", "请添加至少一个玩家ID")
            return
        self.log_text.insert(tk.END, "开始领取任务\n")
        self.log_text.yview(tk.END)
        self.retrieve_flag = True
        self.run_script()

    def stop_retrieve(self):
        self.log_text.insert(tk.END, "停止领取任务\n")
        self.log_text.yview(tk.END)
        self.retrieve_flag = False

    def run_script(self):
        def task():
            successful_ids = set()
            failed_ids = set()
            total_ids = len(self.ids)
            for idx, player_id in enumerate(self.ids):
                if not self.retrieve_flag:
                    break
                self.log_text.insert(tk.END, f"正在执行第 {idx + 1}/{total_ids} 个任务: 玩家ID {player_id}\n")
                self.log_text.yview(tk.END)
                # 登录并获取token
                token = self.login(player_id)
                if not token:
                    failed_ids.add(player_id)
                    self.log_text.insert(tk.END, f"玩家ID {player_id} 登录失败，停止执行该ID任务\n")
                    self.log_text.yview(tk.END)
                    continue
                
                checkin_details = self.get_checkin_details(token, player_id)
                if checkin_details:
                    self.log_text.insert(tk.END, f"玩家 {player_id} 没有可领取的每日签到任务或任务已完成\n")
                    self.log_text.yview(tk.END)
                    successful_ids.add(player_id)
                else:
                    failed_ids.add(player_id)

                self.log_text.insert(tk.END, f"成功的ID总数: {len(successful_ids)}\n")
                self.log_text.insert(tk.END, f"失败的ID总数: {len(failed_ids)}\n")
                self.log_text.yview(tk.END)

            self.write_results(successful_ids, failed_ids)

        threading.Thread(target=task).start()

    def login(self, player_id):
        url = 'https://ls.store.koppay.net/api/v2/store/login/player'
        payload = {'player_id': player_id, 'site_id': 22}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200 and 'Authorization' in response.headers:
                return response.headers['Authorization']
        except requests.RequestException as e:
            self.log_text.insert(tk.END, f"玩家ID {player_id} 登录失败: {e}\n")
            self.log_text.yview(tk.END)
        return None

    def get_checkin_details(self, token, player_id):
        url = f'https://ls.store.koppay.net/api/v2/store/sale/biz/get/checkin/details?project_id=15&player_id={player_id}'
        headers = {
            'Authorization': token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            self.log_text.insert(tk.END, f"玩家ID {player_id} 获取每日签到详情失败: {e}\n")
            self.log_text.yview(tk.END)
        return None

    def open_browser(self):
        webbrowser.open("http://www.xmg888.top")

    def initialize_files(self):
        if not os.path.exists('ids.txt'):
            with open('ids.txt', 'w') as file:
                file.write('')
        if not os.path.exists('results.txt'):
            with open('results.txt', 'w') as file:
                file.write('')

    def write_results(self, successful_ids, failed_ids):
        with open('results.txt', 'a') as file:
            file.write(f"{datetime.now()} 成功的ID: {successful_ids}\n")
            file.write(f"{datetime.now()} 失败的ID: {failed_ids}\n")

if __name__ == '__main__':
    app = Application()
    app.mainloop()
