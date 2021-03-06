import logging
import dotenv
from pyracing import client as pyracing
from discord.ext import commands, tasks
from logdna import LogDNAHandler
from .html_builder import *
from .commands.update_user import UpdateUser
from .commands.update import Update
from .commands.recent_races import RecentRaces
# from .commands.last_series import LastSeries
from .commands.yearly_stats import YearlyStats
from .commands.career_stats import CareerStats
from .commands.save_id import SaveId
from .commands.leaderboard import Leaderboard
# from .commands.iratings import Iratings
from .commands.all_series import AllSeries
from .commands.all_series_db import AllSeriesDb
from .commands.current_series import CurrentSeries
from .commands.set_fav_series import SetFavSeries
from .commands.add_fav_series import AddFavSeries
from .commands.remove_fav_series import RemoveFavSeries
from .commands.current_series_db import CurrentSeriesDb
from .db_helpers import *

dotenv.load_dotenv()

logdna_key = os.getenv("LOGDNA_INGESTION_KEY")
log = logging.getLogger('logdna')
log.setLevel(logging.DEBUG)
handler = LogDNAHandler(logdna_key, {'hostname': os.getenv("LOG_LOCATION")})
log.addHandler(handler)


class Iracing(commands.Cog):
    """A cog that can give iRacing data about users"""

    def __init__(self, bot):
        self.bot = bot
        self.pyracing = pyracing.Client(
            os.getenv("IRACING_USERNAME"),
            os.getenv("IRACING_PASSWORD")
        )
        self.all_series = []
        self.update_user = UpdateUser(self.pyracing, log)
        self.updater = Update(self.pyracing, log, self.update_user)
        self.recent_races = RecentRaces(self.pyracing, log)
        # self.last_series = LastSeries(self.pyracing, log)
        self.yearly_stats = YearlyStats(self.pyracing, log, self.update_user)
        self.career_stats = CareerStats(self.pyracing, log, self.update_user)
        self.save_id = SaveId(log)
        self.leaderboard = Leaderboard(log)
        # self.iratings = Iratings(log)
        self.all_series_command = AllSeries(log)
        self.all_series_db = AllSeriesDb(log)
        self.current_series_db = CurrentSeriesDb(log)
        self.set_fav_series = SetFavSeries(log)
        self.add_fav_series = AddFavSeries(log)
        self.remove_fav_series = RemoveFavSeries(log)
        # self.migrate_fav_series.start()
        self.update_all_servers.start()

    @tasks.loop(hours=3, reconnect=False)
    async def update_all_servers(self):
        """Update all users career stats and iratings for building a current leaderboard"""
        log.info('loading all series')
        self.all_series = await self.pyracing.current_seasons(series_id=True)
        self.all_series.sort(key=lambda x: x.series_id)

        log.info('Successfully got all current season data')
        await self.updater.update_all_servers(self.all_series)
        await Tortoise.close_connections()

    @tasks.loop(hours=4, reconnect=False)
    async def migrate_fav_series(self):
        """Moves fav series from json to DB, should be one time use"""
        log.info('migrating fav series')
        guilds = []
        for file in os.scandir(folder):
            if file.path.endswith('.json'):
                guilds.append(os.path.basename(file.path)[:-5])

        await init_tortoise()
        for guild_id in guilds:
            try:
                favs = get_guild_favorites(guild_id)
                parsed_ids = list(map(int, favs))
                await set_all_fav_series(guild_id, parsed_ids)
            except Exception as e:
                traceback.print_exc()
                log.info(f'failed updating {guild_id}')
                log.info(str(e))
        await Tortoise.close_connections()
        print('finished migrating fav series')
        log.info('finished migrating fav series')

    @commands.command(name='update')
    async def update(self, ctx):
        """Update the career, yearly stats, and iratings for the user who called the command in the given server"""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        await self.updater.update_member(ctx)

    @commands.command(name='updateserver')
    async def updateserver(self, ctx):
        """Update all users career and yearly stats and iratings for building a current leaderboard.
        This is run every hour anyways, so it isn't necessary most of the time to run manually"""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        await self.updater.update_server(ctx)

    @commands.command(name='recentraces')
    async def recentraces(self, ctx, *, iracing_id=None):
        """Shows the recent race data for the given iracing id. If no iracing id is provided it will attempt
        to use the stored iracing id for the user who called the command."""
        await self.recent_races.call(ctx, iracing_id, self.all_series)

    # @commands.command(name='lastseries')
    # async def lastseries(self, ctx, *, iracing_id=None):
    #     """Shows the recent series data for the given iracing id. If no iracing id is provided it will attempt
    #     to use the stored iracing id for the user who called the command."""
    #     await self.last_series.call(ctx, iracing_id)

    @commands.command(name='yearlystats')
    async def yearlystats(self, ctx, *, iracing_id=None):
        """Shows the yearly stats for the given iracing id. If no iracing id is provided it will attempt
        to use the stored iracing id for the user who called the command."""
        await self.yearly_stats.call(ctx, iracing_id)

    @commands.command(name='careerstats')
    async def careerstats(self, ctx, *, iracing_id=None):
        """Shows the career stats for the given iracing id. If no iracing id is provided it will attempt
        to use the stored iracing id for the user who called the command."""
        await self.career_stats.call(ctx, iracing_id)

    @commands.command(name='saveid')
    async def saveid(self, ctx, *, iracing_id):
        """Save your iRacing ID to be placed on the leaderboard.
        Your ID can be found by the top right of your account page under "Customer ID"."""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        await self.save_id.call(ctx, iracing_id)
        await Tortoise.close_connections()

    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx, category='road', type='career'):
        """Displays a leaderboard of the users who have used `!saveid`.
        If the data is not up to date, try `!update` first.
        The categories are `road`, `oval`, `dirtroad`, and `dirtoval` and
        the types are `career` and `yearly`. Default is `road` `career`"""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        await self.leaderboard.call(ctx, category, type)

    # @commands.command()
    # async def iratings(self, ctx, category='road'):
    #     await self.iratings.call(ctx, category)

    @commands.command(name='allseries')
    async def allseries(self, ctx):
        """Show all series currently in iRacing to help with choosing your favorites for
        `!setfavseries`"""
        await self.all_series_db.call(ctx)

    @commands.command(name='setfavseries')
    async def setfavseries(self, ctx, *, ids=''):
        """Use command `!allseries` to get a list of all series and ids.
            Then use this command `!setfavseries` with a list of comma
            separated ids to set your favorite series"""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        if ids == '':
            await ctx.send('You must pass at least one ID. Use `!help setfavseries` for more help')
            return

        await self.set_fav_series.call(ctx, ids, self.all_series)

    @commands.command(name='currentseries')
    async def currentseries(self, ctx):
        """Once you set favorites with `!setfavseries` or `!addfavseries` this command will
        show this and next week tracks for your favorite series"""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        await self.current_series_db.call(ctx)

    @commands.command(name='addfavseries')
    async def addfavseries(self, ctx, series_id=None):
        """Add a series to your favorites, use `!currentseries` to see
        what your current favorites are"""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        if not series_id:
            await ctx.send('You must pass a series ID with this command. Use `!help addfavseries` for more info.')

        await self.add_fav_series.call(ctx, series_id, self.all_series)

    @commands.command(name='removefavseries')
    async def removefavseries(self, ctx, series_id=None):
        """Remove a series from your favorites list, use `!currentseries` to see
        what your current favorites are"""
        if is_support_guild(ctx.guild.id):
            await ctx.send('Sorry, this discord does not allow update, saveid, '
                           'leaderboard, and series commands so as not to overload me. '
                           'Try `!careerstats` or `!yearlystats` with your customer ID to test '
                           'or go to #invite-link to bring the bot to your discord for all functionality')
            return
        if not series_id:
            await ctx.send('You must pass a series ID with this command. Use `!help removefavseries` for more info.')

        await self.remove_fav_series.call(ctx, series_id)


def setup(bot):
    bot.add_cog(Iracing(bot))
