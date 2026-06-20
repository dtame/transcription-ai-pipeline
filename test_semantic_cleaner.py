from book.semantic_cleaner import clean_semantically

text = """
The church must understand artificial intelligence.
Many people are afraid of artificial intelligence.
Artificial intelligence is only a tool.
"""

print(clean_semantically(text))