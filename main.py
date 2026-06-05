import os
import time
import requests
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
import threading
import sys
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote

# ========== 全局配置变量（由界面设置） ==========
CONFIG = {
    "message": "后台查监控",  # 默认消息内容
    "interval_minutes": 1,  # 默认间隔1分钟（方便测试）
    "running": False  # 控制循环停止
}


class Logger:
    """日志重定向器：将 print 输出同时显示到 tkinter 文本框"""

    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.stdout = sys.stdout  # 保存原始 stdout

    def write(self, message):
        # 写入原始控制台
        self.stdout.write(message)
        # 写入界面文本框（在主线程中执行，避免线程安全问题）
        if self.text_widget.winfo_exists():
            self.text_widget.after(0, self._append_text, message)

    def _append_text(self, message):
        try:
            self.text_widget.insert(tk.END, message)
            self.text_widget.see(tk.END)  # 自动滚动到底部
        except tk.TclError:
            pass  # 窗口已关闭

    def flush(self):
        self.stdout.flush()
        

def init_browser():
    """使用 exe 同级目录的 chromedriver 和 chrome"""
    
    if getattr(sys, 'frozen', False):
        # PyInstaller --onefile: sys.executable 是临时目录
        # 用 sys.argv[0] 获取 exe 真实路径
        base_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    local_driver = os.path.join(base_dir, "chromedriver.exe")
    portable_chrome = os.path.join(base_dir, "chrome", "chrome.exe")
    
    print(f"📁 程序目录：{base_dir}")
    print(f"🔍 查找 ChromeDriver：{local_driver}")
    print(f"🔍 查找 Chrome：{portable_chrome}")
    
    if not os.path.exists(local_driver):
        raise FileNotFoundError(f"找不到 chromedriver.exe，请确保与 exe 放在同一目录\n查找路径：{local_driver}")
    
    if not os.path.exists(portable_chrome):
        raise FileNotFoundError(f"找不到 chrome.exe，请确保 chrome 文件夹与 exe 放在同一目录\n查找路径：{portable_chrome}")
    
    print(f"✅ 使用本地 ChromeDriver：{local_driver}")
    print(f"✅ 使用本地 Chrome：{portable_chrome}")
    
    options = webdriver.ChromeOptions()
    options.binary_location = portable_chrome
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("--disable-animations")
    
    driver = webdriver.Chrome(service=Service(local_driver), options=options)
    wait = WebDriverWait(driver, 15)
    short_wait = WebDriverWait(driver, 3)
    return driver, wait, short_wait


def get_latest_cookie():
    """
    从已登录的浏览器中，自动提取最新的有效Cookie
    返回：可以直接放到requests里使用的 cookie字符串
    """
    # 等待一下确保 cookie 已写入
    time.sleep(1)

    # 刷新页面确保 cookie 同步
    driver.refresh()
    time.sleep(0.5)

    cookies = driver.get_cookies()

    # 如果没拿到，重试几次
    retry = 0
    while not cookies and retry < 3:
        print(f"⚠️ Cookie为空，第 {retry + 1} 次重试...")
        time.sleep(1)
        cookies = driver.get_cookies()
        retry += 1

    if not cookies:
        print("❌ 无法获取Cookie，尝试从 document.cookie 获取...")
        # 备选方案：通过 JS 获取（但 HttpOnly 的拿不到）
        js_cookies = driver.execute_script("return document.cookie")
        if js_cookies:
            print("✅ 通过 JS 获取到 Cookie")
            return js_cookies
        else:
            raise Exception("获取 Cookie 失败，请检查是否登录成功")

    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    print(f"✅ 成功获取最新Cookie（共 {len(cookies)} 个）：\n", cookie_str)
    return cookie_str


def get_cat_list(cookie):
    get_car_url = 'http://www.nmgsat.com:8188/CGO8/realtime/indexrs/getallvehiclelist'
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-encoding": "gzip, deflate",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "cookie": cookie,
        "host": "www.nmgsat.com:8188",
        "origin": "http://www.nmgsat.com:8188",
        "referer": "http://www.nmgsat.com:8188/CGO8/MainPage/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest"
    }
    pageIndex = 1
    pageSize = 100000
    get_car_url += f"?pageIndex={pageIndex}&pageSize={pageSize}&winformMode=false"
    get_car_res = requests.get(get_car_url, headers=headers)
    res_json = get_car_res.json()
    return res_json.get("Data", [])


def send_message(msg, cookie, simNum):
    # ========== 正确接口地址 ==========
    send_url = "http://www.nmgsat.com:8188/CGO8/RealTime/SendTextMsg/Send"

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Cookie": cookie,
        "Host": "www.nmgsat.com:8188",
        "Origin": "http://www.nmgsat.com:8188",
        "Referer": "http://www.nmgsat.com:8188/CGO8/MainPage/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Priority": "u=0",
        "X-Requested-With": "XMLHttpRequest"
    }

    # ========== 正确参数（修复格式错误） ==========
    data = {
        "param[0].Type": "label",
        "param[0].Id": "",
        "param[0].Value": "",
        "param[0].Text": "通知类型：",
        "param[0].IsCustomParam": "",
        "param[0].CmdCode": "",
        "param[1].Type": "radio",
        "param[1].Id": "TextType1",
        "param[1].Value": "1",
        "param[1].Text": "",
        "param[1].IsCustomParam": "1",
        "param[1].CmdCode": "",
        "param[2].Type": "label",
        "param[2].Id": "",
        "param[2].Value": "",
        "param[2].Text": "通知;",
        "param[2].IsCustomParam": "",
        "param[2].CmdCode": "",
        "param[3].Type": "radio",
        "param[3].Id": "TextType2",
        "param[3].Value": "0",
        "param[3].Text": "",
        "param[3].CmdCode": "",
        "param[3].IsCustomParam": "1",
        "param[4].Type": "label",
        "param[4].Id": "",
        "param[4].Value": "",
        "param[4].Text": "消息类型：",
        "param[4].CmdCode": "",
        "param[4].IsCustomParam": "",
        "param[5].Type": "combobox",
        "param[5].Id": "Custom2",
        "param[5].Value": "1",
        "param[5].Text": "服务;",
        "param[5].IsCustomParam": "1",
        "param[5].CmdCode": "",
        "param[6].Type": "checkbox",
        "param[6].Id": "Custom4",
        "param[6].Value": "1",
        "param[6].IsCustomParam": "1",
        "param[6].Text": "",
        "param[6].CmdCode": "",
        "param[7].Type": "label",
        "param[7].Id": "",
        "param[7].Value": "",
        "param[7].Text": "终端显示器显示;",
        "param[7].IsCustomParam": "",
        "param[7].CmdCode": "",
        "param[8].Type": "checkbox",
        "param[8].Id": "Custom8",
        "param[8].Value": "1",
        "param[8].Text": "",
        "param[8].IsCustomParam": "1",
        "param[8].CmdCode": "",
        "param[9].Type": "label",
        "param[9].Id": "",
        "param[9].Value": "",
        "param[9].Text": "终端TTS播读;",
        "param[9].IsCustomParam": "",
        "param[9].CmdCode": "",
        "param[10].Type": "checkbox",
        "param[10].Id": "Custom16",
        "param[10].Value": "0",
        "param[10].Text": "",
        "param[10].IsCustomParam": "1",
        "param[10].CmdCode": "",
        "param[11].Type": "combobox",
        "param[11].Id": "Custom32",
        "param[11].Value": "0",
        "param[11].Text": "中心导航信息;",
        "param[11].IsCustomParam": "1",
        "param[11].CmdCode": "",
        "param[12].Type": "label",
        "param[12].Id": "",
        "param[12].Value": "",
        "param[12].Text": "消息内容：",
        "param[12].IsCustomParam": "",
        "param[12].CmdCode": "",
        "param[13].Type": "textarea",
        "param[13].Id": "Text",
        "param[13].Value": msg,
        "param[13].Text": msg,
        "param[13].IsCustomParam": "1",
        "param[13].CmdCode": "",
        "simNumList[0]": str(simNum)
    }

    try:
        # ========== 正确发送方式 POST + data ==========
        send_res = requests.post(send_url, headers=headers, data=data)
        print("返回结果：", send_res.text)

        send_json = send_res.json()
        if send_json.get("Result", False):
            print(f"✅ 车辆唯一识别码：{simNum} 发送内容：{msg} 消息发送成功！")
        else:
            print(f"❌ 车辆唯一识别码：{simNum} 发送内容：{msg} 发送失败：{send_json.get('Error', '未知错误')}")

    except Exception as e:
        print("❌ 请求异常：", str(e))


def close_alarm_dialog():
    try:
        # 按照你提供的HTML，精准定位：标题=车辆报警信息 的 右上角关闭按钮
        close_btn = driver.find_element(By.XPATH,
                                        '//div[text()="车辆报警信息"]/following-sibling::div/a[@class="panel-tool-close"]')

        # JS强制点击，必生效
        driver.execute_script("arguments[0].click();", close_btn)
        print("✅ 成功关闭【车辆报警信息】弹窗")
        time.sleep(0.5)
    except:
        # 没有弹窗就跳过
        print("ℹ️ 没有检测到车辆报警弹窗")


def get_all_car_with_scroll():
    car_set = set()  # 去重，防止重复采集
    container = wait.until(EC.presence_of_element_located((By.ID, "realtime_vehlist")))
    last_len = 0

    while True:
        close_alarm_dialog()
        # 1.采集当前可视区域所有车辆
        car_nodes = driver.find_elements(By.XPATH, '//span[@class="node_name" and contains(.,"蒙")]')
        for node in car_nodes:
            txt = node.text.strip()
            if '有限公司' in txt:
                continue
            if txt:
                car_set.add(txt)

        close_alarm_dialog()
        # 2.容器JS向下滚动
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
        # time.sleep(0.5)  # 等待DOM渲染新加载数据

        # 3.判断是否到底：数据数量不再变化=滚动完毕
        if len(car_set) == last_len:
            print("✅ 滚动完毕，已获取所有车辆")
            break
        last_len = len(car_set)

    # 🔹 按 车牌 去重（提取蒙Xxxxxx 作为唯一标识）
    unique_car_dict = {}

    for info in car_set:
        # 截取车牌：取第一个空格前的内容 ==> 蒙KB0238
        plate = info.split("(")[0]

        # 车牌不存在则保存，已存在则跳过（去重）
        if plate not in unique_car_dict:
            unique_car_dict[plate] = info

    # 输出结果
    car_list = sorted(unique_car_dict.values())
    print(f"总计车辆：{len(car_list)}")
    for idx, info in enumerate(car_list, 1):
        print(f"{idx:2d}. {info}")
    return unique_car_dict.keys()


def run_once():
    """
    执行一次完整的消息发送流程（每次独立打开/关闭浏览器）
    """
    global driver, wait, short_wait

    try:
        # 每次执行都重新初始化浏览器
        print("🌐 正在启动浏览器...")
        driver, wait, short_wait = init_browser()

        # 打开平台
        driver.get("http://www.nmgsat.com:8188/CGO8/MainPage/#")

        # 1.定位用户名输入框
        user_input = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="用户名"]')))
        user_input.clear()
        user_input.send_keys("碌通物流")

        # 2.定位密码输入框
        pwd_input = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="密码"]')))
        pwd_input.clear()
        pwd_input.send_keys("LT2025!@#")

        # 插件登录按钮（ID = btn_Login1）
        login_btn = driver.find_element(By.ID, "btn_Login0")

        # 【终极解决点击无效】用 JS 强制点击
        driver.execute_script("arguments[0].click();", login_btn)
        time.sleep(3)  # 等待登录完成
        print("✅ 登录成功！")

        # ====================== 【调用】登录后直接拿Cookie ======================
        cookie = get_latest_cookie()

        # ==================核心操作：全部状态下拉→行驶车辆==================
        # 1.点击【全部状态】下拉按钮
        all_status_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[contains(text(),"全部状态")]')))
        driver.execute_script("arguments[0].click();", all_status_btn)
        time.sleep(1.2)

        # 2.下拉菜单里点击【行驶车辆】
        run_car_item = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[contains(text(),"行驶车辆")]')))
        driver.execute_script("arguments[0].click();", run_car_item)
        time.sleep(3)
        print("✅ 已点击：行驶车辆列表")

        # 等待元素出现 + 可点击，再用JS点击
        switch_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="realtime_vehlist_vehTree_2_switch"]'))
        )
        driver.execute_script("arguments[0].click();", switch_btn)
        print("✅ 树形箭头点击成功")

        close_alarm_dialog()

        # 最稳：JS 点击刷新按钮
        refresh_btn = driver.find_element(By.XPATH, '//*[@id="refresh"]')
        driver.execute_script("arguments[0].click();", refresh_btn)
        print("✅ 已点击【刷新】按钮")

        drive_car_number_list = get_all_car_with_scroll()
        print("✅ 已获取所有车辆列表：")
        for idx, car_num in enumerate(drive_car_number_list, 1):
            print(f"{idx:2d}. {car_num}")

        all_car_list = get_cat_list(cookie)

        car_dict = {}
        for car_row in all_car_list:
            name = car_row.get("name", "未知车牌")
            simNum = car_row.get("simNum", "未知SIM")
            if name in drive_car_number_list:
                car_dict[name] = simNum

        msg = CONFIG["message"]
        for k, v in car_dict.items():
            print(f"行驶车辆: {k} 对应SIM: {v}")
            send_message(msg=msg, cookie=cookie, simNum=v)

        print(f"✅ 本轮发送完成")

    except Exception as e:
        import traceback
        traceback.print_exc()

    finally:
        # 无论成功失败，都关闭浏览器
        try:
            driver.quit()
            print("🚪 浏览器已关闭")
        except:
            pass


def worker_loop():
    """
    后台线程：循环执行 run_once()
    每次循环：打开浏览器 → 登录 → 执行任务 → 关闭浏览器 → 等待间隔时间
    """
    CONFIG["running"] = True
    while CONFIG["running"]:
        start_time = datetime.now()
        next_time = start_time + timedelta(minutes=CONFIG["interval_minutes"])

        print(f"\n{'=' * 60}")
        print(f"🚀 第 1 轮执行开始")
        print(f"⏰ 开始时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📨 消息内容：{CONFIG['message']}")
        print(f"⏳ 下次执行：{next_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}\n")

        run_once()

        if not CONFIG["running"]:
            break

        # 计算实际需要等待的时间（考虑执行耗时）
        elapsed = (datetime.now() - start_time).total_seconds()
        sleep_seconds = CONFIG["interval_minutes"] * 60 - elapsed

        if sleep_seconds > 0:
            print(f"⏳ 本轮耗时 {elapsed:.1f} 秒，等待 {sleep_seconds:.1f} 秒后继续...")

            # 使用一次性 sleep，避免逐秒循环的累积误差
            # 但支持随时停止：拆分成小段检查
            chunk_size = 1  # 每1秒检查一次是否停止
            slept = 0
            while slept < sleep_seconds and CONFIG["running"]:
                time.sleep(min(chunk_size, int(sleep_seconds - slept)))
                slept += chunk_size
        else:
            print(f"⚠️ 本轮耗时 {elapsed:.1f} 秒，已超过间隔时间，立即开始下一轮")

    print("✅ 程序已停止")


def start_program():
    """点击开始按钮"""
    msg = entry_msg.get().strip()
    interval_str = entry_interval.get().strip()

    if not msg:
        messagebox.showerror("错误", "消息内容不能为空！")
        return

    try:
        interval = int(interval_str)
        if interval < 1:
            messagebox.showerror("错误", "间隔时间至少为1分钟！")
            return
    except ValueError:
        messagebox.showerror("错误", "间隔时间必须是整数！")
        return

    CONFIG["message"] = msg
    CONFIG["interval_minutes"] = interval

    # 禁用输入和开始按钮，启用停止按钮
    entry_msg.config(state="disabled")
    entry_interval.config(state="disabled")
    btn_start.config(state="disabled")
    btn_stop.config(state="normal")

    # 在新线程中运行，避免卡死界面
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()

    status_label.config(text=f"运行中 | 消息：{msg} | 间隔：{interval}分钟", fg="green")


def stop_program():
    """点击停止按钮"""
    CONFIG["running"] = False
    status_label.config(text="已停止", fg="red")

    # 恢复界面
    entry_msg.config(state="normal")
    entry_interval.config(state="normal")
    btn_start.config(state="normal")
    btn_stop.config(state="disabled")


# ==================== tkinter 界面 ====================
root = tk.Tk()
root.title("车辆消息自动发送工具")
root.geometry("800x650")
root.minsize(700, 500)

# 顶部配置区域
top_frame = tk.Frame(root, padx=15, pady=10)
top_frame.pack(fill="x")

tk.Label(top_frame, text="车辆消息自动发送配置", font=("Microsoft YaHei", 14, "bold")).pack(anchor="w")

# 配置输入区域
config_frame = tk.Frame(top_frame)
config_frame.pack(fill="x", pady=10)

# 消息内容
tk.Label(config_frame, text="发送消息内容：", font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", pady=5)
entry_msg = tk.Entry(config_frame, font=("Microsoft YaHei", 10), width=40)
entry_msg.grid(row=0, column=1, sticky="w", padx=5)
entry_msg.insert(0, CONFIG["message"])

# 间隔时间
tk.Label(config_frame, text="执行间隔(分钟)：", font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", pady=5)
entry_interval = tk.Entry(config_frame, font=("Microsoft YaHei", 10), width=15)
entry_interval.grid(row=1, column=1, sticky="w", padx=5)
entry_interval.insert(0, str(CONFIG["interval_minutes"]))

# 按钮区域
btn_frame = tk.Frame(top_frame)
btn_frame.pack(fill="x", pady=5)

btn_start = tk.Button(btn_frame, text="▶ 开始运行", font=("Microsoft YaHei", 11),
                      bg="#4CAF50", fg="white", width=12, command=start_program)
btn_start.pack(side="left", padx=5)

btn_stop = tk.Button(btn_frame, text="⏹ 停止运行", font=("Microsoft YaHei", 11),
                     bg="#f44336", fg="white", width=12, command=stop_program, state="disabled")
btn_stop.pack(side="left", padx=5)

# 状态栏
status_label = tk.Label(top_frame, text="就绪 - 请配置参数后点击开始", font=("Microsoft YaHei", 9), fg="gray")
status_label.pack(anchor="w", pady=5)

# 分隔线
tk.Frame(root, height=2, bg="#cccccc").pack(fill="x", padx=10)

# 日志显示区域
log_frame = tk.Frame(root, padx=15, pady=10)
log_frame.pack(fill="both", expand=True)

tk.Label(log_frame, text="📋 控制台日志", font=("Microsoft YaHei", 11, "bold")).pack(anchor="w")

# 带滚动条的日志文本框
log_text = scrolledtext.ScrolledText(
    log_frame,
    wrap=tk.WORD,
    font=("Consolas", 10),
    bg="#1e1e1e",
    fg="#d4d4d4",
    insertbackground="white",
    state="normal",
    height=20
)
log_text.pack(fill="both", expand=True, pady=5)

# 日志操作按钮
log_btn_frame = tk.Frame(log_frame)
log_btn_frame.pack(anchor="e")


def clear_log():
    log_text.delete(1.0, tk.END)


tk.Button(log_btn_frame, text="🗑 清空日志", font=("Microsoft YaHei", 9),
          command=clear_log).pack(side="left", padx=5)

# 重定向 print 到日志框
sys.stdout = Logger(log_text)

original_stdout = sys.stdout.stdout if hasattr(sys.stdout, 'stdout') else sys.__stdout__

# 启动界面
root.mainloop()

# 恢复原始 stdout
sys.stdout = original_stdout
# sys.stdout = sys.stdout.stdout if hasattr(sys.stdout, 'stdout') else sys.__stdout__
