import asyncio
import gc
import json
import os
import sys
import psutil
import discord
import time
from datetime import datetime
from discord.ext import commands

CONFIG_FILE = "config.json"

def get_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

class MemoryCleaner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.high_ram_count = 0  # 連續高記憶體計數器
        self.start_time = time.time()  # 紀錄開機時間
        # 啟動背景常駐守護任務
        self.clean_task = self.bot.loop.create_task(self.guardian_loop())

    def cog_unload(self):
        # 當模組被卸載時安全取消任務
        self.clean_task.cancel()
        
    def get_uptime(self):
        # 計算機器人已經連續運作了多長時間
        uptime_seconds = int(time.time() - self.start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}小時 {minutes}分 {seconds}秒"

    async def guardian_loop(self):
        # 等待機器人完全準備就緒
        await self.bot.wait_until_ready()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"🛡️ [{now}] [系統管家] 完美防禦版守護模組已正式上線！")

        while not self.bot.is_closed():
            try:
                config = get_config()
                notify_channel_id = config.get("notification_channel_id", "")
                
                # 動態讀取危險標準，若設定檔沒寫則採用預設值 (450MB警告 / 550MB重啟)
                warn_limit = config.get("ram_warning_mb", 450)
                restart_limit = config.get("ram_restart_mb", 550)

                # 1. 取得當前 Python 行程的資源佔用狀況
                process = psutil.Process(os.getpid())
                ram_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent(interval=1)
                
                # 2. 執行 Python 的全域垃圾回收
                collected = gc.collect()

                # 3. 檢查 Discord 網路閘道延遲 (Ping)
                latency_ms = self.bot.latency * 1000
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 4. 印出精緻版綜合健康報告 (含時間與存活時長)
                print(
                    f"📊 [{current_time}] [效能] RAM: {ram_mb:.1f}MB | "
                    f"CPU: {cpu_percent}% | "
                    f"Ping: {latency_ms:.0f}ms | "
                    f"清理: {collected}項 | "
                    f"穩定運作: {self.get_uptime()}"
                )

                channel = None
                if notify_channel_id:
                    try:
                        channel = self.bot.get_channel(int(notify_channel_id))
                    except Exception:
                        pass

                # 5. 資源超標智慧警告與 Discord 通報 (加上 try-except 防止網路斷線引發崩潰)
                if ram_mb > warn_limit:
                    self.high_ram_count += 1
                    print(f"⚠️ [{current_time}] [系統警告] 記憶體偏高 ({ram_mb:.1f}MB)，連續次數: {self.high_ram_count}")
                    if channel and self.high_ram_count == 1:
                        try:
                            await channel.send(
                                f"⚠️ **[系統防禦警告]** 機器人記憶體佔用偏高 (`{ram_mb:.1f} MB`)。\n"
                                f"🕒 目前已連續服役：{self.get_uptime()}"
                            )
                        except Exception: pass
                else:
                    self.high_ram_count = 0

                if latency_ms > 600:
                    print(f"⚠️ [{current_time}] [網路警告] 與 Discord 連線延遲偏高 ({latency_ms:.0f}ms)")
                    if channel:
                        try:
                            await channel.send(f"⚠️ **[網路警告]** 伺服器連線延遲飆高 (`{latency_ms:.0f}ms`)。")
                        except Exception: pass

                # 6. 終極預防重啟機制 (真・原地重啟)
                if ram_mb > restart_limit:
                    print(f"🚨 [{current_time}] [嚴重警告] 記憶體突破 {restart_limit}MB 閥值，執行緊急深層重啟！")
                    if channel:
                        try:
                            await channel.send("🚨 **[系統自癒協議啟動]** 記憶體超載，為保護伺服器，系統正在自動重新啟動，預計 10 秒後恢復哨兵勤務...")
                        except Exception: pass
                    
                    await asyncio.sleep(3) # 給予 3 秒鐘讓訊息發送完畢
                    
                    # 這一行是核心：用新的 Python 行程覆蓋掉舊的，完美實現無縫重啟！
                    os.execv(sys.executable, ['python3'] + sys.argv)

                # 7. 自動清理殘留在根目錄的過期暫存截圖檔案
                for file in os.listdir("."):
                    if file.endswith(".png") and ("screenshot" in file or "debug" in file):
                        try:
                            os.remove(file)
                            print(f"🧹 [{current_time}] [暫存清理] 已清除殘留圖檔: {file}")
                        except Exception:
                            pass

            except Exception as e:
                print(f"❌ [系統管家] 執行過程中發生未預期錯誤: {e}")

            # 每 15 分鐘（900秒）執行一次巡邏檢測
            await asyncio.sleep(900)

async def setup(bot):
    await bot.add_cog(MemoryCleaner(bot))
