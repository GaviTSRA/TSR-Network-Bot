import asyncio
import discord
from discord.utils import get
from discord.ext import commands
import platform
import subprocess
from datetime import datetime
import socket
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PREFIX = '>'
EMOJI_RUNNING = ":green_circle:"
EMOJI_OFFLINE = ":red_circle:"

ips = {
    "hub": "ult4.falix.gg:26904",
    "sandbox": "ult10.falix.gg:27370",
    "survival": "ult7.falix.gg:25843",
    "anarchy": "ult5.falix.gg:27319",
    "sandbox_backup": "ult4.falix.gg:27180",
    "smp": "ult1.falix.gg:26017",
    "gt": "ult7.falix.gg:26811",
    "website": "gavitsra.github.io",
    "smp_dynmap": "ult1.falix.gg:26984"
}
show_ips = {
    "hub": "ult4.falix.gg:26904",
    "sandbox": "ult10.falix.gg:27370",
    "survival": "ult7.falix.gg:25843",
    "anarchy": "ult5.falix.gg:27319",
    "sandbox_backup": "ult4.falix.gg:27180",
    "smp": "smp.tsrnetwork.ga",
    "gt": "Private",
    "website": "tsrnetwork.ga",
    "smp_dynmap": "ult1.falix.gg:26984"
}

bot = commands.Bot(command_prefix=PREFIX)
client = discord.Client()

@client.event
async def on_ready():
    print('Ready')

@client.event
async def on_message(message):
    await client.wait_until_ready()
    if message.content.startswith(PREFIX):
        args = message.content.split(' ')
        args[0] = args[0].replace(">", "")

        if args[0] == 'poll':
            text = ""
            for arg in args[4:]:
                text += arg + " "
            texts = text.split("|")
            try:
                color = discord.Colour.from_rgb(int(args[1]), int(args[2]), int(args[3]))
            except ValueError:
                await message.channel.send("Invalid rgb color! (Did you use numbers from 0-255?)")
            except IndexError:
                await message.channel.send("Syntax: " + PREFIX + "poll R G B TITLE | DESCRIPTION")
            try:
                desc = texts[1]
            except IndexError:
                await message.channel.send("Invalid description! (Did you use | to separate title and description?)")
            embed = discord.Embed(
                title=texts[0],
                description=desc,
                color=color
            )
            message2 = await message.channel.send(embed=embed)
            await message2.add_reaction('⬆️')
            await message2.add_reaction('⬇️')
            await message.delete()

        elif args[0] == 'roleMessage':
            if not message.author.bot:
                for role in message.author.roles:
                    if role.name == 'Owner':
                        roleName = args[1]
                        for arg in args[2:-1]:
                            roleName += " " + arg
                            embed = discord.Embed(
                                title="Get a role by reacting",
                                description=roleName + " | " + args[-1]
                            )
                            message2 = await message.channel.send(embed=embed)
                            await message2.add_reaction(args[-1])
                            await message.delete()
                            break

        elif args[0] == 'status':
            embed = discord.Embed(title="TSR Network Status",description=f"{EMOJI_OFFLINE}: Offline or Unknown\n{EMOJI_RUNNING}: Online\nChecked at: {datetime.utcnow()} (UTC)")
            embed.add_field(
                name="Mindustry Servers",
                value='{hub} Hub\n{sandbox} Sandbox\n{survival} Survival\n{anarchy} Anarchy\n{sandbox_backup} Sandbox Backup'.format(
                    hub=EMOJI_RUNNING if ping(ips["hub"]) else EMOJI_OFFLINE,
                    sandbox=EMOJI_RUNNING if ping(ips["sandbox"]) else EMOJI_OFFLINE,
                    survival=EMOJI_RUNNING if ping(ips["survival"]) else EMOJI_OFFLINE,
                    anarchy=EMOJI_RUNNING if ping(ips["anarchy"]) else EMOJI_OFFLINE,
                    sandbox_backup=EMOJI_RUNNING if ping(ips["sandbox_backup"]) else EMOJI_OFFLINE,
                )
            )
            embed.add_field(
                name="Minecraft Servers",
                value="{smp} SMP\n{gt} GT".format(
                    smp=EMOJI_RUNNING if ping(ips["smp"]) else EMOJI_OFFLINE,
                    gt=EMOJI_RUNNING if ping(ips["gt"]) else EMOJI_OFFLINE,
                )
            )
            embed.add_field(
                name="Other",
                value="{website} TSR Website\n{smp_dynmap} SMP Dynmap".format(
                    website=EMOJI_RUNNING if ping(ips["website"]) else EMOJI_OFFLINE,
                    smp_dynmap=EMOJI_RUNNING if ping(ips["smp_dynmap"]) else EMOJI_OFFLINE,
                )
            )
            await message.channel.send(embed=embed)
            await message.delete()

        elif args[0] == 'ips':
            embed = discord.Embed(
                title="TSR Network Ips",
                description=""
            )
            embed.add_field(
                name="Mindustry Servers",
                value="Hub:\n{hub}\nSandbox:\n{sandbox}\nSurvival:\n{survival}\nAnarchy:\n{anarchy}\nSandbox Backup:\n{sandbox_backup}".format(
                    hub=show_ips["hub"],
                    sandbox=show_ips["sandbox"],
                    survival=show_ips["survival"],
                    anarchy=show_ips["anarchy"],
                    sandbox_backup=show_ips["sandbox_backup"],
                )
            )
            embed.add_field(
                name="Minecraft Servers",
                value="SMP:\n{smp}\nGT:\n{gt}".format(
                    smp=show_ips["smp"],
                    gt=show_ips["gt"],
                )
            )
            embed.add_field(
                name="Other",
                value="TSR Website:\n{website}\nSMP Dynmap:\n{smp_dynmap}".format(
                    website=show_ips["website"],
                    smp_dynmap=show_ips["smp_dynmap"],
                )
            )
            await message.channel.send(embed=embed)
            await message.delete()

        elif args[0] == 'status_task':
            if not message.author.bot:
                for role in message.author.roles:
                    if role.name == 'Owner':
                        bot.loop.create_task(update_status(message))

@client.event
async def on_raw_reaction_add(payload):
    await client.wait_until_ready()
    channel = await client.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    user = await client.fetch_user(payload.user_id)
    member = payload.member
    reaction = payload.emoji

    if not user.bot and message.author.bot:
        for embed in message.embeds:
            try:
                role = embed.description.split(' | ')[0]
                emoji = embed.description.split(' | ')[1]
                if str(reaction) == emoji:
                    role2 = get(message.guild.roles, name=role)
                    await member.add_roles(role2)
            except IndexError:
                pass

async def update_status(message):
    global online
    global offline
    channel = message.channel
    await message.delete()
    status_message = None
    ping_message = None
    while True:
        online = 0
        offline = 0
        embed = discord.Embed(
            title="TSR Network Status",
            description=f"{EMOJI_OFFLINE}: Offline or Unknown\n{EMOJI_RUNNING}: Online\nLast updated: {datetime.utcnow()} (UTC)"
        )
        embed.add_field(
            name="Mindustry Servers",
            value="{hub} Hub\n{sandbox} Sandbox\n{survival} Survival\n{anarchy} Anarchy\n{sandbox_backup} Sandbox Backup".format(
                hub=EMOJI_RUNNING if ping_task(ips["hub"]) else EMOJI_OFFLINE,
                sandbox=EMOJI_RUNNING if ping_task(ips["sandbox"]) else EMOJI_OFFLINE,
                survival=EMOJI_RUNNING if ping_task(ips["survival"]) else EMOJI_OFFLINE,
                anarchy=EMOJI_RUNNING if ping_task(ips["anarchy"]) else EMOJI_OFFLINE,
                sandbox_backup=EMOJI_RUNNING if ping_task(ips["sandbox_backup"]) else EMOJI_OFFLINE,
            )
        )
        embed.add_field(
            name="Minecraft Servers",
            value="{smp} SMP\n{gt} GT".format(
                smp=EMOJI_RUNNING if ping_task(ips["smp"]) else EMOJI_OFFLINE,
                gt=EMOJI_RUNNING if ping_task(ips["gt"]) else EMOJI_OFFLINE,
            )
        )
        embed.add_field(
            name="Other",
            value="{website} TSR Website\n{smp_dynmap} SMP Dynmap".format(
                website=EMOJI_RUNNING if ping_task(ips["website"]) else EMOJI_OFFLINE,
                smp_dynmap=EMOJI_RUNNING if ping_task(ips["smp_dynmap"]) else EMOJI_OFFLINE,
            )
        )
        if status_message == None:
            status_message = await channel.send(embed=embed)
        else:
            await status_message.edit(embed=embed)
        if offline > 1:
            if ping_message != None:
                await ping_message.delete()
            ping_message = await channel.send("<@600352709106991106>")
        else:
            if ping_message != None:
                await ping_message.delete()
                ping_message = None
        await asyncio.sleep(10)

def ping(host):
    host = host.split(":")
    ip = host[0]
    if len(host) < 2:
        port = 443
    else:
        port = host[1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
        s.shutdown(2)
        return True
    except:
        return False

def ping_task(host):
    global offline
    global online
    host = host.split(":")
    ip = host[0]
    if len(host) < 2:
        port = 443
    else:
        port = host[1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
        s.shutdown(2)
        online += 1
        return True
    except:
        offline += 1
        return False


online = 0
offline = 0
client.run(TOKEN)