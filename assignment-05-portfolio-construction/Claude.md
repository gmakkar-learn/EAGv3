As part of assignment 5 of EAGv3, we are supposed to create an application
using a prompt. That prompt must align with the structure and constraints
provided in the local file meta_prompt.md.

I want to create a FASTapi based application that leverages Pydantic for clear
structure definitions.

The application automatically constructs an investment portfolio of 10 stocks
that are selected from the list of stocks present in the S&P500 universe.

The portfolio must be constructed to maximize Jensens Alpha for best risk
adjusted rewards.

The portfolio must also consider the phase of life that the investor is in.
The following should be selected from a drop down menu: Early investor (<5 yrs of working capital), Accelerate (upto 10 years), Growth (up to 20 years), Protect(up to 30 years) and Retirement (beyond 30 years). Risk is proportionally reduced and returns expectations are moderated as one goes from Early investor stage to Retirement stage.

The assumption is that higher volatility stocks that have delivered long term returns are good for an early investor. But for an investor in retirement, minimizing the maximum drawdown should also be a critical consideration, while generating alpha.

The goal should be to generate at least 4 percent from the Index, which is S&P500 performance.

Please create a prompt with the above specification, which I can review with you. Also please ask any clarifying questions before you generate the prompt. I need you to take the role of a professional grade investment advisor and research analyst when doing this deep analysis.
