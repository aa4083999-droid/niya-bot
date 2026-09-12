import asyncio
import json
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
COGS_DIR = BASE_DIR / "cogs"
CONFIG_FILE = BASE_DIR / "config.json"

load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("discord_bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    def get_guild_id_from_config(self):
        guild_id = os.getenv("GUILD_ID")
        if guild_id and guild_id.isdigit():
            return int(guild_id)

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    gid = data.get("guild_id", "")
                    if str(gid).isdigit():
                        return int(gid)
            except Exception as e:
                log.warning("讀取 config.json 的 guild_id 失敗: %s", e)
        return None

    async def setup_hook(self):
        if not COGS_DIR.is_dir():
            raise FileNotFoundError(f"找不到 cogs 目錄：{COGS_DIR}")

        # 1. 載入所有 Cogs
        for path in sorted(COGS_DIR.glob("*.py")):
            if path.name.startswith("_"):
                continue

            extension = f"cogs.{path.stem}"
            try:
                await self.load_extension(extension)
                log.info("已成功載入模組：%s", extension)
            except Exception:
                log.exception("載入模組失敗：%s", extension)

        commands_list = self.tree.get_commands()
        log.info(f"目前 tree 內共收集到 {len(commands_list)} 個斜線指令")
        
        # ⚠️ 注意：這裡拿掉了開機自動同步，改由完全手動觸發，避免時機點錯誤！

    async def on_ready(self):
        status_name = os.getenv("BOT_STATUS", "線上運作中 🚀")
        await self.change_presence(
            activity=discord.Game(name=status_name)
        )
        log.info("機器人已上線！帳號：%s | 目前狀態：%s", self.user, status_name)

    async def on_message(self, message):
        if message.author.bot:
            return
        log.info(f"💬 收到來自 {message.author.name} 的訊息: {message.content}")
        await super().on_message(message)


bot = MyBot()


@bot.command()
async def sync(ctx, mode: str = None):
    """
    手動同步斜線指令
    """
    if not ctx.author.guild_permissions.administrator:
        await ctx.send(":x: 權限不足：你必須是**伺服器管理員**才能使用這個指令！", delete_after=10)
        return

    try:
        try:
            await ctx.message.delete()
        except Exception:
            pass  

        if mode == "guild":
            # 終極暴力解：直接把目前 tree 裡所有的指令（這 38 個）全部塞進這個伺服器！
            # 不再使用 copy_global_to，因為如果指令本身帶有 guild_id，複製會失敗。
            ctx.bot.tree.copy_global_to(guild=ctx.guild) # 將全域指令拷貝過來
            synced = await ctx.bot.tree.sync(guild=ctx.guild) # 執行同步
            
            await ctx.send(
                f":white_check_mark: 強制同步成功！已將 **{len(synced)}** 個指令註冊至 **當前伺服器 ({ctx.guild.name})**！\n*(請大家按 `Ctrl + R` 重新整理)*", 
                delete_after=10
            )
        else:
            synced = await bot.tree.sync()
            await ctx.send(
                f":earth_africa: 已成功 **全域同步 {len(synced)}** 個指令！\n*(此訊息將於 10 秒後自動刪除)*", 
                delete_after=10
            )
    except Exception as e:
        log.exception("手動同步指令執行失敗")
        await ctx.send(f":x: 執行同步時發生錯誤: `{e}`", delete_after=15)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "❌ 權限不足：你必須是**伺服器管理員**才能使用這個指令！"
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        msg = f"⏳ 指令冷卻中，請在 {error.retry_after:.1f} 秒後再試一次。"
    else:
        msg = "❌ 執行指令時發生未預期的錯誤，管理員已收到通知。"
        log.exception("斜線指令執行發生例外：%s", error)

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        log.exception("發送指令錯誤提示訊息失敗")


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if token:
        token = token.strip('"\' \r\n')  

    if not token:
        raise RuntimeError("找不到 DISCORD_TOKEN 環境變數，請確認 .env 或系統環境變數設定。")

    await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("機器人已手動停止")
