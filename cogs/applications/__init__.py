from .applications import ApplicationsCog

def setup(bot):
    bot.add_cog(ApplicationsCog(bot))
