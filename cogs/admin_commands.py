import discord
from discord.ext import commands
import logging
import asyncio
from typing import List, Optional

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord_bot')

    @commands.command(name='refresh')
    @commands.has_permissions(administrator=True)
    async def refresh(self, ctx):
        """Refresh bot by reloading all extensions"""
        loading_msg = await ctx.send("🔄 Reloading all extensions...")

        try:
            extensions = [
                'cogs.education_manager_new',
                'cogs.subject_curriculum_new',
                'cogs.admin_commands'
            ]

            for extension in extensions:
                await self.bot.reload_extension(extension)
                self.logger.info(f"Successfully reloaded extension: {extension}")

            await loading_msg.edit(content="✨ Rohanpreet all extensions and commands are loaded and working! ✨")

        except Exception as e:
            self.logger.error(f"Error refreshing bot: {e}")
            await loading_msg.edit(content=f"❌ Error refreshing bot: {str(e)}")

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check bot's latency"""
        latency = round(self.bot.latency * 1000)
        ping_embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: {latency}ms",
            color=discord.Color.green() if latency < 200 else discord.Color.orange()
        )

        if latency < 100:
            status = "🟢 Excellent"
        elif latency < 200:
            status = "🟡 Good"
        else:
            status = "🔴 Poor"

        ping_embed.add_field(
            name="Connection Quality",
            value=status,
            inline=False
        )
        await ctx.send(embed=ping_embed)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))