# -*- coding: cp949 -*- 

import discord
from discord.ext import commands
from riotwatcher import LolWatcher, ApiError
import asyncio
import json
import yaml
with open('config.yml') as f:
    keys = yaml.load(f, Loader=yaml.FullLoader)

# Riot API 키와 디스코드 봇 토큰 설정
discord_bot_token = keys['keys']['discord_bot_token']
riot_api_key = keys['keys']['riot_api_key']

class CustomHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, **options):
        super().__init__(**options)

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="도움말", description="`!help [명령어]`형식으로 해당 명령어에 대한 도움말을 볼 수 있습니다.", color=0x00ff00)
        for cog, commands in mapping.items():
            filtered = await self.filter_commands(commands, sort=True)
            command_signatures = [self.get_command_signature(c) for c in filtered]
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "명령어 목록")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=self.get_command_signature(command), description=command.help or "설명 없음", color=0x00ff00)
        channel = self.get_destination()
        await channel.send(embed=embed)

# Riot API와 디스코드 클라이언트 초기화
lol_watcher = LolWatcher(riot_api_key)
client = commands.Bot(command_prefix='!', intents=discord.Intents.all(), help_command=CustomHelpCommand())

# 각 디스코드 사용자의 롤 계정을 저장하는 딕셔너리
user_lol_accounts = {}  # key: discord user id, value: list of LolAccount objects

# 유저들이 선택한 롤 계정을 저장할 리스트
selected_accounts = []

now_human = 1 # 현재 인원 수
need_human =1 # 필요한 사람 수. 원래 10명인데 테스트를 위해 값을 바꿔보자.

# 전역 변수로 팀 데이터를 저장
red_team = []
blue_team = []

@client.command(name='intro')
async def send_intro(ctx):
    embed = discord.Embed(
        title="디스코드 봇 소개",
        description="안녕하세요! 저는 League of Legends 팀 생성을 도와주는 디스코드 봇입니다.",
        color=0x00ff00
    )
    embed.add_field(name="기능", value="팀 자동 분할, 롤 계정 데이터 관리, 음성 채널 이동 등", inline=False)
    embed.add_field(name="사용 방법", value="`!help` 명령어로 모든 명령어와 사용 방법을 확인하세요.", inline=False)
    embed.add_field(name="개발자", value="[Kim YoungBeen | coldburgundy@gmail.com]", inline=False)
    embed.add_field(name="버전", value="v0.7.0", inline=False)

    await ctx.send(embed=embed)


# 데이터 저장
def save_data_to_file(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"파일 저장 중 오류 발생: {e}")

# 데이터 불러오기
def load_data_from_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if not data:
                return {}
       
        loaded_data = {}
        for uid, accounts_data in data.items():
            loaded_accounts = [LolAccount.from_dict(account_data) for account_data in accounts_data]
            # 각 계정에 순차적으로 인덱스 부여
            for index, account in enumerate(loaded_accounts):
                account.accountsIndex = index
            # 변환된 계정 리스트를 loaded_data에 저장
            loaded_data[int(uid)] = loaded_accounts
  
        return loaded_data
    
    except FileNotFoundError:
        # 파일이 없을 경우 빈 파일 생성
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump({}, file, ensure_ascii=False, indent=4)
        return {}
    except json.JSONDecodeError as e:
        print(f"JSON 파일 형식 오류: {e}")
        return {}
    except IOError as e:
        print(f"파일 읽기 중 오류 발생: {e}")
        return {}
        
# 롤 계정 객체 정의
class LolAccount:
    def __init__(self, nickname, discord_id = None):
        self.discord_id = discord_id
        self.accountsIndex = None
        self.nickname = nickname
        self.preferred_roles = []  # 선호하는 라인
        self.assigned_role = None  # 결정된 포지션
        self.team = None  # 소속된 팀
        self.solo_rank_tier = None  # 솔로랭크 티어
        self.solo_rank_rank = None  # 솔로랭크 로마숫자
        self.solo_rank_points = None  # 솔로랭크 포인트
        self.flex_rank_tier = None  # 자유랭크 티어
        self.flex_rank_rank = None  # 자유랭크 로마숫자
        self.flex_rank_points = None  # 자유랭크 포인트
        self.rankScore = None # 랭크 수치화
        self.win_rate = None  # 랭크게임 승률
        self.top_champions = []  # 숙련도 높은 챔피언 5개
        self.update_account_info()

    def update_account_info(self):
        try:
            # 소환사 정보 가져오기
            summoner_info = lol_watcher.summoner.by_name('kr', self.nickname)

            # 랭크 정보 가져오기
            ranked_stats = lol_watcher.league.by_summoner('kr', summoner_info['id'])

            self.solo_rank_tier = None
            self.flex_rank_tier = None
            total_wins = 0
            total_losses = 0

            # 솔로랭크 및 자유랭크 정보 추출
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
                    
            # 티어를 숫자로 변환하는 함수
            def tier_to_number(tier):
                tiers = ["None", "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
                return tiers.index(tier) * 10 if tier in tiers else 0

            # 서브티어를 숫자로 변환하는 함수
            def rank_to_number(rank):
                ranks = {"None" : -1, "IV": 0, "III": 2.5, "II": 5, "I": 7.5}
                return ranks.get(rank, 0)

            # 랭크 점수 계산
            def calculate_rank_score(tier, rank, points):
                if tier_to_number(tier) == 0:
                    return 0
                return tier_to_number(tier) + rank_to_number(rank) + (points / 100)

            # 솔로랭크 점수 계산
            solo_rank_score = calculate_rank_score(self.solo_rank_tier, self.solo_rank_rank, self.solo_rank_points)

            # 자유랭크 점수 계산
            flex_rank_score = calculate_rank_score(self.flex_rank_tier, self.flex_rank_rank, self.flex_rank_points)

            # 최종 랭크 점수
            self.rankScore = solo_rank_score * 0.7 + flex_rank_score * 0.3
            
            '''

            # 숙련도 높은 챔피언 정보 가져오기
            mastery_info = lol_watcher.champion_mastery.by_summoner('kr', summoner_info['id'])
            self.top_champions = [mastery['championId'] for mastery in mastery_info[:5]]

            '''
            # 전체 랭크 게임 승률 계산
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




# 유저 세팅
@client.command(name='user_setting', help = "사용자에 따라 롤 계정 데이터 추가와 사용할 계정 선택을 위한 명령어입니다.")
async def team_split(ctx):
    lobby_channel = discord.utils.get(ctx.guild.voice_channels, name='로비') # 테스트중
    red_channel = discord.utils.get(ctx.guild.voice_channels, name='레드')
    blue_channel = discord.utils.get(ctx.guild.voice_channels, name='블루')
    
    global user_lol_accounts
    user_lol_accounts = load_data_from_file('user_accounts.json')
    members = lobby_channel.members
    now_human = len(members) # 디버깅할 때 적절하게 조절하기
    if now_human != need_human:
        await ctx.send(f"로비에 {need_human-now_human}명의 유저가 필요합니다. (현재 {now_human}명/{need_human}명)")
        return
    
    await ctx.send(f"로비에 {need_human}명의 유저가 있습니다. 각 유저에 대해 데이터를 확인합니다.\n")

    # 각 사용자의 롤 계정 정보 확인 및 추가
    for member in members:
        while True:
            user_lol_accounts = load_data_from_file('user_accounts.json')
            if member.id in user_lol_accounts:
                accounts = user_lol_accounts[member.id]
                account_list = "\n".join([f"{idx+1}: {account.nickname}" for idx, account in enumerate(accounts)])
                await ctx.send(f"{member.mention}, 현재 등록된 롤 계정 목록:\n{account_list}\n사용할 계정 번호를 입력하거나, 새 계정을 추가하려면 'new'를 입력하세요. (건너뛰려면 '0'을 입력)")

                try:
                    response = await client.wait_for('message', check=lambda m: m.author == member and m.channel == ctx.channel, timeout=60.0)

                    if response.content.lower() == 'new':
                        await add_new_lol_account(member, ctx)
                    elif response.content == '0':
                        break
                    elif response.content.isdigit() and 1 <= int(response.content) <= len(accounts):
                        selected_index = int(response.content) - 1
                        # 선택된 계정에 대한 추가 처리 (예: 팀 할당)
                        global selected_accounts
                        selected_accounts.append(accounts[selected_index])
                        await ctx.send(f"{member.display_name}님의 선택: {accounts[selected_index].nickname}")
                        print(f"{member.display_name}님의 선택: {accounts[selected_index].nickname}")
                        break
                    else:
                        await ctx.send(f"{member.mention}, 잘못된 입력입니다. 다시 시도해주세요.")
                except asyncio.TimeoutError:
                    await ctx.send(f"{member.mention}, 시간이 초과되었습니다.")
                    break
                except Exception as e:
                    await ctx.send(f"{member.mention}, 에러가 발생했습니다(team_split): {e}")
                    break
            else:
                await add_new_lol_account(member, ctx)
                break
    await ctx.send(f"모든 사람의 계정선택이 끝났습니다. \"!team_split\"명령으로 팀을 구성하세요!\n")



# 팀나누기
@client.command(name='team_split', help = "사용자들을 두 팀으로 나누고 각 팀의 구성원을 보여주는 명령어입니다.")
async def assign_teams(ctx, selected_accounts):

    # 할당된 플레이어 추적을 위한 리스트
    assigned_players = []
    global red_team, blue_team
    

    # 정글, 서폿, 미드 포지션에 대한 플레이어 선택
    for position, position_name in [('정글', 'jug'), ('서폿', 'sup'), ('미드', 'mid')]:
        position_players = [player for player in selected_accounts if position in player.preferred_roles and player not in assigned_players]

        if len(position_players) < 2:
            await ctx.send(f"{position} 라인을 선택하는데 문제가 발생했습니다. {position}을 선호하는 유저가 2명 이상이어야 합니다. 다시 롤 닉네임을 선택해주세요.")
            print(f"{position} 라인을 선택하는데 문제가 발생했습니다. {position}을 선호하는 유저가 2명 이상이어야 합니다. 다시 롤 닉네임을 선택해주세요.")
            return

        # 두 플레이어 간의 랭크 점수 차이가 가장 작은 조합을 찾기
        position_dis_min = float('inf')
        for i in range(len(position_players)):
            for j in range(i + 1, len(position_players)):
                dis = abs(position_players[i].rankScore - position_players[j].rankScore)
                if dis < position_dis_min:
                    position_dis_min = dis
                    selected_pair = (position_players[i], position_players[j])

        if position_dis_min > 7:
            await ctx.send(f"{position} 라인의 실력 차이가 큽니다. 다시 롤 닉네임을 선택해주세요.")
            print(f"{position} 라인의 실력 차이가 큽니다. 다시 롤 닉네임을 선택해주세요.")
            return
        else:
            if position_name == 'jug':
                red_jug, blue_jug = selected_pair
            elif position_name == 'sup':
                red_sup, blue_sup = selected_pair
            elif position_name == 'mid':
                red_mid, blue_mid = selected_pair

            # 할당된 플레이어를 추적 리스트에 추가
            assigned_players.extend(selected_pair)

    # 팀 할당
    red_team = [red_jug, red_sup, red_mid]
    blue_team = [blue_jug, blue_sup, blue_mid]

    # 남은 플레이어들 추가
    remaining_players = [player for player in selected_accounts if player not in assigned_players]
    for player in remaining_players:
        if len(red_team) < 5:
            red_team.append(player)
        elif len(blue_team) < 5:
            blue_team.append(player)
            
    # 팀 구성원 출력
    await ctx.send("[레드팀 구성원]")
    print("레드팀 구성원")
    for member in red_team:
        await ctx.send(member.nickname)
        print(member.nickname)

    await ctx.send("[블루팀 구성원]")
    print("블루팀 구성원:")
    for member in blue_team:
        await ctx.send(member.nickname)
        print(member.nickname)

    # 팀 구성원 저장
    red_team = [member for member in red_team]
    blue_team = [member for member in blue_team]

    await ctx.send("팀 분할 완료. '!move_teams' 명령어를 사용하여 멤버들을 음성 채널로 이동시킬 수 있습니다.")

@client.command(name='move_teams', help = "생성된 팀을 바탕으로 각 팀의 음성채팅방으로 한번에 이동시키는 명령어입니다.")
async def move_teams_to_channels(ctx):
    red_voice_channel = discord.utils.get(ctx.guild.voice_channels, name='레드')
    blue_voice_channel = discord.utils.get(ctx.guild.voice_channels, name='블루')

    # 레드 팀 이동
    if red_voice_channel:
        for member in red_team:
            discord_member = ctx.guild.get_member(member.discord_id)
            if discord_member:
                try:
                    await discord_member.move_to(red_voice_channel)
                    await ctx.send(f"{member.nickname}을(를) 레드 채널로 이동시켰습니다.")
                except discord.errors.HTTPException:
                    await ctx.send(f"{member.nickname}을(를) 레드 채널로 이동하지 못했습니다.")

    # 블루 팀 이동
    if blue_voice_channel:
        for member in blue_team:
            discord_member = ctx.guild.get_member(member.discord_id)
            if discord_member:
                try:
                    await discord_member.move_to(blue_voice_channel)
                    await ctx.send(f"{member.nickname}을(를) 블루 채널로 이동시켰습니다.")
                except discord.errors.HTTPException:
                    await ctx.send(f"{member.nickname}을(를) 블루 채널로 이동하지 못했습니다.")

    await ctx.send("모든 팀 멤버의 이동을 완료했습니다.")

############################
# 테스트를 위한 임시 LolAccount 객체 생성
def create_test_accounts(n):
    test_accounts = []
    for i in range(n):
        account = LolAccount(f"hideonbush{i}")
        account.rankScore = i  # 테스트를 위해 간단한 랭크 점수 부여
        account.preferred_roles = ["정글", "미드", "서폿"][i % 3]  # 예시로 세 가지 포지션을 순환적으로 할당
        test_accounts.append(account)
    return test_accounts


# 테스트 함수 호출
@client.command(name='test_team_split', help = "실시간으로 10명보다 적어 team_split의 기능을 확인하지 못해 이를 테스트하기 위한 명령어입니다.")
async def team_split_test(ctx):

    await ctx.send(f"지금부터 \"!team_split\"에 대해 테스트합니다.\n\n")    
    # 테스트 계정 생성
    test_accounts = create_test_accounts(10)  # 예시로 10개의 테스트 계정 생성
    # 테스트 데이터 사용
    selected_accounts = test_accounts

    await assign_teams(ctx,selected_accounts)
    await ctx.send(f"**테스트 끝\n\n")


@client.command(name='remove_account', help = "저장된 롤 계정 중 지우고자 하는 데이터를 삭제하기 위한 명령어입니다.")
async def remove_account(ctx):
    # 유저 ID 가져오기
    member_id = ctx.author.id
    global user_lol_accounts
    user_lol_accounts = load_data_from_file('user_accounts.json')
    # 유저의 롤 계정 목록 확인
    if member_id not in user_lol_accounts or not user_lol_accounts[member_id]:
        await ctx.send("등록된 롤 계정이 없습니다.")
        return

    # 롤 닉네임 목록 출력
    accounts = user_lol_accounts[member_id]
    account_list = "\n".join([f"{idx+1}. {account.nickname}" for idx, account in enumerate(accounts)])
    await ctx.send(f"삭제할 롤 계정을 선택해주세요:\n{account_list}\n번호를 입력하거나, 취소하려면 '0'을 입력하세요.")

    try:
        # 유저 응답 기다리기
        response = await client.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60.0)

        if response.content == '0':
            await ctx.send("취소되었습니다.")
            return

        # 입력된 번호 확인
        if response.content.isdigit() and 1 <= int(response.content) <= len(accounts):
            selected_index = int(response.content) - 1
            deleted_nickname = accounts[selected_index].nickname
            del accounts[selected_index]  # 선택된 계정 삭제
            await ctx.send(f"{deleted_nickname} 계정이 삭제되었습니다.")
              
            # 변경된 데이터 저장
            accounts_data = {uid: [acc.to_dict() for acc in accounts] for uid, accounts in user_lol_accounts.items()}
            save_data_to_file(accounts_data, 'user_accounts.json')
        else:
            await ctx.send("잘못된 입력입니다.")
    except asyncio.TimeoutError:
        await ctx.send("시간이 초과되었습니다.")


async def add_new_lol_account(member, ctx):
    while True:
        await ctx.send(f"{member.mention}, 새 롤 계정 닉네임을 입력해주세요. (취소하려면 '0'을 입력)")

        try:
            response = await client.wait_for('message', check=lambda m: m.author == member and m.channel == ctx.channel, timeout=60.0)

            if response.content == '0':
                break

            account = LolAccount(response.content, member.id)
            account.update_account_info()
            # 선호하는 라인 입력
            while True:
                
                await ctx.send(f"{account.nickname}님, 선호하는 라인을 입력하세요 (콤마로 구분, 예: 탑,미드): ")
                response = await client.wait_for('message', timeout=60.0)
                preferred_roles = [role.strip().lower() for role in response.content.split(',')]
                if all(role in ['탑', '정글', '미드', '원딜', '서폿'] for role in preferred_roles):
                    account.preferred_roles = preferred_roles
                    break
                else:
                    await ctx.send("올바른 라인을 입력하세요.")

            global user_lol_accounts
            print(len(user_lol_accounts))
            account.accountsIndex = len(user_lol_accounts) - 1
            user_lol_accounts[member.id] = user_lol_accounts.get(member.id, []) + [account]
            accounts_data = {uid: [acc.to_dict() for acc in accounts] for uid, accounts in user_lol_accounts.items()}
            save_data_to_file(accounts_data, 'user_accounts.json')
            await ctx.send(f"{response.content}에 대한 데이터를 저장했습니다.")
            break
        except asyncio.TimeoutError:
            await ctx.send(f"{member.mention}, 시간이 초과되었습니다.")
        except Exception as e:
            await ctx.send(f"{member.mention}, 에러가 발생했습니다(add_new_lol_account): {e}")


def get_champion_mapping(api_key, region='kr'): #챔피언 이름 맵핑
    lol_watcher = LolWatcher(api_key)
    latest_version = lol_watcher.data_dragon.versions_for_region(region)['n']['champion']
    champions = lol_watcher.data_dragon.champions(latest_version, False, 'en_US')['data']
    return {data['key']: name for name, data in champions.items()}
champion_mapping = get_champion_mapping(riot_api_key)


@client.command(name='show_accounts', help = "저장되어 있는 전체 롤 계정 정보를 유저별로 보여주는 명령어입니다.") # 저장된 전체 계정 출력
async def show_accounts(ctx):
    user_lol_accounts = load_data_from_file('user_accounts.json')
    for member_id, accounts in user_lol_accounts.items():
        member = ctx.guild.get_member(member_id)
        if member is None or not accounts:
            continue

        account_info = "\n".join([
            f"닉네임: {account.nickname}, 선호 포지션: {', '.join(account.preferred_roles)}, "
            f"솔로랭크 티어: {account.solo_rank_tier, account.solo_rank_rank}, 솔로랭크 포인트: {account.solo_rank_points}, "
            f"자유랭크 티어: {account.flex_rank_tier, account.flex_rank_rank}, 자유랭크 포인트: {account.flex_rank_points}, "
            f"랭크 점수 : {account.rankScore}, 승률: {account.win_rate}%, 숙련도 높은 챔피언: {', '.join(account.get_top_champion_names(champion_mapping))}"
            for account in accounts
        ])

        response = f"{member.mention}의 롤 계정:\n{account_info}"
        await ctx.send(response)


# 봇 실행
client.run(discord_bot_token)