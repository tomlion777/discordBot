import discord
import asyncio
import paramiko
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MAC_IP = os.getenv("MAC_IP")
SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
TMUX_SESSION = "mcserver"
SERVER_PATH = "/Users/nathan/1.21.5 Fabric MC Server"  # Adjust if needed

intents = discord.Intents.default()
intents.message_content = True
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
    print(f'✅ Bot is online as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!startmc'):
        await message.channel.send("🟢 Attempting to start Minecraft server...")

        tmux_cmd = (
            f'/opt/homebrew/bin/tmux new-session -d -s {TMUX_SESSION} '
            f'\'cd "{SERVER_PATH}" && exec java -Xmx8G -Xms8G -jar fabricserver.jar nogui\''
        )
        ssh_run(tmux_cmd)

        await asyncio.sleep(5)
        check = ssh_run(f'/opt/homebrew/bin/tmux has-session -t {TMUX_SESSION}')

        if "no server running" in check:
            await message.channel.send("❌ Failed to start Minecraft server — check server path or logs.")
        else:
            await message.channel.send("✅ Minecraft server started successfully!")

    elif message.content.startswith('!stopmc'):
        await message.channel.send("🛑 Sending stop command to Minecraft server...")

        stop_cmd = f'/opt/homebrew/bin/tmux send-keys -t {TMUX_SESSION} "stop" Enter'
        ssh_run(stop_cmd)

        await asyncio.sleep(5)
        check = ssh_run(f'/opt/homebrew/bin/tmux has-session -t {TMUX_SESSION}')

        if "no server running" in check:
            await message.channel.send("✅ Server stopped successfully.")
        else:
            await message.channel.send("⚠️ Stop command sent, but server is still running.")

    elif message.content.startswith('!mcstatus'):
        await message.channel.send("📄 Fetching Minecraft server console output...")
        output = ssh_run(f'/opt/homebrew/bin/tmux capture-pane -pt {TMUX_SESSION} -S -40')
        if output.strip():
            await message.channel.send(f"```\n{output[-1900:]}\n```")
        else:
            await message.channel.send("⚠️ No output or session not found.")

    elif message.content.startswith('!/'):
        mc_command = message.content[2:].strip()
        if not mc_command:
            await message.channel.send("❌ You didn't enter a command after `!/`.")
            return
        await message.channel.send(f"💬 Sending command: `{mc_command}`")
        send_cmd = f'/opt/homebrew/bin/tmux send-keys -t {TMUX_SESSION} "{mc_command}" Enter'
        ssh_run(send_cmd)
        await asyncio.sleep(1)
        output = ssh_run(f'/opt/homebrew/bin/tmux capture-pane -pt {TMUX_SESSION} -S -20')
        await message.channel.send(f"```\n{output[-1900:]}\n```")

# 🔁 Auto-shutdown monitor
inactivity_timer_running = False

async def monitor_inactivity():
    global inactivity_timer_running
    await client.wait_until_ready()
    channel = discord.utils.get(client.get_all_channels(), name="your-discord-channel-name")  # Replace this

    while not client.is_closed():
        session_check = ssh_run(f'/opt/homebrew/bin/tmux has-session -t {TMUX_SESSION}')
        if "no server running" in session_check:
            await asyncio.sleep(60)
            continue

        output = ssh_run(f'/opt/homebrew/bin/tmux capture-pane -pt {TMUX_SESSION} -S -1')
        last_line = output.strip().splitlines()[-1] if output.strip() else ""

        if "Server empty for 60 seconds." in last_line and not inactivity_timer_running:
            inactivity_timer_running = True
            print("🕐 Inactivity detected — starting 20-minute countdown...")
            if channel:
                await channel.send(
                    "⚠️ Server is empty. If it remains inactive for 20 minutes, it will shut down.\n"
                    "_(To avoid this, interact with the server or send a message in-game.)_"
                )

            for _ in range(40):  # 20 minutes = 40 × 30s
                await asyncio.sleep(30)
                recent = ssh_run(f'/opt/homebrew/bin/tmux capture-pane -pt {TMUX_SESSION} -S -1')
                latest_line = recent.strip().splitlines()[-1] if recent.strip() else ""
                if "Server empty for 60 seconds." not in latest_line:
                    inactivity_timer_running = False
                    print("✅ Activity resumed — shutdown canceled.")
                    if channel:
                        await channel.send("✅ Server activity resumed. Auto-shutdown canceled.")
                    break
            else:
                print("🛑 Inactivity timeout — shutting down server.")
                ssh_run(f'/opt/homebrew/bin/tmux send-keys -t {TMUX_SESSION} "stop" Enter')
                if channel:
                    await channel.send(
                        "🛑 Stopping server due to inactivity.\n"
                        "_(To avoid this, rejoin the server or interact before 20 minutes of being empty.)_"
                    )
                inactivity_timer_running = False

        await asyncio.sleep(30)

# Launch background monitor
client.loop.create_task(monitor_inactivity())

# Start the bot
client.run(TOKEN)
