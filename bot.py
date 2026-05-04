import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput, Select
import json
import os
import asyncio
from datetime import datetime, timedelta
import random

# ============================================================
# CONFIGURATION - Edit these to match your server
# ============================================================
TOKEN = "YOUR_BOT_TOKEN_HERE"  # Paste your bot token here

# Channel IDs (right-click channel > Copy ID)
WELCOME_CHANNEL_ID = 0        # #welcome
APPLY_CHANNEL_ID = 0          # #apply-here
APPLICATIONS_CHANNEL_ID = 0   # #applications (staff only)
LOGS_CHANNEL_ID = 0           # #logs
RULES_CHANNEL_ID = 0          # #rules
GENERAL_CHANNEL_ID = 0        # #general
ANNOUNCEMENTS_CHANNEL_ID = 0  # #announcements

# Role IDs (right-click role > Copy ID)
MEMBER_ROLE_ID = 0            # Given after rules accepted
BUILDER_ROLE_ID = 0
SCRIPTER_ROLE_ID = 0
MODELLER_ROLE_ID = 0
UI_DESIGNER_ROLE_ID = 0
STAFF_ROLE_ID = 0
OWNER_ROLE_ID = 0
VERIFIED_ROLE_ID = 0          # Given after Roblox verification
MUTED_ROLE_ID = 0

# ============================================================
# BOT SETUP
# ============================================================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

applications_data = {}  # Stores pending applications
warnings_data = {}      # Stores user warnings
notes_data = {}         # Stores staff notes on users
suggestions_data = {}   # Stores suggestions

# ============================================================
# APPLICATION MODAL (The form new members fill out)
# ============================================================
class ApplicationModal(Modal, title="🎮 Young Boy Studios — Apply"):
    roblox_name = TextInput(
        label="Your Roblox Username",
        placeholder="e.g. CoolBuilder123",
        required=True,
        max_length=50
    )
    real_name = TextInput(
        label="What should we call you?",
        placeholder="First name or nickname is fine",
        required=True,
        max_length=30
    )
    age = TextInput(
        label="Your Age",
        placeholder="e.g. 16",
        required=True,
        max_length=3
    )
    role = TextInput(
        label="What role are you applying for?",
        placeholder="Builder / Scripter / Modeller / UI Designer",
        required=True,
        max_length=50
    )
    experience = TextInput(
        label="Tell us about your experience & skills",
        placeholder="How long have you been developing? What are you best at?",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Store partial application
        applications_data[interaction.user.id] = {
            "roblox_name": self.roblox_name.value,
            "real_name": self.real_name.value,
            "age": self.age.value,
            "role": self.role.value,
            "experience": self.experience.value,
            "user": interaction.user,
            "timestamp": datetime.now().isoformat()
        }
        await interaction.response.send_message(
            "✅ **Step 1 done!** Now please send:\n"
            "1. 📁 **Your portfolio** (images, links, videos of your work)\n"
            "2. 💬 **Why you want to join Young Boy Studios**\n\n"
            "Just type/paste them in this channel!",
            ephemeral=True
        )

class ApplicationModal2(Modal, title="📋 Almost done!"):
    why_join = TextInput(
        label="Why do you want to join Young Boy Studios?",
        placeholder="What motivates you? What can you bring to the team?",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    availability = TextInput(
        label="How many hours per week can you commit?",
        placeholder="e.g. 10 hours/week, weekends only, etc.",
        required=True,
        max_length=100
    )
    portfolio = TextInput(
        label="Portfolio links (put N/A if none yet)",
        placeholder="https://... or describe your work",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    extra = TextInput(
        label="Anything else you want us to know?",
        placeholder="Extra skills, goals, questions...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id not in applications_data:
            await interaction.response.send_message("❌ Please start with the first form first!", ephemeral=True)
            return

        app = applications_data[interaction.user.id]
        app["why_join"] = self.why_join.value
        app["availability"] = self.availability.value
        app["portfolio"] = self.portfolio.value
        app["extra"] = self.extra.value

        # Send to staff applications channel
        channel = bot.get_channel(APPLICATIONS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"📋 New Application — {app['real_name']}",
                color=0x5865F2,
                timestamp=datetime.now()
            )
            embed.set_author(name=str(app['user']), icon_url=app['user'].display_avatar.url)
            embed.add_field(name="🎮 Roblox Username", value=app['roblox_name'], inline=True)
            embed.add_field(name="👤 Name", value=app['real_name'], inline=True)
            embed.add_field(name="🎂 Age", value=app['age'], inline=True)
            embed.add_field(name="🔨 Applying For", value=app['role'], inline=True)
            embed.add_field(name="⏰ Availability", value=app['availability'], inline=True)
            embed.add_field(name="⚙️ Experience", value=app['experience'], inline=False)
            embed.add_field(name="💡 Why Join", value=app['why_join'], inline=False)
            embed.add_field(name="📁 Portfolio", value=app['portfolio'], inline=False)
            if app.get('extra'):
                embed.add_field(name="➕ Extra Info", value=app['extra'], inline=False)
            embed.set_footer(text=f"User ID: {app['user'].id}")

            view = ApplicationReviewView(app['user'].id)
            await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            "🎉 **Application submitted!** Our team will review it and get back to you soon. Good luck!",
            ephemeral=True
        )

# ============================================================
# APPLICATION REVIEW BUTTONS (for staff)
# ============================================================
class ApplicationReviewView(View):
    def __init__(self, applicant_id):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Staff only!", ephemeral=True)
            return
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        if member:
            role = guild.get_role(MEMBER_ROLE_ID)
            if role:
                await member.add_roles(role)
            await member.send(
                "🎉 **Congratulations!** Your application to **Young Boy Studios** has been **accepted!**\n"
                "Welcome to the team! Head to the server to get started."
            )
        await interaction.message.edit(content=f"✅ Accepted by {interaction.user.mention}", view=None)
        await interaction.response.send_message("✅ Application accepted!", ephemeral=True)

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: Button):
        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Staff only!", ephemeral=True)
            return
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        if member:
            await member.send(
                "😔 Unfortunately your application to **Young Boy Studios** was **not accepted** this time.\n"
                "Feel free to reapply in 2 weeks after improving your portfolio!"
            )
        await interaction.message.edit(content=f"❌ Declined by {interaction.user.mention}", view=None)
        await interaction.response.send_message("❌ Application declined.", ephemeral=True)

    @discord.ui.button(label="⏳ Pending Interview", style=discord.ButtonStyle.blurple)
    async def interview(self, interaction: discord.Interaction, button: Button):
        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Staff only!", ephemeral=True)
            return
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        if member:
            await member.send(
                "👋 Your application to **Young Boy Studios** looks great!\n"
                "We'd like to **interview you** — a staff member will DM you shortly to arrange a time."
            )
        await interaction.message.edit(content=f"⏳ Interview stage — set by {interaction.user.mention}", view=None)
        await interaction.response.send_message("⏳ Moved to interview stage.", ephemeral=True)

# ============================================================
# APPLY BUTTON VIEW
# ============================================================
class ApplyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📋 Start Application", style=discord.ButtonStyle.blurple, custom_id="start_apply")
    async def start_apply(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ApplicationModal())

    @discord.ui.button(label="📝 Part 2 of Application", style=discord.ButtonStyle.green, custom_id="apply_part2")
    async def apply_part2(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ApplicationModal2())

# ============================================================
# ROLE SELECTION VIEW
# ============================================================
class RoleSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔨 Builder", style=discord.ButtonStyle.secondary, custom_id="role_builder")
    async def builder(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(BUILDER_ROLE_ID)
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message("Removed Builder role!", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("Added Builder role!", ephemeral=True)

    @discord.ui.button(label="💻 Scripter", style=discord.ButtonStyle.secondary, custom_id="role_scripter")
    async def scripter(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(SCRIPTER_ROLE_ID)
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message("Removed Scripter role!", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("Added Scripter role!", ephemeral=True)

    @discord.ui.button(label="🎨 Modeller", style=discord.ButtonStyle.secondary, custom_id="role_modeller")
    async def modeller(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(MODELLER_ROLE_ID)
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message("Removed Modeller role!", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("Added Modeller role!", ephemeral=True)

    @discord.ui.button(label="🖥️ UI Designer", style=discord.ButtonStyle.secondary, custom_id="role_ui")
    async def ui_designer(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(UI_DESIGNER_ROLE_ID)
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message("Removed UI Designer role!", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("Added UI Designer role!", ephemeral=True)

# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="Young Boy Studios 🎮"
    ))
    status_cycle.start()

@bot.event
async def on_member_join(member):
    # Welcome message
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=f"👋 Welcome to Young Boy Studios, {member.display_name}!",
            description=(
                f"Hey {member.mention}! We're glad you're here.\n\n"
                f"📋 Head to <#{APPLY_CHANNEL_ID}> to **apply for the dev team**\n"
                f"📜 Check <#{RULES_CHANNEL_ID}> for the server rules\n"
                f"💬 Say hi in <#{GENERAL_CHANNEL_ID}>!\n\n"
                f"We're **Young Boy Studios** — a Roblox game dev team. Let's build something great!"
            ),
            color=0x5865F2
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")
        await channel.send(embed=embed)

    # DM the new member
    try:
        await member.send(
            f"👋 Hey **{member.display_name}**! Welcome to **Young Boy Studios**!\n\n"
            f"We're a Roblox game development studio looking for talented developers.\n"
            f"Head to the **#apply-here** channel to join the team!\n\n"
            f"Good luck! 🚀"
        )
    except:
        pass

    # Log
    log_channel = bot.get_channel(LOGS_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📥 **{member}** joined. Total members: {member.guild.member_count}")

@bot.event
async def on_member_remove(member):
    log_channel = bot.get_channel(LOGS_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📤 **{member}** left. Total members: {member.guild.member_count}")

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_channel = bot.get_channel(LOGS_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="🗑️ Message Deleted", color=0xff0000)
        embed.add_field(name="Author", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Content", value=message.content or "*(no text)*", inline=False)
        await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    log_channel = bot.get_channel(LOGS_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="✏️ Message Edited", color=0xffaa00)
        embed.add_field(name="Author", value=before.author.mention)
        embed.add_field(name="Channel", value=before.channel.mention)
        embed.add_field(name="Before", value=before.content[:500] or "*(empty)*", inline=False)
        embed.add_field(name="After", value=after.content[:500] or "*(empty)*", inline=False)
        await log_channel.send(embed=embed)

# ============================================================
# TASKS
# ============================================================
statuses = [
    "Young Boy Studios 🎮",
    "Building something epic 🔨",
    "Hiring developers! Apply now",
    "Roblox game dev team 🚀",
]

@tasks.loop(minutes=10)
async def status_cycle():
    status = random.choice(statuses)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name=status
    ))

# ============================================================
# SETUP COMMANDS (run these once to set up your server)
# ============================================================
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_apply(ctx):
    """Sends the application panel to the apply channel"""
    channel = bot.get_channel(APPLY_CHANNEL_ID) or ctx.channel
    embed = discord.Embed(
        title="🚀 Join Young Boy Studios Dev Team",
        description=(
            "We're looking for talented Roblox developers to join our studio!\n\n"
            "**We need:**\n"
            "🔨 Builders\n🎨 Modellers\n💻 Scripters\n🖥️ UI Designers\n\n"
            "**Click below to apply. The form has 2 parts — complete both!**\n\n"
            "✅ Work on real Roblox projects\n"
            "✅ Grow your portfolio\n"
            "✅ Be part of a studio from the ground up"
        ),
        color=0x5865F2
    )
    await channel.send(embed=embed, view=ApplyView())
    await ctx.send("✅ Apply panel sent!", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    """Sends the role selection panel"""
    embed = discord.Embed(
        title="🎭 Pick Your Roles",
        description="Click the buttons below to add or remove skill roles!",
        color=0x5865F2
    )
    await ctx.send(embed=embed, view=RoleSelectView())

# ============================================================
# MODERATION COMMANDS
# ============================================================
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member}** has been kicked. Reason: {reason}")
    log = bot.get_channel(LOGS_CHANNEL_ID)
    if log:
        await log.send(f"👢 {member} kicked by {ctx.author} — {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 **{member}** has been banned. Reason: {reason}")
    log = bot.get_channel(LOGS_CHANNEL_ID)
    if log:
        await log.send(f"🔨 {member} banned by {ctx.author} — {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, name):
    banned = [entry async for entry in ctx.guild.bans()]
    for entry in banned:
        if str(entry.user) == name:
            await ctx.guild.unban(entry.user)
            await ctx.send(f"✅ **{entry.user}** has been unbanned.")
            return
    await ctx.send("❌ User not found in ban list.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: int = 10, *, reason="No reason"):
    role = ctx.guild.get_role(MUTED_ROLE_ID)
    if role:
        await member.add_roles(role)
        await ctx.send(f"🔇 **{member}** muted for {duration} minutes. Reason: {reason}")
        await asyncio.sleep(duration * 60)
        await member.remove_roles(role)
        await ctx.send(f"🔊 **{member}** has been unmuted.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = ctx.guild.get_role(MUTED_ROLE_ID)
    if role:
        await member.remove_roles(role)
        await ctx.send(f"🔊 **{member}** has been unmuted.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    if member.id not in warnings_data:
        warnings_data[member.id] = []
    warnings_data[member.id].append({"reason": reason, "by": str(ctx.author), "time": datetime.now().isoformat()})
    count = len(warnings_data[member.id])
    await ctx.send(f"⚠️ **{member}** warned. Total warnings: {count}. Reason: {reason}")
    try:
        await member.send(f"⚠️ You've been warned in **Young Boy Studios**.\nReason: {reason}\nWarnings: {count}/3")
    except:
        pass
    if count >= 3:
        await ctx.send(f"🚨 {member.mention} has reached 3 warnings! Consider further action.")

@bot.command()
async def warnings(ctx, member: discord.Member = None):
    member = member or ctx.author
    warns = warnings_data.get(member.id, [])
    if not warns:
        await ctx.send(f"✅ **{member}** has no warnings.")
        return
    embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=0xffaa00)
    for i, w in enumerate(warns, 1):
        embed.add_field(name=f"Warning {i}", value=f"{w['reason']} — by {w['by']}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clearwarnings(ctx, member: discord.Member):
    warnings_data[member.id] = []
    await ctx.send(f"✅ Cleared warnings for **{member}**.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {amount} messages.", delete_after=3)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"⏱️ Slowmode set to {seconds} seconds.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Channel locked.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 Channel unlocked.")

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, nickname):
    await member.edit(nick=nickname)
    await ctx.send(f"✅ Nickname changed to **{nickname}**.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, member: discord.Member, *, role_name):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        await member.add_roles(role)
        await ctx.send(f"✅ Added **{role.name}** to {member.mention}.")
    else:
        await ctx.send("❌ Role not found.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role_name):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed **{role.name}** from {member.mention}.")
    else:
        await ctx.send("❌ Role not found.")

# ============================================================
# INFO & UTILITY COMMANDS
# ============================================================
@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"👤 {member}", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Account Created", value=member.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Roles", value=", ".join([r.mention for r in member.roles[1:]]) or "None")
    embed.add_field(name="Warnings", value=len(warnings_data.get(member.id, [])))
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"🏠 {g.name}", color=0x5865F2)
    embed.set_thumbnail(url=g.icon.url if g.icon else None)
    embed.add_field(name="Owner", value=g.owner.mention)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Channels", value=len(g.channels))
    embed.add_field(name="Roles", value=len(g.roles))
    embed.add_field(name="Created", value=g.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Boost Level", value=g.premium_tier)
    await ctx.send(embed=embed)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member}'s Avatar", color=0x5865F2)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latency: **{round(bot.latency * 1000)}ms**")

@bot.command()
async def uptime(ctx):
    await ctx.send(f"⏱️ Bot has been online since startup.")

@bot.command()
async def membercount(ctx):
    await ctx.send(f"👥 **{ctx.guild.member_count}** members in the server!")

@bot.command()
async def roleinfo(ctx, *, role_name):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send("❌ Role not found.")
        return
    embed = discord.Embed(title=f"🎭 Role: {role.name}", color=role.color)
    embed.add_field(name="ID", value=role.id)
    embed.add_field(name="Members", value=len(role.members))
    embed.add_field(name="Mentionable", value=role.mentionable)
    embed.add_field(name="Color", value=str(role.color))
    await ctx.send(embed=embed)

@bot.command()
async def whois(ctx, member: discord.Member = None):
    await userinfo(ctx, member)

# ============================================================
# FUN / ENGAGEMENT COMMANDS
# ============================================================
@bot.command()
async def dice(ctx):
    result = random.randint(1, 6)
    await ctx.send(f"🎲 You rolled a **{result}**!")

@bot.command()
async def coinflip(ctx):
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 **{result}!**")

@bot.command()
async def poll(ctx, question, *options):
    if len(options) < 2:
        await ctx.send("❌ Provide at least 2 options.")
        return
    emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    desc = "\n".join([f"{emojis[i]} {opt}" for i, opt in enumerate(options)])
    embed = discord.Embed(title=f"📊 {question}", description=desc, color=0x5865F2)
    msg = await ctx.send(embed=embed)
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

@bot.command()
async def suggest(ctx, *, suggestion):
    suggestions_data[len(suggestions_data)] = {"suggestion": suggestion, "by": str(ctx.author)}
    embed = discord.Embed(title="💡 New Suggestion", description=suggestion, color=0x00ff00)
    embed.set_footer(text=f"Suggested by {ctx.author}")
    channel = bot.get_channel(GENERAL_CHANNEL_ID) or ctx.channel
    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await ctx.message.delete()

@bot.command()
async def pick(ctx, *choices):
    if not choices:
        await ctx.send("❌ Give me some options!")
        return
    await ctx.send(f"🎯 I pick: **{random.choice(choices)}**")

@bot.command()
async def announce(ctx, *, message):
    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ Staff only!")
        return
    channel = bot.get_channel(ANNOUNCEMENTS_CHANNEL_ID) or ctx.channel
    embed = discord.Embed(title="📢 Announcement", description=message, color=0x5865F2, timestamp=datetime.now())
    embed.set_footer(text=f"Posted by {ctx.author}")
    await channel.send("@everyone", embed=embed)

@bot.command()
async def dm(ctx, member: discord.Member, *, message):
    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ Staff only!")
        return
    try:
        await member.send(f"📨 **Message from Young Boy Studios staff:**\n{message}")
        await ctx.send(f"✅ DM sent to {member.mention}.")
    except:
        await ctx.send("❌ Couldn't DM that user.")

@bot.command()
async def note(ctx, member: discord.Member, *, note_text):
    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ Staff only!")
        return
    if member.id not in notes_data:
        notes_data[member.id] = []
    notes_data[member.id].append({"note": note_text, "by": str(ctx.author), "time": datetime.now().isoformat()})
    await ctx.send(f"📝 Note added for {member.mention}.")

@bot.command()
async def notes(ctx, member: discord.Member):
    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ Staff only!")
        return
    member_notes = notes_data.get(member.id, [])
    if not member_notes:
        await ctx.send(f"📝 No notes for {member}.")
        return
    embed = discord.Embed(title=f"📝 Notes for {member}", color=0xffaa00)
    for i, n in enumerate(member_notes, 1):
        embed.add_field(name=f"Note {i} by {n['by']}", value=n['note'], inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def stafflist(ctx):
    role = ctx.guild.get_role(STAFF_ROLE_ID)
    if not role:
        await ctx.send("❌ Staff role not configured.")
        return
    members = [m.mention for m in role.members]
    embed = discord.Embed(title="👮 Staff Members", description="\n".join(members) or "None", color=0x5865F2)
    await ctx.send(embed=embed)

# ============================================================
# HELP COMMAND
# ============================================================
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🤖 Young Boy Studios Bot — Commands", color=0x5865F2)
    embed.add_field(name="🛠️ Setup (Admin)", value="`!setup_apply` `!setup_roles`", inline=False)
    embed.add_field(name="⚖️ Moderation", value="`!kick` `!ban` `!unban` `!mute` `!unmute` `!warn` `!warnings` `!clearwarnings` `!purge` `!slowmode` `!lock` `!unlock` `!nick` `!addrole` `!removerole`", inline=False)
    embed.add_field(name="ℹ️ Info", value="`!userinfo` `!serverinfo` `!avatar` `!ping` `!membercount` `!roleinfo` `!stafflist`", inline=False)
    embed.add_field(name="🎉 Fun & Utility", value="`!dice` `!coinflip` `!poll` `!suggest` `!pick` `!announce` `!dm` `!note` `!notes`", inline=False)
    embed.set_footer(text="Young Boy Studios Bot | Prefix: !")
    await ctx.send(embed=embed)

# ============================================================
# RUN THE BOT
# ============================================================
bot.run(TOKEN)
