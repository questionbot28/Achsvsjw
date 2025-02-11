import discord
from discord.ext import commands
import logging
import asyncio
import aiohttp
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import Dict, Optional
import os
from discord.ui import View, Select, Button
from discord import ButtonStyle

class SongSelectionView(discord.ui.View):
    def __init__(self, bot, ctx, songs):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.songs = songs
        self.bot = bot

        select = discord.ui.Select(placeholder="Choose a song...", min_values=1, max_values=1)

        for i, song in enumerate(songs[:5]):
            title = song["title"][:100]
            select.add_option(label=title, value=str(i))

        select.callback = self.song_selected
        self.add_item(select)

    async def song_selected(self, interaction: discord.Interaction):
        try:
            selected_index = int(interaction.data["values"][0])
            song = self.songs[selected_index]

            vc = self.ctx.voice_client
            if not vc or not vc.is_connected():
                vc = await self.ctx.author.voice.channel.connect()

            FFMPEG_OPTIONS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}
            vc.play(discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTIONS))

            await interaction.response.edit_message(content=f"🎶 Now playing: {song['title']}", view=None)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error playing song: {str(e)}", ephemeral=True)


class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord_bot')
        self.youtube_together_id = "880218394199220334"  # YouTube Together App ID

        # Configure yt-dlp options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'quiet': True,
            'no_warnings': True,
            'source_address': '0.0.0.0'
        }

    def get_youtube_video_url(self, query: str) -> Optional[str]:
        """Searches YouTube and returns the first video link."""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if "entries" in info and len(info["entries"]) > 0:
                    return info["entries"][0]["webpage_url"]
                return None
        except Exception as e:
            self.logger.error(f"Error searching YouTube video: {e}")
            return None

        # Configure Spotify client if credentials are available
        spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if spotify_client_id and spotify_client_secret:
            self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=spotify_client_id,
                client_secret=spotify_client_secret
            ))
        else:
            self.sp = None
            self.logger.warning("Spotify credentials not found. Spotify features will be disabled.")

        # YouTube DL options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'source_address': '0.0.0.0',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        # FFmpeg options
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        self.SongSelectionView = SongSelectionView

    def get_spotify_track(self, spotify_url: str) -> Optional[str]:
        """Extract track information from Spotify URL"""
        if not self.sp:
            return None

        try:
            track = self.sp.track(spotify_url)
            song_name = track["name"]
            artist_name = track["artists"][0]["name"]
            return f"{song_name} by {artist_name}"
        except Exception as e:
            self.logger.error(f"Error getting Spotify track: {e}")
            return None

    def get_youtube_results(self, query: str) -> Optional[list]:
        try:
            ydl_opts = {"format": "bestaudio"}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch10:{query}", download=False)  # Get top 10 results
                results = [
                    {"title": entry["title"], "url": entry["url"]}
                    for entry in info["entries"][:5]  # Show only top 5 results in dropdown
                ]
                return results
        except Exception as e:
            print(f"❌ Error searching YouTube: {e}")
            return None

    def get_youtube_audio(self, query: str) -> Optional[str]:
        """Search YouTube for audio URL"""
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'quiet': True,
                'no_warnings': True,
                'source_address': '0.0.0.0'
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if "entries" in info and len(info["entries"]) > 0:
                    return info["entries"][0]["url"]  # Return first search result
                return None  # No results found
        except Exception as e:
            self.logger.error(f"Error searching YouTube: {e}")
            return None

    @commands.command(name='join')
    async def join(self, ctx):
        """Join the user's voice channel"""
        if not ctx.author.voice:
            await ctx.send("❌ You must be in a voice channel!")
            return

        try:
            channel = ctx.author.voice.channel
            if ctx.voice_client:
                if ctx.voice_client.channel.id == channel.id:
                    await ctx.send("✅ Already in your voice channel!")
                    return
                await ctx.voice_client.move_to(channel)
            else:
                await channel.connect()
            await ctx.send(f"✅ Joined {channel.name}!")
            self.logger.info(f"Bot joined voice channel: {channel.name}")
        except Exception as e:
            self.logger.error(f"Error joining voice channel: {e}")
            await ctx.send("❌ An error occurred while joining the voice channel.")

    @commands.command(name='leave')
    async def leave(self, ctx):
        """Leave the current voice channel"""
        if not ctx.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return

        try:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Left the voice channel!")
            self.logger.info("Bot left voice channel")
        except Exception as e:
            self.logger.error(f"Error leaving voice channel: {e}")
            await ctx.send("❌ An error occurred while leaving the voice channel.")

    @commands.command(name='play')
    async def play(self, ctx, *, query: str):
        """Play audio from a song name, YouTube URL, or Spotify URL"""
        if not ctx.author.voice:
            await ctx.send("❌ You must be in a voice channel!")
            return

        async with ctx.typing():
            try:
                # Handle Spotify URLs
                if "spotify.com/track/" in query:
                    query = self.get_spotify_track(query)
                    if not query:
                        await ctx.send("❌ Invalid Spotify URL or song not found.")
                        return

                # Get YouTube results
                songs = await asyncio.get_event_loop().run_in_executor(None, self.get_youtube_results, query)
                if not songs:
                    await ctx.send(f"❌ No songs found matching '{query}'!")
                    return

                # Show song selection dropdown
                view = SongSelectionView(self.bot, ctx, songs)
                await ctx.send("🎵 Select a song to play:", view=view)
                self.logger.info(f"Showing song selection for: {query}")

            except Exception as e:
                self.logger.error(f"Error playing audio: {e}")
                await ctx.send("❌ An error occurred while trying to play the audio.")

        # Connect to voice if not already connected
        if not ctx.voice_client:
            try:
                await ctx.author.voice.channel.connect()
            except Exception as e:
                self.logger.error(f"Error connecting to voice: {e}")
                await ctx.send("❌ Could not join your voice channel!")
                return

        # Stop current playback if any
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

        async with ctx.typing():
            try:
                # Handle Spotify URLs
                if "spotify.com/track/" in query:
                    query = self.get_spotify_track(query)
                    if not query:
                        await ctx.send("❌ Invalid Spotify URL or song not found.")
                        return

                # Run yt-dlp in executor to avoid async issues
                loop = asyncio.get_event_loop()
                songs = await loop.run_in_executor(None, self.get_youtube_results, query)

                if not songs:
                    await ctx.send(f"❌ No songs found matching '{query}'!")
                    return

                # Show song selection dropdown
                view = SongSelectionView(self.bot, ctx, songs)
                await ctx.send("🎵 Select a song to play:", view=view)
                self.logger.info(f"Showing song selection for: {query}")

            except Exception as e:
                self.logger.error(f"Error playing audio: {e}")
                await ctx.send("❌ An error occurred while trying to play the audio.")

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Pause the currently playing audio"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Music paused.")
        else:
            await ctx.send("❌ No music is playing.")

    @commands.command(name='resume')
    async def resume(self, ctx):
        """Resume the paused audio"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Music resumed.")
        else:
            await ctx.send("❌ Music is not paused.")

    @commands.command(name='stop')
    async def stop(self, ctx):
        """Stop the currently playing audio"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏹️ Music stopped.")
        else:
            await ctx.send("❌ No music is playing.")

    @commands.command(name='vplay')
    async def vplay(self, ctx, *, query: str = None):
        """Start a YouTube Watch Party with the specified song"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ You must be in a voice channel!")
                return

            if not query:
                await ctx.send("❌ Please provide a song name!")
                return

            # Log permission check
            permissions = ctx.guild.me.guild_permissions
            required_perms = ['create_instant_invite', 'connect', 'speak']
            missing_perms = [perm for perm in required_perms if not getattr(permissions, perm)]

            if missing_perms:
                await ctx.send(f"❌ Missing required permissions: {', '.join(missing_perms)}")
                return

            # Send searching message
            status_msg = await ctx.send("🔍 Searching for your song...")

            video_url = self.get_youtube_video_url(query)
            if not video_url:
                await status_msg.edit(content=f"❌ No videos found for '{query}'!")
                return

            voice_channel_id = ctx.author.voice.channel.id

            async with aiohttp.ClientSession() as session:
                json_data = {
                    "max_age": 86400,
                    "max_uses": 0,
                    "target_application_id": self.youtube_together_id,
                    "target_type": 2,
                    "temporary": False,
                    "validate": None,
                }

                self.logger.info(f"Creating Watch Party for: {query}")
                await status_msg.edit(content="⚡ Creating Watch Party...")

                async with session.post(
                    f"https://discord.com/api/v9/channels/{voice_channel_id}/invites",
                    json=json_data,
                    headers={"Authorization": f"Bot {self.bot.http.token}", "Content-Type": "application/json"}
                ) as resp:
                    data = await resp.json()
                    self.logger.info(f"Watch Party created: {data}")

                    if resp.status != 200:
                        await status_msg.edit(content=f"❌ API Error: Status {resp.status}, Response: {data}")
                        return

                    if "code" not in data:
                        error_msg = data.get('message', 'Unknown error')
                        await status_msg.edit(content=f"❌ Failed to create Watch Party: {error_msg}")
                        return

                    invite_link = f"https://discord.com/invite/{data['code']}?video={video_url.split('v=')[-1]}"

                    embed = discord.Embed(
                        title="📽️ YouTube Watch Party Started!",
                        description=f"**Playing:** {query}",
                        color=0x00ff00
                    )
                    embed.add_field(
                        name="🎬 Join Watch Party",
                        value=f"[Click to Join]({invite_link})",
                        inline=False
                    )
                    embed.add_field(
                        name="🔊 Important: Enable Sound",
                        value="1. Join the Watch Party\n2. Click on the video\n3. Click the speaker icon (bottom-left) to unmute",
                        inline=False
                    )
                    embed.add_field(
                        name="▶️ Auto-Play Video",
                        value=f"[Click to Auto-Play](https://www.youtube.com/watch?v={video_url.split('v=')[-1]}&autoplay=1)",
                        inline=False
                    )
                    embed.set_footer(text="💡 Remember to unmute the video for sound!")

                    await status_msg.edit(content=None, embed=embed)
                    self.logger.info(f"Watch Party ready for: {query}")

        except Exception as e:
            self.logger.error(f"Error in vplay command: {e}")
            await ctx.send(f"❌ Error creating Watch Party: `{str(e)}`")

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))