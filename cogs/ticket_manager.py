
import discord
from discord.ext import commands
import asyncio
from discord import ButtonStyle, SelectOption
from discord.ui import Button, View

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            SelectOption(label="Support Ticket", description="Get help with any issues", emoji="🎫", value="support"),
            SelectOption(label="Claim Reward", description="Claim your rewards and prizes", emoji="🎁", value="reward")
        ]
        super().__init__(placeholder="Choose ticket type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, TicketView):
            await view.create_ticket_callback(interaction, self.values[0])

class TicketView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(TicketSelect())
    
    async def create_ticket_callback(self, interaction: discord.Interaction, ticket_type: str):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user already has a ticket
        cog = self.bot.get_cog('TicketManager')
        if interaction.user.id in cog.active_tickets:
            await interaction.followup.send("❌ You already have an active ticket!", ephemeral=True)
            return
            
        # Create ticket channel
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name='Tickets')
        
        if category is None:
            category = await guild.create_category('Tickets')
            
        channel_name = f'ticket-{interaction.user.name}'
        
        # Set permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Create the ticket channel
        ticket_channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites
        )
        
        cog.active_tickets[interaction.user.id] = ticket_channel.id
        
        # Create embed for the ticket channel
        embed = discord.Embed(
            title=f"{'🎫 Support Request Channel' if ticket_type == 'support' else '🎁 Reward Claim Channel'}",
            description=f"```ansi\n[1;36m┏━━━━━ Welcome Message ━━━━━┓[0m\n[1;33m👋 Hello {interaction.user.name}![0m\n[0;37mYour ticket has been created![0m\n[1;36m┗━━━━━━━━━━━━━━━━━━━━━━━━┛[0m\n```\n⌛ **Please wait while our team assists you**\n💬 Meanwhile, feel free to describe your request in detail.",
            color=discord.Color.brand_green() if ticket_type == 'support' else discord.Color.gold()
        )
        
        # User Information with fancy formatting
        user_info = (
            "```ansi\n"
            "[1;35m┏━━━━━ Ticket Info ━━━━━┓[0m\n"
            f"[0;36m▸ User:[0m {interaction.user.name}\n"
            f"[0;36m▸ ID:[0m {interaction.user.id}\n"
            f"[0;36m▸ Type:[0m {'Support' if ticket_type == 'support' else 'Reward'}\n"
            f"[0;36m▸ Status:[0m [1;32mActive[0m\n"
            "[1;35m┗━━━━━━━━━━━━━━━━━━━━━┛[0m\n"
            "```"
        )
        embed.add_field(name="", value=user_info, inline=False)
        
        # Instructions
        instructions = (
            "```ansi\n"
            "[1;33m┏━━━━━ Instructions ━━━━━┓[0m\n"
            "1️⃣ Describe your request clearly\n"
            "2️⃣ Wait for staff response\n"
            "3️⃣ Use 🔒 button when done\n"
            "[1;33m┗━━━━━━━━━━━━━━━━━━━━━━┛[0m\n"
            "```"
        )
        embed.add_field(name="", value=instructions, inline=False)
        embed.set_footer(text="🔔 A staff member will be with you shortly!")

        class CloseButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.danger, label="Close Ticket", emoji="🔒")

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer()
                cog = interaction.client.get_cog('TicketManager')
                ctx = await interaction.client.get_context(interaction.message)
                await cog.close_ticket(ctx)

        view = discord.ui.View(timeout=None)
        view.add_item(CloseButton())
        
        await ticket_channel.send(f"{interaction.user.mention}", embed=embed, view=view)
        await interaction.followup.send(f"✅ Ticket created! Please check {ticket_channel.mention}", ephemeral=True)

class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tickets = {}
        self.ticket_channel_id = None

    @commands.command(name='setuptickets')
    @commands.has_permissions(administrator=True)
    async def setup_tickets(self, ctx, channel: discord.TextChannel = None):
        """Set up the ticket system in a specific channel"""
        channel = channel or ctx.guild.get_channel(1338330187632476291)
        if not channel:
            await ctx.send("❌ Channel not found!")
            return
            
        self.ticket_channel_id = channel.id
        
        # Create the ticket message
        embed = discord.Embed(
            title="🎫 Support & Rewards Center",
            description="```ansi\n[1;35m┏━━━━━ Welcome to Ticket System ━━━━━┓[0m\n[0;36mSelect your ticket type from the menu below![0m\n[1;35m┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛[0m\n```",
            color=discord.Color.blue()
        )
        ticket_types = (
            "```ansi\n"
            "[1;33m┏━━━━━ Available Options ━━━━━┓[0m\n"
            "[1;34m🎫 Support Ticket[0m\n"
            "  • Technical assistance\n"
            "  • General inquiries\n"
            "  • Issue reporting\n\n"
            "[1;32m🎁 Reward Claims[0m\n"
            "  • Claim prizes\n"
            "  • Redeem rewards\n"
            "  • Special requests\n"
            "[1;33m┗━━━━━━━━━━━━━━━━━━━━━━━━━┛[0m\n"
            "```"
        )
        embed.add_field(
            name="",
            value=ticket_types,
            inline=False
        )
        embed.add_field(
            name="💡 How it works",
            value="1️⃣ Click the appropriate button below\n"
                  "2️⃣ A private channel will be created\n"
                  "3️⃣ Describe your request there\n"
                  "4️⃣ Staff will assist you shortly",
            inline=False
        )
        embed.set_footer(text="Choose your ticket type below!")
        
        # Send message with button
        view = TicketView(self.bot)
        await channel.send(embed=embed, view=view)

    @commands.command(name='close')
    async def close_ticket(self, ctx):
        """Close a support ticket"""
        if not isinstance(ctx.channel, discord.TextChannel) or 'ticket-' not in ctx.channel.name:
            await ctx.send("❌ This command can only be used in ticket channels!")
            return

        close_embed = discord.Embed(
            title="🔒 Closing Ticket",
            description="This ticket will be closed in 5 seconds...",
            color=discord.Color.orange()
        )
        await ctx.send(embed=close_embed)
        await asyncio.sleep(5)
        
        # Remove from active tickets
        user_id = next((k for k, v in self.active_tickets.items() if v == ctx.channel.id), None)
        if user_id:
            del self.active_tickets[user_id]

        await ctx.channel.delete()

async def setup(bot):
    await bot.add_cog(TicketManager(bot))
