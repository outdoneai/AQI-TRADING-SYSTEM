from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
import time
import json
from tradingagents.agents.utils.agent_utils import (
    get_news,
    get_reddit_sentiment,
    get_finnhub_sentiment,
    analyze_text_sentiment,
)
from tradingagents.dataflows.config import get_config


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        tools = [
            get_news,
            get_reddit_sentiment,
            get_finnhub_sentiment,
        ]

        system_message = (
            "You are a sentiment and market mood analyst tasked with analyzing public sentiment "
            "for a specific company using REAL data sources. You have access to:\n"
            "1. get_news(query, start_date, end_date) — News articles for sentiment tone analysis\n"
            "2. get_reddit_sentiment(ticker, look_back_days, limit) — Real Reddit posts from Indian investing subreddits\n"
            "3. get_finnhub_sentiment(ticker) — Market sentiment scores and analyst recommendations\n\n"
            "Your job is to synthesize sentiment from these REAL sources into a comprehensive report.\n\n"
            "CRITICAL RULES:\n"
            "1. ONLY report sentiment from data returned by the tools. Do NOT fabricate social media posts.\n"
            "2. If a tool returns 'UNAVAILABLE', state that clearly — do NOT make up data to fill the gap.\n"
            "3. Do NOT invent Twitter/X posts, Reddit discussions, or sentiment percentages.\n"
            "4. Quote actual post titles from Reddit data when available.\n"
            "5. Clearly attribute each data point to its source (Reddit, Finnhub, or News).\n"
            "6. If limited data is available, say so honestly. A short honest report is better than a long fabricated one.\n"
            "Do not simply state the trends are mixed, provide detailed and finegrained "
            "analysis and insights that may help traders make decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points.",
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. The current company we want to analyze is {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)

        try:
            result = chain.invoke(state["messages"])
        except Exception as e:
            error_report = f"[SENTIMENT ANALYSIS ERROR] Failed to generate sentiment report for {ticker}: {str(e)}"
            return {
                "messages": [AIMessage(content=error_report)],
                "sentiment_report": error_report,
            }

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
