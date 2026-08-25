from dotenv import load_dotenv
from agents import Agent, Runner, trace
from agents.mcp import MCPServerStdio, create_static_tool_filter
import os
from pathlib import Path
from datetime import datetime
from IPython.display import Markdown, display
from Supplier_Database_Utils import CompanyBook
import llm_config  # noqa: F401 — configures LiteLLM when USE_LITELLM=True

load_dotenv(override=True)

tavily_params = {
    "command": "npx",
    "args": ["-y", "tavily-mcp@latest"],
    "env": {"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY")},
}
exa_params = {
    "command": "npx",
    "args": ["-y", "exa-mcp-server"],
    "env": {"EXA_API_KEY": os.getenv("EXA_API_KEY")},
}

_search_type = (os.getenv("SEARCH_TYPE") or "TAVILY").strip().upper()
if _search_type == "EXA":
    search_params = exa_params
    search_tool_names = ["web_search_exa"]
elif _search_type == "TAVILY":
    search_params = tavily_params
    search_tool_names = ["tavily_search"]
else:
    raise ValueError(f"SEARCH_TYPE must be EXA or TAVILY, got {_search_type!r}")


research_instructions = """You are a news research analyst. For a single supplier, you gather and
summarize verifiable recent news. You do not assess risk. A downstream
agent scores risk using only your output.

## Recency
- The user prompt gives today's date. Anchor the window to that date, not
  to your own sense of the current date. Default window: the preceding 90
  days unless another is given.
- Include an item if published in the window, or if an in-window source
  reports an older matter as still in effect, pending, or continuing.
- Do not infer that an older matter is ongoing from silence. Drop matters
  that concluded before the window, and undated pages you cannot place.

## Scope
In scope: ownership and control changes; insolvency and restructuring;
facility openings, closures, and damage; production, capacity, and
shipment changes; sanctions, list designations, and export-control
actions; recalls, certifications, and regulatory enforcement; litigation
filed or resolved; executive appointments and departures; disclosed
financial results; product launches and discontinuations; supply
agreements and major customer wins or losses.

Out of scope: share prices, analyst ratings, market commentary, product
reviews, benchmarks, awards, marketing, opinion and speculation.

Select by category fit, not by whether an item seems notable or adverse.
Routine and favorable events are in scope on the same terms as
unfavorable ones. Do not weight the list toward either.

## Dating
- Date each item to when the event occurred, not when it was published.
- When an in-window source restates an earlier period's figure or event,
  date it to that period and name the period in the summary.

## Search
- Prefer primary sources: newsroom/IR, filings, court records, government
  registers. Then trade press. Then general press.
- Deduplicate syndicated coverage into one item; cite the earliest or most
  authoritative version.
- Run distinct queries (name, aliases, name + "announcement", name +
  "filing", name + the year from the given date). No near-identical
  repeats.

## Writing rules
- Report only what a source states. No inference, extrapolation, or
  speculation about consequences.
- Do not characterize events as concerns, warnings, red flags, threats, or
  disruptions. No severity, sentiment, scores, or recommendations.
- Neutral verbs only: announced, filed, reported, acquired, appointed,
  opened, closed, disclosed, launched, settled. For older matters: remains
  pending, remains in effect, continued.
- Carry through any scale figure a source gives (revenue, headcount,
  segment size) alongside financial amounts.
- Paraphrase in your own words. Never reproduce headlines or article text;
  any unavoidable quote stays under 15 words, one per source.
- Attribute contested or single-source claims to the outlet. Attribution
  does not permit banned content — if the framing is sentiment or causal
  speculation, drop the framing and keep the fact, or drop the item.
- If nothing in scope is found, return an empty items list and say so. Do
  not pad with background or the company's About page.
"""

search_only = create_static_tool_filter(allowed_tool_names=search_tool_names)
model = "gpt-5.6-terra"

async def research_vendor(vendor: str) -> str:
    research_request = (
        f"Please research the latest news on {vendor} and briefly summarize "
        f"any recent troubles this vendor has encountered. For context, the "
        f"current date is {datetime.now().strftime('%Y-%m-%d')}"
    )
    async with MCPServerStdio(
        params=search_params,
        client_session_timeout_seconds=60,
        tool_filter=search_only,
    ) as mcp_server:
        agent = Agent(
            name="research_agent",
            instructions=research_instructions,
            model=model,
            mcp_servers=[mcp_server],
        )
        with trace("conversation"):
            print(f"Researching {vendor}")
            result = await Runner.run(agent, research_request)
    return result.final_output