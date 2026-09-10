import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import datetime
import aiohttp
from bs4 import BeautifulSoup
import logging

log = logging.getLogger("discord_bot")

# 定義台灣時區與自動開獎時間 (21:00)
tz_tpe = datetime.timezone(datetime.timedelta(hours=8))
draw_time = datetime.time(hour=21, minute=0, tzinfo=tz_tpe)

class GuGu39(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bet_channel_id = None 
        self.tz = tz_tpe
        
        self.daily_bets = {}      
        self.user_balances = {}   
        self.claimed_users = set() 
        self.bot_admins = set()    
        self.last_checkin = {}    # 紀錄玩家最後一次簽到的日期 (格式: YYYY-MM-DD)
        
        self.COST_PER_CAR = 3000
        self.PRIZE_PER_CAR = 22000

        self.auto_draw_task.start()

    def cog_unload(self):
        self.auto_draw_task.cancel()

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        is_server_admin = interaction.user.guild_permissions.administrator
        is_bot_admin = interaction.user.id in self.bot_admins
        return is_server_admin or is_bot_admin

    @app_commands.command(name="setbetchannel", description="[管理員] 將當前頻道設定為咕咕谷39的專屬下注頻道")
    @app_commands.default_permissions(administrator=True)
    async def set_bet_channel(self, interaction: discord.Interaction):
        self.bet_channel_id = interaction.channel.id
        await interaction.response.send_message(f"✅ **設定成功！** 本頻道（<#{self.bet_channel_id}>）已成為咕咕谷39的專屬下注與開獎頻道。")

    @app_commands.command(name="addadmin", description="[伺服器管理員] 授權指定成員成為機器人管理員")
    @app_commands.default_permissions(administrator=True)
    async def add_admin(self, interaction: discord.Interaction, member: discord.Member):
        if member.id in self.bot_admins:
            await interaction.response.send_message(f"⚠️ {member.mention} 已經是機器人管理員了！", ephemeral=True)
            return

        self.bot_admins.add(member.id)
        await interaction.response.send_message(f"✅ **授權成功！** 已將 {member.mention} 登記為機器人管理員。", ephemeral=False)

    @app_commands.command(name="removeadmin", description="[伺服器管理員] 移除指定成員的機器人管理員身份")
    @app_commands.default_permissions(administrator=True)
    async def remove_admin(self, interaction: discord.Interaction, member: discord.Member):
        if member.id not in self.bot_admins:
            await interaction.response.send_message(f"⚠️ {member.mention} 本來就不是機器人管理員。", ephemeral=True)
            return

        self.bot_admins.remove(member.id)
        await interaction.response.send_message(f"🗑️ **已移除！** 已取消 {member.mention} 的機器人管理員身份。", ephemeral=False)

    @app_commands.command(name="addmoney", description="[管理員] 指定一位玩家並為其增加指定金額的楓幣")
    async def add_money(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ **權限不足：** 你必須是伺服器管理員或機器人授權管理員才能使用此指令！", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ 增加的金額必須大於 0！", ephemeral=True)
            return

        user_id = member.id
        self.user_balances[user_id] = self.user_balances.get(user_id, 0) + amount
        new_balance = self.user_balances[user_id]

        await interaction.response.send_message(
            f"✅ **管理員操作成功！** 已成功為 {member.mention} 增加 **{amount:,}** 楓幣。\n💰 該玩家目前錢包餘額：**{new_balance:,} 楓幣**",
            ephemeral=False
        )

    @app_commands.command(name="daily", description="每日簽到領取 50,000 楓幣 (每日 00:00 重置)")
    async def daily_checkin(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        now = datetime.datetime.now(self.tz)
        today_str = now.strftime("%Y-%m-%d")

        if self.last_checkin.get(user_id) == today_str:
            await interaction.response.send_message("❌ 你今天已經簽到過了喔！請於台灣時間 00:00 後再來簽到。", ephemeral=True)
            return

        self.user_balances[user_id] = self.user_balances.get(user_id, 0) + 50000
        self.last_checkin[user_id] = today_str
        
        balance = self.user_balances[user_id]
        await interaction.response.send_message(f"🎉 **簽到成功！** 你領取了每日獎勵 **50,000** 楓幣！\n💰 目前錢包餘額：**{balance:,} 楓幣**")

    @app_commands.command(name="claim", description="領取 1,000,000 楓幣新手下注資金（限領一次）")
    async def claim_funds(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        if user_id in self.claimed_users:
            await interaction.response.send_message("❌ 你已經領取過新手資金了，不能重複領取喔！", ephemeral=True)
            return

        self.user_balances[user_id] = self.user_balances.get(user_id, 0) + 1000000
        self.claimed_users.add(user_id)
        
        balance = self.user_balances[user_id]
        await interaction.response.send_message(f"🎉 **領取成功！** 你獲得了 **1,000,000** 楓幣新手資金！\n💰 目前錢包餘額：**{balance:,} 楓幣**", ephemeral=True)

    @app_commands.command(name="balance", description="查詢自己目前的楓幣餘額")
    async def check_balance(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        balance = self.user_balances.get(user_id, 0)
        await interaction.response.send_message(f"💰 你的目前楓幣餘額：**{balance:,} 楓幣**", ephemeral=True)

    def calculate_payout_message(self, winning_numbers: set):
        result_msg = "💰 **本期派彩結果：**\n"
        winners_count = 0
        
        for user_id, user_bets in self.daily_bets.items():
            win_cars = 0.0
            for num, rate in user_bets.items():
                if num in winning_numbers:
                    win_cars += rate
            
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"玩家 {user_id}"

            if win_cars > 0:
                winners_count += 1
                prize = int(win_cars * self.PRIZE_PER_CAR)
                self.user_balances[user_id] = self.user_balances.get(user_id, 0) + prize
                result_msg += f"✨ {name} 命中 {win_cars:g} 車，獲得 **{prize:,}** 楓幣！\n"
            else:
                result_msg += f"💧 {name} 未中獎\n"

        if winners_count == 0:
            result_msg += "\n今日無人中獎，明天繼續努力！"
            
        return result_msg

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # 讓所有以 ! 開頭的傳統指令（如 !sync）直接放行給機器人處理
        if message.content.startswith("!"):
            await self.bot.process_commands(message)
            return

        if self.bet_channel_id and message.channel.id != self.bet_channel_id:
            return

        pattern = r"(0?[1-9]|[1-3][0-9])[xX\*]([0-9]+(?:\.[0-9]+)?)"
        matches = re.findall(pattern, message.content)

        if not matches:
            return 

        if not self.bet_channel_id:
            self.bet_channel_id = message.channel.id

        # 檢查下注時間限制 (只允許週一至週六 00:00 ~ 20:00 下注)
        now = datetime.datetime.now(self.tz)
        if now.weekday() == 6:  # 6 代表週日
            await message.reply("❌ **下注失敗！** 今日（週日）為非開獎日，暫不開放下注。")
            return
            
        if now.time() >= datetime.time(hour=20, minute=0):
            await message.reply("❌ **下注失敗！** 已經超過今日下注截止時間（20:00），現在提交的下注視為無效！")
            return

        user_id = message.author.id
        
        total_bet_cars = 0.0
        temp_bets = {}
        for number, rate_str in matches:
            rate = float(rate_str)
            std_number = str(int(number)).zfill(2)
            temp_bets[std_number] = temp_bets.get(std_number, 0.0) + rate
            total_bet_cars += rate

        total_cost = int(total_bet_cars * self.COST_PER_CAR)

        current_balance = self.user_balances.get(user_id, 0)
        if current_balance < total_cost:
            await message.reply(f"❌ **餘額不足！** 你的錢包只有 `{current_balance:,} 楓幣`，此次下注需要 `{total_cost:,} 楓幣`。請先輸入 `/daily` 或 `/claim` 領取資金！")
            return

        self.user_balances[user_id] = current_balance - total_cost

        if user_id not in self.daily_bets:
            self.daily_bets[user_id] = {}

        bet_details = []
        for std_number, rate in temp_bets.items():
            current_rate = self.daily_bets[user_id].get(std_number, 0.0)
            if current_rate + rate > 1000:
                rate = 1000 - current_rate
                if rate <= 0:
                    continue
            self.daily_bets[user_id][std_number] = current_rate + rate
            display_number = int(std_number)
            bet_details.append(f"{display_number}號{rate:g}車")

        remaining_balance = self.user_balances[user_id]
        detail_str = " ".join(bet_details)
        reply_msg = f"🎰 **成功下注!** {detail_str}\n"
        reply_msg += f"*(總計 {total_bet_cars:g} 車，扣除 {total_cost:,} 楓幣 | 剩餘餘額：{remaining_balance:,} 楓幣)*"
        
        await message.reply(reply_msg)

    # 每日 21:00 觸發自動開獎與派彩
    @tasks.loop(time=draw_time)
    async def auto_draw_task(self):
        now = datetime.datetime.now(self.tz)
        if now.weekday() == 6 or not self.bet_channel_id:
            return

        channel = self.bot.get_channel(self.bet_channel_id)
        if not channel:
            return

        await channel.send("🔍 **時間到！自動連線抓取今日 今彩539 開獎結果...**")

        try:
            # 採用穩定的第三方開獎資訊站抓取
            url = "https://tw.pilio.idv.tw/ltobig/list.asp"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    html = await response.text()
                    
            soup = BeautifulSoup(html, "html.parser")
            number_tags = soup.find_all('b')
            numbers = []
            for tag in number_tags:
                text = tag.get_text(strip=True)
                if text.isdigit() and 1 <= int(text) <= 39:
                    numbers.append(text.zfill(2))
                    if len(numbers) == 5:
                        break

            issue_number = now.strftime("%Y%m%d")
            if len(numbers) < 5:
                raise ValueError("無法抓取完整 5 個號碼")

            num_list = sorted(numbers)
            winning_numbers = set(num_list)

            announcement = (
                f"🎰 **咕咕谷39 今日({issue_number})開獎結果**\n\n"
                f"開獎號碼：{'、'.join(num_list)}\n\n"
                f"*(正在計算派彩結果...)*"
            )
            await channel.send(announcement)

            result_msg = self.calculate_payout_message(winning_numbers)
            await channel.send(result_msg)
            self.daily_bets.clear()

        except Exception as e:
            log.error(f"自動抓取失敗: {e}")
            await channel.send("⚠️ **自動抓取開獎號碼失敗！請管理員使用 `/draw39` 手動開獎。**")

    @app_commands.command(name="draw39", description="[管理員] 手動輸入期數與今彩539開獎號碼並進行派彩")
    @app_commands.default_permissions(administrator=True)
    async def draw_39(self, interaction: discord.Interaction, issue_number: str, n1: str, n2: str, n3: str, n4: str, n5: str):
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ **權限不足：** 你必須是伺服器管理員或機器人授權管理員才能使用此指令！", ephemeral=True)
            return

        num_list = sorted([str(n1).zfill(2), str(n2).zfill(2), str(n3).zfill(2), str(n4).zfill(2), str(n5).zfill(2)])
        winning_numbers = set(num_list)
        
        announcement = (
            f"🎰 **咕咕谷39 第{issue_number}期手動開獎結果**\n\n"
            f"開獎號碼：{'、'.join(num_list)}\n\n"
            f"*(正在計算派彩結果...)*"
        )
        await interaction.response.send_message(announcement)
        
        result_msg = self.calculate_payout_message(winning_numbers)
        await interaction.followup.send(result_msg)
        self.daily_bets.clear()

async def setup(bot):
    await bot.add_cog(GuGu39(bot))
