import os
import discord
import requests
import asyncio
import json
from bs4 import BeautifulSoup

# ------------------- Zmienne środowiskowe -------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # możesz tu później dodać listę kanałów, jeśli chcesz

URL = "https://cyleria.pl/?subtopic=killstatistics"
DATA_FILE = "watched.json"  # plik do przechowywania listy śledzonych postaci

HEADERS = {
    "User-Agent": "Mozilla/5.0 (CyleriaBot; Discord death tracker)"
}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

last_seen = set()

# ------------------- Funkcje do persistencji -------------------
def load_watched():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except:
            print("Błąd wczytywania pliku watched.json")
    # defaultowe postacie
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

# ------------------- Zmienna globalna -------------------
WATCHED = load_watched()

# ------------------- Funkcje monitorowania -------------------
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

# ------------------- Pętla monitorowania -------------------
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

                player_kill = is_player(killer)
                msg = f"🕒 {time}\nZginął 🟢 **{name}** na poziomie {level} przez "
                if player_kill:
                    msg += f"🔴 **{killer}**"
                else:
                    msg += killer

                await channel.send(msg)
                last_seen.add(key)

            # ograniczenie ostatnich 300 wpisów
            if len(last_seen) > 300:
                last_seen = set(list(last_seen)[-300:])

        except Exception as e:
            print("ERROR pętli:", e)

        await asyncio.sleep(30)

# ------------------- Komendy Discord -------------------
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # !dodaj "Nick"
    if message.content.startswith('!dodaj'):
        try:
            nick = message.content.split('"')[1].strip()
        except IndexError:
            await message.channel.send("Błąd: użyj formatu `!dodaj \"Nick Postaci\"`")
            return

        if nick in WATCHED:
            await message.channel.send(f"{nick} już jest w śledzonych postaciach ✅")
        else:
            WATCHED.add(nick)
            save_watched()
            await message.channel.send(f"✅ Dodano {nick} do śledzonych postaci")

    # !usun "Nick"
    elif message.content.startswith('!usun'):
        try:
            nick = message.content.split('"')[1].strip()
        except IndexError:
            await message.channel.send("Błąd: użyj formatu `!usun \"Nick Postaci\"`")
            return

        if nick not in WATCHED:
            await message.channel.send(f"{nick} nie znajduje się w śledzonych postaciach ❌")
        else:
            WATCHED.remove(nick)
            save_watched()
            await message.channel.send(f"✅ Usunięto {nick} ze śledzonych postaci")

    # !lista – pokaż wszystkich w WATCHED
    elif message.content.startswith('!lista'):
        if not WATCHED:
            await message.channel.send("Brak śledzonych postaci ❌")
        else:
            lista_postaci = "\n".join(f"🟢 {nick}" for nick in sorted(WATCHED))
            await message.channel.send(f"**Śledzone postacie:**\n{lista_postaci}")

    # !info – pokaż wszystkie komendy i opis
    elif message.content.startswith('!info'):
        komendy = (
            "**Dostępne komendy bota:**\n"
            "1. `!dodaj \"Nick\"` – dodaje postać do listy śledzonych\n"
            "2. `!usun \"Nick\"` – usuwa postać ze śledzonych\n"
            "3. `!lista` – pokazuje wszystkie śledzone postacie\n"
            "4. `!info` – pokazuje wszystkie komendy i opis ich działania"
        )
        await message.channel.send(komendy)

# ------------------- Ready event -------------------
@client.event
async def on_ready():
    print("Bot zalogowany jako", client.user)
    channel = client.get_channel(CHANNEL_ID)
    
    # Powiadomienie startowe
    await channel.send("**Zgony v1.2.0** Rozpoczyna pracę.\nMonitoring Cylerii uruchomiony ✅")
    
    client.loop.create_task(check_loop())

# ------------------- Start bota -------------------
client.run(DISCORD_TOKEN)
