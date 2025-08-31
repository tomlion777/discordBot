import discord
import asyncio
import paramiko
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Discord bot token
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# SSH configuration
MAC_IP = os.getenv("MAC_IP")               # e.g., 192.168.1.100
SSH_USER = os.getenv("SSH_USER")           # e.g., your macOS username
SSH_PASSWORD = os.getenv("SSH_PASSWORD")   # Plain password or use keychain
TMUX_SESSION = "mcserver"
SERVER_PATH = "/Users/nathan/1.21.5 Fabric MC Server"  # update this

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def ssh_run(command):
    client_ssh = paramiko.SSHClient()
    client_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client_ssh.connect(MAC_IP, username=SSH_USER, password=SSH_PASSWORD, timeout=10)
        stdin, stdout, stderr = client_ssh.exec_command(command)
        output = stdout.read().decode() + stderr.read().decode()
        client_ssh.close()
        return output
    except Exception as e:
        return f"SSH Error: {e}"

@client.event
async def on_ready():
    print(f'✅ Bot connected as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Start Minecraft server
    if message.content.startswith('!startmc'):
        await message.channel.send("🟢 Attempting to SSH into Mac mini and start server...")

        tmux_cmd = (
            f'tmux new-session -d -s {TMUX_SESSION} "cd {SERVER_PATH} && '
            f'exec java -Xmx8G -Xms8G -jar fabricserver.jar nogui"'
        )
        output = ssh_run(tmux_cmd)
        await message.channel.send("🚀 Server start attempted:\n" + f"```\n{output[-1900:]}\n```")

    # Stop Minecraft server
    elif message.content.startswith('!stopmc'):
        await message.channel.send("🛑 Sending stop command to Minecraft server...")
        stop_cmd = f'tmux send-keys -t {TMUX_SESSION} "stop" Enter'
        output = ssh_run(stop_cmd)
        await message.channel.send(f"✅ Stop command sent.\n```\n{output[-1900:]}\n```")

    # Check Minecraft server status
    elif message.content.startswith('!mcstatus'):
        await message.channel.send("📄 Fetching Minecraft server console output...")
        capture_cmd = f'tmux capture-pane -pt {TMUX_SESSION} -S -40'
        output = ssh_run(capture_cmd)
        if output.strip():
            await message.channel.send(f"```\n{output[-1900:]}\n```")
        else:
            await message.channel.send("⚠️ No output or session not found.")

    # Send command to Minecraft server
    elif message.content.startswith('!/'):
        mc_command = message.content[2:].strip()
        if not mc_command:
            await message.channel.send("❌ You didn't enter any command after `!/`.")
            return

        await message.channel.send(f"💬 Sending command to server: `{mc_command}`")

        send_cmd = f'tmux send-keys -t {TMUX_SESSION} "{mc_command}" Enter'
        ssh_run(send_cmd)

        # Optional: show feedback
        await asyncio.sleep(1)
        capture_cmd = f'tmux capture-pane -pt {TMUX_SESSION} -S -20'
        output = ssh_run(capture_cmd)
        await message.channel.send(f"📤 Command sent.\n```\n{output[-1900:]}\n```")

client.run(TOKEN)
