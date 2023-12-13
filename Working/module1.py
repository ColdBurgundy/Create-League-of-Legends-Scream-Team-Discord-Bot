# -*- coding: cp949 -*- 

import discord
from discord.ext import commands
from riotwatcher import LolWatcher, ApiError
import asyncio
import json
import yaml
with open('config.yml') as f:
    keys = yaml.load(f, Loader=yaml.FullLoader)

# Riot API Ű�� ���ڵ� �� ��ū ����
discord_bot_token = keys['keys']['discord_bot_token']
riot_api_key = keys['keys']['riot_api_key']

class CustomHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, **options):
        super().__init__(**options)

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="����", description="`!help [��ɾ�]`�������� �ش� ��ɾ ���� ������ �� �� �ֽ��ϴ�.", color=0x00ff00)
        for cog, commands in mapping.items():
            filtered = await self.filter_commands(commands, sort=True)
            command_signatures = [self.get_command_signature(c) for c in filtered]
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "��ɾ� ���")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=self.get_command_signature(command), description=command.help or "���� ����", color=0x00ff00)
        channel = self.get_destination()
        await channel.send(embed=embed)

# Riot API�� ���ڵ� Ŭ���̾�Ʈ �ʱ�ȭ
lol_watcher = LolWatcher(riot_api_key)
client = commands.Bot(command_prefix='!', intents=discord.Intents.all(), help_command=CustomHelpCommand())

# �� ���ڵ� ������� �� ������ �����ϴ� ��ųʸ�
user_lol_accounts = {}  # key: discord user id, value: list of LolAccount objects

# �������� ������ �� ������ ������ ����Ʈ
selected_accounts = []

now_human = 1 # ���� �ο� ��
need_human =1 # �ʿ��� ��� ��. ���� 10���ε� �׽�Ʈ�� ���� ���� �ٲ㺸��.

# ���� ������ �� �����͸� ����
red_team = []
blue_team = []

@client.command(name='intro')
async def send_intro(ctx):
    embed = discord.Embed(
        title="���ڵ� �� �Ұ�",
        description="�ȳ��ϼ���! ���� League of Legends �� ������ �����ִ� ���ڵ� ���Դϴ�.",
        color=0x00ff00
    )
    embed.add_field(name="���", value="�� �ڵ� ����, �� ���� ������ ����, ���� ä�� �̵� ��", inline=False)
    embed.add_field(name="��� ���", value="`!help` ��ɾ�� ��� ��ɾ�� ��� ����� Ȯ���ϼ���.", inline=False)
    embed.add_field(name="������", value="[Kim YoungBeen | coldburgundy@gmail.com]", inline=False)
    embed.add_field(name="����", value="v0.7.0", inline=False)

    await ctx.send(embed=embed)


# ������ ����
def save_data_to_file(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"���� ���� �� ���� �߻�: {e}")

# ������ �ҷ�����
def load_data_from_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if not data:
                return {}
       
        loaded_data = {}
        for uid, accounts_data in data.items():
            loaded_accounts = [LolAccount.from_dict(account_data) for account_data in accounts_data]
            # �� ������ ���������� �ε��� �ο�
            for index, account in enumerate(loaded_accounts):
                account.accountsIndex = index
            # ��ȯ�� ���� ����Ʈ�� loaded_data�� ����
            loaded_data[int(uid)] = loaded_accounts
  
        return loaded_data
    
    except FileNotFoundError:
        # ������ ���� ��� �� ���� ����
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump({}, file, ensure_ascii=False, indent=4)
        return {}
    except json.JSONDecodeError as e:
        print(f"JSON ���� ���� ����: {e}")
        return {}
    except IOError as e:
        print(f"���� �б� �� ���� �߻�: {e}")
        return {}
        
# �� ���� ��ü ����
class LolAccount:
    def __init__(self, nickname, discord_id = None):
        self.discord_id = discord_id
        self.accountsIndex = None
        self.nickname = nickname
        self.preferred_roles = []  # ��ȣ�ϴ� ����
        self.assigned_role = None  # ������ ������
        self.team = None  # �Ҽӵ� ��
        self.solo_rank_tier = None  # �ַη�ũ Ƽ��
        self.solo_rank_rank = None  # �ַη�ũ �θ�����
        self.solo_rank_points = None  # �ַη�ũ ����Ʈ
        self.flex_rank_tier = None  # ������ũ Ƽ��
        self.flex_rank_rank = None  # ������ũ �θ�����
        self.flex_rank_points = None  # ������ũ ����Ʈ
        self.rankScore = None # ��ũ ��ġȭ
        self.win_rate = None  # ��ũ���� �·�
        self.top_champions = []  # ���õ� ���� è�Ǿ� 5��
        self.update_account_info()

    def update_account_info(self):
        try:
            # ��ȯ�� ���� ��������
            summoner_info = lol_watcher.summoner.by_name('kr', self.nickname)

            # ��ũ ���� ��������
            ranked_stats = lol_watcher.league.by_summoner('kr', summoner_info['id'])

            self.solo_rank_tier = None
            self.flex_rank_tier = None
            total_wins = 0
            total_losses = 0

            # �ַη�ũ �� ������ũ ���� ����
            for queue in ranked_stats:
                if queue['queueType'] == 'RANKED_SOLO_5x5':
                    self.solo_rank_tier = queue['tier']
                    self.solo_rank_rank = queue['rank']
                    self.solo_rank_points = queue['leaguePoints']
                    total_wins += queue['wins']
                    total_losses += queue['losses']
                elif queue['queueType'] == 'RANKED_FLEX_SR':
                    self.flex_rank_tier = queue['tier']
                    self.flex_rank_rank = queue['rank']
                    self.flex_rank_points = queue['leaguePoints']
                    total_wins += queue['wins']
                    total_losses += queue['losses']
                    
            # Ƽ� ���ڷ� ��ȯ�ϴ� �Լ�
            def tier_to_number(tier):
                tiers = ["None", "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
                return tiers.index(tier) * 10 if tier in tiers else 0

            # ����Ƽ� ���ڷ� ��ȯ�ϴ� �Լ�
            def rank_to_number(rank):
                ranks = {"None" : -1, "IV": 0, "III": 2.5, "II": 5, "I": 7.5}
                return ranks.get(rank, 0)

            # ��ũ ���� ���
            def calculate_rank_score(tier, rank, points):
                if tier_to_number(tier) == 0:
                    return 0
                return tier_to_number(tier) + rank_to_number(rank) + (points / 100)

            # �ַη�ũ ���� ���
            solo_rank_score = calculate_rank_score(self.solo_rank_tier, self.solo_rank_rank, self.solo_rank_points)

            # ������ũ ���� ���
            flex_rank_score = calculate_rank_score(self.flex_rank_tier, self.flex_rank_rank, self.flex_rank_points)

            # ���� ��ũ ����
            self.rankScore = solo_rank_score * 0.7 + flex_rank_score * 0.3
            
            '''

            # ���õ� ���� è�Ǿ� ���� ��������
            mastery_info = lol_watcher.champion_mastery.by_summoner('kr', summoner_info['id'])
            self.top_champions = [mastery['championId'] for mastery in mastery_info[:5]]

            '''
            # ��ü ��ũ ���� �·� ���
            total_games = total_wins + total_losses
            if total_games > 0:
                self.win_rate = round((total_wins / total_games) * 100, 2)
            
            
               
        except ApiError as err:
            print(f"API Error: {err}")
            
    def get_top_champion_names(self, champion_mapping):
        return [champion_mapping.get(str(champ_id), f"Unknown ID: {champ_id}") for champ_id in self.top_champions]
    
    def to_dict(self):
        return {
            'nickname': self.nickname,
            'accountsIndex': self.accountsIndex,
            'preferred_roles': self.preferred_roles,
            'solo_rank_tier': self.solo_rank_tier,
            'solo_rank_rank': self.solo_rank_rank,
            'solo_rank_points': self.solo_rank_points,
            'flex_rank_tier': self.flex_rank_tier,
            'flex_rank_rank': self.flex_rank_rank,
            'flex_rank_points': self.flex_rank_points,
            'rankScore': self.rankScore,
            'win_rate': self.win_rate,
            'top_champions': self.top_champions
        }
    
    @classmethod
    def from_dict(cls, data):
        account = cls(data['nickname'])
        account.accountsIndex = data.get('accountsIndex', [])
        account.preferred_roles = data.get('preferred_roles', [])
        account.solo_rank_tier = data.get('solo_rank_tier')
        account.solo_rank_rank = data.get('solo_rank_rank')
        account.solo_rank_points = data.get('solo_rank_points')
        account.flex_rank_tier = data.get('flex_rank_tier')
        account.flex_rank_rank = data.get('flex_rank_rank')
        account.flex_rank_points = data.get('flex_rank_points')
        account.rankScore = data.get('rankScore')
        account.win_rate = data.get('win_rate')
        account.top_champions = data.get('top_champions', [])
        return account




# ���� ����
@client.command(name='user_setting', help = "����ڿ� ���� �� ���� ������ �߰��� ����� ���� ������ ���� ��ɾ��Դϴ�.")
async def team_split(ctx):
    lobby_channel = discord.utils.get(ctx.guild.voice_channels, name='�κ�') # �׽�Ʈ��
    red_channel = discord.utils.get(ctx.guild.voice_channels, name='����')
    blue_channel = discord.utils.get(ctx.guild.voice_channels, name='���')
    
    global user_lol_accounts
    user_lol_accounts = load_data_from_file('user_accounts.json')
    members = lobby_channel.members
    now_human = len(members) # ������� �� �����ϰ� �����ϱ�
    if now_human != need_human:
        await ctx.send(f"�κ� {need_human-now_human}���� ������ �ʿ��մϴ�. (���� {now_human}��/{need_human}��)")
        return
    
    await ctx.send(f"�κ� {need_human}���� ������ �ֽ��ϴ�. �� ������ ���� �����͸� Ȯ���մϴ�.\n")

    # �� ������� �� ���� ���� Ȯ�� �� �߰�
    for member in members:
        while True:
            user_lol_accounts = load_data_from_file('user_accounts.json')
            if member.id in user_lol_accounts:
                accounts = user_lol_accounts[member.id]
                account_list = "\n".join([f"{idx+1}: {account.nickname}" for idx, account in enumerate(accounts)])
                await ctx.send(f"{member.mention}, ���� ��ϵ� �� ���� ���:\n{account_list}\n����� ���� ��ȣ�� �Է��ϰų�, �� ������ �߰��Ϸ��� 'new'�� �Է��ϼ���. (�ǳʶٷ��� '0'�� �Է�)")

                try:
                    response = await client.wait_for('message', check=lambda m: m.author == member and m.channel == ctx.channel, timeout=60.0)

                    if response.content.lower() == 'new':
                        await add_new_lol_account(member, ctx)
                    elif response.content == '0':
                        break
                    elif response.content.isdigit() and 1 <= int(response.content) <= len(accounts):
                        selected_index = int(response.content) - 1
                        # ���õ� ������ ���� �߰� ó�� (��: �� �Ҵ�)
                        global selected_accounts
                        selected_accounts.append(accounts[selected_index])
                        await ctx.send(f"{member.display_name}���� ����: {accounts[selected_index].nickname}")
                        print(f"{member.display_name}���� ����: {accounts[selected_index].nickname}")
                        break
                    else:
                        await ctx.send(f"{member.mention}, �߸��� �Է��Դϴ�. �ٽ� �õ����ּ���.")
                except asyncio.TimeoutError:
                    await ctx.send(f"{member.mention}, �ð��� �ʰ��Ǿ����ϴ�.")
                    break
                except Exception as e:
                    await ctx.send(f"{member.mention}, ������ �߻��߽��ϴ�(team_split): {e}")
                    break
            else:
                await add_new_lol_account(member, ctx)
                break
    await ctx.send(f"��� ����� ���������� �������ϴ�. \"!team_split\"������� ���� �����ϼ���!\n")



# ��������
@client.command(name='team_split', help = "����ڵ��� �� ������ ������ �� ���� �������� �����ִ� ��ɾ��Դϴ�.")
async def assign_teams(ctx, selected_accounts):

    # �Ҵ�� �÷��̾� ������ ���� ����Ʈ
    assigned_players = []
    global red_team, blue_team
    

    # ����, ����, �̵� �����ǿ� ���� �÷��̾� ����
    for position, position_name in [('����', 'jug'), ('����', 'sup'), ('�̵�', 'mid')]:
        position_players = [player for player in selected_accounts if position in player.preferred_roles and player not in assigned_players]

        if len(position_players) < 2:
            await ctx.send(f"{position} ������ �����ϴµ� ������ �߻��߽��ϴ�. {position}�� ��ȣ�ϴ� ������ 2�� �̻��̾�� �մϴ�. �ٽ� �� �г����� �������ּ���.")
            print(f"{position} ������ �����ϴµ� ������ �߻��߽��ϴ�. {position}�� ��ȣ�ϴ� ������ 2�� �̻��̾�� �մϴ�. �ٽ� �� �г����� �������ּ���.")
            return

        # �� �÷��̾� ���� ��ũ ���� ���̰� ���� ���� ������ ã��
        position_dis_min = float('inf')
        for i in range(len(position_players)):
            for j in range(i + 1, len(position_players)):
                dis = abs(position_players[i].rankScore - position_players[j].rankScore)
                if dis < position_dis_min:
                    position_dis_min = dis
                    selected_pair = (position_players[i], position_players[j])

        if position_dis_min > 7:
            await ctx.send(f"{position} ������ �Ƿ� ���̰� Ů�ϴ�. �ٽ� �� �г����� �������ּ���.")
            print(f"{position} ������ �Ƿ� ���̰� Ů�ϴ�. �ٽ� �� �г����� �������ּ���.")
            return
        else:
            if position_name == 'jug':
                red_jug, blue_jug = selected_pair
            elif position_name == 'sup':
                red_sup, blue_sup = selected_pair
            elif position_name == 'mid':
                red_mid, blue_mid = selected_pair

            # �Ҵ�� �÷��̾ ���� ����Ʈ�� �߰�
            assigned_players.extend(selected_pair)

    # �� �Ҵ�
    red_team = [red_jug, red_sup, red_mid]
    blue_team = [blue_jug, blue_sup, blue_mid]

    # ���� �÷��̾�� �߰�
    remaining_players = [player for player in selected_accounts if player not in assigned_players]
    for player in remaining_players:
        if len(red_team) < 5:
            red_team.append(player)
        elif len(blue_team) < 5:
            blue_team.append(player)
            
    # �� ������ ���
    await ctx.send("[������ ������]")
    print("������ ������")
    for member in red_team:
        await ctx.send(member.nickname)
        print(member.nickname)

    await ctx.send("[����� ������]")
    print("����� ������:")
    for member in blue_team:
        await ctx.send(member.nickname)
        print(member.nickname)

    # �� ������ ����
    red_team = [member for member in red_team]
    blue_team = [member for member in blue_team]

    await ctx.send("�� ���� �Ϸ�. '!move_teams' ��ɾ ����Ͽ� ������� ���� ä�η� �̵���ų �� �ֽ��ϴ�.")

@client.command(name='move_teams', help = "������ ���� �������� �� ���� ����ä�ù����� �ѹ��� �̵���Ű�� ��ɾ��Դϴ�.")
async def move_teams_to_channels(ctx):
    red_voice_channel = discord.utils.get(ctx.guild.voice_channels, name='����')
    blue_voice_channel = discord.utils.get(ctx.guild.voice_channels, name='���')

    # ���� �� �̵�
    if red_voice_channel:
        for member in red_team:
            discord_member = ctx.guild.get_member(member.discord_id)
            if discord_member:
                try:
                    await discord_member.move_to(red_voice_channel)
                    await ctx.send(f"{member.nickname}��(��) ���� ä�η� �̵����׽��ϴ�.")
                except discord.errors.HTTPException:
                    await ctx.send(f"{member.nickname}��(��) ���� ä�η� �̵����� ���߽��ϴ�.")

    # ��� �� �̵�
    if blue_voice_channel:
        for member in blue_team:
            discord_member = ctx.guild.get_member(member.discord_id)
            if discord_member:
                try:
                    await discord_member.move_to(blue_voice_channel)
                    await ctx.send(f"{member.nickname}��(��) ��� ä�η� �̵����׽��ϴ�.")
                except discord.errors.HTTPException:
                    await ctx.send(f"{member.nickname}��(��) ��� ä�η� �̵����� ���߽��ϴ�.")

    await ctx.send("��� �� ����� �̵��� �Ϸ��߽��ϴ�.")

############################
# �׽�Ʈ�� ���� �ӽ� LolAccount ��ü ����
def create_test_accounts(n):
    test_accounts = []
    for i in range(n):
        account = LolAccount(f"hideonbush{i}")
        account.rankScore = i  # �׽�Ʈ�� ���� ������ ��ũ ���� �ο�
        account.preferred_roles = ["����", "�̵�", "����"][i % 3]  # ���÷� �� ���� �������� ��ȯ������ �Ҵ�
        test_accounts.append(account)
    return test_accounts


# �׽�Ʈ �Լ� ȣ��
@client.command(name='test_team_split', help = "�ǽð����� 10���� ���� team_split�� ����� Ȯ������ ���� �̸� �׽�Ʈ�ϱ� ���� ��ɾ��Դϴ�.")
async def team_split_test(ctx):

    await ctx.send(f"���ݺ��� \"!team_split\"�� ���� �׽�Ʈ�մϴ�.\n\n")    
    # �׽�Ʈ ���� ����
    test_accounts = create_test_accounts(10)  # ���÷� 10���� �׽�Ʈ ���� ����
    # �׽�Ʈ ������ ���
    selected_accounts = test_accounts

    await assign_teams(ctx,selected_accounts)
    await ctx.send(f"**�׽�Ʈ ��\n\n")


@client.command(name='remove_account', help = "����� �� ���� �� ������� �ϴ� �����͸� �����ϱ� ���� ��ɾ��Դϴ�.")
async def remove_account(ctx):
    # ���� ID ��������
    member_id = ctx.author.id
    global user_lol_accounts
    user_lol_accounts = load_data_from_file('user_accounts.json')
    # ������ �� ���� ��� Ȯ��
    if member_id not in user_lol_accounts or not user_lol_accounts[member_id]:
        await ctx.send("��ϵ� �� ������ �����ϴ�.")
        return

    # �� �г��� ��� ���
    accounts = user_lol_accounts[member_id]
    account_list = "\n".join([f"{idx+1}. {account.nickname}" for idx, account in enumerate(accounts)])
    await ctx.send(f"������ �� ������ �������ּ���:\n{account_list}\n��ȣ�� �Է��ϰų�, ����Ϸ��� '0'�� �Է��ϼ���.")

    try:
        # ���� ���� ��ٸ���
        response = await client.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60.0)

        if response.content == '0':
            await ctx.send("��ҵǾ����ϴ�.")
            return

        # �Էµ� ��ȣ Ȯ��
        if response.content.isdigit() and 1 <= int(response.content) <= len(accounts):
            selected_index = int(response.content) - 1
            deleted_nickname = accounts[selected_index].nickname
            del accounts[selected_index]  # ���õ� ���� ����
            await ctx.send(f"{deleted_nickname} ������ �����Ǿ����ϴ�.")
              
            # ����� ������ ����
            accounts_data = {uid: [acc.to_dict() for acc in accounts] for uid, accounts in user_lol_accounts.items()}
            save_data_to_file(accounts_data, 'user_accounts.json')
        else:
            await ctx.send("�߸��� �Է��Դϴ�.")
    except asyncio.TimeoutError:
        await ctx.send("�ð��� �ʰ��Ǿ����ϴ�.")


async def add_new_lol_account(member, ctx):
    while True:
        await ctx.send(f"{member.mention}, �� �� ���� �г����� �Է����ּ���. (����Ϸ��� '0'�� �Է�)")

        try:
            response = await client.wait_for('message', check=lambda m: m.author == member and m.channel == ctx.channel, timeout=60.0)

            if response.content == '0':
                break

            account = LolAccount(response.content, member.id)
            account.update_account_info()
            # ��ȣ�ϴ� ���� �Է�
            while True:
                
                await ctx.send(f"{account.nickname}��, ��ȣ�ϴ� ������ �Է��ϼ��� (�޸��� ����, ��: ž,�̵�): ")
                response = await client.wait_for('message', timeout=60.0)
                preferred_roles = [role.strip().lower() for role in response.content.split(',')]
                if all(role in ['ž', '����', '�̵�', '����', '����'] for role in preferred_roles):
                    account.preferred_roles = preferred_roles
                    break
                else:
                    await ctx.send("�ùٸ� ������ �Է��ϼ���.")

            global user_lol_accounts
            print(len(user_lol_accounts))
            account.accountsIndex = len(user_lol_accounts) - 1
            user_lol_accounts[member.id] = user_lol_accounts.get(member.id, []) + [account]
            accounts_data = {uid: [acc.to_dict() for acc in accounts] for uid, accounts in user_lol_accounts.items()}
            save_data_to_file(accounts_data, 'user_accounts.json')
            await ctx.send(f"{response.content}�� ���� �����͸� �����߽��ϴ�.")
            break
        except asyncio.TimeoutError:
            await ctx.send(f"{member.mention}, �ð��� �ʰ��Ǿ����ϴ�.")
        except Exception as e:
            await ctx.send(f"{member.mention}, ������ �߻��߽��ϴ�(add_new_lol_account): {e}")


def get_champion_mapping(api_key, region='kr'): #è�Ǿ� �̸� ����
    lol_watcher = LolWatcher(api_key)
    latest_version = lol_watcher.data_dragon.versions_for_region(region)['n']['champion']
    champions = lol_watcher.data_dragon.champions(latest_version, False, 'en_US')['data']
    return {data['key']: name for name, data in champions.items()}
champion_mapping = get_champion_mapping(riot_api_key)


@client.command(name='show_accounts', help = "����Ǿ� �ִ� ��ü �� ���� ������ �������� �����ִ� ��ɾ��Դϴ�.") # ����� ��ü ���� ���
async def show_accounts(ctx):
    user_lol_accounts = load_data_from_file('user_accounts.json')
    for member_id, accounts in user_lol_accounts.items():
        member = ctx.guild.get_member(member_id)
        if member is None or not accounts:
            continue

        account_info = "\n".join([
            f"�г���: {account.nickname}, ��ȣ ������: {', '.join(account.preferred_roles)}, "
            f"�ַη�ũ Ƽ��: {account.solo_rank_tier, account.solo_rank_rank}, �ַη�ũ ����Ʈ: {account.solo_rank_points}, "
            f"������ũ Ƽ��: {account.flex_rank_tier, account.flex_rank_rank}, ������ũ ����Ʈ: {account.flex_rank_points}, "
            f"��ũ ���� : {account.rankScore}, �·�: {account.win_rate}%, ���õ� ���� è�Ǿ�: {', '.join(account.get_top_champion_names(champion_mapping))}"
            for account in accounts
        ])

        response = f"{member.mention}�� �� ����:\n{account_info}"
        await ctx.send(response)


# �� ����
client.run(discord_bot_token)