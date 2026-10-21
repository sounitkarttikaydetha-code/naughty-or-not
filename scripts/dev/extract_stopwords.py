import re

with open('temp_watchman/internal/prepare/union_stopwords.go', encoding='utf-8') as f:
    text = f.read()

words = re.findall(r'"([^"]+)",', text)
print('Extracted stopwords count:', len(words))
# Save as compact json
import json
with open('modules/engine/stopwords.json', 'w', encoding='utf-8') as out:
    json.dump(words, out)
print('Saved stopwords.json')
