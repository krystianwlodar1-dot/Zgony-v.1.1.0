import os
import discord
import requests
import asyncio
import json
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

# ------------------- CONFIG -------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

URL = "https://cyleria.pl/?subtopic=killstatistics"
DATA_FILE = "watched.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (CyleriaBot; Discord death tracker)"
}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

last_seen = set()

# ------------------- LINK BUILDER -------------------
def character_link(name):
    safe = quote_plus(name)
    # <> blokuje generowanie embeda w Discordzie
    return f"<https://cyleria.pl/?subtopic=characters&name={safe}>"

# ------------------- WATCHED -------------------
def load_watched():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            print("Błąd wczytywania watched.json")

    return {
        "Agnieszka",
        "Miekka Parowka",
        "Gazowany Kompot",
        "Tapczan'ed",
        "Negocjator",
        "Astma",
        "Mistrz Negocjacji",
        "Jestem Karma",
        "Pan Trezer",
        "Negocjatorka"
    }

def save_watched():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(list(WATCHED), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Błąd zapisu:", e)

WATCHED = load_watched()

# ------------------- PARSING -------------------
def is_player(killer):
    killer = killer.lower().strip()
    return not killer.startswith(("a ", "an ", "the "))

def get_deaths():
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        tbody = soup.find("tbody")
        if not tbody:
            return []

        deaths = []
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            time = tds[0].get_text(strip=True)
            text = tds[1].get_text(" ", strip=True)

            if "śmierć na poziomie" in text:
                name, rest = text.split("śmierć na poziomie", 1)
                name = name.strip()
                if "przez" in rest:
                    level, killer = rest.split("przez", 1)
                else:
                    level, killer = rest, "Nieznany"
            else:
                parts = text.split("przez")
                name = parts[0].strip()
                level = "?"
                killer = parts[1].strip() if len(parts) > 1 else "Nieznany"

            if name not in WATCHED:
                continue

            key = time + text
            deaths.append((key, time, name, level.strip(), killer.strip()))

        return deaths

    except Exception as e:
        print("Błąd pobierania:", e)
        return []

# ------------------- LOOP -------------------
async def check_loop():
    global last_seen
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    for key, *_ in get_deaths():
        last_seen.add(key)

    print("Zgony v1.3 działa")

    while True:
        try:
            deaths = get_deaths()
            for key, time, name, level, killer in reversed(deaths):
                if key in last_seen:
                    continue

                victim_url = character_link(name)
                killer_url = character_link(killer)

                msg = f"🕒 {time}\nZginął 🟢 **[{name}]({victim_url})** na poziomie {level} przez "

                if is_player(killer):
                    msg += f"🔴 **[{killer}]({killer_url})**"
                else:
                    msg += killer

                # suppress_embeds = 100% brak kart
                await channel.send(msg, suppress_embeds=True)
                last_seen.add(key)

            if len(last_seen) > 300:
                last_seen = set(list(last_seen)[-300:])

        except Exception as e:
            print("Loop error:", e)

        await asyncio.sleep(30)

# ------------------- COMMANDS -------------------
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!dodaj'):
        try:
            nick = message.content.split('"')[1].strip()
        except:
            await message.channel.send('Użyj: `!dodaj "Nick"`')
            return

        if nick in WATCHED:
            await message.channel.send(f"{nick} już jest śledzony")
        else:
            WATCHED.add(nick)
            save_watched()
            await message.channel.send(f"✅ Dodano {nick}")

    elif message.content.startswith('!usun'):
        try:
            nick = message.content.split('"')[1].strip()
        except:
            await message.channel.send('Użyj: `!usun "Nick"`')
            return

        if nick not in WATCHED:
            await message.channel.send(f"{nick} nie jest śledzony")
        else:
            WATCHED.remove(nick)
            save_watched()
            await message.channel.send(f"✅ Usunięto {nick}")

    elif message.content.startswith('!lista'):
        if not WATCHED:
            await message.channel.send("Brak śledzonych postaci")
        else:
            await message.channel.send("**Śledzone:**\n" + "\n".join(WATCHED))

    elif message.content.startswith('!info'):
        await message.channel.send(
            "**Zgony v1.3**\n"
            "`!dodaj \"Nick\"`\n"
            "`!usun \"Nick\"`\n"
            "`!lista`\n"
            "Nicki w alertach są klikalne, bez kart Cylerii."
        )

# ------------------- START -------------------
@client.event
async def on_ready():
    print("Zalogowany jako", client.user)
    channel = client.get_channel(CHANNEL_ID)
    await channel.send("🩸 **Zgony v1.3 uruchomiony**\nLinki aktywne, embedy wyłączone.")
    client.loop.create_task(check_loop())

client.run(DISCORD_TOKEN)
