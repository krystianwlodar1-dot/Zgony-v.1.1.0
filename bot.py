import os
import discord
import requests
import asyncio
import json
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

# ------------------- Zmienne środowiskowe -------------------
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

# ------------------- Link do postaci -------------------
def character_link(name):
    safe = quote_plus(name)
    return f"https://cyleria.pl/?subtopic=characters&name={safe}"

# ------------------- Funkcje do persistencji -------------------
def load_watched():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except:
            print("Błąd wczytywania pliku watched.json")
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
        print("Błąd zapisu watched.json:", e)

WATCHED = load_watched()

# ------------------- Logika -------------------
def is_player(killer):
    killer = killer.lower().strip()
    return not killer.startswith(("a ", "an ", "the "))

def get_deaths():
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print("Cyleria HTTP:", r.status_code)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        tbody = soup.find("tbody")
        if not tbody:
            print("Brak tbody – strona niedostępna?")
            return []

        deaths = []
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            time = tds[0].get_text(strip=True)
            text = tds[1].get_text(" ", strip=True)

            if "śmierć na poziomie" in text:
                parts = text.split("śmierć na poziomie")
                name = parts[0].strip()
                rest = parts[1].strip()
                if "przez" in rest:
                    level_str, killer = rest.split("przez", 1)
                else:
                    level_str, killer = rest, "Nieznany"
                level = level_str.strip()
                killer = killer.strip()
            else:
                name = text.split("przez")[0].strip()
                level = "?"
                killer = text.split("przez")[1].strip() if "przez" in text else "Nieznany"

            if name not in WATCHED:
                continue

            key = time + text
            deaths.append((key, time, name, level, killer))

        return deaths

    except Exception as e:
        print("Błąd połączenia z Cylerią:", e)
        return []

# ------------------- Pętla -------------------
async def check_loop():
    global last_seen
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    for key, *_ in get_deaths():
        last_seen.add(key)

    print("Monitor Cylerii uruchomiony")

    while True:
        try:
            deaths = get_deaths()
            for key, time, name, level, killer in reversed(deaths):
                if key in last_seen:
                    continue

                victim_url = character_link(name)
                killer_url = character_link(killer)

                player_kill = is_player(killer)

                msg = f"🕒 {time}\nZginął 🟢 **[{name}]({victim_url})** na poziomie {level} przez "

                if player_kill:
                    msg += f"🔴 **[{killer}]({killer_url})**"
                else:
                    msg += killer

                await channel.send(msg)
                last_seen.add(key)

            if len(last_seen) > 300:
                last_seen = set(list(last_seen)[-300:])

        except Exception as e:
            print("ERROR pętli:", e)

        await asyncio.sleep(30)

# ------------------- Komendy -------------------
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!dodaj'):
        try:
            nick = message.content.split('"')[1].strip()
        except IndexError:
            await message.channel.send("Użyj: `!dodaj \"Nick\"`")
            return

        if nick in WATCHED:
            await message.channel.send(f"{nick} już jest śledzony ✅")
        else:
            WATCHED.add(nick)
            save_watched()
            await message.channel.send(f"✅ Dodano {nick}")

    elif message.content.startswith('!usun'):
        try:
            nick = message.content.split('"')[1].strip()
        except IndexError:
            await message.channel.send("Użyj: `!usun \"Nick\"`")
            return

        if nick not in WATCHED:
            await message.channel.send(f"{nick} nie jest śledzony ❌")
        else:
            WATCHED.remove(nick)
            save_watched()
            await message.channel.send(f"✅ Usunięto {nick}")

    elif message.content.startswith('!lista'):
        if not WATCHED:
            await message.channel.send("Brak śledzonych postaci ❌")
        else:
            lista = "\n".join(f"🟢 {n}" for n in sorted(WATCHED))
            await message.channel.send(f"**Śledzone postacie:**\n{lista}")

    elif message.content.startswith('!info'):
        await message.channel.send(
            "**Zgony v1.3 – komendy:**\n"
            "`!dodaj \"Nick\"`\n"
            "`!usun \"Nick\"`\n"
            "`!lista`\n"
            "`!info`"
        )

# ------------------- Start -------------------
@client.event
async def on_ready():
    print("Bot zalogowany jako", client.user)
    channel = client.get_channel(CHANNEL_ID)
    await channel.send("**Zgony v1.3** uruchomiony 🩸\nLinki do profili aktywne ✅")
    client.loop.create_task(check_loop())

client.run(DISCORD_TOKEN)
