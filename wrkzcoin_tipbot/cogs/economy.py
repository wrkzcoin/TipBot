import sys, traceback
import time, timeago
import disnake
from disnake.ext import commands

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from config import config
from Bot import *
from Bot import logchanbot
import store


class database_economy():

    async def economy_get_user(self, user_id: str, user_name: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_userinfo WHERE `user_id` = %s LIMIT 1 """
                    await cur.execute(sql, (user_id,))
                    result = await cur.fetchone()
                    if result is None:
                        sql = """ INSERT INTO discord_economy_userinfo (`user_id`, `user_name`, `joined`) 
                                  VALUES (%s, %s, %s) """
                        await cur.execute(sql, (user_id, user_name, int(time.time()),))
                        await conn.commit()

                        sql = """ SELECT * FROM discord_economy_userinfo WHERE `user_id` = %s LIMIT 1 """
                        await cur.execute(sql, (user_id,))
                        result = await cur.fetchone()
                        return result
                    else:
                        return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_last_activities(self, user_id: str, all_activities: bool=False):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if all_activities:
                        sql = """ SELECT * FROM discord_economy_activities WHERE `user_id` = %s ORDER BY `id` DESC """
                        await cur.execute(sql, (user_id,))
                        result = await cur.fetchall()
                        if result: return result
                    else:
                        sql = """ SELECT * FROM discord_economy_activities WHERE `user_id` = %s ORDER BY `id` DESC LIMIT 1 """
                        await cur.execute(sql, (user_id,))
                        result = await cur.fetchone()
                        if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_user_activities_duration(self, user_id: str, duration: int=3600):
        lapDuration = int(time.time()) - duration
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_activities WHERE `user_id` = %s AND `status`=%s AND `started`>%s ORDER BY `started` DESC """
                    await cur.execute(sql, (user_id, 'COMPLETED', lapDuration,))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_get_guild_worklist(self, guild_id: str, get_all: bool=True):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if get_all:
                        sql = """ SELECT * FROM discord_economy_work_reward WHERE `status`=%s ORDER BY `work_id` ASC """
                        await cur.execute(sql, (1))
                        result = await cur.fetchall()
                        if result: return result
                    else:
                        sql = """ SELECT * FROM discord_economy_work_reward WHERE `guild_id` = %s AND `status`=%s ORDER BY `work_id` ASC """
                        await cur.execute(sql, (guild_id, 1))
                        result = await cur.fetchall()
                        if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_workd_id(self, work_id: int):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_work_reward WHERE `work_id`=%s LIMIT 1 """
                    await cur.execute(sql, (work_id))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_insert_activity(self, user_id: str, guild_id: str, work_id: int, duration_in_second: int, reward_coin_name: str, reward_amount: float, fee_amount: float, reward_decimal: float, exp: float, health: float, energy: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_activities (`user_id`, `guild_id`, `work_id`, `started`, `duration_in_second`, `reward_coin_name`, 
                              `reward_amount`, `fee_amount`, `reward_decimal`, `exp`, `health`, `energy`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, guild_id, work_id, int(time.time()), duration_in_second, reward_coin_name, reward_amount, fee_amount, reward_decimal, exp, health, energy))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_update_activity(self, act_id: int, user_id: str, exp: int, health: float, energy: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_economy_activities SET `completed`=%s, `status`=%s 
                              WHERE `id`=%s AND `user_id`=%s """
                    await cur.execute(sql, (int(time.time()), 'COMPLETED', act_id, user_id,))
                    # 2nd query
                    sql = """ UPDATE discord_economy_userinfo SET `exp`=`exp`+%s, `health_current`=`health_current`+%s,
                              `energy_current`=`energy_current`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (exp, health, energy, user_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_guild_foodlist(self, guild_id: str, get_all: bool=True):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if get_all:
                        sql = """ SELECT * FROM discord_economy_food ORDER BY `food_id` ASC """
                        await cur.execute(sql)
                        result = await cur.fetchall()
                        if result: return result
                    else:
                        sql = """ SELECT * FROM discord_economy_food WHERE `guild_id` = %s ORDER BY `food_id` ASC """
                        await cur.execute(sql, (guild_id,))
                        result = await cur.fetchall()
                        if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_insert_eating(self, user_id: str, guild_id: str, cost_coin_name: str, cost_expense_amount: float, fee_amount: float, cost_decimal: float, gained_energy: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_eating (`user_id`, `guild_id`, `date`, `cost_coin_name`, `cost_expense_amount`, 
                              `fee_amount`, `cost_decimal`, `gained_energy`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, guild_id, int(time.time()), cost_coin_name, cost_expense_amount, fee_amount, cost_decimal, gained_energy,))
                    # 2nd query
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`+%s WHERE `user_id`=%s """
                    await cur.execute(sql, (gained_energy, user_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_food_id(self, food_id: int):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_food WHERE `food_id`=%s LIMIT 1 """
                    await cur.execute(sql, (food_id))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_guild_eating_list_record(self, guild_id: str, duration: int=3600):
        lapDuration = int(time.time()) - duration
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_eating WHERE `guild_id` = %s AND `date`>%s ORDER BY `date` DESC """
                    await cur.execute(sql, (guild_id, lapDuration,))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_user_eating_list_record(self, user_id: str, duration: int=3600):
        lapDuration = int(time.time()) - duration
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_eating WHERE `user_id` = %s AND `date`>%s ORDER BY `date` DESC """
                    await cur.execute(sql, (user_id, lapDuration,))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_list_secret_items(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_secret_items WHERE `usable`=%s """
                    await cur.execute(sql, ('YES'))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_insert_secret_findings(self, item_id: int, user_id: str, guild_id: str, item_health: float, item_energy: float, item_gem: int, can_use: bool=True):
        usable = "NO"
        if can_use:
            usable = "YES"
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_secret_findings (`item_id`, `user_id`, `guild_id`, `date`, 
                              `item_health`, `item_energy`, `item_gem`, `can_use`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (item_id, user_id, guild_id, int(time.time()), item_health, item_energy, item_gem, usable,))
                    # 2nd query
                    if item_id != 8:
                        sql = """ UPDATE discord_economy_userinfo SET `backpack_items`=`backpack_items`+1 WHERE `user_id`=%s """
                        await cur.execute(sql, (user_id,))
                    sql = """ UPDATE discord_economy_secret_items SET `found_times`=`found_times`+1 WHERE `id`=%s """
                    await cur.execute(sql, (item_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_user_searched_item_list_record(self, user_id: str, duration: int=3600):
        lapDuration = int(time.time()) - duration
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_secret_findings WHERE `user_id` = %s AND `date`>%s ORDER BY `date` DESC """
                    await cur.execute(sql, (user_id, lapDuration,))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_get_user_inventory(self, user_id: str, count_what: str='ALL'):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if count_what == "ALL":
                        sql = """ SELECT A.item_id, B.item_name, B.item_emoji, A.user_id, A.item_health, A.item_energy, A.item_gem, COUNT(*) AS numbers 
                                  FROM discord_economy_secret_findings A JOIN discord_economy_secret_items B ON B.id = A.item_id 
                                  AND A.user_id=%s AND A.used=%s AND A.can_use=%s GROUP BY A.item_id """
                        await cur.execute(sql, (user_id, 'NO', 'YES'))
                        result = await cur.fetchall()
                        if result: return result
                    else:
                        sql = """ SELECT A.item_id, B.item_name, B.item_emoji, A.user_id, A.item_health, A.item_energy, A.item_gem, COUNT(*) AS numbers 
                                  FROM discord_economy_secret_findings A JOIN discord_economy_secret_items B ON B.id = A.item_id 
                                  AND A.user_id=%s AND A.used=%s AND A.can_use=%s AND B.item_name=%s GROUP BY A.item_id """
                        await cur.execute(sql, (user_id, 'NO', 'YES', count_what))
                        result = await cur.fetchone()
                        if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []


    async def economy_get_item_id(self, item_id: int):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_secret_items WHERE `id`=%s LIMIT 1 """
                    await cur.execute(sql, (item_id))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return None

    async def economy_item_update_used(self, user_id: str, item_id: str, gained_energy: float=0.0, gained_health: float=0.0):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_economy_secret_findings SET `used_date`=%s, `used`=%s WHERE `used`=%s AND `item_id`=%s AND `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (int(time.time()), 'YES', 'NO', item_id, user_id,))
                    # 2nd query
                    if gained_energy > 0:
                        sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`+%s, `backpack_items`=`backpack_items`-1 WHERE `user_id`=%s LIMIT 1 """
                        await cur.execute(sql, (gained_energy, user_id,))
                    # could be 3rd query
                    if gained_health > 0:
                        sql = """ UPDATE discord_economy_userinfo SET `health_current`=`health_current`+%s, `backpack_items`=`backpack_items`-1 WHERE `user_id`=%s LIMIT 1 """
                        await cur.execute(sql, (gained_health, user_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_shop_get_item(self, item_name: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_shopbot WHERE `item_name`=%s OR `item_emoji`=%s LIMIT 1 """
                    await cur.execute(sql, (item_name, item_name))
                    result = await cur.fetchone()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_shop_get_item_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_shopbot ORDER BY `credit_cost` DESC """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []


    async def discord_economy_userinfo_what(self, guild_id: str, user_id: str, item_id: int, what: str, item_nos: int, credit: int):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_economy_shopbot SET `numb_bought`=`numb_bought`+1 WHERE `id`=%s """
                    await cur.execute(sql, (item_id,))
                    # 2nd query
                    if what.upper() == "BAIT" or what == "🎣":
                        sql = """ UPDATE discord_economy_userinfo SET `fishing_bait`=`fishing_bait`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "SEED" or what == "🌱":
                        sql = """ UPDATE discord_economy_userinfo SET `tree_seed`=`tree_seed`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "FARM" or what == "👨‍🌾":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_farm`=`numb_farm`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "CHICKENFARM" or what.upper() == "CHICKEN_FARM" or what.upper() == "CHICKEN FARM":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_chicken_farm`=`numb_chicken_farm`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "TRACTOR" or what == "🚜":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_tractor`=`numb_tractor`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "BOAT" or what == "🚣":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_boat`=`numb_boat`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "DAIRY CATTLE" or what == "DAIRYCATTLE":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_dairy_cattle`=`numb_dairy_cattle`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "MARKET" or what == "🛒":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_market`=`numb_market`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                    elif what.upper() == "COW" or what == "🐄":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_cow`=`numb_cow`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                        # insert to dairy ownership
                        sql = """ INSERT INTO discord_economy_dairy_cattle_ownership (`user_id`, `guild_id`, `bought_date`, `credit_cost`, `possible_collect_date`) 
                                  VALUES (%s, %s, %s, %s, %s) """
                        await cur.execute(sql, (user_id, guild_id, int(time.time()), credit, int(time.time())+config.economy.dairy_collecting_time))
                    elif what.upper() == "CHICKEN" or what == "🐔":
                        sql = """ UPDATE discord_economy_userinfo SET `numb_chicken`=`numb_chicken`+%s, `credit`=`credit`+%s WHERE `user_id`=%s """
                        await cur.execute(sql, (item_nos, credit, user_id,))
                        # insert to dairy ownership
                        sql = """ INSERT INTO discord_economy_chickenfarm_ownership (`user_id`, `guild_id`, `bought_date`, `credit_cost`, `possible_collect_date`) 
                                  VALUES (%s, %s, %s, %s, %s) """
                        await cur.execute(sql, (user_id, guild_id, int(time.time()), credit, int(time.time())+config.economy.egg_collecting_time))
                    elif what.upper() == "CREDIT" or what == "💵":
                        sql = """ UPDATE discord_economy_userinfo SET `credit`=`credit`+%s,`gem_credit`=`gem_credit`-1 WHERE `user_id`=%s """
                        await cur.execute(sql, (credit, user_id))
                    # update to activities
                    sql = """ INSERT INTO discord_economy_shopbot_activities (`shopitem_id`, `user_id`, `guild_id`, `credit_cost`, `date`) 
                              VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (item_id, user_id, guild_id, credit, int(time.time()),))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def economy_get_list_fish_items(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_fish_items """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    # Planned not use
    # TODO: remove
    async def economy_insert_fishing(self, fish_id: int, user_id: str, guild_id: str, fish_strength: float, fish_weight: float, exp_gained: float, energy_loss: float, caught: str, sellable: str="YES"):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_fishing (`fish_id`, `user_id`, `guild_id`, `fish_strength`, `fish_weight`, 
                               `exp_gained`, `energy_loss`, `caught`, `date`, `sellable`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (fish_id, user_id, guild_id, fish_strength, fish_weight, exp_gained, energy_loss, caught, int(time.time()), sellable,))
                    ## add experience and engery loss
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s, `fishing_exp`=`fishing_exp`+%s,`fishing_bait`=`fishing_bait`-1 WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (energy_loss, exp_gained, user_id,))
                    # add fish found
                    sql = """ UPDATE discord_economy_fish_items SET `found_times`=`found_times`+1 WHERE `id`=%s LIMIT 1 """
                    await cur.execute(sql, (fish_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def economy_insert_fishing_multiple(self, list_fishes, total_energy_loss: float, total_exp: float, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_fishing (`fish_id`, `user_id`, `guild_id`, `fish_strength`, `fish_weight`, 
                               `exp_gained`, `energy_loss`, `caught`, `date`, `sellable`) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    fishing_arr = []
                    for each_fish in list_fishes:
                        fishing_arr.append((each_fish['id'], each_fish['user_id'], each_fish['guild_id'], each_fish['fish_strength'], each_fish['fish_weight'], each_fish['exp_gained'], each_fish['energy_loss'], each_fish['caught'], int(time.time()), 'YES'))
                    await cur.executemany(sql, fishing_arr)

                    ## add experience and engery loss
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s, `fishing_exp`=`fishing_exp`+%s,`fishing_bait`=`fishing_bait`-%s WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (total_energy_loss, total_exp, len(list_fishes), user_id,))
                    # add fish found
                    sql = """ UPDATE discord_economy_fish_items SET `found_times`=`found_times`+1 WHERE `id`=%s LIMIT 1 """
                    fishing_id_arr = []
                    for each_fish in list_fishes:
                        fishing_id_arr.append((each_fish['id']))
                    await cur.executemany(sql, fishing_id_arr)
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_list_fish_caught(self, user_id: str, sold: str='NO', caught: str='YES'):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT A.fish_id, B.fish_name, B.fish_emoji, B.minimum_sell_kg, B.credit_per_kg, A.user_id, A.sold, 
                              COUNT(*) AS numbers, SUM(fish_weight) AS Weights 
                              FROM discord_economy_fishing A JOIN discord_economy_fish_items B ON B.id = A.fish_id 
                              AND A.user_id=%s AND A.sold=%s AND A.caught=%s GROUP BY A.fish_id """
                    await cur.execute(sql, (user_id, 'NO', 'YES'))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []


    async def economy_sell_fishes(self, fish_id: int, user_id: str, guild_id: str, total_weight: float, total_credit: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_fish_sold (`fish_id`, `user_id`, `guild_id`, `total_weight`, `total_credit`, `date`) 
                              VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (fish_id, user_id, guild_id, total_weight, total_credit, int(time.time()),))
                    ## add user credit
                    sql = """ UPDATE discord_economy_userinfo SET `credit`=`credit`+%s WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (total_credit, user_id,))
                    # update selected fishes to sold
                    sql = """ UPDATE discord_economy_fishing SET `sold`=%s, `sold_date`=%s WHERE `fish_id`=%s AND `user_id`=%s AND `sold`=%s AND `sellable`=%s """
                    await cur.execute(sql, ('YES', int(time.time()), fish_id, user_id, 'NO', 'YES'))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None


    async def economy_insert_planting(self, user_id: str, guild_id: str, exp_gained: float, energy_loss: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_planting (`user_id`, `guild_id`, `exp_gained`, `energy_loss`, `date`) 
                              VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, guild_id, exp_gained, energy_loss, int(time.time()),))
                    ## add experience and engery loss
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_seed`=`tree_seed`-1,`plant_exp`=`plant_exp`+%s, `tree_planted`=`tree_planted`+1 
                              WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (energy_loss, exp_gained, user_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_insert_woodcutting(self, user_id: str, guild_id: str, timber_volume: float, leaf_kg: float, energy_loss: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_woodcutting (`user_id`, `guild_id`, `timber_volume`, `leaf_kg`, `energy_loss`, `date`) 
                              VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, guild_id, timber_volume, leaf_kg, energy_loss, int(time.time()),))
                    ## add experience and engery loss
                    sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_cut`=`tree_cut`+1 WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (energy_loss, user_id,))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_get_timber_user(self, user_id: str, sold_timber: str='NO', sold_leaf='NO'):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) AS tree_numbers, SUM(timber_volume) AS timbers 
                              FROM discord_economy_woodcutting WHERE `user_id`=%s AND `timber_sold`=%s """
                    await cur.execute(sql, (user_id, 'NO'))
                    result = await cur.fetchone()
                    sql = """ SELECT COUNT(*) AS tree_numbers, SUM(leaf_kg) AS leaves 
                              FROM discord_economy_woodcutting WHERE `user_id`=%s AND `leaf_sold`=%s """
                    await cur.execute(sql, (user_id, 'NO'))
                    result2 = await cur.fetchone()
                    if result and result2: return {'timber_nos': result['tree_numbers'], 'timber_vol': result['timbers'], 'leaf_nos': result2['tree_numbers'], 'leaf_kg': result2['leaves']}
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_farm_get_list_plants(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_farm_plantlist """
                    await cur.execute(sql,)
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            await logchanbot(traceback.format_exc())
        return []

    async def economy_farm_user_planting_check_max(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) FROM discord_economy_farm_planting 
                              WHERE `user_id`=%s and `harvested`=%s """
                    await cur.execute(sql, (user_id, "NO"))
                    result = await cur.fetchone()
                    if 'COUNT(*)' in result:
                        return int(result['COUNT(*)'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return 0

    async def economy_farm_user_planting_group_harvested(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT A.id, A.plant_id, B.plant_name, B.growing_emoji, B.plant_emoji, B.duration_harvest, A.user_id, A.date, 
                              A.harvest_date, A.can_harvest_date, A.harvested, A.number_of_item, A.credit_per_item, A.sold, 
                              COUNT(*) as numbers, SUM(B.number_of_item) AS total_products 
                              FROM discord_economy_farm_planting A JOIN discord_economy_farm_plantlist B ON B.id = A.plant_id 
                              AND A.harvested=%s AND A.sold=%s AND A.user_id=%s
                              GROUP BY A.plant_id """
                    await cur.execute(sql, ('YES', 'NO', user_id))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_farm_user_planting_nogroup(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT A.id, A.plant_id, B.plant_name, B.growing_emoji, B.plant_emoji, B.duration_harvest, A.user_id, A.date, 
                              A.harvest_date, A.can_harvest_date, A.harvested, A.number_of_item, A.credit_per_item 
                              FROM discord_economy_farm_planting A JOIN discord_economy_farm_plantlist B ON B.id = A.plant_id 
                              AND A.user_id=%s WHERE A.harvested=%s ORDER BY id ASC """
                    await cur.execute(sql, (user_id, 'NO'))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_farm_insert_crop(self, plant_id: int, user_id: str, guild_id: str, can_harvest_date: int, number_of_item: int, credit_per_item: float, exp_gained: float, energy_loss: float, numb_planting: int=1):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if numb_planting > 1:
                        sql = """ INSERT INTO discord_economy_farm_planting (`plant_id`, `user_id`, `guild_id`, `date`, `can_harvest_date`, 
                                  `number_of_item`, `credit_per_item`, `energy_loss`, `exp_gained`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        energy_loss = round(energy_loss/numb_planting, 2)
                        temp_list = [(plant_id, user_id, guild_id, int(time.time()), can_harvest_date, number_of_item, credit_per_item, energy_loss, exp_gained)]*numb_planting
                        await cur.executemany(sql, temp_list)
                        inserted = cur.rowcount
                        ## add experience and engery loss
                        sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_seed`=`tree_seed`-%s,`plant_exp`=`plant_exp`+%s, `farm_grow`=`farm_grow`+%s 
                                  WHERE `user_id`=%s LIMIT 1 """
                        await cur.execute(sql, (energy_loss, numb_planting, exp_gained*numb_planting, numb_planting, user_id,))
                        # add planted numbers found
                        sql = """ UPDATE discord_economy_farm_plantlist SET `planted_times`=`planted_times`+%s WHERE `id`=%s LIMIT 1 """
                        await cur.execute(sql, (numb_planting, plant_id,))
                        await conn.commit()
                        return True
                    elif numb_planting == 1:
                        sql = """ INSERT INTO discord_economy_farm_planting (`plant_id`, `user_id`, `guild_id`, `date`, `can_harvest_date`, 
                                  `number_of_item`, `credit_per_item`, `energy_loss`, `exp_gained`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (plant_id, user_id, guild_id, int(time.time()), can_harvest_date, number_of_item, credit_per_item, energy_loss, exp_gained,))
                        ## add experience and engery loss
                        sql = """ UPDATE discord_economy_userinfo SET `energy_current`=`energy_current`-%s,`tree_seed`=`tree_seed`-1,`plant_exp`=`plant_exp`+%s, `farm_grow`=`farm_grow`+1 
                                  WHERE `user_id`=%s LIMIT 1 """
                        await cur.execute(sql, (energy_loss, exp_gained, user_id,))
                        # add planted numbers found
                        sql = """ UPDATE discord_economy_farm_plantlist SET `planted_times`=`planted_times`+1 WHERE `id`=%s LIMIT 1 """
                        await cur.execute(sql, (plant_id,))
                        await conn.commit()
                        return True                
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_farm_harvesting(self, user_id: str, plantlist):        
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE discord_economy_farm_planting SET `harvest_date`=%s, `harvested`=%s WHERE `user_id`=%s AND `id`=%s AND `harvested`=%s """
                    list_update = []
                    for each_item in plantlist:
                        list_update.append((int(time.time()), 'YES', user_id, each_item, 'NO'))
                    await cur.executemany(sql, list_update)
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_farm_sell_item(self, plant_id: int, user_id: str, guild_id: str, total_credit: float, farm_item_sold: int):        
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    ## add user credit
                    sql = """ UPDATE discord_economy_userinfo SET `credit`=`credit`+%s, `farm_item_sold`=`farm_item_sold`+%s WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (total_credit, farm_item_sold, user_id,))
                    # update selected item to sold
                    sql = """ UPDATE discord_economy_farm_planting SET `sold`=%s, `sold_date`=%s WHERE `plant_id`=%s AND `user_id`=%s AND `sold`=%s AND `harvested`=%s """
                    await cur.execute(sql, ('YES', int(time.time()), plant_id, user_id, 'NO', 'YES'))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_dairy_cow_ownership(self, user_id: str):        
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_dairy_cattle_ownership WHERE `user_id`=%s """
                    await cur.execute(sql, (user_id))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_dairy_collecting(self, user_id: str, cowlist, qty_collect: float, credit_raw_milk_liter: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_dairy_collected (`user_id`, `collected_date`, `collected_qty`, `credit_per_item`) 
                              VALUES (%s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, int(time.time()), qty_collect, credit_raw_milk_liter))

                    ## add raw_milk_qty
                    sql = """ UPDATE discord_economy_userinfo SET `raw_milk_qty`=`raw_milk_qty`+%s 
                              WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (qty_collect, user_id,))

                    sql = """ UPDATE discord_economy_dairy_cattle_ownership SET `last_collect_date`=%s, `possible_collect_date`=%s, `total_produced_qty`=`total_produced_qty`+%s 
                              WHERE `user_id`=%s AND `id`=%s """
                    list_update = []
                    for each_item in cowlist:
                        list_update.append((int(time.time()), int(time.time())+config.economy.dairy_collecting_time, config.economy.raw_milk_per_cow, user_id, each_item))
                    await cur.executemany(sql, list_update)
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_dairy_collected(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_dairy_collected WHERE `user_id`=%s AND `sold`=%s """
                    await cur.execute(sql, (user_id, 'NO'))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_dairy_sell_milk(self, user_id: str, ids, credit: float, qty_sell: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    ## update raw_milk_qty
                    sql = """ UPDATE discord_economy_userinfo SET `raw_milk_qty`=`raw_milk_qty`-%s, `raw_milk_qty_sold`=`raw_milk_qty_sold`+%s, `credit`=`credit`+%s 
                              WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (qty_sell, qty_sell, credit, user_id,))
                    sql = """ UPDATE discord_economy_dairy_collected SET `sold`=%s, `sold_date`=%s 
                              WHERE `user_id`=%s AND `id`=%s AND `sold`=%s """
                    list_update = []
                    for each_item in ids:
                        list_update.append(('YES', int(time.time()), user_id, each_item, 'NO'))
                    await cur.executemany(sql, list_update)
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_chicken_farm_ownership(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_chickenfarm_ownership WHERE `user_id`=%s """
                    await cur.execute(sql, (user_id))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_egg_collecting(self, user_id: str, chickenlist, qty_collect: float, credit_egg: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO discord_economy_egg_collected (`user_id`, `collected_date`, `collected_qty`, `credit_per_item`) 
                              VALUES (%s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, int(time.time()), qty_collect, credit_egg))

                    ## add egg
                    sql = """ UPDATE discord_economy_userinfo SET `egg_qty`=`egg_qty`+%s 
                              WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (qty_collect, user_id,))

                    sql = """ UPDATE discord_economy_chickenfarm_ownership SET `last_collect_date`=%s, `possible_collect_date`=%s, `total_produced_qty`=`total_produced_qty`+%s 
                              WHERE `user_id`=%s AND `id`=%s """
                    list_update = []
                    for each_item in chickenlist:
                        list_update.append((int(time.time()), int(time.time())+config.economy.egg_collecting_time, config.economy.egg_per_chicken, user_id, each_item))
                    await cur.executemany(sql, list_update)
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def economy_egg_collected(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM discord_economy_egg_collected WHERE `user_id`=%s AND `sold`=%s """
                    await cur.execute(sql, (user_id, 'NO'))
                    result = await cur.fetchall()
                    if result: return result
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return []

    async def economy_chickenfarm_sell_egg(self, user_id: str, ids, credit: float, qty_sell: float):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    ## update egg
                    sql = """ UPDATE discord_economy_userinfo SET `egg_qty`=`egg_qty`-%s, `egg_qty_sold`=`egg_qty_sold`+%s, `credit`=`credit`+%s 
                              WHERE `user_id`=%s LIMIT 1 """
                    await cur.execute(sql, (qty_sell, qty_sell, credit, user_id,))
                    sql = """ UPDATE discord_economy_egg_collected SET `sold`=%s, `sold_date`=%s 
                              WHERE `user_id`=%s AND `id`=%s AND `sold`=%s """
                    list_update = []
                    for each_item in ids:
                        list_update.append(('YES', int(time.time()), user_id, each_item, 'NO'))
                    await cur.executemany(sql, list_update)
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None
    ## end of economy


class Economy(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        self.db = database_economy()


    async def check_guild(self, ctx):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


        if isinstance(ctx.channel, disnake.DMChannel):
            return {"error": "This command can not be DM."}
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        prefix = await get_guild_prefix(ctx)
        if serverinfo and 'enable_economy' in serverinfo and serverinfo['enable_economy'] == "NO":
            await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **{prefix}economy sell** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            return {"error": f"Economy is not available in this guild yet. Please request Guild owner to enable by `{prefix}SETTING ECONOMY`"}

        if serverinfo['economy_channel']:
            eco_channel = self.bot.get_channel(int(serverinfo['economy_channel']))
            if not eco_channel:
                return {"error": "Can not find economy channel or invalid."}
            elif ctx.channel.id != int(serverinfo['economy_channel']):
                try:
                    EcoChan = self.bot.get_channel(int(serverinfo['economy_channel']))
                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, {EcoChan.mention} is the economy channel!!!"}
                except Exception as e:
                    pass
        else:
            return  {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, There is no economy channel yet!"}

        if ctx.author.id in GAME_INTERACTIVE_ECO:
            return {"error": f"{ctx.author.mention} You are ongoing with one **game economy** play."}

        return {"result": True}


    async def eco_buy(self, ctx, item_name):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # Getting list
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo:
            if get_userinfo['fishing_bait'] >= config.economy.max_bait_per_user and (item_name.upper() == "BAIT" or item_name == "🎣"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have maximum of baits already."}
            elif get_userinfo['tree_seed'] >= config.economy.max_seed_per_user and (item_name.upper() == "SEED" or item_name == "🌱"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have maximum of seeds already."}
            elif get_userinfo['numb_farm'] >= config.economy.max_farm_per_user and (item_name.upper() == "FARM" or item_name == "👨‍🌾"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have a `farm` already."}
            elif get_userinfo['numb_chicken_farm'] >= config.economy.max_chickenfarm_per_user and (item_name.upper() == "CHICKENFARM" or item_name.upper() == "CHICKEN FARM"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have a `chicken farm` already."}
            elif get_userinfo['numb_chicken_farm'] == 0 and (item_name.upper() == "CHICKEN" or item_name == "🐔"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have a `chicken farm`."}
            elif get_userinfo['numb_chicken'] >= config.economy.max_chicken_per_user and (item_name.upper() == "CHICKEN" or item_name == "🐔"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have maximum of chicken already."}
            elif get_userinfo['numb_tractor'] >= config.economy.max_tractor_per_user and (item_name.upper() == "TRACTOR" or item_name == "🚜"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have a `tractor` already."}
            elif get_userinfo['numb_dairy_cattle'] >= config.economy.max_dairycattle_per_user and (item_name.upper() == "DAIRY CATTLE" or item_name == "DAIRYCATTLE"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have a dairy cattle already."}
            elif get_userinfo['numb_dairy_cattle'] == 0 and item_name.upper() == "COW":
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have `dairy cattle`."}
            elif get_userinfo['numb_farm'] == 0 and (item_name.upper() == "TRACTOR" or item_name == "🚜"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have a `farm`."}
            elif get_userinfo['numb_boat'] >= config.economy.max_boat_per_user and (item_name.upper() == "BOAT" or item_name == "🚣"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have a `boat` already."}
            elif get_userinfo['numb_cow'] >= config.economy.max_cow_per_user and (item_name.upper() == "COW" or item_name == "🐄"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have maximum of cows already."}
            elif get_userinfo['numb_market'] >= config.economy.max_market_per_user and (item_name.upper() == "MARKET" or item_name == "🛒"):
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have a `market` already."}
            else:
                try:
                    if item_name.upper() == "LIST":
                        # List item
                        get_shop_itemlist = await self.db.economy_shop_get_item_list()
                        if get_shop_itemlist and len(get_shop_itemlist) > 0:
                            e = disnake.Embed(title="Shop Bot".format(ctx.author.name, ctx.author.discriminator), description="Economy [Testing]", timestamp=datetime.utcnow())
                            for each_item in get_shop_itemlist:
                                remark_text = ""
                                if each_item['remark'] and len(each_item['remark']) > 0:
                                    remark_text = each_item['remark']
                                fee_str = "💵" if each_item['item_name'] != "Credit" else "💎"
                                e.add_field(name=each_item['item_name'] + " " + each_item['item_emoji'] + " Fee: {:,.2f}".format(each_item['credit_cost']) + fee_str, value="```Each: {}, Level: {}\n{}```".format(each_item['item_numbers'], each_item['limit_level'] if each_item['limit_level']>0 else 1, remark_text), inline=False)
                            e.set_footer(text=f"User {ctx.author.name}#{ctx.author.discriminator}")
                            e.set_thumbnail(url=ctx.author.display_avatar)
                            msg = await ctx.reply(embed=e)
                            return {"result": True} ## True: No need to reply after call this function
                        else:
                            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} there is no item in our shop."}
                    elif item_name.upper() == "CREDIT":
                        # Using gem instead of credit
                        get_shop_item = await self.db.economy_shop_get_item(item_name)
                        get_inventory_from_backpack = await self.db.economy_get_user_inventory(str(ctx.author.id), 'Gem')
                        if len(get_inventory_from_backpack) > 0 and 'numbers' in get_inventory_from_backpack:
                            get_userinfo['gem_credit'] += get_inventory_from_backpack['numbers'] 
                        if get_shop_item:
                            level = int((get_userinfo['exp']-10)**0.5) + 1
                            needed_level = get_shop_item['limit_level']
                            if get_userinfo['gem_credit'] <= 0 or get_userinfo['gem_credit'] < get_shop_item['credit_cost']:
                                user_credit = get_userinfo['gem_credit']
                                need_credit = get_shop_item['credit_cost']
                                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have sufficient gem. Having only `{user_credit}`. Need `{need_credit}`."}
                            elif level < get_shop_item['limit_level']:
                                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Your level `{level}` is still low. Needed level `{str(needed_level)}`."}
                            else:
                                if ctx.author.id not in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.append(ctx.author.id)
                                # Make order
                                add_item_numbers = get_shop_item['item_numbers']
                                update_item = await store.discord_economy_userinfo_what(str(ctx.guild.id), str(ctx.author.id), get_shop_item['id'], item_name, 0, add_item_numbers)
                                if update_item:
                                    item_desc = get_shop_item['item_name'] + " " + get_shop_item['item_emoji'] + " x" + str(add_item_numbers)
                                    return {"result": f"{ctx.author.mention}, {EMOJI_INFORMATION} You successfully purchased {item_desc}."}
                        else:
                            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} item `{item_name}` is not available."}
                    else:
                        # Check if enough credit
                        # 1) Check price
                        get_shop_item = await self.db.economy_shop_get_item(item_name)
                        if get_shop_item:
                            level = int((get_userinfo['exp']-10)**0.5) + 1
                            needed_level = get_shop_item['limit_level']
                            your_fishing_exp = get_userinfo['fishing_exp']
                            need_fishing_exp = get_shop_item['fishing_exp']
                            if get_userinfo['credit'] < get_shop_item['credit_cost']:
                                user_credit = "{:,.2f}".format(get_userinfo['credit'])
                                need_credit = "{:,.2f}".format(get_shop_item['credit_cost'])
                                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have sufficient credit. Having only `{user_credit}`. Need `{need_credit}`."}
                            elif level < get_shop_item['limit_level']:
                                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Your level `{level}`  is still low. Needed level `{str(needed_level)}`."}
                            elif need_fishing_exp > 0 and your_fishing_exp <  need_fishing_exp:
                                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Your fishing exp `{your_fishing_exp}`  is still low. Needed fishing exp `{str(need_fishing_exp)}`."}
                            else:
                                if ctx.author.id not in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.append(ctx.author.id)
                                # Make order
                                add_item_numbers = get_shop_item['item_numbers']
                                if (item_name.upper() == "BAIT" or item_name == "🎣") and get_userinfo['fishing_bait'] + add_item_numbers > config.economy.max_bait_per_user:
                                    add_item_numbers = config.economy.max_bait_per_user - get_userinfo['fishing_bait']
                                elif (item_name.upper() == "SEED" or item_name == "🌱") and get_userinfo['tree_seed'] + add_item_numbers > config.economy.max_seed_per_user:
                                    add_item_numbers = config.economy.max_seed_per_user - get_userinfo['tree_seed']
                                update_item = None
                                try:
                                    update_item = await store.discord_economy_userinfo_what(str(ctx.guild.id), str(ctx.author.id), get_shop_item['id'], item_name, add_item_numbers, -get_shop_item['credit_cost'])
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot(traceback.format_exc())
                                item_desc = get_shop_item['item_name'] + " " + get_shop_item['item_emoji'] + " x" + str(add_item_numbers)
                                if update_item:
                                    return {"result": f"{ctx.author.mention}, {EMOJI_INFORMATION} You successfully purchased {item_desc}."}
                                else:
                                    return {"error": f"{ctx.author.mention}, {EMOJI_INFORMATION} internal error {item_desc}."}
                        else:
                            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} item `{item_name}` is not available."}
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)
        else:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Internal error."}


    async def eco_sell(self, ctx, item_name):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # Getting list of work in the guild and re-act
        market_factored = 1.0
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo and get_userinfo['numb_market'] >= 1:
            market_factored = config.economy.market_price_factor

        try:
            get_fish_inventory_list = await self.db.economy_get_list_fish_caught(str(ctx.author.id), sold='NO', caught='YES')
            get_user_harvested_crops = await self.db.economy_farm_user_planting_group_harvested(str(ctx.author.id))
            get_fish_inventory_list_arr = [each_item['fish_name'].upper() for each_item in get_fish_inventory_list]
            get_user_harvested_crops_arr = [each_item['plant_name'].upper() for each_item in get_user_harvested_crops]
            if item_name.strip().upper() in get_fish_inventory_list_arr:
                # Selling Fishes
                if len(get_fish_inventory_list) > 0:
                    selected_fishes = None
                    for each_item in get_fish_inventory_list:
                        if item_name.strip().upper() == each_item['fish_name'].upper() or item_name.strip() == each_item['fish_emoji']:
                            selected_fishes = each_item
                            break
                    if selected_fishes is None:
                        return  {"error": f"{ctx.author.mention} You do not have `{item_name}` to sell."}
                    else:
                        # Have that item to sell
                        if selected_fishes['Weights'] < selected_fishes['minimum_sell_kg']:
                            return  {"error": "{} You do not have sufficient {} to sell. Minimum {:,.2f}kg, having {:,.2f}kg.".format(ctx.author.mention, item_name, selected_fishes['minimum_sell_kg'], selected_fishes['Weights'])}
                        else:
                            # Enough to sell. Update credit, and mark fish as sold
                            # We round credit earning
                            if ctx.author.id not in GAME_INTERACTIVE_ECO:
                                GAME_INTERACTIVE_ECO.append(ctx.author.id)
                            total_earn = int(float(selected_fishes['Weights']) * float(selected_fishes['credit_per_kg']) * market_factored)
                            total_weight = float(selected_fishes['Weights'])
                            get_userinfo['credit'] += total_earn
                            selling_fishes = await self.db.economy_sell_fishes(selected_fishes['fish_id'], str(ctx.author.id), str(ctx.guild.id), total_weight, total_earn)
                            if selling_fishes:
                                return  {"result": "You sold {:,.2f}kg of {} for `{}` Credit(s) (`{:,.2f} Credit per kg`). Your credit now is: `{:,.2f}`.".format(total_weight, item_name, total_earn, float(selected_fishes['credit_per_kg']) * market_factored, get_userinfo['credit']), "market_factored": market_factored}
                            else:
                                return {"error": f"{ctx.author.mention} Internal error."}
                else:
                    return {"error": f"{ctx.author.name}#{ctx.author.discriminator}, You do not have any fish to sell. Do fishing!"}
            elif item_name.strip().upper() in get_user_harvested_crops_arr:
                # Selling vegetable in farm
                if len(get_user_harvested_crops) > 0:
                    selected_item = None
                    for each_item in get_user_harvested_crops:
                        if item_name.strip().upper() == each_item['plant_name'].upper() or item_name.strip() == each_item['plant_emoji']:
                            selected_item = each_item
                            break
                    if selected_item is None:
                        return {"error": f"{ctx.author.mention} You do not have `{item_name}` to sell."}
                    else:
                        # No minimum to sell
                        # Enough to sell. Update credit, and mark fish as sold
                        # We round credit earning
                        if ctx.author.id not in GAME_INTERACTIVE_ECO:
                            GAME_INTERACTIVE_ECO.append(ctx.author.id)
                        total_earn = int(float(selected_item['total_products']) * float(selected_item['credit_per_item']) * market_factored)
                        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
                        get_userinfo['credit'] += total_earn
                        selling_item = await self.db.economy_farm_sell_item(selected_item['plant_id'], str(ctx.author.id), str(ctx.guild.id), total_earn, selected_item['total_products'])
                        if selling_item:
                            return  {"result": "You sold {:,.0f} of {} for `{}` Credit(s) (`{:,.2f} Credit per one`). Your credit now is: `{:,.2f}`.".format(selected_item['total_products'], item_name, total_earn, float(selected_item['credit_per_item']) * market_factored, get_userinfo['credit']), "market_factored": market_factored}
                        else:
                            return {"error": f"{ctx.author.mention} Internal error."}
                else:
                    return {"error": f"{ctx.author.name}#{ctx.author.discriminator}, You do not have any vegetable or fruit to sell. Plant and harvest!"}
            elif item_name.strip().upper() == "MILK":
                # Selling milk
                try:
                    get_raw_milk = await self.db.economy_dairy_collected(str(ctx.author.id))
                    ids = []
                    qty_raw_milk = 0.0
                    credit_sell = 0.0
                    if get_raw_milk and len(get_raw_milk) > 0:
                        for each in get_raw_milk:
                            ids.append(each['id'])
                            qty_raw_milk += float(each['collected_qty'])
                            credit_sell += float(each['collected_qty']) * float(each['credit_per_item']) * market_factored
                        if qty_raw_milk > 0:
                            # has milk, sell all
                            sell_milk = await self.db.economy_dairy_sell_milk(str(ctx.author.id), ids, credit_sell, qty_raw_milk)
                            if sell_milk:
                                get_userinfo['credit'] = float(get_userinfo['credit']) + float(credit_sell)
                                return {"result": "You sold {:,.2f} liter(s) of milk for `{:,.2f}` Credit(s). Your credit now is: `{:,.2f}`.".format(qty_raw_milk, credit_sell, get_userinfo['credit']), "market_factored": market_factored}
                        else:
                            return {"error": f"{ctx.author.name}#{ctx.author.discriminator}, You do not have milk to sell!!"}
                    else:
                        return {"error": f"{ctx.author.name}#{ctx.author.discriminator}, You do not have milk to sell!"}
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            elif item_name.strip().upper() == "EGG":
                # Selling egg
                try:
                    get_eggs = await self.db.economy_egg_collected(str(ctx.author.id))
                    ids = []
                    qty_eggs = 0.0
                    credit_sell = 0.0
                    if get_eggs and len(get_eggs) > 0:
                        for each in get_eggs:
                            ids.append(each['id'])
                            qty_eggs += float(each['collected_qty'])
                            credit_sell += float(each['collected_qty']) * float(each['credit_per_item']) * market_factored
                        if qty_eggs > 0:
                            # has milk, sell all
                            sell_milk = await self.db.economy_chickenfarm_sell_egg(str(ctx.author.id), ids, credit_sell, qty_eggs)
                            if sell_milk:
                                get_userinfo['credit'] = float(get_userinfo['credit']) + float(credit_sell)
                                return {"result": "You sold {:,.0f} chicken egg(s) for `{:,.2f}` Credit(s). Your credit now is: `{:,.2f}`.".format(qty_eggs, credit_sell, get_userinfo['credit']), "market_factored": market_factored}
                        else:
                            return {"error": f"{ctx.author.name}#{ctx.author.discriminator}, You do not have chicken egg(s) to sell!!"}
                    else:
                        return {"error": f"{ctx.author.name}#{ctx.author.discriminator}, You do not have chicken egg(s) to sell!"}
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            else:
                return {"error": f"{ctx.author.name}#{ctx.author.discriminator}, not valid to sell `{item_name}` or you do not have it!"}
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.author.id in GAME_INTERACTIVE_ECO:
            GAME_INTERACTIVE_ECO.remove(ctx.author.id)
        return


    async def eco_info(self, ctx, member):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # Get all available work in the guild
        get_worklist = await self.db.economy_get_guild_worklist(str(ctx.guild.id), True)
        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(member.id), '{}#{}'.format(member.name, member.discriminator))
        if get_userinfo:
            count_eating_record = await self.db.economy_get_guild_eating_list_record(str(ctx.guild.id), 12*3600)
            if count_eating_record is None:
                count_eating_record = []
            allowed_eating_session = int(config.economy.max_guild_food*len(ctx.guild.members))
            try:
                get_inventory_from_backpack = await self.db.economy_get_user_inventory(str(member.id), 'Gem')
                if get_inventory_from_backpack and 'numbers' in get_inventory_from_backpack:
                    get_userinfo['gem_credit'] += get_inventory_from_backpack['numbers']
                embed = disnake.Embed(title="{}#{} - Credit {:,.2f}{}/ Gem: {:,.0f}{}".format(member.name, member.discriminator, get_userinfo['credit'], '💵', get_userinfo['gem_credit'], '💎'), description="Economy [Testing]")
                embed.add_field(name="Health: {0:.2f}%".format(get_userinfo['health_current']/get_userinfo['health_total']*100), value='```{}```'.format(createBox(get_userinfo['health_current'], get_userinfo['health_total'], 20)), inline=False)
                embed.add_field(name="Energy: {0:.2f}%".format(get_userinfo['energy_current']/get_userinfo['energy_total']*100), value='```{}```'.format(createBox(get_userinfo['energy_current'], get_userinfo['energy_total'], 20)), inline=False)
                if get_userinfo['exp'] > 0:
                    level = int((get_userinfo['exp']-10)**0.5) + 1
                    next_level_exp = level**2 + 10
                    current_level_exp = (level-1)**2 + 10
                    embed.add_field(name="Level / Exp: {} / {:,.0f}".format(level, get_userinfo['exp']), value='```{} [{:,.0f}/{:,.0f}]```'.format(createBox(get_userinfo['exp']-current_level_exp, next_level_exp-current_level_exp, 20), get_userinfo['exp']-current_level_exp, next_level_exp-current_level_exp), inline=False)
                try:
                    get_activities_user_1w = await self.db.economy_get_user_activities_duration(str(ctx.author.id), 7*24*3600)
                    embed.add_field(name="Last 1 week works", value=len(get_activities_user_1w), inline=True)
                except:
                    traceback.print_exc(file=sys.stdout)
                # Get user inventory
                get_user_inventory = await self.db.economy_get_user_inventory(str(member.id))
                nos_items = sum(each_item['numbers'] for each_item in get_user_inventory if each_item['item_name'] != "Gem")
                items_str = ''.join([each_item['item_emoji'] for each_item in get_user_inventory]) if len(get_user_inventory) > 0 else ''
                embed.add_field(name="Backpack", value='{}/{} {}'.format(nos_items, config.economy.max_backpack_items, items_str), inline=True)
                embed.add_field(name="Fishing Bait", value='{}/{}'.format(get_userinfo['fishing_bait'], config.economy.max_bait_per_user), inline=True)
                embed.add_field(name="Fishing Exp", value='{:,.0f}'.format(get_userinfo['fishing_exp']), inline=True)
                embed.add_field(name="Seed - Planted/Cut", value='{}/{} - {}/{}'.format(get_userinfo['tree_seed'], config.economy.max_seed_per_user, get_userinfo['tree_planted'], get_userinfo['tree_cut']), inline=True)
                try:
                    get_last_act = await self.db.economy_get_last_activities(str(member.id), False)
                    if get_last_act:
                        get_work_id = await self.db.economy_get_workd_id(get_last_act['work_id'])
                    if get_last_act:
                        work_status = ''
                        if get_last_act['status'] == 'ONGOING':
                            work_status = 'Current work'
                        else:
                            work_status = 'Completed work'
                        embed.add_field(name=work_status, value=get_work_id['work_name'], inline=True)
                        if get_last_act['status'] == 'ONGOING':
                            remaining_duration =  get_last_act['started'] + get_last_act['duration_in_second'] - int(time.time())
                            if remaining_duration < 0: remaining_duration = 0
                            embed.add_field(name='Can claim in', value=seconds_str(remaining_duration), inline=True)
                    else:
                        embed.add_field(name='Work', value='N/A', inline=True)
                except:
                    traceback.print_exc(file=sys.stdout)
                embed.add_field(name="Guild's food quota 12h", value='{}/{}'.format(len(count_eating_record), allowed_eating_session), inline=True)
                embed.add_field(name="Guild's population", value='{}*'.format(len(ctx.guild.members)), inline=True)
                embed.set_thumbnail(url=member.display_avatar)
                embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                await ctx.reply(embed=embed)
            except:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
                error = disnake.Embed(title=":exclamation: Error", description=" :warning: You need to mention the user you want this info for!", color=0xe51e1e)
                await ctx.reply(embed=error)
        else:
            await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error.')
        return {"result": True} ## True: No need to reply after call this function


    async def eco_items(self, ctx):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        
        # Get user inventory
        get_user_inventory = await self.db.economy_get_user_inventory(str(ctx.author.id))
        nos_items = sum(each_item['numbers'] for each_item in get_user_inventory if each_item['item_name'] != "Gem")
        if get_user_inventory and nos_items == 0:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have any item in your backpack."}
        elif get_user_inventory and len(get_user_inventory) > 0:
            # list all of them
            try:
                if ctx.author.id not in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.append(ctx.author.id)
                    # Add work if he needs to do
                    e = disnake.Embed(title="{}#{} Item in backpack".format(ctx.author.name, ctx.author.discriminator), description="Economy [Testing]", timestamp=datetime.utcnow())
                    all_item_backpack = {}
                    if get_user_inventory and len(get_user_inventory) > 0:
                        for each_item in get_user_inventory:
                            if each_item['item_health'] > 0:
                                e.add_field(name=each_item['item_name'] + " " + each_item['item_emoji'] + "x" +str(each_item['numbers']), value="```Health: {}```".format(each_item['item_health']), inline=False)
                                all_item_backpack[str(each_item['item_emoji'])] = each_item['item_id']
                            if each_item['item_energy'] > 0:
                                e.add_field(name=each_item['item_name'] + " " + each_item['item_emoji'] + "x" +str(each_item['numbers']), value="```Energy: {}```".format(each_item['item_energy']), inline=False)
                                all_item_backpack[str(each_item['item_emoji'])] = each_item['item_id']
                            if each_item['item_gem'] > 0:
                                pass
                                #e.add_field(name=each_item['item_name'] + " " + each_item['item_emoji'] + "x" +str(each_item['numbers']), value="```Gem: {}```".format(each_item['item_gem']), inline=False)
                        e.set_footer(text=f"User {ctx.author.name}#{ctx.author.discriminator}")
                        e.set_thumbnail(url=ctx.author.display_avatar)
                        msg = await ctx.reply(embed=e)
                        for key, value in all_item_backpack.items():
                            await msg.add_reaction(key)
                        await msg.add_reaction(EMOJI_OK_BOX)

                        def check(reaction, user):
                            return user == ctx.author and reaction.message.author == self.bot.user and reaction.message.id == msg.id
                        while True:
                            try:
                                reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=check)
                            except asyncio.TimeoutError:
                                if ctx.author.id in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                try:
                                    await msg.delete()
                                except Exception as e:
                                    pass
                                break
                                return
                            if reaction.emoji and str(reaction.emoji) in all_item_backpack:
                                try:
                                    get_item_id = await self.db.economy_get_item_id(all_item_backpack[str(reaction.emoji)])
                                    # Else, go on and Insert work to DB
                                    add_energy = 0
                                    add_energy_health_str = ""
                                    if get_item_id['item_energy'] > 0:
                                        add_energy = get_item_id['item_energy']
                                        if get_userinfo['energy_current'] + add_energy > get_userinfo['energy_total']:
                                            add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                                        add_energy_health_str = "{} energy".format(add_energy)
                                        total_energy = get_userinfo['energy_current'] + add_energy
                                        total_energy_health_str = f"You have total `{total_energy}` energy."
                                    add_health = 0
                                    if get_item_id['item_health'] > 0:
                                        add_health = get_item_id['item_health']
                                        if get_userinfo['health_current'] + add_health > get_userinfo['health_total']:
                                            add_health = get_userinfo['health_total'] - get_userinfo['health_current']
                                        add_energy_health_str = "{} health".format(add_health)
                                        total_health = get_userinfo['health_current'] + add_health
                                        total_energy_health_str = f"You have total `{total_health}` health."
                                    # Update userinfo
                                    update_userinfo = await self.db.economy_item_update_used(str(ctx.author.id), all_item_backpack[str(reaction.emoji)], add_energy, add_health)
                                    using_item = '{} {}'.format(get_item_id['item_name'], get_item_id['item_emoji'])
                                    if update_userinfo:
                                        await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} You used `{using_item}`. You gained `{add_energy_health_str}`. {total_energy_health_str}')
                                        await msg.delete()
                                    else:
                                        return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Internal error."}
                                    if ctx.author.id in GAME_INTERACTIVE_ECO:
                                        GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                    break
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            elif str(reaction.emoji) == EMOJI_OK_BOX:
                                if ctx.author.id in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                return {"result": True} ## True: No need to reply after call this function
                    else:
                        if ctx.author.id in GAME_INTERACTIVE_ECO:
                            GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                        return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have anything in your backpack."}
            except Exception as e:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                traceback.print_exc(file=sys.stdout)
        else:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have anything in your backpack."}


    async def eco_lumber(self, ctx, member):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        try:
            get_lumber_inventory = await self.db.economy_get_timber_user(str(member.id), sold_timber='NO', sold_leaf='NO')
            if len(get_lumber_inventory) > 0:
                e = disnake.Embed(title="{}#{} Lumber/Leaf".format(member.name, member.discriminator), description="Economy [Testing]", timestamp=datetime.utcnow())
                e.add_field(name="Timber / Leaf", value="{:,.2f}m3 / {:,.2f}kg".format(get_lumber_inventory['timber_vol'], get_lumber_inventory['leaf_kg']), inline=False)
                e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                e.set_thumbnail(url=member.display_avatar)
                msg = await ctx.reply(embed=e)
                await msg.add_reaction(EMOJI_OK_BOX)
            else:
                return {"error": f"{member.name}#{member.discriminator}, not having timber/leaves!"}
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def eco_fish(self, ctx, member):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        try:
            get_fish_inventory_list = await self.db.economy_get_list_fish_caught(str(member.id), sold='NO', caught='YES')
            if len(get_fish_inventory_list) > 0:
                e = disnake.Embed(title="{}#{} Fishes".format(member.name, member.discriminator), description="Economy [Testing]", timestamp=datetime.utcnow())
                fishes_lists = ""
                for each_item in get_fish_inventory_list:
                    fishes_lists += each_item['fish_name'] + " " + each_item['fish_emoji'] + " x" +str(each_item['numbers']) + "={:,.2f}kg".format(each_item['Weights']) + "\n"
                total_weight = sum(each_item['Weights'] for each_item in get_fish_inventory_list)
                e.add_field(name="Fishes ({:,.2f}kg)".format(total_weight), value=fishes_lists, inline=False)
                e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                e.set_thumbnail(url=member.display_avatar)
                msg = await ctx.reply(embed=e)
                await msg.add_reaction(EMOJI_OK_BOX)
            else:
                return  {"error": f"{member.name}#{member.discriminator}, not having fish!"}
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def eco_plant(self, ctx, plant_name):
        prefix = await get_guild_prefix(ctx)
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # get farm plant list
        plant_list_arr = await self.db.economy_farm_get_list_plants()
        plant_list_names = [name['plant_name'].lower() for name in plant_list_arr]

        if plant_name and plant_name.upper() == "LIST":
            e = disnake.Embed(title="Plant List", description="Economy [Testing]", timestamp=datetime.utcnow())
            for each_crop in plant_list_arr:
                e.add_field(name=each_crop['plant_name'] + " " + each_crop['plant_emoji'] + " Dur. : {}".format(seconds_str(each_crop['duration_harvest'])), value="Harvested: {} | Credit: {}".format(each_crop['number_of_item'], each_crop['credit_per_item']*each_crop['number_of_item']), inline=False)
            e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
            e.set_thumbnail(url=ctx.author.display_avatar)
            msg = await ctx.reply(embed=e)
            await msg.add_reaction(EMOJI_OK_BOX)
            return
            
        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo and get_userinfo['tree_seed'] <= 0:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have any seed. Please buy `{prefix}eco buy seed`."}

        if get_userinfo['numb_farm'] == 0 and plant_name != "TREE":
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have any farm."}
        
        try:
            has_tractor = False
            will_plant = 1
            if get_userinfo['numb_tractor'] >= 1:
                has_tractor = True
                will_plant = config.economy.max_tractor_can_plant
                if get_userinfo['tree_seed'] < will_plant:
                    will_plant = get_userinfo['tree_seed']
            check_planting_nos = await self.db.economy_farm_user_planting_check_max(str(ctx.author.id))
            if check_planting_nos + will_plant > config.economy.max_farm_plant_per_user and has_tractor == True:
                will_plant = config.economy.max_farm_plant_per_user - check_planting_nos
            # If health less than 50%, stop
            if get_userinfo['health_current']/get_userinfo['health_total'] < 0.5:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Your health is having issue. Do some heatlh check."}
            # If energy less than 20%, stop
            if get_userinfo['energy_current']/get_userinfo['energy_total'] < 0.2:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have very small energy. Eat to powerup."}

            if ctx.author.id in GAME_INTERACTIVE_ECO:
                return {"error": f"{ctx.author.mention} You are ongoing with one **game economy** play."}
            else:
                GAME_INTERACTIVE_ECO.append(ctx.author.id)

            if plant_name not in plant_list_names and plant_name != "TREE":
                plant_name_str = ", ".join(plant_list_names)
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} They are not available. Please use any of this `{plant_name_str}`."}
            # TODO: check if user already has max planted
            
            if check_planting_nos >= config.economy.max_farm_plant_per_user and plant_name != "TREE":
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You planted maximum number of crops already."}
            elif plant_name == "TREE":
                await asyncio.sleep(1.0)
                exp_gained = config.economy.plant_exp_gained
                energy_loss = exp_gained * 2
                insert_item = await self.db.economy_insert_planting(str(ctx.author.id), str(ctx.guild.id), exp_gained, energy_loss)
                if insert_item:
                    msg = await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} Nice! You have planted a tree. You gained `{str(exp_gained)}` planting experience and spent `{str(energy_loss)}` energy.')
            else:
                # Not tree and not max, let's plant
                # Using tractor, loss same energy but gain more experience
                if has_tractor and type(ctx) is not disnake.interactions.app_command_interaction.SlashInteraction:
                    await ctx.message.add_reaction("🚜")
                elif not has_tractor and type(ctx) is not disnake.interactions.app_command_interaction.SlashInteraction:
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                await asyncio.sleep(1.0)
                exp_gained = config.economy.plant_exp_gained
                energy_loss = exp_gained * 2
                selected_crop = None
                for each_item in plant_list_arr:
                    if plant_name.upper() == each_item['plant_name'].upper() or plant_name == each_item['plant_emoji']:
                        selected_crop = each_item
                        break
                crop_name = "`" + selected_crop['plant_name'] + "` " + selected_crop['plant_emoji']
                insert_item = await self.db.economy_farm_insert_crop(selected_crop['id'], str(ctx.author.id), str(ctx.guild.id), 
                                                                   selected_crop['duration_harvest']+int(time.time()), selected_crop['number_of_item'],
                                                                   selected_crop['credit_per_item'], exp_gained, energy_loss, will_plant)
                if insert_item:
                    msg = await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} Nice! You have planted `{will_plant}` {crop_name} in your farm. '
                                          f'You gained `{str(exp_gained*will_plant)}` planting experience and spent `{str(energy_loss)}` energy. '
                                          f'You have {str(check_planting_nos+will_plant)} crop(s) in your farm now.')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.author.id in GAME_INTERACTIVE_ECO:
            GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    async def eco_collect(self, ctx, what):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if what == "MILK" and get_userinfo and get_userinfo['numb_dairy_cattle'] == 0:
            return {"error": f"{ctx.author.mention}, Not having any dairy cattle."}
        elif what == "MILK" and get_userinfo and get_userinfo['numb_cow'] == 0:
            return {"error": f"{ctx.author.mention}, You do not have any cow."}
        elif what == "EGG" and get_userinfo and get_userinfo['numb_chicken_farm'] == 0:
            return {"error": f"{ctx.author.mention}, Not having any chicken farm."}
        elif what == "EGG" and get_userinfo and get_userinfo['numb_chicken'] == 0:
            return {"error": f"{ctx.author.mention}, You do not have any chicken."}
        elif what == "MILK":
            try:
                if ctx.author.id not in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.append(ctx.author.id)
                total_can_collect = 0
                qty_collect = 0.0
                get_cows = await self.db.economy_dairy_cow_ownership(str(ctx.author.id))
                id_collecting = []
                if get_cows and len(get_cows) > 0:
                    for each_cow in get_cows:
                        if each_cow['possible_collect_date'] < int(time.time()):
                            total_can_collect += 1
                            qty_collect += config.economy.raw_milk_per_cow
                            id_collecting.append(each_cow['id'])
                    if total_can_collect > 0:
                        insert_collecting = await self.db.economy_dairy_collecting(str(ctx.author.id), id_collecting, qty_collect, config.economy.credit_raw_milk_liter)
                        if insert_collecting:
                            msg = await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} Nice! You have collected `{qty_collect}` '
                                                  f'liters of milk from `{total_can_collect}` cow(s).')
                    else:
                        return {"error": f"{ctx.author.mention}, You need to wait a bit longer. It\'s not time yet."}
                else:
                    return {"error": f"{ctx.author.mention}, You do not have any cow."}
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        elif what == "EGG":
            try:
                if ctx.author.id not in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.append(ctx.author.id)
                total_can_collect = 0
                qty_collect = 0.0
                get_chickens = await self.db.economy_chicken_farm_ownership(str(ctx.author.id))
                id_collecting = []
                if get_chickens and len(get_chickens) > 0:
                    for each_chicken in get_chickens:
                        if each_chicken['possible_collect_date'] < int(time.time()):
                            total_can_collect += 1
                            qty_collect += config.economy.egg_per_chicken
                            id_collecting.append(each_chicken['id'])
                    if total_can_collect > 0:
                        insert_collecting = await self.db.economy_egg_collecting(str(ctx.author.id), id_collecting, qty_collect, config.economy.credit_egg)
                        if insert_collecting:
                            msg = await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} Nice! You have collected `{qty_collect}` '
                                                  f'egg(s) from `{total_can_collect}` chicken(s).')
                    else:
                        return {"error": f"{ctx.author.mention},You need to wait a bit longer. It\'s not time yet."}
                else:
                    return {"error": f"{ctx.author.mention}, You do not have any chicken."}
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            return {"error": f"{ctx.author.mention}, Sorry `{what}` is not available."}
        if ctx.author.id in GAME_INTERACTIVE_ECO:
            GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    async def eco_dairy(self, ctx, member):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(member.id), '{}#{}'.format(member.name, member.discriminator))
        if get_userinfo and get_userinfo['numb_dairy_cattle'] == 0:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, {member.name}#{member.discriminator} Not having any dairy cattle."}
        else:
            try:
                # Farm list
                fence_left = "❎"
                soil = "🟫"
                fence_right = "❎"
                fence_h = "❎"
                cattle = ""
                can_collect = []
                total_can_collect = 0
                can_harvest_string = "None"
                cow_emoji = "🐄"
                # Get all item in farms
                get_cows = await self.db.economy_dairy_cow_ownership(str(member.id))
                if get_cows and len(get_cows) > 0:
                    cows_array_emoji = [cow_emoji]*len(get_cows)
                    if len(cows_array_emoji) < config.economy.max_cow_per_user:
                        cows_array_emoji = cows_array_emoji + [soil]*(config.economy.max_cow_per_user - len(cows_array_emoji))
                    i=1
                    for each_cow in cows_array_emoji:
                        if (i-1) % 6 == 0:
                            cattle += f"{fence_left}"
                            cattle += f"{each_cow}"
                        elif i > 0 and i % 6 == 0:
                            cattle += f"{each_cow}"
                            cattle += f"{fence_right}\n"
                        else:
                            cattle += f"{each_cow}"
                        i += 1
                    cattle = f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n" + cattle
                    cattle += f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n"
                    for each_cow in get_cows:
                        if each_cow['possible_collect_date'] < int(time.time()):
                            if "{}".format(cow_emoji) not in can_collect:
                                can_collect.append("{}".format(cow_emoji))
                            total_can_collect += 1
                    if total_can_collect > 0:
                        can_harvest_string = "\n".join(can_collect)
                else:
                    # Empty cattle
                    cows_array_emoji = [soil]*(config.economy.max_cow_per_user)
                    i=1
                    for each_cow in cows_array_emoji:
                        if (i-1) % 6 == 0:
                            cattle += f"{fence_left}"
                            cattle += f"{each_cow}"
                        elif i > 0 and i % 6 == 0:
                            cattle += f"{each_cow}"
                            cattle += f"{fence_right}\n"
                        else:
                            cattle += f"{each_cow}"
                        i += 1
                    cattle = f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n" + cattle
                    cattle += f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n"

                e = disnake.Embed(title="{}#{} Dairy Cattle".format(member.name, member.discriminator), description="Economy [Testing]", timestamp=datetime.utcnow())
                e.add_field(name="Dairy Cattle View", value=cattle, inline=False)
                if total_can_collect > 0:
                    e.add_field(name="Can Collect: {}".format(total_can_collect), value=can_harvest_string, inline=False)
                try:
                    get_raw_milk = await self.db.economy_dairy_collected(str(member.id))
                    if get_raw_milk and len(get_raw_milk) > 0:
                        qty_raw_milk = sum(each['collected_qty'] for each in get_raw_milk)
                        e.add_field(name="Raw Milk Available", value=cow_emoji + " x" +str(len(get_raw_milk)) + "={:,.2f}".format(qty_raw_milk), inline=False)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                e.set_thumbnail(url=member.display_avatar)
                msg = await ctx.reply(embed=e)
                await msg.add_reaction(EMOJI_OK_BOX)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())


    async def eco_chicken(self, ctx, member):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(member.id), '{}#{}'.format(member.name, member.discriminator))
        if get_userinfo and get_userinfo['numb_chicken_farm'] == 0:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, {member.name}#{member.discriminator} Not having a chicken farm."}
        else:
            try:
                # Farm list
                fence_left = "❎"
                soil = "🟫"
                fence_right = "❎"
                fence_h = "❎"
                cattle = ""
                can_collect = []
                total_can_collect = 0
                can_harvest_string = "None"
                chicken_emoji = "🐔"
                # Get all item in farms
                get_chickens = await self.db.economy_chicken_farm_ownership(str(member.id))
                if get_chickens and len(get_chickens) > 0:
                    chickens_array_emoji = [chicken_emoji]*len(get_chickens)
                    if len(chickens_array_emoji) < config.economy.max_chicken_per_user:
                        chickens_array_emoji = chickens_array_emoji + [soil]*(config.economy.max_chicken_per_user - len(chickens_array_emoji))
                    i=1
                    for each_chicken in chickens_array_emoji:
                        if (i-1) % 9 == 0:
                            cattle += f"{fence_left}"
                            cattle += f"{each_chicken}"
                        elif i > 0 and i % 9 == 0:
                            cattle += f"{each_chicken}"
                            cattle += f"{fence_right}\n"
                        else:
                            cattle += f"{each_chicken}"
                        i += 1
                    cattle = f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n" + cattle
                    cattle += f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n"
                    for each_chicken in get_chickens:
                        if each_chicken['possible_collect_date'] < int(time.time()):
                            if "{}".format(chicken_emoji) not in can_collect:
                                can_collect.append("{}".format(chicken_emoji))
                            total_can_collect += 1
                    if total_can_collect > 0:
                        can_harvest_string = "\n".join(can_collect)
                else:
                    # Empty cattle
                    chickens_array_emoji = [soil]*(config.economy.max_chicken_per_user)
                    i=1
                    for each_chicken in chickens_array_emoji:
                        if (i-1) % 9 == 0:
                            cattle += f"{fence_left}"
                            cattle += f"{each_chicken}"
                        elif i > 0 and i % 9 == 0:
                            cattle += f"{each_chicken}"
                            cattle += f"{fence_right}\n"
                        else:
                            cattle += f"{each_chicken}"
                        i += 1
                    cattle = f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n" + cattle
                    cattle += f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n"

                e = disnake.Embed(title="{}#{} Chicken Farm".format(member.name, member.discriminator), description="Economy [Testing]", timestamp=datetime.utcnow())
                e.add_field(name="Chicken Farm View", value=cattle, inline=False)
                if total_can_collect > 0:
                    e.add_field(name="Chicken Can Collect: {}".format(total_can_collect), value=can_harvest_string, inline=False)
                try:
                    get_eggs = await self.db.economy_egg_collected(str(member.id))
                    if get_eggs and len(get_eggs) > 0:
                        qty_eggs = sum(each['collected_qty'] for each in get_eggs)
                        e.add_field(name="Egg Available", value=chicken_emoji + " x" +str(len(get_eggs)) + "={:,.0f}".format(qty_eggs), inline=False)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                e.set_thumbnail(url=member.display_avatar)
                msg = await ctx.reply(embed=e)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())


    async def eco_farm(self, ctx, member):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(member.id), '{}#{}'.format(member.name, member.discriminator))
        if get_userinfo and get_userinfo['numb_farm'] == 0:
             return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, {member.name}#{member.discriminator} not having any farm."}
        else:
            try:
                # Farm list
                fence_left = "❎"
                soil = "🟫"
                fence_right = "❎"
                fence_h = "❎"
                farm = ""
                can_harvest = []
                total_can_harvest = 0
                can_harvest_string = "None"
                # Get all item in farms
                get_user_crops = await self.db.economy_farm_user_planting_nogroup(str(member.id))
                if get_user_crops and len(get_user_crops) > 0:
                    crop_array_emoji = [each_item['plant_emoji'] for each_item in get_user_crops]
                    if len(crop_array_emoji) < config.economy.max_farm_plant_per_user:
                        crop_array_emoji = crop_array_emoji + [soil]*(config.economy.max_farm_plant_per_user - len(crop_array_emoji))
                    i=1
                    for each_crop in crop_array_emoji:
                        if (i-1) % 9 == 0:
                            farm += f"{fence_left}"
                            farm += f"{each_crop}"
                        elif i > 0 and i % 9 == 0:
                            farm += f"{each_crop}"
                            farm += f"{fence_right}\n"
                        else:
                            farm += f"{each_crop}"
                        i += 1
                    farm = f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n" + farm
                    farm += f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n"
                    for each_crop in get_user_crops:
                        if each_crop['can_harvest_date'] < int(time.time()):
                            if "{}{}".format(each_crop['plant_name'], each_crop['plant_emoji']) not in can_harvest:
                                can_harvest.append("{}{}".format(each_crop['plant_name'], each_crop['plant_emoji']))
                            total_can_harvest += 1
                    if total_can_harvest > 0:
                        can_harvest_string = "\n".join(can_harvest)
                else:
                    # Empty farm
                    crop_array_emoji = [soil]*(config.economy.max_farm_plant_per_user)
                    i=1
                    for each_crop in crop_array_emoji:
                        if (i-1) % 9 == 0:
                            farm += f"{fence_left}"
                            farm += f"{each_crop}"
                        elif i > 0 and i % 9 == 0:
                            farm += f"{each_crop}"
                            farm += f"{fence_right}\n"
                        else:
                            farm += f"{each_crop}"
                        i += 1
                    farm = f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n" + farm
                    farm += f"{fence_left}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_h}{fence_right}\n"

                e = disnake.Embed(title="{}#{} Farm".format(member.name, member.discriminator), description="Economy [Testing]", timestamp=datetime.utcnow())
                e.add_field(name="Farm View", value=farm, inline=False)
                if total_can_harvest > 0:
                    e.add_field(name="Can Harvest: {}".format(total_can_harvest), value=can_harvest_string, inline=False)
                try:
                    get_user_harvested_crops = await self.db.economy_farm_user_planting_group_harvested(str(member.id))
                    if get_user_harvested_crops and len(get_user_harvested_crops) > 0:
                        harvested_lists = ""
                        for each_item in get_user_harvested_crops:
                            harvested_lists += each_item['plant_name'] + " " + each_item['plant_emoji'] + " x" +str(each_item['numbers']) + "={:,.0f}".format(each_item['total_products']) + "\n"
                        e.add_field(name="Harvested Available", value=harvested_lists, inline=False)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                e.set_thumbnail(url=member.display_avatar)
                msg = await ctx.reply(embed=e)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())


    async def eco_harvest(self, ctx):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        if ctx.author.id in GAME_INTERACTIVE_ECO:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You are ongoing with one **game economy** play."}        

        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo and get_userinfo['numb_farm'] == 0:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You do not have any farm."}
        try:
            if ctx.author.id not in GAME_INTERACTIVE_ECO:
                GAME_INTERACTIVE_ECO.append(ctx.author.id)
            total_can_harvest = 0
            can_harvest = []
            havested_crops = ""
            get_user_crops = await self.db.economy_farm_user_planting_nogroup(str(ctx.author.id))
            if get_user_crops and len(get_user_crops) > 0:
                for each_crop in get_user_crops:
                    if each_crop['can_harvest_date'] < int(time.time()):
                        # add crop ID for update status
                        can_harvest.append(each_crop['id'])
                        havested_crops += each_crop['plant_name'] + each_crop['plant_emoji'] + " "
                        total_can_harvest += 1
                if total_can_harvest == 0:
                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, All your crops are not able to harvest yet!"}
                else:
                    # Let's update farming
                    harvesting = await self.db.economy_farm_harvesting(str(ctx.author.id), can_harvest)
                    if harvesting:
                        await ctx.reply('You harvested {} crop(s) {}.'.format(total_can_harvest, havested_crops))
            else:
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You do not have any plant for harvesting yet. Please plant them!"}
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.author.id in GAME_INTERACTIVE_ECO:
            GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    async def eco_fishing(self, ctx):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # If user has so many items and not use:
        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo and get_userinfo['fishing_bait'] <= 0:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You do not have any bait. Please buy `{prefix}eco buy bait`."}

        # If he has to much fishes
        try:
            get_fish_inventory_list = await self.db.economy_get_list_fish_caught(str(ctx.author.id), sold='NO', caught='YES')
            if len(get_fish_inventory_list) > 0:
                total_weight = sum(each_item['Weights'] for each_item in get_fish_inventory_list)
                if float(total_weight) >= float(config.economy.fishing_max_store):
                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You too much in storage (max. {config.economy.fishing_max_store}kg). Please sell some of them!"}
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        if ctx.author.id in GAME_INTERACTIVE_ECO:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You are ongoing with one **game economy** play."}
        else:
            GAME_INTERACTIVE_ECO.append(ctx.author.id)

        try:
            # If health less than 50%, stop
            if get_userinfo['health_current']/get_userinfo['health_total'] < 0.5:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} Your health is having issue. Do some heatlh check."}
            # If energy less than 20%, stop
            if get_userinfo['energy_current']/get_userinfo['energy_total'] < 0.2:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} You have very small energy. Eat to powerup."}

            has_boat = False
            will_fishing = 1
            if get_userinfo['numb_boat'] >= 1:
                has_boat = True
                will_fishing = config.economy.max_boat_can_fishing
                if get_userinfo['fishing_bait'] < will_fishing:
                    will_fishing = get_userinfo['fishing_bait']
            loop_exp = 0
            fishing_exp = get_userinfo['fishing_exp']
            try:
                loop_exp = math.floor(math.log10(fishing_exp**0.75)) - 1
                if loop_exp < 0: loop_exp = 0
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            selected_item_list = []
            item_list = await self.db.economy_get_list_fish_items()
            total_energy_loss = 0.0
            total_exp = 0.0
            numb_caught = 0
            for x in range(0, will_fishing):
                caught = "YES" if bool(random.getrandbits(1)) else "NO"
                if caught == "NO":
                    while loop_exp > 0 and caught == "NO":
                        loop_exp -= 1
                        caught = "YES" if bool(random.getrandbits(1)) else "NO"
                random.shuffle(item_list)
                selected_item = random.choice(item_list) if item_list and len(item_list) > 0 else None
                # Get a selected fish
                fish_strength = round(random.uniform(float(selected_item['fish_strength_min']), float(selected_item['fish_strength_max'])), 2)
                fish_weight = round(random.uniform(float(selected_item['fish_weight_min']), float(selected_item['fish_weight_max'])), 2)
                energy_loss = round(float(fish_strength)*config.economy.fishing_energy_loss_ratio, 2)
                if caught == "YES":
                    exp_gained = int(fish_weight*config.economy.fishing_exp_strength_ratio) + 1
                    numb_caught += 1
                else:
                    exp_gained = 0
                selected_item_list.append({'id': selected_item['id'], 
                                           'user_id': str(ctx.author.id), 
                                           'guild_id': str(ctx.guild.id), 
                                           'fish_strength': fish_strength, 
                                           'fish_weight': fish_weight, 
                                           'exp_gained': exp_gained, 
                                           'energy_loss': energy_loss, 
                                           'caught': caught,
                                           'fish_name': selected_item['fish_name'],
                                           'fish_emoji': selected_item['fish_emoji'],
                                           })
                total_energy_loss += energy_loss
                total_exp += exp_gained
            total_energy_loss = round(total_energy_loss, 2)
            total_exp = round(total_exp, 2)
            if will_fishing > 0: 
                if has_boat and type(ctx) is not disnake.interactions.app_command_interaction.SlashInteraction:
                    await ctx.message.add_reaction("🚣")
                elif not has_boat and type(ctx) is not disnake.interactions.app_command_interaction.SlashInteraction:
                    await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                await asyncio.sleep(1.0)
                insert_item = await self.db.economy_insert_fishing_multiple(selected_item_list, total_energy_loss, total_exp, str(ctx.author.id))
                if numb_caught > 0:
                    item_info_list = []
                    total_weight = 0.0
                    for each_fish in selected_item_list:
                        if each_fish['caught'] == "YES":
                            item_info_list.append(each_fish['fish_name'] + " " + each_fish['fish_emoji'] + " - weight: {:.2f}kg".format(each_fish['fish_weight']))
                            total_weight += each_fish['fish_weight']
                    item_info = "\n".join(item_info_list)
                    item_info_with_weight = item_info + "\nTotal: {:.2f}kg".format(total_weight)
                    await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} Nice! You have caught `{numb_caught}` fish(es): ```{item_info_with_weight}```You spent `{will_fishing}` bait(s). You gained `{str(total_exp)}` fishing experience and spent `{str(total_energy_loss)}` energy.')
                else:
                    # Not caught
                    await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} Too bad! You lose {will_fishing} fish(es) and spent `{str(total_energy_loss)}` energy!')
            else:
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention} There is no fish."}
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.author.id in GAME_INTERACTIVE_ECO:
            GAME_INTERACTIVE_ECO.remove(ctx.author.id)
        return


    async def eco_woodcutting(self, ctx):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo and get_userinfo['tree_cut'] > 10:
            if get_userinfo['tree_planted'] / get_userinfo['tree_cut'] < config.economy.ratio_plant_cut:
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You have cut many trees than planting. Please plant some trees."}

        # If health less than 50%, stop
        if get_userinfo['health_current']/get_userinfo['health_total'] < 0.5:
            if ctx.author.id in GAME_INTERACTIVE_ECO:
                GAME_INTERACTIVE_ECO.remove(ctx.author.id)
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Your health is having issue. Do some heatlh check."}
        # If energy less than 20%, stop
        if get_userinfo['energy_current']/get_userinfo['energy_total'] < 0.5:
            if ctx.author.id in GAME_INTERACTIVE_ECO:
                GAME_INTERACTIVE_ECO.remove(ctx.author.id)
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You have very small energy. Eat to powerup."}

        if ctx.author.id in GAME_INTERACTIVE_ECO:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You are ongoing with one **game economy** play."}
        else:
            GAME_INTERACTIVE_ECO.append(ctx.author.id)

        try:
            # Get list of items:
            if type(ctx) is not disnake.interactions.MessageInteraction:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            await asyncio.sleep(1.0)
            timber_volume = math.floor(random.uniform(config.economy.plant_volume_rand_min, config.economy.plant_volume_rand_max)) + 1
            leaf_kg = math.floor(config.economy.leaf_per_volume * timber_volume) + 1
            energy_loss = int(timber_volume/5) + 10
            try:
                insert_woodcut = await self.db.economy_insert_woodcutting(str(ctx.author.id), str(ctx.guild.id), timber_volume, leaf_kg, energy_loss)
                if insert_woodcut:
                    await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} You cut a tree. You got `{timber_volume}m3` of timber, '
                                    f'`{leaf_kg}kg` of leaves. You spent `{energy_loss}` energy.')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.author.id in GAME_INTERACTIVE_ECO:
            GAME_INTERACTIVE_ECO.remove(ctx.author.id)
        return


    async def eco_search(self, ctx):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        # If user has so many items and not use:
        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        get_user_inventory = await self.db.economy_get_user_inventory(str(ctx.author.id))
        nos_items = sum(each_item['numbers'] for each_item in get_user_inventory if each_item['item_name'] != "Gem")
        if get_userinfo and nos_items >= config.economy.max_backpack_items:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, There are many items in your backpack. Please use them first."}

        # If user just searched recently;
        get_last_searching = await self.db.economy_get_user_searched_item_list_record(str(ctx.author.id), config.economy.search_duration_lap)
        if get_last_searching and len(get_last_searching) >= config.economy.search_duration_lap_nos_item:
            remaining = config.economy.search_duration_lap - int(time.time()) + get_last_searching[0]['date']
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You just searched recently. Try again in `{seconds_str(remaining)}`."}

        if ctx.author.id in GAME_INTERACTIVE_ECO:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You are ongoing with one **game economy** play."}
        else:
            GAME_INTERACTIVE_ECO.append(ctx.author.id)

        try:
            # Get list of items:
            if type(ctx) is not disnake.interactions.MessageInteraction:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            await asyncio.sleep(1.0)
            if random.randint(1,100) < config.economy.luck_search:
                # You get luck
                try:
                    item_list = await self.db.economy_get_list_secret_items()
                    selected_item = random.choice(item_list)
                    insert_item = await self.db.economy_insert_secret_findings(selected_item['id'], str(ctx.author.id), str(ctx.guild.id), selected_item['item_health'], selected_item['item_energy'], selected_item['item_gem'], True)
                    if insert_item:
                        item_info = selected_item['item_name'] + " " + selected_item['item_emoji']
                        if selected_item['item_health'] and selected_item['item_health'] > 0:
                            item_info += " with {:,.2f} refillable health".format(selected_item['item_health'])
                        if selected_item['item_energy'] and selected_item['item_energy'] > 0:
                            item_info += " with {:,.2f} refillable energy".format(selected_item['item_energy'])
                        if selected_item['item_gem'] and selected_item['item_gem'] > 0:
                            item_info += " with {:,.0f} gem(s)".format(selected_item['item_gem'])
                        await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} Nice! You have found a box and with {item_info} inside. You put it into your backpack.')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            else:
                # Get empty box
                #economy_insert_secret_findings(item_id: int, user_id: str, guild_id: str, item_health: float, item_energy: float, item_gem: int, can_use: bool=True):
                insert_item = await self.db.economy_insert_secret_findings(8, str(ctx.author.id), str(ctx.guild.id), 0, 0, 0, False)
                if insert_item:
                    await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} You found an empty box. Good luck next time!')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.author.id in GAME_INTERACTIVE_ECO:
            GAME_INTERACTIVE_ECO.remove(ctx.author.id)
        return


    async def eco_eat(self, ctx):
        check_this_ctx = await self.check_guild(ctx)
        if "error" in check_this_ctx:
            return check_this_ctx

        if ctx.author.id in GAME_INTERACTIVE_ECO:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You are ongoing with one **game economy** play."}

        # If a user ate a lot already for the last 12h
        user_eat_record = await self.db.economy_get_user_eating_list_record(str(ctx.author.id), 12*3600)
        if user_eat_record and len(user_eat_record) > config.economy.max_user_eat:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You have eaten a lot already for the last 12h."}
        
        # If guild already has many food ordered last 12h
        count_eating_record = await self.db.economy_get_guild_eating_list_record(str(ctx.guild.id), 12*3600)
        allowed_eating_session = int(config.economy.max_guild_food*len(ctx.guild.members))
        if count_eating_record and len(count_eating_record) > allowed_eating_session:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Restaurant out of food. There were allowed only **{str(allowed_eating_session)}** orders for the last 12h."}
        # Get all available work in the guild
        get_foodlist = await self.db.economy_get_guild_foodlist(str(ctx.guild.id), True)
        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo:
            # If energy less than 20%, stop
            if get_userinfo['energy_current']/get_userinfo['energy_total'] > 0.95:
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You still have much energy."}
            if ctx.author.id not in GAME_INTERACTIVE_ECO:
                GAME_INTERACTIVE_ECO.append(ctx.author.id)
                    # Add work if he needs to do
                e = disnake.Embed(title="{}#{} Food list in guild: {}".format(ctx.author.name, ctx.author.discriminator, ctx.guild.name), description="Economy [Testing]", timestamp=datetime.utcnow())
                get_foodlist_guild = await self.db.economy_get_guild_foodlist(str(ctx.guild.id), False)
                all_food_in_guild = {}
                if get_foodlist_guild and len(get_foodlist_guild) > 0:
                    for each_food in get_foodlist_guild:
                        e.add_field(name=each_food['food_name'] + " " + each_food['food_emoji'], value="```Energy: {} / Cost: {}{}```".format(each_food['gained_energy'], num_format_coin(each_food['cost_expense_amount'], each_food['cost_coin_name']), each_food['cost_coin_name']), inline=False)
                        all_food_in_guild[str(each_food['food_emoji'])] = each_food['food_id']
                    e.set_footer(text=f"User {ctx.author.name}#{ctx.author.discriminator}")
                    e.set_thumbnail(url=ctx.author.display_avatar)
                    msg = await ctx.reply(embed=e)
                    for each_food in get_foodlist_guild:
                        await msg.add_reaction(each_food['food_emoji'])

                    def check(reaction, user):
                        return user == ctx.author and reaction.message.author == self.bot.user and reaction.message.id == msg.id
                    while True:
                        try:
                            reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=check)
                        except asyncio.TimeoutError:
                            if ctx.author.id in GAME_INTERACTIVE_ECO:
                                GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                            if type(ctx) is not disnake.interactions.MessageInteraction:
                                await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                            try:
                                await msg.delete()
                            except Exception as e:
                                pass
                            break
                            return
                        if reaction.emoji and str(reaction.emoji) in all_food_in_guild:
                            try:
                                get_food_id = await self.db.economy_get_food_id(all_food_in_guild[str(reaction.emoji)])
                                # Check balance:
                                COIN_NAME = get_food_id['cost_coin_name'].upper()
                                user_from = await store.sql_get_userwallet(str(ctx.author.id), COIN_NAME)
                                if user_from is None:
                                    if COIN_NAME in ENABLE_COIN_ERC:
                                        w = await create_address_eth()
                                        user_from = await store.sql_register_user(str(ctx.author.id), COIN_NAME, SERVER_BOT, 0, w)
                                    elif COIN_NAME in ENABLE_COIN_TRC:
                                        result = await store.create_address_trx()
                                        user_from = await store.sql_register_user(str(ctx.author.id), COIN_NAME, SERVER_BOT, 0, result)
                                    else:
                                        user_from = await store.sql_register_user(str(ctx.author.id), COIN_NAME, SERVER_BOT, 0)
                                userdata_balance = await store.sql_user_balance(str(ctx.author.id), COIN_NAME)
                                xfer_in = 0
                                if COIN_NAME not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                                    xfer_in = await store.sql_user_balance_get_xfer_in(str(ctx.author.id), COIN_NAME)
                                if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                                    actual_balance = float(xfer_in) + float(userdata_balance['Adjust'])
                                elif COIN_NAME in ENABLE_COIN_NANO:
                                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])
                                    actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
                                else:
                                    actual_balance = int(xfer_in) + int(userdata_balance['Adjust'])

                                # Negative check
                                try:
                                    if actual_balance < 0:
                                        msg_negative = 'Negative balance detected:\nUser: '+str(ctx.author.id)+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                                        await logchanbot(msg_negative)
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                                # End negative check
                                food_name = get_food_id['food_name']
                                if get_food_id['cost_expense_amount'] > actual_balance:
                                    if ctx.author.id in GAME_INTERACTIVE_ECO:
                                        GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Insufficient balance to eat `{food_name}`."}
                                # Else, go on and Insert work to DB
                                add_energy = get_food_id['gained_energy']
                                if get_userinfo['energy_current'] + add_energy > get_userinfo['energy_total']:
                                    add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                                total_energy = get_userinfo['energy_current'] + add_energy
                                # economy_insert_eating(user_id: str, guild_id: str, cost_coin_name: str, cost_expense_amount: float, cost_decimal: float, gained_energy: float):
                                insert_eating = await self.db.economy_insert_eating(str(ctx.author.id), str(ctx.guild.id), get_food_id['cost_coin_name'], 
                                                                                    get_food_id['cost_expense_amount'], get_food_id['fee_ratio']*get_food_id['cost_expense_amount'], 
                                                                                    get_food_id['cost_decimal'], add_energy)
                                paid_money = '{} {}'.format(num_format_coin(get_food_id['cost_expense_amount'], get_food_id['cost_coin_name']), get_food_id['cost_coin_name'])
                                if insert_eating:
                                    await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} You paid `{paid_money}` and ate `{food_name}`. You gained `{add_energy}` energy. You have total `{total_energy}` energy.')
                                    await msg.delete()
                                    await ctx.message.add_reaction(reaction.emoji)
                                else:
                                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Internal error."}
                                if ctx.author.id in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                break
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                        elif str(reaction.emoji) == EMOJI_OK_BOX:
                            if ctx.author.id in GAME_INTERACTIVE_ECO:
                                GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                            return
                else:
                    if ctx.author.id in GAME_INTERACTIVE_ECO:
                        GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Sorry, there is no available work yet."}
        else:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Internal error."}


    async def eco_work(self, ctx, claim: str=None):        
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(LOG_CHAN)
        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        prefix = await get_guild_prefix(ctx)
        if serverinfo and 'enable_economy' in serverinfo and serverinfo['enable_economy'] == "NO":
            await self.botLogChan.send(f'{ctx.author.name} / {ctx.author.id} tried **{prefix}economy sell** in {ctx.guild.name} / {ctx.guild.id} which is not ENABLE.')
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Economy is not available in this guild yet. Please request Guild owner to enable by `{prefix}SETTING ECONOMY`"}

        if serverinfo['economy_channel']:
            eco_channel = self.bot.get_channel(int(serverinfo['economy_channel']))
            if not eco_channel:
                return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, Can not find economy channel or invalid."}
            elif ctx.channel.id != int(serverinfo['economy_channel']):
                try:
                    EcoChan = self.bot.get_channel(int(serverinfo['economy_channel']))
                    return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, {EcoChan.mention} is the economy channel!!!"}
                except Exception as e:
                    pass
        else:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, There is no economy channel yet!"}

        if ctx.author.id in GAME_INTERACTIVE_ECO:
            return {"error": f"{EMOJI_RED_NO} {ctx.author.mention}, You are ongoing with one **game economy** play."}

        # Get all available work in the guild
        get_worklist = await self.db.economy_get_guild_worklist(str(ctx.guild.id), True)
        # Getting list of work in the guild and re-act
        get_userinfo = await self.db.economy_get_user(str(ctx.author.id), '{}#{}'.format(ctx.author.name, ctx.author.discriminator))
        if get_userinfo:
            # If health less than 50%, stop
            if get_userinfo['health_current']/get_userinfo['health_total'] < 0.5:
                await asyncio.sleep(0.5)
                return {"error": f"{EMOJI_INFORMATION} {ctx.author.mention}, Your health is having issue. Do some heatlh check."}
                
            elif get_userinfo['health_current']/get_userinfo['health_total'] < 0.3:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_INFORMATION} {ctx.author.mention}, Your health is having issue."}
            # If energy less than 20%, stop
            if get_userinfo['energy_current']/get_userinfo['energy_total'] < 0.2:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                return {"error": f"{EMOJI_INFORMATION} {ctx.author.mention}, You have very small energy. Eat to powerup."}
            try:
                get_last_act = await self.db.economy_get_last_activities(str(ctx.author.id), False)
                if (get_last_act and get_last_act['status'] == 'COMPLETED') or get_last_act is None:
                    if ctx.author.id not in GAME_INTERACTIVE_ECO:
                        GAME_INTERACTIVE_ECO.append(ctx.author.id)
                    # Add work if he needs to do
                    e = disnake.Embed(title="{}#{} Work list in guild: {}".format(ctx.author.name, ctx.author.discriminator, ctx.guild.name), description="Economy [Testing]", timestamp=datetime.utcnow())
                    get_worklist_guild = await self.db.economy_get_guild_worklist(str(ctx.guild.id), False)
                    all_work_in_guild = {}
                    if get_worklist_guild and len(get_worklist_guild) > 0:
                        for each_work in get_worklist_guild:
                            plus_minus = "+" if each_work['reward_expense_amount'] > 0 else ""
                            reward_string = plus_minus + num_format_coin(each_work['reward_expense_amount'], each_work['reward_coin_name']) + " " + each_work['reward_coin_name']
                            e.add_field(name=each_work['work_name'] + " " + each_work['work_emoji'] + " ( Duration: {}) | {}".format(seconds_str(each_work['duration_in_second']), reward_string), value="```Exp: {}xp / Energy: {} / Health: {}```".format(each_work['exp_gained_loss'], each_work['energy_loss'], each_work['health_loss']), inline=False)
                            all_work_in_guild[str(each_work['work_emoji'])] = each_work['work_id']
                        e.set_footer(text=f"User {ctx.author.name}#{ctx.author.discriminator}")
                        e.set_thumbnail(url=ctx.author.display_avatar)
                        msg = await ctx.reply(embed=e)
                        for each_work in get_worklist_guild:
                            await msg.add_reaction(each_work['work_emoji'])

                        def check(reaction, user):
                            return user == ctx.author and reaction.message.author == self.bot.user and reaction.message.id == msg.id
                        while True:
                            try:
                                reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=check)
                            except asyncio.TimeoutError:
                                if ctx.author.id in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                if type(ctx) is not disnake.interactions.MessageInteraction:
                                    await ctx.message.add_reaction(EMOJI_ALARMCLOCK)
                                try:
                                    await msg.delete()
                                except Exception as e:
                                    pass
                                break
                                return
                            if reaction.emoji and str(reaction.emoji) in all_work_in_guild:
                                try:
                                    # Insert work to DB
                                    get_work_id = await self.db.economy_get_workd_id(all_work_in_guild[str(reaction.emoji)])
                                    add_energy = get_work_id['exp_gained_loss']
                                    if get_userinfo['energy_current'] + get_work_id['energy_loss'] > get_userinfo['energy_total'] and get_work_id['energy_loss'] > 0:
                                        add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                                    insert_activity = await self.db.economy_insert_activity(str(ctx.author.id), str(ctx.guild.id), all_work_in_guild[str(reaction.emoji)], 
                                                                                          get_work_id['duration_in_second'], get_work_id['reward_coin_name'], 
                                                                                          get_work_id['reward_expense_amount'], get_work_id['reward_expense_amount']*get_work_id['fee_ratio'], 
                                                                                          get_work_id['reward_decimal'], add_energy, 
                                                                                          get_work_id['health_loss'], get_work_id['energy_loss'])
                                    if insert_activity:
                                        additional_text = " You can claim in: `{}`.".format(seconds_str(get_work_id['duration_in_second']))
                                        task_name = "{} {}".format(get_work_id['work_name'], get_work_id['work_emoji'])
                                        await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} You started a new task - {task_name}! {additional_text}')
                                        await msg.delete()
                                        if type(ctx) is not disnake.interactions.MessageInteraction:
                                            await ctx.message.add_reaction(reaction.emoji)
                                    else:
                                        return {"error": f"{EMOJI_INFORMATION} {ctx.author.mention}, Internal error."}
                                    if ctx.author.id in GAME_INTERACTIVE_ECO:
                                        GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                    break
                                except Exception as e:
                                    await logchanbot(traceback.format_exc())
                            elif str(reaction.emoji) == EMOJI_OK_BOX:
                                if ctx.author.id in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                return
                    else:
                        if ctx.author.id in GAME_INTERACTIVE_ECO:
                            GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                        return {"error": f"{EMOJI_ERROR} {ctx.author.mention}, Sorry, there is no available work yet."}
                else:
                    # He is not free
                    if claim and claim.upper() == 'CLAIM':
                        if ctx.author.id not in GAME_INTERACTIVE_ECO:
                            GAME_INTERACTIVE_ECO.append(ctx.author.id)
                        # Check if he can complete the last work
                        if get_last_act and get_last_act['status'] == 'ONGOING' and get_last_act['started'] + get_last_act['duration_in_second'] <= int(time.time()):
                            # Get guild's balance not ctx.guild
                            played_guild = self.bot.get_guild(int(get_last_act['guild_id']))
                            # Check guild's balance:
                            COIN_NAME = get_last_act['reward_coin_name'].upper()
                            guild_game = await store.sql_get_userwallet(get_last_act['guild_id'], COIN_NAME)
                            if guild_game is None:
                                if COIN_NAME in ENABLE_COIN_ERC:
                                    w = await create_address_eth()
                                    guild_game = await store.sql_register_user(get_last_act['guild_id'], COIN_NAME, SERVER_BOT, 0, w)
                                elif COIN_NAME in ENABLE_COIN_TRC:
                                    result = await store.create_address_trx()
                                    guild_game = await store.sql_register_user(get_last_act['guild_id'], COIN_NAME, SERVER_BOT, 0, result)
                                else:
                                    guild_game = await store.sql_register_user(get_last_act['guild_id'], COIN_NAME, SERVER_BOT, 0)
                            guilddata_balance = await store.sql_user_balance(get_last_act['guild_id'], COIN_NAME)
                            xfer_in = 0
                            if COIN_NAME not in ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                                xfer_in = await store.sql_user_balance_get_xfer_in(get_last_act['guild_id'], COIN_NAME)
                            if COIN_NAME in ENABLE_COIN_DOGE+ENABLE_COIN_ERC+ENABLE_COIN_TRC:
                                actual_balance = float(xfer_in) + float(guilddata_balance['Adjust'])
                            elif COIN_NAME in ENABLE_COIN_NANO:
                                actual_balance = int(xfer_in) + int(guilddata_balance['Adjust'])
                                actual_balance = round(actual_balance / get_decimal(COIN_NAME), 6) * get_decimal(COIN_NAME)
                            else:
                                actual_balance = int(xfer_in) + int(guilddata_balance['Adjust'])

                            # Negative check
                            try:
                                if actual_balance < 0:
                                    msg_negative = 'Negative balance detected:\Guild: '+str(get_last_act['guild_id'])+'\nCoin: '+COIN_NAME+'\nAtomic Balance: '+str(actual_balance)
                                    await logchanbot(msg_negative)
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                            # End negative check
                            if get_last_act['reward_amount'] > actual_balance:
                                await logchanbot(str(get_last_act['guild_id']) + ' runs out of balance for coin {COIN_NAME}. Stop rewarding.')
                                if ctx.author.id in GAME_INTERACTIVE_ECO:
                                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                                return {"error": f"{EMOJI_ERROR} {ctx.author.mention}, This guild runs out of balance to give reward."}
                            # OK, let him claim
                            try:
                                add_energy = get_last_act['energy']
                                if get_userinfo['energy_current'] + add_energy > get_userinfo['energy_total'] and add_energy > 0:
                                    add_energy = get_userinfo['energy_total'] - get_userinfo['energy_current']
                                add_health = get_last_act['health']
                                if get_userinfo['health_current'] + add_health > get_userinfo['health_total'] and add_health > 0:
                                    add_health = get_userinfo['health_total'] - get_userinfo['health_current']
                                update_work = await self.db.economy_update_activity(get_last_act['id'], str(ctx.author.id), get_last_act['exp'], add_health, add_energy)
                                if update_work:
                                    completed_task = 'You completed task #{}\n'.format(get_last_act['id'])
                                    completed_task += 'Gained Exp: {}\n'.format(get_last_act['exp'])
                                    if get_last_act['reward_amount'] and get_last_act['reward_amount'] > 0:
                                        completed_task += 'Reward Coin: {}{}\n'.format(num_format_coin(get_last_act['reward_amount'], get_last_act['reward_coin_name']), get_last_act['reward_coin_name'])
                                    if get_last_act['health'] and get_last_act['health'] > 0:
                                        completed_task += 'Gained Health: {}\n'.format(get_last_act['health'])
                                    if get_last_act['energy'] and get_last_act['energy'] > 0:
                                        completed_task += 'Gained energy: {}\n'.format(get_last_act['energy'])
                                    if get_last_act['energy'] and get_last_act['energy'] < 0:
                                        completed_task += 'Spent of energy: {}'.format(get_last_act['energy'])
                                    await ctx.reply(f'{EMOJI_INFORMATION} {ctx.author.mention} ```{completed_task}```')
                                else:
                                    return {"error": f"{EMOJI_ERROR} {ctx.author.mention}, Internal error."}
                            except:
                                traceback.print_exc(file=sys.stdout)
                                return {"error": f"{EMOJI_ERROR} {ctx.author.mention}, Internal error."}
                        else:
                            remaining = get_last_act['started'] + get_last_act['duration_in_second'] - int(time.time())
                            additional_claim_msg = ""
                            if remaining < 0:
                                remaining = 0
                                additional_claim_msg = "You shall claim it now!"
                            return {"error": f"{EMOJI_ERROR} {ctx.author.mention}, Sorry, you can not claim it now. Remaining time `{seconds_str(remaining)}`. {additional_claim_msg}"}
                    else:
                        remaining = get_last_act['started'] + get_last_act['duration_in_second'] - int(time.time())
                        additional_claim_msg = ""
                        if remaining < 0:
                            remaining = 0
                            additional_claim_msg = "You shall claim it now!"
                        return {"error": f"{EMOJI_ERROR} {ctx.author.mention}, Sorry, you are still busy with other activity. Remaining time `{seconds_str(remaining)}`. {additional_claim_msg}"}
                    if ctx.author.id in GAME_INTERACTIVE_ECO:
                        GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                    return
            except:
                if ctx.author.id in GAME_INTERACTIVE_ECO:
                    GAME_INTERACTIVE_ECO.remove(ctx.author.id)
                traceback.print_exc(file=sys.stdout)
                error = disnake.Embed(title=":exclamation: Error", description=" :warning: internal error!")
                await ctx.reply(embed=error)
        else:
            return {"error": f"{EMOJI_ERROR} {ctx.author.mention}, Internal error."}


    @commands.guild_only()
    @commands.slash_command(
        description="Economy game commands."
    )
    async def eco(self, ctx):
        pass


    @eco.sub_command(
        usage="eco items", 
        description="Get an economy information of a member."
    )
    async def items(
        self, 
        ctx
    ):
        eco_items = await self.eco_items(ctx)
        if eco_items and "error" in eco_items:
            await ctx.reply(eco_items['error'], ephemeral=False)
        if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    @eco.sub_command(
        usage="eco info <member>", 
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Get an economy information of a member."
    )
    async def info(
        self, 
        ctx, 
        member: disnake.Member=None
    ):
        if member is None:
            member = ctx.author

        eco_info = await self.eco_info(ctx, member)
        if eco_info and "error" in eco_info:
            await ctx.reply(eco_info['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco sell <item>", 
        options=[
            Option('item_name', 'item_name', OptionType.string, required=True)
        ],
        description="Sell an economic item."
    )
    async def sell(
        self, 
        ctx, 
        item_name: str
    ):
        eco_sell = await self.eco_sell(ctx, item_name)
        if eco_sell and "error" in eco_sell:
            await ctx.reply(eco_sell['error'], ephemeral=False)
        elif eco_sell and "result" in eco_sell:
            await ctx.reply(eco_sell['result'], ephemeral=False)


    @eco.sub_command(
        usage="eco buy <item>", 
        options=[
            Option('item_name', 'item_name', OptionType.string, required=True)
        ],
        description="Buy an economic item."
    )
    async def buy(
        self, 
        ctx, 
        *, 
        item_name: str
    ):
        eco_buy = await self.eco_buy(ctx, item_name)
        if item_name is None:
            item_name = "LIST"
        if item_name.upper() == "LIST":
            if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)
            return

        if eco_buy and "error" in eco_buy:
            await ctx.reply(eco_buy['error'], ephemeral=False)
        elif eco_buy and "result" in eco_buy:
            await ctx.reply(eco_buy['result'], ephemeral=False)
        if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)

    @eco.sub_command(
        usage="eco lumber <member>", 
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Get an economy information of a member."
    )
    async def lumber(
        self, 
        ctx, 
        member: disnake.Member=None
    ):
        if member is None:
            member = ctx.author
        eco_lumber = await self.eco_lumber(ctx, member)
        if eco_lumber and "error" in eco_lumber:
            await ctx.reply(eco_lumber['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco fish <member>", 
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Show fishes of a member."
    )
    async def fish(
        self, 
        ctx, 
        member: disnake.Member=None
    ):
        if member is None:
            member = ctx.author
        eco_fish = await self.eco_fish(ctx, member)
        if eco_fish and "error" in eco_fish:
            await ctx.reply(eco_fish['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco plant <crop name>", 
        options=[
            Option('plant_name', 'plant_name', OptionType.string, required=True, choices=[
                OptionChoice("🥦 broccoli", "broccoli"),
                OptionChoice("🥕 carrot", "carrot"),
                OptionChoice("🍒 cherry", "cherry"),
                OptionChoice("🌽 corn", "corn"),
                OptionChoice("🥒 cucumber", "cucumber"),
                OptionChoice("🍆 eggplant", "eggplant"),
                OptionChoice("🍇 grape", "grape"),
                OptionChoice("🍋 lemon", "lemon"),
                OptionChoice("🍄 mushroom", "mushroom"),
                OptionChoice("🍅 tomato", "tomato")
            ])
        ],
        description="Plant a crop."
    )
    async def plant(
        self, 
        ctx, 
        plant_name: str
    ):
        eco_plant = await self.eco_plant(ctx, plant_name)
        if eco_plant and "error" in eco_plant:
            await ctx.reply(eco_plant['error'], ephemeral=False)
        if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    @eco.sub_command(
        usage="eco collect <what>", 
        options=[
            Option('what', 'name', OptionType.string, required=True, choices=[
                OptionChoice("EGG", "EGG"),
                OptionChoice("MILK", "MILK")
            ]
            )
        ],
        description="Collect collectible thing."
    )
    async def collect(
        self, 
        ctx, 
        what: str
    ):
        eco_collect = await self.eco_collect(ctx, what)
        if eco_collect and "error" in eco_collect:
            await ctx.reply(eco_collect['error'], ephemeral=False)
        if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    @eco.sub_command(
        usage="eco dairy <member>", 
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Show dairy of a member."
    )
    async def dairy(
        self, 
        ctx, 
        member: disnake.Member=None
    ):
        if member is None:
            member = ctx.author
        eco_dairy = await self.eco_dairy(ctx, member)
        if eco_dairy and "error" in eco_dairy:
            await ctx.reply(eco_dairy['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco chicken <member>", 
        options=[
            Option('member', 'member', OptionType.user, required=True)
        ],
        description="Show chicken farm of a member."
    )
    async def chicken(
        self, 
        ctx, 
        member: disnake.Member=None
    ):
        if member is None:
            member = ctx.author
        eco_chicken = await self.eco_chicken(ctx, member)
        if eco_chicken and "error" in eco_chicken:
            await ctx.reply(eco_chicken['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco farm <member>", 
        options=[
            Option('member', 'member', OptionType.user, required=False)
        ],
        description="Show farm of a member."
    )
    async def farm(
        self, 
        ctx, 
        member: disnake.Member=None
    ):
        if member is None:
            member = ctx.author
        eco_farm = await self.eco_farm(ctx, member)
        if eco_farm and "error" in eco_farm:
            await ctx.reply(eco_farm['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco harvest", 
        description="Harvest your farm."
    )
    async def harvest(
        self, 
        ctx
    ):
        eco_harvest = await self.eco_harvest(ctx)
        if eco_harvest and "error" in eco_harvest:
            await ctx.reply(eco_harvest['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco fishing", 
        description="Do fishing."
    )
    async def fishing(
        self, 
        ctx
    ):
        eco_fishing = await self.eco_fishing(ctx)
        if eco_fishing and "error" in eco_fishing:
            await ctx.reply(eco_fishing['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco woodcutting", 
        description="Cut tree(s)."
    )
    async def woodcutting(
        self, 
        ctx
    ):
        eco_woodcutting = await self.eco_woodcutting(ctx)
        if eco_woodcutting and "error" in eco_woodcutting:
            await ctx.reply(eco_woodcutting['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco search", 
        description="Search collectible items."
    )
    async def search(
        self, 
        ctx
    ):
        eco_search = await self.eco_search(ctx)
        if eco_search and "error" in eco_search:
            await ctx.reply(eco_search['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco eat", 
        description="Eat to gain energy."
    )
    async def eat(
        self, 
        ctx
    ):
        eco_eat = await self.eco_eat(ctx)
        if eco_eat and "error" in eco_eat:
            await ctx.reply(eco_eat['error'], ephemeral=False)


    @eco.sub_command(
        usage="eco work [claim]", 
        options=[
            Option('claim', 'claim', OptionType.string, required=False, choices=[
                OptionChoice("CLAIM", "CLAIM")
            ]
            )
        ],
        description="Work for more experience and thing."
    )
    async def work(
        self, 
        ctx,
        claim: str=None
    ):
        eco_work = await self.eco_work(ctx, claim)
        if eco_work and "error" in eco_work:
            await ctx.reply(eco_work['error'], ephemeral=False)


    # Message commands
    @commands.guild_only()
    @commands.group(
        usage="economy <subcommand>", 
        aliases=['eco', 'economy'], 
        description="Economy game commands."
    )
    async def _economy(self, ctx):
        prefix = await get_guild_prefix(ctx)
        if ctx.invoked_subcommand is None:
            await ctx.reply(f'{ctx.author.mention} Invalid {prefix}economy command.\n Please use {prefix}help economy')
            return


    @economy.command(
        usage="eco sell <item>", 
        aliases=['sell'], 
        description="Sell an economic item."
    )
    async def _sell(
        self, 
        ctx, 
        *, 
        item_name: str
    ):
        eco_sell = await self.eco_sell(ctx, item_name)
        if eco_sell and "error" in eco_sell:
            await ctx.reply(eco_sell['error'])
        elif eco_sell and "result" in eco_sell:
            await ctx.reply(eco_sell['result'])


    @economy.command(
        usage="eco buy <item>", 
        aliases=['buy'], 
        description="Buy an item."
    )
    async def _buy(
        self, 
        ctx, 
        *, 
        item_name: str=None
    ):
        if item_name is None:
            item_name = "LIST"
        eco_buy = await self.eco_buy(ctx, item_name)
        if item_name.upper() == "LIST":
            if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)
            return

        if eco_buy and "error" in eco_buy:
            await ctx.reply(eco_buy['error'])
        elif eco_buy and "result" in eco_buy:
            await ctx.reply(eco_buy['result'])
        if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    @economy.command(
        usage="eco info <member>", 
        aliases=['info'], 
        description="Get an economy information of a member."
    )
    async def _info(
        self, 
        ctx, 
        member: disnake.Member = None
    ):
        if member is None:
            member = ctx.author

        eco_info = await self.eco_info(ctx, member)
        if eco_info and "error" in eco_info:
            await ctx.reply(eco_info['error'])
        return



    @economy.command(
        usage="eco items", 
        aliases=['items', 'item', 'backpack'], 
        description="List items in backpack."
    )
    async def _items(self, ctx):
        eco_items = await self.eco_items(ctx)
        if eco_items and "error" in eco_items:
            await ctx.reply(eco_items['error'])
        if ctx.author.id in GAME_INTERACTIVE_ECO: GAME_INTERACTIVE_ECO.remove(ctx.author.id)


    @economy.command(
        usage="eco lumber <member>", 
        aliases=['lumber', 'timber', 'wood'], 
        description="List lumber."
    )
    async def _lumber(
        self, 
        ctx, 
        member: disnake.Member = None
    ):
        if member is None:
            member = ctx.author

        eco_lumber = await self.eco_lumber(ctx, member)
        if eco_lumber and "error" in eco_lumber:
            await ctx.reply(eco_lumber['error'])


    @economy.command(
        usage="eco fish <member>", 
        aliases=['fish', 'fishes'], 
        description="Show fishes."
    )
    async def _fish(
        self, 
        ctx, 
        member: disnake.Member = None
    ):
        if member is None:
            member = ctx.author

        eco_fish = await self.eco_fish(ctx, member)
        if eco_fish and "error" in eco_fish:
            await ctx.reply(eco_fish['error'])


    @economy.command(
        usage="eco plant <crop name>", 
        aliases=['plant'], 
        description="Plant a crop."
    )
    async def _plant(
        self, 
        ctx, 
        plant_name: str=None
    ):
        if plant_name is None: plant_name = "TREE"
        eco_plant = await self.eco_plant(ctx, plant_name)
        if eco_plant and "error" in eco_plant:
            await ctx.reply(eco_plant['error'])


    @economy.command(
        usage="eco collect <what>", 
        aliases=['cl', 'collect'], 
        description="Collect collectible thing."
    )
    async def _collect(
        self, 
        ctx, 
        what: str = None
    ):
        if what is None:
            await ctx.reply(f'{EMOJI_RED_NO} {ctx.author.mention} What do you need to collect? Tell me that also!')
            return
        else:
            what = what.upper()

        eco_collect = await self.eco_collect(ctx, what)
        if eco_collect and "error" in eco_collect:
            await ctx.reply(eco_collect['error'])


    @economy.command(
        usage="eco dairy <member>", 
        aliases=['cow', 'dairy'], 
        description="Show dairy of a member."
    )
    async def _dairy(
        self, 
        ctx, 
        member: disnake.Member = None
    ):
        if member is None:
            member = ctx.author

        eco_dairy = await self.eco_dairy(ctx, member)
        if eco_dairy and "error" in eco_dairy:
            await ctx.reply(eco_dairy['error'])


    @economy.command(
        usage="eco chicken <member>", 
        aliases=['egg', 'chickenfarm', 'chicken'], 
        description="Show chicken farm of a member."
    )
    async def _chicken(
        self, 
        ctx, 
        member: disnake.Member = None
    ):
        if member is None:
            member = ctx.author

        eco_chicken = await self.eco_chicken(ctx, member)
        if eco_chicken and "error" in eco_chicken:
            await ctx.reply(eco_chicken['error'])


    @economy.command(
        usage="eco farm", 
        aliases=['farms', 'farm'], 
        description="Show a member's farm."
    )
    async def _farm(
        self, 
        ctx, 
        member: disnake.Member = None
    ):        
        if member is None:
            member = ctx.author

        eco_farm = await self.eco_farm(ctx, member)
        if eco_farm and "error" in eco_farm:
            await ctx.reply(eco_farm['error'])


    @economy.command(
        usage="eco harvest", 
        aliases=['harvesting', 'harvest'], 
        description="Harvest your farm."
    )
    async def _harvest(
        self, 
        ctx
    ):
        eco_harvest = await self.eco_harvest(ctx)
        if eco_harvest and "error" in eco_harvest:
            await ctx.reply(eco_harvest['error'])


    @economy.command(
        usage="eco fishing", 
        aliases=['fishing'], 
        description="Do fishing."
    )
    async def _fishing(
        self, 
        ctx
    ):
        eco_fishing = await self.eco_fishing(ctx)
        if eco_fishing and "error" in eco_fishing:
            await ctx.reply(eco_fishing['error'])


    @economy.command(
        usage="eco woodcutting", 
        aliases=['woodcutting', 'cuttree', 'wc', 'cw'], 
        description="Cut tree(s)."
    )
    async def _woodcutting(
        self, 
        ctx
    ):

        eco_woodcutting = await self.eco_woodcutting(ctx)
        if eco_woodcutting and "error" in eco_woodcutting:
            await ctx.reply(eco_woodcutting['error'])


    @economy.command(
        usage="eco search", 
        aliases=['search'], 
        description="Search collectible items."
    )
    async def _search(
        self, 
        ctx
    ):
        eco_search = await self.eco_search(ctx)
        if eco_search and "error" in eco_search:
            await ctx.reply(eco_search['error'])


    @economy.command(
        usage="eco eat", 
        aliases=['eat'], 
        description="Eat to gain energy."
    )
    async def _eat(
        self, 
        ctx
    ):
        eco_eat = await self.eco_eat(ctx)
        if eco_eat and "error" in eco_eat:
            await ctx.reply(eco_eat['error'])


    @economy.command(
        usage="eco work [claim]", 
        aliases=['work'], 
        description="Work for more experience and thing."
    )
    async def _work(
        self, 
        ctx, 
        claim: str=None
    ):

        eco_work = await self.eco_work(ctx, claim)
        if eco_work and "error" in eco_work:
            await ctx.reply(eco_work['error'])


def setup(bot):
    bot.add_cog(Economy(bot))