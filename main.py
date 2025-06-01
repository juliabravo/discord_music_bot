import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
import yt_dlp

# token
load_dotenv()
token = os.getenv("DISCORD_BOT_TOKEN")

print(f"Token loaded? {'Yes' if token else 'No'}")

# intents
intents = discord.Intents.default()  # basic intents
intents.message_content = True
intents.voice_states = True

# da bot
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ping pong


@bot.command()
async def ping(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)
        await ctx.send(f"Pong! Joined {channel.name}! Use `!commands` for help!")
    else:
        await ctx.send("You must be in a voice channel.")


# music player for playlists
class MusicPlayer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.queue = asyncio.Queue()
        self.play_next_song = asyncio.Event()
        self.current = None
        self.bot = ctx.bot
        self.audio_player_task = self.bot.loop.create_task(
            self.audio_player_loop()
        )

    async def audio_player_loop(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.queue.get()
            self.ctx.voice_client.play(
                self.current['source'],
                after=lambda e: self.bot.loop.call_soon_threadsafe(
                    self.play_next_song.set)
            )
            await self.ctx.send(f"Now playing: {self.current['title']}")
            await self.play_next_song.wait()


async def queue_song(self, url):
    if "soundcloud.com" not in url.lower():
        await self.ctx.send("Only SoundCloud links are allowed.")
        return

    ytdlp_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'ignoreerrors': True,  # skip videos with errors
        'no_warnings': True,   # suppress warning output
        'default_search': 'auto',  # auto supports YouTube + SoundCloud
        'extract_flat': False
    }

    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    def get_best_audio_url(entry):
        # Try to pick best audio-only format
        formats = entry.get('formats', [])
        for f in reversed(formats):  # reverse to prioritize better formats
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                return f.get('url')
        return entry.get('url')  # fallback if needed

    with yt_dlp.YoutubeDL(ytdlp_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            await self.ctx.send(f"Error loading audio: {e}")
            return

        # determine if playlist or single track
        entries = info.get('entries') or [info]

        added_count = 0
        for entry in entries:
            if entry is None:
                continue
            try:
                # skip private/unavailable tracks
                if entry.get('is_private') or entry.get('availability') == 'private':
                    continue

                # get best audio stream
                audio_url = get_best_audio_url(entry)
                if not audio_url:
                    continue

                title = entry.get('title', 'Unknown')
                source = await discord.FFmpegOpusAudio.from_probe(audio_url, **ffmpeg_opts)

                # add to queue
                await self.queue.put({'source': source, 'title': title})
                added_count += 1

            except Exception as e:
                print(f"Skipped track due to error: {e}")
                continue

        if added_count == 0:
            await self.ctx.send("No playable songs found.")
        else:
            await self.ctx.send(f"{added_count} song(s) added to queue.")

    def get_queue(self):
        return list(self.queue._queue)


music_players = {}

# commands


@bot.command()
async def play(ctx, url):
    if ctx.author.voice is None:
        await ctx.send("Enter a voice channel to play music.")
        return

    if "soundcloud.com" not in url.lower():
        await ctx.send("Only SoundCloud links are supported")
        return

    voice_channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    if ctx.guild.id not in music_players:
        music_players[ctx.guild.id] = MusicPlayer(ctx)

    player = music_players[ctx.guild.id]
    await player.queue_song(url)


@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped current track.")
    else:
        await ctx.send("There's no song playing.")


@bot.command()
async def queue(ctx):
    player = music_players.get(ctx.guild.id)
    if not player:
        await ctx.send("Nothing is in the queue")
        return

    queue_list = player.get_queue()
    if not queue_list:
        await ctx.send("Queue is empty ")
    else:
        queue_text = "\n".join(
            [f"{idx+1}. {song['title']}" for idx, song in enumerate(queue_list)])
        await ctx.send(f"**Current Queue:**\n{queue_text}")


@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused.")
    else:
        await ctx.send("Nothing is playing.")


@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed.")
    else:
        await ctx.send("Nothing is paused.")


@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        music_players.pop(ctx.guild.id, None)
        await ctx.send("Stopped and left the voice channel.")
    else:
        await ctx.send("Not connected to a voice channel.")


@bot.command(name="commands")
async def show_commands(ctx):
    commands_list = """
 ****Music Bot Commands**** 

`!ping` — Join your voice channel.
`!play <SoundCloud URL>` — Play a song or playlist from SoundCloud.
`!skip` — Skip the currently playing song.
`!pause` — Pause the current song.
`!resume` — Resume a paused song.
`!queue` — Show the list of queued songs.
`!stop` — Stop the music and leave the voice channel.
`!commands` — Show this help message.
    """
    await ctx.send(commands_list)

# run bot
bot.run(token)
