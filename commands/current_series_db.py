from ..storage import *
from ..html_builder import *
import imgkit
import traceback
from ..db_helpers import init_tortoise, Guild, Tortoise


class CurrentSeriesDb:
    def __init__(self, log):
        self.log = log

    async def call(self, ctx):
        try:
            await init_tortoise()
            guild = await Guild.get(discord_id=ctx.guild.id)
            favorite_series = await guild.favorite_series.all()
            if not favorite_series:
                await ctx.send('Follow the directions by calling `!setfavseries` to set favorite'
                               'series before using this command')
                return

            this_week_string = await build_race_week_string_db(favorite_series, 'This Week', self.log, 0)
            next_week_string = await build_race_week_string_db(favorite_series, 'Next Week', self.log, 1)

            this_week_filename = f'{ctx.guild.id}_this_week.jpg'
            next_week_filename = f'{ctx.guild.id}_next_week.jpg'
            imgkit.from_string(this_week_string, this_week_filename)
            imgkit.from_string(next_week_string, next_week_filename)
            await ctx.send(file=discord.File(this_week_filename))
            await ctx.send(file=discord.File(next_week_filename))
            cleanup_file(this_week_filename)
            cleanup_file(next_week_filename)
            await Tortoise.close_connections()
        except Exception as e:
            self.log.warning(f'Current series failed: {e}')
            traceback.print_exc()
            await Tortoise.close_connections()
