import asyncio
import json
import os
from threading import Thread
import time
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# --- ระบบเว็บจำลองสำหรับ Render ---
app = Flask("")


@app.route("/")
def home():
  return "Gatekeeper Bot is alive!"


def run():
  app.run(host="0.0.0.0", port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# --- ระบบจัดการการตั้งค่าแยกตามเซิร์ฟเวอร์ ---
CONFIG_FILE = "servers_config.json"


def load_config():
  if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
      return json.load(f)
  return {}


def save_config(data):
  with open(CONFIG_FILE, "w") as f:
    json.dump(data, f, indent=4)


def get_guild_config(guild_id):
  g_id = str(guild_id)
  if g_id not in config:
    config[g_id] = {
        "channel_id": None,
        "text_cooldown": 0,
        "image_cooldown": 300,
    }
    save_config(config)
  return config[g_id]


config = load_config()
lock_states = {}

# --- ตั้งค่าบอท Discord ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  await bot.tree.sync()
  print(f"บอทออนไลน์แล้ว: {bot.user}")


def format_time(seconds: int) -> str:
  if seconds >= 3600 and seconds % 3600 == 0:
    return f"{seconds // 3600} ชั่วโมง"
  elif seconds >= 60 and seconds % 60 == 0:
    return f"{seconds // 60} นาที"
  else:
    return f"{seconds} วินาที"


# --- คำสั่ง Slash Commands (แสดงข้อความให้ทุกคนเห็นในแชท) ---


@bot.tree.command(
    name="set_channel", description="เลือกห้องแชทที่จะเปิดใช้งานระบบล็อกเวลา"
)
@app_commands.checks.has_permissions(administrator=True)
async def set_channel(
    interaction: discord.Interaction, channel: discord.TextChannel
):
  g_conf = get_guild_config(interaction.guild_id)
  g_conf["channel_id"] = channel.id
  save_config(config)
  await interaction.response.send_message(
      f"✅ {interaction.user.mention} เปิดใช้งานระบบล็อกเวลาที่ห้อง"
      f" {channel.mention} เรียบร้อยแล้ว!"
  )


@bot.tree.command(
    name="set_cooldown",
    description="ตั้งเวลาดีเลย์ (เลือกประเภทและหน่วยเวลาได้เอง)",
)
@app_commands.describe(
    target="เลือกสิ่งที่จะล็อก (ข้อความ หรือ รูปภาพ/ไฟล์)",
    amount="ใส่จำนวนเวลา (ใส่ 0 เพื่อปิดการล็อกประเภทนี้)",
    unit="เลือกหน่วยเวลา (วินาที / นาที / ชั่วโมง)",
)
@app_commands.choices(
    target=[
        app_commands.Choice(
            name="💬 ข้อความอย่างเดียว (Text Only)", value="text"
        ),
        app_commands.Choice(
            name="🖼️ รูปภาพ/วิดีโอ/ไฟล์ (Media/Files)", value="image"
        ),
    ],
    unit=[
        app_commands.Choice(name="วินาที (Seconds)", value=1),
        app_commands.Choice(name="นาที (Minutes)", value=60),
        app_commands.Choice(name="ชั่วโมง (Hours)", value=3600),
    ],
)
@app_commands.checks.has_permissions(administrator=True)
async def set_cooldown(
    interaction: discord.Interaction,
    target: app_commands.Choice[str],
    amount: int,
    unit: app_commands.Choice[int],
):
  if amount < 0:
    await interaction.response.send_message(
        "❌ กรุณาใส่ตัวเลข 0 ขึ้นไปครับ", ephemeral=True
    )
    return

  total_seconds = amount * unit.value
  g_conf = get_guild_config(interaction.guild_id)

  if target.value == "text":
    g_conf["text_cooldown"] = total_seconds
  else:
    g_conf["image_cooldown"] = total_seconds

  save_config(config)

  if total_seconds == 0:
    msg = (
        f"✅ {interaction.user.mention} **ปิดการล็อก** สำหรับ **{target.name}**"
        " เรียบร้อยแล้ว!"
    )
  else:
    msg = (
        f"✅ {interaction.user.mention} ตั้งเวลาล็อก **{target.name}** เป็น"
        f" **{amount} {unit.name}** เรียบร้อย!"
    )

  await interaction.response.send_message(msg)


@bot.tree.command(
    name="disable", description="ปิดการทำงานของบอทในเซิร์ฟเวอร์นี้ชั่วคราว"
)
@app_commands.checks.has_permissions(administrator=True)
async def disable(interaction: discord.Interaction):
  g_conf = get_guild_config(interaction.guild_id)
  g_conf["channel_id"] = None
  save_config(config)
  await interaction.response.send_message(
      f"🛑 {interaction.user.mention}"
      " ปิดการทำงานของระบบล็อกเวลาในเซิร์ฟเวอร์นี้แล้ว"
  )


@bot.tree.command(
    name="status", description="ตรวจสอบการตั้งค่าปัจจุบันของเซิร์ฟเวอร์นี้"
)
async def status(interaction: discord.Interaction):
  g_conf = get_guild_config(interaction.guild_id)
  ch_id = g_conf.get("channel_id")
  ch_text = f"<#{ch_id}>" if ch_id else "ปิดใช้งานอยู่ (ใช้ /set_channel เพื่อเปิด)"

  t_cd = g_conf["text_cooldown"]
  i_cd = g_conf["image_cooldown"]

  t_str = format_time(t_cd) if t_cd > 0 else "ไม่ล็อก (ส่งได้ตลอด)"
  i_str = format_time(i_cd) if i_cd > 0 else "ไม่ล็อก (ส่งได้ตลอด)"

  embed = discord.Embed(
      title=f"⚙️ สถานะระบบคูลดาวน์ ({interaction.guild.name})",
      color=discord.Color.blue(),
  )
  embed.add_field(name="📍 ห้องที่ใช้งาน", value=ch_text, inline=False)
  embed.add_field(name="💬 ล็อกข้อความ", value=t_str, inline=True)
  embed.add_field(name="🖼️ ล็อกรูปภาพ/ไฟล์", value=i_str, inline=True)
  await interaction.response.send_message(embed=embed)


# --- ระบบตรวจจับและบังคับล็อกทุกคน (รวม Owner/Admin) ---


@bot.event
async def on_message(message):
  if message.author.bot or not message.guild:
    return

  g_conf = get_guild_config(message.guild.id)
  if not g_conf["channel_id"] or message.channel.id != g_conf["channel_id"]:
    return

  ch_id = message.channel.id
  now = time.time()

  if ch_id not in lock_states:
    lock_states[ch_id] = {"text_until": 0, "image_until": 0}

  state = lock_states[ch_id]
  has_media = len(message.attachments) > 0

  # กรณีที่ 1: ส่งรูปภาพ / วิดีโอ / ไฟล์
  if has_media:
    cd = g_conf["image_cooldown"]
    if cd <= 0:
      return

    if now < state["image_until"]:
      remaining = int(state["image_until"] - now)
      try:
        await message.delete()
        warn = await message.channel.send(
            f"⏳ {message.author.mention} **ติดคูลดาวน์รูปภาพ/ไฟล์!** กรุณารออีก"
            f" **{format_time(remaining)}**"
        )
        await asyncio.sleep(5)
        await warn.delete()
      except discord.Forbidden:
        await message.channel.send(
            "⚠️ บอทไม่มีสิทธิ์ลบข้อความ! กรุณาเปิดสิทธิ์ `Manage Messages` ให้บอท"
        )
      return

    state["image_until"] = now + cd
    info = await message.channel.send(
        f"🖼️ **ล็อกการส่งรูปภาพ/ไฟล์ชั่วคราว!** กรุณารอ **{format_time(cd)}**"
        " ก่อนส่งรูปถัดไป *(ยังพิมพ์ข้อความคุยได้ปกติ)*"
    )
    await asyncio.sleep(cd)
    try:
      await info.delete()
    except:
      pass

  # กรณีที่ 2: ส่งข้อความธรรมดา
  else:
    cd = g_conf["text_cooldown"]
    if cd <= 0:
      return

    if now < state["text_until"]:
      remaining = int(state["text_until"] - now)
      try:
        await message.delete()
        warn = await message.channel.send(
            f"⏳ {message.author.mention} **ติดคูลดาวน์ข้อความ!** กรุณารออีก"
            f" **{format_time(remaining)}**"
        )
        await asyncio.sleep(5)
        await warn.delete()
      except discord.Forbidden:
        await message.channel.send(
            "⚠️ บอทไม่มีสิทธิ์ลบข้อความ! กรุณาเปิดสิทธิ์ `Manage Messages` ให้บอท"
        )
      return

    state["text_until"] = now + cd
    info = await message.channel.send(
        f"💬 **ล็อกการส่งข้อความชั่วคราว!** กรุณารอ **{format_time(cd)}**"
        " ก่อนส่งข้อความถัดไป"
    )
    await asyncio.sleep(cd)
    try:
      await info.delete()
    except:
      pass


keep_alive()
bot.run(os.environ.get("TOKEN"))
