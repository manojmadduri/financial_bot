import os
import discord
import requests
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import io
from dotenv import load_dotenv
from discord.ext import commands, tasks
import logging
import time
import sys
import warnings
import redis
import json
import redis
import aiohttp
import openai




# Load environment variables
# load_dotenv()

# DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
# UPDATE_CHANNEL_ID = os.getenv("UPDATE_CHANNEL_ID")
# AUTHORIZED_USER_IDS = os.getenv("AUTHORIZED_USER_IDS", "").split(",")
# AUTHORIZED_ROLES = os.getenv("AUTHORIZED_ROLES", "").split(",")
# BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")
# redis_url = os.getenv("REDIS_URL")

# FIN_MODEL_API_KEY = os.getenv("FIN_MODEL_API_KEY")

# openai.api_key = os.getenv("OPENAI_API_KEY")




DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")
UPDATE_CHANNEL_ID = os.environ.get("UPDATE_CHANNEL_ID")
AUTHORIZED_USER_IDS = os.environ.get("AUTHORIZED_USER_IDS", "").split(",")
AUTHORIZED_ROLES = os.environ.get("AUTHORIZED_ROLES", "").split(",")
BOT_OWNER_ID = os.environ.get("BOT_OWNER_ID")
FIN_MODEL_API_KEY = os.environ.get("FIN_MODEL_API_KEY")
openai.api_key = os.environ.get("OPENAI_API_KEY")




# # Step 1: Connect to Redis with Railway URL Handling
# redis_url = os.environ.get("REDIS_URL")
# if not redis_url or redis_url.strip() == "":
#     raise ValueError("[ERROR] REDIS_URL is not set or empty. Verify your Railway environment variables.")

# try:
#     redis_client = redis.from_url(redis_url)
#     redis_client.ping()  # Test the connection
#     print(f"[SUCCESS] Connected to Redis via Railway URL: {redis_url}")
# except redis.ConnectionError as e:
#     raise ConnectionError(f"[ERROR] Failed to connect to Redis from Railway URL. Error: {e}")
# except Exception as e:
#     raise ValueError(f"[ERROR] Unexpected error during Redis connection: {e}")
# # Step 2: Redis Functions Integration

# def add_user_watchlist(username, watchlist):
#     """Add or update user's watchlist."""
#     redis_client.hset(f"user:{username}", "watchlist", ",".join(watchlist))
#     return f"{username}'s watchlist updated: {', '.join(watchlist)}"

# def get_user_watchlist(username):
#     """Retrieve user's watchlist."""
#     watchlist = redis_client.hget(f"user:{username}", "watchlist")
#     return watchlist.decode("utf-8").split(",") if watchlist else []

# def add_user_portfolio(username, portfolio):
#     """Add or update user's portfolio."""
#     redis_client.hset(f"user:{username}", "portfolio", json.dumps(portfolio))
#     return f"{username}'s portfolio updated."

# def get_user_portfolio(username):
#     """Retrieve user's portfolio."""
#     portfolio = redis_client.hget(f"user:{username}", "portfolio")
#     return json.loads(portfolio) if portfolio else {}

# def add_user_alert(username, alert):
#     """Add or update user's price alert."""
#     redis_client.hset(f"user:{username}", "alerts", alert)
#     return f"{username}'s alert added."

# def get_user_alerts(username):
#     """Retrieve user's price alerts."""
#     alerts = redis_client.hget(f"user:{username}", "alerts")
#     return alerts.decode("utf-8") if alerts else "No alerts found."


AUTHORIZED_USER_IDS = [int(user_id) for user_id in AUTHORIZED_USER_IDS if user_id]

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

warnings.simplefilter(action='ignore', category=FutureWarning)

ALERTS_FILE = "price_alerts.csv"
PORTFOLIO_FILE = "portfolio.txt"
WATCHLIST_FOLDER = "watchlists"  # Folder to store user-specific watchlists
os.makedirs(WATCHLIST_FOLDER, exist_ok=True)

# Helper Functions
def get_env_list(var_name):
    value = os.getenv(var_name, "")
    return [item.strip() for item in value.split(",") if item.strip()]

AUTHORIZED_USER_IDS = [int(user_id) for user_id in get_env_list("AUTHORIZED_USER_IDS")]
AUTHORIZED_ROLES = get_env_list("AUTHORIZED_ROLES")

def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

logger = setup_logging()

# CoinGecko IDs mapping for common cryptocurrencies
COINGECKO_SYMBOL_MAP = {
    "BTC": "bitcoin",
    "BITCOIN": "bitcoin",
    "BTCUSD": "bitcoin",

    "ETH": "ethereum",
    "ETHEREUM": "ethereum",
    "ETHUSD": "ethereum",

    "DOGE": "dogecoin",
    "DOGECOIN": "dogecoin",

    "ADA": "cardano",
    "CARDANO": "cardano",

    "BNB": "binancecoin",
    "BINANCE": "binancecoin",

    "XRP": "ripple",
    "RIPPLE": "ripple",

    "SOL": "solana",
    "SOLANA": "solana",

    "DOT": "polkadot",
    "POLKADOT": "polkadot"
}



def is_authorized(ctx):
    if ctx.author.id in AUTHORIZED_USER_IDS:
        return True
    if any(role.name in AUTHORIZED_ROLES for role in ctx.author.roles):
        return True
    return False

def get_user_watchlist_file(ctx):
    username = ctx.author.name.replace(" ", "_")  # Replace spaces with underscores
    return os.path.join(WATCHLIST_FOLDER, f"watchlist_{username}_{ctx.author.id}.txt")

def is_bot_owner(ctx):
    return str(ctx.author.id) == BOT_OWNER_ID

@tasks.loop(minutes=240)
async def market_update():
    if not UPDATE_CHANNEL_ID:
        return
    channel = bot.get_channel(int(UPDATE_CHANNEL_ID))
    if not channel:
        logger.error("⚠️{ctx.author.mention} Market update channel not found.")
        return
    
    stock_symbol = "AAPL"
    stock_price = get_stock_price(stock_symbol)
    bitcoin_price = get_crypto_price("bitcoin")
    
    message = f"📊  **Market Update**\n📈 **AAPL**: ${stock_price}\n💰 **Bitcoin**: ${bitcoin_price} USD"
    await channel.send(message)

@bot.event
async def on_ready():
    logger.info(f"✅ Bot connected as {bot.user}")
    if UPDATE_CHANNEL_ID:
        market_update.start()
        check_price_alerts.start()

# @bot.command(name='stock', help='Get stock price. Usage: !stock SYMBOL')
# async def stock(ctx, symbol: str):
#     try:
#         price = get_stock_price(symbol)
#         await ctx.send(f"📈 {ctx.author.mention} **{symbol.upper()}** price: **${price}**")
#         logger.info(f"Stock price retrieved for {symbol}")
#     except Exception as e:
#         await ctx.send(f"⚠️ {ctx.author.mention} Error fetching stock data for {symbol}: {e}")
#         logger.error(f"Error fetching stock data for {symbol}: {e}")

# def get_stock_price(symbol):
#     try:
#         url = "https://www.alphavantage.co/query"
#         params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": ALPHA_VANTAGE_API_KEY}
#         response = requests.get(url, params=params, timeout=5)
#         response.raise_for_status()
#         data = response.json()
#         return data.get("Global Quote", {}).get("05. price", "N/A")
#     except requests.exceptions.RequestException as e:
#         logger.error(f"Error fetching stock price for {symbol}: {e}")
#         return "⚠️ Error fetching stock price"

# @bot.command(name='stock', help='Get stock price. Usage: !stock SYMBOL')
# async def stock(ctx, symbol: str):
#     try:
#         price = get_stock_price(symbol)
        
#         if price.startswith("❌") or price.startswith("⚠️"):
#             await ctx.send(f"{ctx.author.mention} {price}")
#         else:
#             await ctx.send(f"📈 {ctx.author.mention} **{symbol.upper()}** price: **{price}**")
#             logger.info(f"Stock price retrieved for {symbol}")

#     except Exception as e:
#         await ctx.send(f"⚠️ {ctx.author.mention} Error fetching stock data for {symbol}.")
#         logger.error(f"Error fetching stock data for {symbol}: {e}")

# def get_stock_price(symbol):
#     try:
#         stock = yf.Ticker(symbol)
#         stock_data = stock.history(period="1d")

#         # Check if stock data is empty
#         if stock_data.empty:
#             logger.error(f"No stock data available for {symbol}")
#             return "❌ Stock price unavailable. Try again later."

#         # Extract the latest closing price
#         stock_price = stock_data["Close"].iloc[-1]

#         return f"{stock_price:.2f}"  # Format to 2 decimal places

#     except Exception as e:
#         logger.error(f"Error fetching stock price for {symbol}: {e}")
#         return "⚠️ Error fetching stock price"

@bot.command(name='stock', help='Get detailed stock information. Usage: !stock SYMBOL')
async def stock(ctx, symbol: str):
    try:
        stock_info = get_stock_details(symbol)
        
        if stock_info.startswith("❌") or stock_info.startswith("⚠️"):
            await ctx.send(f"{ctx.author.mention} {stock_info}")
        else:
            await ctx.send(f"📊 {ctx.author.mention} {stock_info}")
            logger.info(f"Stock details retrieved for {symbol.upper()}")

    except Exception as e:
        await ctx.send(f"⚠️ {ctx.author.mention} Error fetching stock data for {symbol.upper()}.")
        logger.error(f"Error fetching stock data for {symbol.upper()}: {e}")

def get_stock_details(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info

        if not info or "regularMarketPrice" not in info:
            return "❌ Invalid stock symbol. Please check the ticker."

        name = info.get("shortName", symbol.upper())
        price = info.get("regularMarketPrice", "N/A")
        change = info.get("regularMarketChangePercent", 0.0)
        volume = info.get("regularMarketVolume", 0)
        market_cap = info.get("marketCap", 0)

        # Format numbers
        price_str = f"${price:,.2f}"
        change_str = f"{change:.2f}%"
        volume_str = f"{volume/1_000_000:.1f}M"  # Volume in millions
        market_cap_str = (
            f"${market_cap/1_000_000_000_000:.1f}T" if market_cap >= 1_000_000_000_000 
            else f"${market_cap/1_000_000_000:.1f}B"
        )

        return f"**{name} ({symbol.upper()})**\nPrice: {price_str} ({'+' if change >= 0 else ''}{change_str})\nVolume: {volume_str}\nMarket Cap: {market_cap_str}"

    except Exception as e:
        logger.error(f"Error fetching stock details for {symbol}: {e}")
        return "⚠️ Error fetching stock details"

# @bot.command(name='crypto', help='Get cryptocurrency price. Usage: !crypto COIN')
# async def crypto(ctx, coin: str):
#     try:
#         price = get_crypto_price(coin)
#         await ctx.send(f"💎 {ctx.author.mention} **{coin.capitalize()}** price: **${price} USD**")
#         logger.info(f"Crypto price retrieved for {coin}")
#     except Exception as e:
#         await ctx.send(f"⚠️ {ctx.author.mention} Error fetching crypto data for {coin}: {e}")
#         logger.error(f"Error fetching crypto data for {coin}: {e}")

# def get_crypto_price(coin):
#     url = "https://api.coingecko.com/api/v3/simple/price"
#     params = {"ids": coin.lower(), "vs_currencies": "usd"}
#     response = requests.get(url, params=params)
#     data = response.json()
#     return data.get(coin.lower(), {}).get("usd", "N/A")

@bot.command(name='crypto', help='Get cryptocurrency price. Usage: !crypto COIN')
async def crypto(ctx, coin: str):
    try:
        price = get_crypto_price(coin.upper())

        if price.startswith("❌") or price.startswith("⚠️"):
            await ctx.send(f"{ctx.author.mention} {price}")
        else:
            await ctx.send(f"💎 {ctx.author.mention} **{coin.upper()}** price: **{price} USD**")
            logger.info(f"Crypto price retrieved for {coin.upper()}")

    except Exception as e:
        await ctx.send(f"⚠️ {ctx.author.mention} Error fetching crypto data for {coin.upper()}.")
        logger.error(f"Error fetching crypto data for {coin.upper()}: {e}")

def get_crypto_price(symbol):
    """Fetch cryptocurrency price from CoinGecko API."""
    try:
        coin_id = COINGECKO_SYMBOL_MAP.get(symbol, symbol.lower())

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd"}

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if coin_id not in data:
            logger.error(f"Invalid cryptocurrency symbol: {symbol}")
            return "❌ Invalid cryptocurrency symbol. Please use a valid ticker."

        price = data[coin_id].get("usd")

        if not price:
            return "❌ Cryptocurrency price unavailable. Try again later."

        return f"{price:.2f}"

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching crypto price for {symbol}: {e}")
        return "⚠️ Error fetching crypto price"



@bot.command(name='chart', help='Generate stock price chart. Usage: !chart SYMBOL 30d')
async def chart(ctx, symbol: str, period: str = "30d"):
    try:
        symbol = symbol.upper()
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        if df.empty:
            await ctx.send(f"❌ {ctx.author.mention} No data available for {symbol}.")
            logger.info(f"No data available for {symbol}")
            return
        
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['Close'], label="Close Price", color='blue', linewidth=2)
        plt.plot(df.index, df['MA20'], label="20-Day MA", color='green', linestyle="--")
        plt.plot(df.index, df['MA50'], label="50-Day MA", color='red', linestyle="--")
        plt.title(f"{symbol} Stock Chart ({period})")
        plt.xlabel("Date")
        plt.ylabel("Price (USD)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()  # Optimize layout
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        await ctx.send(file=discord.File(fp=buf, filename=f"{symbol}_chart.png"))
        logger.info(f"Chart generated for {symbol}")
    except Exception as e:
        await ctx.send(f"⚠️ {ctx.author.mention} Error fetching stock data for {symbol}: {e}")
        logger.error(f"Error fetching stock data for {symbol}: {e}")


@bot.command(name='company', help='Get company details. Usage: !company SYMBOL')
async def company(ctx, symbol: str):
    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={FIN_MODEL_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data:
                    company_data = data[0]
                    name = company_data.get('companyName', 'N/A')
                    industry = company_data.get('industry', 'N/A')
                    sector = company_data.get('sector', 'N/A')
                    ceo = company_data.get('ceo', 'N/A')
                    website = company_data.get('website', 'N/A')
                    description = company_data.get('description', 'N/A')
                    market_cap = company_data.get('mktCap', 'N/A')
                    stock_price = company_data.get('price', 'N/A')

                    embed = discord.Embed(title=f"{name} ({symbol.upper()})", color=0x00ff00)
                    embed.add_field(name="**Industry**", value=industry, inline=True)
                    embed.add_field(name="**Sector**", value=sector, inline=True)
                    embed.add_field(name="**CEO**", value=ceo, inline=False)
                    embed.add_field(name="**Market Cap**", value=f"${market_cap:,.2f}", inline=True)
                    embed.add_field(name="**Stock Price**", value=f"${stock_price:,.2f}", inline=True)
                    embed.add_field(name="**Website**", value=f"[Visit Website]({website})", inline=False)
                    embed.add_field(name="**Description**", value=description[:1024], inline=False)

                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ {ctx.author.mention} No data found for that symbol.")
            else:
                await ctx.send("⚠️{ctx.author.mention} Error fetching data from the external API.")



@bot.command(name='historical', help='Get historical stock data. Usage: !historical SYMBOL 1y')
async def historical(ctx, symbol: str, period: str = "1y"):
    try:
        symbol = symbol.upper()
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        if df.empty:
            await ctx.send(f"❌ {ctx.author.mention} No historical data available for {symbol}.")
            logger.info(f"No historical data available for {symbol}")
            return

        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['Close'], label=f"{symbol} Close Price", color='blue', linewidth=2)
        plt.title(f"{symbol} Historical Price Data ({period})")
        plt.xlabel("Date")
        plt.ylabel("Price (USD)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        await ctx.send(file=discord.File(fp=buf, filename=f"{symbol}_historical_{period}.png"))
        logger.info(f"Historical chart generated for {symbol} ({period})")
    except Exception as e:
        await ctx.send(f"⚠️ {ctx.author.mention} Error fetching historical data for {symbol}: {e}")
        logger.error(f"Error fetching historical data for {symbol}: {e}")

# 

@bot.command(name='ask', help='Ask ChatGPT any financial or general question. Usage: !ask [your question]')
async def ask(ctx, *, question: str):
    try:
        await ctx.send(f"🧠 {ctx.author.mention} Thinking...")

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a helpful financial assistant."},
                    {"role": "user", "content": question}]
        )

        answer = response.choices[0].message['content']
        await ctx.send(f"💬 {ctx.author.mention} {answer}")

    except Exception as e:
        logger.error(f"Error with OpenAI API: {e}")
        await ctx.send(f"⚠️ Error fetching response from ChatGPT.")

@bot.command(name='set_alert', help='Set a price alert. Restricted to authorized users.')
async def set_alert(ctx, asset: str, price: float):
    if not is_authorized(ctx):
        await ctx.send(f"🚫 {ctx.author.mention} You need the 'Trusted' role to set alerts.")
        return
    try:
        with open(ALERTS_FILE, "a") as f:
            f.write(f"{asset.upper()},{price},{ctx.author.id}\n")
        await ctx.send(f"🔔 {ctx.author.mention} Alert set for {asset.upper()} at **${price:,.2f}**.")
        logger.info(f"Alert set for {asset.upper()} at ${price}")
    except Exception as e:
        await ctx.send(f"⚠️ {ctx.author.mention} Error setting alert for {asset}: {e}")
        logger.error(f"Error setting alert for {asset}: {e}")

@bot.command(name='remove_alert', help='Remove a price alert. Restricted to authorized users.')
async def remove_alert(ctx, asset: str):
    if not is_authorized(ctx):
        await ctx.send(f"🚫 {ctx.author.mention} You do not have permission to remove alerts.")
        return
    try:
        asset = asset.upper()
        if not os.path.isfile(ALERTS_FILE):
            await ctx.send(f"❌ {ctx.author.mention} No alerts found.")
            logger.info("No alerts found")
            return
        
        with open(ALERTS_FILE, "r") as f:
            alerts = [line for line in f if not line.startswith(f"{asset},")]

        with open(ALERTS_FILE, "w") as f:
            f.writelines(alerts)

        await ctx.send(f"❌ {ctx.author.mention} Alert removed for {asset}.")
        logger.info(f"Alert removed for {asset}")
    except Exception as e:
        await ctx.send(f"⚠️ {ctx.author.mention} Error removing alert for {asset}: {e}")
        logger.error(f"Error removing alert for {asset}: {e}")

def get_price(symbol):
    """Fetch stock or crypto price based on symbol."""
    try:
        if symbol in COINGECKO_SYMBOL_MAP:
            coin_id = COINGECKO_SYMBOL_MAP[symbol]
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": coin_id, "vs_currencies": "usd"}
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            return data[coin_id]['usd']
        else:
            stock = yf.Ticker(symbol)
            stock_data = stock.history(period="1d")
            if not stock_data.empty:
                return stock_data["Close"].iloc[-1]
            return None
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return None

@tasks.loop(seconds=30)  # Check alerts every 30 seconds
async def check_price_alerts():
    if not os.path.isfile(ALERTS_FILE):
        return

    with open(ALERTS_FILE, "r") as f:
        alerts = f.readlines()

    for alert in alerts:
        try:
            asset, price, user_id = alert.strip().split(",")
            current_price = get_price(asset)
            if current_price and float(current_price) >= float(price):
                user = await bot.fetch_user(int(user_id))
                await user.send(f"🚨 **Price Alert!** {asset} has reached ${current_price:,.2f}")
                logger.info(f"Alert triggered for {asset} at ${current_price}")
                
                # Remove the triggered alert
                alerts.remove(alert)
        except Exception as e:
            logger.error(f"Error processing alert: {e}")

    with open(ALERTS_FILE, "w") as f:
        f.writelines(alerts)


@bot.command(name='portfolio', help='Track your portfolio. Restricted to authorized users.')
async def portfolio(ctx, *stocks: str):
    if not is_authorized(ctx):
        await ctx.send("🚫{ctx.author.mention} You do not have permission to access the portfolio.")
        return
    if len(stocks) % 2 != 0:
        await ctx.send("❌ {ctx.author.mention} Please provide stock symbols and their quantities in pairs.")
        return
    
    total_value = 0
    portfolio_message = "📊 **Your Portfolio**:\n"
    
    for i in range(0, len(stocks), 2):
        symbol = stocks[i].upper()
        quantity = int(stocks[i+1])
        price = get_stock_price(symbol)
        if price == "⚠️ Error fetching stock price":
            portfolio_message += f"❌ {symbol}: Error fetching data\n"
        else:
            value = float(price) * quantity
            total_value += value
            portfolio_message += f"📈 {symbol}: {quantity} shares, ${price} each, Total: ${value:.2f}\n"
    
    portfolio_message += f"\n💰 **Total Portfolio Value**: ${total_value:.2f}"
    await ctx.send(portfolio_message)
    logger.info(f"Portfolio value calculated for {ctx.author.name}")

# Command: Manage watchlist
@bot.command(name='watchlist', help="Manage your personal watchlist. Usage: !watchlist add SYMBOL | !watchlist remove SYMBOL | !watchlist view")
async def watchlist(ctx, action: str, symbol: str = None):
    user_watchlist_file = get_user_watchlist_file(ctx)

    if action.lower() == "add":
        if not symbol:
            await ctx.send(f"❌ {ctx.author.mention}, please provide a stock or crypto symbol to add.")
            return
        symbol = symbol.upper()
        with open(user_watchlist_file, "a") as f:
            f.write(symbol + "\n")
        await ctx.send(f"✅ {ctx.author.mention}, {symbol} has been added to your watchlist!")

    elif action.lower() == "remove":
        if not symbol:
            await ctx.send(f"❌ {ctx.author.mention}, please provide a stock or crypto symbol to remove.")
            return
        symbol = symbol.upper()
        if not os.path.isfile(user_watchlist_file):
            await ctx.send(f"❌ {ctx.author.mention}, you don't have a watchlist yet.")
            return
        with open(user_watchlist_file, "r") as f:
            watchlist = [line.strip() for line in f.readlines()]
        if symbol not in watchlist:
            await ctx.send(f"❌ {ctx.author.mention}, {symbol} is not in your watchlist.")
            return
        watchlist.remove(symbol)
        with open(user_watchlist_file, "w") as f:
            for item in watchlist:
                f.write(item + "\n")
        await ctx.send(f"❌ {ctx.author.mention}, {symbol} has been removed from your watchlist.")

    elif action.lower() == "view":
        if not os.path.isfile(user_watchlist_file):
            await ctx.send(f"📋 {ctx.author.mention}, your watchlist is empty.")
            return
        with open(user_watchlist_file, "r") as f:
            watchlist = [line.strip() for line in f.readlines()]
        if not watchlist:
            await ctx.send(f"📋 {ctx.author.mention}, your watchlist is empty.")
            return

        message = f"📋 **{ctx.author.mention}, your watchlist:**\n"
        for symbol in watchlist:
            price = get_stock_price(symbol) if symbol.isalpha() else get_crypto_price(symbol)
            message += f"📌 **{symbol}** - {price}\n"

        await ctx.send(message)

    else:
        await ctx.send(f"❌ {ctx.author.mention}, invalid action. Use `!watchlist add SYMBOL`, `!watchlist remove SYMBOL`, or `!watchlist view`.")


@bot.command(name='botowner', help='Only the bot owner can use this command')
async def bot_owner(ctx):
    if not is_bot_owner(ctx):
        await ctx.send("🚫 {ctx.author.mention} You are not the bot owner. Access denied.")
        return
    await ctx.send("✅ {ctx.author.mention} You are the bot owner and can execute this command.")

@bot.command(name='adminonly', help='Only Admins can use this command')
async def admin_only(ctx):
    if not is_authorized(ctx):
        await ctx.send("🚫 {ctx.author.mention} You do not have admin privileges.")
        return
    await ctx.send("✅ {ctx.author.mention} Admin access granted.")

@bot.command(name='restricted', help='Restricted command for authorized users only')
async def restricted(ctx):
    if not is_authorized(ctx):
        await ctx.send("🚫 {ctx.author.mention} You are not authorized to use this command.")
        return
    await ctx.send("✅ {ctx.author.mention} You are an authorized user!")

@bot.command(name='news', help='Get latest news for a stock. Usage: !news SYMBOL')
async def news(ctx, symbol: str = None):
    if not symbol:
        await ctx.send("❌ {ctx.author.mention} Please provide a stock symbol. Example: `!news AAPL`")
        return
    url = f"https://newsapi.org/v2/everything?q={symbol}&apiKey=YOUR_NEWSAPI_KEY"
    response = requests.get(url).json()
    articles = response.get("articles", [])[:3]
    if articles:
        message = "\n".join([f"📰 {article['title']} - {article['url']}" for article in articles])
        await ctx.send(f" {ctx.author.mention}**Latest News for {symbol.upper()}:**\n{message}")
    else:
        await ctx.send(f"❌ {ctx.author.mention} No news found for {symbol.upper()}.")

@bot.command(name='commands', help='Display available commands')
async def custom_help(ctx):
    commands_list = "\n".join([f"`!{command.name}` - {command.help}" for command in bot.commands])
    await ctx.send(f"{ctx.author.mention} **Available Commands:**\n{commands_list}")


@bot.command(name="restart", help="Restart the bot (Bot Owner Only)")
async def restart(ctx):
    if not is_bot_owner(ctx):  # Restrict to bot owner
        await ctx.send("🚫 {ctx.author.mention} You do not have permission to restart the bot.")
        return
    
    await ctx.send("♻️ Restarting bot...")
    logger.info("♻️ Restarting bot...")
    
    python = sys.executable  # Get the Python executable
    os.execv(python, [python] + sys.argv)  # Restart the bot


# Task: Check watchlist updates every 30 minutes
@tasks.loop(minutes=30)
async def check_watchlist():
    """Checks all user watchlists and sends price updates."""
    if not os.path.exists(WATCHLIST_FOLDER):
        return

    for file_name in os.listdir(WATCHLIST_FOLDER):
        user_id = file_name.split("_")[-1].replace(".txt", "")
        user_watchlist_file = os.path.join(WATCHLIST_FOLDER, file_name)

        if not os.path.isfile(user_watchlist_file):
            continue

        with open(user_watchlist_file, "r") as f:
            watchlist = [line.strip() for line in f.readlines()]

        if watchlist:
            message = f"🔔 **Watchlist Update:**\n"
            for symbol in watchlist:
                price = get_stock_price(symbol) if symbol.isalpha() else get_crypto_price(symbol)
                message += f"📌 **{symbol}** - **${price}**\n"

            try:
                user = await bot.fetch_user(int(user_id))
                if user:
                    await user.send(message)
            except Exception as e:
                logger.error(f"Failed to send watchlist update to user {user_id}: {e}")


@bot.event
async def on_ready():
    """Bot startup event."""
    logger.info(f"✅ Bot connected as {bot.user}")
    check_watchlist.start() # Start periodic watchlist updates
    check_price_alerts.start()

bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)  # ✅ Runs only when executed directly
