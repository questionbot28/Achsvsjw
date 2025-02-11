import discord
from discord.ext import commands
from discord import PCMVolumeTransformer
import logging
import asyncio
import aiohttp
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import Dict, Optional, Any
import os
from discord.ui import View, Select, Button
from discord import ButtonStyle
import random
from discord.ext.commands import cooldown, BucketType
from datetime import datetime, timedelta
import time

class SongSelectionView(discord.ui.View):
    def __init__(self, bot, ctx, songs, effect=None):
        super().__init__(timeout=15)  # Reduced timeout
        self.ctx = ctx
        self.songs = songs
        self.bot = bot
        self.effect = effect
        self.message = None  # Store message reference

        select = discord.ui.Select(placeholder="Choose a song...", min_values=1, max_values=1)

        for i, song in enumerate(songs[:5]):  # Only show top 5 results
            title = song["title"][:100]
            select.add_option(label=title, value=str(i))

        select.callback = self.song_selected
        self.add_item(select)

    async def song_selected(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()  # Acknowledge interaction immediately
            bot_cog = self.bot.get_cog('MusicCommands')
            if not bot_cog:
                await interaction.followup.send("❌ Bot configuration error!", ephemeral=True)
                return

            selected_index = int(interaction.data["values"][0])
            song = self.songs[selected_index]

            vc = self.ctx.voice_client
            if not vc or not vc.is_connected():
                try:
                    vc = await self.ctx.author.voice.channel.connect()
                except discord.errors.HTTPException as e:
                    if e.status == 429:
                        await bot_cog.handle_rate_limit(e, interaction) #call new function
                        return
                    raise

            # Apply audio effects if specified
            FFMPEG_OPTIONS = {
                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 100M -analyzeduration 100M",
                "options": "-vn -b:a 256k -af volume=3.5,highpass=f=120,acompressor=threshold=-20dB:ratio=3:attack=0.2:release=0.3"
            }

            # Add effect filters if specified
            filters = {
                "bassboost": "bass=g=1.5,volume=3.5,highpass=f=100,acompressor=threshold=-20dB:ratio=3:attack=0.2:release=0.3",
                "nightcore": "asetrate=44100*1.25,atempo=1.25,volume=3.5,highpass=f=120,acompressor=threshold=-20dB:ratio=3:attack=0.2:release=0.3",
                "reverb": "aecho=0.8:0.9:1000:0.3,volume=3.5,highpass=f=120,acompressor=threshold=-20dB:ratio=3:attack=0.2:release=0.3",
                "8d": "apulsator=hz=0.09,volume=3.5,highpass=f=120,acompressor=threshold=-20dB:ratio=3:attack=0.2:release=0.3"
            }

            if self.effect and self.effect in filters:
                FFMPEG_OPTIONS["options"] = f"-vn -b:a 256k -af {filters[self.effect]}"

            try:
                # Create audio source with volume transformer
                source = PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTIONS),
                    volume=bot_cog.current_volume
                )

                if vc.is_playing():
                    vc.stop()  # Stop current song if playing

                vc.play(source, after=lambda e: print(f"Finished playing: {e}" if e else "Song finished successfully"))
                self.ctx.voice_client.current_song_url = song["url"]  # update current song url

            except Exception as e:
                await interaction.followup.send(f"❌ Error playing audio: {str(e)}", ephemeral=True)
                return

            # Create a visual volume bar
            volume_percentage = int(bot_cog.current_volume * 100)
            volume_bar = "▮" * (volume_percentage // 10) + "▯" * ((100 - volume_percentage) // 10)

            effect_msg = f" with {self.effect} effect" if self.effect else ""
            status_msg = f"🎶 Now playing: **{song['title']}**{effect_msg}\n"
            status_msg += f"Volume: {volume_percentage}% `{volume_bar}`"

            try:
                await interaction.followup.send(status_msg)
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    await bot_cog.handle_rate_limit(e, interaction)
                else:
                    raise

        except Exception as e:
            await interaction.followup.send(f"❌ Error playing song: {str(e)}", ephemeral=True)

class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord_bot')
        self.youtube_together_id = "880218394199220334"
        self.current_volume = 1.0  # Default volume (100%)
        self.current_song_url = None  # Store current song URL
        self.retry_count = 0  # Initialize retry counter

        # Rate limit tracking
        self.rate_limit_start = None
        self.rate_limit_resets: Dict[str, datetime] = {}
        self.command_timestamps = {}
        self.max_retries = 5

        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'quiet': True,
            'no_warnings': True,
            'source_address': '0.0.0.0',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '128'
            }]
        }

        # Configure Spotify if credentials exist
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

    async def get_youtube_results(self, query: str) -> Optional[list]:
        """Search YouTube and return multiple results faster."""
        def search():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                    if not info or 'entries' not in info:
                        return None
                    return [
                        {"title": entry["title"], "url": entry["url"]}
                        for entry in info["entries"][:5]
                    ]
            except Exception as e:
                self.logger.error(f"Error searching YouTube: {e}")
                return None

        return await asyncio.get_event_loop().run_in_executor(None, search)

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


    @commands.command(name='play')
    @commands.cooldown(1, 5, BucketType.user)  # 1 command per 5 seconds per user
    async def play(self, ctx, *, query: str):
        """Play audio from a song name with optional effects"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ You must be in a voice channel!")
                return

            # Extract effect from query (last word)
            args = query.split()
            effect = args[-1].lower() if len(args) > 1 else None
            if effect not in ["bassboost", "nightcore", "reverb", "8d"]:
                effect = None
                song_query = query
            else:
                song_query = " ".join(args[:-1])

            # Create initial embed
            embed = discord.Embed(
                title="🎵 Searching for Song...",
                description=f"🔍 Finding **{song_query}** on YouTube...",
                color=discord.Color.blue()
            )
            status_msg = await ctx.send(embed=embed)
            self.logger.info(f"Searching for song: {song_query}")

            try:
                # Handle Spotify URLs
                if "spotify.com/track/" in song_query and self.sp:
                    song_query = self.get_spotify_track(song_query)
                    if not song_query:
                        embed.title = "❌ Invalid Spotify URL!"
                        embed.description = "Could not find the specified track."
                        embed.color = discord.Color.red()
                        await status_msg.edit(embed=embed)
                        return

                # Get YouTube results asynchronously
                songs = await self.get_youtube_results(song_query)
                if not songs:
                    embed.title = "❌ No Songs Found!"
                    embed.description = f"Could not find any songs matching '{song_query}'"
                    embed.color = discord.Color.red()
                    await status_msg.edit(embed=embed)
                    return

                # Show song selection dropdown with effect
                view = SongSelectionView(self.bot, ctx, songs, effect)
                effect_msg = f" with {effect} effect" if effect else ""
                embed.title = "🎵 Select a Song"
                embed.description = f"Choose a song to play{effect_msg}:"
                embed.color = discord.Color.green()
                await status_msg.edit(embed=embed, view=view)
                self.logger.info(f"Song options presented to user for query: {song_query}")

            except discord.errors.HTTPException as e:
                if e.status == 429:  # Rate limit error
                    await self.handle_rate_limit(e, status_msg, endpoint="play") #call new function
                else:
                    self.logger.error(f"HTTP error in play command: {e}")
                    embed.title = "❌ Discord API Error"
                    embed.description = "Please try again in a few moments."
                    embed.color = discord.Color.red()
                    await status_msg.edit(embed=embed)
            except Exception as e:
                self.logger.error(f"Error in play command: {e}")
                embed.title = "❌ Error Occurred"
                embed.description = f"An error occurred while searching: {str(e)}"
                embed.color = discord.Color.red()
                await status_msg.edit(embed=embed)

        except commands.CommandOnCooldown as e:
            await ctx.send(f"⏳ Please wait {e.retry_after:.1f}s before using this command again.")
            return
        except Exception as e:
            self.logger.error(f"Error in play command: {e}")
            await ctx.send(f"❌ An error occurred: {str(e)}")

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

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Pause the currently playing audio"""
        if not ctx.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.send("❌ No music is currently playing!")
            return

        if ctx.voice_client.is_paused():
            await ctx.send("❌ Music is already paused! Use `!resume` to continue playing.")
            return

        ctx.voice_client.pause()
        embed = discord.Embed(
            title="⏸️ Music Paused",
            description="Use `!resume` to continue playing.",
            color=discord.Color.yellow()
        )
        await ctx.send(embed=embed)

    @commands.command(name='resume')
    async def resume(self, ctx):
        """Resume the paused audio"""
        if not ctx.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return

        if not ctx.voice_client.is_paused():
            if ctx.voice_client.is_playing():
                await ctx.send("❌ Music is already playing!")
            else:
                await ctx.send("❌ No music is currently paused!")
            return

        ctx.voice_client.resume()
        embed = discord.Embed(
            title="▶️ Music Resumed",
            description="Enjoy your music!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='stop')
    async def stop(self, ctx):
        """Stop the currently playing audio"""
        if not ctx.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.send("❌ No music is currently playing!")
            return

        try:
            # Stop the audio first
            ctx.voice_client.stop()
            # Reset the current song URL
            self.current_song_url = None
            # Reset volume to default
            self.current_volume = 1.0

            embed = discord.Embed(
                title="⏹️ Music Stopped",
                description="All playback has been stopped and settings reset.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Error stopping music: {e}")
            await ctx.send("❌ An error occurred while stopping the music.")

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

    @commands.command(name='function')
    async def function(self, ctx):
        """Display all music features and commands"""
        embed = discord.Embed(
            title="🎵 EduSphere Bot Music Features",
            description="Here are all the advanced commands your bot supports:",
            color=discord.Color.blue()
        )

        embed.add_field(name="🎶 Basic Commands", value="""
        `!play <song>` - Play a song from YouTube  
        `!pause` - Pause the current song  
        `!resume` - Resume the paused song  
        `!stop` - Stop playing music  
        `!leave` - Disconnect the bot from the voice channel  
        """, inline=False)

        embed.add_field(name="🔥 Advanced Music Effects", value="""
        `!play <song> bassboost` - Play song with **Bass Boost**  
        `!play <song> nightcore` - Play song with **Nightcore Effect**  
        `!play <song> reverb` - Play song with **Slow + Reverb Effect**  
        `!play <song> 8d` - Play song with **8D Surround Sound**  
        """, inline=False)

        embed.add_field(name="🎬 YouTube Watch Party", value="""
        `!vplay <song>` - Start a **YouTube Watch Party** and load the song automatically  
        """, inline=False)

        embed.add_field(name="🔧 Utility Commands", value="""
        `!join` - Make the bot join your voice channel  
        `!function` - Show all available bot commands
        `!volume <0-100>` - Set volume level
        `!seek forward/back` - Skip 10 seconds forward or backward
        """, inline=False)

        embed.set_footer(text="🎵 EduSphere Bot - Your Ultimate Music Experience 🚀")

        await ctx.send(embed=embed)

    @commands.command(name='volume')
    @commands.cooldown(1, 2, BucketType.user)  # 1 command per 2 seconds per user
    async def volume(self, ctx, level: int):
        """Change the volume of the currently playing audio (0-100)"""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ The bot is not connected to a voice channel!")
                return

            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await ctx.send("❌ No music is currently playing or paused!")
                return

            if level < 0 or level > 100:
                await ctx.send("❌ Please set volume between `0` and `100`!")
                return

            self.current_volume = level / 100  # Convert 0-100 scale to FFmpeg volume

            # Update volume of currently playing audio
            if isinstance(ctx.voice_client.source, PCMVolumeTransformer):
                ctx.voice_client.source.volume = self.current_volume
                # Create a visual representation of the volume level
                volume_bar = "▮" * (level // 10) + "▯" * ((100 - level) // 10)
                embed = discord.Embed(
                    title="🔊 Volume Adjusted",
                    description=f"**Volume:** `{level}%`\n`{volume_bar}`",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Cannot adjust volume - incompatible audio source!")

        except commands.CommandOnCooldown as e:
            await ctx.send(f"⏳ Please wait {e.retry_after:.1f}s before adjusting volume again.")
            return
        except Exception as e:
            self.logger.error(f"Error adjusting volume: {e}")
            await ctx.send(f"❌ An error occurred while adjusting volume: {str(e)}")


    @commands.command(name='seek')
    async def seek(self, ctx, direction: str):
        """Seek forward or backward in the current song"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("❌ The bot is not playing any music!")
            return

        if direction not in ["forward", "back"]:
            await ctx.send("❌ Use `!seek forward` or `!seek back`!")
            return

        if not self.current_song_url:
            await ctx.send("❌ No song is currently loaded!")
            return

        time_offset = 10 if direction == "forward" else -10
        vc = ctx.voice_client

        # Create animated embed for seeking
        embed = discord.Embed(
            title="⏭️ Seeking Song...",
            description=f"**{'Skipping forward' if direction == 'forward' else 'Rewinding'} by 10 seconds**",
            color=discord.Color.purple()
        )
        status_msg = await ctx.send(embed=embed)

        try:
            # Create new audio source with seek offset
            FFMPEG_OPTIONS = {
                "before_options": f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 100M -analyzeduration 100M -ss {abs(time_offset)}",
                "options": "-vn -b:a 256k -af volume=3.5,highpass=f=120,acompressor=threshold=-20dB:ratio=3:attack=0.2:release=0.3"
            }

            source = PCMVolumeTransformer(
                discord.FFmpegPCMAudio(self.current_song_url, **FFMPEG_OPTIONS),
                volume=self.current_volume
            )

            vc.stop()
            vc.play(source)

            # Update embed with success message
            embed.title = "✅ Seek Successful!"
            embed.description = f"{'⏩ Skipped' if direction == 'forward' else '⏪ Rewound'} **10 seconds** {'forward' if direction == 'forward' else 'backward'}"
            embed.color = discord.Color.green()
            await status_msg.edit(embed=embed)
        except Exception as e:
            self.logger.error(f"Error seeking: {e}")
            embed.title = "❌ Seek Failed"
            embed.description = f"An error occurred while seeking: {str(e)}"
            embed.color = discord.Color.red()
            await status_msg.edit(embed=embed)

    def _update_rate_limit(self, endpoint: str, reset_after: float):
        """Update rate limit tracking for an endpoint"""
        reset_time = datetime.now() + timedelta(seconds=reset_after)
        self.rate_limit_resets[endpoint] = reset_time
        if not self.rate_limit_start:
            self.rate_limit_start = datetime.now()

    def _should_retry(self, endpoint: str) -> bool:
        """Check if we should retry a rate-limited request"""
        if self.retry_count >= self.max_retries:
            return False

        if endpoint in self.rate_limit_resets:
            if datetime.now() >= self.rate_limit_resets[endpoint]:
                del self.rate_limit_resets[endpoint]
                return True
        return len(self.rate_limit_resets) == 0

    @property
    def retry_delay(self) -> float:
        """Calculate retry delay with improved exponential backoff"""
        base_delay = 1.5
        max_delay = 60
        jitter = random.uniform(0, 0.5)  # Increased jitter for better distribution

        # Add progressive backoff based on global rate limit state
        if self.rate_limit_start:
            time_in_limit = (datetime.now() - self.rate_limit_start).total_seconds()
            additional_delay = min(time_in_limit / 10, 30)  # Cap at 30 seconds
        else:
            additional_delay = 0

        delay = min(base_delay * (2 ** self.retry_count) + additional_delay, max_delay) + jitter
        return delay

    async def handle_rate_limit(self, e, interaction=None, endpoint: str = "global"):
        """Enhanced rate limit handler with better tracking and user feedback"""
        try:
            # Extract rate limit information
            retry_after = getattr(e, 'retry_after', self.retry_delay)
            self._update_rate_limit(endpoint, retry_after)

            # Prepare user-friendly message
            if self.retry_count >= self.max_retries:
                message = "⚠️ Too many retries. Please try again in a few minutes."
                self.logger.warning(f"Rate limit max retries reached for {endpoint}")
                self.retry_count = 0  # Reset counter
                self.rate_limit_start = None
                return False

            delay = self.retry_delay
            warning_msg = (
                f"🕒 Rate limited! Retrying in {delay:.1f}s...\n"
                f"Retry {self.retry_count + 1}/{self.max_retries}"
            )

            # Log the rate limit
            self.logger.warning(
                f"Rate limit hit: endpoint={endpoint}, "
                f"retry={self.retry_count + 1}/{self.max_retries}, "
                f"delay={delay:.1f}s"
            )

            # Send feedback to user
            if interaction:
                try:
                    if isinstance(interaction, discord.Interaction):
                        if not interaction.response.is_done():
                            await interaction.response.defer(ephemeral=True)
                        await interaction.followup.send(warning_msg, ephemeral=True)
                    else:
                        # Assume it's a Context or Message
                        await interaction.edit(content=warning_msg)
                except discord.errors.HTTPException:
                    # If we can't send/edit message, log and continue
                    self.logger.warning("Could not send rate limit message to user")
                    pass

            # Wait with backoff
            await asyncio.sleep(delay)
            self.retry_count += 1

            # Check if we should continue retrying
            return self._should_retry(endpoint)

        except Exception as e:
            self.logger.error(f"Error in rate limit handler: {e}")
            return False

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))