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
risk_evalute_instructions = """
You are a vendor risk analyst. You are given a factual news and filings
summary about one vendor. Classify the risk it indicates. Do not add facts
not in the summary.

## Scope
Risk means: money we have committed to this vendor — prepayments, open POs,
rebates, co-op funds, RMA credits — may not convert into goods we can sell,
because the vendor becomes financially unable to perform or legally or
physically unable to deliver.

In scope: the vendor's own finances, facilities, legal standing, ownership,
certifications, and ability to produce goods.

Out of scope: anything affecting goods in transit rather than the vendor
itself — port disruption, vessel incidents, carrier delays, freight rates,
weather — even when specific to this vendor and even when it delays our
cargo. A fire at the vendor's factory is in scope; an earthquake at a port
they ship through is not. Sector conditions and reputational news are out
unless they carry a direct financial or delivery consequence.

If the summary reports events but all of them are out of scope, score 1 and
say so. If the summary reports no events at all, score 0.

## Scale — highest level the evidence supports
0  No evidence available, or entity not confirmed.
1  No signal. Routine operations, profitable results, normal refinancing.
2  Early. Sector downturn, revenue decline without liquidity strain,
   ordinary leadership change, longer lead times, announced relocation.
3  Deteriorating. Sustained losses, negative operating cash flow, leverage
   near covenant limits, downgrade to or within speculative grade, drawn
   revolver, cost-cutting layoffs, asset sales for cash. Or: regulatory
   proceeding that could restrict import, certification under review,
   single-source shortage, ownership change announced.
4  Distressed or delivery impaired. Going-concern qualification, covenant
   breach or waiver, late statutory filing, auditor resignation,
   restructuring advisors engaged, missed interest payment, negative
   shareholders' equity, delisting notice on financial criteria, emergency
   discounted equity raise. Or: restricted-party listing (BIS, FCC Covered
   List, OFAC), UFLPA detention, plant closure or fire, lost certification,
   confirmed shipment delays, major recall.
5  Failed or stopped. Insolvency proceeding under any regime (Chapter 7/11,
   UK administration or CVA, German Insolvenzverfahren, French redressement
   or liquidation judiciaire, Japanese civil rehabilitation), receivership,
   payment default, liquidation, ceased trading. Or: import/export ban with
   no carve-out, ceased manufacturing, revoked authorization on currently
   shipping models.

## Rules
- Two or more distinct level-3 indicators score 4. Two or more level-4
  indicators score 5. Otherwise take the highest single level. Never average.
- Restrictions applying only to NEW models, where previously authorized
  goods may still be sold, score 4 not 5. Name the affected models and say
  whether existing inventory is exempt.
- Filings, exchange notices, court registers, restricted-party lists, rating
  actions, and the company's own statements about its condition are primary;
  score at face value. A single press source alleging a level-4 or 5
  condition caps at 3 pending confirmation.
- Nothing found scores 0, not 1 — an unwatched vendor must not look clean.
- Score only what the summary states. Judge the condition, not the tone.
  Do not weight by how much we buy.
- A refinancing that resolves a prior breach lowers the score. One that
  leaves a going-concern warning in place does not.
- The reason must state what happened, what it affects, and any carve-out.
  Name any event you excluded as out of scope and why.
"""

RISK_FLAG_THRESHOLD = 3
from openai import OpenAI
from pydantic import BaseModel, Field

class Risk_Decision(BaseModel):
    Risk_Reason: str = Field(
        description="One or two sentences naming the driving event and why it scores at that level. Must reference something stated in the summary."
    )
    Risk_level: int = Field(
        ge=0,
        le=5,
        description=(
            "0 no evidence available, or entity not confirmed. "
            "1 no signal, routine operations. "
            "2 early — sector downturn, revenue decline without liquidity strain. "
            "3 deteriorating — sustained losses, covenant pressure, regulatory "
            "proceeding, ownership change announced. "
            "4 distressed or delivery impaired — going-concern qualification, "
            "covenant breach, restricted-party listing, plant closure, lost "
            "certification. "
            "5 failed or stopped — insolvency proceeding, payment default, "
            "ceased trading, import/export ban with no carve-out. "
            "Take the highest level the evidence supports; never average."
        ),
    )
    @property
    def is_risk(self) -> bool:
        """True when the level is at or above the flag threshold."""
        return self.Risk_level >= RISK_FLAG_THRESHOLD
    
model = "gpt-5.6-terra"
search_only = create_static_tool_filter(allowed_tool_names=["tavily_search"])
research_results = {}

Risk_Analyst = Agent(
    name="Risk_Analyst",
    instructions=risk_evalute_instructions,
    model=model,
    output_type=Risk_Decision,
)

decisions = {}

async def evaluate_vendor(vendor: str, summary:str) -> str:
    risk_eval = f"""Classify supply risk for {vendor} using only the research summary below.
    Do not search or add facts that are not in the summary.

    ## Research summary
    {summary}
    """

    with trace("conversation"):
        print(f"Evaluating Risk for {vendor}")
        risk_result = await Runner.run(Risk_Analyst, risk_eval)
    return risk_result.final_output
