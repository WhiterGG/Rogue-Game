from dataclasses import dataclass
from pathlib import Path

import pygame

from levels import LEVELS, SLIME_TYPES


ROOT = Path(__file__).resolve().parent
SCREEN_SIZE = (1280, 720)
HEART_COUNT = 5
HP_PER_HEART = 10
STEEL_SWORD_LEVEL = 4
SWORD_WINDUP = 0.2
SWORD_FLIGHT = 0.4
SLIME_LUNGE = 1
TRANSITION_TIME = 1.5


def load_sprite(path, size):
    image = pygame.image.load(str(ROOT / "Arts" / path)).convert_alpha()
    return pygame.transform.scale(image, (size, size))


@dataclass(eq=False)
class Slime:
    image: pygame.Surface
    rect: pygame.Rect
    hp: int
    damage: int


class Game:
    def __init__(self, screen):
        self.screen = screen
        background = pygame.image.load(str(ROOT / "Arts/Backgrounds/background.jpg"))
        self.background = pygame.transform.scale(background.convert(), SCREEN_SIZE)
        self.player = pygame.transform.flip(
            load_sprite("Characters/Main/Infantry.png", 100), True, False
        )
        self.player_attack = pygame.transform.flip(
            load_sprite("Characters/Main/Infantry_sheet.png", 100), True, False
        )
        self.player_rect = self.player.get_rect(bottomleft=(100, 555))
        self.idle_hand = (self.player_rect.x + 71, self.player_rect.y + 78)
        self.attack_hand = (self.player_rect.x + 76, self.player_rect.y + 76)
        self.sword_start = pygame.Vector2(self.attack_hand) + (8, -12)
        self.swords = {}
        for name in ("Wooden", "Steel"):
            sword = load_sprite(f"Swords/{name}_Sword.png", 44)
            self.swords[name] = sword.subsurface(sword.get_bounding_rect())
        self.heart = load_sprite("Interface/Heart.png", 32)
        self.empty_heart = load_sprite("Interface/Dead_Heart.png", 32)
        self.heart_bounds = self.heart.get_bounding_rect()
        self.slime_images = {}
        for kind, (filename, size, _) in SLIME_TYPES.items():
            image = load_sprite(f"Enemies/Slime/{filename}", size)
            self.slime_images[kind] = image.subsurface(image.get_bounding_rect())

        font_path = str(ROOT / "fonts/Oswald-VariableFont_wght.ttf")
        font = pygame.font.Font(font_path, 44)
        self.level_font = pygame.font.Font(font_path, 32)
        self.messages = {
            "transition": font.render("Переход на следующий уровень...", True, "white"),
            "defeat": font.render("Проигрыш", True, (255, 65, 65)),
            "victory": font.render("Победа!", True, (80, 220, 85)),
        }
        self.player_hp = HEART_COUNT * HP_PER_HEART
        self.level_index = 0
        self.start_level()

    def start_level(self):
        enemies = LEVELS[self.level_index]
        level_number = self.level_index + 1
        level_text = f"Уровень {level_number} / {len(LEVELS)}"
        self.level_label = self.level_font.render(level_text, True, "white")
        self.level_shadow = self.level_font.render(level_text, True, "black")
        if level_number >= STEEL_SWORD_LEVEL:
            self.sword = self.swords["Steel"]
            self.sword_damage = 2
        else:
            self.sword = self.swords["Wooden"]
            self.sword_damage = 1
        self.held_sword = pygame.transform.rotate(self.sword, -35)

        rows = (446, 502, 558, 614) if len(enemies) == 4 else (473, 543, 613)
        self.slimes = []
        for index, (kind, y) in enumerate(zip(enemies, rows)):
            image = self.slime_images[kind]
            rect = image.get_rect(midbottom=(958 + 130 * (index % 2), y))
            strength = SLIME_TYPES[kind][2]
            self.slimes.append(Slime(image, rect, strength, strength))

        self.selected = 0
        self.sword_target = None
        self.sword_time = 0.0
        self.attacker = None
        self.state = "fight"

    def handle_key(self, key):
        if self.state != "fight":
            return
        if key == pygame.K_UP:
            self.selected = (self.selected - 1) % len(self.slimes)
        elif key == pygame.K_DOWN:
            self.selected = (self.selected + 1) % len(self.slimes)
        elif key == pygame.K_SPACE and self.sword_target is None and self.attacker is None:
            self.sword_target = self.slimes[self.selected]
            self.sword_time = 0.0

    def update(self, dt):
        if self.state == "transition":
            self.transition_left -= dt
            if self.transition_left <= 0:
                self.level_index += 1
                self.start_level()
        elif self.state == "fight":
            if self.sword_target is not None:
                self.update_sword(dt)
            elif self.attacker is not None:
                self.update_slime_attack(dt)

    def update_sword(self, dt):
        self.sword_time += dt
        if self.sword_time < SWORD_WINDUP + SWORD_FLIGHT:
            return

        target = self.sword_target
        self.sword_target = None
        target.hp -= self.sword_damage
        if target.hp <= 0:
            defeated_index = self.slimes.index(target)
            self.slimes.pop(defeated_index)
            if defeated_index < self.selected:
                self.selected -= 1
            self.selected = min(self.selected, len(self.slimes) - 1)

        if self.slimes:
            self.attacker = max(self.slimes, key=lambda slime: slime.damage)
            self.slime_timer = SLIME_LUNGE
        elif self.level_index == len(LEVELS) - 1:
            self.state = "victory"
        else:
            self.state = "transition"
            self.transition_left = TRANSITION_TIME

    def update_slime_attack(self, dt):
        previous_time = self.slime_timer
        self.slime_timer -= dt
        if self.slime_timer <= SLIME_LUNGE / 2 < previous_time:
            self.player_hp = max(0, self.player_hp - self.attacker.damage)
            if self.player_hp == 0:
                self.state = "defeat"
        if self.slime_timer <= 0:
            self.attacker = None

    def slime_rect(self, slime):
        if slime is not self.attacker:
            return slime.rect

        progress = 1 - abs(2 * self.slime_timer / SLIME_LUNGE - 1)
        reach = progress * progress * (3 - 2 * progress)
        start = pygame.Vector2(slime.rect.midbottom)
        end = (self.player_rect.centerx + 20, self.player_rect.bottom)
        rect = slime.rect.copy()
        rect.midbottom = start.lerp(end, reach)
        return rect

    def draw_sword(self):
        if self.sword_target is None or self.sword_time < SWORD_WINDUP:
            return

        target = pygame.Vector2(self.slime_rect(self.sword_target).center)
        progress = (self.sword_time - SWORD_WINDUP) / SWORD_FLIGHT
        position = self.sword_start.lerp(target, progress)
        angle = (target - self.sword_start).angle_to((0, -1))
        sword = pygame.transform.rotate(self.sword, angle)
        self.screen.blit(sword, sword.get_rect(center=position))

    def draw_hearts(self):
        for index in range(HEART_COUNT):
            x, y = 14 + index * 35, 12
            self.screen.blit(self.empty_heart, (x, y))
            hp = self.player_hp - index * HP_PER_HEART
            if hp > 0:
                fill = self.heart_bounds.copy()
                fill.width = round(fill.width * min(hp, HP_PER_HEART) / HP_PER_HEART)
                self.screen.blit(self.heart, (x + fill.x, y + fill.y), fill)

    def draw(self):
        if self.state != "fight":
            self.screen.fill("black")
            message = self.messages[self.state]
            self.screen.blit(message, message.get_rect(center=self.screen.get_rect().center))
            return

        self.screen.blit(self.background, (0, 0))
        throwing = self.sword_target is not None
        pose = self.player_attack if throwing else self.player
        self.screen.blit(pose, self.player_rect)
        if not throwing or self.sword_time < SWORD_WINDUP:
            hand_x, hand_y = self.attack_hand if throwing else self.idle_hand
            grip = self.held_sword.get_rect(bottomleft=(hand_x - 4, hand_y + 5))
            self.screen.blit(self.held_sword, grip)

        for slime in self.slimes:
            self.screen.blit(slime.image, self.slime_rect(slime))

        target = self.slime_rect(self.slimes[self.selected])
        x, y = target.midtop
        marker = ((x - 8, y - 16), (x + 8, y - 16), (x, y - 7))
        pygame.draw.polygon(self.screen, (255, 231, 120), marker)
        pygame.draw.polygon(self.screen, (55, 39, 27), marker, 1)
        self.draw_sword()
        self.draw_hearts()

        label_rect = self.level_label.get_rect(midtop=(self.screen.get_rect().centerx, 10))
        self.screen.blit(self.level_shadow, label_rect.move(1, 2))
        self.screen.blit(self.level_label, label_rect)


def main():
    pygame.init()
    try:
        screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption("RogueLike Game")
        pygame.display.set_icon(pygame.image.load(str(ROOT / "Arts/Characters/Main/Infantry.png")))
        clock = pygame.time.Clock()
        game = Game(screen)

        while True:
            dt = min(clock.tick(60) / 1000, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    game.handle_key(event.key)

            game.update(dt)
            game.draw()
            pygame.display.flip()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()