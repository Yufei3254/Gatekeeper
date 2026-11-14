import asyncio
import os
import re
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


# --- ระบบอ่าน/บันทึกการตั้งค่าลงใน Channel Topic (จำถาวรไม่มีวันหาย) ---
def get_channel_config(channel: discord.TextChannel):
  topic = channel.topic or ""
  match = re.search(r"\[GK:T=(\d+),I=(\d+)\]", topic)
  if match:
    return {
        "active": True,
        "text_cooldown": int(match.group(1)),
        "image_cooldown": int(match.group(2)),
    }
  return {"active": False, "text_cooldown": 0, "image_cooldown": 0}


async def save_channel_config(
    channel: discord.TextChannel, text_cd: int, image_cd: int, active: bool
):
  topic = channel.topic or ""
  clean_topic = re.sub(r"\s*\[GK:T=\d+,I=\d+\]", "", topic).strip()

  if active and (text_cd > 0 or image_cd > 0):
    tag = f"[GK:T={text_cd},I={image_cd}]"
    new_topic = f"{clean_topic} {tag}".strip() if clean_topic else tag
  else:
    new_topic = clean_topic

  await channel.edit(topic=new_topic)


lock_states = {}
allowed_messages = set()

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


# --- คำสั่ง Slash Commands ---


@bot.tree.command(
    name="set_cooldown", description="เลือกห้องและตั้งเวลาดีเลย์ (จำค่าถาวร)"
)
@app_commands.describe(
    channel="เลือกห้องแชทที่ต้องการตั้งค่า",
    target="เลือกสิ่งที่จะล็อก (ข้อความ หรือ รูปภาพ/ไฟล์/ลิงก์)",
    amount="ใส่จำนวนเวลา (ใส่ 0 เพื่อปิดการล็อกประเภทนี้)",
    unit="เลือกหน่วยเวลา (วินาที / นาที / ชั่วโมง)",
)
@app_commands.choices(
    target=[
        app_commands.Choice(
            name="ข้อความอย่างเดียว (Text Only)", value="text"
        ),
        app_commands.Choice(
            name="รูปภาพ/ไฟล์/GIF/ลิงก์ (Media & Links)", value="image"
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
    channel: discord.TextChannel,
    target: app_commands.Choice[str],
    amount: int,
    unit: app_commands.Choice[int],
):
  if amount < 0:
    await interaction.response.send_message(
        "กรุณาใส่ตัวเลข 0 ขึ้นไปครับ", ephemeral=True
    )
    return

  await interaction.response.defer()

  current_conf = get_channel_config(channel)
  text_cd = current_conf["text_cooldown"]
  image_cd = current_conf["image_cooldown"]
  total_seconds = amount * unit.value

  if target.value == "text":
    text_cd = total_seconds
  else:
    image_cd = total_seconds

  try:
    is_active = text_cd > 0 or image_cd > 0
    await save_channel_config(channel, text_cd, image_cd, active=is_active)

    if total_seconds == 0:
      msg = (
          f"✅ {interaction.user.mention} **ปิดการล็อก** สำหรับ"
          f" **{target.name}** ในห้อง {channel.mention} เรียบร้อยแล้ว"
      )
    else:
      msg = (
          f"✅ {interaction.user.mention} ตั้งเวลาล็อก **{target.name}** ในห้อง"
          f" {channel.mention} เป็น **{amount} {unit.name}** เรียบร้อย"
          " *(บันทึกถาวร)*"
      )
    await interaction.followup.send(msg)
  except discord.Forbidden:
    await interaction.followup.send(
        f"**บอทไม่มีสิทธิ์แก้ไขหัวข้อห้อง {channel.mention}** กรุณาเปิดสิทธิ์"
        " `Manage Channels` ให้บอทก่อนครับ"
    )


@bot.tree.command(name="disable", description="เลือกห้องเพื่อปิดระบบล็อกเวลา")
@app_commands.describe(channel="เลือกห้องแชทที่ต้องการปิดระบบล็อก")
@app_commands.checks.has_permissions(administrator=True)
async def disable(
    interaction: discord.Interaction, channel: discord.TextChannel
):
  await interaction.response.defer()
  try:
    await save_channel_config(channel, 0, 0, active=False)
    await interaction.followup.send(
        f"✅ {interaction.user.mention} ปิดระบบล็อกเวลาในห้อง"
        f" {channel.mention} เรียบร้อยแล้ว"
    )
  except discord.Forbidden:
    await interaction.followup.send(
        f"**บอทไม่มีสิทธิ์แก้ไขหัวข้อห้อง {channel.mention}** กรุณาเปิดสิทธิ์"
        " `Manage Channels` ให้บอท"
    )


@bot.tree.command(
    name="status", description="ตรวจสอบการตั้งค่าของห้อง (เลือกห้องได้)"
)
@app_commands.describe(channel="เลือกห้องที่ต้องการดู (ไม่เลือก = ดูห้องนี้)")
async def status(
    interaction: discord.Interaction, channel: discord.TextChannel = None
):
  target_channel = channel or interaction.channel
  conf = get_channel_config(target_channel)

  t_cd = conf["text_cooldown"]
  i_cd = conf["image_cooldown"]

  t_str = format_time(t_cd) if t_cd > 0 else "ไม่ล็อก (ส่งได้ตลอด)"
  i_str = format_time(i_cd) if i_cd > 0 else "ไม่ล็อก (ส่งได้ตลอด)"

  status_text = (
      "เปิดใช้งานอยู่ (บันทึกถาวร)" if conf["active"] else "ปิดใช้งานอยู่"
  )

  embed = discord.Embed(
      title=f"สถานะระบบคูลดาวน์ของห้อง #{target_channel.name}",
      color=discord.Color.green() if conf["active"] else discord.Color.red(),
  )
  embed.add_field(name="สถานะ", value=status_text, inline=False)
  embed.add_field(name="ล็อกข้อความ", value=t_str, inline=True)
  embed.add_field(name="ล็อกรูปภาพ/ไฟล์/ลิงก์", value=i_str, inline=True)
  await interaction.response.send_message(embed=embed)


# --- ฟังก์ชันตรวจจับและจัดการข้อความ ---


async def process_message(message, is_edit=False):
  if message.author.bot or not message.guild:
    return

  if message.id in allowed_messages:
    return

  conf = get_channel_config(message.channel)
  if not conf["active"]:
    return

  ch_id = message.channel.id
  now = time.time()

  if ch_id not in lock_states:
    lock_states[ch_id] = {"text_until": 0, "image_until": 0}

  state = lock_states[ch_id]

  content_lower = message.content.lower()
  has_media = (
      len(message.attachments) > 0
      or len(message.embeds) > 0
      or "http://" in content_lower
      or "https://" in content_lower
      or "tenor.com" in content_lower
      or "giphy.com" in content_lower
  )

  # 1. หมวดรูปภาพ / ไฟล์ / GIF / ลิงก์
  if has_media:
    cd = conf["image_cooldown"]
    if cd <= 0:
      return

    if now < state["image_until"]:
      remaining = max(1, int(state["image_until"] - now))
      try:
        await message.delete()
        warn = await message.channel.send(
            f"{message.author.mention} **ติดคูลดาวน์รูปภาพ/ลิงก์**"
            f" กรุณารออีก **{format_time(remaining)}**"
        )
        await asyncio.sleep(5)
        await warn.delete()
      except discord.Forbidden:
        pass
      return

    allowed_messages.add(message.id)
    state["image_until"] = now + cd

    info = await message.channel.send(
        f"**ล็อกการส่งรูปภาพ/ลิงก์ชั่วคราว** กรุณารอ **{format_time(cd)}**"
        " ก่อนส่งรายการถัดไป"
    )
    await asyncio.sleep(cd)
    allowed_messages.discard(message.id)
    try:
      await info.delete()
    except:
      pass

  # 2. หมวดข้อความธรรมดา
  elif not is_edit:
    cd = conf["text_cooldown"]
    if cd <= 0:
      return

    if now < state["text_until"]:
      remaining = max(1, int(state["text_until"] - now))
      try:
        await message.delete()
        warn = await message.channel.send(
            f"{message.author.mention} **ติดคูลดาวน์ข้อความ**"
            f" กรุณารออีก **{format_time(remaining)}**"
        )
        await asyncio.sleep(5)
        await warn.delete()
      except discord.Forbidden:
        pass
      return

    allowed_messages.add(message.id)
    state["text_until"] = now + cd

    info = await message.channel.send(
        f"**ล็อกการส่งข้อความชั่วคราว** กรุณารอ **{format_time(cd)}**"
        " ก่อนส่งข้อความถัดไป"
    )
    await asyncio.sleep(cd)
    allowed_messages.discard(message.id)
    try:
      await info.delete()
    except:
      pass


@bot.event
async def on_message(message):
  await process_message(message, is_edit=False)


@bot.event
async def on_message_edit(before, after):
  await process_message(after, is_edit=True)


keep_alive()
bot.run(os.environ.get("TOKEN"))
