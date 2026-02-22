from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
import time
import json
from tradingagents.agents.utils.agent_utils import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_insider_transactions
from tradingagents.dataflows.config import get_config


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        system_message = (
            "You are a researcher tasked with analyzing fundamental information about a company. "
            "Please write a comprehensive report of the company's fundamental information such as "
            "financial documents, company profile, basic company financials, and company financial history "
            "to gain a full view of the company's fundamental information to inform traders. "
            "Make sure to include as much detail as possible. Do not simply state the trends are mixed, "
            "provide detailed and finegrained analysis and insights that may help traders make decisions."
            "\n\nCRITICAL RULES:"
            "\n1. ONLY report data that comes directly from Alöthe tool outputs. Do NOT invent or hallucinate any financial figures."
            "\n2. If a data point is missing from the tools, say 'Data not available' — do NOT guess."
            "\n3. When reporting ratios (D/E, P/E, etc.), use the exact values and labels from the tool output."
            "\n4. Do NOT fabricate analyst opinions, price targets, or fair value estimates unless the tool output contains them."
            "\n5. Clearly state whether the stock price is ABOVE or BELOW the 50-day and 200-day moving averages based on the data."
            "\n6. Do NOT claim the stock is 'near 52-week high' or 'near 52-week low' without calculating the actual percentage."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements.",
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
                    "For your reference, the current date is {current_date}. The company we want to look at is {ticker}",
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
            error_report = f"[FUNDAMENTALS ANALYSIS ERROR] Failed to generate fundamentals report for {ticker}: {str(e)}"
            return {
                "messages": [AIMessage(content=error_report)],
                "fundamentals_report": error_report,
            }

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
