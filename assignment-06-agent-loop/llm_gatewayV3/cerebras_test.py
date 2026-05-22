# !pip install cerebras-cloud-sdk

  import os
  from cerebras.cloud.sdk import Cerebras

  client = Cerebras(
      api_key=os.environ.get("CEREBRAS_API_KEY")
  )

  completion = client.chat.completions.create(
      messages=[{"role":"user","content":"Why is fast inference important?"}],
      model="llama3.1-8b",
      max_completion_tokens=1024,
      temperature=0.2,
      top_p=1,
      stream=False
  )

  print(completion.choices[0].message.content)
