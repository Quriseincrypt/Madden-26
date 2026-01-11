import pygame
import random
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# =========================
# CONFIG / CONSTANTS
# =========================

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 360
FPS = 60

NFL_SEASON_GAMES = 17
NFL_PLAYOFF_TEAMS = 14
MAX_CAREER_YEARS = 80

AWARDS = [
    "MVP",
    "Offensive Player of the Year",
    "Defensive Player of the Year",
    "Rookie of the Year",
    "Super Bowl MVP",
]

POSITIONS = ["QB", "WR", "RB", "TE", "LB"]

INJURY_CHANCE_PER_GAME = 0.05
SEVERE_INJURY_CHANCE = 0.2

MAX_OVERALL = 99
MIN_OVERALL = 40


# =========================
# DATA CLASSES
# =========================

@dataclass
class Injury:
    description: str
    weeks_out: int
    severe: bool = False


@dataclass
class Contract:
    years: int
    salary_per_year: float
    current_year: int = 1

    def advance_year(self):
        if self.years > 0:
            self.current_year += 1
            self.years -= 1

    def is_expired(self) -> bool:
        return self.years <= 0


@dataclass
class Player:
    name: str
    position: str
    age: int
    team_id: Optional[int] = None
    overall: int = 70
    is_captain: bool = False
    is_custom: bool = False
    retired: bool = False

    contract: Optional[Contract] = None
    injury: Optional[Injury] = None
    career_years: int = 0
    accolades: List[str] = field(default_factory=list)
    hall_of_fame: bool = False

    last_season_stats: Dict[str, int] = field(default_factory=dict)
    career_stats: Dict[str, int] = field(default_factory=dict)

    def healthy(self) -> bool:
        return self.injury is None or self.injury.weeks_out <= 0

    def tick_injury(self):
        if self.injury:
            self.injury.weeks_out -= 1
            if self.injury.weeks_out <= 0:
                self.injury = None

    def apply_injury(self):
        if random.random() < INJURY_CHANCE_PER_GAME:
            severe = random.random() < SEVERE_INJURY_CHANCE
            weeks = random.randint(1, 4) if not severe else random.randint(5, 20)
            desc = "sprain" if not severe else "torn ligament"
            self.injury = Injury(description=desc, weeks_out=weeks, severe=severe)

    def update_overall_from_stats(self):
        stats = self.last_season_stats
        if not stats:
            return

        score = 0
        score += stats.get("yards_pass", 0) / 100
        score += stats.get("td_pass", 0) * 2
        score += stats.get("yards_rush", 0) / 50
        score += stats.get("td_rush", 0) * 2
        score += stats.get("tackles", 0) / 5

        delta = max(-5, min(10, int(score / 20)))
        self.overall = max(MIN_OVERALL, min(MAX_OVERALL, self.overall + delta))

    def maybe_retire(self):
        self.career_years += 1

        base_retire = 0
        if self.age >= 35:
            base_retire += (self.age - 34) * 5
        if self.overall < 60:
            base_retire += 10
        if self.career_years > 15:
            base_retire += (self.career_years - 15) * 3

        roll = random.randint(1, 100)
        if roll <= base_retire:
            self.retired = True
        else:
            self.age += 1

    def evaluate_hof(self):
        sb_mvps = len([a for a in self.accolades if "Super Bowl MVP" in a])
        mvps = len([a for a in self.accolades if "MVP" in a])
        yards_pass = self.career_stats.get("yards_pass", 0)
        yards_rush = self.career_stats.get("yards_rush", 0)
        tackles = self.career_stats.get("tackles", 0)

        if mvps >= 2 or sb_mvps >= 2:
            self.hall_of_fame = True
        elif yards_pass > 60000 or yards_rush > 15000 or tackles > 2000:
            self.hall_of_fame = True


@dataclass
class GM:
    name: str
    team_id: int

    def praise_player(self, player: Player, accolade: str) -> str:
        return f"{self.name}: Great job, {player.name}! That {accolade} is big-time."

    def announce_captain(self, player: Player) -> str:
        return f"{self.name}: {player.name}, you’ve been named a team captain."

    def talk_trade(self, player: Player, requested: bool = False) -> str:
        if requested:
            return f"{self.name}: We heard your trade request, {player.name}. We’ll explore options."
        else:
            return f"{self.name}: {player.name}, we’ve decided to move you in a trade."


@dataclass
class Team:
    id: int
    name: str
    city: str
    gm: GM
    conference: str = "AFC"
    division: str = "East"
    players: List[Player] = field(default_factory=list)
    wins: int = 0
    losses: int = 0

    def add_player(self, player: Player):
        player.team_id = self.id
        self.players.append(player)

    def remove_player(self, player: Player):
        self.players = [p for p in self.players if p is not player]
        player.team_id = None

    def reset_record(self):
        self.wins = 0
        self.losses = 0

    def record_win(self):
        self.wins += 1

    def record_loss(self):
        self.losses += 1

    def random_captain_update(self) -> Optional[Player]:
        candidates = [p for p in self.players if not p.retired]
        if not candidates:
            return None
        weights = [p.overall for p in candidates]
        new_captain = random.choices(candidates, weights=weights, k=1)[0]
        for p in self.players:
            p.is_captain = False
        new_captain.is_captain = True
        return new_captain


# =========================
# LEAGUE / SEASON
# =========================

@dataclass
class SeasonResult:
    year: int
    champion_team_id: Optional[int] = None
    stats_by_player: Dict[int, Dict[str, int]] = field(default_factory=dict)
    awards: Dict[str, int] = field(default_factory=dict)


@dataclass
class League:
    teams: List[Team]
    year: int = 2025
    season_history: List[SeasonResult] = field(default_factory=list)

    def _all_players(self) -> List[Player]:
        players = []
        for t in self.teams:
            players.extend(t.players)
        return players

    def _get_team_by_id(self, tid: Optional[int]) -> Optional[Team]:
        for t in self.teams:
            if t.id == tid:
                return t
        return None

    def _add_stats(self, stats: Dict[int, Dict[str, int]], player: Player, to_add: Dict[str, int]):
        pid = id(player)
        if pid not in stats:
            stats[pid] = {}
        for k, v in to_add.items():
            stats[pid][k] = stats[pid].get(k, 0) + v

    def simulate_regular_season(self) -> Dict[int, Dict[str, int]]:
        for t in self.teams:
            t.reset_record()

        stats = {}

        for game in range(NFL_SEASON_GAMES):
            for i in range(0, len(self.teams), 2):
                if i + 1 >= len(self.teams):
                    break
                home = self.teams[i]
                away = self.teams[i + 1]

                home_score = random.randint(10, 40)
                away_score = random.randint(10, 40)

                if home_score >= away_score:
                    home.record_win()
                    away.record_loss()
                else:
                    away.record_win()
                    home.record_loss()

                for team in [home, away]:
                    for p in team.players:
                        if p.retired:
                            continue
                        if not p.healthy():
                            p.tick_injury()
                            continue

                        if p.position == "QB":
                            yds = random.randint(0, 400)
                            tds = random.randint(0, 4)
                            self._add_stats(stats, p, {"yards_pass": yds, "td_pass": tds})

                        elif p.position in ("RB", "WR", "TE"):
                            yds = random.randint(0, 200)
                            tds = random.randint(0, 3)
                            if p.position == "RB":
                                self._add_stats(stats, p, {"yards_rush": yds, "td_rush": tds})
                            else:
                                self._add_stats(stats, p, {"yards_rec": yds, "td_rec": tds})

                        elif p.position == "LB":
                            tackles = random.randint(0, 15)
                            self._add_stats(stats, p, {"tackles": tackles})

                        p.apply_injury()

        for p in self._all_players():
            pid = id(p)
            p.last_season_stats = stats.get(pid, {})
            for k, v in p.last_season_stats.items():
                p.career_stats[k] = p.career_stats.get(k, 0) + v

        return stats

    def simulate_playoffs(self) -> int:
        sorted_teams = sorted(self.teams, key=lambda t: t.wins, reverse=True)
        playoff_teams = sorted_teams[:NFL_PLAYOFF_TEAMS]

        while len(playoff_teams) > 1:
            next_round = []
            for i in range(0, len(playoff_teams), 2):
                if i + 1 >= len(playoff_teams):
                    next_round.append(playoff_teams[i])
                    continue
                t1 = playoff_teams[i]
                t2 = playoff_teams[i + 1]
                winner = random.choice([t1, t2])
                next_round.append(winner)
            playoff_teams = next_round

        champion = playoff_teams[0]
        return champion.id

    def assign_awards(self, stats: Dict[int, Dict[str, int]]) -> Dict[str, int]:
        awards_result = {}

        best_pid = None
        best_score = -1
        for p in self._all_players():
            pid = id(p)
            s = stats.get(pid, {})
            score = (
                s.get("yards_pass", 0) / 50
                + s.get("td_pass", 0) * 4
                + s.get("yards_rush", 0) / 25
                + s.get("td_rush", 0) * 4
                + s.get("tackles", 0)
            )
            if score > best_score:
                best_score = score
                best_pid = pid

        if best_pid is not None:
            awards_result["MVP"] = best_pid

        return awards_result

    def off_season_updates(self, season_result: SeasonResult):
        for p in self._all_players():
            if p.retired:
                continue

            p.update_overall_from_stats()
            p.maybe_retire()

            if p.retired:
                p.evaluate_hof()

            if p.contract:
                p.contract.advance_year()
                if p.contract.is_expired() and not p.retired:
                    new_team = random.choice(self.teams)
                    if p.team_id != new_team.id:
                        old_team = self._get_team_by_id(p.team_id)
                        if old_team:
                            old_team.remove_player(p)
                        new_team.add_player(p)
                        p.contract = Contract(
                            years=random.randint(1, 5),
                            salary_per_year=5_000_000,
                        )

    def run_full_season(self) -> SeasonResult:
        stats = self.simulate_regular_season()
        champion_id = self.simulate_playoffs()
        awards = self.assign_awards(stats)

        season = SeasonResult(
            year=self.year,
            champion_team_id=champion_id,
            stats_by_player=stats,
            awards=awards,
        )

        for award_name, pid in awards.items():
            for p in self._all_players():
                if id(p) == pid:
                    p.accolades.append(f"{award_name} {self.year}")

        self.season_history.append(season)
        self.off_season_updates(season)
        self.year += 1
        return season


# =========================
# ROSTER HELPERS
# =========================

NFL_TEAMS = [
    ("Buffalo", "Bills", "AFC", "East"),
    ("Miami", "Dolphins", "AFC", "East"),
    ("New England", "Patriots", "AFC", "East"),
    ("New York", "Jets", "AFC", "East"),
    ("Kansas City", "Chiefs", "AFC", "West"),
    ("Las Vegas", "Raiders", "AFC", "West"),
    ("Los Angeles", "Chargers", "AFC", "West"),
    ("Denver", "Broncos", "AFC", "West"),
    ("Dallas", "Cowboys", "NFC", "East"),
    ("Philadelphia", "Eagles", "NFC", "East"),
    ("New York", "Giants", "NFC", "East"),
    ("Washington", "Commanders", "NFC", "East"),
]

def create_nfl_teams() -> List[Team]:
    teams = []
    for idx, (city, name, conf, div) in enumerate(NFL_TEAMS):
        gm = GM(name=f"{city} GM", team_id=idx)
        team = Team(id=idx, name=name, city=city, gm=gm, conference=conf, division=div)
        teams.append(team)
    return teams

def generate_placeholder_rosters(teams: List[Team]):
    for team in teams:
        qb = Player(
            name=f"{team.city} QB1",
            position="QB",
            age=random.randint(22, 34),
            overall=random.randint(70, 90),
            contract=Contract(years=random.randint(1, 5), salary_per_year=15_000_000),
        )
        team.add_player(qb)

        for i in range(3):
            wr = Player(
                name=f"{team.city} WR{i+1}",
                position="WR",
                age=random.randint(21, 32),
                overall=random.randint(65, 90),
                contract=Contract(years=random.randint(1, 4), salary_per_year=8_000_000),
            )
            team.add_player(wr)

        for i in range(2):
            rb = Player(
                name=f"{team.city} RB{i+1}",
                position="RB",
                age=random.randint(21, 30),
                overall=random.randint(70, 88),
                contract=Contract(years=random.randint(1, 4), salary_per_year=7_000_000),
            )
            team.add_player(rb)

        for i in range(2):
            te = Player(
                name=f"{team.city} TE{i+1}",
                position="TE",
                age=random.randint(22, 32),
                overall=random.randint(68, 88),
                contract=Contract(years=random.randint(1, 4), salary_per_year=6_000_000),
            )
            team.add_player(te)

        for i in range(4):
            lb = Player(
                name=f"{team.city} LB{i+1}",
                position="LB",
                age=random.randint(22, 32),
                overall=random.randint(70, 90),
                contract=Contract(years=random.randint(1, 4), salary_per_year=6_000_000),
            )
            team.add_player(lb)

def create_custom_player(name: str, position: str, age: int = 21, overall: int = 75) -> Player:
    return Player(
        name=name,
        position=position,
        age=age,
        overall=overall,
        is_custom=True,
        contract=Contract(years=4, salary_per_year=5_000_000),
    )

def save_league(league: League, filepath: str):
    def player_to_dict(p: Player) -> dict:
        return {
            "name": p.name,
            "position": p.position,
            "age": p.age,
            "team_id": p.team_id,
            "overall": p.overall,
            "is_captain": p.is_captain,
            "is_custom": p.is_custom,
            "retired": p.retired,
            "contract": {
                "years": p.contract.years,
                "salary_per_year": p.contract.salary_per_year,
                "current_year": p.contract.current_year,
            } if p.contract else None,
            "career_years": p.career_years,
            "accolades": p.accolades,
            "hall_of_fame": p.hall_of_fame,
            "career_stats": p.career_stats,
        }

    def team_to_dict(t: Team) -> dict:
        return {
            "id": t.id,
            "name": t.name,
            "city": t.city,
            "conference": t.conference,
            "division": t.division,
            "gm": {"name": t.gm.name, "team_id": t.gm.team_id},
            "wins": t.wins,
            "losses": t.losses,
# =========================
# MYCAREER MODE
# =========================

class MyCareer:
    def __init__(self, league: League, player: Player):
        self.league = league
        self.player = player
        self.trade_requested = False
        self.messages: List[str] = []

    # -------------------------
    # GM INTERACTIONS
    # -------------------------

    def gm_message(self, text: str):
        """Store a message from the GM to show in menus."""
        self.messages.append(text)

    def check_captaincy(self):
        """If player becomes captain, GM sends a message."""
        team = self.league._get_team_by_id(self.player.team_id)
        if not team:
            return

        new_captain = team.random_captain_update()
        if new_captain and new_captain is self.player:
            msg = team.gm.announce_captain(self.player)
            self.gm_message(msg)

    def request_trade(self):
        """Player asks to be traded."""
        self.trade_requested = True
        team = self.league._get_team_by_id(self.player.team_id)
        if team:
            msg = team.gm.talk_trade(self.player, requested=True)
            self.gm_message(msg)

    def process_trade(self):
        """If trade requested, move player to a random new team."""
        if not self.trade_requested:
            return

        old_team = self.league._get_team_by_id(self.player.team_id)
        new_team = random.choice(self.league.teams)

        if new_team.id == self.player.team_id:
            return  # no change

        if old_team:
            old_team.remove_player(self.player)

        new_team.add_player(self.player)

        # Reset trade request
        self.trade_requested = False

        msg = new_team.gm.talk_trade(self.player, requested=False)
        self.gm_message(msg)

    # -------------------------
    # CAREER PROGRESSION
    # -------------------------

    def play_full_season(self):
        """Simulate a full NFL season and update MyCareer state."""
        # Process trade if requested
        self.process_trade()

        # Run the league season
        season_result = self.league.run_full_season()

        # Check captaincy
        self.check_captaincy()

        # Check if player won any awards
        for award_name, pid in season_result.awards.items():
            if id(self.player) == pid:
                msg = self.league._get_team_by_id(self.player.team_id).gm.praise_player(
                    self.player, award_name
                )
                self.gm_message(msg)

        # Check retirement
        if self.player.retired:
            self.gm_message(f"{self.player.name} has retired from the NFL.")

        return season_result

    # -------------------------
    # CAREER SUMMARY
    # -------------------------

    def get_summary(self) -> Dict[str, any]:
        """Return a dictionary of the player's career info."""
        return {
            "name": self.player.name,
            "position": self.player.position,
            "age": self.player.age,
            "overall": self.player.overall,
            "team_id": self.player.team_id,
            "career_years": self.player.career_years,
            "accolades": self.player.accolades,
            "hall_of_fame": self.player.hall_of_fame,
            "career_stats": self.player.career_stats,
            "messages": self.messages[-10:],  # last 10 messages
        }
# =========================
# RETRO FIELD (PYGAME)
# =========================

class RetroField:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Madden 26 Retro Field")
        self.clock = pygame.time.Clock()

        # Player icon on field
        self.player_x = SCREEN_WIDTH // 2
        self.player_y = SCREEN_HEIGHT // 2
        self.player_speed = 3

    def draw_field(self):
        """Draw a simple retro football field."""
        self.screen.fill((0, 100, 0))  # green field

        # Yard lines
        for x in range(0, SCREEN_WIDTH, 40):
            pygame.draw.line(self.screen, (255, 255, 255), (x, 0), (x, SCREEN_HEIGHT), 1)

        # Hash marks
        for y in range(20, SCREEN_HEIGHT, 40):
            pygame.draw.line(self.screen, (255, 255, 255), (0, y), (SCREEN_WIDTH, y), 1)

        # Player dot
        pygame.draw.circle(self.screen, (255, 255, 0), (self.player_x, self.player_y), 6)

    def handle_input(self):
        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT]:
            self.player_x -= self.player_speed
        if keys[pygame.K_RIGHT]:
            self.player_x += self.player_speed
        if keys[pygame.K_UP]:
            self.player_y -= self.player_speed
        if keys[pygame.K_DOWN]:
            self.player_y += self.player_speed

        # Keep player on screen
        self.player_x = max(0, min(SCREEN_WIDTH, self.player_x))
        self.player_y = max(0, min(SCREEN_HEIGHT, self.player_y))

    def run(self):
        """Main loop for the retro field."""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            self.handle_input()
            self.draw_field()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
# =========================
# MENUS + GAME LAUNCHER
# =========================

class GameMenu:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Madden 26 — Main Menu")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 20)

        # Build league + rosters
        self.teams = create_nfl_teams()
        generate_placeholder_rosters(self.teams)
        self.league = League(self.teams)

        # MyCareer state
        self.myplayer: Optional[Player] = None
        self.mycareer: Optional[MyCareer] = None

    # -------------------------
    # DRAW HELPERS
    # -------------------------

    def draw_text(self, text, x, y, color=(255, 255, 255)):
        surf = self.font.render(text, True, color)
        self.screen.blit(surf, (x, y))

    # -------------------------
    # MAIN MENU
    # -------------------------

    def main_menu(self):
        running = True
        while running:
            self.screen.fill((0, 0, 40))
            self.draw_text("MADDEN 26 — MAIN MENU", 180, 40)
            self.draw_text("1. Start MyCareer", 200, 120)
            self.draw_text("2. Play Retro Field", 200, 160)
            self.draw_text("ESC. Quit", 200, 200)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        self.start_mycareer()
                    if event.key == pygame.K_2:
                        RetroField().run()
                    if event.key == pygame.K_ESCAPE:
                        running = False

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

    # -------------------------
    # MYCAREER SETUP
    # -------------------------

    def start_mycareer(self):
        """Create a custom player and begin MyCareer."""
        # Simple default player for now
        self.myplayer = create_custom_player(
            name="Qurise Backus",
            position="QB",
            age=21,
            overall=80
        )

        # Add player to a random team
        team = random.choice(self.teams)
        team.add_player(self.myplayer)

        # Create MyCareer object
        self.mycareer = MyCareer(self.league, self.myplayer)

        # Enter MyCareer menu
        self.mycareer_menu()

    # -------------------------
    # MYCAREER MENU
    # -------------------------

    def mycareer_menu(self):
        running = True
        while running:
            self.screen.fill((20, 0, 0))
            self.draw_text("MYCAREER MODE", 220, 20)

            self.draw_text("1. Play Full Season", 200, 100)
            self.draw_text("2. Request Trade", 200, 140)
            self.draw_text("3. View Career Summary", 200, 180)
            self.draw_text("4. Enter Retro Field", 200, 220)
            self.draw_text("ESC. Back to Main Menu", 200, 260)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        self.mycareer.play_full_season()
                    if event.key == pygame.K_2:
                        self.mycareer.request_trade()
                    if event.key == pygame.K_3:
                        self.show_career_summary()
                    if event.key == pygame.K_4:
                        RetroField().run()
                    if event.key == pygame.K_ESCAPE:
                        running = False

            pygame.display.flip()
            self.clock.tick(FPS)

    # -------------------------
    # CAREER SUMMARY SCREEN
    # -------------------------

    def show_career_summary(self):
        summary = self.mycareer.get_summary()

        viewing = True
        while viewing:
            self.screen.fill((0, 0, 0))
            self.draw_text("CAREER SUMMARY", 220, 20)

            y = 80
            for key, value in summary.items():
                self.draw_text(f"{key}: {value}", 40, y)
                y += 30

            self.draw_text("ESC to return", 40, SCREEN_HEIGHT - 40)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    viewing = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        viewing = False

            pygame.display.flip()
            self.clock.tick(FPS)


# =========================
# AUTO-START GAME
# =========================

if __name__ == "__main__":
    GameMenu().main_menu()

