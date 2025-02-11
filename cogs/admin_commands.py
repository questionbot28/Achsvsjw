import discord
from discord.ext import commands
import logging
import asyncio
from typing import List, Optional

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord_bot')

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! Latency: {latency}ms")

    @commands.command(name='setupticket')
    @commands.has_permissions(administrator=True)
    async def setup_ticket(self, ctx, channel: discord.TextChannel = None):
        """Set up the ticket system in a channel"""
        channel = channel or ctx.channel
        embed = discord.Embed(
            title="Support Ticket System",
            description="Click the button below to create a support ticket!",
            color=discord.Color.blue()
        )

        class TicketButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.primary, label="Create Ticket", emoji="🎫")

            async def callback(self, interaction):
                # Create ticket channel
                guild = interaction.guild
                category = discord.utils.get(guild.categories, name='Tickets')

                if category is None:
                    category = await guild.create_category('Tickets')

                channel_name = f'ticket-{interaction.user.name.lower()}'

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }

                ticket_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)
                await interaction.response.send_message(f"Ticket created! Check {ticket_channel.mention}", ephemeral=True)

        view = discord.ui.View()
        view.add_item(TicketButton())
        await channel.send(embed=embed, view=view)

    @commands.command(name='staffhelp')
    @commands.has_permissions(administrator=True)
    async def staff_help(self, ctx):
        """Show staff commands help"""
        embed = discord.Embed(
            title="Staff Commands",
            description="Here are the available staff commands:",
            color=discord.Color.blurple()
        )

        # Member Management Commands
        member_commands = (
            "• **!mute** `<member> [reason]` - Temporarily restrict member's messaging ability\n"
            "• **!unmute** `<member>` - Restore member's messaging privileges\n"
            "• **!kick** `<member> [reason]` - Remove a member from the server\n"
            "• **!ban** `<member> [reason]` - Permanently ban a member\n"
            "• **!unban** `<user_id>` - Revoke a member's ban"
        )
        embed.add_field(
            name="Member Management",
            value=member_commands,
            inline=False
        )

        # Channel Control Commands
        channel_commands = (
            "• **!announce** `-r <role> <message>` - Make an announcement with role ping\n"
            "  Example: `!announce -r @everyone New update!`\n"
            "• **!clear** `<amount>` - Clear specified number of messages"
        )
        embed.add_field(
            name="Channel Controls",
            value=channel_commands,
            inline=False
        )

        # System Management Commands
        system_commands = (
            "• **!refresh** - Reload all bot extensions\n"
            "• **!ping** - Check bot's connection status"
        )
        embed.add_field(
            name="System Management",
            value=system_commands,
            inline=False
        )

        embed.set_footer(text="EduSphere Staff Panel • Made with ♥ by Rohanpreet singh Pathania")
        await ctx.send(embed=embed)

    @commands.command(name='refresh')
    @commands.has_permissions(administrator=True)
    async def refresh(self, ctx):
        """Refresh bot by reloading all extensions"""
        loading_msg = await ctx.send("🔄 Reloading all extensions...")

        try:
            extensions = [
                'cogs.education_manager_new',
                'cogs.admin_commands'
            ]

            for extension in extensions:
                await self.bot.reload_extension(extension)
                self.logger.info(f"Successfully reloaded extension: {extension}")

            await loading_msg.edit(content="✨ All extensions and commands are loaded and working! ✨")

        except Exception as e:
            self.logger.error(f"Error refreshing bot: {e}")
            await loading_msg.edit(content=f"❌ Error refreshing bot: {str(e)}")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))