import time
import os
import platform
import re
import asyncio
import inspect
import textwrap
from datetime import datetime, timedelta
from collections import Counter
import aiohttp
import discord
from discord.ext import commands

#Stolen from https://github.com/Rapptz/RoboDanny/blob/b513a32dfbd4fdbd910f7f56d88d1d012ab44826/cogs/meta.py
class TimeParser:
    def __init__(self, argument):
        compiled = re.compile(r"(?:(?P<hours>[0-9]{1,5})h)?(?:(?P<minutes>[0-9]{1,5})m)?(?:(?P<seconds>[0-9]{1,5})s)?$")
        self.original = argument
        try:
            self.seconds = int(argument)
        except ValueError as e:
            match = compiled.match(argument)
            if match is None or not match.group(0):
                raise commands.BadArgument('Wrong time specified, e.g. `4h`, `3m` or `2s`') from e

            self.seconds = 0
            hours = match.group('hours')
            if hours is not None:
                self.seconds += int(hours) * 3600
            minutes = match.group('minutes')
            if minutes is not None:
                self.seconds += int(minutes) * 60
            seconds = match.group('seconds')
            if seconds is not None:
                self.seconds += int(seconds)

        if self.seconds <= 0:
            raise commands.BadArgument('Given too little time, e.g.`4h`, `3m` or `2s`')

        if self.seconds > 604800: # 7 days
            raise commands.BadArgument("7 Days are a long time, don't you think?")

    @staticmethod
    def human_timedelta(dt):
        now = datetime.utcnow()
        delta = now - dt
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        years, days = divmod(days, 365)

        if days:
            if hours:
                return '%s and %s' % (Plural(Tag=days), Plural(Stunde=hours))
            return Plural(day=days)

        if hours:
            if minutes:
                return '%s and %s' % (Plural(Stunde=hours), Plural(Minute=minutes))
            return Plural(hour=hours)

        if minutes:
            if seconds:
                return '%s and %s' % (Plural(Minute=minutes), Plural(Sekunde=seconds))
            return Plural(Minute=minutes)
        return Plural(Second=seconds)

class Plural:
    def __init__(self, **attr):
        iterator = attr.items()
        self.name, self.value = next(iter(iterator))

    def __str__(self):
        v = self.value
        if v > 1:
            return '%s %sn' % (v, self.name)
        return '%s %s' % (v, self.name)

class Utility(commands.Cog, name="Utility"):
    '''General / useful commands that don't fit anywhere else'''

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        print('Error in {0.command.qualified_name}: {1}'.format(ctx, error))

    @staticmethod
    def _newImage(width, height, color):
        return Image.new("L", (width, height), color)

    @staticmethod
    def _getRoles(roles):
        string = ''
        for role in roles[::-1]:
            if not role.is_default():
                string += f'{role.mention}, '
        if string is '':
            return 'None'
        else:
            return string[:-2]

    @staticmethod
    def _getEmojis(emojis):
        string = ''
        for emoji in emojis:
            string += str(emoji)
        if string is '':
            return 'None'
        else:
            return string[:1000] #The maximum allowed charcter amount for embed fields

#    @commands.command(aliases=['uptime', 'up'])
#    async def status(self, ctx):
#        '''Infos über den Bot'''
#        timeUp = time.time() - self.bot.startTime
#        hours = timeUp / 3600
#        minutes = (timeUp / 60) % 60
#        seconds = timeUp % 60

#        admin = self.bot.AppInfo.owner
#        users = 0
#        channel = 0
#        if len(self.bot.commands_used.items()):
#            commandsChart = sorted(self.bot.commands_used.items(), key=lambda t: t[1], reverse=False)
#            topCommand = commandsChart.pop()
#            commandsInfo = '{} (Top-Command: {} x {})'.format(sum(self.bot.commands_used.values()), topCommand[1], topCommand[0])
#        else:
#            commandsInfo = str(sum(self.bot.commands_used.values()))
#        for guild in self.bot.guilds:
#            users += len(guild.members)
#            channel += len(guild.channels)

#        embed = discord.Embed(color=ctx.me.top_role.colour)
#        embed.set_footer(text='Dieser Bot ist Open-Source auf GitHub: https://github.com/Der-Eddy/discord_bot')
#        embed.set_thumbnail(url=ctx.me.avatar_url)
#        embed.add_field(name='Admin', value=admin, inline=False)
#        embed.add_field(name='Uptime', value='{0:.0f} Stunden, {1:.0f} Minuten und {2:.0f} Sekunden\n'.format(hours, minutes, seconds), inline=False)
#        embed.add_field(name='Beobachtete Benutzer', value=users, inline=True)
#        embed.add_field(name='Beobachtete Server', value=len(self.bot.guilds), inline=True)
#        embed.add_field(name='Beobachtete Channel', value=channel, inline=True)
#        embed.add_field(name='Ausgeführte Commands', value=commandsInfo, inline=True)
#        embed.add_field(name='Bot Version', value=self.bot.botVersion, inline=True)
#        embed.add_field(name='Discord.py Version', value=discord.__version__, inline=True)
#        embed.add_field(name='Python Version', value=platform.python_version(), inline=True)
        # embed.add_field(name='Speicher Auslastung', value=f'{round(memory_usage(-1)[0], 3)} MB', inline=True)
#        embed.add_field(name='Betriebssystem', value=f'{platform.system()} {platform.release()} {platform.version()}', inline=False)
#        await ctx.send('**:information_source:** Informationen über diesen Bot:', embed=embed)

#    @commands.command()
#    async def ping(self, ctx):
#        '''Misst die Response Time'''
#        ping = ctx.message
#        pong = await ctx.send('**:ping_pong:** Pong!')
#        delta = pong.created_at - ping.created_at
#        delta = int(delta.total_seconds() * 1000)
#        await pong.edit(content=f':ping_pong: Pong! ({delta} ms)\n*Discord WebSocket Latenz: {round(self.bot.latency, 5)} ms*')

    @commands.command(aliases=['archive'])
    @commands.cooldown(1, 60, commands.cooldowns.BucketType.channel)
    async def log(self, ctx, *limit: int):
        '''Archives the log of the current channel and uploads it as an attachment

        Example:
        -----------

        :log 100
        '''
        if not limit:
            limit = 10
        else:
            limit = limit[0]
        logFile = f'{ctx.channel}.log'
        counter = 0
        with open(logFile, 'w', encoding='UTF-8') as f:
            f.write(f'Archived news from the channel: {ctx.channel} am {ctx.message.created_at.strftime("%d.%m.%Y %H:%M:%S")}\n')
            async for message in ctx.channel.history(limit=limit, before=ctx.message):
                try:
                    attachment = '[Attached file: {}]'.format(message.attachments[0].url)
                except IndexError:
                    attachment = ''
                f.write('{} {!s:20s}: {} {}\r\n'.format(message.created_at.strftime('%d.%m.%Y %H:%M:%S'), message.author, message.clean_content, attachment))
                counter += 1
        msg = f':ok: {counter} Messages have been archived!'
        f = discord.File(logFile)
        await ctx.send(file=f, content=msg)
        os.remove(logFile)

    @log.error
    async def log_error(self, error, ctx):
        if isinstance(error, commands.errors.CommandOnCooldown):
            seconds = str(error)[34:]
            await ctx.send(f':alarm_clock: Cooldown! Try it in {seconds} again')

    @commands.command()
    async def invite(self, ctx):
        '''Creates an invite link for the current channel'''
        invite = await ctx.channel.create_invite(unique=False)
        msg = f'Invite link for **#{ctx.channel.name}**on server **{ctx.guild.name}**:\n`{invite}`'
        await ctx.send(msg)

    @commands.command()
    async def whois(self, ctx, member: discord.Member=None):
        '''Returns information about a user
        Example:
        -----------
        : whois @ Der-Eddy # 6508
        '''
        if member == None:
            member = ctx.author

        if member.top_role.is_default():
            topRole = 'everyone' #to prevent @everyone spam
            topRoleColour = '#000000'
        else:
            topRole = member.top_role
            topRoleColour = member.top_role.colour

        if member is not None:
            embed = discord.Embed(color=member.top_role.colour)
            embed.set_footer(text=f'UserID: {member.id}')
            embed.set_thumbnail(url=member.avatar_url)
            if member.name != member.display_name:
                fullName = f'{member} ({member.display_name})'
            else:
                fullName = member
            embed.add_field(name=member.name, value=fullName, inline=False)
            embed.add_field(name='Discord joined on', value='{}\n(Days since: {})'.format(member.created_at.strftime('%d.%m.%Y'), (datetime.now()-member.created_at).days), inline=True)
            embed.add_field(name='Server joined on', value='{}\n(Days since: {})'.format(member.joined_at.strftime('%d.%m.%Y'), (datetime.now()-member.joined_at).days), inline=True)
            embed.add_field(name='Avatar Link', value=member.avatar_url, inline=False)
            embed.add_field(name='roll', value=self._getRoles(member.roles), inline=True)
            embed.add_field(name='Roll color', value='{} ({})'.format(topRoleColour, topRole), inline=True)
            embed.add_field(name='Status', value=member.status, inline=True)
            await ctx.send(embed=embed)
        else:
            msg = ":no_entry: You haven't specified a user!"
            await ctx.send(msg)

    @commands.command()
    async def emoji(self, ctx, emojiname: str):
        '''Returns an enlarged version of a specified emoji

        Example:
        -----------

        : emoji Emilia
        '''
        emoji = discord.utils.find(lambda e: e.name.lower() == emojiname.lower(), self.bot.emojis)
        if emoji:
            tempEmojiFile = 'tempEmoji.png'
            async with aiohttp.ClientSession() as cs:
                async with cs.get(emoji.url) as img:
                    with open(tempEmojiFile, 'wb') as f:
                        f.write(await img.read())
                f = discord.File(tempEmojiFile)
                await ctx.send(file=f)
                os.remove(tempEmojiFile)
        else:
            await ctx.send(":x: Couldn't find the emoji specified :(")

    @commands.command(aliases=['emotes'])
    async def emojis(self, ctx):
        '''Outputs all emojis to which the bot has access'''
        msg = ''
        for emoji in self.bot.emojis:
            if len(msg) + len(str(emoji)) > 1000:
                await ctx.send(msg)
                msg = ''
            msg += str(emoji)
        await ctx.send(msg)

#    @commands.command(pass_context=True, aliases=['serverinfo', 'guild', 'membercount'])
#    async def server(self, ctx):
#        '''Returns information about the current Discord Guild'''
#        emojis = self._getEmojis(ctx.guild.emojis)
#        #print(emojis)
#        roles = self._getRoles(ctx.guild.roles)
#        embed = discord.Embed(color=0xf1c40f) #Golden
#        embed.set_thumbnail(url=ctx.guild.icon_url)
#        embed.set_footer(text='Emojis may be missing')
#        embed.add_field(name='Name', value=ctx.guild.name, inline=True)
#        embed.add_field(name='ID', value=ctx.guild.id, inline=True)
#        embed.add_field(name='owner', value=ctx.guild.owner, inline=True)
#        embed.add_field(name='Region', value=ctx.guild.region, inline=True)
#        embed.add_field(name='Members', value=ctx.guild.member_count, inline=True)
#        embed.add_field(name='Created on', value=ctx.guild.created_at.strftime('%d.%m.%Y'), inline=True)
#        if ctx.guild.system_channel:
#            embed.add_field(name='Standard Channel', value=f'#{ctx.guild.system_channel}', inline=True)
#        embed.add_field(name='AFK Voice Timeout', value=f'{int(ctx.guild.afk_timeout / 60)} min', inline=True)
#        embed.add_field(name='Guild Shard', value=ctx.guild.shard_id, inline=True)
#        embed.add_field(name='Rolls', value=roles, inline=True)
#        embed.add_field(name='Custom Emojis', value=emojis, inline=True)
#        await ctx.send(embed=embed)

    #Shameful copied from https://github.com/Rapptz/RoboDanny/blob/b513a32dfbd4fdbd910f7f56d88d1d012ab44826/cogs/meta.py
    @commands.command()
    @commands.cooldown(1, 30, commands.cooldowns.BucketType.user)
    async def timer(self, ctx, time : TimeParser, *, message=''):
        '''Set a timer and then notify you

        Example:
        -----------

        : timer 13m pizza

        : timer 2h stream starts
        '''
        reminder = None
        completed = None
        message = message.replace('@everyone', '@\u200beveryone').replace('@here', '@\u200bhere')

        if not message:
            reminder = ':timer: Ok {0.mention}, I set up a timer {1}.'
            completed = ':alarm_clock: Ding Ding Ding {0.mention}! Your timer has expired.'
        else:
            reminder = ':timer: Ok {0.mention}, I am setting a timer for `{2}` on {1}.'
            completed = ':alarm_clock: Ding Ding Ding {0.mention}! Your timer for `{1}` has expired.'

        human_time = datetime.utcnow() - timedelta(seconds=time.seconds)
        human_time = TimeParser.human_timedelta(human_time)
        await ctx.send(reminder.format(ctx.author, human_time, message))
        await asyncio.sleep(time.seconds)
        await ctx.send(completed.format(ctx.author, message, human_time))

    @timer.error
    async def timer_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
        elif isinstance(error, commands.errors.CommandOnCooldown):
            seconds = str(error)[34:]
            await ctx.send(f':alarm_clock: Cooldown! Try it in {seconds} again')

    @commands.command()
    @commands.cooldown(1, 30, commands.cooldowns.BucketType.user)
    async def remindme(self, ctx, usr: str, time : TimeParser, *, message=''):
        '''Set a timer and then notify you

        Example:
        -----------

        : timer 13m pizza

        : timer 2h stream starts
        '''
        user = self.bot.get_user(int(usr))
        reminder = None
        completed = None
        message = message.replace('@everyone', '@\u200beveryone').replace('@here', '@\u200bhere')

        if not message:
            reminder = ':timer: Ok {0.mention}, I set up a timer {1}.'
            completed = ':alarm_clock: Ding Ding Ding {0.mention}! Your timer has expired.'
        else:
            reminder = ':timer: Ok {0.mention}, I am setting a timer for {2} on {1}.'
            completed = ':alarm_clock: Ding Ding Ding {0.mention}! Your timer for {1} has expired.'

        human_time = datetime.utcnow() - timedelta(seconds=time.seconds)
        human_time = TimeParser.human_timedelta(human_time)
        await ctx.send(reminder.format(ctx.author, human_time, message))
        await asyncio.sleep(time.seconds)
        await user.send(completed.format(ctx.author, message, human_time))

    @timer.error
    async def timer_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
        elif isinstance(error, commands.errors.CommandOnCooldown):
            seconds = str(error)[34:]
            await ctx.send(f':alarm_clock: Cooldown! Try it in {seconds} again')

    @commands.command(hidden=True)
    async def roleUsers(self, ctx, *roleName: str):
        '''Lists all users of a role'''
        roleName = ' '.join(roleName)
        role = discord.utils.get(ctx.guild.roles, name=roleName)
        msg = ''
        for member in ctx.guild.members:
            if role in member.roles:
                msg += f'{member.id} | {member}\n'

        if msg == '':
            await ctx.send(':x: Could not find a user with this role!')
        else:
            await ctx.send(msg)

    @commands.command()
    async def games(self, ctx, *scope):
        '''Shows which games are being played and how often on the server'''
        games = Counter()
        for member in ctx.guild.members:
            if member.game != None:
                games[member.game] += 1
        msg = ':chart: Games currently played on this server\n'
        msg += '```js\n'
        msg += '{!s:40s}: {!s:>3s}\n'.format('Name', 'number')
        chart = sorted(games.items(), key=lambda t: t[1], reverse=True)
        for index, (name, amount) in enumerate(chart):
            if len(msg) < 1950:
                msg += '{!s:40s}: {!s:>3s}\n'.format(name, amount)
            else:
                amount = len(chart) - index
                msg += f'+ {amount} Others'
                break
        msg += '```'
        await ctx.send(msg)

    @commands.command()
    async def spoiler(self, ctx, *, text: str):
        '''Creates a GIF image that displays a spoiler text when hovering'''
        #https://github.com/flapjax/FlapJack-Cogs/blob/master/spoiler/spoiler.py
        content = '**' + ctx.author.display_name + '** has spoiled a text:'
        try:
            await ctx.message.delete()
        except discord.errors.Forbidden:
            content += '\n*(Please delete your own post)*'

        lineLength = 60
        margin = (5, 5)
        fontFile = "font/Ubuntu-R.ttf"
        fontSize = 18
        fontColor = 150
        bgColor = 20
        font = ImageFont.truetype(fontFile, fontSize)

        textLines = []
        for line in text.splitlines():
            textLines.extend(textwrap.wrap(line, lineLength, replace_whitespace=False))

        title = 'SPOILER! Hover to read'
        width = font.getsize(title)[0] + 50
        height = 0

        for line in textLines:
            size = font.getsize(line)
            width = max(width, size[0])
            height += size[1] + 2

        width += margin[0]*2
        height += margin[1]*2

        textFull = '\n'.join(textLines)

        spoilIMG = [self._newImage(width, height, bgColor) for _ in range(2)]
        spoilText = [title, textFull]

        for img, txt in zip(spoilIMG, spoilText):
            canvas = ImageDraw.Draw(img)
            canvas.multiline_text(margin, txt, font=font, fill=fontColor, spacing=4)

        path = f'tmp\\{ctx.message.id}.gif'

        spoilIMG[0].save(path, format='GIF', save_all=True, append_images=[spoilIMG[1]], duration=[0, 0xFFFF], loop=0)
        f = discord.File(path)
        await ctx.send(file=f, content=content)

        os.remove(path)

    @commands.command(aliases=['rank', 'role', 'roles'])
    async def ranks(self, ctx, *rankName: str):
        '''Listing of all ranks or joining a certain rank

        Example:
        -----------

        :rank

        :rank Python
        '''
        codingLoungeID = 161637499939192832
        wshbrID = 247830763649761282
        codingRankList = ['HTML + CSS', 'Javascript', 'C++ / C', '.NET', 'PHP', 'NSFW',
                    'Java', 'Gourmet', 'Assembler', 'Python', 'Math', 'AutoIt',
                    'Member', 'Clash', 'Books', 'Chess', 'Free Games', 'macOS', 'Linux', 'Windows', 'Rust']
        wshbrRankList = ['Chuunin', 'Genin']
        if ctx.guild.id == codingLoungeID:
            rankList = codingRankList
        elif ctx.guild.id == wshbrID:
            rankList = wshbrRankList

        if len(rankName) == 0 and ctx.guild.id not in [codingLoungeID, wshbrID] or ''.join(rankName) == 'all':
            rolesList = '`'
            for roleServer in ctx.guild.roles:
                if not roleServer.is_default():
                    count = 0
                    for member in ctx.guild.members:
                        if roleServer in member.roles:
                            count += 1
                    rolesList += f'{roleServer.name:30}{count} Members\n'
            embed = discord.Embed(color=0xf1c40f) #Golden
            embed.set_thumbnail(url=ctx.guild.icon_url)
            embed.add_field(name='Ranks', value=rolesList + '`', inline=True)
            await ctx.send(embed=embed)
        elif len(rankName) == 0 and ctx.guild.id in [codingLoungeID, wshbrID]:
            rolesList = '`'
            for role in rankList:
                count = 0
                roleServer = discord.utils.get(ctx.guild.roles, name=role)
                for member in ctx.guild.members:
                    if roleServer in member.roles:
                        count += 1
                rolesList += f'{role:20}{count} Members\n'
            embed = discord.Embed(color=0x3498db) #Blue
            embed.set_thumbnail(url=ctx.guild.icon_url)
            embed.set_footer(text='Use the ":rank RANKNAME" command to join a rank')
            embed.add_field(name='Ranks', value=rolesList + '`', inline=True)
            await ctx.send(embed=embed)
        elif ctx.guild.id not in [codingLoungeID, wshbrID]:
            await ctx.send(':x: This command only works on the Coding Lounge Server!')
        elif ctx.guild.id in [codingLoungeID, wshbrID]:
            synonyms = []
            synonyms.append(['html / css', 'HTML + CSS'])
            synonyms.append(['html + css', 'HTML + CSS'])
            synonyms.append(['html', 'HTML + CSS'])
            synonyms.append(['css', 'HTML + CSS'])
            synonyms.append(['javascript', 'Javascript'])
            synonyms.append(['js', 'Javascript'])
            synonyms.append(['c / c++', 'C++ / C'])
            synonyms.append(['c++', 'C++ / C'])
            synonyms.append(['c', 'C++ / C'])
            synonyms.append(['c#', '.NET'])
            synonyms.append(['.net', '.NET'])
            synonyms.append(['vs', '.NET'])
            synonyms.append(['php', 'PHP'])
            synonyms.append(['nsfw', 'NSFW'])
            synonyms.append(['porn', 'NSFW'])
            synonyms.append(['java', 'Java'])
            synonyms.append(['gourmet', 'Gourmet'])
            synonyms.append(['assembler', 'Assembler'])
            synonyms.append(['asm', 'Assembler'])
            synonyms.append(['python', 'Python'])
            synonyms.append(['math', 'Math'])
            synonyms.append(['autoit', 'AutoIt'])
            synonyms.append(['clash', 'Clash'])
            synonyms.append(['chess', 'Chess'])
            synonyms.append(['books', 'Books'])
            synonyms.append(['free games', 'Free Games'])
            synonyms.append(['free game', 'Free Games'])
            synonyms.append(['genin', 'Genin'])
            synonyms.append(['chuunin', 'Chuunin'])
            synonyms.append(['linux', 'Linux'])
            synonyms.append(['macos', 'macOS'])
            synonyms.append(['mac', 'macOS'])
            synonyms.append(['osx', 'macOS'])
            synonyms.append(['windows', 'Windows'])
            synonyms.append(['rust', 'Rust'])

            synonyms_dict = dict(synonyms)

            try:
                rankName = synonyms_dict[' '.join(rankName).lower()]
            except KeyError:
                rankName = ' '.join(rankName)

            if not rankName in rankList:
                await ctx.send(':x: Couldn\'t find that rank! Use `:ranks` to list all available ranks')
                return

            rank = discord.utils.get(ctx.guild.roles, name=rankName)
            if rank in ctx.message.author.roles:
                try:
                    await ctx.author.remove_roles(rank)
                except:
                    pass
                await ctx.send(f':negative_squared_cross_mark: Rank **{rank}** removed from **{ctx.author.mention}**')
            else:
                try:
                    await ctx.author.add_roles(rank)
                except:
                    pass
                await ctx.send(f':white_check_mark: Rank **{rank}** added to **{ctx.author.mention}**')

    @commands.command(aliases=['vote', 'addvotes', 'votes'])
    async def addvote(self, ctx, votecount = 'bool'):
        '''Adds emotes as reactions for polls / polls'''
        if votecount.lower() == 'bool':
            emote_list = ['✅', '❌']
        elif votecount in ['2', '3', '4', '5', '6', '7', '8', '9', '10']:
            #emotes = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
            #for whatever reason, the above won't work
            emotes = ['1\u20e3', '2\u20e3', '3\u20e3', '4\u20e3', '5\u20e3', '6\u20e3', '7\u20e3', '8\u20e3', '9\u20e3', '\U0001f51f']
            emote_list = []
            for i in range (0, int(votecount)):
                emote_list.append(emotes[i])
        else:
            ctx.say(':x: Please enter a number between 2 and 10')

        message = await ctx.channel.history(limit=1, before=ctx.message).flatten()
        try:
            await ctx.message.delete()
        except:
            pass

        for emote in emote_list:
            await message[0].add_reaction(emote)


    # This command needs to be at the end due to it's name
    @commands.command()
    async def commands(self, ctx):
        '''Shows how often which command has been used since the last startup'''
        msg = ':chart: List of commands executed (since last startup)\n'
        msg += 'All in all: {}\n'.format(sum(self.bot.commands_used.values()))
        msg += '```js\n'
        msg += '{!s:15s}: {!s:>4s}\n'.format('Name', 'number')
        chart = sorted(self.bot.commands_used.items(), key=lambda t: t[1], reverse=True)
        for name, amount in chart:
            msg += '{!s:15s}: {!s:>4s}\n'.format(name, amount)
        msg += '```'
        await ctx.send(msg)

def setup(bot):
    bot.add_cog(Utility(bot))
