#!/usr/bin/env python3
"""
Sunset ASCII Art Animation
Generates a colorful animated sunset using print() and time modules.
"""

import time
import sys

# ANSI color codes
COLORS = {
    'black': '\033[0m',
    'red': '\033[91m',
    'orange': '\033[33m',
    'yellow': '\033[34m',
    'green': '\033[32m',
    'blue': '\033[35m',
    'purple': '\033[36m',
    'bright_red': '\033[1;91m',
    'bright_orange': '\033[1;33m',
    'bright_yellow': '\033[1;34m',
    'bright_purple': '\033[1;36m',
}

def draw_sun(x, size=5):
    """Draw the sun at position x"""
    sun = ""
    for i in range(size, 0, -1):
        row = ""
        for j in range(i):
            color = COLORS['yellow'] if j < i // 2 else COLORS['orange']
            row += f"{color}{'*' if j % 2 == 0 else '.'}{COLORS['black']}"
        sun += row + "\n"
    return sun

def draw_mountain(x, height, size=5):
    """Draw a mountain at position x"""
    mountain = ""
    for row in range(1, height + 1):
        for col in range(size):
            if row * col >= size * row:
                char = "█"
                color = COLORS['bright_purple']
            elif row * col >= size * (row - 1):
                char = "▓"
                color = COLORS['purple']
            elif row * col >= size * (row - 2):
                char = "▒"
                color = COLORS['bright_orange']
            elif row * col >= size * (row - 3):
                char = "░"
                color = COLORS['orange']
            else:
                char = " "
                color = COLORS['black']
            mountain += f"{color}{char}{COLORS['black']}"
        mountain += "\n"
    return mountain

def draw_cloud(x, height):
    """Draw a cloud at position x"""
    cloud = ""
    for row in range(height):
        for col in range(5):
            if row == 0 and col in [0, 1, 2, 4]:
                char = " "
            elif row == 0 and col == 3:
                char = "."
            elif row == 1 and col in [0, 1, 2, 3]:
                char = "."
            else:
                char = " "
            cloud += f"{COLORS['bright_yellow']}{char}{COLORS['black']}"
        cloud += "\n"
    return cloud

def draw_sunset_phase(phase):
    """Draw sunset based on phase"""
    x = 15
    
    if phase == 0:  # Rising sun
        sun = draw_sun(x, 5)
        mountain = draw_mountain(x, 10, 5)
        cloud = draw_cloud(x, 3)
        return f"{sun}{mountain}{cloud}"
    
    elif phase == 1:  # Setting sun
        sun = draw_sun(x, 4)
        mountain = draw_mountain(x, 9, 5)
        cloud = draw_cloud(x, 3)
        return f"{sun}{mountain}{cloud}"
    
    elif phase == 2:  # Low sun
        sun = draw_sun(x, 3)
        mountain = draw_mountain(x, 8, 5)
        cloud = draw_cloud(x, 3)
        return f"{sun}{mountain}{cloud}"
    
    elif phase == 3:  # Twilight
        sun = draw_sun(x, 2)
        mountain = draw_mountain(x, 7, 5)
        cloud = draw_cloud(x, 3)
        return f"{sun}{mountain}{cloud}"
    
    elif phase == 4:  # Night
        sun = draw_sun(x, 1)
        mountain = draw_mountain(x, 6, 5)
        cloud = draw_cloud(x, 3)
        return f"{sun}{mountain}{cloud}"
    
    return ""

def animate():
    """Animate the sunset"""
    phases = ['☀', '🌅', '🌇', '🌆', '🌙']
    
    for i, phase in enumerate(range(5)):
        print(f"\n{draw_sunset_phase(phase)}")
        time.sleep(0.5)
        if i < len(phases) - 1:
            print(f"{phases[i]}", end='', flush=True)
            time.sleep(0.5)
        else:
            print(f"\n{phases[-1]}")
            time.sleep(2)

if __name__ == "__main__":
    print("=" * 80)
    print("SUNSET ASCII ART ANIMATION")
    print("=" * 80)
    print()
    
    try:
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            animate()
        else:
            print("Running in non-terminal mode...")
            for phase in range(5):
                print(draw_sunset_phase(phase))
                print()
                time.sleep(0.5)
    except Exception as e:
        print(f"Error: {e}")
