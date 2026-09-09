import random
import asyncio
import time
import json
import os
import discord
from discord import app_commands
from discord.ext import commands

# 輔助函式：產生自動倒數的 Discord 時間戳記
def get_delete_timestamp():
    return f"<t:{int(time.time()) + 60}:R>"

DATA_FILE = "rpg_data.json"

def load_player_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 將 JSON 讀出的字串 Key 轉回 Discord ID 的整數型態
                return {int(k): v for k, v in data.items()}
        except Exception:
            pass
    return {}

def save_player_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 使用 JSON 讀取替代原本的空字典
player_data = load_player_data()

class RpgCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rpg_profile", description="[RPG] 查看你的冒險者數值與狀態")
    async def rpg_profile(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        if user_id not in player_data:
            player_data[user_id] = {
                "name": interaction.user.display_name,
                "level": 1,
                "exp": 0,
                "gold": 100,
                "hp": 100,
                "max_hp": 100,
                "attack": 15
            }
            save_player_data(player_data)

        p = player_data[user_id]
        embed = discord.Embed(title=f"🛡️ 冒險者面板：{p['name']}", color=discord.Color.blue())
        embed.add_field(name="等級 (Level)", value=f"`Lv. {p['level']}`", inline=True)
        embed.add_field(name="經驗值 (EXP)", value=f"`{p['exp']} / {p['level'] * 100}`", inline=True)
        embed.add_field(name="金幣 (Gold)", value=f"`🪙 {p['gold']}`", inline=True)
        embed.add_field(name="生命值 (HP)", value=f"`❤️ {p['hp']} / {p['max_hp']}`", inline=True)
        embed.add_field(name="攻擊力 (ATK)", value=f"`⚔️ {p['attack']}`", inline=True)

        msg = await interaction.followup.send(embed=embed, ephemeral=True)
        await asyncio.sleep(60)
        try: await msg.delete()
        except discord.NotFound: pass

    @app_commands.command(name="rpg_hunt", description="[RPG] 出發前往野外狩獵怪物！")
    async def rpg_hunt(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id

        if user_id not in player_data:
            player_data[user_id] = {
                "name": interaction.user.display_name,
                "level": 1,
                "exp": 0,
                "gold": 100,
                "hp": 100,
                "max_hp": 100,
                "attack": 15
            }

        p = player_data[user_id]
        if p["hp"] <= 0:
            await interaction.followup.send(f"❌ 你目前生命值歸零，請先休息或治療！\n*(訊息將於 {get_delete_timestamp()} 自動刪除)*")
            return

        monsters = [
            {"name": "史萊姆", "hp": 30, "atk": 5, "exp": 25, "gold": 15},
            {"name": "哥布林", "hp": 60, "atk": 12, "exp": 50, "gold": 35},
            {"name": "狂暴野狼", "hp": 90, "atk": 20, "exp": 80, "gold": 60}
        ]
        monster = random.choice(monsters)

        # 簡單回合模擬
        p_damage_dealt = random.randint(p["attack"] - 3, p["attack"] + 5)
        m_damage_dealt = random.randint(monster["atk"] - 2, monster["atk"] + 2)

        # 結算
        p["gold"] += monster["gold"]
        p["exp"] += monster["exp"]
        
        result_text = f"⚔️ 你遭遇了 **{monster['name']}**！經過一番激戰...\n" \
                      f"💥 你對其造成了 `{p_damage_dealt}` 點傷害，擊敗了怪物！\n" \
                      f"🎁 獲得獎勵：`+{monster['exp']}` EXP、`+🪙 {monster['gold']}` 金幣！"

        # 檢查升級
        exp_needed = p["level"] * 100
        if p["exp"] >= exp_needed:
            p["level"] += 1
            p["exp"] -= exp_needed
            p["max_hp"] += 20
            p["hp"] = p["max_hp"]
            p["attack"] += 5
            result_text += f"\n\n🎉 **恭喜升級！** 目前等級提升至 `Lv. {p['level']}`！數值全面提升！"

        save_player_data(player_data) # 存檔記錄戰鬥結果
        await interaction.followup.send(result_text)

async def setup(bot):
    await bot.add_cog(RpgCog(bot))
