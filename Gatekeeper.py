import asyncio
import json
import os
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# --- ระบบเว็บจำลองสำหรับ Render ---
app = Flask("")


@app.route("/")
def home():
  return "Bot is alive and ready for all servers!"


def run():
  app.run(host="0.0.0.0", port=8080)


def keep_alive():
  t = Thread(target=run, daemon=True)
  t.start()


# --- ระบบจัดการการตั้งค่าแบบแยกเซิร์ฟเวอร์ ---
CONFIG_FILE = "servers_config.json"
DEFAULT_GUILD_CONFIG = {
    "channel_id": None,
    "text_cooldown": 300,  # ค่าเริ่มต้นข้อความ: 5 นาที
    "image_cooldown": 600,  # ค่าเริ่มต้นรูปภาพ: 10 นาที
}


def load_config():
  config = {}
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r") as f:
        loaded = json.load(f)
      if isinstance(loaded, dict):
        config = loaded
    except (json.JSONDecodeError, OSError):
      pass
  return config


def save_config(data):
  with open(CONFIG_FILE, "w") as f:
    json.dump(data, f, indent=4)


def get_guild_config(guild_id):
  g_id = str(guild_id)
  if g_id not in config:
    config[g_id] = DEFAULT_GUILD_CONFIG.copy()
    save_config(config)
  else:
    config[g_id] = {**DEFAULT_GUILD_CONFIG, **config[g_id]}
  return config[g_id]


config = load_config()
locked_channels = set()  # เก็บรายชื่อ ID ห้องที่กำลังถูกล็อกอยู่ (แยกตามห้อง)

# --- ตั้งค่าบอท Discord ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  await bot.tree.sync()
  print(
      f"บอทออนไลน์แล้วในชื่อ: {bot.user} (พร้อมใช้งานใน {len(bot.guilds)}"
      " เซิร์ฟเวอร์)"
  )


# --- คำสั่ง Slash Commands สำหรับแอดมินแต่ละเซิร์ฟเวอร์ ---


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
      f"✅ เปิดใช้งานระบบล็อกเวลาที่ห้อง {channel.mention} เรียบร้อยแล้ว!",
      ephemeral=True,
  )


@bot.tree.command(
    name="set_text", description="ตั้งเวลาล็อกเมื่อมีคนส่งข้อความ (หน่วย: วินาที)"
)
@app_commands.describe(seconds="ใส่จำนวนวินาที (เช่น 300 = 5 นาที, 0 = ไม่ล็อก)")
@app_commands.checks.has_permissions(administrator=True)
async def set_text(interaction: discord.Interaction, seconds: int):
  if seconds < 0:
    await interaction.response.send_message(
        "❌ กรุณาใส่ตัวเลข 0 ขึ้นไปครับ", ephemeral=True
    )
    return
  g_conf = get_guild_config(interaction.guild_id)
  g_conf["text_cooldown"] = seconds
  save_config(config)
  await interaction.response.send_message(
      f"✅ ตั้งเวลาล็อกเมื่อส่ง **ข้อความ** เป็น **{seconds} วินาที** เรียบร้อย!",
      ephemeral=True,
  )


@bot.tree.command(
    name="set_image",
    description="ตั้งเวลาล็อกเมื่อมีคนส่งรูปภาพหรือไฟล์ (หน่วย: วินาที)",
)
@app_commands.describe(seconds="ใส่จำนวนวินาที (เช่น 600 = 10 นาที, 0 = ไม่ล็อก)")
@app_commands.checks.has_permissions(administrator=True)
async def set_image(interaction: discord.Interaction, seconds: int):
  if seconds < 0:
    await interaction.response.send_message(
        "❌ กรุณาใส่ตัวเลข 0 ขึ้นไปครับ", ephemeral=True
    )
    return
  g_conf = get_guild_config(interaction.guild_id)
  g_conf["image_cooldown"] = seconds
  save_config(config)
  await interaction.response.send_message(
      f"✅ ตั้งเวลาล็อกเมื่อส่ง **รูปภาพ/ไฟล์** เป็น **{seconds} วินาที** เรียบร้อย!",
      ephemeral=True,
  )


@bot.tree.command(
    name="disable", description="ปิดการทำงานของบอทในเซิร์ฟเวอร์นี้ชั่วคราว"
)
@app_commands.checks.has_permissions(administrator=True)
async def disable(interaction: discord.Interaction):
  g_conf = get_guild_config(interaction.guild_id)
  g_conf["channel_id"] = None
  save_config(config)
  await interaction.response.send_message(
      "🛑 ปิดการทำงานของระบบล็อกเวลาในเซิร์ฟเวอร์นี้แล้ว (ใช้ /set_channel"
      " เพื่อเปิดใหม่)",
      ephemeral=True,
  )


@bot.tree.command(
    name="status", description="ตรวจสอบการตั้งค่าปัจจุบันของเซิร์ฟเวอร์นี้"
)
async def status(interaction: discord.Interaction):
  g_conf = get_guild_config(interaction.guild_id)
  ch_id = g_conf.get("channel_id")
  ch_text = f"<#{ch_id}>" if ch_id else "ปิดใช้งานอยู่ (ใช้ /set_channel เพื่อเปิด)"

  embed = discord.Embed(
      title=f"⚙️ สถานะระบบคูลดาวน์ ({interaction.guild.name})",
      color=discord.Color.green(),
  )
  embed.add_field(name="📍 ห้องที่ใช้งาน", value=ch_text, inline=False)
  embed.add_field(
      name="💬 ดีเลย์ข้อความ",
      value=f"{g_conf['text_cooldown']} วินาที",
      inline=True,
  )
  embed.add_field(
      name="🖼️ ดีเลย์รูปภาพ/ไฟล์",
      value=f"{g_conf['image_cooldown']} วินาที",
      inline=True,
  )
  await interaction.response.send_message(embed=embed, ephemeral=True)


# --- ระบบตรวจจับข้อความและรูปภาพ ---


@bot.event
async def on_message(message):
  # ข้ามข้อความจากบอท หรือข้อความส่วนตัว (DM)
  if message.author.bot or not message.guild:
    return

  g_conf = get_guild_config(message.guild.id)

  # ตรวจสอบว่าเป็นห้องที่ตั้งค่าไว้หรือไม่
  if not g_conf["channel_id"] or message.channel.id != g_conf["channel_id"]:
    return

  # ถ้าห้องนี้กำลังถูกล็อกอยู่ ให้ข้ามไป
  if message.channel.id in locked_channels:
    return

  # ตรวจสอบว่าเป็นรูปภาพ/ไฟล์แนบ หรือข้อความ
  has_media = len(message.attachments) > 0
  if has_media:
    cooldown = g_conf["image_cooldown"]
    msg_type = "รูปภาพ/ไฟล์"
  else:
    cooldown = g_conf["text_cooldown"]
    msg_type = "ข้อความ"

  if cooldown <= 0:
    return

  # เริ่มล็อกเฉพาะห้องนี้
  locked_channels.add(message.channel.id)
  channel = message.channel
  everyone_role = message.guild.default_role

  try:
    await channel.set_permissions(everyone_role, send_messages=False)

    minutes = cooldown // 60
    rem_sec = cooldown % 60
    time_str = f"{minutes} นาที" if rem_sec == 0 else f"{cooldown} วินาที"

    info_msg = await channel.send(
        f"⏳ **ห้องถูกล็อกชั่วคราว!** (มีการส่ง{msg_type}) กรุณารอ"
        f" **{time_str}** ก่อนส่งรายการถัดไป"
    )

    await asyncio.sleep(cooldown)

    await channel.set_permissions(everyone_role, send_messages=True)
    try:
      await info_msg.delete()
    except:
      pass
  except discord.Forbidden:
    # กรณีแอดมินเซิร์ฟเวอร์ลืมให้สิทธิ์ Manage Roles หรือลากยศบอทไว้ต่ำเกินไป
    await channel.send(
        "⚠️ **บอทไม่มีสิทธิ์ล็อกห้อง!** กรุณาให้สิทธิ์ `Manage Roles` และลากยศของบอทไว้เหนือยศสมาชิกทั่วไป"
    )
  finally:
    # ปลดสถานะล็อกออกจากระบบเสมอ แม้จะเกิดข้อผิดพลาด
    locked_channels.discard(message.channel.id)



def main():
  token = os.environ.get("TOKEN")
  if not token:
    raise RuntimeError("TOKEN environment variable is not set.")
  keep_alive()
  bot.run(token)


if __name__ == "__main__":
  main()
