
# 롤 내전 디스코드 봇 🎮

## 👋소개

이 디스코드 봇은 League of Legends(롤) 게임을 위한 팀 생성, 롤 계정 데이터 관리, 음성 채널 이동 등의 기능을 제공합니다. 사용자들이 쉽게 팀을 나누고 게임을 즐길 수 있도록 도와주는 도구입니다.

## 🚀 기능

- **팀 구성**: 10명의 사용자를 5:5로 팀으로 나누고, 각 팀은 탑, 정글, 미드, 원딜, 서폿으로 나뉩니다.
-   **롤 계정 데이터 관리**: 롤 API를 통해 사용자 닉네임 별로 데이터를 가져와 사용자에 따른 롤 계정 정보 관리 기능
-   **음성 채널 이동**: 생성된 팀을 각각의 음성 채널로 이동시키는 기능

## 🔧설치 및 실행

1.  Python 설치: Python 3.7 이상 버전이 필요합니다.
2.  필요한 패키지 설치:
   
```
  pip install discord.py
  pip install riotwatcher
  pip install PyYAML
```
3.  `config.yml` 파일에 필요한 디스코드 봇 토큰과 Riot API 키를 저장합니다.
4.  스크립트를 실행하여 봇을 시작합니다:
    
```
  python module1.py`
```

5. 음성채팅방 3개를 만들고, 각각 "로비", "블루", "레드"라고 이름을 지어주세요.
6. 모든 사용자들(10명)은 "로비"음성채팅방에 입장해주세요.
7. `!user_setting`을 통해 각자 사용할 롤 계정을 선택합니다.
8. `!team_split`을 통해 5:5로 두 팀으로 나눕니다.
9. `!move_teams`를 통해 각 팀별 음성채팅방으로 이동합니다.

## 📖 사용법

-   `!help`: 사용 가능한 모든 명령어와 각 명령어의 사용 방법을 보여줍니다.
-   `!intro`: 봇의 기능 및 정보를 보여주는 소개 메시지를 보냅니다.
-   `!user_setting`: 사용자별로 롤 계정을 추가하고 선택합니다.
-   `!team_split`: 선택된 롤 계정을 기반으로 사용자들을 두 팀으로 나눕니다.
-   `!move_teams`: 생성된 두 팀을 각각의 음성 채널로 이동시킵니다.
-   `!remove_account`: 저장된 롤 계정 중 하나를 삭제합니다.
-   `!show_accounts`: 저장된 모든 롤 계정 정보를 유저별로 보여줍니다.

자세한 명령어 및 봇 사용 방법은 봇 내부의 도움말을 참고하세요.

## 🌟 추가 기능 (예정)

- **팀원 교환**: 상황에 따른 팀원 간 교환을 진행합니다.

- **플레이 시간 기록**: 롤을 플레이하는 시간을 측정하여 내전 베팅용 포인트로 활용하는 기능 (추후 구현 예정).

- **내전 데이터 저장**: 게임 종료 후 각 사용자의 내전 데이터(승/패, K/D/A 등)를 저장합니다.

- **내전 기록 조회**: 특정 명령어를 통해 사용자의 내전 기록을 확인

## 📜라이센스
이 프로젝트는 [MIT 라이센스](https://chat.openai.com/c/LICENSE) 하에 라이선스가 부여됩니다.


## 👩‍💻 개발자

-   이름: Kim YoungBeen
-   이메일: coldburgundy@gmail.com
-   버전: v0.7.0

프로젝트에 대한 질문이나 문의사항이 있다면 언제든지 연락해주세요!
