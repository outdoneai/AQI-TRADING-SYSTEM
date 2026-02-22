"""Sentiment data tools — Real social media and market sentiment data.

Integrates:
- PRAW (Reddit) for r/IndianStockMarket, r/IndianStreetBets discussion
- Finnhub for market sentiment scores  
- pyFin-Sentiment for NLP analysis of financial text
"""

from typing import Annotated
from datetime import datetime, timedelta
import json


def get_reddit_sentiment(
    ticker: Annotated[str, "ticker symbol or company name to search"],
    look_back_days: Annotated[int, "number of days to look back"] = 7,
    limit: Annotated[int, "max number of posts to fetch"] = 25,
) -> str:
    """Fetch real Reddit posts about a stock from Indian investing subreddits.
    
    Searches r/IndianStockMarket, r/IndianStreetBets, r/IndiaInvestments.
    Returns actual post titles, scores, and comment counts.
    Requires: pip install praw
    """
    try:
        import praw
    except ImportError:
        return (
            "[REDDIT DATA UNAVAILABLE] praw not installed. "
            "Install with: pip install praw\n"
            "Then set environment variables: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT"
        )

    import os
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "AQI-Trading-Agent/1.0")

    if not client_id or not client_secret:
        return (
            "[REDDIT DATA UNAVAILABLE] Reddit API credentials not configured.\n"
            "Set environment variables: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET\n"
            "Get free credentials at: https://www.reddit.com/prefs/apps\n"
            "NOTE: Reddit API is FREE for personal/research use."
        )

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

        subreddits = ["IndianStockMarket", "IndianStreetBets", "IndiaInvestments"]
        all_posts = []

        # Clean ticker for search (remove .NS, .BO suffixes)
        search_term = ticker.replace(".NS", "").replace(".BO", "").upper()

        for sub_name in subreddits:
            try:
                subreddit = reddit.subreddit(sub_name)
                posts = subreddit.search(
                    search_term,
                    sort="relevance",
                    time_filter="week" if look_back_days <= 7 else "month",
                    limit=min(limit, 10),
                )
                for post in posts:
                    all_posts.append({
                        "subreddit": f"r/{sub_name}",
                        "title": post.title,
                        "score": post.score,
                        "upvote_ratio": post.upvote_ratio,
                        "num_comments": post.num_comments,
                        "created": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M"),
                        "url": f"https://reddit.com{post.permalink}",
                    })
            except Exception:
                continue

        if not all_posts:
            return f"[REDDIT] No recent posts found for '{search_term}' in Indian investing subreddits."

        # Sort by score (popularity)
        all_posts.sort(key=lambda x: x["score"], reverse=True)
        all_posts = all_posts[:limit]

        # Format output
        lines = [f"# Reddit Sentiment for {search_term}"]
        lines.append(f"# Searched: {', '.join(['r/' + s for s in subreddits])}")
        lines.append(f"# Posts found: {len(all_posts)}\n")

        bullish = 0
        bearish = 0

        for i, post in enumerate(all_posts, 1):
            lines.append(f"## Post {i} ({post['subreddit']}) — Score: {post['score']}, Comments: {post['num_comments']}")
            lines.append(f"Title: {post['title']}")
            lines.append(f"Date: {post['created']}, Upvote Ratio: {post['upvote_ratio']:.0%}")
            lines.append(f"URL: {post['url']}\n")

            # Simple keyword-based sentiment
            title_lower = post["title"].lower()
            if any(w in title_lower for w in ["buy", "bullish", "moon", "target", "breakout", "long", "accumulate", "undervalued"]):
                bullish += 1
            elif any(w in title_lower for w in ["sell", "bearish", "crash", "dump", "short", "overvalued", "avoid"]):
                bearish += 1

        total = bullish + bearish
        if total > 0:
            lines.append(f"\n## Quick Sentiment Summary")
            lines.append(f"Bullish posts: {bullish}/{len(all_posts)} ({bullish/len(all_posts)*100:.0f}%)")
            lines.append(f"Bearish posts: {bearish}/{len(all_posts)} ({bearish/len(all_posts)*100:.0f}%)")
            lines.append(f"Neutral/unclear: {len(all_posts) - total}/{len(all_posts)}")

        return "\n".join(lines)

    except Exception as e:
        return f"[REDDIT ERROR] Failed to fetch Reddit data: {str(e)}"


def get_finnhub_sentiment(
    ticker: Annotated[str, "ticker symbol to look up sentiment for"],
) -> str:
    """Fetch market sentiment scores from Finnhub (free API).
    
    Returns: insider sentiment, social sentiment, and recommendation trends.
    Requires: FINNHUB_API_KEY environment variable (free at finnhub.io)
    """
    import os
    api_key = os.environ.get("FINNHUB_API_KEY", "")

    if not api_key:
        return (
            "[FINNHUB DATA UNAVAILABLE] Finnhub API key not configured.\n"
            "Get a FREE API key at: https://finnhub.io/register\n"
            "Then set: FINNHUB_API_KEY environment variable.\n"
            "Free tier: 60 API calls/minute."
        )

    try:
        import requests
    except ImportError:
        return "[FINNHUB ERROR] requests library not installed."

    # Clean ticker — Finnhub uses different formats for Indian stocks
    clean_ticker = ticker.replace(".NS", "").replace(".BO", "")
    # Try both formats
    ticker_variants = [f"{clean_ticker}.NS", f"{clean_ticker}.BO", clean_ticker]

    lines = [f"# Finnhub Sentiment Data for {ticker}"]
    base_url = "https://finnhub.io/api/v1"
    data_found = False

    for t in ticker_variants:
        try:
            # Recommendation trends
            resp = requests.get(
                f"{base_url}/stock/recommendation",
                params={"symbol": t, "token": api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                recs = resp.json()
                if recs:
                    data_found = True
                    lines.append(f"\n## Analyst Recommendations (symbol: {t})")
                    for rec in recs[:3]:
                        lines.append(
                            f"Period: {rec.get('period', 'N/A')} — "
                            f"Buy: {rec.get('buy', 0)}, Hold: {rec.get('hold', 0)}, "
                            f"Sell: {rec.get('sell', 0)}, Strong Buy: {rec.get('strongBuy', 0)}, "
                            f"Strong Sell: {rec.get('strongSell', 0)}"
                        )
                    break

        except Exception:
            continue

    # Also try company news from finnhub
    for t in ticker_variants:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            resp = requests.get(
                f"{base_url}/company-news",
                params={"symbol": t, "from": week_ago, "to": today, "token": api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                news = resp.json()
                if news:
                    data_found = True
                    lines.append(f"\n## Finnhub News Sentiment ({len(news)} articles)")
                    for article in news[:10]:
                        lines.append(
                            f"- [{article.get('source', 'Unknown')}] {article.get('headline', 'No headline')} "
                            f"({article.get('datetime', 'N/A')})"
                        )
                    break
        except Exception:
            continue

    if not data_found:
        lines.append("\n[No Finnhub data found for this ticker. It may not be covered in Finnhub's free tier for Indian stocks.]")

    return "\n".join(lines)


def analyze_text_sentiment(
    text: Annotated[str, "financial text to analyze sentiment of (max 1000 chars)"],
) -> str:
    """Analyze the sentiment of financial text using pyFin-Sentiment NLP.
    
    Returns: bullish, bearish, or neutral classification.
    Requires: pip install pyFin-sentiment
    """
    # Truncate to avoid token issues
    text = text[:1000]

    try:
        from pyFin_sentiment.sentiment import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze(text)
        return f"Sentiment: {result} (analyzed by pyFin-Sentiment, trained on financial Twitter data)"
    except ImportError:
        # Fallback: simple keyword-based sentiment
        text_lower = text.lower()
        bullish_words = ["buy", "bullish", "growth", "profit", "beat", "strong", "outperform", 
                        "upgrade", "positive", "gain", "surge", "rally", "breakout", "opportunity"]
        bearish_words = ["sell", "bearish", "loss", "miss", "weak", "underperform", "downgrade",
                        "negative", "decline", "crash", "risk", "concern", "warning", "debt"]

        bull_count = sum(1 for w in bullish_words if w in text_lower)
        bear_count = sum(1 for w in bearish_words if w in text_lower)

        if bull_count > bear_count + 1:
            sentiment = "BULLISH"
        elif bear_count > bull_count + 1:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        return (
            f"Sentiment: {sentiment} (keyword-based fallback — "
            f"bullish signals: {bull_count}, bearish signals: {bear_count})\n"
            f"NOTE: Install pyFin-sentiment for ML-based analysis: pip install pyFin-sentiment"
        )
