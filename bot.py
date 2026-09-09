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

# 明確指定載入專案根目錄下的 .env 檔案，並覆蓋系統變數
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

bot = commands.Bot(command_prefix="!", intents=intents)
_commands_synced = False


def get_guild_id_from_config():
    """從 config.json 或環境變數讀取伺服器 ID（若有）"""
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


async def load_extensions():
    """載入 cogs 目錄內所有 Python 模組。"""
    if not COGS_DIR.is_dir():
        raise FileNotFoundError(f"找不到 cogs 目錄：{COGS_DIR}")

    for path in sorted(COGS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue

        extension = f"cogs.{path.stem}"

        try:
            await bot.load_extension(extension)
            log.info("已成功載入模組：%s", extension)
        except Exception:
            log.exception("載入模組失敗：%s", extension)


@bot.event
async def on_ready():
    """on_ready 可能因重連再次觸發，因此只同步一次。"""
    global _commands_synced

    if not _commands_synced:
        guild_id = get_guild_id_from_config()
        try:
            if guild_id:
                guild = discord.Object(id=guild_id)
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                log.info("成功在指定伺服器 (%s) 同步 %d 個斜線指令", guild_id, len(synced))
            else:
                synced = await bot.tree.sync()
                log.info("成功進行全域同步 %d 個斜線指令（需等待 Discord快取）", len(synced))
            _commands_synced = True
        except Exception:
            log.exception("同步斜線指令失敗")

    # 讀取各自 .env 裡的 BOT_STATUS，如果沒寫就預設顯示「線上運作中」
    status_name = os.getenv("BOT_STATUS", "線上運作中 🚀")
    await bot.change_presence(
        activity=discord.Game(
            name=status_name
        )
    )

    log.info("機器人已上線！帳號：%s | 目前狀態：%s", bot.user, status_name)


# ==================== 全域斜線指令錯誤處理 ====================
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    """攔截斜線指令執行時發生的例外，提供親切的提示回饋。"""
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
        token = token.strip('"\' \r\n')  # 自動去除可能殘留的引號與空白

    if not token:
        raise RuntimeError("找不到 DISCORD_TOKEN 環境變數，請確認 .env 或系統環境變數設定。")

    async with bot:
        await load_extensions()
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("機器人已手動停止")
