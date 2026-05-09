import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI

# 載入 .env
load_dotenv()

# 建立 Gemini LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,
)

# 測試
result = llm.invoke("請用一句話介紹你自己")

print("LLM 測試成功")
print(result.content)