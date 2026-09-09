import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio

CONFIG_FILE = "config.json"
DEFAULT_TARGETS = ["Aqua", "黑炭", "檸檬", "啊嗚Awu", "妃妃", "均欸", "叮咚雞"]

def load_config():
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    if "target_characters" not in data:
        data["target_characters"] = DEFAULT_TARGETS
    return data

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class MonitorControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_notify", description="設定轉蛋中獎通知要回報的頻道")
    @app_commands.describe(channel="請選擇要接收通知的文字頻道")
    async def set_notify(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = await asyncio.to_thread(load_config)
        data["notification_channel_id"] = str(channel.id)
        await asyncio.to_thread(save_config, data)
        await interaction.response.send_message(f"✅ 已成功將轉蛋通知頻道設定為：{channel.mention}", ephemeral=True)

    @app_commands.command(name="test_notify", description="測試轉蛋通知功能是否正常")
    async def test_notify(self, interaction: discord.Interaction):
        data = await asyncio.to_thread(load_config)
        notify_id = data.get("notification_channel_id")
        
        if not notify_id:
            await interaction.response.send_message("❌ 你還沒有設定通知頻道！請先使用 `/set_notify` 設定。", ephemeral=True)
            return
        
        channel = self.bot.get_channel(int(notify_id))
        if channel:
            await interaction.response.send_message("✅ 正在發送測試訊息...", ephemeral=True)
            await channel.send("🔧 **系統驗收測試**：這是一則測試訊息，如果看到這個，代表機器人已經成功綁定回報頻道，隨時準備抓取中獎通知！")
        else:
            await interaction.response.send_message("❌ 找不到通知頻道，請確認機器人是否有權限在該頻道發言。", ephemeral=True)

    @app_commands.command(name="add_target", description="新增要監控的玩家名字")
    @app_commands.describe(name="玩家名字")
    async def add_target(self, interaction: discord.Interaction, name: str):
        data = await asyncio.to_thread(load_config)
        targets = data["target_characters"]
        if name in targets:
            await interaction.response.send_message(f"⚠️ 玩家 **{name}** 已經在監控名單中了！", ephemeral=True)
            return
        targets.append(name)
        data["target_characters"] = targets
        await asyncio.to_thread(save_config, data)
        await interaction.response.send_message(f"✅ 成功新增玩家：**{name}**\n目前總名單：`{', '.join(targets)}`", ephemeral=True)

    @app_commands.command(name="remove_target", description="從名單中移除玩家")
    @app_commands.describe(name="玩家名字")
    async def remove_target(self, interaction: discord.Interaction, name: str):
        data = await asyncio.to_thread(load_config)
        targets = data["target_characters"]
        if name not in targets:
            await interaction.response.send_message(f"❌ 找不到玩家 **{name}**", ephemeral=True)
            return
        targets.remove(name)
        data["target_characters"] = targets
        await asyncio.to_thread(save_config, data)
        await interaction.response.send_message(f"🗑️ 已移除玩家：**{name}**\n目前剩餘名單：`{', '.join(targets)}`", ephemeral=True)

    @app_commands.command(name="list_targets", description="查看目前的監控名單")
    async def list_targets(self, interaction: discord.Interaction):
        data = await asyncio.to_thread(load_config)
        targets = data.get("target_characters", DEFAULT_TARGETS)
        await interaction.response.send_message(f"📋 **目前監控的玩家名單**：\n`{', '.join(targets)}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MonitorControl(bot))
