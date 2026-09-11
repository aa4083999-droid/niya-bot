import asyncio
json = json
import os
import re
import aiohttp
import discord
from collections import deque
from discord import app_commands
from discord.ext import commands

CONFIG_FILE = "config.json"
TARGET_CHANNEL_ID = "1530658318673121474" 

def get_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

class BrowserMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.latest_messages = [] 
        self.processed_ids = deque(maxlen=500) 
        self.monitor_task = self.bot.loop.create_task(self.run_monitor())

    def cog_unload(self):
        self.monitor_task.cancel()

    async def run_monitor(self):
        print("🚀 啟動終極 API 全方位監控模式！")
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    config = get_config()
                    discord_token = config.get("discord_token", "")
                    notify_channel_id = config.get("notification_channel_id", "")
                    target_characters = config.get("target_characters", [])

                    if not discord_token or not notify_channel_id:
                        await asyncio.sleep(5)
                        continue

                    headers = {
                        "Authorization": discord_token,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }

                    url = f"https://discord.com/api/v9/channels/{TARGET_CHANNEL_ID}/messages?limit=15"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            messages = await resp.json()
                            current_batch = []
                            
                            for msg in reversed(messages):
                                msg_id = msg.get("id")
                                
                                # 💡 收集所有可能藏有玩家名字的欄位
                                author_name = msg.get("author", {}).get("username", "")
                                author_global = msg.get("author", {}).get("global_name", "")
                                content = msg.get("content", "")
                                
                                embed_texts = []
                                for embed in msg.get("embeds", []):
                                    if "title" in embed: embed_texts.append(embed["title"])
                                    if "description" in embed: embed_texts.append(embed["description"])
                                    if "author" in embed and "name" in embed["author"]: embed_texts.append(embed["author"]["name"])
                                    if "footer" in embed and "text" in embed["footer"]: embed_texts.append(embed["footer"]["text"])

                                # 組合出這則訊息的完整可檢索文字
                                full_text = f"[{author_name} / {author_global}] {content} " + " ".join(embed_texts)
                                
                                if full_text.strip():
                                    current_batch.append(full_text)

                                if msg_id in self.processed_ids:
                                    continue
                                self.processed_ids.append(msg_id)

                                # 💡 使用精準的正規表達式比對名字，避免「金桔檸檬」或「檸檬草」誤觸
                                matched_char = None
                                for char in target_characters:
                                    if not char:
                                        continue
                                    # 構造正則：確保目標名字前後「不是」其他中文字，藉此排除金桔檸檬、檸檬草等情況
                                    # \u4e00-\u9fa5 代表中文範圍
                                    pattern = r'(?<![\u4e00-\u9fa5])' + re.escape(char) + r'(?![\u4e00-\u9fa5])'
                                    if re.search(pattern, full_text):
                                        matched_char = char
                                        break

                                if matched_char:
                                    print(f"🎉 偵測到目標玩家 [{matched_char}] 中獎！")
                                    channel = self.bot.get_channel(int(notify_channel_id))
                                    if channel:
                                        await channel.send(
                                            f"🚨 **轉蛋中獎捷報** 🚨\n"
                                            f"恭喜玩家 **{matched_char}** 中獎啦！\n"
                                            f"📜 完整廣播資訊：\n> {content or embed_texts}"
                                        )
                                    break
                                    
                            if current_batch:
                                self.latest_messages = current_batch
                                
                except Exception as e:
                    print(f"❌ 監控發生錯誤: {e}")

                await asyncio.sleep(4)

    @app_commands.command(name="check_latest", description="[測試] 檢查最新抓取的廣播訊息")
    @app_commands.checks.has_permissions(administrator=True)
    async def check_latest(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except:
            return
        
        if not self.latest_messages:
            await interaction.followup.send("⚠️ 尚未讀取到訊息。", ephemeral=True)
            return

        formatted_text = "\n---\n".join(self.latest_messages[-8:])
        report = (
            f"🚨 **全方位 API 快取診斷** 🚨\n"
            f"• **已快取訊息數**：`{len(self.latest_messages)} 筆`\n\n"
            f"**最近抓到的完整內容（含發送者與嵌入）**：\n```text\n{formatted_text[:1500]}\n```"
        )
        await interaction.followup.send(report, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BrowserMonitor(bot))
